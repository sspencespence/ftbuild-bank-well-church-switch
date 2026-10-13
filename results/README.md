# results/ — output files (regenerate with the scripts; see HANDOVER.md)

Every file joins on the **Charity Commission registered charity number** (`registered_number` /
`charity_number`). Snapshot: 10–12 Oct 2026. No trustee/person names, no bank account numbers.

| File | Rows | What it is | Made by |
|---|---|---|---|
| `pdf_extract_final.csv` | 7,563 | `registered_number, assets_cash, figures_source` for every church whose accounts PDF was read. 4,840 have cash; blank = not found or not accepted. Only churches with **no** official cash figure are here. | `scripts/export_pdf_csv.py` |
| `pdf_extract_details.csv` | 7,563 | Same churches, all fields: assets_cash / funds_total / assets_total (accepted values), page, exact quote, confidence, evidence check, Opus second read, why a value was rejected; `reserves_stated_in_report`; `bankers_from_accounts` (2,637). | `scripts/export_pdf_details.py` |
| `bankwell_churches_matched.csv` | 31,691 | Every church on the team list with: sort code found on its website, bank from that sort code (method + confidence + rating), and the accounts-download log (Charity Commission / Companies House). | sort-code crawl + `sort_code_banks.csv` (see `find-church-banks` skill) |
| `sort_code_banks.csv` | 1,042 | Sort code → bank, with method (`tier2_bank_published` / `tier1_page_consensus` / `tier1_single_page`), confidence and evidence. Unknown codes are left unknown — no digit-range guessing. | `find-church-banks` skill |
| `sort_code_page_evidence.csv` | 1,042 | For each sort code: what the church pages printed next to it (votes per bank). | crawl |
| `osm_all_uk_churches.csv` | 44,515 | Every UK church building in OpenStreetMap (10 Oct 2026): name, denomination, kind (38,833 places of worship + 5,682 church/chapel/cathedral buildings not tagged as worship), website, postcode, lat/lon, and the sort code/bank found on its own website (598). Same as `all_uk_churches_osm.xlsx`. © OpenStreetMap contributors (ODbL). | `scripts/osm_all_churches_sheet.py` |
| `osm_all_raw.csv` | 44,515 | The raw Overpass download it is built from (input to the OSM scripts — saves re-querying). | `scripts/osm/q_all.overpassql` |
| `osm_churches_linked.csv` | 44,515 | Every OpenStreetMap church building, linked (where possible) to its charity, with that charity's cash/bank/rating. Map data © OpenStreetMap contributors (ODbL). | `scripts/link_osm_to_charities.py` |

## Acceptance rule for PDF figures (why some cells are blank)

A figure is kept only if it is printed in the accounts **and** (its quote + value are found on the cited
page, or it is a scan) **and** confidence is not low **and** the blind Opus re-read (if done) agrees.
A failed evidence check is kept only when the Opus re-read gives the same value. A blank is a decision,
not a gap in processing — the reason is in `*_flag` in `pdf_extract_details.csv`.
