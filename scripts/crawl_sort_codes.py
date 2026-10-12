#!/usr/bin/env python3
"""Find each church's bank from the sort code on its website's giving/donate pages.

Overnight batch job: no LLM. For each church with a website (largest income first) it fetches
the homepage plus up to a few same-site pages whose link text or URL looks like giving /
donating / contact, and looks for a sort code written next to the words "sort code".

Privacy rule: account numbers are NEVER stored. Snippets are saved for evidence with every
run of 6+ digits masked, and only the sort code itself is kept as a field.

Resumable (re-run skips churches already in the output), respects robots.txt, one page at a
time per site with a delay, several sites in parallel.

Usage:
    python scripts/crawl_sort_codes.py --churches uk_churches.csv --out ~/bankwell-data [--limit N]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import requests

USER_AGENT = "Mozilla/5.0 (compatible; bankwell-church-research/1.0; FaithTech BUILD 2026)"
TIMEOUT_S = 12
PAGE_DELAY_S = 1.0
MAX_PAGES_PER_SITE = 6
MAX_BYTES = 3 * 1024 * 1024

GIVING_LINK_RE = re.compile(r"giv|donat|support|bank|tith|offering|generosity|contact|finance|pay", re.I)
HREF_RE = re.compile(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', re.I | re.S)
TAG_RE = re.compile(r"<script.*?</script>|<style.*?</style>|<[^>]+>", re.I | re.S)
SORT_CODE_RE = re.compile(
    r"sort[\s\-]*code\s*(?:no\.?|number)?\s*[:\-–]?\s*(\d{2})\s*[-–\s.]?\s*(\d{2})\s*[-–\s.]?\s*(\d{2})(?!\d)",
    re.I,
)
BANK_NAME_RE = re.compile(
    r"\b(Barclays|HSBC|NatWest|National Westminster|Lloyds|Santander|Halifax|TSB|Metro Bank|Nationwide|"
    r"Virgin Money|Co-?operative Bank|Co-op Bank|Triodos|CAF Bank|Unity Trust|Charity Bank|Handelsbanken|"
    r"Yorkshire Bank|Bank of Scotland|Ulster Bank|Clydesdale|Starling|Monzo|Tide)\b",
    re.I,
)
LONG_DIGITS_RE = re.compile(r"\d[\d\s]{5,}\d")


def mask(text: str) -> str:
    """Mask anything that could be an account number, keeping sort codes (dd-dd-dd) readable."""
    return LONG_DIGITS_RE.sub(lambda m: m.group(0) if re.fullmatch(r"\d{2}\s\d{2}\s\d{2}", m.group(0)) else "[masked]", text)


def page_text(html_text: str) -> str:
    return re.sub(r"\s+", " ", unescape(TAG_RE.sub(" ", html_text)))


def normalise_site(url: str) -> str | None:
    url = (url or "").strip()
    if not url or "@" in url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    host = urlparse(url).netloc
    return url if "." in host else None


def find_in_text(text: str) -> tuple[list[dict], list[str]]:
    codes = []
    for m in SORT_CODE_RE.finditer(text):
        code = "-".join(m.groups())
        snippet = mask(text[max(0, m.start() - 120): m.end() + 120])
        codes.append({"sort_code": code, "snippet": snippet})
    banks = sorted({b.group(1) for b in BANK_NAME_RE.finditer(text)}, key=str.lower)
    return codes, banks


class Site:
    def __init__(self, session: requests.Session, start: str):
        self.session = session
        self.start = start
        self.host = urlparse(start).netloc
        self.robots = robotparser.RobotFileParser()
        try:
            r = session.get(f"{urlparse(start).scheme}://{self.host}/robots.txt", timeout=TIMEOUT_S)
            self.robots.parse(r.text.splitlines() if r.status_code == 200 else [])
        except requests.RequestException:
            self.robots.parse([])

    def allowed(self, url: str) -> bool:
        return self.robots.can_fetch(USER_AGENT, url)

    def get(self, url: str) -> tuple[str, str] | None:
        if not self.allowed(url):
            return None
        r = self.session.get(url, timeout=TIMEOUT_S, stream=True)
        if r.status_code != 200 or "html" not in r.headers.get("Content-Type", ""):
            return None
        body = r.raw.read(MAX_BYTES, decode_content=True).decode(r.encoding or "utf-8", errors="replace")
        return r.url, body


def crawl_church(church: dict) -> dict:
    record = {**church, "ts": datetime.now(timezone.utc).isoformat()}
    start = normalise_site(church["website"])
    if not start:
        return {**record, "status": "bad_url"}
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    site = Site(session, start)
    if not site.allowed(start):
        return {**record, "status": "robots_disallowed"}

    queue, seen, pages_read = [start], set(), []
    found_codes: list[dict] = []
    bank_mentions: set[str] = set()
    while queue and len(seen) < MAX_PAGES_PER_SITE:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            got = site.get(url)
        except requests.RequestException:
            got = None
        time.sleep(PAGE_DELAY_S)
        if not got:
            continue
        final_url, body = got
        pages_read.append(final_url)
        codes, banks = find_in_text(page_text(body))
        found_codes += [{**c, "page": final_url} for c in codes]
        bank_mentions |= set(banks)
        if found_codes:
            break
        if url == start:  # only follow links from the homepage
            for href, label in HREF_RE.findall(body):
                link = urljoin(final_url, href.strip())
                if urlparse(link).netloc == urlparse(final_url).netloc and GIVING_LINK_RE.search(href + " " + label):
                    queue.append(link.split("#")[0])

    if not pages_read:
        return {**record, "status": "unreachable"}
    distinct = sorted({c["sort_code"] for c in found_codes})
    return {
        **record,
        "status": "sort_code_found" if distinct else "no_sort_code",
        "sort_codes": distinct,
        "evidence": found_codes[:3],
        "bank_mentions": sorted(bank_mentions),
        "pages_read": pages_read,
    }


def _income(row: dict) -> float:
    try:
        return float(row.get("income") or 0)
    except ValueError:
        return 0.0


def load_targets(churches_csv: Path, min_income: float, max_income: float) -> list[dict]:
    with churches_csv.open(encoding="utf-8", errors="replace") as fh:
        rows = list(csv.DictReader(fh))
    targets = [
        {"regno": (r.get("registered_number") or "").split(".")[0], "name": r.get("charity_name", ""),
         "income": _income(r), "website": (r.get("contact_web") or "").strip(),
         "bank_from_pdf": (r.get("principal_bank") or "").strip()}
        for r in rows if (r.get("contact_web") or "").strip() and min_income <= _income(r) <= max_income
    ]
    return sorted(targets, key=lambda t: t["income"], reverse=True)


def run(args: argparse.Namespace) -> int:
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    results = out / "sort_codes.jsonl"
    done = set()
    if results.exists():
        for line in results.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["regno"])
            except (json.JSONDecodeError, KeyError):
                continue
    todo = [t for t in load_targets(Path(args.churches), args.min_income, args.max_income) if t["regno"] not in done][: args.limit]
    print(f"{len(done)} already done, {len(todo)} to crawl this run", flush=True)

    lock = threading.Lock()
    counts = {"n": 0, "found": 0}

    def worker(church: dict) -> None:
        try:
            record = crawl_church(church)
        except Exception as exc:  # noqa: BLE001 - one bad site must not stop the night
            record = {**church, "status": "error", "error": str(exc)[:200]}
        with lock:
            log.write(json.dumps(record) + "\n")
            log.flush()
            counts["n"] += 1
            counts["found"] += record["status"] == "sort_code_found"
            if counts["n"] % 50 == 0:
                print(f"[{counts['n']}/{len(todo)}] sort codes found so far: {counts['found']}", flush=True)

    with results.open("a", encoding="utf-8") as log:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(worker, todo))
    print(f"done: {counts['found']} sort codes from {counts['n']} sites", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--churches", default="uk_churches.csv")
    parser.add_argument("--out", default="~/bankwell-data")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--min-income", type=float, default=0)
    parser.add_argument("--max-income", type=float, default=float("inf"))
    parser.add_argument("--workers", type=int, default=8, help="sites crawled in parallel (each site is sequential)")
    return run(parser.parse_args())


if __name__ == "__main__":
    sys.exit(main())
