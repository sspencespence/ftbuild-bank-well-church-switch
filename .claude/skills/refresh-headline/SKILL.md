---
name: refresh-headline
description: Recompute the Bank Well headline numbers (churches with a verified bank, % ethical, cash by bank rating) from the current data, and check what changed. Use after any data refresh, before quoting a number publicly, or when someone asks where a headline figure came from.
---

# Recompute the headline

```bash
.venv/bin/python scripts/headline.py "Bankwell Data Analysis - with PDF figures.xlsx"               # current data
.venv/bin/python scripts/headline.py "Bankwell Data Analysis - with PDF figures.xlsx" --as-in-deck  # the 10 Oct pitch
```

The sheet comes from `merge_into_sheet.py` (see `extract-pdf-accounts`); the bank per church from
`$BANKWELL_DATA/share/bankwell_churches_matched.csv` (see `find-church-banks`).

## Definitions (keep them when you quote a number)

- **Verified bank** = the bank in the church's own accounts ("Bankers" line, first listed), else the bank
  behind the sort code on the church's own website. The team script's `principal_bank` column is **not** used:
  it is unverified, and including it inflated the worst-rated cash to £760m (vs £179m verified), driven by
  national bodies (e.g. Salvation Army International Trust) that aren't congregations.
- Excluded: rows flagged "linked charity" (the parent's figures) or "possibly not a church"; unrated banks (RBS).
- Cash = `assets_cash`: the official Charity Commission return where it exists, else the accepted PDF figure.
  Churches with no cash figure still count in the church numbers but add nothing to the £.

## The numbers

| | Pitch (10 Oct, `--as-in-deck`) | Current (with "Nat West" spelling fix) |
|---|---|---|
| Churches with a verified, rated bank | 3,827 (2,398 accounts + 1,429 sort codes) | 3,857 (2,428 + 1,429) |
| Ethical (rating 5) | 1,199 = 31% | 1,199 = 31% |
| Cash at worst-rated (1) banks | £178.7m (1,251 of 1,971 have cash; £121m PDFs + £57m official) | £180.4m |
| Cash at middling (3) | £62.1m | £62.1m |
| Cash at ethical (5) | £100.1m | £100.1m |

## Before quoting a number

1. Run both commands; if anything moved, say why (new data or a rule change) in HANDOVER.md.
2. Say "of the churches we could verify", never "of UK churches" — this is ~3.9k of ~31.7k registered churches,
   skewed to £25k–£500k income (see the sample cliff in HANDOVER.md). Extrapolating needs reweighting by income band.
