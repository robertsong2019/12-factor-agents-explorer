#!/usr/bin/env bash
# ptm - Prompt Template Manager
# Store, version, render, and compose AI prompt templates

set -euo pipefail

PTM_DIR="${PTM_DIR:-$HOME/.ptm}"
TEMPLATES_DIR="$PTM_DIR/templates"
VERSIONS_DIR="$PTM_DIR/versions"

_init() {
  mkdir -p "$TEMPLATES_DIR" "$VERSIONS_DIR"
}

_get_template_file() {
  echo "$TEMPLATES_DIR/$1.json"
}

_get_version_dir() {
  echo "$VERSIONS_DIR/$1"
}

_now() {
  date -u +'%Y-%m-%dT%H:%M:%SZ'
}

cmd_add() {
  local name="$1"
  local template_text
  if [[ -t 0 ]]; then
    template_text="${2:-}"
    shift 2
  else
    # template comes from stdin; remaining args are tags/model/temp
    template_text="$(cat)"
    shift 1
  fi
  if [[ -z "$template_text" ]]; then
    echo "❌ Empty template. Usage: ptm add <name> <template> (or pipe template via stdin)" >&2; exit 1
  fi
  
  local tags="${1:-}"
  local model="${2:-default}"
  local temperature="${3:-}"
  
  local file
  file="$(_get_template_file "$name")"
  
  # Save version history if template already exists
  if [[ -f "$file" ]]; then
    local vdir
    vdir="$(_get_version_dir "$name")"
    mkdir -p "$vdir"
    local ts
    ts=$(_now)
    ts="${ts//:/_}"
    cp "$file" "$vdir/${ts}.json"
  fi
  
  # Extract variables from template
  local vars
  vars=$(echo "$template_text" | grep -oP '\{\{\K[^}]+(?=\}\})' | sort -u | tr '\n' ',' | sed 's/,$//')
  
  cat > "$file" << ENDJSON
{
  "name": "$name",
  "template": $(echo "$template_text" | jq -Rs .),
  "variables": $(echo "$vars" | jq -R 'split(",") | map(select(length>0))'),
  "model": "$model",
  "temperature": ${temperature:-null},
  "tags": $(echo "$tags" | jq -R 'split(",") | map(select(length>0))'),
  "updated": "$(_now)"
}
ENDJSON
  
  echo "✅ Template '$name' saved ($(_get_template_file "$name"))"
}

cmd_get() {
  local name="$1"
  local file
  file="$(_get_template_file "$name")"
  if [[ ! -f "$file" ]]; then
    echo "❌ Template '$name' not found" >&2; exit 1
  fi
  jq '.' "$file"
}

cmd_list() {
  local tag_filter="${1:-}"
  # help documents 'list --tag <tag>'; accept both forms
  if [[ "$tag_filter" == "--tag" ]]; then
    tag_filter="${2:-}"
  fi
  if [[ -z "$(ls -A "$TEMPLATES_DIR" 2>/dev/null)" ]]; then
    echo "No templates yet. Use 'ptm add' to create one."
    return
  fi
  for f in "$TEMPLATES_DIR"/*.json; do
    if [[ -n "$tag_filter" ]]; then
      local has_tag
      has_tag=$(jq -r --arg t "$tag_filter" '.tags // [] | map(select(. == $t)) | length' "$f")
      [[ "$has_tag" == "0" ]] && continue
    fi
    local name model vars
    name=$(jq -r '.name' "$f")
    model=$(jq -r '.model // "default"' "$f")
    vars=$(jq -r '(.variables // []) | join(", ")' "$f")
    printf "  %-25s model=%-10s vars=[%s]\n" "$name" "$model" "$vars"
  done
}

cmd_render() {
  local name="$1"
  shift
  local file
  file="$(_get_template_file "$name")"
  if [[ ! -f "$file" ]]; then
    echo "❌ Template '$name' not found" >&2; exit 1
  fi
  
  local template
  template=$(jq -r '.template' "$file")
  
  # Parse -k key=val arguments. Index-based walk: mixing shift with
  # 'for arg in "$@"' desyncs and silently drops later vars.
  local _args=("$@")
  local i=0
  while (( i < ${#_args[@]} )); do
    local arg="${_args[i]}"
    if [[ "$arg" == -k=* ]]; then
      local kv="${arg#-k=}"
      local key="${kv%%=*}"
      local val="${kv#*=}"
      template="${template//\{\{${key}\}\}/${val}}"
    elif [[ "$arg" == "-k" ]] && (( i+1 < ${#_args[@]} )); then
      local kv="${_args[i+1]}"
      local key="${kv%%=*}"
      local val="${kv#*=}"
      template="${template//\{\{${key}\}\}/${val}}"
      i=$((i+1))
    fi
    i=$((i+1))
  done
  
  # Check for unfilled variables
  local unfilled
  unfilled=$(echo "$template" | grep -oP '\{\{[^}]+\}\}' || true)
  if [[ -n "$unfilled" ]]; then
    echo "⚠️  Unfilled variables:" >&2
    echo "$unfilled" >&2
    echo "---" >&2
  fi
  
  echo "$template"
}

cmd_compose() {
  local result=""
  for name in "$@"; do
    local file
    file="$(_get_template_file "$name")"
    if [[ ! -f "$file" ]]; then
      echo "❌ Template '$name' not found" >&2; exit 1
    fi
    local section
    section=$(jq -r '.template' "$file")
    result="${result}${section}"
    [[ $# -gt 1 ]] && result="${result}\n\n---\n\n"
  done
  echo -e "$result"
}

cmd_history() {
  local name="$1"
  local vdir
  vdir="$(_get_version_dir "$name")"
  if [[ ! -d "$vdir" ]] || [[ -z "$(ls -A "$vdir")" ]]; then
    echo "No version history for '$name'"
    return
  fi
  echo "Version history for '$name':"
  for f in "$vdir"/*.json; do
    local ts
    ts=$(basename "$f" .json | sed 's/_/:/g')
    local preview
    preview=$(jq -r '.template' "$f" | head -1 | cut -c1-60)
    echo "  $ts  →  $preview..."
  done
}

cmd_export() {
  local out="${1:-ptm-export.json}"
  jq -s '.' "$TEMPLATES_DIR"/*.json > "$out" 2>/dev/null || echo '[]' > "$out"
  echo "✅ Exported to $out"
}

cmd_import() {
  local file="$1"
  local count=0
  for name in $(jq -r '.[].name' "$file"); do
    local idx=$(jq -r "to_entries[] | select(.value.name==\"$name\") | .key" "$file")
    jq ".[$idx]" "$file" > "$(_get_template_file "$name")"
    count=$((count + 1))
  done
  echo "✅ Imported $count templates"
}

cmd_diff() {
  local name="$1"
  local vdir="$(_get_version_dir "$name")"
  local current="$(_get_template_file "$name")"
  if [[ ! -d "$vdir" ]]; then
    echo "No history to diff"; return
  fi
  local latest
  latest=$(ls -t "$vdir"/*.json | head -1)
  diff <(jq -r '.template' "$latest") <(jq -r '.template' "$current") || true
}

# Main
_init

case "${1:-help}" in
  add)      shift; cmd_add "$@" ;;
  get)      shift; cmd_get "$@" ;;
  list|ls)  shift; cmd_list "$@" ;;
  render|r) shift; cmd_render "$@" ;;
  compose)  shift; cmd_compose "$@" ;;
  history)  shift; cmd_history "$@" ;;
  export)   shift; cmd_export "$@" ;;
  import)   shift; cmd_import "$@" ;;
  diff)     shift; cmd_diff "$@" ;;
  help|--help|-h)
    echo "ptm - Prompt Template Manager"
    echo ""
    echo "Commands:"
    echo "  add <name> <template> [tags] [model] [temp]  Add/update template"
    echo "  get <name>                                    View template"
    echo "  list [--tag <tag>]                            List templates"
    echo "  render <name> -k key=val ...                  Render with vars"
    echo "  compose <name1> <name2> ...                   Compose templates"
    echo "  history <name>                                Version history"
    echo "  diff <name>                                   Diff with last version"
    echo "  export [file]                                 Export as JSON"
    echo "  import <file>                                 Import from JSON"
    ;;
  *) echo "Unknown command: $1. Run 'ptm help'." >&2; exit 1 ;;
esac
