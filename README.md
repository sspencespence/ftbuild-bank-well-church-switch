# UK Church Charity Data Extractor

Extracts a CSV of all currently registered UK church charities from the Charity Commission
open data, enriched with:
- **Denomination** — via keyword matching on objects text, with Claude API fallback for ambiguous cases
- **Principal bank** — via downloading and parsing each charity's most recent accounts PDF

---

## Output columns

| Column | Source |
|---|---|
| `charity_name` | CC bulk data |
| `registered_number` | CC bulk data |
| `contact_postcode` | CC bulk data (contact addresses) |
| `contact_web` | CC bulk data (contact addresses) |
| `income` | CC bulk data (most recent financial year) |
| `expenditure` | CC bulk data (most recent financial year) |
| `denomination` | Keyword parsing → Claude API fallback |
| `principal_bank` | PDF accounts scrape & parse |

---

## Setup

### 1. Python environment

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install requests pandas pdfplumber anthropic tqdm
```

### 2. API key (for denomination fallback)

```bash
export LLM_API_KEY=sk-ant-...
```

You can get a key from your chosen LLM provider. If you don't set this,
keyword-only matching is used and ambiguous churches will show `Unknown`.

---

## Usage

### Full run (all churches, all fields)
```bash
python church_charity_extractor.py
```
Output: `uk_churches.csv`

### Test run (first 50 churches)
```bash
python church_charity_extractor.py --limit 50
```

### Skip PDF download (faster, no principal bank data)
```bash
python church_charity_extractor.py --skip-pdf
```

### Skip Claude API (keyword-only denomination, no API cost)
```bash
python church_charity_extractor.py --skip-denomination-api
```

### Custom output filename
```bash
python church_charity_extractor.py --output my_churches.csv
```

---

## How it works

### 1. Bulk data download
Downloads four CSVs from the Charity Commission's open data portal:
- **RegEntity** — charity names, numbers, registration status
- **ContactAddresses** — postcodes, websites
- **FinancialHistory** — income & expenditure per year
- **CharityClassification** — objects/purpose text

Only charities with status `R` (registered, i.e. not removed) are kept.

### 2. Church filtering
Churches are identified by matching the charity name and objects text against
keywords: `church`, `parish`, `chapel`, `cathedral`, `congregation`, `Baptist`,
`Methodist`, `Pentecostal`, etc.

### 3. Denomination classification

**Stage 1 — keyword matching** (fast, free):
The charity name and objects text are scanned against ~20 denomination patterns.
This correctly identifies ~80% of cases.

**Stage 2 — LLM API fallback** (for ambiguous cases):
Where keyword matching returns nothing, the charity name and objects text are
sent to an LLM with a short prompt asking for the denomination.
This costs a fraction of a penny per charity and handles edge cases well.

### 4. Principal bank via PDF
For each church:
1. The Charity Commission charity page is scraped for a PDF link to the most
   recent submitted accounts.
2. The PDF is downloaded and text is extracted using `pdfplumber`.
3. Text near "principal bank", "bankers", "banking with", "accounts held with"
   etc. is searched for known UK bank names.
4. If a known bank is found in context, it is recorded; otherwise the field is blank.

> **Note**: PDFs that are scanned images (not text-searchable) will return blank.
> OCR support (e.g. with `pytesseract`) can be added as a future enhancement.

---

## Performance & cost estimates

| Step | Time | API cost |
|---|---|---|
| Bulk data download | ~2 min | Free |
| Denomination keywords | ~1 min for ~15k churches | Free |
| Denomination Claude API (~20% ambiguous = ~3k calls) | ~10 min | ~$0.30 |
| PDF download & parse (~15k PDFs, 2s each) | ~8–10 hours | Free |

> **Tip**: Run `--skip-pdf` first to validate the core data, then re-run with
> PDF extraction on a subset using `--limit`.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `KeyError` on column name | The CC data schema may have changed. Print `df.columns` at the top and check `_find_col` fallbacks. |
| PDF downloads timing out | Increase `REQUEST_TIMEOUT` or add `--skip-pdf` |
| `ANTHROPIC_API_KEY` errors | Set the env var or use `--skip-denomination-api` |
| Very large output file | Use `--limit` to test first; full dataset ~15k rows |

---

## Data sources

- [Charity Commission Full Register Download](https://register-of-charities.charitycommission.gov.uk/register/full-register-download)
- [Charity Commission API documentation](https://api.charitycommission.gov.uk/)
