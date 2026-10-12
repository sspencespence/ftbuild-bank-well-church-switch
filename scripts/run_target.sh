#!/usr/bin/env bash
# Full run, in priority order: biggest churches first, text before scans. Resumable.
cd "$(dirname "$0")/.." || exit 1
for g in "target-100k-500k-text" "target-100k-500k-scan" "target-25k-100k-text" "target-25k-100k-scan"; do
  echo "$(date +%T) === $g"
  bash scripts/run_workers.sh "shards/$g-*.txt" 6 sonnet "$PWD/scripts/worker-prompt.md" out medium
done
echo "$(date +%T) === all done"
