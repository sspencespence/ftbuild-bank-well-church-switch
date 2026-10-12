#!/usr/bin/env bash
# Run headless Claude readers over shard files, P at a time. Resumable: a shard whose output exists is skipped.
# REVERSE=1 processes shards last-first (a second runner meeting the first in the middle).
# Usage: bash scripts/run_workers.sh <shard-glob> [P=4] [model=sonnet] [prompt=scripts/worker-prompt.md] [outdir=out] [effort=medium]
set -u
REPO=$(cd "$(dirname "$0")/.." && pwd)
cd "${BANKWELL_DATA:-$HOME/bankwell-data}/extract" || exit 1
GLOB=${1:?shard glob, e.g. "shards/pilot-*.txt"}; P=${2:-4}; MODEL=${3:-sonnet}; PROMPT=${4:-$REPO/scripts/worker-prompt.md}; OUT=${5:-out}; EFFORT=${6:-medium}
mkdir -p "$OUT" logs
export MODEL PROMPT OUT EFFORT
ls $GLOB | { if [ "${REVERSE:-0}" = 1 ]; then sort -r; else cat; fi; } | xargs -P "$P" -I{} bash -c '
  name=$(basename {} .txt); o="$PWD/$OUT/$name.jsonl"
  [ -s "$o" ] && exit 0
  printf "%s\n\nBATCH FILE: %s\nOUTPUT FILE: %s\n" "$(cat "$PROMPT")" "$PWD/{}" "$o" > "logs/$name.$OUT.prompt"
  echo "$(date +%T) start $name"
  timeout 1500 claude -p --model "$MODEL" --effort "$EFFORT" --allowedTools "Read,Edit(/$PWD/$OUT/**)" < "logs/$name.$OUT.prompt" > "logs/$name.$OUT.log" 2>&1
  echo "$(date +%T) end   $name rc=$? lines=$(wc -l < "$o" 2>/dev/null || echo 0)"
'
