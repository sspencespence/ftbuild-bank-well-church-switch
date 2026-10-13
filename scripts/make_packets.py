#!/usr/bin/env python3
"""Turn downloaded accounts PDFs into reading packets for the finance extraction.

Method: Bricksave lease_history_extraction (triage -> packet -> read with evidence).
For each church PDF it writes, under <out>/:
  packets/<regno>.txt   page-tagged layout text (text-layer PDFs), columns kept in place
  pages/<regno>/pN.png  rendered pages (scanned PDFs only)
  docs.jsonl            one line per document: regno, source, pdf, kind (text|scan), pages, income, band, kat

Only the pages likely to hold the figures go in a text packet (balance sheet, statement of assets,
reserves, bankers), so a reader sees ~2-6 pages, not 40.

Usage:
    .venv/bin/python scripts/make_packets.py --sheet "Bankwell Data Analysis.xlsx" \
        --data ~/bankwell-data --partb data/raw/publicextract.charity_annual_return_partb.zip
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

PAGE_HINT = re.compile(
    r"balance sheet|statement of (assets|financial position)|cash at bank|cash funds|bank balances?"
    r"|total funds|net assets|reserves|bankers?\b|receipts and payments",
    re.I,
)
SCAN_CHARS = 200  # fewer characters than this across the doc = scanned
MAX_TEXT_PAGES = 6
SCAN_RENDER_PAGES = 40
RENDER_DPI = 100


def layout_text(page) -> str:
    """Rebuild lines from word positions so table columns stay aligned."""
    words = page.get_text("words")
    rows: list[list] = []
    for w in sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0])):
        mid = (w[1] + w[3]) / 2
        if rows and abs(rows[-1][0] - mid) < 3:
            rows[-1][1].append(w)
        else:
            rows.append([mid, [w]])
    lines = []
    for _, ws in rows:
        line = ""
        for w in sorted(ws, key=lambda w: w[0]):
            col = int(w[0] / 4.5)
            line += " " * max(1 if line else 0, col - len(line)) + w[4]
        lines.append(line.rstrip())
    return "\n".join(lines)


def triage_one(job: dict) -> dict:
    try:
        return _triage(job)
    except Exception as exc:  # noqa: BLE001 - one broken/encrypted PDF must not stop the run
        return {**job["meta"], "kind": "unreadable", "error": str(exc)[:120]}


def _triage(job: dict) -> dict:
    import pymupdf

    out = Path(job["out"])
    try:
        doc = pymupdf.open(job["pdf_path"])
    except Exception as exc:  # noqa: BLE001 - a broken PDF is recorded, not fatal
        return {**job["meta"], "kind": "unreadable", "error": str(exc)[:120]}
    texts = [layout_text(p) for p in doc]
    meta = {**job["meta"], "pages": doc.page_count}
    if sum(len(t.strip()) for t in texts) < SCAN_CHARS:
        folder = out / "pages" / meta["regno"]
        folder.mkdir(parents=True, exist_ok=True)
        names = []
        for i in range(min(SCAN_RENDER_PAGES, doc.page_count)):
            name = f"p{i + 1}.png"
            doc[i].get_pixmap(dpi=RENDER_DPI).save(folder / name)
            names.append(name)
        return {**meta, "kind": "scan", "images": names}
    hits = [i for i, t in enumerate(texts) if PAGE_HINT.search(t)]
    # strongest pages first: balance sheet / statement of assets, then the rest
    strong = [i for i in hits if re.search(r"balance sheet|statement of assets|cash funds|cash at bank", texts[i], re.I)]
    keep = sorted(set(strong[:4] + [i for i in hits if i not in strong][: MAX_TEXT_PAGES - len(strong[:4])]))
    if not keep:
        keep = list(range(min(MAX_TEXT_PAGES, doc.page_count)))
    body = "\n".join(f"=== PAGE {i + 1} ===\n{texts[i]}" for i in keep)
    (out / "packets").mkdir(parents=True, exist_ok=True)
    (out / "packets" / f"{meta['regno']}.txt").write_text(
        json.dumps({k: meta[k] for k in ("regno", "name", "source", "pdf")}) + "\n" + body, encoding="utf-8")
    return {**meta, "kind": "text", "packet_pages": [i + 1 for i in keep]}


def band(income: float) -> str:
    return "100k-500k" if income > 1e5 else "25k-100k" if income > 25e3 else "under-25k"


def load_sheet(path: Path) -> dict[str, dict]:
    import openpyxl
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)["UK Churches (from python script"]
    rows = ws.iter_rows(values_only=True)
    head = next(rows)
    return {str(r[head.index("registered_number")]): dict(zip(head, r)) for r in rows}


def load_partb_regnos(path: Path) -> set[str]:
    csv.field_size_limit(10**9)
    with zipfile.ZipFile(path) as z, z.open(z.namelist()[0]) as raw:
        reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace"), delimiter="\t")
        return {r["registered_charity_number"] for r in reader if (r.get("assets_cash") or "").strip()}


def build_jobs(sheet: dict, data: Path, partb: set[str], out: Path) -> list[dict]:
    jobs, seen = [], set()
    sources = [("charity_commission", data / "manifest.jsonl", data / "pdfs"),
               ("companies_house", data / "companies-house" / "manifest.jsonl", data / "companies-house" / "pdfs")]
    for source, manifest, folder in sources:
        latest = {}
        for line in manifest.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            if rec.get("pdf") and (folder / rec["pdf"]).exists():
                latest[str(rec["regno"])] = rec
        for regno, rec in latest.items():
            row = sheet.get(regno)
            if not row or regno in seen:
                continue
            income = float(row.get("income") or 0)
            has_cash = row.get("assets_cash") not in (None, "")
            kat = regno in partb
            if has_cash and not kat:
                continue  # already filled and not usable as a test
            seen.add(regno)
            jobs.append({"pdf_path": str(folder / rec["pdf"]), "out": str(out), "meta": {
                "regno": regno, "name": row.get("charity_name") or "", "source": source, "pdf": rec["pdf"],
                "source_url": rec.get("source_url", ""), "income": income, "band": band(income),
                "kat": kat, "target": not has_cash}})
    return jobs


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sheet", required=True)
    p.add_argument("--data", default="~/bankwell-data")
    p.add_argument("--partb", required=True)
    p.add_argument("--out", default="~/bankwell-data/extract")
    p.add_argument("--workers", type=int, default=12)
    args = p.parse_args()
    data, out = Path(args.data).expanduser(), Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    jobs = build_jobs(load_sheet(Path(args.sheet)), data, load_partb_regnos(Path(args.partb)), out)
    print(f"{len(jobs)} documents to triage", flush=True)
    with ProcessPoolExecutor(args.workers) as pool, (out / "docs.jsonl").open("w", encoding="utf-8") as log:
        for i, rec in enumerate(pool.map(triage_one, jobs, chunksize=8), 1):
            log.write(json.dumps(rec) + "\n")
            if i % 500 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
