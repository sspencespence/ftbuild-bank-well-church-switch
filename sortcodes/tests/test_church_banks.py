import csv

import church_banks

CRAWL_HEADER = ["charity_number", "charity_name", "income", "denomination", "sort_code",
                "bank_named_on_page", "sort_code_page_url", "sort_code_page_shared_with"]
CRAWL_ROWS = [
    ["1", "St A", "1000.0", "CofE", "40-52-40", "CAF Bank", "https://a.example/give", "0"],
    ["2", "St B", "2000", "Baptist", "30-94-12", "", "https://b.example/give", "0"],
    ["3", "St C", "3000", "Methodist", "60-01-73; 20-27-41", "", "https://c.example/give", "2"],
    ["4", "St D", "4000", "CofE", "", "", "", ""],
    ["5", "St E", "5000", "CofE", "40-52-40", "", "https://e.example/give", "0"],
]


def write_crawl(path):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(CRAWL_HEADER)
        w.writerows(CRAWL_ROWS)


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_ratings_parsed_from_bank_ratings_md():
    r = church_banks.ratings()
    assert (r["Barclays"], r["Lloyds"], r["Caf Bank"], r["Tsb"]) == ("1", "3", "5", "1")


def test_annotate_writes_church_and_code_files(tmp_path):
    crawl = tmp_path / "crawl.csv"
    write_crawl(crawl)
    assert church_banks.main(["annotate", "--crawl", str(crawl), "--out-dir", str(tmp_path)]) == 0

    churches = {r["charity_number"]: r for r in read(tmp_path / "church_banks.csv")}
    assert set(churches) == {"1", "2", "3", "5"}                      # no-code church left out
    assert (churches["1"]["bank"], churches["1"]["rating"], churches["1"]["page_agrees"]) == ("CAF Bank", "5", "yes")
    assert churches["1"]["income"] == "1000"
    assert churches["2"]["match"] == "ambiguous" and churches["2"]["candidates"] == "Lloyds/TSB"
    assert churches["3"]["bank"] == "Reliance Bank;Barclays"
    assert churches["3"]["shared_page"] == "2"

    codes = {r["sort_code"]: r for r in read(tmp_path / "sort_code_map.csv")}
    assert codes["40-52-40"]["bank"] == "CAF Bank" and codes["40-52-40"]["churches"] == "2"
    assert codes["20-27-41"]["bank"] == "Barclays"
    assert next(iter(codes)) == "40-52-40"                           # most-used code first
