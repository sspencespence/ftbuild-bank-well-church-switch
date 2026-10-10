"""Check whether each row of church_banks_extended.csv is a church (a congregation or its PCC).

  python church_check.py --bulk C:/Users/Brian/bankwell-data/bulk [--team-filter "filtered data.csv"]

Run after extend_sources.py (which rewrites the file without these columns). Adds two columns
to results/church_banks_extended.csv and writes results/church_check_review.csv (the `unsure`
rows plus the evidence, for a person to decide).

  church_check   church | not_church | unsure
  church_reason  which signals decided it

Signals for charity rows:
  name         church words (church, chapel, PCC, fellowship...) or non-congregation words
               (school, hall, foodbank, "friends of", fund, lands, diocese...)
  class        Charity Commission classification includes "Religious Activities"
  activities   the charity's own activities text mentions worship or services
  team filter  (optional) the teammates' church list: charities in it count as church-like

Then, in order of precedence: OpenStreetMap (--osm-truth) makes any charity whose website or giving
page is a listed church `church`; otherwise results/church_check_decisions.csv (agent + hand review)
settles rows the rules left `unsure`.

A church-attached fund, hall, school or Christian charity is `not_church`: Bank Well's target is
the congregation. OSM rows are places of worship tagged in OpenStreetMap and are marked
`church` without checking (no charity record to check against).
"""
import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from extend_sources import SHARED_HOSTS, domain

HERE = Path(__file__).parent
DEFAULT_FILE = HERE / "results" / "church_banks_extended.csv"
DEFAULT_DECISIONS = HERE / "results" / "church_check_decisions.csv"

# Not a congregation, even with "church" in the name
NOT_CONGREGATION = re.compile(
    r"\b(schools?|academy|college|nursery|pre-?school|playgroup|toddlers|food ?banks?|church halls?|"
    r"village halls?|community (centre|center|hub|project)|friends of|fabric|restoration|appeal|"
    r"almshouses?|charity of|charities|bequest|scouts?|guides|youth club|hospice|counsell?ing|"
    r"museum|heritage|historic churches|housing|choir|ringers|bells|festival|bookshop|cafe|debt|"
    r"y\.?[mw]\.?c\.?a|young (men|women)'?s christian association|shelter|street pastors|street angels|pregnancy|board of finance|parish council|"
    r"town council|relief in need|educational|churchyard)\b", re.I)
# Not a congregation unless the name also says church, chapel, PCC...
WEAK_NOT = re.compile(r"\b(halls?|lands?|estates?|funds?|foundation|diocesan|diocese|"
                      r"club|homes|poor)\b", re.I)
OTHER_FAITH = re.compile(r"islam|muslim|masjid|mosque|synagogue|jewish|hebrew|gurdwara|sikh|hindu|"
                         r"mandir|temple|buddhis|vihara|jain", re.I)
CHURCH_NAME = re.compile(
    r"church|chapel|\bparish\b|\bp\.?c\.?c\b|parochial|fellowship|congregation|assembl(y|ies)|"
    r"tabernacle|cathedral|minster|gospel hall|kingdom hall|meeting house|quakers|"
    r"society of friends|\bcorps\b|citadel|\bbenefice\b|\bkirk\b", re.I)
# activities text in which the charity describes itself as a worshipping church
SELF_CHURCH = re.compile(
    r"\b(we are|is|as) an? [\w\s,-]{0,40}church\b|\bour church\b|\bchurch services\b|"
    r"\b(sunday|weekly|regular|public|church|congregational) (worship|services|meetings|gatherings)\b|"
    r"\bservices of worship\b|\bworship services\b|\bcongregation\b|\bsacraments?\b|\beucharist\b|"
    r"\bholy communion\b|\bparish\b", re.I)


def classify(name, classes, activities, in_team):
    """Return (church_check, church_reason)."""
    religious = "Religious Activities" in classes
    church_name = bool(CHURCH_NAME.search(name))
    self_church = bool(SELF_CHURCH.search(activities))
    if m := NOT_CONGREGATION.search(name):
        return "not_church", f"name: '{m.group(0)}'"
    if (m := WEAK_NOT.search(name)) and not church_name:
        return "not_church", f"name: '{m.group(0)}'"
    if (m := OTHER_FAITH.search(name)) or (not church_name and (m := OTHER_FAITH.search(activities))):
        return "not_church", f"not Christian: '{m.group(0)}'"
    signals = [s for s, on in [("name", church_name), ("class", religious), ("activities", self_church),
                               ("team filter", in_team)] if on]
    if religious and (church_name or self_church):
        return "church", "+".join(signals)
    if not religious and not church_name and not self_church:
        return "not_church", "no religious class, no church in name or activities"
    return "unsure", "only: " + ("+".join(signals) or "none")


def read_tsv(path, ids, cols):
    """Main-charity rows (linked_charity_number 0) of a bulk Charity Commission file for these ids."""
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            if r["linked_charity_number"] == "0" and r["registered_charity_number"] in ids:
                yield {c: r[c] for c in cols}


def site_key(url, directories):
    """Domain of a URL, plus the path when the domain is a directory hosting many churches."""
    host = domain(url)
    if host not in directories:
        return host
    path = urlparse(url if "//" in url else "//" + url).path.lower().rstrip("/")
    return host + path if path else ""


def osm_sites(path):
    """Website keys of the OpenStreetMap church list. A domain used by 3+ churches is a directory
    (achurchnearyou.com, salvationarmy.org.uk, facebook.com): there only the full path matches."""
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        urls = [u.strip() for r in csv.DictReader(f) for u in (r["website"], r.get("contact:website", "")) if u.strip()]
    uses = Counter(domain(u) for u in urls)
    directories = {d for d, n in uses.items() if n >= 3} | SHARED_HOSTS
    return {k for u in urls if (k := site_key(u, directories))}, directories


def main(argv=None):
    p = argparse.ArgumentParser(description="Mark which rows of church_banks_extended.csv are churches.")
    p.add_argument("--bulk", required=True, help="folder with the Charity Commission publicextract.*.txt files")
    p.add_argument("--team-filter", help="teammates' church list (registered_number column)")
    p.add_argument("--osm-truth", help="OpenStreetMap church list (website column): a charity whose website or "
                                       "giving page is on it is a church, whatever the rules say")
    p.add_argument("--decisions", default=str(DEFAULT_DECISIONS),
                   help="hand or agent decisions for unsure rows (charity_number, decision, note)")
    p.add_argument("--file", default=str(DEFAULT_FILE))
    args = p.parse_args(argv)

    path = Path(args.file)
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    fields = [c for c in rows[0] if c not in ("church_check", "church_reason")] + ["church_check", "church_reason"]
    ids = {r["charity_number"] for r in rows}
    bulk = Path(args.bulk)
    activities, websites = {}, {}
    for r in read_tsv(bulk / "publicextract.charity.txt", ids,
                      ["registered_charity_number", "charity_activities", "charity_contact_web"]):
        activities[r["registered_charity_number"]] = r["charity_activities"]
        websites[r["registered_charity_number"]] = r["charity_contact_web"]
    classes = {}
    for r in read_tsv(bulk / "publicextract.charity_classification.txt", ids,
                      ["registered_charity_number", "classification_description"]):
        classes.setdefault(r["registered_charity_number"], []).append(r["classification_description"])
    team = None
    if args.team_filter:
        with open(args.team_filter, encoding="utf-8", errors="replace", newline="") as f:
            team = {r["registered_number"] for r in csv.DictReader(f)}
    osm, directories = osm_sites(args.osm_truth) if args.osm_truth else (set(), set())
    decisions = {}
    if Path(args.decisions).exists():
        with open(args.decisions, encoding="utf-8", newline="") as f:
            decisions = {r["charity_number"]: r for r in csv.DictReader(f)}

    review = []
    for r in rows:
        num = r["charity_number"]
        if r["origin"] == "osm":
            r["church_check"], r["church_reason"] = "church", "OpenStreetMap place of worship"
            continue
        r["church_check"], r["church_reason"] = classify(
            r["charity_name"], classes.get(num, []), activities.get(num, ""), team is not None and num in team)
        if osm & {site_key(u, directories) for u in (websites.get(num, ""), r["page_url"])} - {""}:
            if r["church_check"] != "church":
                r["church_reason"] = f"OpenStreetMap church website (rules said {r['church_check']}: {r['church_reason']})"
            r["church_check"] = "church"
        elif r["church_check"] == "unsure" and num in decisions:
            d = decisions[num]
            r["church_check"], r["church_reason"] = d["decision"], f"reviewed ({d['source']}): {d['note']}"
        if r["church_check"] == "unsure":
            review.append({"charity_number": num, "charity_name": r["charity_name"], "income": r["income"],
                           "denomination": r["denomination"], "church_reason": r["church_reason"],
                           "classification": "; ".join(classes.get(num, [])),
                           "activities": activities.get(num, ""), "website": websites.get(num, ""),
                           "page_url": r["page_url"], "decision": ""})

    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    review.sort(key=lambda r: -float(r["income"] or 0))  # most money first
    review_path = path.with_name("church_check_review.csv")
    with open(review_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(review[0]) if review else ["charity_number"])
        w.writeheader()
        w.writerows(review)
    counts = {}
    for r in rows:
        counts[r["church_check"]] = counts.get(r["church_check"], 0) + 1
    print(counts)
    print(f"{len(review)} rows to review -> {review_path}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
