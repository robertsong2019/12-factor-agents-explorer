#!/usr/bin/env bash
# dep-guard 🔒 — Dependency health & security scanner
# Supports: Node.js (package.json), Python (requirements.txt)
set -euo pipefail

VERSION="1.1.0"
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# Defaults
FORMAT="text"
SECURITY_ONLY=false
MIN_SCORE=0
FAIL_ON="none"
IGNORE=""
PROJECT_DIR="."

usage() {
  cat <<EOF
dep-guard v${VERSION} — Dependency health & security scanner

Usage: dep-guard.sh [options] [project-dir]

Options:
  --format FORMAT    Output: text, json, csv, markdown (default: text)
  --security-only    Only check for vulnerabilities
  --min-score N      Exit 1 if health score < N (CI mode)
  --fail-on WHAT     Exit 1 if category non-empty: none, vuln, major, outdated
  --ignore A,B,C     Package names to exclude from vuln/outdated counting
  --help             Show this help
  --version          Show version
EOF
  exit 0
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --format)   FORMAT="$2"; shift 2 ;;
    --security-only) SECURITY_ONLY=true; shift ;;
    --min-score) MIN_SCORE="$2"; shift 2 ;;
    --fail-on) FAIL_ON="$2"; shift 2 ;;
    --ignore)  IGNORE="$2"; shift 2 ;;
    --help) usage ;;
    --version) echo "dep-guard v${VERSION}"; exit 0 ;;
    -*) echo "Unknown option: $1"; exit 1 ;;
    *) PROJECT_DIR="$1"; shift ;;
  esac
done

case "$FAIL_ON" in
  none|vuln|major|outdated) ;;
  *) echo "Error: --fail-on must be one of: none, vuln, major, outdated" >&2; exit 1 ;;
esac

cd "$PROJECT_DIR" 2>/dev/null || { echo "Error: cannot access $PROJECT_DIR"; exit 1; }

# ─── Detect project type ────────────────────────────
detect_project() {
  if [[ -f package.json ]]; then echo "node"
  elif [[ -f requirements.txt ]] || [[ -f pyproject.toml ]] || [[ -f Pipfile ]]; then echo "python"
  else echo "unknown"
  fi
}

PROJECT_TYPE=$(detect_project)
if [[ "$PROJECT_TYPE" == "unknown" ]]; then
  echo "Error: No package.json or requirements.txt found in $PROJECT_DIR"
  exit 1
fi

# ─── Data collectors ────────────────────────────────
declare -a VULNS=()
declare -a OUTDATED_MAJOR=()
declare -a OUTDATED_MINOR=()
HAS_LOCKFILE=false

# Append non-empty lines from $2 to array named $1.
# NOTE: parsing must NOT happen in a pipeline subshell — array writes there
# are lost (the v1.0.0 bug that silently zeroed all scan results).
append_lines() {
  local -n __arr=$1
  local __line
  while IFS= read -r __line; do
    if [[ -n "$__line" ]]; then
      __arr+=("$__line")
    fi
  done <<< "$2"
  return 0
}

scan_node() {
  # Lockfile check
  [[ -f package-lock.json || -f yarn.lock || -f pnpm-lock.yaml ]] && HAS_LOCKFILE=true

  # Security audit
  if command -v npm &>/dev/null; then
    local audit_output parsed
    audit_output=$(npm audit --json 2>/dev/null || true)
    if [[ -n "$audit_output" ]]; then
      parsed=$(echo "$audit_output" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for name, info in d.get('vulnerabilities',{}).items():
        severity = info.get('severity','?')
        title = info.get('title','')
        print(f'{severity}|{name}|{title}')
except Exception: pass
" 2>/dev/null || true)
      append_lines VULNS "$parsed"
    fi
  fi

  # Outdated check
  if [[ "$SECURITY_ONLY" == "false" ]] && command -v npm &>/dev/null; then
    local outdated_output parsed_major parsed_minor
    outdated_output=$(npm outdated --json 2>/dev/null || true)
    if [[ -n "$outdated_output" && "$outdated_output" != "{}" ]]; then
      parsed_major=$(echo "$outdated_output" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for name, info in d.items():
        current = info.get('current','?')
        latest = info.get('latest','?')
        if current == 'missing' or latest == 'missing': continue
        try:
            cm = int(current.split('.')[0]); lm = int(latest.split('.')[0])
            if cm != lm: print(f'{name}|{current}|{latest}')
        except ValueError: pass
except Exception: pass
" 2>/dev/null || true)
      parsed_minor=$(echo "$outdated_output" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for name, info in d.items():
        current = info.get('current','?')
        latest = info.get('latest','?')
        if current == 'missing' or latest == 'missing': continue
        try:
            cm = int(current.split('.')[0]); lm = int(latest.split('.')[0])
            if cm == lm: print(f'{name}|{current}|{latest}')
        except ValueError: print(f'{name}|{current}|{latest}')
except Exception: pass
" 2>/dev/null || true)
      append_lines OUTDATED_MAJOR "$parsed_major"
      append_lines OUTDATED_MINOR "$parsed_minor"
    fi
  fi
}

scan_python() {
  [[ -f requirements.txt || -f Pipfile.lock ]] && HAS_LOCKFILE=true

  # pip-audit
  if command -v pip-audit &>/dev/null; then
    local audit parsed
    audit=$(pip-audit --format json 2>/dev/null || true)
    if [[ -n "$audit" ]]; then
      parsed=$(echo "$audit" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for v in d.get('vulnerabilities',[]):
        print(f\"{v.get('severity','?')}|{v.get('package','?')}|{v.get('summary','')}\")
except Exception: pass
" 2>/dev/null || true)
      append_lines VULNS "$parsed"
    fi
  fi

  # Outdated via pip list --outdated
  if [[ "$SECURITY_ONLY" == "false" ]] && command -v pip &>/dev/null; then
    local parsed_major parsed_minor
    parsed_major=$(pip list --outdated --format=json 2>/dev/null | python3 -c "
import sys, json
try:
    for pkg in json.load(sys.stdin):
        name = pkg.get('name','?'); ver = pkg.get('version','?'); latest = pkg.get('latest_version','?')
        try:
            cm = int(ver.split('.')[0]); lm = int(latest.split('.')[0])
            if cm != lm: print(f'{name}|{ver}|{latest}')
        except ValueError: pass
except Exception: pass
" 2>/dev/null || true)
    parsed_minor=$(pip list --outdated --format=json 2>/dev/null | python3 -c "
import sys, json
try:
    for pkg in json.load(sys.stdin):
        name = pkg.get('name','?'); ver = pkg.get('version','?'); latest = pkg.get('latest_version','?')
        try:
            cm = int(ver.split('.')[0]); lm = int(latest.split('.')[0])
            if cm == lm: print(f'{name}|{ver}|{latest}')
        except ValueError: print(f'{name}|{ver}|{latest}')
except Exception: pass
" 2>/dev/null || true)
    append_lines OUTDATED_MAJOR "$parsed_major"
    append_lines OUTDATED_MINOR "$parsed_minor"
  fi
}

# Split ignore list into array
declare -a IGNORES=()
if [[ -n "$IGNORE" ]]; then
  IFS=',' read -ra IGNORES <<< "$IGNORE"
fi

# ─── Run scan ────────────────────────────────────────
if [[ "$PROJECT_TYPE" == "node" ]]; then scan_node; else scan_python; fi

# ─── Apply --ignore (name field: vulns=1, outdated=0) ──
filter_ignored() {
  local -n __src=$1
  local __field=$2 __line __keep __ig
  local -a __out=()
  if [[ ${#IGNORES[@]} -eq 0 ]]; then return 0; fi
  for __line in "${__src[@]}"; do
    __keep=true
    for __ig in "${IGNORES[@]}"; do
      if [[ "$(cut -d'|' -f$((__field+1)) <<< "$__line")" == "$__ig" ]]; then __keep=false; fi
    done
    if [[ "$__keep" == "true" ]]; then __out+=("$__line"); fi
  done
  __src=("${__out[@]}")
  return 0
}
filter_ignored VULNS 1
filter_ignored OUTDATED_MAJOR 0
filter_ignored OUTDATED_MINOR 0

# ─── Calculate score ────────────────────────────────
# Per-item deduction (NOT the weighted-average table in the old README):
#   high/critical vuln -15, low/moderate vuln -5, major outdated -5,
#   minor outdated -2, missing lockfile -5. Clamped to [0,100].
VULN_COUNT=${#VULNS[@]}
MAJOR_COUNT=${#OUTDATED_MAJOR[@]}
MINOR_COUNT=${#OUTDATED_MINOR[@]}

SCORE=100
for v in "${VULNS[@]}"; do
  IFS='|' read -r sev _ _ <<< "$v"
  if [[ "$sev" == "high" || "$sev" == "critical" ]]; then
    SCORE=$((SCORE - 15))
  else
    SCORE=$((SCORE - 5))
  fi
done
SCORE=$((SCORE - MAJOR_COUNT * 5))
SCORE=$((SCORE - MINOR_COUNT * 2))
[[ "$HAS_LOCKFILE" == "false" ]] && SCORE=$((SCORE - 5))

(( SCORE < 0 )) && SCORE=0
(( SCORE > 100 )) && SCORE=100

# ─── Output ──────────────────────────────────────────
score_emoji() {
  if (( SCORE >= 80 )); then echo "✅"
  elif (( SCORE >= 60 )); then echo "⚠️"
  else echo "🔴"
  fi
}

VULNS_STR=""
MAJOR_STR=""
MINOR_STR=""
if (( VULN_COUNT > 0 ));   then VULNS_STR=$(printf '%s\n' "${VULNS[@]}"); fi
if (( MAJOR_COUNT > 0 )); then MAJOR_STR=$(printf '%s\n' "${OUTDATED_MAJOR[@]}"); fi
if (( MINOR_COUNT > 0 )); then MINOR_STR=$(printf '%s\n' "${OUTDATED_MINOR[@]}"); fi

if [[ "$FORMAT" == "json" ]]; then
  DEPG_PROJECT="$PROJECT_DIR" DEPG_TYPE="$PROJECT_TYPE" DEPG_SCORE="$SCORE" \
  DEPG_VULN_COUNT="$VULN_COUNT" DEPG_MAJOR_COUNT="$MAJOR_COUNT" DEPG_MINOR_COUNT="$MINOR_COUNT" \
  DEPG_LOCKFILE="$HAS_LOCKFILE" DEPG_VULNS="$VULNS_STR" DEPG_MAJOR="$MAJOR_STR" DEPG_MINOR="$MINOR_STR" \
  python3 -c "
import json, os
def triples(s):
    out = []
    for line in (s or '').splitlines():
        p = line.split('|', 2)
        if len(p) == 3:
            out.append({'name': p[0], 'current': p[1], 'latest': p[2]})
    return out
print(json.dumps({
    'project': os.environ['DEPG_PROJECT'],
    'type': os.environ['DEPG_TYPE'],
    'score': int(os.environ['DEPG_SCORE']),
    'vulnerabilities': int(os.environ['DEPG_VULN_COUNT']),
    'outdated_major': int(os.environ['DEPG_MAJOR_COUNT']),
    'outdated_minor': int(os.environ['DEPG_MINOR_COUNT']),
    'lockfile': os.environ['DEPG_LOCKFILE'] == 'true',
    'details': {
        'vulnerabilities': [
            dict(zip(('severity','name','title'), l.split('|', 2)))
            for l in (os.environ['DEPG_VULNS'] or '').splitlines() if l
        ],
        'outdated_major': triples(os.environ['DEPG_MAJOR']),
        'outdated_minor': triples(os.environ['DEPG_MINOR']),
    },
}, indent=2))
"

elif [[ "$FORMAT" == "csv" ]]; then
  echo "metric,value"
  echo "project,$PROJECT_DIR"
  echo "type,$PROJECT_TYPE"
  echo "score,$SCORE"
  echo "vulnerabilities,$VULN_COUNT"
  echo "outdated_major,$MAJOR_COUNT"
  echo "outdated_minor,$MINOR_COUNT"
  echo "lockfile,$HAS_LOCKFILE"

elif [[ "$FORMAT" == "markdown" ]]; then
  echo "# dep-guard Report"
  echo ""
  echo "| Metric | Value |"
  echo "|--------|-------|"
  echo "| Project | \`${PROJECT_DIR}\` |"
  echo "| Type | ${PROJECT_TYPE} |"
  echo "| **Score** | **${SCORE}/100 $(score_emoji)** |"
  echo "| Vulnerabilities | ${VULN_COUNT} |"
  echo "| Outdated (major) | ${MAJOR_COUNT} |"
  echo "| Outdated (minor) | ${MINOR_COUNT} |"
  echo "| Lockfile | $( $HAS_LOCKFILE && echo '✓' || echo '✗' ) |"
  echo ""
  if (( VULN_COUNT > 0 )); then
    echo "## Vulnerabilities"
    for v in "${VULNS[@]}"; do
      IFS='|' read -r sev name title <<< "$v"
      echo "- **[${sev}]** ${name}: ${title}"
    done
    echo ""
  fi
  if (( MAJOR_COUNT > 0 )); then
    echo "## Outdated (Major)"
    for o in "${OUTDATED_MAJOR[@]}"; do
      IFS='|' read -r name cur lat <<< "$o"
      echo "- **${name}** ${cur} → ${lat}"
    done
    echo ""
  fi

else
  # Text (default)
  echo ""
  echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
  echo -e "${CYAN}║${NC}  ${BOLD}dep-guard${NC} · Dependency Health Scan   ${CYAN}║${NC}"
  echo -e "${CYAN}╠══════════════════════════════════════╣${NC}"
  echo -e "${CYAN}║${NC}  Project: $(basename "$PROJECT_DIR")$(printf '%*s' $((26 - ${#PROJECT_DIR})) '')  ${CYAN}║${NC}"
  echo -e "${CYAN}║${NC}  Type:    ${PROJECT_TYPE}$(printf '%*s' $((27 - ${#PROJECT_TYPE})) '')  ${CYAN}║${NC}"
  printf "${CYAN}║${NC}  ${BOLD}Score:   ${SCORE}/100 $(score_emoji)${NC}\n"
  echo -e "${CYAN}╠══════════════════════════════════════╣${NC}"
  echo -e "${CYAN}║${NC}                                      ${CYAN}║${NC}"

  # Vulnerabilities
  if (( VULN_COUNT == 0 )); then
    echo -e "${CYAN}║${NC}  🔒 Security: ${GREEN}0 issues${NC}               ${CYAN}║${NC}"
  else
    echo -e "${CYAN}║${NC}  🔒 Security: ${RED}${VULN_COUNT} issue(s)${NC}           ${CYAN}║${NC}"
    for v in "${VULNS[@]}"; do
      IFS='|' read -r sev name title <<< "$v"
      echo -e "${CYAN}║${NC}    ${RED}[${sev}]${NC} ${name}: ${title:0:25}  ${CYAN}║${NC}"
    done
  fi

  # Outdated
  if [[ "$SECURITY_ONLY" == "false" ]]; then
    total_out=$((MAJOR_COUNT + MINOR_COUNT))
    if (( total_out == 0 )); then
      echo -e "${CYAN}║${NC}  📦 Outdated: ${GREEN}0 packages${NC}           ${CYAN}║${NC}"
    else
      echo -e "${CYAN}║${NC}  📦 Outdated: ${YELLOW}${total_out} package(s)${NC}         ${CYAN}║${NC}"
      for o in "${OUTDATED_MAJOR[@]}"; do
        IFS='|' read -r name cur lat <<< "$o"
        echo -e "${CYAN}║${NC}    ${YELLOW}•${NC} ${name} ${cur} → ${lat} (major)  ${CYAN}║${NC}"
      done
      for o in "${OUTDATED_MINOR[@]}"; do
        IFS='|' read -r name cur lat <<< "$o"
        echo -e "${CYAN}║${NC}    ${DIM}•${NC} ${name} ${cur} → ${lat}  ${CYAN}║${NC}"
      done
    fi
  fi

  # Lockfile
  if $HAS_LOCKFILE; then
    echo -e "${CYAN}║${NC}  🔐 Lockfile: ${GREEN}present ✓${NC}            ${CYAN}║${NC}"
  else
    echo -e "${CYAN}║${NC}  🔐 Lockfile: ${YELLOW}missing ✗${NC}           ${CYAN}║${NC}"
  fi

  echo -e "${CYAN}║${NC}                                      ${CYAN}║${NC}"
  echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
  echo ""
fi

# ─── CI gates ────────────────────────────────────────
GATE_MSG=""
if (( MIN_SCORE > 0 && SCORE < MIN_SCORE )); then
  GATE_MSG="❌ Health score ${SCORE} is below threshold ${MIN_SCORE}"
elif [[ "$FAIL_ON" != "none" ]]; then
  case "$FAIL_ON" in
    vuln)     (( VULN_COUNT > 0 )) && GATE_MSG="❌ --fail-on vuln: ${VULN_COUNT} vulnerability(ies) found" ;;
    major)    (( MAJOR_COUNT > 0 )) && GATE_MSG="❌ --fail-on major: ${MAJOR_COUNT} major outdated package(s)" ;;
    outdated) (( MAJOR_COUNT + MINOR_COUNT > 0 )) && GATE_MSG="❌ --fail-on outdated: $((MAJOR_COUNT + MINOR_COUNT)) outdated package(s)" ;;
  esac
fi
if [[ -n "$GATE_MSG" ]]; then
  echo "$GATE_MSG"
  exit 1
fi
