#!/usr/bin/env bash
# Test F13: grep command + F14: tail command
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

export HOME="$(mktemp -d)"
mkdir -p "$HOME/.openclaw/workspace/memory" "$HOME/.openclaw/sessions"
trap 'rm -rf "$HOME"' EXIT
export OPENCLAW_WORKSPACE="$HOME/.openclaw/workspace"
SCRIPT="$SCRIPT_DIR/agent-log.sh"

# Create mock session files
echo -e "line1: hello world\nline2: foo bar\nline3: hello again" > "$HOME/.openclaw/sessions/test-session-1.md"
echo -e "line1: different content\nline2: another thing" > "$HOME/.openclaw/sessions/test-session-2.md"
touch -d "2026-05-24" "$HOME/.openclaw/sessions/test-session-1.md"
touch -d "2026-05-23" "$HOME/.openclaw/sessions/test-session-2.md"

pass=0 fail=0
assert() {
  local desc="$1" expect="$2" actual="$3"
  if [[ "$actual" == *"$expect"* ]]; then
    echo "  ✅ $desc"; pass=$((pass+1))
  else
    echo "  ❌ $desc"; echo "    expected: $expect"; echo "    got: ${actual:0:200}"; fail=$((fail+1))
  fi
}

echo "=== F13: grep command tests ==="

# Test 1: grep finds pattern
out=$(bash "$SCRIPT" grep "hello" 2>&1)
assert "grep finds hello" "hello" "$out"

# Test 2: grep no match
out=$(bash "$SCRIPT" grep "nonexistent_xyz" 2>&1)
assert "grep no match shows no matches" "(no matches)" "$out"

# Test 3: grep no args
out=$(bash "$SCRIPT" grep 2>&1) && rc=0 || rc=$?
assert "grep no args shows error" "Usage" "$out"

echo
echo "=== F14: tail command tests ==="

# Test 4: tail default shows last lines
out=$(bash "$SCRIPT" tail 2>&1)
assert "tail shows most recent session" "test-session-1" "$out"
assert "tail shows content" "hello again" "$out"

# Test 5: tail -n 1
out=$(bash "$SCRIPT" tail -n 1 2>&1)
assert "tail -n 1 shows one line" "hello again" "$out"

# Test 6: tail with no sessions
HOME2="$(mktemp -d)"; mkdir -p "$HOME2/.openclaw/workspace/memory" "$HOME2/.openclaw/sessions"
OPENCLAW_WORKSPACE2="$HOME2/.openclaw/workspace"
out=$(HOME="$HOME2" OPENCLAW_WORKSPACE="$OPENCLAW_WORKSPACE2" bash "$SCRIPT" tail 2>&1) && rc=0 || rc=$?
assert "tail no sessions shows error" "No session files found" "$out"
rm -rf "$HOME2"

echo
echo "Results: $pass passed, $fail failed"
exit $fail
