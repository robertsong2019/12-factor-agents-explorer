#!/usr/bin/env bash
# F18: Performance benchmark for agent-log on large synthetic log sets.
# Creates a hermetic temp workspace with N daily memory files, times core
# commands, and asserts each stays under a generous threshold.
# Usage: ./test/bench.sh [num_days] [lines_per_file]
#   num_days       default 365
#   lines_per_file default 50

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_LOG="$SCRIPT_DIR/../agent-log.sh"

NUM_DAYS="${1:-365}"
LINES_PER_FILE="${2:-50}"
# Generous CI-safe thresholds (seconds). Local runs are usually 10-50x faster.
THRESHOLD_SEARCH=30
THRESHOLD_TODAY=15
THRESHOLD_SUMMARY=30
THRESHOLD_STATS=15

TMPDIR_BENCH=$(mktemp -d)
trap 'rm -rf "$TMPDIR_BENCH"' EXIT

WORKSPACE="$TMPDIR_BENCH/workspace"
mkdir -p "$WORKSPACE/memory"

# --- Generate synthetic log corpus -----------------------------------------
gen_start=$(date +%s)
for i in $(seq 0 $((NUM_DAYS - 1))); do
  d=$(date -d "-$i days" +%F)
  f="$WORKSPACE/memory/$d.md"
  {
    echo "# Daily log $d"
    for j in $(seq 1 "$LINES_PER_FILE"); do
      echo "- item $j: worked on feature-$((j % 7)) and fixed bug-$((j % 13))"
    done
  } > "$f"
done
gen_end=$(date +%s)
TOTAL_LINES=$((NUM_DAYS * LINES_PER_FILE + NUM_DAYS))
echo "Corpus: $NUM_DAYS daily files x $LINES_PER_FILE lines (~$TOTAL_LINES total lines, generated in $((gen_end - gen_start))s)"

# --- Timing helper ----------------------------------------------------------
PASS=0; FAIL=0
run_bench() { # name command threshold
  local name="$1" cmd="$2" threshold="$3"
  local t0 t1 elapsed
  t0=$(date +%s%N)
  OPENCLAW_WORKSPACE="$WORKSPACE" bash "$AGENT_LOG" $cmd > /dev/null 2>&1
  t1=$(date +%s%N)
  elapsed=$(( (t1 - t0) / 1000000 )) # ms
  local status="PASS"
  if (( elapsed > threshold * 1000 )); then status="FAIL"; FAIL=$((FAIL + 1)); else PASS=$((PASS + 1)); fi
  printf '%-12s %6d ms  (threshold %ds)  %s\n' "$name" "$elapsed" "$threshold" "$status"
}

echo ""
echo "=== agent-log benchmark ==="
run_bench search "search feature-3" "$THRESHOLD_SEARCH"
run_bench today    "today"          "$THRESHOLD_TODAY"
run_bench summary  "summary 30"     "$THRESHOLD_SUMMARY"
run_bench stats    "stats"          "$THRESHOLD_STATS"

echo ""
if (( FAIL > 0 )); then
  echo "RESULT: $FAIL/$((PASS + FAIL)) benchmarks FAILED"
  exit 1
fi
echo "RESULT: all $PASS benchmarks passed"
