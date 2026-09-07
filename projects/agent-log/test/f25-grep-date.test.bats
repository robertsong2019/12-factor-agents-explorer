#!/usr/bin/env bats
# F25: cmd_grep false "(no matches)" + cmd_date end-of-day boundary bugs.
#
# Bug 1 (red-verified 2026-09-08): `grep -r ... | head -50 || echo "(no matches)"`
# under `set -o pipefail` — when >50 matches make head close the pipe early,
# grep dies SIGPIPE (141) → pipefail turns the pipeline status non-zero →
# the `||` fallback fires AFTER head has already emitted 50 real match lines.
# User sees 50 results followed by a false "(no matches)" claim.
#
# Bug 2 (red-verified 2026-09-08): cmd_date used `! -newermt "$d 23:59:59"`,
# which excludes sessions modified in the final second of the day
# (23:59:59.000001–23:59:59.999999) from that day's session activity.

setup() {
  source "$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)/setup_fixture.sh"
  setup
  AGENT_LOG="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)/../agent-log.sh"
  export AGENT_LOG
  SESS="$FAKEHOME/.openclaw/sessions"
}

teardown() { teardown; }

@test "F25: grep with >50 matches does NOT falsely claim (no matches)" {
  for i in $(seq 1 2000); do
    echo "needlepin line $i aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  done > "$SESS/big.md"
  run "$AGENT_LOG" grep needlepin
  [ "$status" -eq 0 ]
  # RED (bug 1): output ends with a false "(no matches)" after real results
  [[ "$output" != *"(no matches)"* ]]
}

@test "F25: grep with >50 matches shows exactly 50 match lines" {
  for i in $(seq 1 2000); do
    echo "needlepin line $i aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  done > "$SESS/big.md"
  run "$AGENT_LOG" grep needlepin
  [ "$status" -eq 0 ]
  local n
  n=$(printf '%s\n' "$output" | grep -c 'needlepin')
  [ "$n" -eq 50 ]
}

@test "F25: grep with zero matches says so honestly" {
  echo "nothing relevant here" > "$SESS/plain.md"
  run "$AGENT_LOG" grep needlepin
  [ "$status" -eq 0 ]
  [[ "$output" == *"(no matches)"* ]]
}

@test "F25: grep shows file:line prefix for matches" {
  printf 'alpha first\nbeta second\nalpha third\n' > "$SESS/mix.md"
  run "$AGENT_LOG" grep alpha
  [ "$status" -eq 0 ]
  [[ "$output" == *":1:alpha first"* ]]
  [[ "$output" == *":3:alpha third"* ]]
}

@test "F25: date includes session modified in the final second of the day" {
  touch -d "$FIX_D1 23:59:59.5" "$SESS/edge.md"
  touch -d "$FIX_D1 12:00:00" "$SESS/noon.md"
  run "$AGENT_LOG" date "$FIX_D1"
  [ "$status" -eq 0 ]
  # RED (bug 2): edge.md was invisible to that day's session activity
  [[ "$output" == *"edge.md"* ]]
  [[ "$output" == *"noon.md"* ]]
}

@test "F25: date does not leak sessions from the next day" {
  local nd
  nd=$(date -d "$FIX_D1 + 1 day" +%Y-%m-%d 2>/dev/null || date -v+1d -j -f "%Y-%m-%d" "$FIX_D1" +%Y-%m-%d)
  touch -d "$nd 08:00:00" "$SESS/tomorrow.md"
  touch -d "$FIX_D1 12:00:00" "$SESS/noon.md"
  run "$AGENT_LOG" date "$FIX_D1"
  [ "$status" -eq 0 ]
  [[ "$output" == *"noon.md"* ]]
  [[ "$output" != *"tomorrow.md"* ]]
}
