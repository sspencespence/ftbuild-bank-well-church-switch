#!/usr/bin/env python3
"""Link every OpenStreetMap church (osm_all.csv) to a registered church charity, then carry over what we know.

Match rules, strongest first (a building takes the first that fires):
  website        same website as the charity's registered website (directory/shared sites excluded)
  domain         same web domain (e.g. stmarys.org.uk/give vs stmarys.org.uk)
  postcode+name  same full postcode AND a distinctive word in both names (one charity only)
Postcode-only matches are NOT used (mostly wrong in our earlier check).
Carried over from the charity: income, cash, cash source, bank (accounts first, then sort code), rating.

Usage: .venv/bin/python scripts/link_osm_to_charities.py "<sheet with PDF figures>.xlsx" osm_churches_linked.xlsx
"""
import collections, csv, re, sys
from pathlib import Path
import openpyxl
from openpyxl.styles import Font, PatternFill

sys.path.insert(0, str(Path(__file__).parent))
from bank_ratings import RATINGS  # noqa: E402  (the one shared rating table)
from bankwell_paths import DATA, REGISTER  # noqa: E402

OSM = DATA / "osm-crawl/osm_all.csv"
SHEET = sys.argv[1] if len(sys.argv) > 1 else "Bankwell Data Analysis - with PDF figures.xlsx"
OUT = sys.argv[2] if len(sys.argv) > 2 else "osm_churches_linked.xlsx [osm_churches_linked.csv]"
DIRECTORY = ("jw.org", "achurchnearyou.com", "churchofjesuschrist.org", "catholicdirectory.org", "facebook.com", "salvationarmy.org.uk",
             "instagram.com", "twitter.com", "wikipedia.org", "google.com", "youtube.com", "linktr.ee", "methodist.org.uk",
             "churchofscotland.org.uk", "quaker.org.uk", "britishlistedbuildings.co.uk", "wordpress.com", "weebly.com", "wixsite.com",
             "blogspot.com", "org.uk/churches", "findachurch")
COMMON = {"church", "chapel", "saint", "st", "the", "of", "and", "parish", "united", "free", "hall", "centre", "christian", "fellowship",
          "ministries", "mission", "trust", "charity", "council", "parochial", "ecclesiastical", "baptist", "methodist", "catholic", "roman",
          "anglican", "evangelical", "pentecostal", "reformed", "congregational", "community", "new", "life", "all", "saints", "mary",
          "virgin", "christ", "holy", "trinity", "john", "peter", "paul", "andrew", "michael", "angels", "james", "church's", "chapel's"}
UMBRELLA_MIN = 5  # buildings sharing one charity via its website before we call it an umbrella body


def norm_url(u):
    u = str(u or "").strip().lower()
    u = re.sub(r"^https?://", "", u); u = re.sub(r"^www\.", "", u)
    return u.split("#")[0].split("?")[0].rstrip("/")


def shared(u):
    return any(d in u for d in DIRECTORY)


def norm_pc(pc):
    return re.sub(r"\s+", "", str(pc or "")).upper()


def words(name):
    return {w for w in re.findall(r"[a-z]{3,}", str(name or "").lower()) if w not in COMMON}


def rate(b):
    s = (b or "").lower()
    if not s: return ""
    if "royal bank of scotland" in s: return "not rated"
    for k in sorted(RATINGS, key=len, reverse=True):
        if k in s: return RATINGS[k]
    return "not rated"


def outward(pc):
    pc = norm_pc(pc)
    return pc[:-3] if len(pc) >= 5 else ""


def add_places(charities):
    """Attach each charity's town words and postcode district from the register's contact address."""
    import io, zipfile
    csv.field_size_limit(10**9)
    with zipfile.ZipFile(REGISTER) as z, z.open(z.namelist()[0]) as raw:
        for r in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace"), delimiter="\t"):
            c = charities.get(r["registered_charity_number"])
            if c is None or r["linked_charity_number"] != "0":
                continue
            lines = [r[f"charity_contact_address{i}"] for i in range(2, 6)]
            c["places"] = {re.sub(r"[^a-z ]", "", l.lower()).strip() for l in lines if l and not re.search(r"\d", l)}
            c["district"] = outward(r["charity_contact_postcode"])


DENOMS = {"methodist": "methodist", "baptist": "baptist", "catholic": "catholic", "united reformed": "urc", "urc": "urc",
          "congregational": "congregational", "pentecostal": "pentecostal", "salvation army": "salvation", "quaker": "quaker",
          "friends meeting": "quaker", "latter": "lds", "kingdom hall": "jw", "evangelical": "evangelical", "elim": "elim",
          "parochial church council": "cofe", "parish church": "cofe", "christadelphian": "christadelphian", "gospel hall": "brethren",
          "orthodox": "orthodox", "presbyterian": "presbyterian", "assemblies of god": "aog", "seventh": "adventist", "adventist": "adventist"}
NOT_CHURCH = re.compile(r"\b(hall fund|village hall|recreation|playgroup|pre-?school|school|friends of|heritage|restoration fund|"
                        r"fabric fund|trust fund|war memorial|benefaction|parents|association|brigade|institute|youth|college|almshouse|charity estate|community centre|scout|guide|club|society)\b", re.I)
WEAK = {"rooms", "great", "little", "old", "jesus", "god", "gods", "day", "latter", "gospel", "road", "street", "lane", "village", "east",
        "west", "north", "south", "upper", "lower", "high", "green", "park", "hill", "bridge", "house", "memorial", "meeting", "kingdom",
        "witnesses", "army", "salvation", "elim", "court", "place", "victoria", "king", "kings", "christian", "bethel", "zion", "ebenezer"}


def denoms(name):
    s = str(name or "").lower()
    return {v for k, v in DENOMS.items() if re.search(r"\\b" + k + r"\\b", s)}


FILLER = {"church", "chapel", "the", "of", "and", "st", "saint", "parish", "with", "capel", "eglwys"}


SAINTS = {"john", "mary", "peter", "paul", "james", "andrew", "michael", "thomas", "philip", "matthew", "mark", "luke", "george",
          "nicholas", "martin", "margaret", "anne", "aidan", "basil", "giles", "stephen", "lawrence", "leonard", "bartholomew", "barnabas",
          "edmund", "alban", "augustine", "catherine", "helen", "hilda", "chad", "cuthbert", "oswald", "swithun", "luke", "jude", "simon",
          "saviour", "saviours", "joseph", "patrick", "david", "dunstan", "wilfrid", "botolph", "mildred", "agnes", "faith", "clement",
          "laurence", "francis", "benedict", "anselm", "columba", "ninian", "bride", "brigid", "teilo", "dyfrig", "elizabeth", "magdalene",
          "evangelist", "baptist", "virgin", "apostle", "martyr", "holy", "cross", "trinity", "christ", "saints", "angels", "emmanuel"}
GENERIC = SAINTS | COMMON | WEAK | {"church", "chapel", "with", "on", "in", "le", "by", "less", "apostolic", "orthodox", "greek", "russian",
                                    "spiritualist", "gospel", "road", "parish", "fellowship", "centre", "christian", "community"}


def _saints(ws):
    return {w.rstrip("s") for w in ws if w.rstrip("s") in SAINTS or w in SAINTS} - {"evangelist", "baptist", "virgin", "holy"}


def coverage(osm_name, charity_name, city):
    """Share of the OSM name's meaningful words (minus filler and the town) found in the charity name."""
    ow = {w for w in re.findall(r"[a-z]{2,}", str(osm_name).lower()) if w not in FILLER} - set(city.split())
    cw = set(re.findall(r"[a-z]{2,}", str(charity_name).lower()))
    allo = set(re.findall(r"[a-z]{2,}", str(osm_name).lower())) | set(city.split())
    if not (allo & cw) - GENERIC:
        return 0, 0  # only saint names / generic words shared - not enough to tell parishes apart
    so, sc = _saints(allo), _saints(cw)
    if so and sc and not so & sc:
        return 0, 0  # different dedications
    return (len(ow & cw) / len(ow) if ow else 0), len(ow & cw)


def place_match(o, charities, by_word):
    """Distinctive name word shared AND (same town in the charity's address OR same postcode district). Unique only.
    Stricter than the postcode tiers: drops non-church charities (halls, schools, friends-of), denomination clashes,
    and weak words (great, rooms, jesus, ...) that link unrelated bodies in the same town."""
    ow = words(o["name"]) - WEAK
    if not ow:
        return None, ""
    od = denoms(o["name"]) | ({"cofe"} if (o["denomination"] or "") == "anglican" else set()) | denoms(o["denomination"])
    city = re.sub(r"[^a-z ]", "", (o["addr:city"] or "").lower()).strip()
    district = outward(o["addr:postcode"])
    if not city and not district:
        return None, ""
    cands = set().union(*(by_word.get(w, set()) for w in ow))
    hits = [c for c in cands if (city and city in charities[c].get("places", ())) or (district and district == charities[c].get("district"))]
    hits = [c for c in hits if not NOT_CHURCH.search(str(charities[c]["name"])) and "possibly not" not in charities[c]["flag"]
            and not (od and denoms(charities[c]["name"]) and not od & denoms(charities[c]["name"]))
            and (lambda cv: cv[0] >= 0.75 and cv[1] >= 2)(coverage(o["name"], charities[c]["name"], city))]
    if len(hits) == 1:
        c = charities[hits[0]]
        return hits[0], "name+town" if city and city in c.get("places", ()) else "name+postcode district"
    return None, ""


def main():
    sc = {r["charity_number"]: r["bank_from_sort_code"] for r in csv.DictReader(open(DATA / "share/bankwell_churches_matched.csv", encoding="utf-8-sig"))
          if r["bank_from_sort_code"] not in ("", "unknown") and ";" not in r["bank_from_sort_code"]}
    rows = list(openpyxl.load_workbook(SHEET, read_only=True, data_only=True)["UK Churches (from python script"].iter_rows(values_only=True))
    h = rows[0]; ix = {k: i for i, k in enumerate(h)}
    charities, by_url, by_dom, by_pc = {}, {}, collections.defaultdict(set), collections.defaultdict(list)
    for r in rows[1:]:
        reg = str(r[ix["registered_number"]]).split(".")[0]
        flag = str(r[ix["flag"]] or "")
        acc = r[ix["bankers_from_accounts"]]
        bank, bsrc = (acc.split(";")[0].strip(), "accounts") if acc else ((sc[reg], "sort code") if reg in sc else ("", ""))
        charities[reg] = dict(name=r[ix["charity_name"]], income=r[ix["income"]], cash=r[ix["assets_cash"]], cash_source=r[ix["figures_source"]],
                              bank=bank, bank_source=bsrc, rating=rate(bank), flag=flag)
        u = norm_url(r[ix["contact_web"]])
        if u and not shared(u):
            by_url.setdefault(u, reg)
            by_dom[u.split("/")[0]].add(reg)
        pc = norm_pc(r[ix["contact_postcode"]])
        if pc: by_pc[pc].append(reg)

    add_places(charities)
    by_word = collections.defaultdict(set)
    for reg, c in charities.items():
        for w in words(c["name"]):
            by_word[w].add(reg)

    osm = list(csv.DictReader(open(OSM, encoding="utf-8")))
    out, st = [], collections.Counter()
    for o in osm:
        web = o["website"] or o["contact:website"] or o["url"]
        u = norm_url(web); reg, how = None, ""
        if u and not shared(u):
            if u in by_url: reg, how = by_url[u], "website"
            elif len(by_dom.get(u.split("/")[0], ())) == 1: reg, how = next(iter(by_dom[u.split("/")[0]])), "domain"
        if not reg:
            pc = norm_pc(o["addr:postcode"]); ow = words(o["name"])
            if pc and ow:
                hits = [c for c in by_pc.get(pc, []) if ow & words(charities[c]["name"])]
                if len(hits) == 1: reg, how = hits[0], "postcode+name"
        if not reg:
            reg, how = place_match(o, charities, by_word)
        st[how or "not linked"] += 1
        c = charities.get(reg, {})
        out.append([o["@type"], int(o["@id"]), o["name"], o["denomination"], web, o["addr:postcode"], o["addr:city"],
                    float(o["@lat"]) if o["@lat"] else None, float(o["@lon"]) if o["@lon"] else None,
                    how or "not linked", int(reg) if reg and reg.isdigit() else reg, c.get("name"), c.get("income"),
                    c.get("cash"), c.get("cash_source"), c.get("bank"), c.get("bank_source"), c.get("rating"), c.get("flag")])
        if reg:
            st["linked with cash"] += c.get("cash") not in (None, "")
            st["linked with bank"] += bool(c.get("bank"))
    per_charity = collections.Counter(r[10] for r in out if r[10])
    # A charity whose one website covers many buildings is an umbrella body (e.g. Churches Conservation Trust),
    # not the congregation: keep the link visible but don't pass its bank/cash to the building.
    umbrella = {c for c, n in per_charity.items() if n > UMBRELLA_MIN}
    for r in out:
        if r[10] in umbrella and r[9] in ("website", "domain"):
            r[9] = "umbrella body's website (not this church's own)"
            r[13:18] = [None, None, None, None, None]
    st = collections.Counter(r[9] for r in out)
    st["linked with cash"] = sum(1 for r in out if r[10] and r[10] not in umbrella and r[13] not in (None, ""))
    st["linked with bank"] = sum(1 for r in out if r[10] and r[10] not in umbrella and r[15])

    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "OSM churches linked"
    hdr = ["osm_type", "osm_id", "church_name (OSM)", "denomination", "website", "postcode", "city", "lat", "lon", "link_method",
           "charity_number", "charity_name", "charity_income", "cash_at_bank", "cash_source", "bank", "bank_source", "bank_rating (1 worst, 5 ethical)",
           "charity_flag", "buildings_linked_to_this_charity"]
    ws.append(hdr)
    for cell in ws[1]: cell.font = Font(bold=True, color="FFFFFF"); cell.fill = PatternFill("solid", fgColor="325569")
    y = PatternFill("solid", fgColor="FFF2A8")
    for r in sorted(out, key=lambda r: (r[9] == "not linked", r[2] or "")):
        ws.append(r + [per_charity.get(r[10], 0) if r[10] else None])
        if r[9] != "not linked":
            ws.cell(ws.max_row, 11).fill = y
    for col, w in zip("ABCDEFGHIJKLMNOPQRST", [8, 12, 30, 14, 30, 10, 13, 9, 9, 13, 11, 40, 11, 12, 22, 18, 11, 10, 30, 10]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"; ws.auto_filter.ref = ws.dimensions
    n = wb.create_sheet("READ ME", 0)
    for t in ["OSM churches linked to registered church charities — 10 Oct 2026",
              "Each OpenStreetMap church building is linked to a Charity Commission church charity by: same website > same web domain > same postcode AND a shared distinctive name word > name + same town/postcode district. Postcode alone is never used.",
              "Linked buildings carry the charity's cash, bank and rating. One charity can cover several buildings (e.g. a parish with two churches) — see buildings_linked_to_this_charity; don't add its cash up per building.",
              "name+town / name+postcode district (LOWER CONFIDENCE, ~85-90% right in a 40-row spot check): most of the church's name appears in the charity's name, same town or postcode district in the charity's register address, no denomination clash, not just a shared saint's name, and only one charity fits.",
              "Not linked: no website/postcode match — often Scottish/Northern Irish churches (different regulator), churches below the charity threshold, or name/postcode differences.",
              "umbrella body's website: the building's website belongs to a national/regional body covering many churches - linked for reference only, no cash/bank carried over.",
              "charity_flag: 'possibly not a church' / 'linked charity' rows — check before using.",
              "Map data © OpenStreetMap contributors (ODbL)."]:
        n.append([t])
    n.column_dimensions["A"].width = 150; n["A1"].font = Font(bold=True, size=13)
    wb.save(OUT)
    if len(sys.argv) > 3:  # optional plain CSV copy (for the repo)
        with open(sys.argv[3], "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh); w.writerow(hdr)
            for r in sorted(out, key=lambda r: (r[9] == "not linked", r[2] or "")):
                w.writerow(r + [per_charity.get(r[10], 0) if r[10] else None])
    print(f"{len(out)} OSM churches -> {OUT}")
    for k, v in st.most_common(): print(f"  {k}: {v}")
    print(f"  distinct charities linked: {len(per_charity)}")


if __name__ == "__main__":
    sys.exit(main())
