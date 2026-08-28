#!/usr/bin/env bats
# Bats tests for agent-log core commands (F16, hermetic via setup_fixture since F21)

setup() {
  source "$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)/setup_fixture.sh"
  setup
  AGENT_LOG="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)/../agent-log.sh"
  export AGENT_LOG
}

teardown() {
  teardown
}

# --- summary command ---

@test "summary shows activity for specified days" {
  run bash "$AGENT_LOG" summary 3
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Activity summary" ]]
}

@test "summary with keyword filters results" {
  run bash "$AGENT_LOG" summary 7 "EventBus"
  [ "$status" -eq 0 ]
  [[ "$output" =~ "filter: EventBus" ]]
}

@test "summary with non-matching keyword shows zero files" {
  run bash "$AGENT_LOG" summary 3 "xyznonexistent999"
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Total:" ]]
}

@test "summary JSON output is valid structure" {
  run bash "$AGENT_LOG" summary -j 3
  [ "$status" -eq 0 ]
  [[ "$output" =~ '"command":"summary"' ]]
  # hermetic: dynamic fixture dates guarantee all 3 files fall in the window
  [[ "$output" =~ '"total_files":3' ]]
}

# --- search command ---

@test "search finds keyword in logs" {
  run bash "$AGENT_LOG" search "EventBus"
  [ "$status" -eq 0 ]
  # hermetic: EventBus exists only in the D1 fixture file
  [[ "$output" =~ "$FIX_D1.md" ]]
  [[ "$output" =~ "Refactored EventBus" ]]
}

@test "search with regex flag works" {
  run bash "$AGENT_LOG" search -r "Event.*"
  [ "$status" -eq 0 ]
}

# --- stats command ---

@test "stats shows workspace statistics" {
  run bash "$AGENT_LOG" stats
  [ "$status" -eq 0 ]
}

# --- trend command ---

@test "trend shows activity trends" {
  run bash "$AGENT_LOG" trend 7
  [ "$status" -eq 0 ]
}
