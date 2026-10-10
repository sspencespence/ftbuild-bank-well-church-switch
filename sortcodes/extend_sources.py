"""Add churches from other teammates' sources to the team crawl and look up their banks.

  python extend_sources.py --team-crawl ../../bankwell_churches_matched.csv \
      --martin scraped_sort_codes.csv [--martin-recheck martin_recheck.csv] \
      [--osm-jsonl osm_crawl/sort_codes.jsonl --osm-list osm_new_all.csv] \
      [--recrawl-jsonl recrawl/s0/sort_codes.jsonl ...]

Sources:
  team crawl   bankwell_churches_matched.csv (same columns church_banks.py reads)
  Martin       scraped_sort_codes.csv from the `martin` branch (registered_number, cleansed_base_url,
               sort_code, source_url); only charities the team crawl has no code for are added.
               His regex is not anchored to "sort code", so placeholders and dates leak in.
  Martin re-check (optional) his pages re-fetched with the anchored crawler: a page that loaded
               replaces his codes with the anchored ones (none -> charity dropped); a page that did
               not load keeps his filtered codes, marked verified=martin_only.
  OSM          scripts/crawl_sort_codes.py output for OpenStreetMap churches not in the team list.
               Northern Ireland churches (BT postcode or NI bank) are dropped. A code found on a
               team charity's own website fills that charity if it has none (origin=team_via_osm);
               other pages on a site already covered by a charity are dropped as duplicates.
  Re-crawl     scripts/crawl_sort_codes.py output for team-crawl sites that had no code; fills
               those charities' blank codes (origin=team_recrawl).

Writes one row per church with a code (church_banks.annotate unchanged) plus `origin`,
`verified` and a rough `maybe_not_church` flag, and results/sort_code_map_extended.csv
(one row per code, counting the churches in the church file).
"""
import argparse
import csv
import json
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

import church_banks
from sortcode_lookup import load_table

HERE = Path(__file__).parent
DEFAULT_OUT = HERE / "results" / "church_banks_extended.csv"

NON_CHURCH = re.compile(r"\b(village hall|hall|food ?bank|age (concern|uk)|parish council|town council|school|academy|"
                        r"scouts?|guides|playgroup|pre-?school|museum|club|hospice|community centre)\b", re.I)
CHURCHY = re.compile(r"church|chapel|parochial|parish of|ministr|fellowship|congregation|cathedral|minster|abbey|"
                     r"mission|gospel|christian|methodist|baptist|quaker|friends|evangel|orthodox|pentecost", re.I)
MAX_CODES = 3  # a page yielding more unanchored codes than this is a list of dates
# hosts serving many unrelated churches: sharing one is not a duplicate
SHARED_HOSTS = {"sites.google.com", "docs.google.com", "facebook.com", "m.facebook.com", "linktr.ee"}
NI_BANKS = {"Ulster Bank", "Bank of Ireland", "Danske Bank", "AIB"}  # institutions.csv: Northern Ireland


def digits(code):
    return re.sub(r"\D", "", code or "")


def junk(code):
    """Placeholder codes seen on templates: 12-13-14, 11-11-11, 12-34-56."""
    code = digits(code)
    a, b, c = int(code[:2]), int(code[2:4]), int(code[4:])
    return (b == a + 1 and c == b + 1) or a == b == c or code in {"123456", "654321"}


def bad(code):
    """Junk, or 10-xx (Bank of England: a date such as 10-11-25, not a church account)."""
    return len(digits(code)) != 6 or junk(code) or digits(code).startswith("10")


def read_csv(path):
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        return [{k: v or "" for k, v in r.items()} for r in csv.DictReader(f)]


def martin_rows(martin, have, info, recheck=None):
    """(rows, verified-by-regno, stats) for Martin's charities that the team crawl lacks."""
    scraped = [r for r in martin if r["sort_code"] and r["registered_number"] not in have]
    shared = Counter()
    for url in {(r["source_url"], r["registered_number"]) for r in scraped}:
        shared[url[0]] += 1
    by_regno = {}
    for r in scraped:
        by_regno.setdefault(r["registered_number"], []).append(r)

    pages = {}
    for p in recheck or []:
        for regno in p["regnos"].split(";"):
            pages.setdefault(regno, []).append(p)

    rows, verified, stats = [], {}, Counter(martin_new_charities=len(by_regno), martin_new_rows=len(scraped))
    for regno, got in sorted(by_regno.items()):
        checked = [p for p in pages.get(regno, []) if p["status"] == "checked"]
        if checked:
            codes = sorted({c for p in checked for c in p["anchored_codes"].split(";") if c and not bad(c)})
            hit = [p for p in checked if p["anchored_codes"]]
            url = (hit or checked)[0]["source_url"]
            named = ";".join(sorted({b for p in checked for b in p["bank_mentions"].split(";") if b}))
            how = "anchored"
        else:
            raw = {r["sort_code"] for r in got}
            codes = sorted(c for c in raw if not bad(c)) if len(raw) <= MAX_CODES else []
            url, named = got[0]["source_url"], ""
            how = "martin_only" if recheck is not None else ""
        if not codes:
            stats["martin_dropped"] += 1
            continue
        i = info.get(regno, {})
        rows.append({"charity_number": regno, "charity_name": i.get("charity_name", ""),
                     "income": i.get("income", ""), "denomination": i.get("denomination", ""),
                     "sort_code": ";".join(codes), "bank_named_on_page": named, "sort_code_page_url": url,
                     "sort_code_page_shared_with": str(max(shared.get(url, 1) - 1, 0))})
        verified[regno] = how
        stats[f"martin_{how or 'kept'}"] += 1
    return rows, verified, stats


def domain(url):
    url = (url or "").strip().lower()
    try:
        return urlparse(url if "//" in url else "//" + url).netloc.removeprefix("www.")
    except ValueError:  # malformed, e.g. "[hyphen]..." read as an IPv6 host
        return ""


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def osm_rows(jsonl, osm_list, skip_domains=frozenset(), team_sites=None):
    """(rows, status counts, team matches) from a crawl_sort_codes.py run over OSM churches.

    Drops Northern Ireland churches (BT postcodes). A page on a team charity's own website
    (team_sites: domain -> charity number) is returned in team matches, re-keyed to that charity;
    a page on another site already covered by a charity is dropped as a duplicate."""
    meta = {f"osm:{r['osm_type']}/{r['osm_id']}": r for r in osm_list}
    rows, status, matches = [], Counter(), []
    for rec in read_jsonl(jsonl):
        status[rec["status"]] += 1
        codes = [c for c in rec.get("sort_codes", []) if not junk(c)]
        if not codes:
            continue
        info = meta.get(rec["regno"], {})
        if (info.get("addr:postcode") or "").strip().upper().startswith("BT"):
            status["dropped_ni_postcode"] += 1
            continue
        site = domain(rec["evidence"][0]["page"])
        if site in (team_sites or {}):
            matches.append({**rec, "regno": team_sites[site]})
            continue
        if site in skip_domains:
            status["dropped_duplicate"] += 1
            continue
        rows.append({"charity_number": rec["regno"], "charity_name": rec["name"], "income": "",
                     "denomination": info.get("denomination", ""), "sort_code": ";".join(codes),
                     "bank_named_on_page": ";".join(rec.get("bank_mentions", [])),
                     "sort_code_page_url": rec["evidence"][0]["page"], "sort_code_page_shared_with": "0"})
    return rows, status, matches


def team_sites(team):
    """Website domain -> charity number, for domains that belong to exactly one charity."""
    owners = {}
    for r in team:
        d = domain(r.get("website"))
        if d and d not in SHARED_HOSTS:
            owners.setdefault(d, set()).add(r["charity_number"])
    return {d: n.pop() for d, n in owners.items() if len(n) == 1}


def fill_from_recrawl(rows, recrawl):
    """Fill blank team-crawl codes from a re-crawl; returns the charity numbers filled."""
    found = {}
    for rec in recrawl:
        codes = [c for c in rec.get("sort_codes", []) if not junk(c)]
        if codes:
            found[rec["regno"]] = (codes, rec)
    filled = set()
    for r in rows:
        if r["sort_code"] or r["charity_number"] not in found:
            continue
        codes, rec = found[r["charity_number"]]
        r.update(sort_code=";".join(codes), bank_named_on_page=";".join(rec.get("bank_mentions", [])),
                 sort_code_page_url=rec["evidence"][0]["page"], sort_code_page_shared_with="0")
        filled.add(r["charity_number"])
    return filled


def build(team, martin=None, recheck=None, osm_jsonl=None, osm_list=None, recrawl=None):
    """(crawl rows, origin, verified, stats) combining every source."""
    rows = [{k: r.get(k, "") for k in FIELDS} for r in team]
    origin = {r["charity_number"]: "team_crawl" for r in team if r["sort_code"]}
    stats = Counter()
    if recrawl:
        filled = fill_from_recrawl(rows, recrawl)
        origin.update({n: "team_recrawl" for n in filled})
        stats["team_recrawl_filled"] = len(filled)
    have = {r["charity_number"] for r in rows if r["sort_code"]}
    info = {r["charity_number"]: r for r in team}
    verified = {}
    if martin is not None:
        extra, verified, martin_stats = martin_rows(martin, have, info, recheck)
        stats.update(martin_stats)
        rows += extra
        origin.update({r["charity_number"]: "martin" for r in extra})
    if osm_jsonl:
        known = {domain(r["sort_code_page_url"]) for r in rows if r["sort_code"]}
        known |= {domain(r.get("website")) for r in team}
        extra, status, matches = osm_rows(osm_jsonl, osm_list or [], known - SHARED_HOSTS - {""}, team_sites(team))
        # OSM found a code on a team charity's own site: give it to the charity if it has none
        coded = {r["charity_number"] for r in rows if r["sort_code"]}  # includes Martin's rows
        filled = fill_from_recrawl(rows, [m for m in matches if m["regno"] not in coded])
        origin.update({n: "team_via_osm" for n in filled})
        status["matched_team_filled"] = len(filled)
        status["dropped_duplicate"] += len({m["regno"] for m in matches} - filled)
        rows += extra
        origin.update({r["charity_number"]: "osm" for r in extra})
        stats.update({f"osm_{k}": v for k, v in status.items()})
    return rows, origin, verified, stats


FIELDS = ["charity_number", "charity_name", "income", "denomination", "sort_code",
          "bank_named_on_page", "sort_code_page_url", "sort_code_page_shared_with"]


def main(argv=None):
    p = argparse.ArgumentParser(description="Add teammates' sources to the team crawl and look up banks.")
    p.add_argument("--team-crawl", required=True, help="bankwell_churches_matched.csv")
    p.add_argument("--martin", help="scraped_sort_codes.csv from the martin branch")
    p.add_argument("--martin-recheck", help="anchored re-check of Martin's pages")
    p.add_argument("--osm-jsonl", help="crawl_sort_codes.py output for OSM churches")
    p.add_argument("--osm-list", help="OSM churches fed to the crawl (for denomination)")
    p.add_argument("--recrawl-jsonl", nargs="+", default=[],
                   help="crawl_sort_codes.py output(s) re-crawling team sites that had no code")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--code-map", help="one row per sort code (default: sort_code_map_extended.csv beside --out)")
    args = p.parse_args(argv)

    rows, origin, verified, stats = build(
        read_csv(args.team_crawl), read_csv(args.martin) if args.martin else None,
        read_csv(args.martin_recheck) if args.martin_recheck else None,
        args.osm_jsonl, read_csv(args.osm_list) if args.osm_list else None,
        [rec for path in args.recrawl_jsonl for rec in read_jsonl(path)])

    with tempfile.TemporaryDirectory() as tmp:
        crawl = Path(tmp) / "combined_crawl.csv"
        with open(crawl, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)
        church_banks.annotate(load_table(), church_banks.read_crawl(crawl), Path(tmp))
        res = read_csv(Path(tmp) / "church_banks.csv")
        code_map = read_csv(Path(tmp) / "sort_code_map.csv")
    # OSM covers the UK; drop Northern Ireland churches the postcode check missed
    ni = [r for r in res if origin.get(r["charity_number"]) == "osm" and r["bank"].split(";")[0] in NI_BANKS]
    res = [r for r in res if r not in ni]
    stats["osm_dropped_ni_bank"] = len(ni)
    uses = Counter(c for r in res for c in church_banks.split_codes(r["sort_code"]))
    code_map = [{**e, "churches": uses[digits(e["sort_code"])]} for e in code_map if uses[digits(e["sort_code"])]]
    code_map.sort(key=lambda e: (-e["churches"], e["sort_code"]))
    with open(args.code_map or Path(args.out).with_name("sort_code_map_extended.csv"), "w",
              encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=church_banks.MAP_FIELDS)
        w.writeheader()
        w.writerows(code_map)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["origin", *church_banks.CHURCH_FIELDS, "verified", "maybe_not_church"])
        w.writeheader()
        for r in res:
            n = r["charity_name"]
            w.writerow({"origin": origin.get(r["charity_number"], ""), **r,
                        "verified": verified.get(r["charity_number"], ""),
                        "maybe_not_church": "yes" if NON_CHURCH.search(n) and not CHURCHY.search(n) else ""})
    print(dict(stats))
    print(f"{len(res)} churches -> {out}")
    print("by origin:", dict(Counter(origin.get(r["charity_number"], "") for r in res)))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
