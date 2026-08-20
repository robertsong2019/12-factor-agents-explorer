#!/usr/bin/env bash
# test.sh — hermetic test suite for skill-test
# All fixtures live in a mktemp dir; no live-workspace dependency.
#
# Usage: bash tests/test.sh [--keep]   (--keep preserves the fixture dir)

set -u

SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/skill-test"
FIXTURES="$(mktemp -d /tmp/skill-test-fixtures.XXXXXX)"
PASS=0; FAIL=0; TESTS=()

ok()     { PASS=$((PASS+1)); echo "  ok $PASS - $1"; }
not_ok() { FAIL=$((FAIL+1)); echo "  NOT OK - $1"; }

# run_skill <args...> — capture combined output + exit code into OUT / RC
OUT=""; RC=0
run_skill() {
  OUT="$(bash "$SCRIPT" "$@" 2>&1)"; RC=$?
}

# assert_no ANSI codes leak into machine-readable lines
strip_ansi() { printf '%s' "$OUT" | sed -E 's/\x1b\[[0-9;]*[mK]//g'; }

# ─── Fixtures ───

mkdir -p "$FIXTURES/good"
cat > "$FIXTURES/good/SKILL.md" <<'EOF'
# Good Skill

Description: does useful things reliably.

## Usage

Example: run `myscript.sh --dry-run` for a preview.
EOF
echo 'echo hi' > "$FIXTURES/good/myscript.sh"
chmod +x "$FIXTURES/good/myscript.sh"

mkdir -p "$FIXTURES/empty"
: > "$FIXTURES/empty/placeholder"

mkdir -p "$FIXTURES/short"
printf '# T\nd\n' > "$FIXTURES/short/SKILL.md"

mkdir -p "$FIXTURES/danger"
cat > "$FIXTURES/danger/SKILL.md" <<'EOF'
# Danger Skill

Description: cleans things up quickly.

## Usage

Example: rm -rf /tmp/cache
EOF

mkdir -p "$FIXTURES/secrets"
cat > "$FIXTURES/secrets/SKILL.md" <<'EOF'
# Secret Skill

Description: holds credentials.

## Usage

Set OPENAI_KEY=sk-abcdefghijklmnopqrstuvwxyz123456
EOF

mkdir -p "$FIXTURES/nousage"
cat > "$FIXTURES/nousage/SKILL.md" <<'EOF'
# Bare Skill

Description: minimal but valid content without any samples.
This document deliberately avoids the word for a common demonstration
so that the discoverability check has nothing to latch onto.
It simply describes behavior in plain prose for the reader.
Nothing else to see here at all, truly.
EOF

mkdir -p "$FIXTURES/refs"
cat > "$FIXTURES/refs/SKILL.md" <<'EOF'
# Refs Skill

Description: references local files.

## Usage

Read helper.md first, then run build.sh.
EOF
echo '# helper' > "$FIXTURES/refs/helper.md"
echo 'echo build' > "$FIXTURES/refs/build.sh"
chmod -x "$FIXTURES/refs/build.sh"

# ─── 1. Good skill passes ───
TESTS+=("good skill: exit 0")
run_skill "$FIXTURES/good"
[ "$RC" -eq 0 ] && ok "good skill exits 0" || not_ok "good skill exits 0 (got $RC)"

TESTS+=("good skill: summary line")
strip_ansi | grep -q "Skill looks good" && ok "good skill shows success summary" || not_ok "good skill shows success summary"

TESTS+=("good skill: title extracted")
strip_ansi | grep -q "Has title: Good Skill" && ok "title extracted from H1" || not_ok "title extracted from H1"

# ─── 2. Missing SKILL.md ───
TESTS+=("missing SKILL.md: exit 1")
run_skill "$FIXTURES/empty"
[ "$RC" -eq 1 ] && ok "missing SKILL.md exits 1" || not_ok "missing SKILL.md exits 1 (got $RC)"

TESTS+=("missing SKILL.md: message")
strip_ansi | grep -qi "SKILL.md missing" && ok "missing SKILL.md reported" || not_ok "missing SKILL.md reported"

# ─── 3. Too short ───
TESTS+=("short SKILL.md: fails length check")
run_skill "$FIXTURES/short"
[ "$RC" -eq 1 ] && strip_ansi | grep -q "too short" \
  && ok "short SKILL.md flagged" || not_ok "short SKILL.md flagged"

# ─── 4. Dangerous commands ───
TESTS+=("dangerous command: exit 1")
run_skill "$FIXTURES/danger"
[ "$RC" -eq 1 ] && ok "rm -rf skill exits 1" || not_ok "rm -rf skill exits 1 (got $RC)"

TESTS+=("dangerous command: message")
strip_ansi | grep -qi "dangerous command" && ok "dangerous pattern reported" || not_ok "dangerous pattern reported"

# ─── 5. Hardcoded secrets ───
TESTS+=("hardcoded secret: exit 1")
run_skill "$FIXTURES/secrets"
[ "$RC" -eq 1 ] && strip_ansi | grep -qi "secret" \
  && ok "sk- key detected" || not_ok "sk- key detected (rc=$RC)"

# ─── 6. No usage examples → warn but exit 0 ───
TESTS+=("no usage: warn + exit 0")
run_skill "$FIXTURES/nousage"
[ "$RC" -eq 0 ] && strip_ansi | grep -qi "No usage examples" \
  && ok "missing usage warns without failing" || not_ok "missing usage warns without failing (rc=$RC)"

# ─── 7. Local refs ───
TESTS+=("local ref exists: verbose info")
run_skill "$FIXTURES/refs" --verbose
strip_ansi | grep -q "Referenced file exists: helper.md" \
  && ok "existing ref confirmed in verbose" || not_ok "existing ref confirmed in verbose"

TESTS+=("existing ref: no false warning")
! strip_ansi | grep -q "helper.md not found" \
  && ok "existing ref not warned" || not_ok "existing ref not warned"

TESTS+=("non-executable script: warn suggests --fix")
[ "$RC" -eq 0 ] && strip_ansi | grep -q "Script not executable: build.sh" \
  && ok "non-executable warned, run passes" || not_ok "non-executable warned, run passes (rc=$RC)"

# ─── 8. --fix chmods scripts ───
TESTS+=("--fix: chmods non-executable script")
run_skill "$FIXTURES/refs" --fix
[ -x "$FIXTURES/refs/build.sh" ] && ok "--fix made script executable" || not_ok "--fix made script executable"

TESTS+=("--fix: reports the fix")
strip_ansi | grep -qi "Fixed permissions: build.sh" && ok "--fix reports chmod" || not_ok "--fix reports chmod"

# ─── 9. No args defaults to cwd ───
TESTS+=("no args: tests current dir")
OUT="$(cd "$FIXTURES/good" && bash "$SCRIPT" 2>&1)"; RC=$?
[ "$RC" -eq 0 ] && printf '%s' "$OUT" | sed -E 's/\x1b\[[0-9;]*[mK]//g' | grep -q "Testing: $FIXTURES/good" \
  && ok "no-arg defaults to cwd" || not_ok "no-arg defaults to cwd"

# ─── 10. Results counters present ───
TESTS+=("summary counters rendered")
run_skill "$FIXTURES/good"
strip_ansi | grep -Eq "Pass: [0-9]+" && strip_ansi | grep -Eq "Warn: [0-9]+" \
  && ok "Pass/Warn counters shown" || not_ok "Pass/Warn counters shown"

# ─── 11. Flag-first invocation keeps the path (regression: flags dropped path) ───
TESTS+=("flag-first: path honored after flags")
OUT="$(cd /tmp && bash "$SCRIPT" --verbose "$FIXTURES/good" 2>&1)"; RC=$?
[ "$RC" -eq 0 ] && printf '%s' "$OUT" | sed -E 's/\x1b\[[0-9;]*[mK]//g' | grep -q "Testing: $FIXTURES/good" \
  && ok "--verbose <path> tests <path>" || not_ok "--verbose <path> tests <path>"

TESTS+=("flag-first: --fix keeps path")
chmod -x "$FIXTURES/good/myscript.sh"
OUT="$(cd /tmp && bash "$SCRIPT" --fix "$FIXTURES/good" 2>&1)"; RC=$?
[ -x "$FIXTURES/good/myscript.sh" ] \
  && ok "--fix <path> chmods in <path>" || not_ok "--fix <path> chmods in <path>"

# ─── 12. URL refs don't trigger false warnings (regression: https://… .md extracted as local ref)
TESTS+=("url ref: no false not-found warning")
mkdir -p "$FIXTURES/urlrefs"
cat > "$FIXTURES/urlrefs/SKILL.md" <<'EOF'
# URL Refs Skill

Description: links to external docs.

## Usage

See https://example.com/guide.md and https://raw.githubusercontent.com/o/r/main/README.md
EOF
run_skill "$FIXTURES/urlrefs"
! strip_ansi | grep -q "not found" \
  && ok "https .md refs ignored" || not_ok "https .md refs ignored"

# ─── Summary ───
TOTAL=$((PASS+FAIL))
echo ""
echo "skill-test suite: $PASS/$TOTAL pass"
if [ -n "${1:-}" ] && [ "$1" = "--keep" ]; then
  echo "fixtures kept at: $FIXTURES"
else
  rm -rf "$FIXTURES"
fi
[ "$FAIL" -eq 0 ]
