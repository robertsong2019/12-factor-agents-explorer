#!/usr/bin/env bash
# Test script for F5: summary with activity types

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_LOG="$SCRIPT_DIR/agent-log.sh"

GREEN='\033[0;32m'; RED='\033[0;31m'; RESET='\033[0m'
test_count=0; passed_count=0; failed_count=0

run_test() {
  local test_name="$1" test_cmd="$2" expected_pattern="$3"
  ((test_count++))
  echo -n "Test $test_count: $test_name ... "
  local output; output=$(eval "$test_cmd" 2>&1)
  if [[ $? -ne 0 ]]; then echo -e "${RED}FAILED${RESET} (exit)"; ((failed_count++)); return; fi
  if echo "$output" | grep -q "$expected_pattern"; then
    echo -e "${GREEN}PASSED${RESET}"; ((passed_count++))
  else
    echo -e "${RED}FAILED${RESET}"
    echo "  Expected: $expected_pattern"; echo "$output" | head -3 | sed 's/^/    /'
    ((failed_count++))
  fi
}

echo "Running tests for F5: summary activity types"
echo "=============================================="
echo

# Test 1: --types flag shows activity labels
run_test "Types flag shows parenthesized type" \
  "$AGENT_LOG summary 7 --types" \
  "research"

# Test 2: Without --types, no type labels
run_test "Default summary has no type labels" \
  "$AGENT_LOG summary 7 2>&1 | grep -c 'lines (' || echo 0" \
  "^0$"

# Test 3: Summary still works normally without --types
run_test "Normal summary still works" \
  "$AGENT_LOG summary 3" \
  "Activity summary"

# Test 4: JSON output ignores --types gracefully
run_test "JSON with --types works" \
  "$AGENT_LOG summary 3 --types -j" \
  '"command":"summary"'

echo
echo "=============================================="
echo -e "  Total:   $test_count"
echo -e "  ${GREEN}Passed:  $passed_count${RESET}"
echo -e "  ${RED}Failed:  $failed_count${RESET}"

[[ $failed_count -eq 0 ]] && echo -e "\n${GREEN}All tests passed!${RESET}" && exit 0
echo -e "\n${RED}Some tests failed!${RESET}" && exit 1
