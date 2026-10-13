#!/usr/bin/env python3
"""Score extracted figures against the Charity Commission's own Part B figures (known answers).

A figure is matched to the Part B row for the same charity whose financial year end is within
10 days of the figure's fy_end. Correct = within £1 (or £1,000 when the accounts are in £000).
A figure with no matching Part B year is "unmatched" and not scored. "close" = within 2% (usually
group vs charity-only figures, or cash vs cash + deposits - a definition gap, not a misread).

Usage:
    python scripts/score_kat.py --partb data/raw/publicextract.charity_annual_return_partb.zip \
        ~/bankwell-data/extract/regex.jsonl [more.jsonl ...] [--only-regnos kat60.txt] [--wrong wrong.jsonl]
"""

from __future__ import annotations

import argparse
import collections
import csv
import io
import json
import sys
import zipfile
from datetime import date
from pathlib import Path

FIELD_TO_PARTB = {"assets_cash": "assets_cash", "funds_total": "funds_total",
                  "assets_total": "assets_total_assets_and_liabilities", "reserves": "reserves"}


def load_partb(path: Path) -> dict[str, list[dict]]:
    csv.field_size_limit(10**9)
    rows = collections.defaultdict(list)
    with zipfile.ZipFile(path) as z, z.open(z.namelist()[0]) as raw:
        for r in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace"), delimiter="\t"):
            rows[r["registered_charity_number"]].append(r)
    return rows


def to_date(text: str | None) -> date | None:
    try:
        return date.fromisoformat((text or "")[:10])
    except ValueError:
        return None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("files", nargs="+")
    p.add_argument("--partb", required=True)
    p.add_argument("--only-regnos")
    p.add_argument("--wrong", help="write wrong figures here for error analysis")
    args = p.parse_args()
    partb = load_partb(Path(args.partb))
    only = set(Path(args.only_regnos).read_text().split()) if args.only_regnos else None

    tally = collections.defaultdict(collections.Counter)
    wrong = []
    for f in args.files:
        for line in Path(f).expanduser().read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            field, regno = rec.get("field"), str(rec.get("regno"))
            if field not in FIELD_TO_PARTB or regno not in partb or (only and regno not in only):
                continue
            if rec.get("value_gbp") is None:
                tally[field]["blank"] += 1
                continue
            fy = to_date(rec.get("fy_end"))
            match = [r for r in partb[regno] if fy and (d := to_date(r["fin_period_end_date"])) and abs((d - fy).days) <= 10]
            if not match:
                tally[field]["unmatched_year"] += 1
                continue
            truth = float(match[0][FIELD_TO_PARTB[field]] or 0)
            tol = 1000 if rec.get("units") == "£000" else 1
            diff = abs(float(rec["value_gbp"]) - truth)
            if diff <= tol:
                tally[field]["correct"] += 1
            elif truth and diff / abs(truth) <= 0.02:
                tally[field]["close"] += 1  # within 2%: usually group vs charity-only, or cash vs cash+deposits
                wrong.append({**rec, "partb_value": truth, "verdict": "close"})
            else:
                tally[field]["wrong"] += 1
                wrong.append({**rec, "partb_value": truth, "verdict": "wrong"})

    print(f"{'field':<14}{'exact':>7}{'close':>7}{'wrong':>7}{'blank':>7}{'no year':>9}{'exact%':>8}{'wrong%':>8}")
    for field, c in sorted(tally.items()):
        scored = c["correct"] + c["close"] + c["wrong"]
        pct = lambda k: f"{100 * c[k] / scored:.1f}%" if scored else "-"
        print(f"{field:<14}{c['correct']:>7}{c['close']:>7}{c['wrong']:>7}{c['blank']:>7}{c['unmatched_year']:>9}"
              f"{pct('correct'):>8}{pct('wrong'):>8}")
    if args.wrong:
        Path(args.wrong).write_text("".join(json.dumps(w) + "\n" for w in wrong), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
