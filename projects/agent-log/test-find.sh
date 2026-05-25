#!/usr/bin/env bash
# Test F9: find command — find sessions by pattern/date
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$SCRIPT_DIR/agent-log.sh"

# Setup temp dirs
export OPENCLAW_WORKSPACE="$(mktemp -d)"
mkdir -p "$OPENCLAW_WORKSPACE/memory"
MOCK_SESSIONS="$(mktemp -d)"
trap 'rm -rf "$OPENCLAW_WORKSPACE" "$MOCK_SESSIONS"' EXIT

# Override SESSIONS_DIR by patching the script
# We'll source helper functions and call directly instead
# Simpler: just create files in the real path via HOME override
export HOME="$(mktemp -d)"
mkdir -p "$HOME/.openclaw/workspace/memory" "$HOME/.openclaw/sessions"
trap 'rm -rf "$OPENCLAW_WORKSPACE" "$MOCK_SESSIONS" "$HOME"' EXIT
export OPENCLAW_WORKSPACE="$HOME/.openclaw/workspace"
SCRIPT="$SCRIPT_DIR/agent-log.sh"

# Create mock session files
echo "Session with agent: gpt-4 model running task" > "$HOME/.openclaw/sessions/2026-05-20-gpt4-session.md"
echo "Session with agent: claude model running task" > "$HOME/.openclaw/sessions/2026-05-22-claude-session.md"
echo "Session with agent: glm model running task" > "$HOME/.openclaw/sessions/2026-05-24-glm-session.md"

# Fix timestamps for date filtering
touch -d "2026-05-20" "$HOME/.openclaw/sessions/2026-05-20-gpt4-session.md"
touch -d "2026-05-22" "$HOME/.openclaw/sessions/2026-05-22-claude-session.md"
touch -d "2026-05-24" "$HOME/.openclaw/sessions/2026-05-24-glm-session.md"

pass=0 fail=0
assert() {
  local desc="$1" expect="$2" actual="$3"
  if [[ "$actual" == *"$expect"* ]]; then
    echo "  ✅ $desc"; pass=$((pass+1))
  else
    echo "  ❌ $desc"; echo "    expected: $expect"; echo "    got: ${actual:0:200}"; fail=$((fail+1))
  fi
}

echo "=== F9: find command tests ==="

# Test 1: find by pattern
out=$(bash "$SCRIPT" find "gpt-4" 2>&1)
assert "find by pattern matches" "gpt4-session" "$out"

# Test 2: find by pattern (no match)
out=$(bash "$SCRIPT" find "nonexistent-model" 2>&1)
assert "find no match returns 0 sessions" "0 sessions" "$out"

# Test 3: find with date range
out=$(bash "$SCRIPT" find "" -a 2026-05-21 -b 2026-05-23 2>&1)
assert "date range filters correctly" "claude-session" "$out"

# Test 4: find with --after only
out=$(bash "$SCRIPT" find "" -a 2026-05-23 2>&1)
assert "after filter works" "glm-session" "$out"

# Test 5: find with JSON output
out=$(bash "$SCRIPT" find "claude" -j 2>&1)
assert "JSON output has command field" '"command":"find"' "$out"
assert "JSON output has claude session" "claude-session" "$out"

# Test 6: find with no args shows error
out=$(bash "$SCRIPT" find 2>&1) && rc=0 || rc=$?
assert "no args shows usage error" "Usage" "$out"

echo
echo "Results: $pass passed, $fail failed"
exit $fail
