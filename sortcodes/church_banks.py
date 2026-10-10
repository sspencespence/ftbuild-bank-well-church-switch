"""Join a crawl of church giving-page sort codes to the sort-code table.

  python church_banks.py annotate --crawl bankwell_churches_matched.csv
      writes results/church_banks.csv (one row per church with a sort code)
      and results/sort_code_map.csv (one row per sort code seen, with church counts)
  python church_banks.py accuracy --crawl ...   agreement with the bank printed beside the code
  python church_banks.py evidence --crawl ...   candidate table rows where a church page settles
                                                or corrects our answer (for a person to review)

The crawl CSV (team crawl, 9-10 Oct 2026) needs: charity_number, charity_name, income,
denomination, sort_code, bank_named_on_page, sort_code_page_url, sort_code_page_shared_with.
"""
import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from sortcode_lookup import load_table, normalise

HERE = Path(__file__).parent
RATINGS_MD = HERE.parent / "bank-ratings.md"
DEFAULT_OUT = HERE / "results"
MIN_EVIDENCE = 20  # page-named Lloyds/TSB codes needed before inferring a likely bank for a prefix

# names printed on pages -> our brand names; "Lloyds TSB" pages are pre-2013 wording and settle nothing
PAGE_ALIASES = {
    "barclays": "Barclays", "lloyds": "Lloyds", "lloyds bank": "Lloyds", "caf bank": "CAF Bank",
    "hsbc": "HSBC", "natwest": "NatWest", "nat west": "NatWest", "national westminster": "NatWest",
    "co-operative bank": "Co-operative Bank", "cooperative bank": "Co-operative Bank",
    "co-op bank": "Co-operative Bank", "metro bank": "Metro Bank", "virgin money": "Virgin Money",
    "santander": "Santander", "royal bank of scotland": "Royal Bank of Scotland",
    "rbs": "Royal Bank of Scotland", "tsb": "TSB", "charity bank": "Charity Bank",
    "unity trust": "Unity Trust", "bank of scotland": "Bank of Scotland", "triodos": "Triodos",
    "halifax": "Halifax", "nationwide": "Nationwide", "reliance bank": "Reliance Bank",
    "starling": "Starling", "clydesdale": "Virgin Money", "yorkshire bank": "Virgin Money",
    "monzo": "Monzo",
}

# a page contradicting one of our ranges is used only after a live check (2026-10-10);
# unchecked contradictions included "our charity bank account" read as Charity Bank
HAND_CHECKED = {"120103", "120881", "086115"}
LIVE_CHECKED = {"309911", "779138"}  # TSB pages confirmed live

CHURCH_FIELDS = ["charity_number", "charity_name", "income", "denomination", "sort_code",
                 "bank", "group", "rating", "match", "candidates", "likely_bank", "likely_note",
                 "bank_named_on_page", "page_agrees", "shared_page", "page_url", "source"]
MAP_FIELDS = ["sort_code", "bank", "group", "rating", "match", "candidates", "likely_bank",
              "churches", "source"]


def read_crawl(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def split_codes(raw):
    out = []
    for part in re.split(r"[;,|]+", raw or ""):
        try:
            out.append(normalise(part))
        except ValueError:
            pass
    return out


def dashed(code):
    return f"{code[:2]}-{code[2:4]}-{code[4:]}"


def page_bank(raw):
    """One mapped brand if the page names exactly one bank, else None."""
    names = {n.strip().lower() for n in (raw or "").split(";") if n.strip()}
    mapped = {PAGE_ALIASES.get(n) for n in names}
    if len(mapped) != 1 or None in mapped:
        return None
    return mapped.pop()


def ratings():
    """bank-ratings.md alternates 'Bank | ...' and 'Rating | ...' rows."""
    out, banks = {}, None
    for line in RATINGS_MD.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells[0] == "Bank":
            banks = cells[1:]
        elif cells[0] == "Rating" and banks:
            out.update({b: r for b, r in zip(banks, cells[1:]) if b and r})
    return out


def single_evidence(rows):
    """(row, code, named) for unshared pages showing one code and naming one bank."""
    for r in rows:
        codes = split_codes(r["sort_code"])
        named = page_bank(r["bank_named_on_page"])
        if len(codes) == 1 and named and (r["sort_code_page_shared_with"] or "0") == "0":
            yield r, codes[0], named


def lloyds_share(rows):
    """Per 2-digit prefix: (share of page-named Lloyds/TSB codes that are Lloyds, count)."""
    counts = defaultdict(Counter)
    for _, code, named in single_evidence(rows):
        if named in ("Lloyds", "TSB"):
            counts[code[:2]][named] += 1
    return {p: (c["Lloyds"] / (c["Lloyds"] + c["TSB"]), c["Lloyds"] + c["TSB"]) for p, c in counts.items()}


def likely(result, shares):
    """(bank, note) inferred for an ambiguous Lloyds/TSB code, or ('', '')."""
    if result["match"] != "ambiguous" or set(result["candidates"]) != {"Lloyds", "TSB"}:
        return "", ""
    p, n = shares.get(result["sort_code"][:2], (None, 0))
    if p is None or n < MIN_EVIDENCE:
        return "", ""
    bank = "Lloyds" if p >= 0.5 else "TSB"
    return bank, (f"inferred: {max(p, 1 - p):.0%} of {n} page-named "
                  f"{result['sort_code'][:2]}-xx Lloyds/TSB codes are {bank}")


def annotate(table, rows, out_dir):
    rating = ratings()
    shares = lloyds_share(rows)
    churches, per_code = [], {}
    for r in rows:
        codes = split_codes(r["sort_code"])
        if not codes:
            continue
        results = [table.lookup(c) for c in codes]
        guesses = [likely(x, shares) for x in results]
        join = lambda vals: ";".join(str(v or "") for v in vals)  # noqa: E731
        named = page_bank(r["bank_named_on_page"])
        agrees = ""
        if named and len(codes) == 1:
            first = results[0]
            agrees = "yes" if named == first["bank"] else "candidate" if named in first["candidates"] else "no"
        churches.append({
            "charity_number": r["charity_number"], "charity_name": r["charity_name"],
            "income": re.sub(r"\.0$", "", r["income"] or ""), "denomination": r["denomination"], "sort_code": r["sort_code"],
            "bank": join(x["bank"] for x in results), "group": join(x["group"] for x in results),
            "rating": join(rating.get(x["rating_name"] or "", "") for x in results),
            "match": join(x["match"] for x in results),
            "candidates": join("/".join(x["candidates"]) for x in results),
            "likely_bank": join(g[0] for g in guesses), "likely_note": join(g[1] for g in guesses),
            "bank_named_on_page": r["bank_named_on_page"], "page_agrees": agrees,
            "shared_page": r["sort_code_page_shared_with"], "page_url": r["sort_code_page_url"],
            "source": join(x["source"] for x in results),
        })
        for x, g in zip(results, guesses):
            entry = per_code.setdefault(x["sort_code"], {
                "sort_code": dashed(x["sort_code"]), "bank": x["bank"] or "", "group": x["group"] or "",
                "rating": rating.get(x["rating_name"] or "", ""), "match": x["match"],
                "candidates": "/".join(x["candidates"]), "likely_bank": g[0], "churches": 0,
                "source": x["source"] or ""})
            entry["churches"] += 1

    out_dir.mkdir(parents=True, exist_ok=True)
    codes = sorted(per_code.values(), key=lambda e: (-e["churches"], e["sort_code"]))
    for name, fields, data in (("church_banks.csv", CHURCH_FIELDS, churches),
                               ("sort_code_map.csv", MAP_FIELDS, codes)):
        with open(out_dir / name, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(data)
    print(f"{len(churches)} churches, {len(codes)} distinct sort codes -> {out_dir}")
    print("codes by match:", dict(Counter(m for c in churches for m in c["match"].split(";"))))


def accuracy(table, rows, out_dir):
    verdicts, disagreements = Counter(), []
    for r, code, named in single_evidence(rows):
        res = table.lookup(code)
        if res["match"] == "ambiguous":
            v = "ambiguous, page names a candidate" if named in res["candidates"] else "ambiguous, page names other"
        elif res["bank"] is None:
            v = "ours unknown"
        elif res["bank"] == named:
            v = "agree"
        else:
            v = "disagree"
            disagreements.append((dashed(code), res["bank"], named, r["sort_code_page_url"]))
        verdicts[v] += 1
    decided = verdicts["agree"] + verdicts["disagree"]
    print(f"evidence pairs (one code, one bank named, page not shared): {sum(verdicts.values())}")
    for k, v in verdicts.most_common():
        print(f"  {k}: {v}")
    if decided:
        print(f"agreement where both give one bank: {verdicts['agree']}/{decided} = "
              f"{verdicts['agree'] / decided:.1%}")
    for d in disagreements:
        print("  disagree:", *d)


def evidence(table, rows, out_dir):
    """Codes where every unshared page naming a bank agrees, and that bank changes our answer."""
    by_code = defaultdict(list)
    for r, code, named in single_evidence(rows):
        by_code[code].append((named, r["sort_code_page_url"]))
    out = []
    for code, ev in sorted(by_code.items()):
        banks = {b for b, _ in ev}
        res = table.lookup(code)
        if len(banks) != 1:
            print(f"conflict, skipped: {dashed(code)} {sorted(banks)}")
            continue
        bank = banks.pop()
        if res["match"] == "ambiguous" and bank in res["candidates"]:
            why = "resolves ambiguity"
        elif res["bank"] not in (None, bank) and res["match"] == "range" and code in HAND_CHECKED:
            why = f"page contradicts range ({res['bank']})"
        else:
            continue
        checked = "checked live 2026-10-10" if code in HAND_CHECKED | LIVE_CHECKED else "not re-checked live"
        out.append({"start": code, "end": code, "kind": "exact", "bank": bank, "source": ev[0][1],
                    "verified": "2026-10-10",
                    "notes": f"church giving page names bank beside code ({len(ev)} page(s)); "
                             f"from teammate crawl 9-10 Oct, {checked}; {why}"})
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "evidence_candidates.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["start", "end", "kind", "bank", "source", "verified", "notes"])
        w.writeheader()
        w.writerows(out)
    print(f"{len(out)} candidate rows -> {path} (review before adding to sort_codes.csv)")


def main(argv=None):
    p = argparse.ArgumentParser(description="Join church giving-page sort codes to the sort-code table.")
    p.add_argument("command", choices=["annotate", "accuracy", "evidence"])
    p.add_argument("--crawl", required=True, help="crawl CSV, e.g. bankwell_churches_matched.csv")
    p.add_argument("--out-dir", default=str(DEFAULT_OUT))
    args = p.parse_args(argv)
    commands = {"annotate": annotate, "accuracy": accuracy, "evidence": evidence}
    commands[args.command](load_table(), read_crawl(args.crawl), Path(args.out_dir))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
