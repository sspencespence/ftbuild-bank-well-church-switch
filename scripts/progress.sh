#!/usr/bin/env bash
# One-screen progress for the finance extraction.
E=${BANKWELL_DATA:-$HOME/bankwell-data}/extract
python3 - "$E" <<'PY'
import json, sys, glob, os, collections
E = sys.argv[1]
docs = [json.loads(l) for l in open(f"{E}/docs.jsonl")] if os.path.exists(f"{E}/docs.jsonl") else []
print(f"1. Preparing PDFs:   {len(docs):>5} / 8646  ({100*len(docs)/8646:.0f}%)")
for group in ("pilot", "kat", "target-100k-500k", "target-25k-100k"):
    shards = glob.glob(f"{E}/shards/{group}-*.txt")
    if not shards:
        continue
    n_docs = sum(1 for s in shards for _ in open(s))
    done = [s for s in shards if os.path.getsize(f"{E}/out/{os.path.basename(s)[:-4]}.jsonl") > 0] if False else \
           [s for s in shards if os.path.exists(f"{E}/out/{os.path.basename(s)[:-4]}.jsonl") and os.path.getsize(f"{E}/out/{os.path.basename(s)[:-4]}.jsonl") > 0]
    d_docs = sum(1 for s in done for _ in open(s))
    print(f"2. Reading {group:<17} {d_docs:>5} / {n_docs:<5} docs ({100*d_docs/max(n_docs,1):.0f}%)")
tot = done_all = 0
for s in glob.glob(f"{E}/shards/target-*.txt"):
    n = sum(1 for _ in open(s)); tot += n
    o = f"{E}/out/{os.path.basename(s)[:-4]}.jsonl"
    if os.path.exists(o) and os.path.getsize(o) > 0:
        done_all += n
if tot:
    print(f"== OVERALL target: {done_all} / {tot} docs ({100*done_all/tot:.1f}%)")
found = collections.Counter()
for f in [g for g in glob.glob(f"{E}/out/target-*.jsonl") if not g.endswith(".checked.jsonl")]:
    for l in open(f):
        try: r = json.loads(l)
        except ValueError: continue
        if r.get("value_gbp") is not None or r.get("text_value"):
            found[r["field"]] += 1
if found:
    print("3. Figures found so far:", dict(found))
PY
