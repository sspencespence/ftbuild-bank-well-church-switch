# Bank Well — handover (FaithTech BUILD, 9–10 Oct 2026)

**Question:** how much UK church money sits in banks rated badly vs ethically (bank.green), and how much
could switch? This file says what was built, where every number comes from, how good it is, and how to
re-run or extend it. Method background: `METHODS.md`. Output files: `results/README.md`.

## Headline (as pitched, 10 Oct)

Of **3,827 churches whose bank we could verify**, **1,199 (31%)** bank ethically (rating 5).
Cash held: **£178.7m** at worst-rated banks (1) · £62.1m middling (3) · £100.1m ethical (5).
Reproduce: `scripts/headline.py "<sheet with PDF figures>.xlsx" --as-in-deck`. With a later spelling fix
("Nat West") it is 3,857 churches and £180.4m worst-rated — see `.claude/skills/refresh-headline`.

"Verified" = the bank named in the church's own accounts (2,398) or behind the sort code on its own website
(1,429). We deliberately did **not** use the team script's `principal_bank`: unverified, and dominated by
national bodies (it gave £760m worst-rated).

## What was built (pipeline)

```
Charity Commission register ──► team church list (uk_churches.csv, 31,691)
        │                                   │
        │ accounts PDFs (CC + Companies House)│ church websites
        ▼                                   ▼
  extract-pdf-accounts               find-church-banks
  cash / funds / net assets,         sort code ──► bank ──► rating
  "Bankers" line, with evidence      (never guessed)
        └──────────────┬────────────────────┘
                       ▼
           merge_into_sheet.py  ──►  refresh-headline (the numbers)
                       │
OpenStreetMap buildings ──► link-osm-churches (building ↔ charity)
```

Each box is a skill in `.claude/skills/<name>/SKILL.md` — written so a person can follow it by hand, and
so Claude Code picks it up automatically in this repo. Scripts are in `scripts/`; data lives outside the
repo in `$BANKWELL_DATA` (default `~/bankwell-data`).

| Step | Skill | Key scripts | Result |
|---|---|---|---|
| Download accounts | `extract-pdf-accounts` §1 | `fetch_accounts.py`, `pdf_when_up.sh`, `fetch_companies_house.py` | 7,584 CC + 2,257 Companies House PDFs |
| Read figures | `extract-pdf-accounts` §2–6 | `make_packets.py` → `run_workers.sh` → `check_evidence.py` → Opus check → `export_*.py` | 7,563 read; cash 4,840 · total funds 4,202 · net assets 3,697 · bankers 2,637 |
| Banks from websites | `find-church-banks` | `crawl_sort_codes.py`, `build_church_banks.py`, `bank_ratings.py` | 2,401 sort codes → 1,728 churches with one bank |
| Join + headline | `refresh-headline` | `merge_into_sheet.py`, `headline.py` | the numbers above |
| OSM buildings | `link-osm-churches` | `scripts/osm/*.overpassql`, `link_osm_to_charities.py`, `osm_sortcode_sheet.py` | 3,724 of 44,515 buildings linked |

## How good is it

| Check | Result |
|---|---|
| Sonnet reader vs official Part B figures (60-doc pilot) | cash 16/18 exact (both misses = errors in the official data), total funds 23/23, net assets 18/18. **Reserves 6/14 → never used in totals** |
| Blind Opus re-read (random 10% + every flagged doc) | 1,349 / 1,354 figures agree (99.6%) |
| Mechanical evidence check (quote on the cited page, value in the quote) | 92–93% pass; failures accepted only if Opus agrees |
| Sort-code bank vs bank in the accounts | 199 / 220 agree (90%) — rest mostly churches with two accounts |
| OSM `name+town` links | ~85–90% right (40-row spot check); higher tiers are exact-match rules |

Not done: the full ~600-document known-answer score (`make_shards.py --set kat`) — planned, never run.

## Known gaps — read before extrapolating

1. **The sample cliff.** The CC document store failed overnight (≈01:00–03:06, then down from 09:10 on
   10 Oct) while we downloaded largest-income first. Result: **no** CC PDFs for churches with £150k–£500k
   income; 4,902 downloads are still `links_hidden`. Re-running `fetch_accounts.py` fills it (it resumes).
   Until then the PDF sample is skewed to £25k–£150k — reweight by income band before scaling to "all UK churches".
2. **Coverage.** ~3.9k of ~31.7k registered churches have a verified bank. Small CofE parishes (<£100k) are
   *excepted* from registering; Catholic churches sit under one diocesan trust; Scotland/NI use other regulators.
3. **One church, several accounts.** We take the first bank listed. Some churches split money across banks.
4. **Ratings** come from `bank-ratings.md` (bank.green). RBS isn't rated there, so RBS churches are excluded.
5. **Cash** = cash at bank and in hand on the balance sheet. Some accounts merge deposits/investments —
   the `*_quote` column shows exactly what was read.

## Privacy rules (keep these)

- Accounts PDFs contain **trustee names**: PDFs, packets, page images and raw reader outputs stay in
  `$BANKWELL_DATA`, never in git or public pages. Only `results/` CSVs are shared.
- **No bank account numbers** anywhere: the crawler masks them at source; exports mask 8+ digit runs.
- Testimony on the website must be people's own words.

## Re-run / extend

- New register extract or new accounts filed → `extract-pdf-accounts` (resumes), then `refresh-headline`.
- New churches or websites → `find-church-banks`, then `refresh-headline`.
- Quick "is it still right?" → `refresh-headline` (both commands) and compare with the table above.
- Ideas not done: retry the 4,902 hidden-link downloads; reweight by income band; a licensed sort-code
  lookup for the 650 unknown codes; denomination/region coverage map; merge with the teammate pipeline on
  the `sortcode-db` branch.

## Where things were (10–12 Oct)

The data folder was on one team laptop (`~/bankwell-data`, ~31 GB with PDFs and page images) plus a curated copy
(`BankWell-curated`). Ask the team for it rather than re-downloading if it still exists — the CC
document store was unreliable. Run notes: `docs/overnight-run-notes.md`.
