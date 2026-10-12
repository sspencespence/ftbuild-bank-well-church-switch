# Overnight run — Fri 9 → Sat 10 Oct (started ~00:45)

Two background jobs on one team laptop. Output in `~/bankwell-data/` (WSL home, not in the repo).

| Job | Script | Output | Log |
|---|---|---|---|
| Sort codes from church websites | `scripts/crawl_sort_codes.py` | `sort_codes.jsonl` | `crawl.log` |
| Latest accounts PDF per church (Charity Commission) | `scripts/pdf_when_up.sh` → `fetch_accounts.py` | `pdfs/` + `manifest.jsonl` | `pdfs.log` |
| Latest accounts per **company**-church (Companies House) | `scripts/fetch_companies_house.py` | `companies-house/` (`pdfs/`, `pages/<regno>/p1-4.png`, `manifest.jsonl`) | `companies-house.log` |

Python deps for the Companies House job live in `.venv/` (`uv venv .venv && uv pip install --python .venv/bin/python requests pypdf pymupdf`).

## Check progress

```bash
tail -2 ~/bankwell-data/crawl.log ~/bankwell-data/pdfs.log
python3 -c "import json,collections;[print(f,collections.Counter(json.loads(l)['status'] for l in open(f'~/bankwell-data/{f}.jsonl'))) for f in ['sort_codes','manifest']]"
pgrep -af "crawl_sort_codes|fetch_accounts"   # still running?
```

Both are **resumable**: if either stopped, re-run the same command — it skips what's done
(PDF timeouts are retried on the next run).

```bash
cd ~/hackathon/ftbuild-bank-well-church-switch
nohup python3 scripts/crawl_sort_codes.py --out ~/bankwell-data --workers 8 >> ~/bankwell-data/crawl.log 2>&1 &
nohup bash scripts/pdf_when_up.sh >> ~/bankwell-data/pdfs.log 2>&1 &
nohup .venv/bin/python scripts/fetch_companies_house.py --register data/raw/publicextract.charity.zip --out ~/bankwell-data/companies-house >> ~/bankwell-data/companies-house.log 2>&1 &
```

Stop the Charity Commission wrapper with `pkill -f "^bash scripts/pdf_when_up"`.

## Charity Commission PDFs — what happened (01:00–01:20)

The CC **document store** failed, not us. Evidence (page source of St Paul Woking, org 5014742):
at 00:20/01:00 the "Accounts and TAR 31 Dec 2024" row had `<a class="accounts-download-link" … objectiveId=A17783243>`;
at 01:03 the same row's Download cell was **empty**. When links did show, every PDF request returned
**504 from Microsoft-Azure-Application-Gateway at exactly 30 s** on both backend servers seen
(`ApplicationGatewayAffinity` 5b6f53c9f7 and 69b5f7433d). Register pages, bulk download and API
portal stayed fast (~0.1 s). Same PDFs had downloaded in 0.7–28 s earlier in the evening.
`pdf_when_up.sh` probes 3 parish PDFs every 10 min and runs the fetcher only when one returns a PDF.
`fetch_accounts.py` now records hidden links as `links_hidden` (retried), not `no_accounts`.

Also: a small-parish TAR (St Paul Woking 2020, CC template) has **no bankers field at all** —
PDFs will mostly help for larger churches with accountant-prepared accounts.

## Companies House route (works — use this for company-churches)

3,673 churches in `uk_churches.csv` are registered companies and hold **59% of total church income**;
2,395 have no `principal_bank` and income > £25k → that's the overnight job. Companies House stores
accounts as **scanned images**, so the bank is read from the rendered page PNGs (Claude vision),
using the Bricksave `lease_history_extraction` rules: exact quote + page, never guess.

**Hit-rate test (random sample, seed 42, read by hand 01:30):** bank named on pages 1–3 in **5 of 8**
(+ Diss = 6/9):

| Charity | Bank (quote) | Note |
|---|---|---|
| 1132992 Diss Christian Community Church | "Bankers CAF Bank Limited" | Company Information, printed p1 (PDF p2); filed 23 Sep 2026, y/e 31 Dec 2025 |
| 1169264 New Horizons Coventry | "Bankers HSBC plc" | Charity information |
| 1102396 House on the Rock | "Bankers Barclays Bank PLC" | Legal & administrative info |
| 1109814 Frontline Trust | "Bankers CAF Bank" | Legal & administrative info |
| 1184056 Calvario Ltd | "Principal bankers Royal Bank of Scotland" | ⚠ same page: "Investment advisers Barclays" — don't take the first bank name |
| 1144831 Westminster Chapel | "Bankers Barclays Bank PLC … CAF Bank Ltd" | two banks — decide a rule (primary = first listed?) |
| 1072436 Salisbury Vineyard, 1164181 Holding Forth the Word, 1157365 St Anne's Lutheran | not on pp1–3 | may be later in the doc, or not stated |

Pages also list trustee names — store only the bank line + page, never names.

## The bug to tell the team at 9:45

`church_bank_cc_fill.py` builds the accounts URL with `registered_number`, but the Charity
Commission page needs `organisation_number`. They differ for **20,980 of 31,691 churches (66%)**
and **all 2,141 banks found so far come from the 10,709 where they match** — the other two-thirds
were never actually fetched. `fetch_accounts.py` fixes it by mapping reg → org from the bulk
`publicextract.charity.zip` (`linked_charity_number = 0`).

## What we saw in testing

- **Sort codes:** 15 found on 60 parish-sized sites (25%), none of which had a bank in the CSV.
  `40-52-40` appeared 3× (likely CAF Bank — **confirm with a proper sort-code lookup**, never
  infer the bank from the first two digits). Account numbers are never stored; snippets are masked.
- **PDFs:** the Commission's document server was slow (~28 s per PDF, frequent 504s at 30 s) —
  not blocking, just slow. Expect low PDF yield overnight; largest charities time out most.
- **Data quality:** `uk_churches.csv` includes non-churches (universities, schools, a Muslim
  community association, Watch Tower). Team 1 / Team 2 should filter before estimating.

## Next (Saturday)

0. Read the Companies House page images (`companies-house/pages/<regno>/`) with Claude: bank + quote + page per church; "unknown" if absent. Check pages 4+ for the misses.

1. Sort code → bank via a real directory, then map to `bank-ratings.md`.
2. Read downloaded PDFs: text layer (pdfplumber) → render scans to PNG for Claude vision (Bricksave
   `lease_history_extraction` method) → bank + exact quote + page, "unknown" rather than guess.
3. Blind hand-check ~60 rows (maker ≠ checker) before any number goes on the page.
