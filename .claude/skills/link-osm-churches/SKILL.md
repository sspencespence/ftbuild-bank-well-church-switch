---
name: link-osm-churches
description: Download every UK church building from OpenStreetMap and link each one to its registered church charity, carrying over cash, bank and ethical rating. Use when refreshing the building-level map data, or when asked "which church buildings do we have figures for".
---

# Link OpenStreetMap churches to the charity register

OpenStreetMap (OSM) has the **buildings** (~38.8k Christian places of worship in the UK, 44.5k rows with
chapels/halls). The Charity Commission register has the **charities**. They are different things: one
charity can run several buildings, and most small buildings have no charity record of their own.

## Steps

1. **Download OSM churches** — Overpass query `scripts/osm/q_all.overpassql` (every `amenity=place_of_worship`
   + `religion=christian` in the UK, plus untagged `building=church|chapel|cathedral`; `out center`; CSV out).
   `scripts/osm/q_counts.overpassql` gives the counts only (sanity check, fast).
   - Public endpoint: `https://overpass-api.de/api/interpreter` (rate-limited; 504s at busy times — retry,
     or split the query by region). Run it from <https://overpass-turbo.eu> → Export → CSV if easier.
   - ```bash
     curl -s --data-urlencode data@scripts/osm/q_all.overpassql https://overpass-api.de/api/interpreter \
         > "$BANKWELL_DATA/osm-crawl/osm_all.csv"      # ~44.5k rows; check it isn't an HTML error page
     ```
   A snapshot of this download is committed as `results/osm_all_raw.csv` — copy it to the path above to skip Overpass.
2. **Whole-UK sheet** (all buildings + sort code/bank from their websites) —
   `.venv/bin/python scripts/osm_all_churches_sheet.py all_uk_churches_osm.xlsx results/osm_all_uk_churches.csv`
3. **Link** —
   ```bash
   .venv/bin/python scripts/link_osm_to_charities.py "<Bankwell sheet with PDF figures>.xlsx" \
       osm_churches_linked.xlsx results/osm_churches_linked.csv
   ```
   Needs `data/raw/publicextract.charity.zip` (register download) and
   `$BANKWELL_DATA/share/bankwell_churches_matched.csv` (sort-code banks; see `find-church-banks`).

## Match rules (strongest first; a building takes the first that fires)

| Method | Rule | Confidence |
|---|---|---|
| `website` | same website as the charity's registered website (directory sites like achurchnearyou excluded) | high |
| `domain` | same web domain, and only one charity has it | high |
| `postcode+name` | same full postcode AND a shared distinctive name word, one charity only | high |
| `name+town` / `name+postcode district` | ≥75% of the church's name words in the charity name (≥2 words), same town or postcode district in the charity's register address, no denomination clash, not just a shared saint's name, not a hall/school/"friends of" body, one charity only | ~85–90% (40-row spot check) |
| `umbrella body's website` | >5 buildings share one charity via website (e.g. Churches Conservation Trust) — kept for reference, **no cash/bank carried** | — |

**Postcode alone is never used** — in our check most postcode-only matches were wrong (the register
postcode is often the treasurer's home).

## Results (12 Oct 2026)

44,515 buildings → 3,724 linked (website 1,441 · postcode+name 1,423 · name+town 363 · domain 259 ·
name+postcode district 48) + 192 umbrella; 1,266 carry cash, 818 a bank. 40,789 not linked.

**Why most don't link** (not fixable by better matching): small CofE parishes under £100k are *excepted*
from registering; Catholic churches sit under one diocesan trust; Scotland/NI use other regulators.

## Rules when changing this

- After any rule change, **spot-check 40 random rows of each new tier** and record the error rate in the
  sheet's READ ME — the first version of `name+town` was ~50% wrong and looked fine in the counts.
- Never sum a charity's cash per building (`buildings_linked_to_this_charity` > 1 means shared).
- Keep the ODbL credit: "Map data © OpenStreetMap contributors".
