#!/usr/bin/env python3
"""Download the latest filed accounts PDF for each church, largest income first.

Overnight batch job: no LLM, no parsing. Resumable (re-run skips anything already in the
manifest), polite (fixed delay between requests), and it stops itself if the site starts
refusing requests.

Fixes the org-number bug in church_bank_cc_fill.py: the Charity Commission accounts page is
keyed by organisation_number, not registered_number (they differ for ~66% of churches).

Usage:
    python scripts/fetch_accounts.py --register data/raw/publicextract.charity.zip \
        --churches uk_churches.csv --out ~/bankwell-data [--limit N] [--min-income 25000]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import re
import sys
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests

ACCOUNTS_PAGE = (
    "https://register-of-charities.charitycommission.gov.uk/en/charity-search/-/charity-details/"
    "{org}/accounts-and-annual-returns"
    "?_uk_gov_ccew_onereg_charitydetails_web_portlet_CharityDetailsPortlet_organisationNumber={org}"
)
LINK_RE = re.compile(r'<a[^>]+class="[^"]*accounts-download-link[^"]*"[^>]+href="([^"]+)"', re.I)
OBJECTIVE_RE = re.compile(r"objectiveId=(A\d+)")
USER_AGENT = "Mozilla/5.0 (compatible; bankwell-church-research/1.0; FaithTech BUILD 2026)"
DELAY_S = 1.5
TIMEOUT_S = 60
MAX_PDF_BYTES = 25 * 1024 * 1024
MAX_CONSECUTIVE_FAILURES = 15  # blocking-type failures in a row -> stop rather than hammer
# Statuses that mean "this one document is slow or broken", not "we are blocked". They are
# retried on the next run but never count towards the stop rule.
SOFT_FAILURES = {"pdf_server_timeout", "pdf_http_error", "page_http_error", "links_hidden"}
BLOCK_HTTP = {403, 429}


def load_reg_to_org(register_zip: Path) -> dict[str, str]:
    """Map registered_charity_number -> organisation_number for main (non-linked) charities."""
    csv.field_size_limit(10**9)
    with zipfile.ZipFile(register_zip) as z:
        with z.open(z.namelist()[0]) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace"), delimiter="\t")
            return {
                row["registered_charity_number"]: row["organisation_number"]
                for row in reader
                if row.get("linked_charity_number") == "0"
            }


def _income(row: dict) -> float:
    try:
        return float(row.get("income") or 0)
    except ValueError:
        return 0.0


def load_targets(churches_csv: Path, reg_to_org: dict[str, str], min_income: float, max_income: float) -> list[dict]:
    """Churches without a bank yet, above the accounts-filing threshold, largest income first."""
    with churches_csv.open(encoding="utf-8", errors="replace") as fh:
        rows = list(csv.DictReader(fh))
    targets = []
    for row in rows:
        reg = (row.get("registered_number") or "").split(".")[0].strip()
        if (row.get("principal_bank") or "").strip() or not (min_income < _income(row) <= max_income):
            continue
        org = reg_to_org.get(reg)
        if org:
            targets.append({"regno": reg, "org": org, "name": row.get("charity_name", ""), "income": _income(row)})
    return sorted(targets, key=lambda t: t["income"], reverse=True)


def load_done(manifest: Path) -> set[str]:
    """Registered numbers already settled (downloaded, or confirmed to have no accounts)."""
    if not manifest.exists():
        return set()
    done = set()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("status") in {"ok", "too_large"}:  # no_accounts is re-checked: it may have been hidden links
            done.add(rec["regno"])
    return done


def fetch_one(session: requests.Session, target: dict, pdf_dir: Path) -> dict:
    """Fetch the accounts page, then the most recent PDF. Returns a manifest record."""
    record = {**target, "ts": datetime.now(timezone.utc).isoformat()}
    page = session.get(ACCOUNTS_PAGE.format(org=target["org"]), timeout=TIMEOUT_S)
    if page.status_code in BLOCK_HTTP:
        return {**record, "status": "blocked", "http": page.status_code}
    if page.status_code != 200:
        return {**record, "status": "page_http_error", "http": page.status_code}

    links = [html.unescape(h) for h in LINK_RE.findall(page.text)]
    if not links:
        # Filings listed but no Download links = the site is hiding links (document store down).
        # That is retryable, not "this charity has no accounts".
        if "Accounts and TAR" in page.text:
            return {**record, "status": "links_hidden"}
        return {**record, "status": "no_accounts"}

    latest = links[0]  # page lists filings newest first
    objective = OBJECTIVE_RE.search(latest)
    time.sleep(DELAY_S)
    pdf = session.get(latest, timeout=TIMEOUT_S)
    content_type = pdf.headers.get("Content-Type", "")
    if pdf.status_code in (502, 503, 504):
        return {**record, "status": "pdf_server_timeout", "http": pdf.status_code}
    if pdf.status_code in BLOCK_HTTP:
        return {**record, "status": "blocked", "http": pdf.status_code}
    if pdf.status_code != 200 or "pdf" not in content_type.lower():
        return {**record, "status": "pdf_http_error", "http": pdf.status_code, "content_type": content_type}
    if len(pdf.content) > MAX_PDF_BYTES:
        return {**record, "status": "too_large", "bytes": len(pdf.content)}

    path = pdf_dir / f"{target['regno']}_{objective.group(1) if objective else 'latest'}.pdf"
    path.write_bytes(pdf.content)
    return {
        **record,
        "status": "ok",
        "filings_listed": len(links),
        "pdf": path.name,
        "bytes": len(pdf.content),
        "sha256": hashlib.sha256(pdf.content).hexdigest(),
        "source_url": latest,
    }


def run(args: argparse.Namespace) -> int:
    out = Path(args.out).expanduser()
    pdf_dir = out / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    manifest = out / "manifest.jsonl"

    targets = load_targets(Path(args.churches), load_reg_to_org(Path(args.register)), args.min_income, args.max_income)
    done = load_done(manifest)
    todo = [t for t in targets if t["regno"] not in done][: args.limit]
    print(f"{len(targets)} targets, {len(done)} already done, {len(todo)} to fetch this run", flush=True)

    lock = threading.Lock()
    state = {"consecutive": 0, "count": 0, "stop": False}
    local = threading.local()

    def worker(target: dict) -> None:
        if state["stop"]:
            return
        if not hasattr(local, "session"):
            local.session = requests.Session()
            local.session.headers["User-Agent"] = USER_AGENT
        try:
            record = fetch_one(local.session, target, pdf_dir)
        except requests.Timeout as exc:
            record = {**target, "status": "pdf_server_timeout", "error": str(exc)[:200]}
        except requests.RequestException as exc:
            record = {**target, "status": "network_error", "error": str(exc)[:200]}
        record.setdefault("ts", datetime.now(timezone.utc).isoformat())
        with lock:
            log.write(json.dumps(record) + "\n")
            log.flush()
            state["count"] += 1
            ok = record["status"] in {"ok", "no_accounts", "too_large"}
            if ok:
                state["consecutive"] = 0
            elif record["status"] not in SOFT_FAILURES:
                state["consecutive"] += 1
            if state["count"] % 25 == 0 or record["status"] not in SOFT_FAILURES | {"ok", "no_accounts"}:
                print(f"[{state['count']}/{len(todo)}] {record['status']:<18} {target['regno']} {target['name'][:45]}", flush=True)
            if state["consecutive"] >= MAX_CONSECUTIVE_FAILURES:
                state["stop"] = True
        time.sleep(DELAY_S)

    with manifest.open("a", encoding="utf-8") as log:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(worker, todo))
    if state["stop"]:
        print(f"STOP: {state['consecutive']} blocking-type failures in a row. Re-run later to resume.", flush=True)
        return 2
    print("done", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--register", required=True, help="publicextract.charity.zip from the Charity Commission")
    parser.add_argument("--churches", default="uk_churches.csv")
    parser.add_argument("--out", default="~/bankwell-data")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=3, help="parallel downloads (keep small: be polite)")
    parser.add_argument("--min-income", type=float, default=25000)
    parser.add_argument("--max-income", type=float, default=float("inf"),
                        help="skip the very largest (often not churches; PDFs time out)")
    return run(parser.parse_args())


if __name__ == "__main__":
    sys.exit(main())
