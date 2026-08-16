#!/usr/bin/env bash
# Test script for F1: search with regex support

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
      echo "$output" | head -3 | sed 's/^/    /'
    fi
  fi
}

echo "Running tests for F1: search with regex support"
echo "================================================"
echo

# Hermetic fixture workspace (no dependency on real workspace content)
FIXTURE_DIR=$(mktemp -d)
export OPENCLAW_WORKSPACE="$FIXTURE_DIR"
mkdir -p "$FIXTURE_DIR/memory"
printf '# Regex fixture\nfixed f49 bug, F42 approved\nran test123 with docker container\n' > "$FIXTURE_DIR/memory/$(date +%Y-%m-%d).md"
trap 'rm -rf "$FIXTURE_DIR"' EXIT

# Test 1: Basic text search (should still work)
run_test "Basic text search" \
  "$AGENT_LOG search 'test' | head -5" \
  "Searching for (text):"

# Test 2: Regex search with -r flag
run_test "Regex search with -r flag" \
  "$AGENT_LOG search -r 'F[0-9]{2}' | head -5" \
  "Searching for (regex):"

# Test 3: Regex search with --regex flag
run_test "Regex search with --regex flag" \
  "$AGENT_LOG search --regex 'test[0-9]+' | head -5" \
  "Searching for (regex):"

# Test 4: Regex pattern matches numbers
run_test "Regex pattern matches F followed by digits" \
  "$AGENT_LOG search -r 'F[0-9]{2}' | head -10" \
  "f49"

# Test 5: Regex with alternation
run_test "Regex with alternation (docker|k8s)" \
  "$AGENT_LOG search -r 'docker|k8s' | head -5" \
  "Searching for (regex):"

# Test 6: Error when no query provided
run_test "Error when no query provided" \
  "$AGENT_LOG search -r 2>&1" \
  "Usage: agent-log search" \
  1

echo
echo "================================================"
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
