import csv
import json

import pytest

import church_banks
import extend_sources as es

TEAM = [
    {"charity_number": "1", "charity_name": "St A", "income": "1000", "denomination": "CofE",
     "sort_code": "40-52-40", "bank_named_on_page": "CAF Bank", "sort_code_page_url": "https://a.example/give",
     "sort_code_page_shared_with": "0", "website": "a.example"},
    {"charity_number": "2", "charity_name": "St B", "income": "2000", "denomination": "Baptist",
     "sort_code": "", "bank_named_on_page": "", "sort_code_page_url": "", "sort_code_page_shared_with": ""},
    {"charity_number": "3", "charity_name": "St C", "income": "3000", "denomination": "Methodist",
     "sort_code": "", "bank_named_on_page": "", "sort_code_page_url": "", "sort_code_page_shared_with": ""},
    {"charity_number": "4", "charity_name": "St D Hall", "income": "4000", "denomination": "Unknown",
     "sort_code": "", "bank_named_on_page": "", "sort_code_page_url": "", "sort_code_page_shared_with": ""},
]


def m(regno, code, url):
    return {"registered_number": regno, "cleansed_base_url": url, "sort_code": code, "source_url": url}


MARTIN = [
    m("1", "40-52-40", "https://a.example/give"),          # team already has it: ignored
    m("2", "40-11-58", "https://b.example/give"),
    m("2", "12-13-14", "https://b.example/give"),          # placeholder
    m("3", "10-11-25", "https://c.example"),               # Bank of England prefix: a date
    *[m("4", f"0{i}-0{i}-1{i}", "https://d.example") for i in range(1, 5)],  # 4 codes: a date list
]


@pytest.mark.parametrize("code,expected", [
    ("12-13-14", True), ("11-11-11", True), ("123456", True), ("40-11-58", False), ("08-92-99", False)])
def test_junk(code, expected):
    assert es.junk(code) is expected


def test_bad_rejects_bank_of_england_prefix():
    assert es.bad("10-11-25") and not es.bad("20-11-25")


def test_martin_filters_without_recheck():
    rows, verified, stats = es.martin_rows(MARTIN, {"1"}, {r["charity_number"]: r for r in TEAM})
    assert [(r["charity_number"], r["sort_code"]) for r in rows] == [("2", "40-11-58")]
    assert rows[0]["charity_name"] == "St B" and rows[0]["income"] == "2000"
    assert verified == {"2": ""}
    assert stats["martin_dropped"] == 2                     # 3: only 10-xx; 4: more than 3 codes


def recheck(url, regnos, status, anchored="", banks=""):
    return {"source_url": url, "regnos": regnos, "martin_codes": "", "status": status,
            "anchored_codes": anchored, "bank_mentions": banks}


def test_recheck_precedence():
    martin = [m("2", "40-11-58", "https://b.example/give"), m("3", "20-20-21", "https://c.example"),
              m("4", "30-90-92", "https://d.example")]
    rc = [recheck("https://b.example/give", "2", "checked", "40-38-07", "HSBC"),   # anchored replaces Martin's
          recheck("https://c.example", "3", "checked"),                           # loaded, nothing anchored
          recheck("https://d.example", "4", "unreachable")]                       # keeps Martin's
    rows, verified, _ = es.martin_rows(martin, set(), {}, rc)
    got = {r["charity_number"]: (r["sort_code"], r["bank_named_on_page"]) for r in rows}
    assert got == {"2": ("40-38-07", "HSBC"), "4": ("30-90-92", "")}
    assert verified == {"2": "anchored", "4": "martin_only"}


def test_osm_rows(tmp_path):
    jsonl = tmp_path / "sort_codes.jsonl"
    recs = [{"regno": "osm:node/1", "name": "Chapel", "status": "sort_code_found", "sort_codes": ["40-11-58"],
             "evidence": [{"page": "https://o.example/give"}], "bank_mentions": ["HSBC"]},
            {"regno": "osm:node/2", "name": "Kirk", "status": "sort_code_found", "sort_codes": ["12-13-14"],
             "evidence": [{"page": "https://k.example"}], "bank_mentions": []},
            {"regno": "osm:node/3", "name": "Abbey", "status": "no_sort_code"}]
    jsonl.write_text("\n".join(json.dumps(r) for r in recs), encoding="utf-8")
    rows, status, _ = es.osm_rows(jsonl, [{"osm_type": "node", "osm_id": "1", "denomination": "baptist"}])
    assert [(r["charity_number"], r["denomination"], r["bank_named_on_page"]) for r in rows] == \
        [("osm:node/1", "baptist", "HSBC")]
    assert status == {"sort_code_found": 2, "no_sort_code": 1}


def osm_rec(n, code, page, banks=()):
    return {"regno": f"osm:node/{n}", "name": f"Church {n}", "status": "sort_code_found", "sort_codes": [code],
            "evidence": [{"page": page}], "bank_mentions": list(banks)}


def test_osm_drops_ni_postcode_and_known_sites(tmp_path):
    jsonl = tmp_path / "sort_codes.jsonl"
    recs = [osm_rec(1, "40-11-58", "https://keep.example/give"),
            osm_rec(2, "40-11-58", "https://belfast.example/give"),      # BT postcode
            osm_rec(3, "40-11-58", "https://www.b.example/donate"),      # site Martin already covers
            osm_rec(4, "40-11-58", "https://sites.google.com/view/x")]   # shared host: not a duplicate
    jsonl.write_text("\n".join(json.dumps(r) for r in recs), encoding="utf-8")
    meta = [{"osm_type": "node", "osm_id": "2", "addr:postcode": "bt9 6aa"}]
    rows, status, _ = es.osm_rows(jsonl, meta, {"b.example"})
    assert [r["charity_number"] for r in rows] == ["osm:node/1", "osm:node/4"]
    assert status["dropped_ni_postcode"] == 1 and status["dropped_duplicate"] == 1


@pytest.mark.parametrize("url,expected", [
    ("https://www.a.example/give", "a.example"), ("a.example", "a.example"), ("[hyphen]x.example", ""), ("", "")])
def test_domain(url, expected):
    assert es.domain(url) == expected


def test_recrawl_fills_blank_team_codes_only():
    rows = [{k: r.get(k, "") for k in es.FIELDS} for r in TEAM]
    recrawl = [osm_rec(0, "20-20-20", "https://x.example") | {"regno": "1"},          # team has a code: kept
               osm_rec(0, "40-38-07", "https://b.example/give", ["HSBC"]) | {"regno": "2"},
               osm_rec(0, "12-13-14", "https://c.example") | {"regno": "3"}]          # placeholder
    assert es.fill_from_recrawl(rows, recrawl) == {"2"}
    by = {r["charity_number"]: r for r in rows}
    assert by["1"]["sort_code"] == "40-52-40" and by["3"]["sort_code"] == ""
    assert (by["2"]["sort_code"], by["2"]["bank_named_on_page"], by["2"]["sort_code_page_url"]) == \
        ("40-38-07", "HSBC", "https://b.example/give")


def test_recrawl_beats_martin_and_ni_bank_dropped(tmp_path):
    team, martin, rc = tmp_path / "team.csv", tmp_path / "martin.csv", tmp_path / "rc.jsonl"
    osm, osm_list = tmp_path / "osm.jsonl", tmp_path / "osm.csv"
    write(team, TEAM)
    write(martin, MARTIN)
    rc.write_text(json.dumps(osm_rec(0, "40-38-07", "https://b.example/give") | {"regno": "2"}), encoding="utf-8")
    osm.write_text("\n".join(json.dumps(r) for r in [osm_rec(1, "40-11-58", "https://o.example"),
                                                     osm_rec(2, "95-02-31", "https://ni.example")]),
                   encoding="utf-8")
    write(osm_list, [{"osm_type": "node", "osm_id": "1", "addr:postcode": "SW1A 1AA"}])
    out = tmp_path / "extended.csv"
    assert es.main(["--team-crawl", str(team), "--martin", str(martin), "--osm-jsonl", str(osm),
                    "--osm-list", str(osm_list), "--recrawl-jsonl", str(rc), "--out", str(out)]) == 0
    got = {(r["origin"], r["charity_number"], r["sort_code"]) for r in read(out)}
    assert ("team_recrawl", "2", "40-38-07") in got                 # Martin's 40-11-58 for 2 not used
    assert not any(n == "2" and o == "martin" for o, n, _ in got)
    assert ("osm", "osm:node/1", "40-11-58") in got
    assert not any(n == "osm:node/2" for _, n, _ in got)            # 95- is Danske Bank


def test_osm_code_on_team_site_fills_that_charity(tmp_path):
    team = [dict(TEAM[0]), dict(TEAM[1], website="www.b.example"), dict(TEAM[2], website="c.example"),
            dict(TEAM[3], website="sites.google.com")]
    osm = tmp_path / "osm.jsonl"
    osm.write_text("\n".join(json.dumps(r) for r in [
        osm_rec(1, "20-20-21", "https://a.example/give"),       # charity 1 already has a code: dropped
        osm_rec(2, "40-11-58", "https://b.example/give"),       # charity 2 has Martin's code: dropped
        osm_rec(3, "40-38-07", "https://www.c.example/donate"),  # charity 3 has none: filled
        osm_rec(4, "30-90-92", "https://sites.google.com/view/y")]), encoding="utf-8")  # shared host: own row
    rows, origin, _, stats = es.build(team, [m("2", "40-11-58", "https://b.example/give")], osm_jsonl=osm)
    coded = [(origin[r["charity_number"]], r["charity_number"], r["sort_code"]) for r in rows if r["sort_code"]]
    assert coded == [("team_crawl", "1", "40-52-40"), ("team_via_osm", "3", "40-38-07"),
                     ("martin", "2", "40-11-58"), ("osm", "osm:node/4", "30-90-92")]
    assert stats["osm_matched_team_filled"] == 1 and stats["osm_dropped_duplicate"] == 2


def write(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_team_rows_pass_through_unchanged(tmp_path):
    team, martin = tmp_path / "team.csv", tmp_path / "martin.csv"
    write(team, TEAM)
    write(martin, MARTIN)
    church_banks.main(["annotate", "--crawl", str(team), "--out-dir", str(tmp_path / "base")])
    base = read(tmp_path / "base" / "church_banks.csv")

    out = tmp_path / "extended.csv"
    assert es.main(["--team-crawl", str(team), "--martin", str(martin), "--out", str(out)]) == 0
    ext = read(out)
    team_rows = [{k: r[k] for k in church_banks.CHURCH_FIELDS} for r in ext if r["origin"] == "team_crawl"]
    assert team_rows == base
    assert [(r["origin"], r["charity_number"], r["verified"]) for r in ext if r["origin"] != "team_crawl"] == \
        [("martin", "2", "")]
