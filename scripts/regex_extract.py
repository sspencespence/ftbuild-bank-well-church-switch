#!/usr/bin/env python3
"""Pick the clear-cut figures out of text packets with anchors - no model, no guessing.

A figure is accepted only when it is unambiguous:
  - the line starts with a known label (e.g. "Cash at bank and in hand"),
  - after dropping a note number, exactly two amounts remain (this year, last year),
  - the page's year header reads newest-first (e.g. "2025 2024"),
  - the page is the main balance sheet / statement of assets (title in its first 15 lines),
  - the page is not in thousands (£000) and has no group/consolidated columns - those go to the model reader,
  - every matching line in the packet gives the same current-year value.
Everything else is left for the model reader. Each value keeps its exact line as the quote.

Usage:
    python scripts/regex_extract.py --extract ~/bankwell-data/extract
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

LABELS = {
    "assets_cash": re.compile(
        r"^(cash at bank( and| &) (in|on) hand|cash (in hand|at bank) and (at bank|in hand)|cash at bank"
        r"|total cash funds|cash and cash equivalents)\b", re.I),
    "assets_total": re.compile(r"^(total )?net assets(\s*/\s*\(?liabilities\)?)?\b(?!.*current)", re.I),
    "funds_total": re.compile(r"^total (charity |the charity'?s |unrestricted and restricted )?funds\b(?!.*brought)", re.I),
}
AMOUNT = re.compile(r"\(?-?£?\d[\d,]*\)?|(?<!\w)-(?!\w)")
YEARS = re.compile(r"\b(20\d\d)\b.*?\b(20\d\d)\b")
THOUSANDS = re.compile(r"'?000\b(?!,)|£k\b|£m\b|\bin thousands\b|\bmillions?\b", re.I)
MAIN_STATEMENT = re.compile(r"balance\s+sheet|statement\s+of\s+(assets|financial\s+position)", re.I)
GROUP = re.compile(r"\b(group|consolidated)\b", re.I)
FY_END = re.compile(
    r"(?:as at|year ended|period ended|year ending|ended)\s+(\d{1,2})(?:st|nd|rd|th)?\s+"
    r"(january|february|march|april|may|june|july|august|september|october|november|december)\s*,?\s+(20\d\d)", re.I)
MONTHS = "january february march april may june july august september october november december".split()


def parse_amount(token: str) -> float | None:
    if token.strip() == "-":
        return 0.0
    negative = token.startswith("(") or token.startswith("-")
    digits = re.sub(r"[^\d]", "", token)
    if not digits:
        return None
    return -float(digits) if negative else float(digits)


def amounts_after_label(line: str, label_end: int) -> list[float]:
    tokens = AMOUNT.findall(line[label_end:])
    values = [parse_amount(t) for t in tokens]
    values = [v for v in values if v is not None]
    # a leading 1-2 digit integer without a comma is a note reference ("Total funds  9  30,695  41,790")
    if len(values) == 3 and tokens and re.fullmatch(r"\d{1,2}", tokens[0]):
        values = values[1:]
    return values


def fy_end(text: str) -> str | None:
    m = FY_END.search(text)
    if not m:
        return None
    return f"{m.group(3)}-{MONTHS.index(m.group(2).lower()) + 1:02d}-{int(m.group(1)):02d}"


def pages_of(packet: str) -> list[tuple[int, str]]:
    parts = re.split(r"^=== PAGE (\d+) ===$", packet, flags=re.M)
    return [(int(parts[i]), parts[i + 1]) for i in range(1, len(parts) - 1, 2)]


def newest_first(page_text: str) -> bool:
    for line in page_text.splitlines():
        m = YEARS.search(line)
        if m and len(line.split()) <= 6:
            return int(m.group(1)) > int(m.group(2))
    return False


def extract(regno: str, packet: str) -> list[dict]:
    found: dict[str, list[dict]] = {}
    doc_fy = fy_end(packet)
    for page_no, text in pages_of(packet):
        header = "\n".join(text.splitlines()[:15])
        if (not MAIN_STATEMENT.search(header) or GROUP.search(text)
                or any(THOUSANDS.search(l) for l in text.splitlines() if len(l.split()) <= 6)
                or not newest_first(text)):
            continue
        for line in text.splitlines():
            stripped = line.strip()
            for field, label in LABELS.items():
                m = label.match(stripped)
                if not m:
                    continue
                values = amounts_after_label(stripped, m.end())
                if len(values) == 2:
                    found.setdefault(field, []).append({"value_gbp": values[0], "quote": stripped[:160],
                                                       "page": page_no, "fy_end": fy_end(text) or doc_fy})
                else:
                    found.setdefault(field, []).append({"ambiguous": True})
    rows = []
    for field, hits in found.items():
        values = {h.get("value_gbp") for h in hits}
        if len(values) == 1 and None not in values:
            rows.append({"regno": regno, "field": field, **hits[0], "method": "regex", "confidence": "high"})
    return rows


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--extract", default="~/bankwell-data/extract")
    args = p.parse_args()
    root = Path(args.extract).expanduser()
    n_docs = n_rows = 0
    with (root / "regex.jsonl").open("w", encoding="utf-8") as out:
        for packet in sorted((root / "packets").glob("*.txt")):
            rows = extract(packet.stem, packet.read_text(encoding="utf-8"))
            n_docs += 1
            n_rows += len(rows)
            for row in rows:
                out.write(json.dumps(row) + "\n")
    print(f"{n_docs} packets, {n_rows} figures accepted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
