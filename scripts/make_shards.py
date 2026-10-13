#!/usr/bin/env python3
"""Split documents into small reader batches (shards). Smaller batches = more careful reading.

  --set pilot   60 known-answer docs (smallest charities that have official Part B figures): 45 text + 15 scan
  --set kat     all remaining known-answer docs (background accuracy score)
  --set target  churches missing figures, £100k-500k first, then £25k-100k; text before scans

Shards are written as shards/<set>-NNN.txt, lines: regno<TAB>kind<TAB>path. Existing shard files are kept.
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bankwell_paths import DATA, EXTRACT, REGISTER  # noqa: E402




def path_for(d: dict) -> str:
    return str(EXTRACT / "packets" / f"{d['regno']}.txt") if d["kind"] == "text" else str(EXTRACT / "pages" / d["regno"])


def write(name: str, docs: list[dict], size: int, start: int) -> int:
    n = start
    for i in range(0, len(docs), size):
        n += 1
        f = EXTRACT / "shards" / f"{name}-{n:03d}.txt"
        f.write_text("".join(f"{d['regno']}\t{d['kind']}\t{path_for(d)}\n" for d in docs[i:i + size]))
    return n


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--set", choices=["pilot", "kat", "target"], required=True)
    p.add_argument("--text-size", type=int, default=12)
    p.add_argument("--scan-size", type=int, default=6)
    a = p.parse_args()
    (EXTRACT / "shards").mkdir(exist_ok=True)
    docs = [d for d in map(json.loads, (EXTRACT / "docs.jsonl").read_text().splitlines()) if d.get("kind") in ("text", "scan")]
    pilot_file = EXTRACT / "pilot_regnos.txt"
    if a.set == "pilot":
        kat = sorted((d for d in docs if d["kat"] and not d["target"]), key=lambda d: d["income"])
        chosen = [d for d in kat if d["kind"] == "text"][:45] + [d for d in kat if d["kind"] == "scan"][:15]
        pilot_file.write_text("\n".join(d["regno"] for d in chosen) + "\n")
        n = write("pilot", [d for d in chosen if d["kind"] == "text"], a.text_size, 0)
        write("pilot", [d for d in chosen if d["kind"] == "scan"], a.scan_size, n)
        print(f"pilot: {len(chosen)} docs, income £{chosen[0]['income']:,.0f}-£{max(d['income'] for d in chosen):,.0f}")
    elif a.set == "kat":
        skip = set(pilot_file.read_text().split()) if pilot_file.exists() else set()
        kat = sorted((d for d in docs if d["kat"] and not d["target"] and d["regno"] not in skip), key=lambda d: d["income"])
        n = write("kat", [d for d in kat if d["kind"] == "text"], a.text_size, 0)
        write("kat", [d for d in kat if d["kind"] == "scan"], a.scan_size, n)
        print(f"kat: {len(kat)} docs")
    else:
        n = 0
        for band in ("100k-500k", "25k-100k"):
            for kind, size in (("text", a.text_size), ("scan", a.scan_size)):
                group = sorted((d for d in docs if d["target"] and d["band"] == band and d["kind"] == kind),
                               key=lambda d: -d["income"])
                n = write(f"target-{band}-{kind}", group, size, 0)
                print(f"{band} {kind}: {len(group)} docs -> {n} shards")
    return 0


if __name__ == "__main__":
    sys.exit(main())
