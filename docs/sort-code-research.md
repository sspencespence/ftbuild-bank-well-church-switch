# Tier 2 research: sort code -> bank (researched 2026-10-10)

Method note: web searches returned model-written summaries of pages; the key claims below marked "fetched" were
re-read directly via page fetch. Third-party directories (bank-code.net) block bots (Cloudflare) and were NOT scraped.
Confidence: H = bank's own page or Pay.UK/Vocalink; M = Wikipedia or multiple customer pages agree; L = single third-party; U = from memory/unverified.

## 1. Published sort codes

| Bank | Sort code(s) | Source URL | Confidence |
|---|---|---|---|
| CAF Bank | 40-52-40 (shared by all customers; account no. differs) | Not on cafonline.org (service-quality page fetched: no sort code). Customer pages: https://carshalton-methodist.org.uk/about/our-bank-details/ ; https://cchp.org.uk/donations ; statement https://www.cuckfield.gov.uk/media/documents/meetings/agendas/FC061-a-Bankstatement-caf-31st-march-2023.pdf (IBAN GB##CAFB405240########, "CAFB" bank code + 405240) | M-H (IBAN bank code CAFB is strong evidence). YES, 40-52-40 = CAF Bank |
| Co-operative Bank | Range 08-xx (Wikipedia). 08-92-99 = a Co-op code (Business Direct, Skelmersdale per directory). Other Co-op codes seen: 08-93-03, 08-90-32, 08-92-74, 83-91-25, main 08-01-00 | https://en.wikipedia.org/wiki/Sort_code ; https://bank-code.net/uk-sort-code/089299-the-co_operative-bank-plc (third-party) | M for "08-9x = Co-op"; L for 08-92-99 specifics. No official Co-op page found listing it |
| Unity Trust Bank | 60-83-01 | Unity tariff, paying-in slip text: https://assets.unity.co.uk/Standard-Service-Tariff-Unity-Trust-Bank.pdf | H (bank's own document, via search summary; not re-fetched) |
| Triodos Bank UK | 16-58-10 | https://www.triodos.co.uk/help/about-triodos-bank ("The sort code for Triodos Bank is: 16-58-10") fetched | H |
| Charity Bank | 60-83-16 ("Charity Bank Agency Sort code for internal clearing") | https://charitybank.org/savings-frequently-asked-questions fetched | H. The 3 codes you saw (40-40-01, 20-41-50, 60-22-23) are NOT confirmed as Charity Bank anywhere I could find; treat those pages as pairing errors or the charity's own bank, not Charity Bank's code |
| Metro Bank | 23-05-80 (head office listing) | https://en.wikipedia.org/wiki/Sort_code ; https://wise.com/gb/swift-codes/countries/united-kingdom/metro-bank-swift-code | M. Metro has many 23-05-xx branch codes; no Metro page found. Single code is not exhaustive |
| Nationwide BS | 07-00-00 to 07-49-99 (07-xx), 05-xx?, 82-xx (Scotland, ex-Clydesdale per Wikipedia) | https://en.wikipedia.org/wiki/Sort_code | M (Wikipedia's "05, 07, 82" summary came via fetch tool; verify) |
| Handelsbanken UK | NO own branch codes. Individual customers get a code "which represents NatWest/RBS"; corporate customers a code "representing HSBC". Wikipedia lists 60-95-34 personal | https://www.handelsbanken.co.uk/en/about-us/important-information/sort-codes (fetched) | H. Cannot be identified from sort code alone |
| Starling | 60-83-71 (also 04-00-40 reported) | https://en.wikipedia.org/wiki/Sort_code ; customer sources https://wise.com/il/iban/uk/starling-bank | M. No Starling help page retrieved |
| Monzo | 04-00-04 (older), 04-00-03 newer; Wikipedia range 04-00-03..04-00-08 | https://en.wikipedia.org/wiki/Sort_code ; https://community.monzo.com/t/new-monzo-sort-code/142830 | M (staff replies in community forum, not monzo.com help) |
| Virgin Money / Clydesdale / Yorkshire | Yorkshire Bank 05-xx; Virgin Money 08-60-64, 04-00-79..80, 40-64-25; Clydesdale 82-xx (Wikipedia says 82 now Nationwide). Customers keep sort codes during Nationwide transfer | https://en.wikipedia.org/wiki/Sort_code ; https://uk.virginmoney.com/downloads/pdf/nationwide-transfer/mortgages-clydesdale-bank-and-customer-of-nationwide.pdf | M/L. Ranges are shared historically (05, 82 also legacy); treat as ambiguous brands |
| Ecology Building Society | Wikipedia: 04-13-04..05. BUT its payment-in account is 08-90-72 (a Co-op-range code, ie agency) | https://www.ecology.co.uk/faq-interactive/can-i-pay-money-in-to-my-account-via-interactive/ ; Wikipedia | H for 08-90-72 (via search; not re-fetched) |
| Reliance Bank | Wikipedia: 60-01-73 (NatWest range). Bank "is not a clearing bank and uses National Westminster Bank to act as its agent" | https://en.wikipedia.org/wiki/Reliance_Bank ; https://en.wikipedia.org/wiki/Sort_code | M. Agency case |
| Cumberland BS | 16-52-21 | https://cumberland.co.uk/help-support/payment-details | H (via search summary) |
| Tide | 04-06-05 (ClearBank); e-money accounts via PrePay: 23-69-72 | https://www.tide.co/support/joining/partnerships/what-details-should-i-give-my-clients-to-get-paid/ ; https://www.tide.co/support/help/account-security/how-do-i-receive-payments-with-confirmation-of-payee/ | H for 04-06-05; M for 23-69-72 |

### Specific questions
- 40-52-40 = CAF Bank: YES (M-H, see above).
- 08-92-99 = Co-operative Bank: yes, a Co-op code (L-M); not on a Co-op page.
- 60-83-01 = Unity Trust: YES (H).
- 23-05-80 = Metro Bank: yes (M).
- 16-58-10 = Triodos: YES (H).
- Charity Bank: 60-83-16 (H). 40-40-01 / 20-41-50 / 60-22-23: no evidence found for Charity Bank.
- 82-12-08 and 30-54-66: UNRESOLVED. Searches returned nothing. Only hint: 82-xx is Nationwide-owned (ex-Clydesdale, Scotland) per Wikipedia (M), and 30-xx is Lloyds-range by long-standing convention (U, memory). Do not label without EISCD/API lookup.
- Note: 60-83-xx hosts Unity (60-83-01), Charity Bank (60-83-16) and Starling (60-83-71): one range, different brands. First-two/four digits clearly cannot identify the brand.

## 2. Lookup sources at volume

| Source | What it gives | Cost / terms | Verdict |
|---|---|---|---|
| Pay.UK / Vocalink EISCD | The authoritative file: sort code, BIC, bank/branch title, clearing + settlement info, address. Pay.UK: EISCD is "the central source of information used by all the payment systems" | https://vocalink.com/tools/extended-industry-sort-code-directory/ : Single-site ~GBP 2,117/yr, Distributor ~8,339, Master ~39,414 + VAT (via search summary, prices may be stale). Pay.UK page: quarterly fee, unlimited downloads. Licence forbids sharing/copying outside organisation. Registration via Payment Services Website; customer types: member bank, agency bank, Bacs solution supplier, "Other" | Authoritative but paid and slow; not same-day for a hackathon |
| sortcodes.co.uk / iban.com SortWare REST (authorised Vocalink distributor) | bank, branch, BIC, address, payment-scheme flags, from EISCD | Free trial exists, prices on separate page, terms not stated in docs. https://sortcodes.co.uk/sortware-rest-api-documentation | Best licensed route for ~1,000 codes; check trial credit and ToS first |
| Postcoder bank/sortcode | bankname, branchname, BICs, scheme flags; EISCD-derived | 1 credit/request, key required, prices on site. https://postcoder.com/docs/bank-validation/bank-sortcode | Alternative to above |
| API Ninjas /v1/sortcode | free tier: only sort_code, city, postcode, country, checksum_valid; bank_name & branch_name premium; no commercial use on free tier; source not named | https://api-ninjas.com/api/sortcode | Free tier does NOT give the bank name |
| Wikipedia sort-code page | Range-level ownership (05, 07, 08, 60-83-71...) | CC BY-SA, https://en.wikipedia.org/wiki/Sort_code | Good for sanity-checking, incomplete, ranges not exact |
| bank-code.net and similar scraped directories | Per-code bank name | Bot-blocked (Cloudflare challenge). Terms not reviewed; scraping would breach likely ToS | Do not bulk scrape; manual spot-check only |
| Individual banks' own pages | Authoritative per bank | Open web, small scale | Use for Tier-1 anchors (done above) |

Recommendation (same day): (1) Take the 1,042 distinct codes, run them through a paid-but-trial-friendly EISCD distributor API (sortcodes.co.uk/iban.com or Postcoder), within the trial credits or a small credit pack (1 credit per code = ~1,000 credits, cheap vs EISCD licence), after reading their ToS for batch use. (2) Cross-check against the bank-own codes in table 1. (3) Report "unknown" where the API has no record. Fallback if no API key: exact-code match against table 1 only; leave the rest unlabelled. Caveat: I did not see these vendors' bulk/ToS terms and could not confirm free-trial size; confirm before sending 1,000 requests.

## 3. Clearing bank vs account bank (agency banking)

- Pay.UK: sort codes go to PSPs; indirect participants settle "under an agency relationship with a direct participant (sponsor PSP)" and receive their codes from that sponsor. A sort code "does not necessarily belong to a PSP" that participates (https://www.wearepay.uk/what-we-do/payment-systems/access-to-payment-systems/getting-started/sort-code-information/).
- EISCD/API output reports the code holder (bank/branch title, BIC), i.e. the owning/sponsor institution. Vocalink's EISCD FAQ defines an "Agency Bank" as non-Bacs-member sponsored by a member bank but describes no explicit "owning bank" field (fetched). Postcoder returns bankname/branchname only, no agency field (fetched). So a lookup cannot reliably tell you the brand when the code is leased.
- Real examples: Handelsbanken UK uses NatWest/RBS and HSBC-represented codes; Reliance Bank clears via NatWest; Ecology's payment-in account is in the 08-9x (Co-op) range; Charity Bank and Unity both in 60-83-xx; Tide on ClearBank 04-06-05 (itself a clearing bank for many fintechs).
- Practical rule: treat an exact-code match to a bank-published code as brand evidence (High); treat a range/EISCD owner as "clearing institution only" and label as such; never infer brand from the first digits.
- Exception that proves the rule: the same code may be valid for multiple brands over time (Virgin/Clydesdale/Yorkshire/Nationwide migration keeps old sort codes).
