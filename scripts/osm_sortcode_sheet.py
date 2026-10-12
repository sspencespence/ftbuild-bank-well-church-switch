#!/usr/bin/env python3
"""Build osm_church_sort_codes.xlsx (path = first argument) from the OSM crawl (church_rows.json + sort_codes.jsonl).
Sort code -> bank via the verified sort_code_banks.csv; else the bank named next to the code on the page; never guessed."""
import json, csv, collections, openpyxl
from openpyxl.styles import Font, PatternFill
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bank_ratings import RATINGS  # noqa: E402  (the one shared rating table)
from bankwell_paths import DATA  # noqa: E402
O = DATA / "osm-crawl"
OUT = sys.argv[1] if len(sys.argv) > 1 else "osm_church_sort_codes.xlsx"
codes = {r["sort_code"]: r for r in csv.DictReader(open(DATA / "sortcode-banks/sort_code_banks.csv"))}
NAMES = [('royal bank of scotland','Royal Bank of Scotland'),('bank of scotland','Bank of Scotland'),('national westminster','NatWest'),('nat west','NatWest'),('natwest','NatWest'),('barclays','Barclays'),('hsbc','HSBC'),('lloyds','Lloyds'),('santander','Santander'),('halifax','Halifax'),('tsb','TSB'),('caf bank','CAF Bank'),('charities aid','CAF Bank'),('co-operative bank','Co-operative Bank'),('co-op bank','Co-operative Bank'),('cooperative bank','Co-operative Bank'),('unity trust','Unity Trust Bank'),('triodos','Triodos Bank'),('charity bank','Charity Bank'),('metro bank','Metro Bank'),('virgin money','Virgin Money'),('clydesdale','Clydesdale Bank'),('nationwide','Nationwide'),('starling','Starling'),('monzo','Monzo'),('handelsbanken','Handelsbanken'),('yorkshire bank','Yorkshire Bank')]
METHOD = {'tier2_bank_published':'bank-published code','tier1_page_consensus':'2+ church pages agree','tier1_single_page':'1 church page names it'}

def rate(b):
    s = (b or '').lower()
    if 'royal bank of scotland' in s: return 'not rated'
    for k in sorted(RATINGS, key=len, reverse=True):
        if k in s: return RATINGS[k]
    return 'not rated'

def named(snippet):
    s = (snippet or '').lower()
    return next((v for k, v in NAMES if k in s), None)

recs = {}
for line in open(O / "sort_codes.jsonl"):
    d = json.loads(line); recs[d["regno"]] = d
rows = json.load(open(O / "church_rows.json"))
share = collections.Counter(r["site_key"] for r in rows)
out, st = [], collections.Counter()
for r in rows:
    d = recs.get(r["site_key"], {}); status = d.get("status", "not crawled")
    found = d.get("sort_codes") or []
    ev = {e["sort_code"]: e for e in d.get("evidence", [])}
    code = found[0] if found else ""
    bank = method = page = snip = ""
    if code:
        e = ev.get(code, {}); page, snip = e.get("page", ""), e.get("snippet", "")
        t = codes.get(code)
        if t and t["bank"] not in ("", "unknown"):
            bank, method = t["bank"], METHOD.get(t["method"], t["method"])
        elif named(snip):
            bank, method = named(snip), "named next to code on this page (single page)"
        else:
            bank, method = "unknown", "not confirmed (no guessing from digits)"
        st["with sort code"] += 1
        st["bank known"] += bank != "unknown"
    else:
        st[status] += 1
    out.append([r["name"], r["denomination"], r["website"], r["postcode"], r["city"], code, "; ".join(found[1:]), bank,
                rate(bank) if bank not in ("", "unknown") else "", method, share[r["site_key"]] - 1, page, snip[:200], status])
hdr = ["church_name (OSM)","denomination","website","postcode","city","sort_code","other_sort_codes_on_page","bank","bank_rating (1 worst, 5 ethical)","how_bank_was_found","other_churches_sharing_this_website","page_url","evidence_snippet (account numbers masked)","crawl_status"]
wb = openpyxl.Workbook(); ws = wb.active; ws.title = "OSM church sort codes"; ws.append(hdr)
for c in ws[1]: c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="325569")
y = PatternFill("solid", fgColor="FFF2A8")
for row in sorted(out, key=lambda x: (x[5] == "", x[0] or "")):
    ws.append(row)
    if row[5]:
        for col in (6, 8): ws.cell(ws.max_row, col).fill = y
for col, w in zip("ABCDEFGHIJKLMN", [34,16,36,10,14,11,16,20,12,30,12,40,60,16]): ws.column_dimensions[col].width = w
ws.freeze_panes = "A2"; ws.auto_filter.ref = ws.dimensions
n = wb.create_sheet("READ ME", 0)
for t in ["OSM church sort codes — crawled 10 Oct 2026",
          f"Source: OpenStreetMap, UK Christian places of worship tagged website / contact:website / url ({len(rows)} churches kept after skipping shared directory sites). Websites already crawled overnight were reused.",
          'Method: homepage + up to 6 giving/donate pages; sort code taken only next to the words "sort code"; account numbers never stored.',
          'Bank: verified sort-code table (bank-published codes or 2+ church pages agreeing), else the bank named next to the code on that page. No guessing from the first two digits — otherwise "unknown".',
          'Check by hand: rows where other_churches_sharing_this_website > 0, and banks found from a single page.',
          "Yellow = sort code and bank found."]:
    n.append([t])
n.column_dimensions["A"].width = 150; n["A1"].font = Font(bold=True, size=13)
wb.save(OUT)
print(dict(st))
print(collections.Counter(row[7] for row in out if row[5]).most_common(8))
