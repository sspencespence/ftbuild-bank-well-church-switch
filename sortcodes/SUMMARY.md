# Which bank do churches use? Sort code results

*FaithTech BUILD, 10 October 2026. Branch `sortcode-db`.*

Many churches never name their bank, but their website giving page shows a sort code. We built a table that turns a UK sort code into the bank behind it, then ran it over the team's crawl of church giving pages.

![Churches by bank](results/churches_by_bank.png)

## Headline numbers

- **2,401 churches** (of 31,691 on the list) show a sort code on their website. **2,342** show exactly one.
- Of the 2,342, by the bank's ethical rating in `bank-ratings.md`:

| Rating | Churches | Share |
|---|---|---|
| 1 (low) | 1,136 | 49% |
| 3 | 244 | 10% |
| 5 (high) | 727 | 31% |
| Unrated or unresolved | 235 | 10% |

- Biggest banks: Barclays 437, CAF Bank 363, HSBC 322, NatWest 320, Lloyds 235, Co-operative Bank 206.
- **Accuracy:** on 719 church pages that print one sort code with one bank named beside it, the table agreed with the page 711 times (**98.9%**), measured before any church-page rows were added.

## Files

| File | What it is |
|---|---|
| `results/church_banks.csv` | One row per church with a sort code: charity number, name, income, denomination, sort code, **bank, group, rating**, match type, the bank printed on the page, and the page URL |
| `results/sort_code_map.csv` | One row per sort code seen (1,042 codes): bank, group, rating, and how many churches use it |
| `results/churches_by_bank.png` | The chart above |
| `sort_codes.csv`, `institutions.csv` | The sort-code table itself (every row cites a public source) |
| `sortcode_lookup.py` | Look up any sort code: `python sortcode_lookup.py 60-01-73` |
| `church_banks.py`, `make_chart.py` | Rebuild the results from the crawl CSV |
| `README.md` | How the table works, how to add a row, licensing |

Join `church_banks.csv` to anything else on **`charity_number`**.

## How to read the columns

- `match`: `exact` (the code itself is listed, e.g. CAF Bank 40-52-40), `range` (falls in a bank's range), `ambiguous` (more than one bank possible), `unknown`.
- **Lloyds or TSB:** TSB kept its branch sort codes when it split from Lloyds in 2013, so many codes could be either (Lloyds is rated 3, TSB 1). Where a church page names the bank we use it; 182 churches stay ambiguous. For those, `likely_bank` says "Lloyds" with a note: 95% of page-named 30-xx codes are Lloyds. That is an estimate, not a fact.
- `page_agrees`: whether the bank printed on the page matches our answer (`yes`, `candidate` for an ambiguous code, `no`).
- `shared_page`: above 0 means the code came from a page listing several churches, so it may belong to a sibling church. 236 churches; check by hand before relying on them.
- Churches with several sort codes have values separated by `;` in the same order.

## Worth knowing

- **Agency banks hide inside big banks' ranges.** Euston Church's `60-01-73` looks like NatWest but is **Reliance Bank** (formerly the Salvation Army Bank). Likewise CAF Bank (40-52-40, inside HSBC), Charity Bank (60-83-16), Unity Trust (60-83-01) and Triodos (16-58-10). Guessing from the first two digits gets exactly the ethical banks wrong.
- **Church deposit funds are invisible here.** The CBF Church of England Deposit Fund and the Methodist CFB fund collect through an HSBC account (`40-05-30`), so money held in them cannot be seen from a sort code.
- Royal Bank of Scotland is part of NatWest Group but has no rating of its own in `bank-ratings.md`, so it shows as unrated.

## Limits before quoting any number

- These are churches whose website shows a sort code, not a random sample, and the counts are **not weighted by money**.
- A giving-page code is the donations account: usually, not always, the main bank.
- The church list includes some non-churches (schools, YMCAs); not yet filtered.
- Ratings come from `bank-ratings.md`, whose source is still to be confirmed.
- Covers registered charities in England and Wales only.

## Next steps

1. **Read the "Bankers" line from the accounts PDFs** (about 7,600 Charity Commission and 2,300 Companies House documents already downloaded by the crawl). This covers churches with no sort code online and gives an independent check on these results.
2. Weight by money: join to income or cash figures to estimate how much church money sits at each rating.
3. Filter out non-churches and hand-check the 236 shared-page rows.
4. Settle more Lloyds/TSB codes as church pages or published statements name them.
