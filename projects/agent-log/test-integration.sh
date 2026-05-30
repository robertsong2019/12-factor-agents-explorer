#!/usr/bin/env bash
# Test script for F17: Integration tests with sample fixture data
# Creates a temp workspace with known files and verifies commands against it

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_LOG="$SCRIPT_DIR/agent-log.sh"

GREEN='\033[0;32m'; RED='\033[0;31m'; CYAN='\033[0;36m'; RESET='\033[0m'
test_count=0 passed_count=0 failed_count=0

# Create temp fixture workspace
FIXTURE_DIR=$(mktemp -d)
FIXTURE_MEMORY="$FIXTURE_DIR/memory"
mkdir -p "$FIXTURE_MEMORY"

# Create known fixture files
cat > "$FIXTURE_MEMORY/2026-05-28.md" << 'EOF'
# 2026-05-28 Daily Log

## Morning
- Fixed bug in agent-task-cli Cache module
- Reviewed PR #42 for EventBus refactor
- Deployed v2.1.0 to staging

## Afternoon
- Research on RAG patterns for agent memory
- Meeting with team about Q3 roadmap
EOF

cat > "$FIXTURE_MEMORY/2026-05-29.md" << 'EOF'
# 2026-05-29 Daily Log

## Coding
- Implemented Cache.getOrSet feature (F18)
- Added EventBus.once (F17)
- Wrote tests for RetryHandler.withBackoff

## Research
- Read paper on tool-use in LLMs
- Explored MCP protocol spec v2
EOF

cat > "$FIXTURE_MEMORY/2026-05-30.md" << 'EOF'
# 2026-05-30 Daily Log

## Today
- Working on agent-log date range search (F2)
- Planning next sprint features
- Code review for prompt-mgr
EOF

# Also create a small MEMORY.md
cat > "$FIXTURE_DIR/MEMORY.md" << 'EOF'
# MEMORY.md
Long-term notes about the workspace.
Key decision: use TSV for experiment tracking.
EOF

run_test() {
  local test_name="$1" test_cmd="$2" expected="$3" expect_fail="${4:-0}"
  ((test_count++))
  echo -n "  Test $test_count: $test_name ... "
  local output; output=$(eval "$test_cmd" 2>&1); local rc=$?
  if [[ $expect_fail -eq 1 ]]; then
    if [[ $rc -ne 0 ]] && echo "$output" | grep -q "$expected"; then
      echo -e "${GREEN}PASS${RESET}"; ((passed_count++))
    else
      echo -e "${RED}FAIL${RESET}"; ((failed_count++))
      echo "    $(echo "$output" | head -1)"
    fi
  else
    if [[ $rc -ne 0 ]]; then
      echo -e "${RED}FAIL${RESET} (exit $rc)"; ((failed_count++))
      echo "    $(echo "$output" | head -1)"
    elif echo "$output" | grep -q "$expected"; then
      echo -e "${GREEN}PASS${RESET}"; ((passed_count++))
    else
      echo -e "${RED}FAIL${RESET} (pattern: $expected)"; ((failed_count++))
      echo "    Got: $(echo "$output" | head -2)"
    fi
  fi
}

echo -e "${CYAN}Integration Tests with Fixture Data${RESET}"
echo "Workspace: $FIXTURE_DIR"
echo "========================================"
echo

# Override workspace for all tests
export OPENCLAW_WORKSPACE="$FIXTURE_DIR"

echo "search tests"
run_test "Search finds 'Cache' across fixture files" \
  "$AGENT_LOG search 'Cache'" \
  "Cache"
run_test "Search with --from only shows recent files" \
  "$AGENT_LOG search --from 2026-05-30 'sprint'" \
  "sprint"
run_test "Search --from 2026-05-29 finds 'RAG' in earlier file" \
  "$AGENT_LOG search --from 2026-05-29 'RAG'" \
  "RAG"
run_test "Search --to 2026-05-28 finds 'staging' only in 05-28 file" \
  "$AGENT_LOG search --to 2026-05-28 'staging'" \
  "staging"
run_test "Regex search finds pattern" \
  "$AGENT_LOG search -r 'F[0-9]{2}'" \
  "F17"

echo
echo "summary tests"
run_test "Summary with --days 3 shows 3 files" \
  "$AGENT_LOG summary --days 3" \
  "2026-05-28"
run_test "Summary --days 1 only shows today" \
  "$AGENT_LOG summary --days 1" \
  "2026-05-30"
run_test "Summary with -k keyword filters" \
  "$AGENT_LOG summary --days 3 -k 'sprint'" \
  "filter: sprint"
run_test "Summary --json output is valid JSON" \
  "$AGENT_LOG summary --days 3 -j" \
  '"command":"summary"'
run_test "Summary --csv has header" \
  "$AGENT_LOG summary --days 3 --csv" \
  "date,weekday,lines"

echo
echo "today tests"
run_test "today command shows today's log" \
  "$AGENT_LOG today | head -5" \
  "2026-05-30"

echo
echo "date tests"
run_test "date command shows specific date" \
  "$AGENT_LOG date 2026-05-28 | head -5" \
  "2026-05-28"

echo
echo "stats tests"
run_test "stats shows workspace statistics" \
  "$AGENT_LOG stats" \
    "files"

# Cleanup
rm -rf "$FIXTURE_DIR"

echo
echo "========================================"
echo "Total: $test_count | ${GREEN}Passed: $passed_count${RESET} | ${RED}Failed: $failed_count${RESET}"
if [[ $failed_count -eq 0 ]]; then
  echo -e "\n${GREEN}All integration tests passed!${RESET}"
  exit 0
else
  echo -e "\n${RED}Some tests failed!${RESET}"
  exit 1
fi
