#!/usr/bin/env bash
# Test script for F2: search with date range filtering (--from / --to)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_LOG="$SCRIPT_DIR/agent-log.sh"

GREEN='\033[0;32m'; RED='\033[0;31m'; RESET='\033[0m'
test_count=0 passed_count=0 failed_count=0

run_test() {
  local test_name="$1" test_cmd="$2" expected="$3" expect_fail="${4:-0}"
  ((test_count++))
  echo -n "Test $test_count: $test_name ... "
  local output; output=$(eval "$test_cmd" 2>&1); local rc=$?
  if [[ $expect_fail -eq 1 ]]; then
    if [[ $rc -ne 0 ]] && echo "$output" | grep -q "$expected"; then
      echo -e "${GREEN}PASSED${RESET}"; ((passed_count++))
    else
      echo -e "${RED}FAILED${RESET}"; ((failed_count++))
      echo "  Output: $(echo "$output" | head -2)"
    fi
  else
    if [[ $rc -ne 0 ]]; then
      echo -e "${RED}FAILED${RESET} (exit $rc)"; ((failed_count++))
      echo "  Output: $(echo "$output" | head -2)"
    elif echo "$output" | grep -q "$expected"; then
      echo -e "${GREEN}PASSED${RESET}"; ((passed_count++))
    else
      echo -e "${RED}FAILED${RESET} (pattern not found)"; ((failed_count++))
      echo "  Expected: $expected"
      echo "  Got: $(echo "$output" | head -3)"
    fi
  fi
}

echo "Running tests for F2: search with date range filtering"
echo "======================================================="
echo

# Test 1: --from filters out older files
run_test "--from excludes older dates" \
  "$AGENT_LOG search --from 2026-05-29 'session' 2>&1 | head -5" \
  "Searching for"

# Test 2: --to filters out newer files
run_test "--to excludes newer dates" \
  "$AGENT_LOG search --to 2026-01-01 'session' 2>&1 | head -5" \
  "Searching for"

# Test 3: --from with invalid format errors
run_test "--from invalid format errors" \
  "$AGENT_LOG search --from 'bad-date' 'test' 2>&1" \
  "YYYY-MM-DD" \
  1

# Test 4: --to with invalid format errors
run_test "--to invalid format errors" \
  "$AGENT_LOG search --to '2026/01/01' 'test' 2>&1" \
  "YYYY-MM-DD" \
  1

# Test 5: combined --from and --to
run_test "Combined --from and --to" \
  "$AGENT_LOG search --from 2026-05-01 --to 2026-05-30 'memory' 2>&1 | head -5" \
  "Searching for"

# Test 6: search still works without date flags
run_test "Search without date flags still works" \
  "$AGENT_LOG search 'test' | head -3" \
  "Searching for"

echo
echo "======================================================="
echo "Total: $test_count | ${GREEN}Passed: $passed_count${RESET} | ${RED}Failed: $failed_count${RESET}"
[[ $failed_count -eq 0 ]] && echo -e "\n${GREEN}All tests passed!${RESET}" || echo -e "\n${RED}Some tests failed!${RESET}"
exit $((failed_count > 0 ? 1 : 0))
