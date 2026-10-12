#!/usr/bin/env python3
"""Turn the website sort-code crawl into a bank per church. No model, no guessing.

Steps (ported from the 10 Oct session, same rules):
  1. Join uk_churches.csv with the crawl (sort_codes.jsonl) and the download logs (manifest.jsonl for the
     Charity Commission, companies-house/manifest.jsonl) -> one row per church, keyed on charity number.
  2. bank_named_on_page = bank names found in the evidence snippets only (text next to the sort code),
     and sort_code_page_shared_with = how many other churches use the same giving page (hand-check those).
  3. Tier 1 (page votes): a page votes only when it shows exactly one sort code and one bank name.
     tier1_page_consensus = >=2 pages, >=80% agree; tier1_single_page = one page; else conflict / needs_lookup.
  4. Tier 2: codes the bank itself publishes (PUBLISHED, from sortcode research notes) override tier 1.
  5. Per church: one bank -> that bank; codes at several banks -> "several_banks" (hand check);
     no confirmed bank -> "unknown". Unknown codes are NEVER guessed from the digit range.
Royal Bank of Scotland is matched before Bank of Scotland (the 10 Oct mislabel) and is not rated.

Writes $BANKWELL_DATA/share/bankwell_churches_matched.csv and $BANKWELL_DATA/sortcode-banks/
{tier1_page_evidence,sort_code_banks}.csv.

Usage: python3 scripts/build_church_banks.py [--churches uk_churches.csv]
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bankwell_paths import DATA, REPO  # noqa: E402

CANON = [(r"CAF\s*Bank", "CAF Bank"), (r"Co-?op(erative)?\s*Bank|Co-op Bank", "Co-operative Bank"), (r"Metro\s*Bank", "Metro Bank"),
         (r"Unity\s*Trust", "Unity Trust Bank"), (r"Triodos", "Triodos Bank"), (r"Charity\s*Bank", "Charity Bank"), (r"Lloyds", "Lloyds"),
         (r"Nat\s*West|National\s*Westminster", "NatWest"), (r"Barclays", "Barclays"), (r"HSBC", "HSBC"), (r"Santander", "Santander"),
         (r"Halifax", "Halifax"), (r"TSB", "TSB"), (r"Nationwide", "Nationwide"), (r"Virgin\s*Money", "Virgin Money"),
         (r"Handelsbanken", "Handelsbanken"), (r"Yorkshire\s*Bank", "Yorkshire Bank"),
         (r"Royal\s*Bank\s*of\s*Scotland|\bRBS\b", "Royal Bank of Scotland"),  # before Bank of Scotland
         (r"Bank\s*of\s*Scotland", "Bank of Scotland"), (r"Ulster\s*Bank", "Ulster Bank"), (r"Clydesdale", "Clydesdale"),
         (r"Starling", "Starling"), (r"Monzo", "Monzo"), (r"\bTide\b", "Tide")]
BANK = re.compile(r"\b(Barclays|HSBC|NatWest|Nat West|National Westminster|Lloyds|Santander|Halifax|TSB|Metro Bank|Nationwide|"
                  r"Virgin Money|Co-?operative Bank|Co-op Bank|Triodos|CAF Bank|Unity Trust|Charity Bank|Handelsbanken|Yorkshire Bank|"
                  r"Bank of Scotland|Ulster Bank|Clydesdale|Starling|Monzo|Tide|Royal Bank of Scotland|RBS)\b", re.I)
# Codes the bank itself publishes (or well-sourced), from sortcode-banks/tier2_research.md
PUBLISHED = {"40-52-40": ("CAF Bank", "high", "customer pages + CAF IBAN code CAFB"),
             "60-83-01": ("Unity Trust Bank", "high", "Unity Trust tariff PDF"),
             "16-58-10": ("Triodos Bank", "high", "Triodos help page"),
             "60-83-16": ("Charity Bank", "high", "Charity Bank FAQ (agency sort code)"),
             "16-52-21": ("Cumberland Building Society", "high", "bank-sourced"),
             "04-06-05": ("Tide", "high", "bank-sourced"),
             "08-92-99": ("Co-operative Bank", "medium", "third-party directory; 08 range = Co-op (Wikipedia)"),
             "23-05-80": ("Metro Bank", "medium", "Wikipedia + Wise"),
             "60-83-71": ("Starling", "medium", "Wikipedia + Wise"),
             "04-00-04": ("Monzo", "medium", "Wikipedia/Wise/Monzo forum staff"),
             "04-00-03": ("Monzo", "medium", "Wikipedia/Wise/Monzo forum staff")}
# bank-ratings.md, keyed on the canonical names above (5 = ethical). Banks not listed -> UNRATED.
RATING = {"Barclays": 1, "HSBC": 1, "NatWest": 1, "Santander": 1, "Standard Chartered": 1, "TSB": 1, "Bank of Scotland": 3,
          "Halifax": 3, "Lloyds": 3, "Tide": 4, "CAF Bank": 5, "Co-operative Bank": 5, "Charity Bank": 5, "Clydesdale": 5,
          "Handelsbanken": 5, "Nationwide": 5, "Metro Bank": 5, "Unity Trust Bank": 5, "Triodos Bank": 5, "Virgin Money": 5,
          "Yorkshire Bank": 5}


def canon(name: str) -> str | None:
    return next((c for pat, c in CANON if re.search(pat, name, re.I)), None)


def latest(path: Path) -> dict:
    d = {}
    if path.exists():
        for line in open(path):
            r = json.loads(line)
            d[r["regno"]] = r
    return d


def church_rows(churches: Path) -> list[dict]:
    """Steps 1-2: one row per church with its sort code, the bank named next to it, and the download logs."""
    sc, ch, cc = latest(DATA / "sort_codes.jsonl"), latest(DATA / "companies-house/manifest.jsonl"), latest(DATA / "manifest.jsonl")
    pagecount = collections.Counter(r["evidence"][0]["page"] for r in sc.values() if r["status"] == "sort_code_found")
    out = []
    for r in csv.DictReader(open(churches, encoding="utf-8", errors="replace")):
        n = r["registered_number"].split(".")[0]
        s, c, p = sc.get(n, {}), ch.get(n, {}), cc.get(n, {})
        found = s.get("status") == "sort_code_found"
        ev = (s.get("evidence") or [{}])[0]
        ch_ok = c.get("status") in ("scan_rendered", "text_bank_found", "text_no_bank")
        cc_ok = p.get("status") == "ok"
        shared = pagecount[ev.get("page")] if found else 0
        out.append({
            "charity_number": n, "charity_name": r["charity_name"], "income": r["income"], "denomination": r["denomination"],
            "website": r["contact_web"], "principal_bank_existing": r["principal_bank"],
            "sort_code": "; ".join(s.get("sort_codes", [])) if found else "",
            "bank_named_on_page": "; ".join(sorted({m.group(1) for e in s["evidence"] for m in BANK.finditer(e["snippet"])}, key=str.lower)) if found else "",
            "sort_code_page_url": ev.get("page", "") if found else "",
            "sort_code_page_shared_with": (str(shared - 1) if shared > 1 else "0") if found else "",
            "sort_code_status": s.get("status", "not_crawled (no website)"),
            "ch_company_number": c.get("company", ""), "ch_status": c.get("status", "not_a_company_or_not_tried") if c else "",
            "ch_filing_date": c.get("filing_date", ""), "ch_document": c.get("document", ""),
            "ch_pdf_file": f"bankwell-data\\companies-house\\pdfs\\{c['pdf']}" if c.get("pdf") else "",
            "ch_page_images_folder": f"bankwell-data\\companies-house\\pages\\{n}" if c.get("status") == "scan_rendered" else "",
            "ch_source_url": c.get("source_url", ""),
            "cc_organisation_number": p.get("org", ""), "cc_status": p.get("status", ""),
            "cc_pdf_file": f"bankwell-data\\pdfs\\{p['pdf']}" if cc_ok else "", "cc_source_url": p.get("source_url", ""),
            "any_new_source": "yes" if (found or ch_ok or cc_ok) else "no"})
    return out


def code_banks(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Steps 3-4: tier-1 page votes, then tier-2 published codes, then rating."""
    votes, churches = collections.defaultdict(collections.Counter), collections.Counter()
    for r in rows:
        if not r["sort_code"]:
            continue
        codes = [c.strip() for c in r["sort_code"].split(";")]
        banks = {canon(b) for b in r["bank_named_on_page"].split(";") if b.strip()} - {None}
        for c in codes:
            churches[c] += 1
            if len(codes) == 1 and len(banks) == 1:
                votes[c][next(iter(banks))] += 1
    tier1, final = [], []
    for c, n in churches.most_common():
        v = votes[c]
        tot = sum(v.values())
        if tot:
            top, k = v.most_common(1)[0]
            agree = k / tot
            status = "tier1_page_consensus" if (k >= 2 and agree >= 0.8) else ("tier1_single_page" if tot == 1 else "conflict")
        else:
            top, k, agree, status = "", 0, 0, "needs_lookup"
        t = {"sort_code": c, "churches": n, "page_bank": top, "pages_agreeing": k, "pages_naming_any_bank": tot,
             "agreement": f"{agree:.0%}" if tot else "", "status": status,
             "all_page_votes": "; ".join(f"{b}:{x}" for b, x in v.most_common())}
        tier1.append(t)
        if c in PUBLISHED:
            bank, conf, src = PUBLISHED[c]
            method = "tier2_bank_published"
            if top and top != bank and status != "needs_lookup":
                src += f" | NOTE pages said {t['all_page_votes']}"
        elif status == "tier1_page_consensus":
            bank, conf, method, src = top, "medium", status, f"{k} church pages agree ({t['all_page_votes']})"
        elif status == "tier1_single_page":
            bank, conf, method, src = top, "low", status, "1 church page names this bank next to the code"
        elif status == "conflict":
            bank, conf, method, src = "", "", "unknown_conflict", f"pages disagree: {t['all_page_votes']} - human check"
        else:
            bank, conf, method, src = "", "", "unknown_needs_lookup", "no bank named; needs a licensed sort-code lookup"
        final.append({"sort_code": c, "churches": n, "bank": bank, "confidence": conf, "method": method,
                      "rating": RATING.get(bank, "" if not bank else "UNRATED"), "evidence": src})
    return tier1, final


def add_church_banks(rows: list[dict], final: list[dict]) -> collections.Counter:
    """Step 5: bank columns per church."""
    look, st = {o["sort_code"]: o for o in final}, collections.Counter()
    for r in rows:
        r.update(bank_from_sort_code="", bank_method="", bank_confidence="", bank_rating="", bank_evidence="")
        if not r["sort_code"]:
            continue
        codes = [c.strip() for c in r["sort_code"].split(";")]
        hits = [look[c] for c in codes if look.get(c, {}).get("bank")]
        banks = sorted({h["bank"] for h in hits})
        if len(banks) == 1:
            h = hits[0]
            r.update(bank_from_sort_code=h["bank"], bank_method=h["method"], bank_confidence=h["confidence"],
                     bank_rating=h["rating"], bank_evidence=h["evidence"])
        elif banks:
            r.update(bank_from_sort_code="; ".join(banks), bank_method="several_banks",
                     bank_rating="; ".join(sorted({str(h["rating"]) for h in hits})),
                     bank_evidence="church lists sort codes at more than one bank - human check")
        else:
            u = [look[c]["method"] for c in codes if c in look]
            r.update(bank_from_sort_code="unknown", bank_method=u[0] if u else "unknown_needs_lookup",
                     bank_evidence="no bank confirmed for this sort code (left unknown, no digit-range guessing)")
        st[r["bank_method"]] += 1
    return st


def write(path: Path, rows: list[dict], fields: list[str], bom: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig" if bom else "utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--churches", default=str(REPO / "uk_churches.csv"))
    a = p.parse_args()
    rows = church_rows(Path(a.churches))
    tier1, final = code_banks(rows)
    st = add_church_banks(rows, final)
    cols = list(rows[0])
    i = cols.index("sort_code_page_shared_with") + 1
    new = ["bank_from_sort_code", "bank_method", "bank_confidence", "bank_rating", "bank_evidence"]
    cols = cols[:i] + new + [c for c in cols[i:] if c not in new]
    write(DATA / "sortcode-banks/tier1_page_evidence.csv", tier1, list(tier1[0]))
    write(DATA / "sortcode-banks/sort_code_banks.csv", final, list(final[0]))
    write(DATA / "share/bankwell_churches_matched.csv", rows, cols, bom=True)
    print(f"{len(rows)} churches, {sum(bool(r['sort_code']) for r in rows)} with a sort code, {len(final)} distinct codes")
    print("per-church bank_method:", dict(st))
    return 0


if __name__ == "__main__":
    sys.exit(main())
