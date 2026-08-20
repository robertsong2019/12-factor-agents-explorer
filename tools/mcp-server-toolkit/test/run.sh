#!/usr/bin/env bash
# Hermetic test suite for mcp-server-toolkit (mcpt CLI)
# Runs in a mktemp sandbox; no network, no HOME pollution.
set -u
TOOL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MCPT="node $TOOL_DIR/bin/mcpt.js"
PASS=0; FAIL=0; FAILED=()

t() { # t <name> <expected_rc> <cmd...>  — runs cmd, compares rc, stdout captured in $OUT
  local name="$1" want_rc="$2"; shift 2
  local rc
  OUT="$(cd "$WORK" && "$@" 2>&1)"; rc=$?
  if [ "$rc" -eq "$want_rc" ]; then PASS=$((PASS+1));
  else FAIL=$((FAIL+1)); FAILED+=("$name (rc=$rc want=$want_rc)"); echo "FAIL: $name rc=$rc want=$want_rc"; echo "$OUT" | head -5; fi
}
assert_out() { # assert_out <name> <pattern>
  local name="$1" pat="$2"
  if printf '%s' "$OUT" | grep -q "$pat"; then PASS=$((PASS+1));
  else FAIL=$((FAIL+1)); FAILED+=("$name"); echo "FAIL: $name — pattern not found: $pat"; fi
}
assert_file() {
  local name="$1" f="$2"
  if [ -e "$WORK/$2" ]; then PASS=$((PASS+1));
  else FAIL=$((FAIL+1)); FAILED+=("$name"); echo "FAIL: $name — missing $f"; fi
}

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# --- CLI loads at all (missing command modules / syntax errors fail here) ---
t "help-exit0" 0 $MCPT --help
assert_out "help-lists-commands" "init"
assert_out "help-lists-validate" "validate"
t "noarg-shows-help" 0 $MCPT
assert_out "noarg-help-text" "Usage"
t "version" 0 $MCPT --version
assert_out "version-string" "1\.0\.0"

# --- init happy path ---
t "init-creates-project" 0 $MCPT init demo-server -d "my test server"
assert_file "init-dir-package" "demo-server/package.json"
assert_file "init-dir-tsconfig" "demo-server/tsconfig.json"
assert_file "init-dir-mcp-config" "demo-server/mcp-server.json"
assert_file "init-dir-src" "demo-server/src/index.ts"
assert_file "init-dir-readme" "demo-server/README.md"
assert_file "init-dir-gitignore" "demo-server/.gitignore"
assert_file "init-dir-examples" "demo-server/examples"

OUT="$(cat "$WORK/demo-server/package.json")"
assert_out "pkg-name" '"name": "demo-server"'
assert_out "pkg-description" '"description": "my test server"'
assert_out "pkg-bin" '"demo-server": "./dist/index.js"'

OUT="$(cat "$WORK/demo-server/mcp-server.json")"
assert_out "mcp-config-name" '"name": "demo-server"'
assert_out "mcp-config-transport-default" '"transport": "stdio"'

OUT="$(cat "$WORK/demo-server/src/index.ts")"
assert_out "src-server-name" "'demo-server'"

# --- init with -t sse records transport in config ---
t "init-sse-rc0" 0 $MCPT init sse-server -t sse
OUT="$(cat "$WORK/sse-server/mcp-server.json")"
assert_out "mcp-config-transport-sse" '"transport": "sse"'

# --- init into existing dir fails ---
mkdir -p "$WORK/taken"
t "init-existing-dir-fails" 1 $MCPT init taken
assert_out "init-existing-msg" "已存在"

# --- invalid name rejected (consistency with inquirer validate) ---
t "init-invalid-name-fails" 1 $MCPT init Bad_Name
assert_out "init-invalid-msg" "小写字母"

# --- CLI 提供名称时可用 --example 生成示例代码（与交互式路径对等） ---
t "init-example-rc0" 0 $MCPT init demo-ex -e
OUT="$(cat "$WORK/demo-ex/src/index.ts")"
assert_out "example-has-echo-tool" "echo"
OUT="$(cat "$WORK/demo-server/src/index.ts")"
if printf '%s' "$OUT" | grep -q '示例工具'; then FAIL=$((FAIL+1)); FAILED+=("default-no-example"); echo "FAIL: default-no-example"; else PASS=$((PASS+1)); fi

# --- stub commands are honest placeholders (module exists, exit 1) ---
t "validate-stub" 1 $MCPT validate
assert_out "validate-stub-msg" "尚未实现"
t "generate-stub" 1 $MCPT generate
assert_out "generate-stub-msg" "尚未实现"
t "test-cmd-stub" 1 $MCPT test
assert_out "test-stub-msg" "尚未实现"
t "serve-stub" 1 $MCPT serve
assert_out "serve-stub-msg" "尚未实现"

echo
echo "PASS=$PASS FAIL=$FAIL"
[ $FAIL -eq 0 ] && echo "OK: all green" || { printf 'failed: %s\n' "${FAILED[@]}"; exit 1; }
