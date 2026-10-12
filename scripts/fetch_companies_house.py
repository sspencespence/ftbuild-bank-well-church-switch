#!/usr/bin/env python3
"""Get the latest filed accounts for churches that are registered companies, from Companies House.

Why: the Charity Commission document store was failing on 9-10 Oct (504s, hidden download
links). Companies House holds the same accounts for charitable companies and was fast. Company
accounts usually carry a "Bankers" line on the company-information page.

For each church with a company number (largest income first) it:
  1. reads the Companies House filing history (accounts category) and takes the newest accounts,
  2. downloads the PDF (keeps sha256 + source URL + filing date for the capture path),
  3. tries the text layer and records a "Bankers" line with its page number and exact quote,
  4. if there is no text layer (a scan), renders pages 1-4 to PNG for a vision read later.

No LLM, no OCR. Personal data (trustee names) is never written to the manifest - only the
bank line. Resumable: re-running skips churches already settled in the manifest.

Usage:
    python scripts/fetch_companies_house.py --register data/raw/publicextract.charity.zip \
        --churches uk_churches.csv --out ~/bankwell-data/companies-house [--limit N] [--sample N]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import random
import re
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = "https://find-and-update.company-information.service.gov.uk"
USER_AGENT = "Mozilla/5.0 (compatible; bankwell-church-research/1.0; FaithTech BUILD 2026)"
DELAY_S = 1.2
TIMEOUT_S = 45
RENDER_PAGES = 4
RENDER_DPI = 90

ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
DOC_RE = re.compile(r'href="([^"]*/document\?format=pdf[^"]*)"')
BANKERS_RE = re.compile(r"(?im)^\s*(?:principal\s+)?bankers?\s*[:\-]?\s*(.{3,80})$")
SETTLED = {"text_bank_found", "text_no_bank", "scan_rendered", "no_accounts_filed"}


def _clean(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def load_company_numbers(register_zip: Path) -> dict[str, str]:
    csv.field_size_limit(10**9)
    with zipfile.ZipFile(register_zip) as z, z.open(z.namelist()[0]) as raw:
        reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace"), delimiter="\t")
        return {
            r["registered_charity_number"]: (r.get("charity_company_registration_number") or "").strip()
            for r in reader
            if r.get("linked_charity_number") == "0" and (r.get("charity_company_registration_number") or "").strip()
        }


def _income(row: dict) -> float:
    try:
        return float(row.get("income") or 0)
    except ValueError:
        return 0.0


def load_targets(churches_csv: Path, companies: dict[str, str], min_income: float) -> list[dict]:
    with churches_csv.open(encoding="utf-8", errors="replace") as fh:
        rows = list(csv.DictReader(fh))
    targets = []
    for row in rows:
        reg = (row.get("registered_number") or "").split(".")[0].strip()
        company = companies.get(reg)
        if company and not (row.get("principal_bank") or "").strip() and _income(row) > min_income:
            targets.append({"regno": reg, "company": company.zfill(8) if company.isdigit() else company,
                            "name": row.get("charity_name", ""), "income": _income(row)})
    return sorted(targets, key=lambda t: t["income"], reverse=True)


def latest_accounts(session: requests.Session, company: str) -> dict | None:
    """Newest accounts filing on the Companies House filing-history page."""
    r = session.get(f"{BASE}/company/{company}/filing-history?category=accounts", timeout=TIMEOUT_S)
    if r.status_code != 200:
        return {"error_http": r.status_code}
    for row in ROW_RE.findall(r.text):
        doc = DOC_RE.search(row)
        if not doc:
            continue
        cells = [c for c in (_clean(c) for c in CELL_RE.findall(row)) if c]
        # The page lists every filing type even with ?category=accounts - keep accounts only.
        if not any("accounts made up to" in c.lower() for c in cells):
            continue
        return {"filed": cells[0] if cells else "", "form": cells[1] if len(cells) > 1 else "",
                "description": cells[2] if len(cells) > 2 else "",
                "url": BASE + html.unescape(doc.group(1))}
    return None


def page_texts(pdf_bytes: bytes) -> list[str]:
    import pypdf  # imported lazily so --help works without it
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return [(p.extract_text() or "") for p in reader.pages]


def render(pdf_path: Path, out_dir: Path) -> list[str]:
    import pymupdf
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(pdf_path)
    names = []
    for i in range(min(RENDER_PAGES, doc.page_count)):
        name = f"p{i + 1}.png"
        doc[i].get_pixmap(dpi=RENDER_DPI).save(out_dir / name)
        names.append(name)
    return names


def process(session: requests.Session, target: dict, out: Path) -> dict:
    record = {**target, "ts": datetime.now(timezone.utc).isoformat(), "source": "companies_house"}
    filing = latest_accounts(session, target["company"])
    if filing is None:
        return {**record, "status": "no_accounts_filed"}
    if "error_http" in filing:
        return {**record, "status": "history_http_error", "http": filing["error_http"]}
    time.sleep(DELAY_S)
    pdf = session.get(filing["url"], timeout=TIMEOUT_S)
    if pdf.status_code != 200 or "pdf" not in pdf.headers.get("Content-Type", "").lower():
        return {**record, **filing, "status": "pdf_http_error", "http": pdf.status_code}

    pdf_path = out / "pdfs" / f"{target['regno']}_{target['company']}.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(pdf.content)
    base = {**record, "filing_date": filing["filed"], "form": filing["form"], "document": filing["description"],
            "source_url": filing["url"], "pdf": pdf_path.name, "sha256": hashlib.sha256(pdf.content).hexdigest(),
            "bytes": len(pdf.content)}

    texts = page_texts(pdf.content)
    if sum(len(t.strip()) for t in texts) > 200:
        for page_no, text in enumerate(texts, 1):
            m = BANKERS_RE.search(text)
            if m:
                return {**base, "status": "text_bank_found", "method": "text_layer", "page": page_no,
                        "quote": m.group(0).strip()[:120]}
        return {**base, "status": "text_no_bank", "method": "text_layer", "pages": len(texts)}

    images = render(pdf_path, out / "pages" / target["regno"])
    return {**base, "status": "scan_rendered", "method": "needs_vision", "images": images, "pages": len(texts)}


def run(args: argparse.Namespace) -> int:
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    manifest = out / "manifest.jsonl"
    done = set()
    if manifest.exists():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            if rec.get("status") in SETTLED:
                done.add(rec["regno"])
    targets = [t for t in load_targets(Path(args.churches), load_company_numbers(Path(args.register)), args.min_income)
               if t["regno"] not in done]
    if args.sample:
        targets = random.Random(42).sample(targets, min(args.sample, len(targets)))
    targets = targets[: args.limit]
    print(f"{len(done)} already done, {len(targets)} to fetch", flush=True)

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    with manifest.open("a", encoding="utf-8") as log:
        for i, target in enumerate(targets, 1):
            try:
                record = process(session, target, out)
            except Exception as exc:  # noqa: BLE001 - one bad filing must not stop the night
                record = {**target, "status": "error", "error": str(exc)[:200]}
            log.write(json.dumps(record) + "\n")
            log.flush()
            print(f"[{i}/{len(targets)}] {record['status']:<18} {target['regno']} {target['name'][:45]}", flush=True)
            time.sleep(DELAY_S)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--register", required=True)
    p.add_argument("--churches", default="uk_churches.csv")
    p.add_argument("--out", default="~/bankwell-data/companies-house")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--sample", type=int, default=None, help="random sample (seed 42) instead of largest-first")
    p.add_argument("--min-income", type=float, default=25000)
    return run(p.parse_args())


if __name__ == "__main__":
    sys.exit(main())
