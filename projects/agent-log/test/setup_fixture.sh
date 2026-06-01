#!/usr/bin/env bash
# Setup test fixtures for agent-log bats tests
setup() {
  export FIXTURE_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)/fixtures"
  export MEMORY_DIR="$FIXTURE_DIR/memory"
  mkdir -p "$MEMORY_DIR"
  
  # Create sample log files
  cat > "$MEMORY_DIR/2026-05-30.md" <<'EOF'
# 2026-05-30

## 10:00 - Started work on agent-log
- Implemented F4 keyword filtering
- Tests passing

## 14:00 - Review session
- Reviewed PR #42
- Fixed edge case in search command
EOF

  cat > "$MEMORY_DIR/2026-05-31.md" <<'EOF'
# 2026-05-31

## 09:00 - Morning standup
- Discussed roadmap

## 11:00 - coding session with gpt-4
- Refactored EventBus
- Added emitAsync feature

## 16:00 - wrap up
- Committed changes
EOF

  cat > "$MEMORY_DIR/2026-06-01.md" <<'EOF'
# 2026-06-01

## 08:00 - planning
- Today's goals: Bats tests
EOF

  # Create minimal session files
  mkdir -p "$FIXTURE_DIR/sessions"
  cat > "$FIXTURE_DIR/sessions/session-2026-05-31-001.json" <<'EOF'
{"id":"session-001","agent":"catalyst","model":"gpt-4","date":"2026-05-31","messages":["hello","world"]}
EOF
  cat > "$FIXTURE_DIR/sessions/session-2026-05-30-001.json" <<'EOF'
{"id":"session-002","agent":"catalyst","model":"claude-3","date":"2026-05-30","messages":["test"]}
EOF
}

teardown() {
  rm -rf "$FIXTURE_DIR"
}
