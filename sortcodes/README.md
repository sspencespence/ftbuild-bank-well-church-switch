# Sort code to bank lookup

**Results for 2,949 charities and churches (2,252 confirmed churches) are in [SUMMARY.md](SUMMARY.md)** (`results/church_banks_extended.csv`, `results/sort_code_map_extended.csv`, chart). The team crawl alone (2,401 churches) is the `origin = team_crawl` rows of the extended file; `python church_banks.py annotate --crawl bankwell_churches_matched.csv` still writes it on its own. See "Adding other sources" below for the full set.

Many churches never name their bank in their Charity Commission filings, but their website giving page often shows a sort code. This folder turns a UK sort code into the bank that holds the account (brand and parent group), using a table built only from public sources.

Example: Euston Church's giving page shows sort code `60-01-73`. That code sits inside NatWest's `60` range, but it is an agency code for **Reliance Bank** (formerly the Salvation Army Bank), which clears through NatWest. A first-two-digits lookup would get this wrong; this table gets it right.

## Usage

Run from this folder with the project venv (`C:\Users\Brian\.venvs\bankwell`).

```
python sortcode_lookup.py 60-01-73
600173  Reliance Bank  Reliance Bank  exact
```

Annotate a CSV of scraped giving pages (adds `sc_bank`, `sc_group`, `sc_rating_name`, `sc_match`, `sc_candidates`, `sc_source` and `sc_normalised` columns; blank or malformed codes get `sc_match=invalid` and do not stop the run):

```
python sortcode_lookup.py --csv churches.csv --column sort_code --context-column regno --out churches_banks.csv
```

From Python:

```python
from sortcode_lookup import lookup
lookup("40-52-40")   # {'bank': 'CAF Bank', 'group': 'Charities Aid Foundation', 'match': 'exact', ...}
```

Accepted input: `60-01-73`, `600173`, `60 01 73`, `60.01.73`, en dashes and non-breaking spaces. Anything that is not six digits is rejected.

### What `match` means

| match | meaning |
|---|---|
| `exact` | the code itself is listed (agency banks, small institutions) |
| `range` | the code falls in a bank's range; the narrowest matching range wins |
| `ambiguous` | equally narrow ranges name different banks; `candidates` lists them (for example Lloyds and TSB share the 30 and 77 ranges) |
| `unknown` | no row covers the code |

`unknown` and `ambiguous` results are added to `to_verify.csv` (once per code) for a person to check.

## The verify queue

1. Open `to_verify.csv`.
2. Look the code up by hand on a free checker (sortcodes.co.uk, BankVal demo, Mintly free tool). These are for finding out, not for citing.
3. Find a **public** page that states the same fact: the bank's own website, or a bank statement or payment page published by an organisation (parish councils publish many).
4. Add a row to `sort_codes.csv` citing that page, then run the tests.

## Adding a row

`sort_codes.csv` columns: `start,end,kind,bank,source,verified,notes`. Codes are six digits with leading zeros kept (`040605`). `kind` is `exact` (start equals end) or `range`. `bank` must exist in `institutions.csv`, which holds `group`, `type`, the `rating_name` used in `bank-ratings.md` (blank if unrated) and history notes. Every row needs a `source` URL and a `verified` date.

Run the tests after any edit:

```
python -m pytest -q
```

The loader rejects a bad row and names it, giving both the data row and the line in the file (for example `sort_codes.csv row 12 (line 13): bank 'Nobody Bank' is not in institutions.csv`). A bank listed twice in `institutions.csv` is also rejected.

## Licensing: why no API data is committed

Every commercial sort code service (eSortcode, Mintly, SortWare, BankVal) resells Vocalink's Extended Industry Sort Code Directory (EISCD). eSortcode's terms say customers "shall not redistribute, resell, or sublicense EISCD data" (4.3) and must not "Create derivative databases based on EISCD data" (6.2). So nothing obtained from an API or checker goes in this table unless a public page confirms it, and that page is what the row cites. The test suite fails if a row cites one of those services.

## Cross-check (private)

`crosscheck.py` compares our answers with the eSortcode API and **prints** the agreement rate and the disagreements. It writes nothing. It needs a free eSortcode account (50 free checks, no card) and `ESORTCODE_API_KEY=...` in the project `.env`. The API also wants an account number; pass it as `code:account` when you have it from the giving page.

```
python crosscheck.py 60-01-73:00216252 20-27-41 --limit 20
```

## Crawling and adding other sources

`crawl_sort_codes.py` fetches each church's homepage plus up to five same-site giving, donate or contact pages, respecting robots.txt, and records the sort code. It never stores account numbers (snippets mask any run of 6+ digits). It accepts a code after a label (`Sort code`, `Sort`, `SC:`, `S/C:`, `Bank Code`) or, with no label, a hyphenated code near an account word or a code directly followed by an account number. It skips placeholders (`12-13-14`, `11-11-11`) and `10-` codes (Bank of England, almost always a date). Input needs `registered_number, charity_name, contact_web, income`; run several copies on split inputs to go faster (four at 16 workers did 11,276 sites in about 10 minutes).

```
python crawl_sort_codes.py --churches sites.csv --out C:\Users\Brian\bankwell-data\team_recrawl\s0 --workers 16
```

`extend_sources.py` joins every source and writes `results/church_banks_extended.csv` and `results/sort_code_map_extended.csv` (it reuses `church_banks.annotate`, so team-crawl rows keep the same banks; only `likely_note` wording can shift as new pages add Lloyds/TSB evidence). Then run `church_check.py` (below), then `python make_chart.py` redraws the chart from confirmed churches only. The 10 October run (inputs kept outside the repo in `C:\Users\Brian\bankwell-data\`):

```
python extend_sources.py --team-crawl ..\..\bankwell_churches_matched.csv ^
  --martin extend_inputs\scraped_sort_codes.csv --martin-recheck extend_inputs\martin_recheck.csv ^
  --osm-jsonl osm_merged.jsonl --osm-list extend_inputs\osm_new_all.csv ^
  --recrawl-jsonl team_recrawl\s0\sort_codes.jsonl ... team_recrawl\u3\sort_codes.jsonl
```

Rules it applies: a re-crawl fills a team charity's blank code first; Martin's charities come next, using the re-checked code (`martin_recheck.csv`, made by fetching his pages again with the crawler's pattern); OpenStreetMap churches come last, minus Northern Ireland (BT postcode or NI bank) and duplicates of a charity's own website. Each row's `origin` says which source it came from.

Then mark which rows are churches (a congregation or its PCC). This adds `church_check`, `church_reason` and `in_osm` (where the row is found on the OpenStreetMap church sheet) to the file and writes `results/church_check_review.csv`, the `unsure` rows with their evidence, most income first, for a person to decide. Rerun it after every `extend_sources.py` run, which drops these columns:

```
python church_check.py --bulk C:\Users\Brian\bankwell-data\bulk --team-filter "filtered data.csv" ^
  --osm-truth "..\..\Bankwell Data Analysis - All UK Churches (OpenStreetMap).csv"
```

`--bulk` is the Charity Commission bulk extract (classification, activities text, website); `--team-filter` is the teammates' church list of 10 October (optional). `results/church_check_decisions.csv` (read by default) settles rows the rules leave `unsure`. `--osm-truth` overrides everything: a charity whose website or giving page is on the OpenStreetMap church list is `church`.

## Coverage and limits

- Covered: all major clearing ranges in England and Wales, Scotland and Northern Ireland; agency codes for Reliance Bank, CAF Bank, Charity Bank, Unity Trust, Triodos, Metro Bank, Starling, Monzo, Revolut, Tide, ClearBank, Atom, Zopa, Chase UK, Wise, Ecology, Coventry, Newcastle and Cumberland building societies, and others.
- Most rows cite a fixed revision of Wikipedia's sort code article (marked `secondary source`). CAF Bank, Charity Bank, Unity Trust and Triodos rows cite the bank's own site or a bank statement published by a parish council.
- 97 rows cite a church's own giving page that prints the bank beside the sort code (from the team's crawl of 9 to 10 October 2026). Most settle Lloyds versus TSB for a single code; three correct our ranges (two `12-` codes that are Bank of Scotland, and `08-61-15` for Virgin Money) and were checked live. Pages saying "Lloyds TSB" were not used.
- Accuracy: against 719 church pages that name one bank beside one sort code, the table (before the church-page rows were added) agreed 711 times (98.9%). Most of the 8 disagreements were the page, not the table (for example "our charity bank account" read as Charity Bank).
- Lloyds and TSB share the `30` and `77` ranges because TSB kept its branch codes when it split from Lloyds in 2013. Codes without a church-page row stay `ambiguous`.
- Church deposit funds cannot be detected by sort code. The CBF Church of England Deposit Fund (CCLA) and the Methodist CFB Deposit Fund both take deposits through ordinary HSBC collection accounts on `40-05-30`, so a church's money in them has no sort code of its own. A giving page showing `40-05-30` resolves to HSBC, which is correct for that account.
- Unresolved (no public source yet): Handelsbanken business branches (each branch has its own code; only the personal code `60-95-34` is public) and most building societies. Building society savings are usually paid in through a clearing bank's sort code plus a roll number, so they rarely appear on giving pages. Codes from these show up as the host bank's range or as `unknown`.
- Co-op's `08-60` to `08-61` range is shared by several building societies; it returns a placeholder institution, not a specific society.
- A sort code shows where one account is held. A church may bank in more than one place.
- Ratings in `institutions.csv` follow `bank-ratings.md`, whose source is still to be confirmed. Clydesdale and Yorkshire Bank are rated there but now trade as Virgin Money; they map to Virgin Money here.
