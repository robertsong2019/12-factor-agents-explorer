#!/usr/bin/env bash
# Test script for F12: Markdown export (--md flag for summary/stats)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_LOG="$SCRIPT_DIR/agent-log.sh"
TEST_DIR=$(mktemp -d)

GREEN='\033[0;32m'; RED='\033[0;31m'; RESET='\033[0m'
test_count=0 passed_count=0 failed_count=0

# Setup test data
OPENCLAW_WORKSPACE="$TEST_DIR" MEMORY_DIR="$TEST_DIR/memory"
mkdir -p "$MEMORY_DIR"
echo -e "# Test log\nLine 1\nLine 2\nLine 3" > "$MEMORY_DIR/$(date +%Y-%m-%d).md"

run_test() {
  local name="$1" cmd="$2" expected="$3"
  ((test_count++))
  echo -n "Test $test_count: $name ... "
  local output; output=$(eval "$cmd" 2>&1); local ec=$?
  if [[ $ec -ne 0 ]]; then
    echo -e "${RED}FAILED${RESET} (exit $ec)"; ((failed_count++))
    echo "$output" | head -3 | sed 's/^/  /'
  elif echo "$output" | grep -qF "$expected"; then
    echo -e "${GREEN}PASSED${RESET}"; ((passed_count++))
  else
    echo -e "${RED}FAILED${RESET} (pattern not found)"; ((failed_count++))
    echo "  Expected: $expected"
    echo "$output" | tail -5 | sed 's/^/  /'
  fi
}

echo "=== F12: Markdown export tests ==="
echo

# Summary --md tests
run_test "summary --md produces markdown header" \
  "OPENCLAW_WORKSPACE=$TEST_DIR $AGENT_LOG summary --md" \
  "# Activity Summary"

run_test "summary --md has table header" \
  "OPENCLAW_WORKSPACE=$TEST_DIR $AGENT_LOG summary --md" \
  "| Date | Day | Lines |"

run_test "summary --md has table row" \
  "OPENCLAW_WORKSPACE=$TEST_DIR $AGENT_LOG summary --md" \
  "| $(date +%Y-%m-%d) |"

run_test "summary --md shows total" \
  "OPENCLAW_WORKSPACE=$TEST_DIR $AGENT_LOG summary --md" \
  "**Total:**"

# Stats --md tests
run_test "stats --md produces markdown header" \
  "OPENCLAW_WORKSPACE=$TEST_DIR $AGENT_LOG stats --md" \
  "# Workspace Stats"

run_test "stats --md has table" \
  "OPENCLAW_WORKSPACE=$TEST_DIR $AGENT_LOG stats --md" \
  "| Metric | Value |"

run_test "stats --md has memory files row" \
  "OPENCLAW_WORKSPACE=$TEST_DIR $AGENT_LOG stats --md" \
  "| Memory files |"

# Cleanup
rm -rf "$TEST_DIR"

echo
echo -e "${GREEN}Results: $passed_count/$test_count passed${RESET}"
[[ $failed_count -gt 0 ]] && echo -e "${RED}$failed_count failed${RESET}"
exit $((failed_count > 0 ? 1 : 0))
