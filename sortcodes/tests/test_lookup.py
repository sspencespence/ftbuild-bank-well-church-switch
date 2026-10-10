import pytest

from conftest import FIX_INSTITUTIONS, FIX_SORT_CODES
from sortcode_lookup import TableError, load_table, normalise


@pytest.mark.parametrize("raw", ["60-01-73", "600173", "60 01 73", "60.01.73",
                                 " 60–01–73 ", "60‑01‑73", "60 01 73"])
def test_normalise_accepts(raw):
    assert normalise(raw) == "600173"


@pytest.mark.parametrize("raw", ["60017", "6001734", "60-01-7a", "", "abcdef"])
def test_normalise_rejects(raw):
    with pytest.raises(ValueError):
        normalise(raw)


def test_exact_beats_range(t):
    r = t.lookup("40-52-40")
    assert (r["bank"], r["match"]) == ("CAF Bank", "exact")


def test_range(t):
    r = t.lookup("60-01-73")
    assert (r["bank"], r["group"], r["match"]) == ("NatWest", "NatWest Group", "range")


def test_rating_name(t):
    assert t.lookup("600173")["rating_name"] == "Natwest"


def test_narrowest_range_wins(t):
    # 30-50-00 is only in the wide Lloyds range
    assert t.lookup("305000")["bank"] == "Lloyds"


def test_ambiguous(t):
    r = t.lookup("309500")
    assert r["match"] == "ambiguous" and r["bank"] is None
    assert r["candidates"] == ["Lloyds", "TSB"]


def test_unknown(t):
    r = t.lookup("990000")
    assert r["match"] == "unknown" and r["bank"] is None and r["candidates"] == []


def test_leading_zero(t):
    r = t.lookup("04-00-04")
    assert (r["sort_code"], r["bank"]) == ("040004", "Monzo")


def _broken(tmp_path, old, new):
    text = FIX_SORT_CODES.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert old in lines[2]
    lines[2] = lines[2].replace(old, new, 1)
    p = tmp_path / "sort_codes.csv"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


@pytest.mark.parametrize("old,new,extra", [
    ("CAF Bank", "Nobody Bank", "Nobody Bank"),       # bank missing from institutions
    ("405240,405240", "405240,405239", ""),            # start > end
    ("405240,405240", "40524,405240", ""),             # not 6 digits
    (",exact,", ",prefix,", ""),                       # bad kind
    ("https://example.org/fixture", "", ""),           # missing source
])
def test_integrity_errors_name_row(tmp_path, old, new, extra):
    p = _broken(tmp_path, old, new)
    with pytest.raises(TableError, match="row 2") as e:
        load_table(p, FIX_INSTITUTIONS)
    assert extra in str(e.value)


def test_integrity_error_also_gives_file_line(tmp_path):
    p = _broken(tmp_path, "CAF Bank", "Nobody Bank")
    with pytest.raises(TableError, match=r"row 2 \(line 3\)"):
        load_table(p, FIX_INSTITUTIONS)


def test_duplicate_institution_rejected(tmp_path):
    inst = tmp_path / "institutions.csv"
    inst.write_text(FIX_INSTITUTIONS.read_text(encoding="utf-8") + "Monzo,Other group,bank,,\n",
                    encoding="utf-8")
    with pytest.raises(TableError, match="Monzo"):
        load_table(FIX_SORT_CODES, inst)
