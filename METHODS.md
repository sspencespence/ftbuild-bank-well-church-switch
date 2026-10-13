# Quantifying the UK church finance in ethical banks

We want to calculate how much cash from UK churches is held with ethical banks.
Shared github repo: https://github.com/sspencespence/ftbuild-bank-well-church-switch/tree/main

We've pulled table of charities from the charity commission register public extract:
- charity (name, registered number, description, postcode, contact)
- financial parta (income, expenditure)
- financial partb (income, expenditure, gain/loss, assets, funds)

Then we apply filters:
1. must be an active registered charity
2. check for church or denomination key words in the charity name and activities description
3. Remove any which don't do Religious activities 
4. Remove any with name "CHURCH LAND" (associated with assets rather than current cash)
5. Remove any with url address with domain .ac.uk (educational institution)
Note: Currently we're including Diocese Boards which potentially oversee several churches within the diocese and also give funds to other diocese-related activities

Ranking of how ethical banks are was obtained from bank.green site

Challenges:
- ambiguity in what is a church (e.g. we misclassified Trinity College Cambridge, neet to filter those out. e.g. Alpha came down as a Christian charity, but it's not a church). For this project only church checking accounts are in scope (ignore other Christian charities, ignore savings and assets)
- charity commission register servers went down, 502 and 504 errors
- register doesn't give us the bank, sometimes get from accounts pdf but often missing. scraped webpages to find giving account details to get sort codes which we convert into bank names. still many missing.
- we want to know asset_cash: the cash they have in the bank, but this is missing for most entities (only obliged to submit that info if their income is >£500k)
- some churches don't have a single account, and we might not be able to resolve the ambiguity
- pdfs we extracted from accounts have ~£100k: a skewed sample towards the lower end
- using AI agents to extract data from tables in pdfs, not able to validate all of its results


Directions: 
1. Fill in the data set - extract as much data as we can from church websites / charity commission / etc to fill out our data set as much as possible 
  1.a. AI agents scraped sort codes from the charity websites giving pages, 
  1.b. created a map of sort codes to bank names using agents that probe a checking site
  1.c. used submitted accounts pdfs to extract more financial information from tables
2. Test the appropriateness of extrapolation - test how reliably we could extrapolate from this data with the gaps that we have, work out how else we might extract insights from this data
  2.a. analyse trends between variables of income, expenditure, location, and asset cash.
3. Tell a story with the data - decide on exactly what story we are trying to tell and what we need in order to tell it. Make sure that by the end of day we have a new website page telling that story!
4. making a google app script to re-run the analysis, keeping a live sheet with the results and allowing API to pull into a website -- note: if the pdf is that same as last time you don't need to re-run it
## What was done for 1.a–1.c (added 12 Oct) — full detail in HANDOVER.md

- **1.a Sort codes:** crawled church websites' giving/contact pages (robots.txt respected, account numbers
  masked at source): 2,401 churches with a sort code. Skill: `.claude/skills/find-church-banks`.
- **1.b Sort code → bank:** bank-published codes first, then agreement between church pages that name the bank
  next to the code; unknown codes left unknown (no digit-range guessing) → 1,728 churches with one bank;
  90% agree with the bank in their accounts.
- **1.c Accounts PDFs:** 7,563 accounts read by Claude (Sonnet) with page + exact quote for every figure,
  a mechanical evidence check and a blind Opus re-read (99.6% agreement). Accepted: cash 4,840, total funds
  4,202, net assets 3,697, bankers 2,637. Output: `results/pdf_extract_final.csv` (+ `pdf_extract_details.csv`).
  Skill: `.claude/skills/extract-pdf-accounts`.
- **Challenge added:** the register's document store failed overnight while downloading largest-first, so
  there are no Charity Commission PDFs for £150k–£500k income churches — the PDF sample is skewed low.
- **Headline:** `scripts/headline.py` (skill `refresh-headline`) — 3,827 churches with a verified bank,
  31% ethical, £178.7m at worst-rated banks.
