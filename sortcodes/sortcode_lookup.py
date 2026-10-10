"""Map a UK sort code to the bank brand and parent group that issued it.

Data lives in two CSVs next to this file:
  sort_codes.csv    ranges and exact codes -> bank brand (every row cites a public source)
  institutions.csv  bank brand -> group, type, rating name

Precedence: exact code, then the narrowest matching range. Equally narrow
ranges naming different banks give "ambiguous"; no match gives "unknown".
"""
import csv
import re
from pathlib import Path

HERE = Path(__file__).parent
DEFAULT_SORT_CODES = HERE / "sort_codes.csv"
DEFAULT_INSTITUTIONS = HERE / "institutions.csv"

SIX_DIGITS = re.compile(r"\d{6}")
KINDS = {"exact", "range"}


class TableError(ValueError):
    """A CSV row breaks the table's rules."""


def normalise(code):
    """'60-01-73', '60 01 73', '60–01–73' -> '600173'. Raises ValueError otherwise."""
    cleaned = re.sub(r"[\W_]", "", str(code))
    if not SIX_DIGITS.fullmatch(cleaned) or not cleaned.isascii():
        raise ValueError(f"not a 6-digit sort code: {code!r}")
    return cleaned


def _read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class Table:
    def __init__(self, rows, institutions):
        self.rows = rows
        self.institutions = institutions

    def _result(self, code, match, bank=None, source=None, candidates=()):
        inst = self.institutions.get(bank, {})
        return {
            "sort_code": code,
            "bank": bank,
            "group": inst.get("group") if bank else None,
            "rating_name": (inst.get("rating_name") or None) if bank else None,
            "match": match,
            "candidates": list(candidates),
            "source": source,
        }

    def lookup(self, code):
        code = normalise(code)
        exact = [r for r in self.rows if r["kind"] == "exact" and r["start"] == code]
        if exact:
            banks = sorted({r["bank"] for r in exact})
            if len(banks) == 1:
                return self._result(code, "exact", banks[0], exact[0]["source"])
            return self._result(code, "ambiguous", candidates=banks)

        ranges = [r for r in self.rows if r["kind"] == "range" and r["start"] <= code <= r["end"]]
        if not ranges:
            return self._result(code, "unknown")
        width = min(int(r["end"]) - int(r["start"]) for r in ranges)
        narrow = [r for r in ranges if int(r["end"]) - int(r["start"]) == width]
        banks = sorted({r["bank"] for r in narrow})
        if len(banks) == 1:
            return self._result(code, "range", banks[0], narrow[0]["source"])
        return self._result(code, "ambiguous", candidates=banks)


def load_table(sort_codes_csv=DEFAULT_SORT_CODES, institutions_csv=DEFAULT_INSTITUTIONS):
    """Load and validate both CSVs. Row numbers in errors count data rows from 1."""
    institutions = {r["bank"]: r for r in _read(institutions_csv)}
    rows = _read(sort_codes_csv)
    for n, r in enumerate(rows, start=1):
        where = f"{Path(sort_codes_csv).name} row {n}"
        for col in ("start", "end"):
            if not SIX_DIGITS.fullmatch(r.get(col) or ""):
                raise TableError(f"{where}: {col} {r.get(col)!r} is not 6 digits")
        if r["start"] > r["end"]:
            raise TableError(f"{where}: start {r['start']} is after end {r['end']}")
        if r.get("kind") not in KINDS:
            raise TableError(f"{where}: kind {r.get('kind')!r} must be exact or range")
        if r["kind"] == "exact" and r["start"] != r["end"]:
            raise TableError(f"{where}: exact row must have start == end")
        if r.get("bank") not in institutions:
            raise TableError(f"{where}: bank {r.get('bank')!r} is not in {Path(institutions_csv).name}")
        if not (r.get("source") or "").strip():
            raise TableError(f"{where}: missing source")
    return Table(rows, institutions)


_default = None


def lookup(code):
    """Look up a code in the shipped tables."""
    global _default
    if _default is None:
        _default = load_table()
    return _default.lookup(code)
