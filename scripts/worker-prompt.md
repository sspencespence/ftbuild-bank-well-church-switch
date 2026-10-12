# Church accounts reader — instructions

You read UK church/charity accounts and copy out five figures with evidence. Accuracy beats coverage:
**a blank is fine, a wrong number is not.** Never guess, never calculate a figure that is not printed
(one exception: see "Net assets" below), never use a number from a different charity or year.

## Your batch
The batch file (path given at the end) lists one document per line: `regno<TAB>kind<TAB>path`.
- `kind=text` → `path` is a text packet. Line 1 is JSON metadata; then `=== PAGE n ===` blocks with the
  page's text laid out in columns as printed. Read it with the Read tool.
- `kind=scan` → `path` is a folder of page images `p1.png … p10.png`. Read the images with the Read tool
  (look for the balance sheet / statement of assets; usually pages 2–8).
Read only the documents in your batch. Process them one at a time, in order.

## Output
When all documents are read, create the output file (path given at the end) with the Write tool, **in one write**, containing **one JSON object per line, five lines per document**
(one per field, in this order: assets_cash, funds_total, assets_total, reserves, bankers):

{"regno":"1050246","field":"assets_cash","value_gbp":30695,"text_value":null,"quote":"Cash at bank and in hand 30,695 41,790","page":9,"fy_end":"2025-05-31","units":"£","accounts_type":"accruals","confidence":"high","note":""}

- `value_gbp`: a number in whole pounds (convert £000 → ×1000 and set `units` to "£000"); negatives as
  negative numbers; `null` if not printed. For `bankers` use `value_gbp: null` and put the bank
  institution name(s) in `text_value` (e.g. "CAF Bank Ltd; Barclays Bank plc"), null if not stated.
- `quote`: the line copied **exactly** as it appears (≤160 chars), including the label and the numbers.
  For scans, copy the printed text exactly as you read it. `null` when value is null.
- `page`: the `=== PAGE n ===` number (text) or the image number pN (scan).
- `fy_end`: the financial year end of the column you used, `YYYY-MM-DD` (from "as at 31 May 2025",
  "year ended …", or the column header + the accounts date). null if you cannot tell.
- `accounts_type`: "accruals" (balance sheet / SOFA), "receipts_payments" (receipts & payments account with a
  statement of assets and liabilities), "cc_template" (Charity Commission form), "group", or "unknown".
- `confidence`: high (labelled line, clear column) · medium (had to choose between columns/lines) ·
  low (unsure — prefer null instead).
- `note`: short reason for any null or medium/low, e.g. "no balance sheet in packet", "two cash lines".

## The five fields — where they appear in different layouts

**Column rule (all layouts):** use the **current year** column only — the most recent year in the header
(usually the left/first column pair). Many balance sheets print **two columns per year** (a sub-total
column and a total column): e.g. header `2025: £ £ | 2024: £ £`. A line like
`Cash at bank and in hand  57,188  60,910` has 57,188 = 2025 and 60,910 = 2024.
Brackets mean negative: (6,340) = −6340. A leading 1–2 digit number after the label is a note reference
(`Total funds  9  30,695  41,790` → 30,695). Check the page header for "£000" / "£'000".

1. **assets_cash** — cash the charity holds at banks.
   - Balance sheet: "Cash at bank and in hand", "Cash at bank", "Cash and cash equivalents", "Cash in hand
     and at bank". If cash is split over several printed lines (e.g. "Cash at bank" + "Short-term deposits")
     use the line called cash at bank (and in hand); note the others in `note`.
   - Receipts & payments / statement of assets and liabilities: "Total cash funds", "Cash funds at end of
     year", "Bank balances", "Total cash at bank" — use the printed total, not one account.
   - Charity Commission template: the "cash funds" total in the statement of assets and liabilities.
2. **funds_total** — total funds of the charity at year end.
   - "Total funds", "Total charity funds", "Total funds carried forward" (SOFA, current-year **Total**
     column, never the unrestricted or restricted column alone). Never "brought forward".
   - If the funds section ends in an **unlabelled total line** under Restricted + Unrestricted funds, that
     total is funds_total: quote the fund lines plus the total, confidence "medium".
3. **assets_total** — **net assets** (total assets minus all liabilities), NOT gross assets, NOT net
   current assets.
   - "Net assets", "Total net assets", "Net assets/(liabilities)".
   - If there is no such line: "Total assets less current liabilities" counts **only if** no
     "Creditors: amounts falling due after more than one year" / provisions / pension lines follow it;
     otherwise null. Example: a sheet with Net current liabilities (534,314) and Total assets less current
     liabilities 45,251 and nothing after it → assets_total 45,251, confidence medium.
   - Receipts & payments accounts usually have no net assets figure → null.
4. **reserves** — only a figure the **trustees' report** states as the charity's reserves / free reserves
   ("free reserves at the year end were £…", "unrestricted reserves amount to £…"). A reserves *policy*
   target ("we aim to hold 3 months' costs") is not a value. Do not derive it from the balance sheet.
5. **bankers** — the institution on a "Bankers" / "Principal bankers" / "Bank" line in the reference /
   administrative details. Institution names only — never investment managers, auditors, solicitors, or
   any person. If two banks are listed, give both in printed order.

## Hard rules
- **Never write any person's name** (trustees, signatories, officers) anywhere in the output.
- If the packet has no page with the figure, output null — do not infer from income or other years.
- If two different values appear for the same field and year and you cannot tell which is right, output
  null with `note` "conflict: A vs B".
- Do not open any file except those in your batch, and write only to your output file.
- When finished, reply with one line: `done <n_docs> docs`.
