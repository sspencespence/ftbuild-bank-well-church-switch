"""Private accuracy check: compare our lookup with the eSortcode API.

Prints results only. Never writes files: eSortcode's terms (4.3, 6.2) forbid
redistributing its EISCD data, so disagreements are research leads, and a
table fix needs a public source.

Usage:  python crosscheck.py 60-01-73 20-27-41:12345678 --limit 20
        python crosscheck.py --codes codes.txt
Each code may carry an account number after a colon; the API needs one, so a
placeholder is sent when it is missing (the API may then return no answer).
Needs ESORTCODE_API_KEY in .env (free account, 50 credits, no card).
"""
import argparse
import os
import re
import sys
import time
from urllib.parse import quote, quote_plus

import requests
from dotenv import find_dotenv, load_dotenv

from sortcode_lookup import lookup, normalise

API_URL = "https://wsp.esortcode.com/uk/v1/validateaccount"
PLACEHOLDER_ACCOUNT = "00000000"

# eSortcode returns legal, often truncated names; map our brands to them where substrings fail
ALIASES = {
    "NatWest": ["national westminster"],
    "Co-operative Bank": ["co-operative bank", "co-op bank"],
    "Royal Bank of Scotland": ["royal bank of scot"],
}


def _clean(s):
    return re.sub(r"[^a-z0-9& ]", "", (s or "").lower()).strip()


def _same(ours, theirs):
    a, b = _clean(ours), _clean(theirs)
    if not a or not b:
        return False
    return a in b or b in a or any(_clean(x) in b for x in ALIASES.get(ours, []))


def compare(ours, their_bank):
    if not their_bank:
        return "no_answer"
    if _same(ours.get("bank"), their_bank):
        return "brand"
    if _same(ours.get("group"), their_bank):
        return "group"
    if ours.get("match") in ("unknown", "ambiguous"):
        return "unresolved_ours"
    return "mismatch"


def fetch_bank(code, api_key, account=None):
    """One lookup. Returns the first branch's bankName, or None if not found.
    Raises RuntimeError on auth/credit/throttle errors. Never puts the URL (which holds the key) in a message."""
    try:
        resp = requests.get(API_URL, timeout=20, params={
            "key": api_key, "sortcode": code, "accountNumber": account or PLACEHOLDER_ACCOUNT})
    except requests.RequestException as e:
        raise RuntimeError(f"request failed ({type(e).__name__})") from None
    if resp.status_code == 400:
        return None
    try:
        body = resp.json()
    except ValueError:
        body = None
    if resp.status_code != 200:
        msg = str((body or {}).get("message") or "") if isinstance(body, dict) else ""
        for form in (api_key, quote(api_key, safe=""), quote_plus(api_key)):
            msg = msg.replace(form, "***")
        raise RuntimeError(f"HTTP {resp.status_code}: {msg}")
    if not isinstance(body, dict):
        raise RuntimeError("HTTP 200 but response was not JSON")
    branches = body.get("branches") or []
    return branches[0].get("bankName") if branches else None


def main(argv=None):
    p = argparse.ArgumentParser(description="Compare our sort code table with eSortcode (prints only).")
    p.add_argument("codes", nargs="*", help="sort codes, optionally code:account")
    p.add_argument("--codes", dest="codes_file", help="file with one code (or code:account) per line")
    p.add_argument("--limit", type=int, default=50, help="max API calls (free allowance is 50)")
    args = p.parse_args(argv)

    load_dotenv(find_dotenv())
    api_key = os.environ.get("ESORTCODE_API_KEY")
    if not api_key:
        print("ESORTCODE_API_KEY not set in .env; sign up free at esortcode.com", file=sys.stderr)
        return 1

    items = list(args.codes)
    if args.codes_file:
        with open(args.codes_file, encoding="utf-8") as f:
            items += [line.strip() for line in f if line.strip()]

    counts, calls = {}, 0
    print(f"{'code':8}  {'ours':28}  {'theirs':32}  verdict")
    for item in items:
        raw, _, account = item.partition(":")
        try:
            code = normalise(raw)
        except ValueError:
            print(f"{raw:8}  {'':28}  {'':32}  invalid")
            counts["invalid"] = counts.get("invalid", 0) + 1
            continue
        if calls >= args.limit:
            break
        ours = lookup(code)
        try:
            theirs = fetch_bank(code, api_key, account or None)
        except RuntimeError as e:
            print(f"stopping: {e}", file=sys.stderr)
            break
        calls += 1
        verdict = compare(ours, theirs)
        counts[verdict] = counts.get(verdict, 0) + 1
        label = ours["bank"] or ours["match"] + (f" ({';'.join(ours['candidates'])})" if ours["candidates"] else "")
        print(f"{code:8}  {label[:28]:28}  {(theirs or '-')[:32]:32}  {verdict}")
        time.sleep(1)

    answered = sum(v for k, v in counts.items() if k not in ("no_answer", "invalid"))
    agreed = counts.get("brand", 0) + counts.get("group", 0)
    print("\n" + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    rate = f"{agreed}/{answered} = {agreed / answered:.0%}" if answered else "n/a"
    print(f"API calls: {calls}. Agreement (brand or group, of answered): {rate}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
