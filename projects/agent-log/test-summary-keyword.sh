#!/usr/bin/env bash
# Test script for F4: summary with keyword filtering

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_LOG="$SCRIPT_DIR/agent-log.sh"

# Colors
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; RESET='\033[0m'

test_count=0
passed_count=0
failed_count=0

run_test() {
  local test_name="$1"
  local test_cmd="$2"
  local expected_pattern="$3"
  local expect_failure="${4:-0}"

  ((test_count++))

  echo -n "Test $test_count: $test_name ... "

  local output
  local exit_code
  output=$(eval "$test_cmd" 2>&1)
  exit_code=$?

  # Check if command failure was expected
  if [[ $expect_failure -eq 1 ]]; then
    if [[ $exit_code -ne 0 ]]; then
      # Command failed as expected, now check pattern
      if echo "$output" | grep -q "$expected_pattern"; then
        echo -e "${GREEN}PASSED${RESET}"
        ((passed_count++))
      else
        echo -e "${RED}FAILED${RESET} (expected pattern not found in error output)"
        ((failed_count++))
        echo "  Expected to find: $expected_pattern"
        echo "  Output preview:"
        echo "$output" | head -3 | sed 's/^/    /'
      fi
    else
      echo -e "${RED}FAILED${RESET} (command should have failed but succeeded)"
      ((failed_count++))
    fi
  else
    # Command should succeed
    if [[ $exit_code -ne 0 ]]; then
      echo -e "${RED}FAILED${RESET} (command failed unexpectedly)"
      ((failed_count++))
      echo "  Output preview:"
      echo "$output" | head -3 | sed 's/^/    /'
      return
    fi

    if echo "$output" | grep -q "$expected_pattern"; then
      echo -e "${GREEN}PASSED${RESET}"
      ((passed_count++))
    else
      echo -e "${RED}FAILED${RESET} (expected pattern not found)"
      ((failed_count++))
      echo "  Expected to find: $expected_pattern"
      echo "  Output preview:"
      echo "$output" | head -5 | sed 's/^/    /'
    fi
  fi
}

echo "Running tests for F4: summary with keyword filtering"
echo "===================================================="
echo

# Hermetic fixture workspace (no dependency on real workspace content)
FIXTURE_DIR=$(mktemp -d)
export OPENCLAW_WORKSPACE="$FIXTURE_DIR"
mkdir -p "$FIXTURE_DIR/memory"
TODAY=$(date +%Y-%m-%d)
printf '# Keyword fixture\nworked on test suite improvements and test helpers\n' > "$FIXTURE_DIR/memory/$TODAY.md"
trap 'rm -rf "$FIXTURE_DIR"' EXIT

# Test 1: Basic summary without keyword (backward compatibility)
run_test "Basic summary without keyword" \
  "$AGENT_LOG summary 3" \
  "Activity summary (last 3 days)"

# Test 2: Summary with keyword filter
run_test "Summary with keyword filter" \
  "$AGENT_LOG summary 7 'test'" \
  "filter: test"

# Test 3: Keyword filter shows filtered results
run_test "Keyword filter shows matching files" \
  "$AGENT_LOG summary 7 'test'" \
  "$TODAY"

# Test 4: Non-matching keyword shows zero files
run_test "Non-matching keyword shows zero files" \
  "$AGENT_LOG summary 3 'xyznonexistent123'" \
  "Total:.*0 files"

# Test 5: Case-insensitive keyword matching
run_test "Case-insensitive keyword matching" \
  "$AGENT_LOG summary 7 'TEST'" \
  "filter: TEST"

# Test 6: Summary with 1 day and keyword
run_test "Summary with 1 day and keyword" \
  "$AGENT_LOG summary 1 'test'" \
  "Activity summary (last 1 days)"

echo
echo "===================================================="
echo "Test Summary:"
echo -e "  Total:   $test_count"
echo -e "  ${GREEN}Passed:  $passed_count${RESET}"
echo -e "  ${RED}Failed:  $failed_count${RESET}"

if [[ $failed_count -eq 0 ]]; then
  echo -e "\n${GREEN}All tests passed!${RESET}"
  exit 0
else
  echo -e "\n${RED}Some tests failed!${RESET}"
  exit 1
fi
