#!/usr/bin/env bash
# dep-guard hermetic test suite — stubs npm/pip via PATH, zero network.
# Run: bash test/run.sh   (from tools/dep-guard)
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPG="$SCRIPT_DIR/dep-guard.sh"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

BIN="$TMP/bin"; mkdir -p "$BIN"

# ─── stub npm ─────────────────────────────────────────
cat > "$BIN/npm" <<'STUB'
#!/usr/bin/env bash
echo "npm $*" >> "$STUB_LOG"
if [[ "$1" == "audit" ]]; then
  case "${DEPG_FIXTURE:-clean}" in
    dirty) cat <<'JSON'
{"metadata":{"vulnerabilities":{"info":0,"low":0,"moderate":1,"high":1,"critical":0,"total":2}},
 "vulnerabilities":{
   "lodash":{"severity":"high","title":"Prototype pollution in lodash"},
   "minimist":{"severity":"moderate","title":"Prototype Pollution in minimist"}
 }}
JSON
;;
    heavy) cat <<'JSON'
{"metadata":{"vulnerabilities":{"info":0,"low":0,"moderate":0,"high":7,"critical":0,"total":7}},
 "vulnerabilities":{
   "a":{"severity":"high","title":"v1"},"b":{"severity":"high","title":"v2"},
   "c":{"severity":"high","title":"v3"},"d":{"severity":"high","title":"v4"},
   "e":{"severity":"high","title":"v5"},"f":{"severity":"high","title":"v6"},
   "g":{"severity":"high","title":"v7"}}
}
JSON
;;
    *) echo '{"metadata":{"vulnerabilities":{"info":0,"low":0,"moderate":0,"high":0,"critical":0,"total":0}},"vulnerabilities":{}}'
;;
  esac
elif [[ "$1" == "outdated" ]]; then
  case "${DEPG_FIXTURE:-clean}" in
    dirty) echo '{"express":{"current":"4.18.0","wanted":"4.18.0","latest":"5.1.0"},"ms":{"current":"2.1.1","wanted":"2.1.3","latest":"2.1.3"}}'
;;
    zero) python3 -c "
import json
d = {f'pkg{i:02d}': {'current':'1.0.0','latest':'2.0.0'} for i in range(20)}
print(json.dumps(d))"
;;
    weird) echo '{"ghost":{"current":"missing","latest":"1.0.0"},"beta":{"current":"1.0.0-beta.1","latest":"1.2.0"}}'
;;
    *) echo '{}'
;;
  esac
fi
exit 0
STUB
chmod +x "$BIN/npm"

# ─── stub pip (hermetic python path) ──────────────────
cat > "$BIN/pip" <<'STUB'
#!/usr/bin/env bash
echo "pip $*" >> "$STUB_LOG"
echo '[]'
exit 0
STUB
chmod +x "$BIN/pip"

export PATH="$BIN:$PATH"
export STUB_LOG="$TMP/stub.log"

# ─── fixtures ─────────────────────────────────────────
mkproj() { mkdir -p "$TMP/$1"; }
mkproj proj_node;    echo '{"name":"node","version":"1.0.0"}' > "$TMP/proj_node/package.json"
                       echo '{"lockfileVersion":3}' > "$TMP/proj_node/package-lock.json"
mkproj proj_nolock;  echo '{"name":"nolock","version":"1.0.0"}' > "$TMP/proj_nolock/package.json"
mkproj proj_py;      echo 'requests==2.31.0' > "$TMP/proj_py/requirements.txt"
mkproj proj_unknown

# ─── helpers ──────────────────────────────────────────
PASS=0; FAIL=0; FAILED=()
t() { # t <name> <expected-exit> <cmd...>
  local name="$1" want="$2"; shift 2
  : > "$STUB_LOG"
  "$@" >"$TMP/out" 2>"$TMP/err"; local got=$?
  if [[ "$got" == "$want" ]]; then
    PASS=$((PASS+1)); echo "ok $PASS - $name"
  else
    FAIL=$((FAIL+1)); FAILED+=("$name")
    echo "not ok $PASS - $name (exit $got, want $want)"
    sed 's/^/    # /' "$TMP/err" | head -5
  fi
  return 0
}
assert_contains() { # assert_contains <name> <pattern>
  if grep -q "$2" "$TMP/out" 2>/dev/null; then
    PASS=$((PASS+1)); echo "ok $PASS - $1"
  else
    FAIL=$((FAIL+1)); FAILED+=("$1")
    echo "not ok $PASS - $1 (missing: $2)"
  fi
  return 0
}

run() { # run <fixture> <proj> [args...] — output captured in $TMP/out
  DEPG_FIXTURE="$1" "$DEPG" "${@:3}" "$TMP/$2" >"$TMP/out" 2>"$TMP/err"
}

# ─── 1. bug: pipe-subshell data loss (score was always ~100) ──
t "dirty json exit 0" 0 run dirty proj_node --format json
assert_contains "dirty json score 73 (was 100 pre-fix)" '"score": 73'
assert_contains "dirty json vuln count 2" '"vulnerabilities": 2'
assert_contains "dirty json major 1" '"outdated_major": 1'
assert_contains "dirty json minor 1" '"outdated_minor": 1'
assert_contains "dirty json lockfile true" '"lockfile": true'

# json validity
python3 -m json.tool "$TMP/out" >/dev/null 2>&1 && { PASS=$((PASS+1)); echo "ok $PASS - json output is valid JSON"; } \
  || { FAIL=$((FAIL+1)); FAILED+=("json valid"); echo "not ok - json output is valid JSON"; }

# F10: details arrays
run dirty proj_node --format json
assert_contains "F10 json details vuln entry" '"name": "lodash"'
assert_contains "F10 json details severity" '"severity": "high"'
assert_contains "F10 json details major entry" '"latest": "5.1.0"'

# ─── 2. lockfile deduction ──
t "clean nolock exit 0" 0 run clean proj_nolock --format json
assert_contains "clean nolock score 95" '"score": 95'
assert_contains "clean nolock lockfile false" '"lockfile": false'
run clean proj_node --format json
assert_contains "clean lock score 100" '"score": 100'

# ─── 3. bug: arithmetic zero crash (set -e + ((x -= y)) == 0) ──
t "zero-land exit 0 (crashed pre-fix)" 0 run zero proj_node --format json
assert_contains "zero-land score 0" '"score": 0'

# clamp below zero
t "heavy clamp exit 0" 0 run heavy proj_node --format json
assert_contains "heavy score clamped 0" '"score": 0'

# ─── 4. weird version data ──
t "weird versions exit 0" 0 run weird proj_node --format json
assert_contains "weird: missing skipped, beta → minor" '"outdated_minor": 1'

# ─── 5. bug: local outside function (text output crashed) ──
t "text output exit 0 (crashed pre-fix)" 0 run dirty proj_node
assert_contains "text banner" 'Dependency Health Scan'
assert_contains "text score line" 'Score:   73/100'

# ─── 6. markdown ──
t "markdown exit 0" 0 run dirty proj_node --format markdown
assert_contains "markdown score row" '73/100'
assert_contains "markdown vuln detail" 'high.*lodash'

# ─── 7. F9: csv ──
t "F9 csv exit 0" 0 run dirty proj_node --format csv
assert_contains "csv header" '^metric,value'
assert_contains "csv score" '^score,73'
assert_contains "csv lockfile" '^lockfile,true'

# ─── 8. F7: --min-score gate ──
t "F7 min-score 80 on 73 → exit 1" 1 run dirty proj_node --format json --min-score 80
assert_contains "F7 gate message" 'below threshold 80'
t "F7 min-score 70 on 73 → exit 0" 0 run dirty proj_node --format json --min-score 70

# ─── 9. F8: --fail-on ──
t "F8 fail-on vuln dirty → exit 1" 1 run dirty proj_node --format json --fail-on vuln
assert_contains "F8 vuln msg" 'vulnerability'
t "F8 fail-on vuln clean → exit 0" 0 run clean proj_node --format json --fail-on vuln
t "F8 fail-on major dirty → exit 1" 1 run dirty proj_node --format json --fail-on major
t "F8 fail-on outdated dirty → exit 1" 1 run dirty proj_node --format json --fail-on outdated
assert_contains "F8 outdated msg counts 2" 'outdated package'
t "F8 fail-on outdated clean → exit 0" 0 run clean proj_node --format json --fail-on outdated
t "F8 fail-on bogus → exit 1" 1 env DEPG_FIXTURE=clean "$DEPG" --fail-on wat "$TMP/proj_node" --format json

# ─── 10. --security-only ──
t "security-only exit 0" 0 run dirty proj_node --format json --security-only
assert_contains "security-only score 80" '"score": 80'
grep -q '^npm audit' "$STUB_LOG" && { PASS=$((PASS+1)); echo "ok $PASS - security-only calls audit"; } \
  || { FAIL=$((FAIL+1)); FAILED+=("sec-only audit"); echo "not ok - security-only calls audit"; }
if grep -q '^npm outdated' "$STUB_LOG"; then
  FAIL=$((FAIL+1)); FAILED+=("sec-only no outdated"); echo "not ok - security-only skips outdated"
else
  PASS=$((PASS+1)); echo "ok $PASS - security-only skips outdated"
fi

# ─── 11. python + unknown projects ──
t "python project exit 0" 0 run clean proj_py --format json
assert_contains "python type detected" '"type": "python"'
assert_contains "python req.txt as lockfile" '"lockfile": true'
t "unknown project exit 1" 1 env DEPG_FIXTURE=clean "$DEPG" "$TMP/proj_unknown"
t "missing dir exit 1" 1 env DEPG_FIXTURE=clean "$DEPG" "$TMP/nope-does-not-exist"

echo ""
echo "# tests=$((PASS+FAIL)) pass=$PASS fail=$FAIL"
if [[ $FAIL -gt 0 ]]; then
  printf 'FAILED: %s\n' "${FAILED[@]}"
  exit 1
fi
