#!/usr/bin/env bash
# Test script for F6: trend command

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_LOG="$SCRIPT_DIR/agent-log.sh"

GREEN='\033[0;32m'; RED='\033[0;31m'; RESET='\033[0m'
test_count=0; passed_count=0; failed_count=0

run_test() {
  local test_name="$1" test_cmd="$2" expected_pattern="$3"
  ((test_count++))
  echo -n "Test $test_count: $test_name ... "
  local output; output=$(eval "$test_cmd" 2>&1)
  if [[ $? -ne 0 ]]; then echo -e "${RED}FAILED${RESET} (exit code)"; ((failed_count++)); return; fi
  if echo "$output" | grep -q "$expected_pattern"; then
    echo -e "${GREEN}PASSED${RESET}"; ((passed_count++))
  else
    echo -e "${RED}FAILED${RESET} (pattern not found)"
    echo "  Expected: $expected_pattern"; echo "$output" | head -3 | sed 's/^/    /'
    ((failed_count++))
  fi
}

echo "Running tests for F6: trend command"
echo "===================================="
echo

# Test 1: Basic trend output
run_test "Basic trend with header" \
  "$AGENT_LOG trend 7" \
  "Activity trend"

# Test 2: Contains sparkline bars
run_test "Contains sparkline characters" \
  "$AGENT_LOG trend 7" \
  "[▁▂▃▄▅▆▇█]"

# Test 3: Day count header
run_test "Shows correct day count" \
  "$AGENT_LOG trend 5" \
  "last 5 days"

# Test 4: JSON output
run_test "JSON output mode" \
  "$AGENT_LOG trend 3 -j" \
  '"command":"trend"'

# Test 5: JSON contains data array
run_test "JSON has data entries" \
  "$AGENT_LOG trend 3 --json" \
  '"lines":'

# Test 6: Max label shown
run_test "Scale label present" \
  "$AGENT_LOG trend 7" \
  "Max:"

echo
echo "===================================="
echo -e "  Total:   $test_count"
echo -e "  ${GREEN}Passed:  $passed_count${RESET}"
echo -e "  ${RED}Failed:  $failed_count${RESET}"

[[ $failed_count -eq 0 ]] && echo -e "\n${GREEN}All tests passed!${RESET}" && exit 0
echo -e "\n${RED}Some tests failed!${RESET}" && exit 1
