#!/usr/bin/env bats
# F19 (search --count) + F20 (pipe-safe color output) tests

setup() {
  source "$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)/setup_fixture.sh"
  setup
  # Hermetic: agent-log.sh derives MEMORY_DIR from WORKSPACE, so point it at the fixture
  export OPENCLAW_WORKSPACE="$FIXTURE_DIR"
  AGENT_LOG="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)/../agent-log.sh"
  export AGENT_LOG
}

teardown() {
  teardown
}

# --- F19: search --count ---

@test "F19: --count prints ranked match counts with fixture file" {
  run bash "$AGENT_LOG" search --count emitAsync
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Match counts" ]]
  [[ "$output" =~ "2026-05-31.md" ]]
}

@test "F19: --count value matches fixture content (emitAsync appears once)" {
  run bash "$AGENT_LOG" search --count emitAsync
  [ "$status" -eq 0 ]
  count=$(printf '%s\n' "$output" | awk '/2026-05-31\.md$/{print $1}')
  [ "$count" = "1" ]
}

@test "F19: --count output is sorted descending" {
  run bash "$AGENT_LOG" search --count e
  [ "$status" -eq 0 ]
  counts=$(printf '%s\n' "$output" | awk '/\.md[[:space:]]*$/{gsub(/^[[:space:]]+/,""); print $1}')
  [ -n "$counts" ]
  [ "$counts" = "$(printf '%s\n' "$counts" | sort -rn)" ]
}

@test "F19: --count JSON results sorted by matches desc" {
  run bash "$AGENT_LOG" search --count -j e
  [ "$status" -eq 0 ]
  [[ "$output" =~ '"command":"search"' ]]
  nums=$(printf '%s\n' "$output" | grep -o '"matches":[0-9]*' | cut -d: -f2)
  [ -n "$nums" ]
  [ "$nums" = "$(printf '%s\n' "$nums" | sort -rn)" ]
}

@test "F19: --count export writes ranking to file" {
  local out="$FIXTURE_DIR/counts.txt"
  run bash "$AGENT_LOG" search --count -o "$out" emitAsync
  [ "$status" -eq 0 ]
  [ -f "$out" ]
  grep -q '# Match counts for: emitAsync' "$out"
  count=$(awk '/2026-05-31\.md$/{print $1}' "$out")
  [ "$count" = "1" ]
}

@test "F19: --count with no matches exits gracefully" {
  run bash "$AGENT_LOG" search --count xyznonexistent999
  [ "$status" -eq 0 ]
  [[ "$output" =~ "No matches" ]]
}

# --- F20: pipe-safe / NO_COLOR output ---

@test "F20: piped search output contains no ANSI escapes" {
  run bash "$AGENT_LOG" search EventBus
  [ "$status" -eq 0 ]
  ! printf '%s' "$output" | grep -q $'\033'
}

@test "F20: piped trend output contains no ANSI escapes" {
  run bash "$AGENT_LOG" trend 3
  [ "$status" -eq 0 ]
  ! printf '%s' "$output" | grep -q $'\033'
}

@test "F20: NO_COLOR is accepted without breaking output" {
  export NO_COLOR=1
  run bash "$AGENT_LOG" summary 3
  unset NO_COLOR
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Activity summary" ]]
}
