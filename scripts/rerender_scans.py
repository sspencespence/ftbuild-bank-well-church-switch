#!/usr/bin/env python3
"""Re-render every page (up to 40) of the scanned PDFs listed in docs.jsonl, so the reader can find the balance sheet."""
import json, sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bankwell_paths import DATA, EXTRACT, REGISTER  # noqa: E402

ROOT = DATA
MAX_PAGES, DPI = 40, 100


def render(rec: dict) -> str:
    import pymupdf
    folder = ROOT / ("pdfs" if rec["source"] == "charity_commission" else "companies-house/pdfs")
    try:
        doc = pymupdf.open(folder / rec["pdf"])
        out = EXTRACT / "pages" / rec["regno"]
        out.mkdir(parents=True, exist_ok=True)
        for i in range(min(MAX_PAGES, doc.page_count)):
            target = out / f"p{i + 1}.png"
            if not target.exists():
                doc[i].get_pixmap(dpi=DPI).save(target)
        return "ok"
    except Exception as exc:  # noqa: BLE001
        return f"error {rec['regno']}: {str(exc)[:80]}"


if __name__ == "__main__":
    scans = [r for r in map(json.loads, (EXTRACT / "docs.jsonl").read_text().splitlines())
             if r.get("kind") == "scan" and r.get("pages", 0) > 10]
    print(len(scans), "scans with more than 10 pages", flush=True)
    with ProcessPoolExecutor(12) as pool:
        for res in pool.map(render, scans, chunksize=4):
            if res != "ok":
                print(res, flush=True)
    print("done", flush=True)
    sys.exit(0)
