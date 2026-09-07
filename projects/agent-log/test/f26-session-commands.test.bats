#!/usr/bin/env bats
# F26: characterization coverage for commands with zero bats coverage:
# sessions, session, find, tail, trend. (grep/date bugs live in F25.)

setup() {
  source "$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)/setup_fixture.sh"
  setup
  AGENT_LOG="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)/../agent-log.sh"
  export AGENT_LOG
  SESS="$FAKEHOME/.openclaw/sessions"
  printf 'alpha report body\n' > "$SESS/20260901-alpha.md"
  printf 'beta report body\n'  > "$SESS/20260902-beta.md"
  touch -d "$FIX_D1 10:00:00" "$SESS/20260901-alpha.md"
  touch -d "$FIX_D2 10:00:00" "$SESS/20260902-beta.md"
}

teardown() { teardown; }

# ── sessions ──

@test "F26: sessions lists fixture sessions newest first" {
  run "$AGENT_LOG" sessions
  [ "$status" -eq 0 ]
  [[ "$output" == *"alpha.md"* ]]
  [[ "$output" == *"beta.md"* ]]
  local pa pb
  pa=${output%%alpha.md*}; pb=${output%%beta.md*}
  [ "${#pa}" -lt "${#pb}" ]   # alpha (newer) appears first
}

@test "F26: sessions --json reports count and entries" {
  run "$AGENT_LOG" sessions --json
  [ "$status" -eq 0 ]
  [[ "$output" == *'"command":"sessions"'* ]]
  [[ "$output" == *'"count":2'* ]]
  [[ "$output" == *'"file":"'* ]]
}

# ── session ──

@test "F26: session shows a session by exact name" {
  run "$AGENT_LOG" session 20260901-alpha.md
  [ "$status" -eq 0 ]
  [[ "$output" == *"alpha report body"* ]]
}

@test "F26: session resolves a partial id" {
  run "$AGENT_LOG" session alpha
  [ "$status" -eq 0 ]
  [[ "$output" == *"alpha report body"* ]]
}

@test "F26: session --json includes content and lines" {
  run "$AGENT_LOG" session alpha --json
  [ "$status" -eq 0 ]
  [[ "$output" == *'"command":"session"'* ]]
  [[ "$output" == *'"lines":1'* ]]
  [[ "$output" == *'alpha report body'* ]]
}

@test "F26: session for missing id is a usage error" {
  run "$AGENT_LOG" session no-such-session
  [ "$status" -eq 1 ]
  [[ "$output" == *"not found"* ]]
}

# ── find ──

@test "F26: find matches pattern in session content" {
  printf 'gamma report body\n' > "$SESS/20260903-gamma.md"
  run "$AGENT_LOG" find gamma
  [ "$status" -eq 0 ]
  [[ "$output" == *"gamma.md"* ]]
}

@test "F26: find --json reports matched count" {
  run "$AGENT_LOG" find beta --json
  [ "$status" -eq 0 ]
  [[ "$output" == *'"command":"find"'* ]]
  [[ "$output" == *'"count":1'* ]]
  [[ "$output" == *'beta.md'* ]]
}

@test "F26: find --after filters by modification date" {
  run "$AGENT_LOG" find report -a "$FIX_D1" --json
  [ "$status" -eq 0 ]
  [[ "$output" == *'alpha.md'* ]]
  [[ "$output" != *'beta.md'* ]]   # beta modified D2 (before cutoff)
}

@test "F26: find with no args is a usage error" {
  run "$AGENT_LOG" find
  [ "$status" -eq 1 ]
  [[ "$output" == *"Usage"* ]]
}

# ── tail ──

@test "F26: tail shows the most recent session file" {
  run "$AGENT_LOG" tail
  [ "$status" -eq 0 ]
  [[ "$output" == *"alpha.md"* ]]
  [[ "$output" == *"alpha report body"* ]]
}

@test "F26: tail -n limits output lines" {
  printf 'l1\nl2\nl3\nl4\nl5\n' > "$SESS/five-lines.md"
  run "$AGENT_LOG" tail -n 2
  [ "$status" -eq 0 ]
  [[ "$output" == *"l4"* ]]
  [[ "$output" == *"l5"* ]]
  [[ "$output" != *"l3"* ]]
}

# ── trend ──

@test "F26: trend --json emits one data point per day" {
  run "$AGENT_LOG" trend 7 --json
  [ "$status" -eq 0 ]
  [[ "$output" == *'"command":"trend"'* ]]
  local n
  n=$(printf '%s\n' "$output" | grep -o '"date"' | wc -l)
  [ "$n" -eq 7 ]
}

@test "F26: trend includes today's note line count" {
  run "$AGENT_LOG" trend 3
  [ "$status" -eq 0 ]
  [[ "$output" == *"Max:"* ]]
}
