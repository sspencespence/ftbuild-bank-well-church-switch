---
name: extract-pdf-accounts
description: Download church accounts PDFs (Charity Commission + Companies House) and extract cash at bank, total funds, net assets, reserves and bankers with evidence, using Claude readers plus mechanical and blind second-read checks. Use when refreshing pdf_extract_final.csv, adding churches, or re-running after new accounts are filed.
---

# Extract figures from church accounts PDFs

**Why:** the Charity Commission's structured data (Part B) only has `assets_cash` for charities over £500k
income. For everyone else the figure is only in the filed accounts PDF. This pipeline reads those PDFs.

**Accuracy beats coverage.** A blank is fine; a wrong number is not. Every figure keeps its page and the
exact printed line, and is only accepted after checks (rules at the end).

## Before you start

- Inputs (not in git — download them):
  - `data/raw/publicextract.charity.zip` and `data/raw/publicextract.charity_annual_return_partb.zip` from the
    Charity Commission register extract: <https://register-of-charities.charitycommission.gov.uk/en/register/full-register-download>
  - `Bankwell Data Analysis.xlsx` — the team sheet (tab `UK Churches (from python script`), which decides
    which churches lack figures.
- `export BANKWELL_DATA=~/bankwell-data` (default). **Keep it outside the repo** — PDFs contain trustee names.
- Python deps: `uv venv .venv && uv pip install --python .venv/bin/python requests pypdf pymupdf openpyxl`.
- `claude` CLI logged in (the readers are headless `claude -p` runs).

## 1. Download (no model; resumable; polite)

```bash
python3 scripts/fetch_accounts.py --register data/raw/publicextract.charity.zip --churches uk_churches.csv \
    --out "$BANKWELL_DATA" --workers 3 --min-income 25000          # Charity Commission, largest income first
bash scripts/pdf_when_up.sh                                          # same, but waits until the CC document store answers
.venv/bin/python scripts/fetch_companies_house.py --register data/raw/publicextract.charity.zip \
    --out "$BANKWELL_DATA/companies-house"                          # churches that are companies
```
- CC accounts pages are keyed by **organisation number**, not charity number (differs for ~66%); the script handles it.
- 9–10 Oct 2026 the CC document store failed (504s after 30 s, hidden download links, then down from 09:10).
  That is why the £150k–£500k band is thin — see HANDOVER.md "sample cliff". Re-run to fill it; it skips done files.
- Companies House was fast and reliable — prefer it for company-churches.

## 2. Prepare packets

```bash
.venv/bin/python scripts/make_packets.py --sheet "Bankwell Data Analysis.xlsx" --data "$BANKWELL_DATA" \
    --partb data/raw/publicextract.charity_annual_return_partb.zip --workers 12
.venv/bin/python scripts/rerender_scans.py          # scans: render up to 40 pages (balance sheet is often past p10)
.venv/bin/python scripts/regex_extract.py           # optional cross-check: clear-cut lines only, no model
```
Triage: text-layer PDFs → page-tagged layout text (only the likely pages); scans → page PNGs.

## 3. Pilot on known answers (do this before any big run)

```bash
.venv/bin/python scripts/make_shards.py --set pilot        # 60 docs that DO have official Part B figures
bash scripts/run_workers.sh "shards/pilot-*.txt" 4 sonnet
E="$BANKWELL_DATA/extract"
.venv/bin/python scripts/check_evidence.py $E/out/pilot-*.jsonl
.venv/bin/python scripts/score_kat.py --partb data/raw/publicextract.charity_annual_return_partb.zip $E/out/pilot-*.checked.jsonl
```
Our pilot: cash 16/18 exact (both misses traced to errors in the official data), total funds 23/23, net
assets 18/18, **reserves 6/14 → reserves are never used in totals.** If cash/funds drop below ~90% exact, stop
and fix the prompt (`scripts/worker-prompt.md`) before scaling.

## 4. Full run

```bash
.venv/bin/python scripts/make_shards.py --set target       # missing-figure churches; £100k–500k first; text before scans
bash scripts/run_target.sh                                  # 6 Sonnet workers, effort medium; resumable
REVERSE=1 bash scripts/run_workers.sh "shards/target-*.txt" 3 sonnet   # optional 2nd runner from the other end
bash scripts/progress.sh                                    # % done
```
Workers get `Read` + `Edit` limited to the output folder only. Each shard is small (more careful reading).

## 5. Check

```bash
.venv/bin/python scripts/check_evidence.py $E/out/target-*.jsonl            # quote on the page? value in the quote?
.venv/bin/python scripts/make_check_shards.py target-100k-500k-text          # random 10% + every flagged doc
bash scripts/run_workers.sh "shards/check-target-100k-500k-text-*.txt" 2 opus "" check high
.venv/bin/python scripts/check_evidence.py $E/check/*.jsonl
```
The Opus re-read uses the **same prompt and never sees the first answers** (blind). Our result: 1,349/1,354
figures agree (99.6%); evidence check passed 92–93%.

## 6. Export

```bash
.venv/bin/python scripts/export_pdf_csv.py --sheet "Bankwell Data Analysis.xlsx" --out results/pdf_extract_final.csv
.venv/bin/python scripts/export_pdf_details.py --out results/pdf_extract_details.csv
.venv/bin/python scripts/merge_into_sheet.py --sheet "Bankwell Data Analysis.xlsx" --register data/raw/publicextract.charity.zip
```
The merge writes a NEW `... - with PDF figures.xlsx` (never the original): fills empty cells only, yellow =
filled by us, orange = flagged, READ ME tab explains.

## Acceptance rule (in `merge_into_sheet.decide()` — every export uses it)

Accept a figure only if: printed in the accounts **and** (evidence check passed, or it is a scan) **and**
confidence ≠ low **and** the Opus re-read (if any) did not disagree. A failed evidence check is accepted only
when the Opus re-read gives the same value. Otherwise blank, with the reason in the flag column.

## Never

- Commit PDFs, packets, page images, `out/`/`check/` JSONL, or logs (trustee names). Only `results/` CSVs.
- Store account numbers (8+ digit runs are masked in exported quotes).
- Sum `reserves` (trustees' wording varies; 50% wrong in the pilot) or add group/consolidated figures.
- Change the prompt and keep old outputs mixed with new ones — use a new output folder and re-score the pilot.

## Cost / time (10 Oct 2026)

7,563 documents: the main run took ~2.5 hours wall clock (12:24–14:48) with 6 Sonnet workers plus extra and
reverse runners (up to ~9 in parallel). The Opus checks ran alongside it (12:44–14:48). Pilot of 60 docs: ~3 minutes.
Token cost was not metered — measure it on the pilot before a full re-run.
