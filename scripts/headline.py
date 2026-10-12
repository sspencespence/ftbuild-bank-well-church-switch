#!/usr/bin/env python3
"""The headline numbers: how many churches bank where, and how much cash sits at each rating.

"Verified" bank only (the pitch numbers):
  1. the "Bankers" line read from the church's own accounts (first bank listed), else
  2. the bank behind the sort code printed on the church's own website (single bank only).
  The team script's `principal_bank` is NOT used (unverified - it inflated the worst-rated total to £760m).
Dropped: rows flagged "linked charity" or "possibly not a church"; banks with no rating (RBS, unknown).
Cash = assets_cash (official Part B return, else accepted PDF figure); churches without cash still count.

Usage:
    .venv/bin/python scripts/headline.py "Bankwell Data Analysis - with PDF figures.xlsx" \
        [--matched "$BANKWELL_DATA/share/bankwell_churches_matched.csv"] [--as-in-deck]
--as-in-deck reproduces the 10 Oct pitch exactly (before the "Nat West" spelling fix: 3,827 / 31% / £179m).
"""
from __future__ import annotations

import argparse
import collections
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bank_ratings import RATINGS, rate  # noqa: E402
from bankwell_paths import DATA  # noqa: E402

TAB = "UK Churches (from python script"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sheet")
    p.add_argument("--matched", default=str(DATA / "share/bankwell_churches_matched.csv"))
    p.add_argument("--as-in-deck", action="store_true")
    a = p.parse_args()
    ratings = {k: v for k, v in RATINGS.items() if not (a.as_in_deck and k == "nat west")}
    import openpyxl
    sc = {r["charity_number"]: r["bank_from_sort_code"] for r in csv.DictReader(open(a.matched, encoding="utf-8-sig"))
          if r["bank_from_sort_code"] not in ("", "unknown") and ";" not in r["bank_from_sort_code"]}
    rows = openpyxl.load_workbook(a.sheet, read_only=True, data_only=True)[TAB].iter_rows(values_only=True)
    ix = {k: i for i, k in enumerate(next(rows))}
    n, cash, with_cash, src, unrated = (collections.Counter() for _ in range(5))
    cash_src = collections.Counter()
    for r in rows:
        flag = str(r[ix["flag"]] or "")
        if "linked charity" in flag or "not a church" in flag:
            continue
        reg, acc = str(r[ix["registered_number"]]).split(".")[0], r[ix["bankers_from_accounts"]]
        bank, how = (acc.split(";")[0], "accounts") if acc else (sc.get(reg), "sort code")
        if not bank:
            continue
        rt = rate(bank, ratings)
        if rt is None:
            unrated[how] += 1
            continue
        n[rt] += 1
        src[how] += 1
        c = r[ix["assets_cash"]]
        if c not in (None, ""):
            cash[rt] += float(c)
            with_cash[rt] += 1
            if rt == 1:
                cash_src["official" if str(r[ix["figures_source"]]).startswith("official") else "PDF"] += float(c)
    total = sum(n.values())
    label = {1: "worst (1)", 3: "middling (3)", 4: "rating 4", 5: "ethical (5)"}
    print(f"Churches with a verified, rated bank: {total:,}  (from accounts {src['accounts']:,} + "
          f"from sort codes {src['sort code']:,}; {sum(unrated.values())} more had an unrated bank, e.g. RBS)")
    print(f"Ethical (rating 5): {n[5]:,} = {100 * n[5] / total:.0f}%")
    for rt in sorted(n):
        print(f"  {label[rt]:<13} {n[rt]:>5} churches, {with_cash[rt]:>5} with cash, £{cash[rt] / 1e6:6.1f}m")
    print(f"Worst-rated cash: £{cash[1] / 1e6:.1f}m = £{cash_src['PDF'] / 1e6:.0f}m from PDFs + "
          f"£{cash_src['official'] / 1e6:.0f}m from official returns")
    return 0


if __name__ == "__main__":
    sys.exit(main())
