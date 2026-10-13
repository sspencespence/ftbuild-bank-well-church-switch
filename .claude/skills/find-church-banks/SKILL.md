---
name: find-church-banks
description: Find which bank each church uses from the sort code printed on its own website's giving page, map sort codes to banks without guessing, and rate the bank (bank.green). Use when refreshing bank data, adding churches, or checking how a church's bank was decided.
---

# Find each church's bank from its website sort code

Churches print bank details on "Give" / "Donate" pages. The sort code identifies the bank; we never keep
the account number.

## Steps

```bash
# 1. Crawl church websites (no model; resumable; robots.txt respected; account numbers masked at source)
python3 scripts/crawl_sort_codes.py --churches uk_churches.csv --out "$BANKWELL_DATA" --workers 8
#    OSM buildings with websites (see link-osm-churches): build a targets.csv with
#    registered_number,charity_name,contact_web,income,principal_bank (key "osm<N>") and run with
#    --churches targets.csv --out "$BANKWELL_DATA/osm-crawl" --workers 16
# 2. Sort code -> bank -> per-church bank (writes share/bankwell_churches_matched.csv + sortcode-banks/*.csv)
python3 scripts/build_church_banks.py
cp "$BANKWELL_DATA"/share/bankwell_churches_matched.csv "$BANKWELL_DATA"/sortcode-banks/sort_code_banks.csv results/
# 3. OSM buildings sheet (optional)
.venv/bin/python scripts/osm_sortcode_sheet.py osm_church_sort_codes.xlsx
```

## How a sort code becomes a bank (in order of trust)

| Method | Rule | Confidence |
|---|---|---|
| `tier2_bank_published` | the bank publishes the code (CAF 40-52-40, Unity 60-83-01, Triodos 16-58-10, Charity Bank 60-83-16, …) — `PUBLISHED` in the script; sources in `docs/sort-code-research.md` | high / medium |
| `tier1_page_consensus` | ≥2 church pages name the same bank next to that code, ≥80% agree | medium |
| `tier1_single_page` | one church page names the bank next to the code | low |
| `unknown_*` | nothing names it → left **unknown**. Never guessed from the digit range. | — |

A page only "votes" when it shows exactly one sort code and one bank name. A church with codes at more than
one bank → `several_banks` (hand check). `sort_code_page_shared_with` > 0 means a giving page used by several
churches (e.g. a circuit page) — 236 rows; hand check before trusting.

## Accuracy (10 Oct 2026)

2,401 churches with a sort code → 1,728 with one bank. Where the accounts also name a bank, 199 of 220
agree (90%). Most disagreements were churches with more than one account, plus a Royal Bank of Scotland /
Bank of Scotland mislabel — fixed (RBS is matched first and is **not rated**: it isn't in bank-ratings.md).

## Rating

`scripts/bank_ratings.py` is the only copy of the rating table (from `bank-ratings.md`, bank.green):
1 worst · 3 middling · 4 · 5 ethical. Import it — do not paste another copy (the "Nat West" spelling bug
came from copies drifting). Unknown banks are unrated, never defaulted.

## Related

The `sortcode-db` branch has a teammate's separate sort-code pipeline (`sortcodes/`, with tests and
`church_banks_extended.csv`). Compare before merging the two; both key on charity number.
