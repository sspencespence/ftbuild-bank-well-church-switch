#!/usr/bin/env python3
"""Pick documents for the blind Opus second read: a random 10% + every document with a flagged figure.

Flagged = a failed evidence check, low confidence, a "conflict" note, or a multi-line stitched quote (" / ").
Usage: python scripts/make_check_shards.py <group-prefix, e.g. target-100k-500k-text> [--rate 0.10] [--size 12]
Writes shards/check-<group>-NNN.txt and check_selection_<group>.json. Re-running keeps earlier picks.
"""
import argparse, glob, json, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bankwell_paths import DATA, EXTRACT, REGISTER  # noqa: E402

E = EXTRACT


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("group")
    p.add_argument("--rate", type=float, default=0.10)
    p.add_argument("--size", type=int, default=12)
    p.add_argument("--random-only", action="store_true", help="random sample only, no flagged docs")
    a = p.parse_args()
    paths, flagged, reasons = {}, set(), {}
    for shard in glob.glob(str(E / "shards" / f"{a.group}-*.txt")):
        for line in open(shard):
            regno, kind, path = line.rstrip("\n").split("\t")
            paths[regno] = (kind, path)
    for f in glob.glob(str(E / "out" / f"{a.group}-*.checked.jsonl")) + glob.glob(str(E / "out" / f"{a.group}-*.jsonl")):
        if f.endswith(".checked.jsonl") is False and Path(f.replace(".jsonl", ".checked.jsonl")).exists():
            continue
        for line in open(f):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            why = []
            if str(r.get("checks", "")).startswith("failed"): why.append(r["checks"])
            if r.get("confidence") == "low": why.append("low_confidence")
            if "conflict" in str(r.get("note", "")).lower(): why.append("conflict")
            if " / " in str(r.get("quote") or ""): why.append("stitched_quote")
            if why and str(r["regno"]) in paths:
                flagged.add(str(r["regno"])); reasons.setdefault(str(r["regno"]), []).extend(f"{r['field']}:{w}" for w in why)
    done = {p.stem for p in (E / "out").glob(f"{a.group}-*.jsonl") if not p.name.endswith(".checked.jsonl")}
    read = sorted(r for r in paths if any(r in open(E / "shards" / f"{d}.txt").read() for d in done))
    sample = set(random.Random(2026).sample(read, max(1, round(a.rate * len(read)))))
    if a.random_only:
        flagged, reasons = set(), {}
    chosen = sorted(flagged | sample)
    sel = E / f"check_selection_{a.group}.json"
    sel.write_text(json.dumps({"random_sample": sorted(sample), "flagged": reasons}, indent=1))
    for old in glob.glob(str(E / "shards" / f"check-{a.group}-*.txt")):
        Path(old).unlink()
    for i in range(0, len(chosen), a.size):
        (E / "shards" / f"check-{a.group}-{i // a.size + 1:03d}.txt").write_text(
            "".join(f"{r}\t{paths[r][0]}\t{paths[r][1]}\n" for r in chosen[i:i + a.size]))
    print(f"{a.group}: {len(read)} read, {len(sample)} random + {len(flagged)} flagged = {len(chosen)} to re-read")
    return 0


if __name__ == "__main__":
    sys.exit(main())
