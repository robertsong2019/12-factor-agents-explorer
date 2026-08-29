#!/usr/bin/env bats
# F22 (search -C/--context N) + F23 (hot top-K terms) tests

setup() {
  source "$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)/setup_fixture.sh"
  setup
  # OPENCLAW_WORKSPACE + HOME are exported hermetically by setup_fixture (F21)
  AGENT_LOG="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)/../agent-log.sh"
  export AGENT_LOG

  # Controlled corpus for hot (F23): deterministic counts, no ties at the top.
  cat > "$MEMORY_DIR/hot-corpus.md" <<EOF
# hot corpus
kubernetes kubernetes kubernetes kubernetes kubernetes
docker docker docker
the the the the the the the the and and and
EOF
}

teardown() {
  teardown
}

# --- F22: search -C/--context ---

@test "F22: -C 2 shows more surrounding lines than default" {
  run bash "$AGENT_LOG" search emitAsync
  [ "$status" -eq 0 ]
  default_lines=$(printf '%s\n' "$output" | wc -l)
  run bash "$AGENT_LOG" search -C 5 emitAsync
  [ "$status" -eq 0 ]
  wide_lines=$(printf '%s\n' "$output" | wc -l)
  [ "$wide_lines" -gt "$default_lines" ]
}

@test "F22: -C 2 includes lines 2 away from match" {
  # D1 file: "## 11:00 - coding session with gpt-4" / "- Refactored EventBus" / "- Added emitAsync feature"
  # match "emitAsync" with -C 2 must include the heading 2 lines above
  run bash "$AGENT_LOG" search -C 2 emitAsync
  [ "$status" -eq 0 ]
  [[ "$output" =~ "coding session" ]]
}

@test "F22: -C 0 shows no context lines (match lines only)" {
  run bash "$AGENT_LOG" search -C 0 emitAsync
  [ "$status" -eq 0 ]
  [[ "$output" =~ "emitAsync" ]]
  # The heading and the "Refactored" neighbor must NOT appear as context
  [[ ! "$output" =~ "coding session" ]]
}

@test "F22: invalid -C value dies with error" {
  run bash "$AGENT_LOG" search -C xyz emitAsync
  [ "$status" -ne 0 ]
  [[ "$output" =~ "non-negative integer" ]]
}

@test "F22: -C applies to exported file too" {
  outfile="$FIXTURE_DIR/export-context.txt"
  run bash "$AGENT_LOG" search -C 3 -o "$outfile" emitAsync
  [ "$status" -eq 0 ]
  grep -q "coding session" "$outfile"
}

# --- F23: hot ---

@test "F23: hot ranks controlled corpus first (kubernetes=5)" {
  run bash "$AGENT_LOG" hot 5
  [ "$status" -eq 0 ]
  top=$(printf '%s\n' "$output" | awk '/kubernetes/{print $1; exit}')
  [ "$top" = "5" ]
}

@test "F23: hot respects N (default 10, hot 1 single row)" {
  run bash "$AGENT_LOG" hot 1
  [ "$status" -eq 0 ]
  rows=$(printf '%s\n' "$output" | grep -cE '^[[:space:]]+[0-9]+[[:space:]]+[a-z]')
  [ "$rows" = "1" ]
  [[ "$output" =~ "kubernetes" ]]
}

@test "F23: hot filters stopwords (the/and absent)" {
  run bash "$AGENT_LOG" hot 20
  [ "$status" -eq 0 ]
  [[ ! "$output" =~ ^' '*3' the' ]]
  [[ ! "$output" =~ ^' '*3' and' ]]
  # "the" count would be 6+ from corpus if unfiltered
  [[ ! "$output" =~ ' the'$'\n' ]]
  [[ "$output" =~ "docker" ]]
}

@test "F23: hot --from excludes older files" {
  # hot-corpus.md has a non-date basename so it is always included;
  # FIX_D1..now window excludes FIX_D2 (agent-log mention lives there).
  run bash "$AGENT_LOG" hot 20 --from "$FIX_D1"
  [ "$status" -eq 0 ]
  [[ ! "$output" =~ "agent-log" ]]
  [[ "$output" =~ "kubernetes" ]]
}

@test "F23: hot --to excludes newer files" {
  # --to FIX_D2 keeps D2 (agent-log mention) + undated corpus, drops D1/D0 terms.
  run bash "$AGENT_LOG" hot 30 --to "$FIX_D2"
  [ "$status" -eq 0 ]
  [[ "$output" =~ "agent-log" ]]
  [[ ! "$output" =~ "eventbus" ]]
  [[ ! "$output" =~ "bats" ]]
}

@test "F23: hot JSON shape and counts" {
  run bash "$AGENT_LOG" hot 2 -j
  [ "$status" -eq 0 ]
  [[ "$output" =~ '"command":"hot"' ]]
  [[ "$output" =~ '"term":"kubernetes","count":5' ]]
  [[ "$output" =~ '"term":"docker","count":3' ]]
}

@test "F23: hot invalid N dies" {
  run bash "$AGENT_LOG" hot 0
  [ "$status" -ne 0 ]
  run bash "$AGENT_LOG" hot -n xyz
  [ "$status" -ne 0 ]
  [[ "$output" =~ "positive integer" ]]
}
