"""Checks on the shipped tables (not fixtures)."""
import re

import pytest

from sortcode_lookup import DEFAULT_SORT_CODES, _read, load_table, lookup

RATING_NAMES = {
    "Barclays", "Hsbc", "Natwest", "Santander", "Standard Chartered", "Tsb",
    "Bank Of Scotland", "Halifax", "Lloyds", "Tide", "Caf Bank", "Co-Operative Bank",
    "Charity Bank", "Clydesdale", "Handelsbanken", "Nationwide", "Metro Bank",
    "Unity Trust", "Triodos", "Virgin Money", "Yorkshire Bank",
}
BANNED_SOURCES = ["sortcodes.co.uk", "unifiedsoftware", "mintly", "esortcode",
                  "api-ninjas", "bankcheck.dev"]

ROWS = _read(DEFAULT_SORT_CODES)


def test_shipped_tables_load():
    load_table()


def test_every_row_cited():
    for n, r in enumerate(ROWS, start=1):
        assert r["source"].startswith("http"), f"row {n}"
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["verified"]), f"row {n}"


def test_no_api_sources():
    for n, r in enumerate(ROWS, start=1):
        assert not any(b in r["source"] for b in BANNED_SOURCES), f"row {n}: {r['source']}"


def test_euston():
    # Euston Church's giving page code: an agency code inside NatWest's range
    r = lookup("60-01-73")
    assert (r["bank"], r["match"]) == ("Reliance Bank", "exact")


def test_sainsburys_bank_now_natwest_group():
    assert lookup("12-00-00")["group"] == "NatWest Group"


@pytest.mark.parametrize("code,bank", [("60-83-16", "Charity Bank"),
                                       ("60-83-01", "Unity Trust"), ("16-58-10", "Triodos"),
                                       ("23-05-80", "Metro Bank"), ("04-06-05", "Tide")])
def test_agency_codes_beat_host_range(code, bank):
    assert lookup(code)["bank"] == bank


def test_plain_natwest():
    r = lookup("60-70-80")
    assert (r["bank"], r["group"], r["match"]) == ("NatWest", "NatWest Group", "range")


def test_caf_not_hsbc():
    caf = [r for r in ROWS if r["bank"] == "CAF Bank" and r["kind"] == "exact"]
    assert caf, "no cited CAF Bank exact row"
    for r in caf:
        assert lookup(r["start"])["bank"] == "CAF Bank"


def test_rating_names_valid():
    inst = _read(load_table.__defaults__[1])
    for r in inst:
        assert not r["rating_name"] or r["rating_name"] in RATING_NAMES, r["bank"]


def test_tsb_lloyds_overlap():
    overlap = [r for r in ROWS if r["bank"] == "TSB" and r["kind"] == "range"
               and any(o["bank"] == "Lloyds" and o["kind"] == "range"
                       and (o["start"], o["end"]) == (r["start"], r["end"]) for o in ROWS)]
    if not overlap:
        pytest.skip("no public source for TSB/Lloyds overlap")
    r = lookup(overlap[0]["start"])
    assert r["match"] == "ambiguous" and set(r["candidates"]) >= {"Lloyds", "TSB"}
