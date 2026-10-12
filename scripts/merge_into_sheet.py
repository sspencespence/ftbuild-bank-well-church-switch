#!/usr/bin/env python3
"""Join the extracted church finances onto the team spreadsheet (a NEW copy - the original is never written).

Sheet: "UK Churches (from python script" tab, joined on registered_number.
  - Rows that already have official figures keep them (figures_source = official Part B return).
  - Empty assets_cash / funds_total / assets_total cells are filled from the PDF read, only when the
    figure is accepted:
        value printed + (evidence check passed, or a scan) + confidence not low + Opus re-read did not disagree.
    A failed evidence check is accepted only if the blind Opus re-read gives the same value.
  - Anything not accepted stays blank, with the reason in `flag`.
  - reserves from trustees' reports go in `reserves_stated_in_report` (never summed, never in `reserves`).
New columns: figures_source, fy_end, accounts_type, <field>_quote/_page, checks, second_read, confidence,
reserves_stated_in_report, bankers_from_accounts, bankers_quote, pdf_file, pdf_source_url, flag.

Usage:
    .venv/bin/python scripts/merge_into_sheet.py --sheet "Bankwell Data Analysis.xlsx" \
        --register data/raw/publicextract.charity.zip [--out "<same folder>/Bankwell Data Analysis - with PDF figures.xlsx"]
"""

from __future__ import annotations

import argparse
import collections
import csv
import glob
import io
import json
import re
import sys
import zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bankwell_paths import DATA, EXTRACT, REGISTER  # noqa: E402

E = EXTRACT
TAB = "UK Churches (from python script"
FIELDS = ("assets_cash", "funds_total", "assets_total")
NON_CHURCH = re.compile(
    r"\b(school|academy|college|universit|synagogue|jewish|mosque|islamic|muslim|hindu|sikh|gurdwara|temple|"
    r"buddhist|ymca|ywca|almshouse|hospice|housing|homes)\b", re.I)


def load_rows(pattern: str) -> dict[tuple[str, str], dict]:
    """Latest record per (regno, field) from JSONL outputs; uses .checked.jsonl when present."""
    rows = {}
    for f in sorted(glob.glob(pattern)):
        if f.endswith(".checked.jsonl"):
            continue
        checked = Path(f[: -len(".jsonl")] + ".checked.jsonl")
        for line in (checked if checked.exists() else Path(f)).read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("regno") and r.get("field"):
                rows[(str(r["regno"]), r["field"])] = r
    return rows


def same(a, b) -> bool:
    return a is not None and b is not None and abs(float(a) - float(b)) <= 1


def decide(first: dict | None, second: dict | None) -> tuple[float | None, str, str]:
    """Return (accepted value or None, second_read verdict, flag reason)."""
    if not first or first.get("value_gbp") is None:
        if second and second.get("value_gbp") is not None:
            return None, "only_second_read_found", "second read found a value the first missed - check by hand"
        return None, "not_checked" if not second else "agree_blank", ""
    v, checks = first["value_gbp"], str(first.get("checks", ""))
    verdict = "not_checked"
    if second:
        verdict = "agree" if same(v, second.get("value_gbp")) else "disagree"
    if verdict == "disagree":
        return None, verdict, f"readers disagree ({v:,.0f} vs {second.get('value_gbp')})"
    if first.get("confidence") == "low":
        return None, verdict, "low confidence"
    if checks.startswith("failed") and verdict != "agree":
        return None, verdict, f"evidence check {checks}"
    return float(v), verdict, ""


def linked_charity_names(register_zip: Path) -> dict[str, str]:
    csv.field_size_limit(10**9)
    main = {}
    with zipfile.ZipFile(register_zip) as z, z.open(z.namelist()[0]) as raw:
        for r in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace"), delimiter="\t"):
            if r["linked_charity_number"] == "0":
                main[r["registered_charity_number"]] = r["charity_name"].strip().upper()
    return main


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sheet", required=True)
    p.add_argument("--register", required=True)
    p.add_argument("--out")
    a = p.parse_args()
    src = Path(a.sheet)
    out = Path(a.out) if a.out else src.with_name(src.stem + " - with PDF figures.xlsx")
    if out.resolve() == src.resolve():
        sys.exit("refusing to overwrite the original spreadsheet")

    first = load_rows(str(E / "out" / "target-*.jsonl"))
    second = load_rows(str(E / "check" / "*.jsonl"))
    docs = {d["regno"]: d for d in map(json.loads, (E / "docs.jsonl").read_text().splitlines())}
    main_names = linked_charity_names(Path(a.register))

    import openpyxl
    from openpyxl.styles import Font, PatternFill
    yellow = PatternFill("solid", fgColor="FFFF00")      # a figure we filled in
    orange = PatternFill("solid", fgColor="FFC000")      # a flag: check before using
    blue = PatternFill("solid", fgColor="BDD7EE")        # header of a column we added
    wb = openpyxl.load_workbook(src)
    ws = wb[TAB]
    head = [c.value for c in ws[1]]
    col = {h: i + 1 for i, h in enumerate(head)}
    new_cols = ["figures_source", "fy_end", "accounts_type"] + [f"{f}_{k}" for f in FIELDS for k in ("quote", "page")] + [
        "checks", "second_read", "confidence", "reserves_stated_in_report", "bankers_from_accounts", "bankers_quote",
        "pdf_file", "pdf_source_url", "flag"]
    for name in new_cols:
        if name not in col:
            col[name] = ws.max_column + 1
            ws.cell(1, col[name], name)
        ws.cell(1, col[name]).fill = blue

    stats = collections.Counter()
    for row in range(2, ws.max_row + 1):
        regno = str(ws.cell(row, col["registered_number"]).value or "").split(".")[0]
        name = str(ws.cell(row, col["charity_name"]).value or "")
        flags = []
        if regno in main_names and main_names[regno] != name.strip().upper():
            flags.append(f"linked charity - figures are the parent's ({main_names[regno].title()})")
        if NON_CHURCH.search(name):
            flags.append("possibly not a church")
        has_official = ws.cell(row, col["assets_cash"]).value not in (None, "")
        if has_official:
            ws.cell(row, col["figures_source"], "official (Charity Commission annual return)")
            stats["official"] += 1
        elif regno in docs:
            d = docs[regno]
            verdicts, confidences, checks, any_value = [], [], [], False
            for f in FIELDS:
                r1, r2 = first.get((regno, f)), second.get((regno, f))
                value, verdict, why = decide(r1, r2)
                verdicts.append(f"{f}:{verdict}")
                if r1:
                    confidences.append(f"{f}:{r1.get('confidence')}")
                    checks.append(f"{f}:{r1.get('checks', 'n/a')}")
                    ws.cell(row, col["fy_end"], ws.cell(row, col["fy_end"]).value or r1.get("fy_end"))
                    ws.cell(row, col["accounts_type"], ws.cell(row, col["accounts_type"]).value or r1.get("accounts_type"))
                if why:
                    flags.append(f"{f}: {why}")
                if value is not None:
                    any_value = True
                    ws.cell(row, col[f], value).fill = yellow
                    ws.cell(row, col[f"{f}_quote"], (r1.get("quote") or "")[:160])
                    ws.cell(row, col[f"{f}_page"], r1.get("page"))
                    stats[f"filled_{f}"] += 1
            res, bank = first.get((regno, "reserves")), first.get((regno, "bankers"))
            if res and res.get("value_gbp") is not None:
                ws.cell(row, col["reserves_stated_in_report"], res["value_gbp"]).fill = yellow
            if bank and bank.get("text_value"):
                ws.cell(row, col["bankers_from_accounts"], bank["text_value"]).fill = yellow
                ws.cell(row, col["bankers_quote"], (bank.get("quote") or "")[:160])
                stats["bankers"] += 1
            read = any((regno, f) in first for f in FIELDS)
            ws.cell(row, col["figures_source"], ("PDF accounts read by Claude" if any_value else "PDF read - figures not found")
                    if read else "PDF not yet read")
            ws.cell(row, col["second_read"], "; ".join(verdicts) if read else None)
            ws.cell(row, col["confidence"], "; ".join(confidences) or None)
            ws.cell(row, col["checks"], "; ".join(checks) or None)
            ws.cell(row, col["pdf_file"], d["pdf"])
            ws.cell(row, col["pdf_source_url"], d.get("source_url"))
            stats["read" if read else "not_read_yet"] += 1
        else:
            ws.cell(row, col["figures_source"], "no accounts available")
        if flags:
            ws.cell(row, col["flag"], " | ".join(flags)).fill = orange
            stats["flagged_rows"] += 1

    if "READ ME - new figures" in wb.sheetnames:
        del wb["READ ME - new figures"]
    guide = wb.create_sheet("READ ME - new figures", 0)
    lines = [
        ("What changed in this copy", True),
        ("Tab 'UK Churches (from python script' - the only tab changed. All other tabs are untouched.", False),
        ("", False),
        ("YELLOW cell = a figure we filled in from the church's own accounts PDF (was blank before).", False),
        ("ORANGE cell (flag column) = check before using: e.g. a parent charity's figures, possibly not a church, "
         "or a figure held back because a check failed.", False),
        ("BLUE header = a column we added. Official Charity Commission figures that were already there are unchanged.", False),
        ("", False),
        ("How to check a yellow figure", True),
        ("1. Read <field>_quote and <field>_page - the exact line the number was copied from and its page.", False),
        ("2. Open pdf_source_url (Charity Commission / Companies House) or pdf_file, go to that page, compare.", False),
        ("3. checks: 'passed' = code confirmed the quote is in the PDF and contains the number; "
         "'scan_unverified' = scanned PDF (relies on the second read).", False),
        ("4. second_read: 'agree' = a second AI model re-read the PDF blind and got the same figure; "
         "'not_checked' = not in the re-read sample.", False),
        ("", False),
        ("Filter tips: figures_source = 'PDF accounts read by Claude' shows only rows with new figures. "
         "Exclude rows with a flag before totalling.", False),
        ("Definitions: assets_cash = 'cash at bank and in hand' (or total cash funds) for the latest year; "
         "funds_total = total funds; assets_total = NET assets. reserves_stated_in_report is as written in the "
         "trustees' report - do not sum.", False),
    ]
    for i, (text, bold) in enumerate(lines, 1):
        guide.cell(i, 1, text).font = Font(bold=bold, size=12 if bold else 11)
    guide.column_dimensions["A"].width = 140
    for r, fill in ((17, yellow), (18, orange), (19, blue)):
        guide.cell(r, 1, {17: "yellow = filled in by us", 18: "orange = flag, check first", 19: "blue = added column"}[r]).fill = fill
    wb.save(out)
    print(f"saved {out}")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
