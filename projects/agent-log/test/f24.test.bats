#!/usr/bin/env bats
# F24 (cron --job <pattern> filter) tests.
#
# Mocks: a fake `openclaw` binary is prepended to PATH so cmd_cron's
# `openclaw cron list` call returns a fixed job table. Hermetic (F21 spirit):
# never touches the real openclaw CLI or live cron table.

setup() {
  source "$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)/setup_fixture.sh"
  setup
  AGENT_LOG="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)/../agent-log.sh"
  export AGENT_LOG

  # Fake openclaw: stable multi-job listing (mimics `openclaw cron list`)
  export FAKEBIN="$FIXTURE_DIR/fakebin"
  mkdir -p "$FAKEBIN"
  cat > "$FAKEBIN/openclaw" <<'EOF'
#!/usr/bin/env bash
if [ "$1" = "cron" ] && [ "$2" = "list" ]; then
  printf '%s\n' \
    "62bf7f3b  tool-development-evening  22:00  daily" \
    "9a2c1d4e  essay-morning             05:00  daily" \
    "510a8d6d  github-creative-evening    21:00  daily" \
    "84707ade  ai-neuroscience-research   22:30  weekly"
  exit 0
fi
exit 1
EOF
  chmod +x "$FAKEBIN/openclaw"
}

teardown() {
  teardown
}

@test "F24: cron without --job lists all jobs (passthrough intact)" {
  run bash -c "PATH=\"$FAKEBIN:$PATH\" bash '$AGENT_LOG' cron"
  [ "$status" -eq 0 ]
  [[ "$output" =~ "tool-development-evening" ]]
  [[ "$output" =~ "essay-morning" ]]
  [[ "$output" =~ "ai-neuroscience-research" ]]
}

@test "F24: cron --job filters to matching rows only" {
  run bash -c "PATH=\"$FAKEBIN:$PATH\" bash '$AGENT_LOG' cron --job evening"
  [ "$status" -eq 0 ]
  [[ "$output" =~ "tool-development-evening" ]]
  [[ "$output" =~ "github-creative-evening" ]]
  [[ ! "$output" =~ "essay-morning" ]]   # 05:00 morning job must be filtered out
}

@test "F24: cron --job is case-insensitive" {
  run bash -c "PATH=\"$FAKEBIN:$PATH\" bash '$AGENT_LOG' cron --job ESSAY"
  [ "$status" -eq 0 ]
  [[ "$output" =~ "essay-morning" ]]
  [[ ! "$output" =~ "tool-development-evening" ]]
}

@test "F24: cron --job with no match says so honestly" {
  run bash -c "PATH=\"$FAKEBIN:$PATH\" bash '$AGENT_LOG' cron --job nonexistent-job"
  [ "$status" -eq 0 ]
  [[ "$output" =~ "no matching cron jobs" ]]
  [[ ! "$output" =~ "essay-morning" ]]
}

@test "F24: cron --job without a value is a usage error" {
  run bash -c "PATH=\"$FAKEBIN:$PATH\" bash '$AGENT_LOG' cron --job"
  [ "$status" -ne 0 ]
  [[ "$output" =~ "--job requires a pattern" ]]
}

@test "F24: cron degrades gracefully when openclaw is unavailable" {
  run bash -c "mkdir -p /tmp/f24-nocli && PATH=/tmp/f24-nocli:/usr/bin:/bin bash '$AGENT_LOG' cron --job x"
  [ "$status" -eq 0 ]
  [[ "$output" =~ "openclaw" ]]
}
