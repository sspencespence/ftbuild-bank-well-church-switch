# Which bank do churches use? Sort code results

*FaithTech BUILD, 10 October 2026. Branch `sortcode-db`.*

Many churches never name their bank, but their website giving page shows a sort code. We built a table that turns a UK sort code into the bank behind it, then ran it over church giving pages found by the team's crawl, Martin's scrape and an OpenStreetMap list of churches.

![Churches by bank](results/churches_by_bank.png)

## Headline numbers

- **2,949 churches** show a sort code on their website. **2,874** show exactly one.
- Of the 2,874, by the bank's ethical rating in `bank-ratings.md`:

| Rating | Churches | Share |
|---|---|---|
| 1 (low) | 1,430 | 50% |
| 3 | 296 | 10% |
| 5 (high) | 837 | 29% |
| Unrated or unresolved | 311 | 11% |

- Biggest banks: Barclays 543, NatWest 411, HSBC 405, CAF Bank 400, Lloyds 273, Co-operative Bank 251.
- **Accuracy:** on 719 church pages from the team crawl that print one sort code with one bank named beside it, the table agreed with the page 711 times (**98.9%**), measured before any church-page rows were added. For the newer sources see "Where the churches came from".

## Where the churches came from

| Source (`origin` column) | Churches | What it is |
|---|---|---|
| `team_crawl` | 2,401 | The team's crawl of 9 to 10 October (`bankwell_churches_matched.csv`) |
| `team_recrawl` | 217 | Team-list charities whose site gave no code first time (11,276 sites) or did not load (5,090), re-crawled with the improved pattern below |
| `martin` | 156 | Charities in Martin's `scraped_sort_codes.csv` (branch `martin`) with no code from the team crawl or re-crawl |
| `osm` | 170 | Churches from the OpenStreetMap list whose website is not in the team list. No charity number, so no income |
| `team_via_osm` | 5 | A code the OpenStreetMap crawl found on a team charity's own website |

- **Improved pattern.** The original crawler only accepted a code written straight after "sort code". Real pages also write `Sort code: *`, `Sort Code |`, `SC:`, `Bank Code:`, or the code beside an account number with no label. On 305 of Martin's pages the new pattern found 283 codes against 138, and it found nothing on 150 pages known to have no code.
- **Martin's codes were re-checked.** His scraper did not need the words "sort code", so dates, phone numbers and placeholders such as `12-13-14` got in. Each of his pages was fetched again with the new pattern: 132 charities kept a code that passed (`verified=anchored`), 24 kept his code because the page did not load (`verified=martin_only`, treat with care), 62 were dropped.
- **OpenStreetMap rows.** 24 Northern Ireland churches were dropped (BT postcode or an NI bank), and 241 duplicates of charities that already had a code.
- **Agreement on the new rows** (548 churches): where the page names one bank, our answer matched 177 times, was one of the candidates 16 times, and conflicted 13 times. This is weaker evidence than the 98.9%, because the crawler records any bank named anywhere on the page, not only beside the code.

## Files

| File | What it is |
|---|---|
| `results/church_banks_extended.csv` | **Main file.** One row per church with a sort code, from every source: `origin`, charity number, name, income, denomination, sort code, **bank, group, rating**, match type, the bank printed on the page, the page URL, `verified` and a rough `maybe_not_church` flag |
| `results/sort_code_map_extended.csv` | One row per sort code seen (1,243 codes): bank, group, rating, and how many churches use it |
| `results/church_banks.csv`, `results/sort_code_map.csv` | The same for the team crawl alone (2,401 churches, 1,042 codes) |
| `results/churches_by_bank.png` | The chart above |
| `sort_codes.csv`, `institutions.csv` | The sort-code table itself (every row cites a public source) |
| `sortcode_lookup.py` | Look up any sort code: `python sortcode_lookup.py 60-01-73` |
| `crawl_sort_codes.py` | Crawls church websites for a sort code on the giving page |
| `church_banks.py`, `extend_sources.py`, `make_chart.py` | Rebuild the results (see README) |
| `README.md` | How the table works, how to add a row, licensing |

Join to anything else on **`charity_number`** (OpenStreetMap rows use `osm:<type>/<id>`, for example `osm:node/4118141`, instead).

## How to read the columns

- `match`: `exact` (the code itself is listed, e.g. CAF Bank 40-52-40), `range` (falls in a bank's range), `ambiguous` (more than one bank possible), `unknown`.
- **Lloyds or TSB:** TSB kept its branch sort codes when it split from Lloyds in 2013, so many codes could be either (Lloyds is rated 3, TSB 1). Where a church page names the bank we use it; 233 churches stay ambiguous. For those, `likely_bank` says "Lloyds" with a note: 96% of 180 page-named 30-xx codes are Lloyds. That is an estimate, not a fact.
- `page_agrees`: whether the bank printed on the page matches our answer (`yes`, `candidate` for an ambiguous code, `no`).
- `shared_page`: above 0 means the code came from a page listing several churches, so it may belong to a sibling church. 253 churches; check by hand before relying on them.
- `maybe_not_church`: `yes` where the name looks like a hall, school, foodbank or similar (39 rows). Not removed.
- Churches with several sort codes have values separated by `;` in the same order.

## Worth knowing

- **Agency banks hide inside big banks' ranges.** Euston Church's `60-01-73` looks like NatWest but is **Reliance Bank** (formerly the Salvation Army Bank). Likewise CAF Bank (40-52-40, inside HSBC), Charity Bank (60-83-16), Unity Trust (60-83-01) and Triodos (16-58-10). Guessing from the first two digits gets exactly the ethical banks wrong.
- **Church deposit funds are invisible here.** The CBF Church of England Deposit Fund and the Methodist CFB fund collect through an HSBC account (`40-05-30`), so money held in them cannot be seen from a sort code.
- Royal Bank of Scotland is part of NatWest Group but has no rating of its own in `bank-ratings.md`, so it shows as unrated.

## Limits before quoting any number

- These are churches whose website shows a sort code, not a random sample, and the counts are **not weighted by money**. The 170 OpenStreetMap churches have no income figure at all.
- A giving-page code is the donations account: usually, not always, the main bank.
- The list includes some non-churches (schools, YMCAs, foodbanks); flagged roughly, not filtered.
- Ratings come from `bank-ratings.md`, whose source is still to be confirmed.
- Charity rows cover registered charities in England and Wales. OpenStreetMap rows may include churches in Scotland; Northern Ireland churches were removed.

## Next steps

1. **Read the "Bankers" line from the accounts PDFs** (about 7,600 Charity Commission and 2,300 Companies House documents already downloaded by the crawl). This covers churches with no sort code online and gives an independent check on these results.
2. Weight by money: join to income or cash figures to estimate how much church money sits at each rating.
3. Filter out non-churches and hand-check the 253 shared-page rows and the 13 new-row conflicts.
4. Settle more Lloyds/TSB codes as church pages or published statements name them.
