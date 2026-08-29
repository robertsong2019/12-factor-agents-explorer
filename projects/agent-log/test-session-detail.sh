#!/usr/bin/env bash
# Test script for F8: session detail command

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_LOG="$SCRIPT_DIR/agent-log.sh"

GREEN='\033[0;32m'; RED='\033[0;31m'; RESET='\033[0m'
test_count=0 passed_count=0 failed_count=0

run_test() {
  local name="$1" cmd="$2" expected="$3" expect_fail="${4:-0}"
  ((test_count++))
  echo -n "Test $test_count: $name ... "
  local output; output=$(eval "$cmd" 2>&1); local ec=$?
  if [[ $expect_fail -eq 1 ]]; then
    if [[ $ec -ne 0 ]] && echo "$output" | grep -qF "$expected"; then
      echo -e "${GREEN}PASSED${RESET}"; ((passed_count++))
    else
      echo -e "${RED}FAILED${RESET}"; ((failed_count++))
    fi
  else
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
  fi
}

# Create a test session file
SESS_DIR="$HOME/.openclaw/sessions"
mkdir -p "$SESS_DIR"
TEST_SESS="$SESS_DIR/test-session-abc123.md"
echo -e "# Test Session\nThis is test content.\nSome activity here." > "$TEST_SESS"

echo "=== F8: session detail tests ==="
echo

run_test "session shows content" \
  "$AGENT_LOG session test-session-abc123" \
  "This is test content."

run_test "session shows header" \
  "$AGENT_LOG session test-session-abc123" \
  "Session: test-session-abc123.md"

run_test "session shows metadata" \
  "$AGENT_LOG session test-session-abc123" \
  "lines"

run_test "session partial match works" \
  "$AGENT_LOG session abc123" \
  "This is test content."

run_test "session --json outputs JSON" \
  "$AGENT_LOG session test-session-abc123 -j" \
  '"command":"session"'

run_test "session --json has content" \
  "$AGENT_LOG session test-session-abc123 --json" \
  "test content"

run_test "session missing id errors" \
  "$AGENT_LOG session" \
  "Usage:" \
  1

run_test "session nonexistent errors" \
  "$AGENT_LOG session nonexistent-xyz789" \
  "not found" \
  1

# Cleanup
rm -f "$TEST_SESS"

echo
echo -e "${GREEN}Results: $passed_count/$test_count passed${RESET}"
[[ $failed_count -gt 0 ]] && echo -e "${RED}$failed_count failed${RESET}"
exit $((failed_count > 0 ? 1 : 0))
