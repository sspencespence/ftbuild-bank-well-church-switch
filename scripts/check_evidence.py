#!/usr/bin/env python3
"""Mechanically check every model-read figure against its own document.

For text packets: the quote must appear in the packet (whitespace ignored) on the cited page, and the
value must appear inside the quote (as printed, e.g. 30,695 / (6,340) / 5,079 for £000). Scans can't be
checked this way - they are marked "scan_unverified" and rely on the blind second read.

Writes <in>.checked.jsonl with "checks": "passed" | "failed:<reason>" | "scan_unverified".

Usage: python scripts/check_evidence.py ~/bankwell-data/extract/out/pilot-*.jsonl
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bankwell_paths import DATA, EXTRACT, REGISTER  # noqa: E402




def squash(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


def page_text(regno: str, page: int | None) -> str | None:
    packet = EXTRACT / "packets" / f"{regno}.txt"
    if not packet.exists():
        return None
    text = packet.read_text(encoding="utf-8")
    if page is None:
        return text
    m = re.search(rf"^=== PAGE {page} ===$(.*?)(?=^=== PAGE \d+ ===$|\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


def value_in_quote(value: float, units: str | None, quote: str) -> bool:
    shown = abs(value) / 1000 if units == "£000" else abs(value)
    # compare against each printed number in the quote (pence dropped: 40,333.77 -> 40333)
    printed = {re.sub(r"[^\d]", "", n.split(".")[0]) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", quote)}
    return any(t in printed for t in {str(int(shown)), str(int(round(shown)))})


def check(rec: dict) -> str:
    if rec.get("value_gbp") is None and not rec.get("text_value"):
        return "blank"
    quote = rec.get("quote") or ""
    if not quote:
        return "failed:no_quote"
    text = page_text(str(rec["regno"]), rec.get("page"))
    if text is None:
        return "scan_unverified"
    if squash(quote) not in squash(text):
        whole = page_text(str(rec["regno"]), None) or ""
        return "failed:quote_on_other_page" if squash(quote) in squash(whole) else "failed:quote_not_in_document"
    if rec.get("value_gbp") is not None and not value_in_quote(float(rec["value_gbp"]), rec.get("units"), quote):
        return "failed:value_not_in_quote"
    return "passed"


def main() -> int:
    for name in sys.argv[1:]:
        path = Path(name)
        if path.name.endswith(".checked.jsonl"):
            continue
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            rows.append({**rec, "checks": check(rec)})
        path.with_suffix(".checked.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
