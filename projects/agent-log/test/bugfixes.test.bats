#!/usr/bin/env bats
# Regression tests for 2026-08-22 bugfix cycle (B3/B4/B7 + JSON escaping)

AGENT_LOG="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)/../agent-log.sh"

setup() {
  export TESTHOME="$(mktemp -d)"
  export HOME="$TESTHOME"
  export OPENCLAW_WORKSPACE="$TESTHOME/.openclaw/workspace"
  mkdir -p "$OPENCLAW_WORKSPACE/memory" "$TESTHOME/.openclaw/sessions"
}

teardown() {
  rm -rf "$TESTHOME"
}

json_ok() { python3 -c 'import json,sys; json.load(sys.stdin)'; }

# --- B4: help was completely empty (usage() grepped nonexistent "## Usage" section) ---

@test "help prints non-empty usage with command list" {
  run bash "$AGENT_LOG" help
  [ "$status" -eq 0 ]
  [ "${#output}" -gt 100 ]
  [[ "$output" =~ "search" ]]
  [[ "$output" =~ "clean" ]]
  [[ "$output" =~ "OPENCLAW_WORKSPACE" ]]
}

@test "no args falls back to help (non-empty)" {
  run bash "$AGENT_LOG"
  [ "$status" -eq 0 ]
  [ "${#output}" -gt 100 ]
}

# --- B3: clean deleted content-bearing files without trailing newline (wc -l == 0) ---

@test "clean dry-run does not flag no-newline content file as empty" {
  printf 'content without trailing newline' > "$OPENCLAW_WORKSPACE/memory/2026-08-21.md"
  run bash "$AGENT_LOG" clean -n
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Files removed:" ]]
  [[ "$output" != *"empty:"* ]]
}

@test "clean removes truly empty file but preserves no-newline content file" {
  : > "$OPENCLAW_WORKSPACE/memory/2026-08-20.md"
  printf 'kept content' > "$OPENCLAW_WORKSPACE/memory/2026-08-19.md"
  run bash "$AGENT_LOG" clean
  [ "$status" -eq 0 ]
  [ ! -f "$OPENCLAW_WORKSPACE/memory/2026-08-20.md" ]
  [ -f "$OPENCLAW_WORKSPACE/memory/2026-08-19.md" ]
  grep -q 'kept content' "$OPENCLAW_WORKSPACE/memory/2026-08-19.md"
}

# --- B7: find -j emitted }{ (string append, no commas) with 2+ results ---

@test "find -j with multiple results is valid JSON" {
  printf 'alpha topic\n' > "$HOME/.openclaw/sessions/a.md"
  printf 'beta topic\n'  > "$HOME/.openclaw/sessions/b.md"
  touch -d '2026-08-20' "$HOME/.openclaw/sessions/a.md" "$HOME/.openclaw/sessions/b.md"
  run bash "$AGENT_LOG" find topic -j
  [ "$status" -eq 0 ]
  [[ "$output" == *"{"*","*"{"* ]]   # comma-separated entries
  echo "$output" | json_ok
  [[ "$output" =~ '"count":2' ]]
}

@test "find -j with zero results emits empty results array" {
  run bash "$AGENT_LOG" find nonexistent-zzz -j
  [ "$status" -eq 0 ]
  [[ "$output" =~ '"count":0' ]]
  echo "$output" | json_ok
}

# --- JSON string escaping (query/keyword/pattern/content) ---

@test "search -j escapes double quotes in query" {
  printf 'plain git notes\n' > "$OPENCLAW_WORKSPACE/memory/2026-08-01.md"
  run bash "$AGENT_LOG" search 'git "quoted" term' -j
  [ "$status" -eq 0 ]
  echo "$output" | json_ok
  [[ "$output" =~ '\"quoted\"' ]]
}

@test "summary -j escapes double quotes in keyword" {
  printf 'notes with "quoted" text\n' > "$OPENCLAW_WORKSPACE/memory/$(date +%Y-%m-%d).md"
  run bash "$AGENT_LOG" summary -j 1 -k '"quoted"'
  [ "$status" -eq 0 ]
  echo "$output" | json_ok
  [[ "$output" =~ '"total_files":1' ]]
}

@test "find -j escapes double quotes in pattern" {
  printf 'file containing "quoted" token\n' > "$HOME/.openclaw/sessions/q.md"
  run bash "$AGENT_LOG" find '"quoted"' -j
  [ "$status" -eq 0 ]
  echo "$output" | json_ok
}

@test "session -j escapes newlines and quotes in content" {
  printf '# line one\nline "two"\nline three\n' > "$HOME/.openclaw/sessions/multi.md"
  run bash "$AGENT_LOG" session multi -j
  [ "$status" -eq 0 ]
  echo "$output" | json_ok
  echo "$output" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "line \"two\"" in d["content"], d["content"]; print("content round-trips")'
}
