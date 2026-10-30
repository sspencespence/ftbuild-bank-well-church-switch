# Findings (Wave 1) — Bank Well data sources + cost — checked 2026-10-28

Condensed from researcher reports. Not yet spot-verified (RT-6). SOURCED/JUDGEMENT tags as reported.

## RT-1 OSCR + CCNI (confidence: HIGH existence, LOW fields)
- OSCR: free daily bulk download (full / 5-year / former register), https://www.oscr.org.uk/about-charities/search-the-register/download-the-scottish-charity-register/ . OGL v3.0 plus conditions: no direct marketing; don't present as the official register. Attribution text required. API in beta (application form, dataresearch@oscr.org.uk). From 9 Mar 2026 register shows trustee names + accounts documents (bulk vs per-charity UNVERIFIED).
- OSCR fields UNVERIFIED: field-description PDF https://www.oscr.org.uk/media/4577/2023-03-22-description-of-charity-register-download-fields.pdf could not be parsed by researcher. Religion purpose exists in law (2005 Act) — column unconfirmed.
- CCNI: CSV export via https://www.charitycommissionni.org.uk/umbraco/api/charityApi/ExportSearchResultsToCsv/?pageNumber=1 (listed on OpenDataNI, OGL label from catalogues only). Columns, cadence, primary licence text UNVERIFIED. 2016 figure: 1,389/5,215 (27%) listed advancement of religion (LOW).
- Next: download both files, check headers.

## RT-2 Church directories
- A Church Near You (CofE): one entry per church; fields: name, address, phone, website, lat/long, church code, deanery, benefice, parish legal name, diocese. NO charity number, NO finance. "Most churches are 'Excepted Charities'". robots.txt allows all but /christmas/events/; terms: "not to reproduce, duplicate, copy or re-sell any part of our site" → treat as needing written permission. https://www.achurchnearyou.com/terms/
- Church Heritage Record: "over 16,000 entries on church buildings in England"; no download/licence found. CofE: "12,500 parishes".
- Methodist: robots.txt Disallow /search/ (find-a-church) → automated use blocked. Baptist Union: 1,875 churches (2024, secondary); member-church PDF by association exists (unread). URC ~1,250 congregations. Catholic: parishes under diocesan trusts (on CC register) → match via register. Elim/AoG/RCCG/CoS/Church in Wales: counts secondary and conflicting; terms UNVERIFIED. Aggregators not assessed.
- Prompt-injection seen on cavac.at search result; ignored.

## RT-3 Address data
- AddressBase class ZW = "Object of Interest / Place of Worship" (OS AddressBase Core overview page). All religions; no Christian sub-code found.
- Licence: paid or PSGA (public-sector members); no source says charities qualify. Derived-data publication described only for PSGA members. AddressBase/Plus end of life Autumn 2027. → do not use volunteer's copy until its licence is shown.
- Open alternatives: OSM amenity=place_of_worship + religion/denomination (global 1.63m objects; no UK count sourced; licence wording not fetched). OS Open Map Local "important buildings" likely includes Church/Chapel (VectorMap Local spec; Open release unconfirmed). OS Open UPRN: no classification. Royal Mail PAF: free non-commercial for charities <£10m income; addresses only.

## RT-5 Cost (confidence: MEDIUM)
- Prices (platform.claude.com pricing, checked 2026-10-28): Haiku 5.5 $0.10/$0.50 per MTok (≤100k prompt), batch 50% off; Sonnet 5.5 $2/$10. Gemini 2.5 Flash-Lite $0.10/$0.40, 258 tokens/page for PDFs. gpt-5-nano $0.05/$0.40.
- Claude PDFs: "1,500–3,000 tokens per page" text + image tokens (image estimate unverified).
- Full read 8k PDFs × 15 pp: Haiku 5.5 ≈ £37 (£19 batch); Sonnet 5.5 ≈ £741; Gemini Flash-Lite ≈ £3.
- Hybrid (regex 60%, LLM 3 pages for rest): Haiku ≈ £3/yr at 8k PDFs.
- Gemini free tier: data-use terms UNVERIFIED — matters (trustee names).

## RT-4 Accounts disclosure (confidence MEDIUM-HIGH on verdict)
- SORP classifies cash by purpose/maturity, not account type: cash at bank = "held to meet short-term cash commitments"; deposits held for investment → current asset investments (CFG factsheet quoting SORP 10.74/10.70, older edition; current Module 10 UNREAD).
- R&P accounts (≤£250k, CC16): statement of assets & liabilities; PCC bank balances reported per FUND, not per account type (churchofengland.org/node/10826).
- Bankers line: likely optional; UNVERIFIED (CC templates unreadable).
- Parish Giving Scheme pays into the PCC's own bank account (~by the 10th; sources differ on timing) → inside cash figure. Diocese-held funds: reporting UNVERIFIED.
- CC register: Part B only for income > £500k; field assets_cash = cash at bank and in hand incl. on-demand deposits. No other cash field.
- Verdict: current accounts are NOT measurable from public data. Define measure as "cash at bank and in hand per published accounts" = upper bound on current-account balances.

## RT-6 verification (lead, 2026-10-28)
- OSCR field PDF read locally (updated 29 Aug 2022): CONFIRMED fields — Charity Number, Name, Status, Postcode, Constitutional Form, Main Operating Location, Purposes (multi-value incl. "The advancement of religion"), Website, Income, Expenditure, Year end, Parent Charity Name/Number, **"Designated Religious body" Yes/No** ("whether or not the charity's principal purpose is as the advancement of religion"). No cash/bank-balance field. Income breakdown only for income ≥ £250k.
- CCNI export URL returns an HTML page, not a CSV, to a plain GET → export needs the search UI (filtered). Columns still UNVERIFIED.
- Claude pricing CONFIRMED on platform.claude.com/docs/en/about-claude/pricing.md: Haiku 5.5 $0.10 in / $0.50 out (≤100k prompt), batch $0.05/$0.25; Sonnet 5.5 $2/$10, batch $1/$5. Note: a full 15-page PDF in ONE request stays under 100k tokens (~60k) → low tier holds.
- ACNY terms quote CONFIRMED verbatim: "reproduce, duplicate, copy or re-sell any part of our site in contravention of the provisions of this policy".
- CC Data Definition.docx CONFIRMED verbatim: assets_cash "includes deposits with banks and other financial institutions, which are repayable on demand, but excludes bank overdrafts"; "charities are only required to submit a part B when their income for that year exceeds £500k".
