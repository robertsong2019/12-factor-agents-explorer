#!/usr/bin/env bash
# Setup test fixtures for agent-log bats tests.
#
# Hermetic (F21): exports OPENCLAW_WORKSPACE and overrides HOME so that
# agent-log.sh's derived MEMORY_DIR/SESSIONS_DIR point at fixture data,
# never at the live workspace. Previously fixtures were decorative —
# agent-log.sh re-derived MEMORY_DIR from WORKSPACE, so search/summary
# tests accidentally passed against live workspace data.
#
# Dates are dynamic (D0=today, D1=yesterday, D2=two days ago) so fixture
# files always fall inside summary/trend day windows.

setup() {
  export FIXTURE_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)/fixtures"
  export MEMORY_DIR="$FIXTURE_DIR/memory"
  mkdir -p "$MEMORY_DIR"

  # Hermetic environment: fake HOME => SESSIONS_DIR lands in fakehome
  export FAKEHOME="$FIXTURE_DIR/fakehome"
  mkdir -p "$FAKEHOME/.openclaw/sessions"
  export HOME="$FAKEHOME"
  export OPENCLAW_WORKSPACE="$FIXTURE_DIR"

  # Dynamic dates
  export FIX_D0="$(date +%Y-%m-%d)"
  export FIX_D1="$(date -d '1 day ago' +%Y-%m-%d 2>/dev/null || date -v-1d +%Y-%m-%d)"
  export FIX_D2="$(date -d '2 days ago' +%Y-%m-%d 2>/dev/null || date -v-2d +%Y-%m-%d)"

  cat > "$MEMORY_DIR/$FIX_D2.md" <<EOF
# $FIX_D2

## 10:00 - Started work on agent-log
- Implemented F4 keyword filtering
- Tests passing

## 14:00 - Review session
- Reviewed PR #42
- Fixed edge case in search command
EOF

  cat > "$MEMORY_DIR/$FIX_D1.md" <<EOF
# $FIX_D1

## 09:00 - Morning standup
- Discussed roadmap

## 11:00 - coding session with gpt-4
- Refactored EventBus
- Added emitAsync feature

## 16:00 - wrap up
- Committed changes
EOF

  cat > "$MEMORY_DIR/$FIX_D0.md" <<EOF
# $FIX_D0

## 08:00 - planning
- Today's goals: Bats tests
EOF
}

teardown() {
  rm -rf "$FIXTURE_DIR"
}
