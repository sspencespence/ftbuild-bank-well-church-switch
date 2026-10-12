#!/usr/bin/env python3
"""Write the full PDF-extraction result as CSV: one row per church whose accounts PDF was read.

Same acceptance rules as merge_into_sheet.py (decide()): a figure is written only when it passed the checks;
otherwise it is blank and the reason is in <field>_flag. Quotes are the balance-sheet line the figure came
from (8+ digit runs masked, in case an account number is on the line). No trustee or person names are
exported: the reserves/bankers quotes come from the trustees' report and are left out.

Usage:
    .venv/bin/python scripts/export_pdf_details.py --out results/pdf_extract_details.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from merge_into_sheet import E, FIELDS, decide, load_rows  # noqa: E402

MASK = re.compile(r"\d{8,}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    first = load_rows(str(E / "out" / "target-*.jsonl"))
    second = load_rows(str(E / "check" / "*.jsonl"))
    docs = {d["regno"]: d for d in map(json.loads, (E / "docs.jsonl").read_text().splitlines())}
    head = ["registered_number", "pdf_source", "pdf_kind", "fy_end", "accounts_type"]
    for f in FIELDS:
        head += [f, f"{f}_page", f"{f}_quote", f"{f}_confidence", f"{f}_evidence_check", f"{f}_second_read", f"{f}_flag"]
    head += ["reserves_stated_in_report", "bankers_from_accounts"]
    n, n_cash = 0, 0
    with open(a.out, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(head)
        for regno in sorted(docs, key=int):
            if not any((regno, f) in first for f in FIELDS):
                continue  # PDF prepared but never read (not in a target shard)
            any_rec = next(first[(regno, f)] for f in FIELDS if (regno, f) in first)
            row = [regno, docs[regno].get("source", ""), docs[regno].get("kind", ""), any_rec.get("fy_end", ""),
                   any_rec.get("accounts_type", "")]
            for f in FIELDS:
                r1, r2 = first.get((regno, f)), second.get((regno, f))
                value, verdict, flag = decide(r1, r2)
                r1 = r1 or {}
                row += ["" if value is None else (int(value) if float(value).is_integer() else value), r1.get("page", ""), MASK.sub("########", str(r1.get("quote") or "")),
                        r1.get("confidence", ""), r1.get("checks", ""), verdict, flag]
                n_cash += f == "assets_cash" and value is not None
            res, bank = first.get((regno, "reserves"), {}), first.get((regno, "bankers"), {})
            row += [res.get("value_gbp") if res.get("value_gbp") is not None else "", bank.get("text_value") or ""]
            w.writerow(row)
            n += 1
    print(f"wrote {a.out}: {n} churches, {n_cash} with accepted cash")
    return 0


if __name__ == "__main__":
    sys.exit(main())
