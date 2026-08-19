#!/usr/bin/env bash
# ptm (bash) hermetic test suite — PTM_DIR overrides store, jq required.
# Run: bash test/run.sh   (from tools/prompt-manager)
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PTM="$SCRIPT_DIR/ptm.sh"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export PTM_DIR="$TMP/store"

PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "  ok $PASS - $1"; }
fail() { FAIL=$((FAIL+1)); echo "  not ok $FAIL - $1"; }
check() { # check <desc> <expected> <actual>
  if [[ "$2" == "$3" ]]; then ok "$1"; else fail "$1 (expected: $(printf %q "$2"), got: $(printf %q "$3"))"; fi
}
check_match() { # check_match <desc> <regex> <actual>
  if [[ "$3" =~ $2 ]]; then ok "$1"; else fail "$1 (pattern $2, got: $(printf %q "$3"))"; fi
}

echo "TAP-ish output for ptm.sh"

# ─── add + get ───────────────────────────────────────

OUT=$(echo 'Review {{language}} code' | bash "$PTM" add review "code,review" default 2>/dev/null)
check_match "add reports saved" 'Template .review. saved' "$OUT"
[[ -f "$PTM_DIR/templates/review.json" ]] && ok "add writes json file" || fail "add writes json file"

GOT=$(bash "$PTM" get review | jq -r '.name')
check "get returns template json" "review" "$GOT"

GOT=$(bash "$PTM" get review | jq -r '.template')
check "get preserves template text" "Review {{language}} code" "$GOT"

VARS=$(bash "$PTM" get review | jq -c '.variables')
check "add extracts variables" '["language"]' "$VARS"

TAGS=$(bash "$PTM" get review | jq -c '.tags')
check "add stores tags" '["code","review"]' "$TAGS"

GOT=$(bash "$PTM" get missing 2>/dev/null; echo "exit=$?")
check "get missing exits 1" "exit=1" "$GOT"

# stdin add via pipe (non-tty path)
echo 'Hello {{who}}' | bash "$PTM" add greet >/dev/null
GOT=$(bash "$PTM" get greet | jq -r '.template')
check "add reads template from pipe" "Hello {{who}}" "$GOT"

# ─── list ────────────────────────────────────────────

GOT=$(bash "$PTM" list)
check_match "list shows names" 'review' "$GOT"
check_match "list shows other name" 'greet' "$GOT"
check_match "list shows vars" 'language' "$GOT"

GOT=$(bash "$PTM" list review | grep -c review)
check "list filters by bare tag" "1" "$GOT"
GOT=$(bash "$PTM" list review | grep -c greet)
check "list bare-tag filter excludes others" "0" "$GOT"

# help-documented form: list --tag <tag>
GOT=$(bash "$PTM" list --tag review | grep -c '^  review')
check "list --tag filters (as documented in help)" "1" "$GOT"

# ─── render ──────────────────────────────────────────

GOT=$(bash "$PTM" render review -k language=python)
check "render -k= substitutes" "Review python code" "$GOT"

GOT=$(bash "$PTM" render review -k language=python 2>/dev/null)
check "render filled emits no warning" "0" "$(grep -c 'Unfilled' <<<"$GOT")"

echo 'Hi {{a}} {{b}}' | bash "$PTM" add two >/dev/null
GOT=$(bash "$PTM" render two -k=a=1 -k=b=2)
check "render multiple -k= vars" "Hi 1 2" "$GOT"

GOT=$(bash "$PTM" render two -k a=1 -k b=2 2>/dev/null)
check "render separate -k form, multiple vars" "Hi 1 2" "$GOT"

GOT=$(bash "$PTM" render two -k a=1 2>&1 >/dev/null)
check_match "render unfilled var warns on stderr" 'Unfilled' "$GOT"

GOT=$(bash "$PTM" render missing 2>/dev/null; echo "exit=$?")
check "render missing exits 1" "exit=1" "$GOT"

# ─── versioning ──────────────────────────────────────

echo 'v2 text {{x}}' | bash "$PTM" add review >/dev/null
GOT=$(ls "$PTM_DIR/versions/review"/*.json 2>/dev/null | wc -l)
check "re-add snapshots previous version" "1" "$GOT"

GOT=$(bash "$PTM" diff review)
check_match "diff shows change" 'v2 text' "$GOT"

GOT=$(bash "$PTM" history review)
check_match "history lists snapshot" 'Version history' "$GOT"

GOT=$(bash "$PTM" history nohist)
check_match "history without snapshots says none" 'No version history' "$GOT"

# ─── compose ─────────────────────────────────────────

GOT=$(bash "$PTM" compose review two | head -1)
check "compose concatenates first template" "v2 text {{x}}" "$GOT"
GOT=$(bash "$PTM" compose review two | grep -c '^v2 text\|^Hi')
check "compose includes all templates" "2" "$GOT"

# ─── export / import roundtrip ───────────────────────

bash "$PTM" export "$TMP/export.json" >/dev/null
GOT=$(jq 'length' "$TMP/export.json")
check "export contains all templates" "3" "$GOT"

rm -rf "$PTM_DIR/templates"
bash "$PTM" import "$TMP/export.json" >/dev/null
GOT=$(bash "$PTM" get review | jq -r '.name')
check "import roundtrip restores template" "review" "$GOT"

# ─── unknown command ─────────────────────────────────

GOT=$(bash "$PTM" bogus 2>/dev/null; echo "exit=$?")
check "unknown command exits 1" "exit=1" "$GOT"

echo
echo "# pass $PASS / $((PASS+FAIL))"
[[ $FAIL -eq 0 ]] && echo "ALL PASS" || echo "FAILURES: $FAIL"
exit $((FAIL > 0))
