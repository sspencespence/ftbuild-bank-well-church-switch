"""Map a UK sort code to the bank brand and parent group that issued it.

Data lives in two CSVs next to this file:
  sort_codes.csv    ranges and exact codes -> bank brand (every row cites a public source)
  institutions.csv  bank brand -> group, type, rating name

Precedence: exact code, then the narrowest matching range. Equally narrow
ranges naming different banks give "ambiguous"; no match gives "unknown".
"""
import argparse
import csv
import re
import sys
from datetime import date
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
    # utf-8-sig: Excel's "CSV UTF-8" adds a BOM that would otherwise corrupt the first header
    with open(path, encoding="utf-8-sig", newline="") as f:
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
    """Load and validate both CSVs. Errors give the data row (from 1) and the file line."""
    institutions = {}
    for n, r in enumerate(_read(institutions_csv), start=1):
        if r["bank"] in institutions:
            raise TableError(f"{Path(institutions_csv).name} row {n} (line {n + 1}): "
                             f"duplicate bank {r['bank']!r}")
        institutions[r["bank"]] = r
    rows = _read(sort_codes_csv)
    for n, r in enumerate(rows, start=1):
        where = f"{Path(sort_codes_csv).name} row {n} (line {n + 1})"
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


DEFAULT_QUEUE = HERE / "to_verify.csv"
QUEUE_FIELDS = ["sort_code", "match", "candidates", "context", "added"]
OUT_FIELDS = ["sc_normalised", "sc_bank", "sc_group", "sc_rating_name",
              "sc_match", "sc_candidates", "sc_source"]


def queue_unresolved(results, queue_path=DEFAULT_QUEUE, context=None):
    """Append unknown/ambiguous results to the verify queue, once per code. Returns rows added.
    A result may carry its own "context" key, which overrides the context argument."""
    queue_path = Path(queue_path)
    # zfill: Excel strips leading zeros if someone saves the queue from it
    queued = ({(r.get("sort_code") or "").zfill(6) for r in _read(queue_path)}
              if queue_path.exists() else set())
    new = []
    for r in results:
        if r["match"] in ("unknown", "ambiguous") and r["sort_code"] not in queued:
            queued.add(r["sort_code"])
            new.append({"sort_code": r["sort_code"], "match": r["match"],
                        "candidates": ";".join(r["candidates"]),
                        "context": r.get("context", context) or "",
                        "added": date.today().isoformat()})
    if new:
        write_header = not queue_path.exists() or queue_path.stat().st_size == 0
        needs_newline = not write_header and not queue_path.read_bytes().endswith(b"\n")
        with open(queue_path, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=QUEUE_FIELDS)
            if write_header:
                w.writeheader()
            if needs_newline:
                f.write("\r\n")
            w.writerows(new)
    return len(new)


def _run_csv(table, args, parser):
    with open(args.csv, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        header = reader.fieldnames
    if not header:
        parser.error(f"{args.csv} is empty")
    # re-running on our own output: overwrite the sc_* columns rather than adding a second set
    fields = header + [c for c in OUT_FIELDS if c not in header]
    if args.column not in header:
        parser.error(f"column {args.column!r} not in {args.csv}; columns are {header}")
    unresolved = []
    for row in rows:
        row.pop(None, None)  # extra fields from a stray comma
        try:
            r = table.lookup(row.get(args.column) or "")
        except ValueError:
            row.update({k: "" for k in OUT_FIELDS}, sc_match="invalid")
            continue
        row.update(sc_normalised=r["sort_code"], sc_bank=r["bank"] or "", sc_group=r["group"] or "",
                   sc_rating_name=r["rating_name"] or "", sc_match=r["match"],
                   sc_candidates=";".join(r["candidates"]), sc_source=r["source"] or "")
        ctx = row.get(args.context_column) if args.context_column else None
        unresolved.append({**r, "context": ctx})
    queue_unresolved(unresolved, args.queue)
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows written to {args.out}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Look up the bank behind a UK sort code.")
    p.add_argument("code", nargs="?", help="a sort code, e.g. 60-01-73")
    p.add_argument("--csv", help="input CSV to annotate")
    p.add_argument("--column", default="sort_code", help="sort code column in --csv")
    p.add_argument("--out", help="output CSV for --csv mode")
    p.add_argument("--context", help="label stored in the queue, e.g. a charity number")
    p.add_argument("--context-column", help="column used as the queue label in --csv mode")
    p.add_argument("--queue", default=str(DEFAULT_QUEUE))
    p.add_argument("--sort-codes", default=str(DEFAULT_SORT_CODES))
    p.add_argument("--institutions", default=str(DEFAULT_INSTITUTIONS))
    args = p.parse_args(argv)

    table = load_table(args.sort_codes, args.institutions)
    if args.csv:
        if not args.out:
            p.error("--csv needs --out")
        return _run_csv(table, args, p)
    if not args.code:
        p.error("give a sort code or --csv")
    try:
        r = table.lookup(args.code)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    print(f"{r['sort_code']}  {r['bank'] or '-'}  {r['group'] or '-'}  {r['match']}  "
          f"{';'.join(r['candidates'])}")
    queue_unresolved([r], args.queue, args.context)
    return 0


if __name__ == "__main__":
    sys.exit(main())
