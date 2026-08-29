#!/usr/bin/env bash
# agent-log — Search, filter, and summarize OpenClaw session logs
# Zero dependencies. Works with standard OpenClaw directory layout.

set -euo pipefail

WORKSPACE="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}"
MEMORY_DIR="$WORKSPACE/memory"
SESSIONS_DIR="$HOME/.openclaw/sessions"
HEARTBEAT_STATE="$MEMORY_DIR/heartbeat-state.json"

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; GRAY='\033[0;90m'; RESET='\033[0m'

# F20: pipe-safe output — suppress ANSI colors when stdout is not a TTY or NO_COLOR is set
if [[ ! -t 1 ]] || [[ -n "${NO_COLOR:-}" ]]; then
  RED=''; GREEN=''; YELLOW=''; BLUE=''; CYAN=''; GRAY=''; RESET=''
fi

# Global JSON flag
JSON_OUTPUT=0

die() { echo -e "${RED}Error:${RESET} $*" >&2; exit 1; }

# ── Helper: escape a string for embedding in JSON output ──
esc_json() {
  local s="$1"
  s="${s//\\\\/\\\\\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/\\n}"
  s="${s//$'\t'/\\t}"
  s="${s//$'\r'/}"
  printf '%s' "$s"
}

# ── Helper: build JSON result for search ──
build_search_json() {
  local query="$1" stype="$2"
  shift 2
  local items=("$@")
  local count=${#items[@]}
  printf '{"command":"search","query":"%s","type":"%s","file_count":%d,"results":[%s]}\n' \
    "$(esc_json "$query")" "$stype" "$count" "$(IFS=,; echo "${items[*]+${items[*]}}")"
}

# ── Commands ──

cmd_search() {
  local use_regex=0 query="" output_file="" date_from="" date_to="" count_only=0 context=1

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -r|--regex) use_regex=1 ;;
      -o|--output) shift; output_file="${1:-}" ;;
      -j|--json) JSON_OUTPUT=1 ;;
      --count) count_only=1 ;;
      -C|--context) shift; context="${1:-}" ;;
      --from) shift; date_from="${1:-}" ;;
      --to) shift; date_to="${1:-}" ;;
      *) query="$1" ;;
    esac
    shift
  done

  [[ -z "$query" ]] && die "Usage: agent-log search [-r|--regex] [-o file] [-j|--json] [--from DATE] [--to DATE] [--count] [-C N|--context N] <query>"

  # Validate date formats
  local date_re='^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
  [[ -n "$date_from" ]] && ! [[ "$date_from" =~ $date_re ]] && die "--from requires YYYY-MM-DD format, got: $date_from"
  [[ -n "$date_to" ]] && ! [[ "$date_to" =~ $date_re ]] && die "--to requires YYYY-MM-DD format, got: $date_to"
  [[ "$context" =~ ^[0-9]+$ ]] || die "-C/--context requires a non-negative integer, got: $context"

  local files=()
  while IFS= read -r -d '' f; do files+=("$f"); done < <(
    find "$MEMORY_DIR" -name '*.md' -print0 2>/dev/null
    find "$WORKSPACE" -maxdepth 1 -name '*.md' -print0 2>/dev/null
    find "$SESSIONS_DIR" -name '*.md' -print0 2>/dev/null
  )

  # Filter by date range (only applies to files with dates in their path/name)
  if [[ -n "$date_from" ]] || [[ -n "$date_to" ]]; then
    local filtered=()
    for f in "${files[@]}"; do
      local basename; basename=$(basename "$f" .md)
      if [[ "$basename" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
        [[ -n "$date_from" ]] && [[ "$basename" < "$date_from" ]] && continue
        [[ -n "$date_to" ]] && [[ "$basename" > "$date_to" ]] && continue
      fi
      filtered+=("$f")
    done
    files=("${filtered[@]}")
  fi
  [[ ${#files[@]} -eq 0 ]] && die "No log files found. Check WORKSPACE=$WORKSPACE"

  local search_type="text"
  [[ $use_regex -eq 1 ]] && search_type="regex"

  local grep_opts=(--include='*.md' -i)
  [[ $use_regex -eq 1 ]] && grep_opts+=(-E)

  local json_results=()
  local plain_output=""
  local grep_color=()
  [[ -t 1 && -z "${NO_COLOR:-}" ]] && grep_color=(--color=always)

  local found_files
  found_files=$(grep -rl "${grep_opts[@]}" "$query" "${files[@]}" 2>/dev/null || true)

  local rank_rows=()
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    local rel="${f#$HOME/}"
    if [[ $count_only -eq 1 ]]; then
      local matches
      matches=$(grep "${grep_opts[@]}" -c "$query" "$f" 2>/dev/null || echo 0)
      rank_rows+=("$matches"$'\t'"$rel")
    elif [[ $JSON_OUTPUT -eq 1 ]]; then
      local matches
      matches=$(grep "${grep_opts[@]}" -c "$query" "$f" 2>/dev/null || echo 0)
      # Escape special chars in filename for JSON
      local esc_rel="${rel//\"/\\\"}"
      json_results+=("{\"file\":\"$esc_rel\",\"matches\":$matches}")
    else
      plain_output+="$(echo -e "${BLUE}$rel${RESET}")"$'\n'
      plain_output+="$(grep "${grep_color[@]}" "${grep_opts[@]}" -n -C "$context" "$query" "$f" 2>/dev/null | head -20 | sed 's/^/  /' || true)"$'\n\n'
    fi
  done <<< "$found_files"

  # F19: --count — ranked per-file match counts, sorted descending
  if [[ $count_only -eq 1 ]]; then
    if [[ ${#rank_rows[@]} -eq 0 ]]; then
      echo "No matches."
      return
    fi
    if [[ $JSON_OUTPUT -eq 1 ]]; then
      local sorted_json=() m rel_row
      while IFS=$'\t' read -r m rel_row; do
        sorted_json+=("{\"file\":\"${rel_row//\"/\\\"}\",\"matches\":$m}")
      done < <(printf '%s\n' "${rank_rows[@]}" | sort -rn)
      build_search_json "$query" "$search_type" "${sorted_json[@]+${sorted_json[@]}}"
    else
      echo -e "${CYAN}Match counts ($search_type):${RESET} $query"
      echo -e "${GRAY}(${#files[@]} files scanned)${RESET}"
      echo
      printf '%s\n' "${rank_rows[@]}" | sort -rn | awk -F'\t' '{printf "  %5d  %s\n", $1, $2}'
    fi
    if [[ -n "$output_file" ]]; then
      {
        echo "# Match counts for: $query"
        echo "# Type: $search_type"
        echo "# Generated: $(date -Iseconds)"
        echo ""
        printf '%s\n' "${rank_rows[@]}" | sort -rn | awk -F'\t' '{printf "%6d  %s\n", $1, $2}'
      } > "$output_file"
      echo -e "${GREEN}Results exported to: $output_file${RESET}"
    fi
    return
  fi

  if [[ $JSON_OUTPUT -eq 1 ]]; then
    build_search_json "$query" "$search_type" "${json_results[@]+${json_results[@]}}"
  else
    echo -e "${CYAN}Searching for ($search_type):${RESET} $query"
    echo -e "${GRAY}(${#files[@]} files)${RESET}"
    echo
    echo -n "$plain_output"
  fi

  # Export to file
  if [[ -n "$output_file" ]]; then
    {
      echo "# Search results for: $query"
      echo "# Type: $search_type"
      echo "# Generated: $(date -Iseconds)"
      echo ""
      if [[ -n "$found_files" ]]; then
        while IFS= read -r f; do
          [[ -z "$f" ]] && continue
          echo "== ${f#$HOME/} =="
          grep "${grep_opts[@]}" -n -C "$context" "$query" "$f" 2>/dev/null | head -20
          echo ""
        done <<< "$found_files"
      fi
    } > "$output_file"
    echo -e "${GREEN}Results exported to: $output_file${RESET}"
  fi
}

cmd_hot() {
  # F23: top-K most frequent terms across memory logs in a date window.
  local top_n=10 date_from="" date_to=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -n|--top) shift; top_n="${1:-}" ;;
      -j|--json) JSON_OUTPUT=1 ;;
      --from) shift; date_from="${1:-}" ;;
      --to) shift; date_to="${1:-}" ;;
      -h|--help) usage; return ;;
      *) if [[ "$1" =~ ^[0-9]+$ ]]; then top_n="$1"; else die "Usage: agent-log hot [N] [-n N] [--from DATE] [--to DATE] [-j|--json]"; fi ;;
    esac
    shift
  done
  [[ "$top_n" =~ ^[1-9][0-9]*$ ]] || die "--top requires a positive integer, got: $top_n"

  local date_re='^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
  [[ -n "$date_from" ]] && ! [[ "$date_from" =~ $date_re ]] && die "--from requires YYYY-MM-DD format, got: $date_from"
  [[ -n "$date_to" ]] && ! [[ "$date_to" =~ $date_re ]] && die "--to requires YYYY-MM-DD format, got: $date_to"

  local files=()
  while IFS= read -r -d '' f; do files+=("$f"); done < <(find "$MEMORY_DIR" -name '*.md' -print0 2>/dev/null | sort -z)
  [[ ${#files[@]} -eq 0 ]] && die "No log files found in MEMORY_DIR=$MEMORY_DIR"

  if [[ -n "$date_from" ]] || [[ -n "$date_to" ]]; then
    local filtered=()
    for f in "${files[@]}"; do
      local basename; basename=$(basename "$f" .md)
      if [[ "$basename" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
        [[ -n "$date_from" ]] && [[ "$basename" < "$date_from" ]] && continue
        [[ -n "$date_to" ]] && [[ "$basename" > "$date_to" ]] && continue
      fi
      filtered+=("$f")
    done
    files=("${filtered[@]}")
  fi
  [[ ${#files[@]} -eq 0 ]] && die "No log files in range ${date_from:-..}${date_to:+ .. $date_to}"

  # Tokenize: lowercase words (letters/digits/_/-), min length 3, drop stopwords.
  local stopwords=(the and for that with this from not are was were has have had you your out all can will would could should into over under than then when what who how why its its been being their there these those also more most some such only each other about after before between during through very just like made make many much need now one two three new old see use used using get got set put run ran but our ours she her him his they them were what which while who will with)
  local terms_raw
  terms_raw=$(cat "${files[@]}" 2>/dev/null | tr '[:upper:]' '[:lower:]' \
    | grep -oE '[a-z][a-z0-9_-]{2,}' \
    | grep -vxF -f <(printf '%s\n' "${stopwords[@]}") \
    | sort | uniq -c | sort -rn | head -n "$top_n" || true)

  if [[ $JSON_OUTPUT -eq 1 ]]; then
    local json_items=() cnt term
    while IFS= read -r row; do
      [[ -z "$row" ]] && continue
      cnt=$(printf '%s' "$row" | awk '{print $1}')
      term=$(printf '%s' "$row" | awk '{$1=""; sub(/^ /,""); print}')
      json_items+=("{\"term\":\"$(esc_json "$term")\",\"count\":$cnt}")
    done <<< "$terms_raw"
    printf '{"command":"hot","n":%d,"file_count":%d,"terms":[%s]}\n' \
      "$top_n" "${#files[@]}" "$(IFS=,; echo "${json_items[*]+${json_items[*]}}")"
  else
    echo -e "${CYAN}Top terms:${RESET}"
    echo -e "${GRAY}(${#files[@]} files, top $top_n)${RESET}"
    [[ -z "$terms_raw" ]] && { echo "No terms found."; return; }
    printf '%s\n' "$terms_raw" | awk -F' :' '{count=$1; sub(/^ */,"",count); printf "  %6s  %s\n", count, $2}'
  fi
}

cmd_today() {
  local today
  today=$(date +%Y-%m-%d)
  cmd_date "$today"
}

cmd_date() {
  local d="$1"
  local file="$MEMORY_DIR/${d}.md"
  echo -e "${CYAN}📅 $d${RESET}"
  echo
  if [[ -f "$file" ]]; then cat "$file"; else echo -e "${GRAY}(no daily notes for $d)${RESET}"; fi
  if [[ -d "$SESSIONS_DIR" ]]; then
    echo; echo -e "${YELLOW}Session activity:${RESET}"
    find "$SESSIONS_DIR" -name '*.md' -newermt "$d 00:00:00" ! -newermt "$d 23:59:59" -print0 2>/dev/null \
      | xargs -0 -I{} bash -c 'echo -e "  ${GRAY}$(stat -c %y "{}" 2>/dev/null | cut -d. -f1)${RESET} {}"' 2>/dev/null \
      | sort | head -20
  fi
}

classify_activity() {
  local file="$1"
  local content; content=$(cat "$file" 2>/dev/null | tr '[:upper:]' '[:lower:]')
  local code_score=0 research_score=0 planning_score=0
  # Coding signals
  for kw in git commit code function class test bug fix refactor npm pip install error exception; do
    echo "$content" | grep -q "$kw" && ((code_score++))
  done
  # Research signals
  for kw in search read article paper study analysis research found discovered; do
    echo "$content" | grep -q "$kw" && ((research_score++))
  done
  # Planning signals
  for kw in plan todo task schedule meeting goal roadmap milestone agenda decision; do
    echo "$content" | grep -q "$kw" && ((planning_score++))
  done
  local max=$code_score type="coding"
  (( research_score > max )) && { max=$research_score; type="research"; }
  (( planning_score > max )) && { max=$planning_score; type="planning"; }
  echo "$type"
}

cmd_summary() {
  local days="7" keyword="" csv_output=0 md_output=0 show_types=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -j|--json) JSON_OUTPUT=1 ;;
      --csv) csv_output=1 ;;
      --md) md_output=1 ;;
      -t|--types) show_types=1 ;;
      -d|--days) shift; days="${1:-7}" ;;
      -k|--keyword) shift; keyword="${1:-}" ;;
      [0-9]*) days="$1" ;;
      *) keyword="$1" ;;
    esac
    shift
  done

  [[ $JSON_OUTPUT -eq 0 ]] && [[ $csv_output -eq 0 ]] && { echo -e "${CYAN}📊 Activity summary (last $days days)${RESET}"; [[ -n "$keyword" ]] && echo "  [filter: $keyword]"; echo; }

  local total_lines=0 total_files=0 json_entries=()

  for ((i=0; i<days; i++)); do
    local d
    d=$(date -d "$i days ago" +%Y-%m-%d 2>/dev/null || date -v-${i}d +%Y-%m-%d 2>/dev/null)
    local file="$MEMORY_DIR/${d}.md"
    [[ -f "$file" ]] || continue
    [[ -n "$keyword" ]] && ! grep -qi "$keyword" "$file" 2>/dev/null && continue
    local lines; lines=$(wc -l < "$file")
    total_lines=$((total_lines + lines)); total_files=$((total_files + 1))
    local weekday; weekday=$(date -d "$d" +%a 2>/dev/null || date -j -f "%Y-%m-%d" "$d" +%a 2>/dev/null)
    local activity_type=""
    [[ $show_types -eq 1 ]] && activity_type=" ($(classify_activity "$file"))"
    json_entries+=("{\"date\":\"$d\",\"weekday\":\"$weekday\",\"lines\":$lines}")
    [[ $JSON_OUTPUT -eq 0 ]] && [[ $csv_output -eq 0 ]] && printf "  ${GREEN}%s %-3s${RESET} %4d lines%s\n" "$d" "$weekday" "$lines" "$activity_type"

  done
  if [[ $csv_output -eq 1 ]]; then
    echo "date,weekday,lines"
    for (( idx=0; idx<${#json_entries[@]}; idx++ )); do
      local e="${json_entries[$idx]}"
      local ed ewd el
      ed=$(echo "$e" | sed 's/.*"date":"\([^"]*\)".*/\1/')
      ewd=$(echo "$e" | sed 's/.*"weekday":"\([^"]*\)".*/\1/')
      el=$(echo "$e" | sed 's/.*"lines":\([0-9]*\).*/\1/')
      echo "$ed,$ewd,$el"
    done
  elif [[ $JSON_OUTPUT -eq 1 ]]; then
    printf '{"command":"summary","days":%s,"keyword":"%s","total_files":%d,"total_lines":%d,"entries":[%s]}\n' \
      "$days" "$(esc_json "$keyword")" "$total_files" "$total_lines" "$(IFS=,; echo "${json_entries[*]+${json_entries[*]}}")"
  else
    echo; echo -e "  ${YELLOW}Total:${RESET} $total_files files, $total_lines lines"
    if [[ -f "$WORKSPACE/MEMORY.md" ]]; then
      local mem_lines; mem_lines=$(wc -l < "$WORKSPACE/MEMORY.md")
      echo -e "  ${YELLOW}MEMORY.md:${RESET} $mem_lines lines"
    fi
  fi

  if [[ $md_output -eq 1 ]]; then
    echo "# Activity Summary"
    echo ""
    echo "Period: last $days days"
    [[ -n "$keyword" ]] && echo "Filter: $keyword"
    echo ""
    echo "| Date | Day | Lines |"
    echo "|------|-----|-------|"
    for (( idx=0; idx<${#json_entries[@]}; idx++ )); do
      local e="${json_entries[$idx]}"
      local ed ewd el
      ed=$(echo "$e" | sed 's/.*"date":"\([^"]*\)".*/\1/')
      ewd=$(echo "$e" | sed 's/.*"weekday":"\([^"]*\)".*/\1/')
      el=$(echo "$e" | sed 's/.*"lines":\([0-9]*\).*/\1/')
      echo "| $ed | $ewd | $el |"
    done
    echo ""
    echo "**Total:** $total_files files, $total_lines lines"
  fi
}

cmd_cron() {
  local job_pattern=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --job)
        [[ -n "${2-}" ]] || { echo -e "${RED}--job requires a pattern${RESET}" >&2; return 1; }
        job_pattern="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  echo -e "${CYAN}⏰ Cron logs${RESET}"
  echo
  local cli_ok=0 listing
  if command -v openclaw &>/dev/null; then
    cli_ok=1
    listing=$(openclaw cron list 2>/dev/null || echo "(openclaw cron not available)")
  else
    listing="(openclaw CLI not in PATH)"
  fi
  if [[ -n "$job_pattern" && "$cli_ok" -eq 1 ]]; then
    local filtered
    filtered=$(printf '%s\n' "$listing" | grep -i -- "$job_pattern" || true)
    if [[ -z "${filtered// /}" ]]; then
      echo -e "${GRAY}(no matching cron jobs for: $job_pattern)${RESET}"
    else
      printf '%s\n' "$filtered"
    fi
  else
    printf '%s\n' "$listing"
  fi
}

cmd_sessions() {
  local json_out=0
  while [[ $# -gt 0 ]]; do case "$1" in -j|--json) json_out=1 ;; esac; shift; done

  [[ -d "$SESSIONS_DIR" ]] || { echo -e "${GRAY}(no sessions directory)${RESET}"; return; }

  local count=0 json_items=()
  local files; files=$(find "$SESSIONS_DIR" -name '*.md' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -30)

  [[ $json_out -eq 0 ]] && echo -e "${CYAN}📋 Recent sessions${RESET}"

  while IFS=' ' read -r ts f; do
    [[ -z "$f" ]] && continue
    local rel="${f#$HOME/}"
    local lines; lines=$(wc -l < "$f" 2>/dev/null || echo 0)
    local mod; mod=$(stat -c %y "$f" 2>/dev/null | cut -d. -f1)
    local size; size=$(stat -c %s "$f" 2>/dev/null || echo 0)
    count=$((count + 1))
    if [[ $json_out -eq 1 ]]; then
      json_items+=("{\"file\":\"$rel\",\"lines\":$lines,\"size\":$size,\"modified\":\"$mod\"}")
    else
      printf "  ${GREEN}%s${RESET} %5d lines %6s bytes  %s\n" "$mod" "$lines" "$size" "$(basename "$f")"
    fi
  done <<< "$files"

  if [[ $json_out -eq 1 ]]; then
    printf '{"command":"sessions","count":%d,"entries":[%s]}\n' "$count" "$(IFS=,; echo "${json_items[*]+${json_items[*]}}")"
  else
    echo; echo -e "  ${YELLOW}Total:${RESET} $count sessions shown"
  fi
}

cmd_clean() {
  local dry_run=0 age_days=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -n|--dry-run) dry_run=1 ;;
      -a|--age) shift; age_days="${1:-0}" ;;
      *) die "Usage: agent-log clean [-n|--dry-run] [-a|--age DAYS]" ;;
    esac
    shift
  done

  local removed=0 total_size=0

  echo -e "${CYAN}🧹 Clean log files${RESET}"
  [[ $dry_run -eq 1 ]] && echo -e "  ${YELLOW}(dry run — no files deleted)${RESET}"
  echo

  # Remove empty files (size 0; wc -l misses content without trailing newline)
  for f in "$MEMORY_DIR"/*.md; do
    [[ -f "$f" ]] || continue
    if [[ ! -s "$f" ]]; then
      local sz; sz=$(stat -c %s "$f" 2>/dev/null || echo 0)
      echo -e "  ${RED}empty:${RESET} $(basename "$f")"
      [[ $dry_run -eq 0 ]] && rm "$f"
      removed=$((removed + 1)); total_size=$((total_size + sz))
    fi
  done

  # Remove files older than age_days
  if [[ $age_days -gt 0 ]]; then
    local cutoff; cutoff=$(date -d "$age_days days ago" +%Y-%m-%d 2>/dev/null || date -v-${age_days}d +%Y-%m-%d 2>/dev/null)
    for f in "$MEMORY_DIR"/*.md; do
      [[ -f "$f" ]] || continue
      local fname; fname=$(basename "$f" .md)
      # Only match date-formatted files (YYYY-MM-DD)
      [[ "$fname" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || continue
      [[ "$fname" < "$cutoff" ]] || continue
      local sz; sz=$(stat -c %s "$f" 2>/dev/null || echo 0)
      echo -e "  ${RED}old ($fname):${RESET} $(basename "$f")"
      [[ $dry_run -eq 0 ]] && rm "$f"
      removed=$((removed + 1)); total_size=$((total_size + sz))
    done
  fi

  echo
  echo -e "  ${YELLOW}Files removed:${RESET} $removed (${total_size} bytes)"
}

cmd_stats() {
  local md_output=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -j|--json) JSON_OUTPUT=1 ;;
      --md) md_output=1 ;;
    esac
    shift
  done

  local mem_count=0 sess_count=0
  [[ -d "$MEMORY_DIR" ]] && mem_count=$(find "$MEMORY_DIR" -name '*.md' | wc -l)
  [[ -d "$SESSIONS_DIR" ]] && sess_count=$(find "$SESSIONS_DIR" -name '*.md' | wc -l)
  local ws_size; ws_size=$(du -sh "$WORKSPACE" 2>/dev/null | cut -f1)

  local latest_file="" latest_time=0
  for f in "$MEMORY_DIR"/*.md; do
    [[ -f "$f" ]] || continue
    local t; t=$(stat -c %Y "$f" 2>/dev/null || echo 0)
    (( t > latest_time )) && { latest_time=$t; latest_file="$f"; }
  done
  local latest_name=""; [[ -n "$latest_file" ]] && latest_name=$(basename "$latest_file")

  if [[ $JSON_OUTPUT -eq 1 ]]; then
    printf '{"command":"stats","memory_files":%d,"session_files":%d,"workspace_size":"%s","latest_note":"%s"}\n' \
      "$mem_count" "$sess_count" "$ws_size" "$latest_name"
  else
    echo -e "${CYAN}📈 Workspace stats${RESET}"
    echo
    echo -e "  Memory files:   ${GREEN}$mem_count${RESET}"
    echo -e "  Session files:  ${GREEN}$sess_count${RESET}"
    echo -e "  Workspace size: ${GREEN}$ws_size${RESET}"
    [[ -n "$latest_file" ]] && echo -e "  Latest note:    ${BLUE}$(basename "$latest_file")${RESET}"
  fi

  if [[ $md_output -eq 1 ]]; then
    echo "# Workspace Stats"
    echo ""
    echo "Generated: $(date -Iseconds)"
    echo ""
    echo "| Metric | Value |"
    echo "|--------|-------|"
    echo "| Memory files | $mem_count |"
    echo "| Session files | $sess_count |"
    echo "| Workspace size | $ws_size |"
    echo "| Latest note | ${latest_name:-N/A} |"
  fi
}

cmd_find() {
  local pattern="" date_after="" date_before="" json_out=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -j|--json) json_out=1 ;;
      -a|--after) shift; date_after="${1:-}" ;;
      -b|--before) shift; date_before="${1:-}" ;;
      *) pattern="$1" ;;
    esac
    shift
  done

  [[ -d "$SESSIONS_DIR" ]] || die "No sessions directory"
  [[ -z "$pattern" && -z "$date_after" && -z "$date_before" ]] && die "Usage: agent-log find <pattern> [-a DATE] [-b DATE] [-j|--json]"

  local count=0 json_items=()
  [[ $json_out -eq 0 ]] && echo -e "${CYAN}🔍 Find sessions${RESET}"
  [[ -n "$pattern" ]] && [[ $json_out -eq 0 ]] && echo -e "  pattern: $pattern"
  [[ -n "$date_after" ]] && [[ $json_out -eq 0 ]] && echo -e "  after: $date_after"
  [[ -n "$date_before" ]] && [[ $json_out -eq 0 ]] && echo -e "  before: $date_before"
  [[ $json_out -eq 0 ]] && echo

  while IFS= read -r -d '' f; do
    [[ -f "$f" ]] || continue
    local mod; mod=$(stat -c %Y "$f" 2>/dev/null || echo 0)
    local mod_date; mod_date=$(date -d "@$mod" +%Y-%m-%d 2>/dev/null || echo "")

    # Date filtering
    [[ -n "$date_after" && "$mod_date" < "$date_after" ]] && continue
    [[ -n "$date_before" && "$mod_date" > "$date_before" ]] && continue

    # Pattern filtering (search in filename + content)
    if [[ -n "$pattern" ]]; then
      local basename_f; basename_f=$(basename "$f")
      grep -qi "$pattern" "$f" 2>/dev/null || [[ "$basename_f" == *"$pattern"* ]] || continue
    fi

    local lines; lines=$(wc -l < "$f" 2>/dev/null || echo 0)
    local rel="${f#$HOME/}"
    count=$((count + 1))

    if [[ $json_out -eq 1 ]]; then
      json_items+=("{\"file\":\"$(esc_json "$rel")\",\"lines\":$lines,\"modified\":\"$mod_date\"}")
    else
      printf "  ${GREEN}%s${RESET} %5d lines  %s\n" "$mod_date" "$lines" "$(basename "$f")"
    fi
  done < <(find "$SESSIONS_DIR" -name '*.md' -print0 2>/dev/null | sort -z)

  if [[ $json_out -eq 1 ]]; then
    printf '{"command":"find","pattern":"%s","after":"%s","before":"%s","count":%d,"results":[%s]}\n' \
      "$(esc_json "$pattern")" "$date_after" "$date_before" "$count" "$(IFS=,; echo "${json_items[*]+${json_items[*]}}")"
  else
    echo -e "  ${YELLOW}Found:${RESET} $count sessions"
  fi
}

cmd_grep() {
  local pattern="" json_out=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -j|--json) json_out=1 ;;
      *) pattern="$1" ;;
    esac
    shift
  done
  [[ -z "$pattern" ]] && die "Usage: agent-log grep <pattern> [-j|--json]"

  [[ -d "$SESSIONS_DIR" ]] || die "No sessions directory"
  local grep_color=()
  [[ -t 1 && -z "${NO_COLOR:-}" ]] && grep_color=(--color=always)
  grep -r --include='*.md' "${grep_color[@]}" -n "$pattern" "$SESSIONS_DIR" 2>/dev/null \
    | head -50 || echo -e "${GRAY}(no matches)${RESET}"
}

cmd_tail() {
  local n="20" follow=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -n) shift; n="${1:-20}" ;;
      -f|--follow) follow=1 ;;
      *) n="$1" ;;
    esac
    shift
  done

  [[ -d "$SESSIONS_DIR" ]] || die "No sessions directory"

  # Find most recent session file
  local latest; latest=$(find "$SESSIONS_DIR" -name '*.md' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
  [[ -z "$latest" ]] && die "No session files found"

  echo -e "${CYAN}📋 Tailing: $(basename "$latest")${RESET}"
  echo

  if [[ $follow -eq 1 ]]; then
    tail -n "$n" -f "$latest"
  else
    tail -n "$n" "$latest"
  fi
}

cmd_session() {
  local id="" json_out=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -j|--json) json_out=1 ;;
      *) id="$1" ;;
    esac
    shift
  done

  [[ -z "$id" ]] && die "Usage: agent-log session <file-or-pattern> [-j|--json]"
  [[ -d "$SESSIONS_DIR" ]] || die "No sessions directory"

  # Try exact match first, then partial match
  local target=""
  if [[ -f "$SESSIONS_DIR/$id" ]]; then
    target="$SESSIONS_DIR/$id"
  elif [[ -f "$SESSIONS_DIR/$id.md" ]]; then
    target="$SESSIONS_DIR/$id.md"
  else
    # Search by partial name
    local found; found=$(find "$SESSIONS_DIR" -name "*${id}*.md" -print -quit 2>/dev/null)
    [[ -n "$found" ]] && target="$found"
  fi

  [[ -z "$target" ]] && die "Session not found: $id"

  local lines; lines=$(wc -l < "$target" 2>/dev/null || echo 0)
  local size; size=$(stat -c %s "$target" 2>/dev/null || echo 0)
  local mod; mod=$(stat -c %y "$target" 2>/dev/null | cut -d. -f1)

  if [[ $json_out -eq 1 ]]; then
    local content; content=$(cat "$target" | head -100)
    printf '{"command":"session","file":"%s","lines":%d,"size":%d,"modified":"%s","content":"%s"}\n' \
      "$(esc_json "${target#$HOME/}")" "$lines" "$size" "$mod" "$(esc_json "$content")"
  else
    echo -e "${CYAN}📋 Session: $(basename "$target")${RESET}"
    echo -e "  ${GRAY}Modified: $mod | $lines lines | $size bytes${RESET}"
    echo
    cat "$target"
  fi
}

cmd_trend() {
  local days="14"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -d|--days) shift; days="${1:-14}" ;;
      -j|--json) JSON_OUTPUT=1 ;;
      [0-9]*) days="$1" ;;
    esac
    shift
  done

  [[ $JSON_OUTPUT -eq 0 ]] && echo -e "${CYAN}📈 Activity trend (last $days days)${RESET}"

  local entries=() labels=() values=()
  for ((i=days-1; i>=0; i--)); do
    local d
    d=$(date -d "$i days ago" +%Y-%m-%d 2>/dev/null || date -v-${i}d +%Y-%m-%d 2>/dev/null)
    local file="$MEMORY_DIR/${d}.md"
    local lines=0
    [[ -f "$file" ]] && lines=$(wc -l < "$file")
    local short_d=$(date -d "$d" +%m/%d 2>/dev/null || echo "$d")
    labels+=("$short_d")
    values+=("$lines")
    [[ $JSON_OUTPUT -eq 1 ]] && entries+=("{\"date\":\"$d\",\"lines\":$lines}")
  done

  if [[ $JSON_OUTPUT -eq 1 ]]; then
    printf '{"command":"trend","days":%d,"data":[%s]}\n' "$days" "$(IFS=,; echo "${entries[*]}")"
    return
  fi

  # Find max for scaling
  local max=1
  for v in "${values[@]}"; do (( v > max )) && max=$v; done

  local bar_chars='▁▂▃▄▅▆▇█'
  local num_bars=${#bar_chars}

  for ((i=0; i<${#values[@]}; i++)); do
    local v=${values[$i]}
    local idx=0
    if [[ $v -gt 0 ]]; then
      idx=$(( v * (num_bars - 1) / max ))
    fi
    local bar=${bar_chars:$idx:1}
    printf "  %s %4d  %s\n" "${labels[$i]}" "$v" "$bar"
  done

  echo
  echo -e "  ${GRAY}Max: $max lines | Scale: ▁(0) → █($max)${RESET}"
}

# ── Main ──

usage() {
  cat <<'EOF'
agent-log — Search, filter, and summarize OpenClaw session logs

Usage: agent-log <command> [args]

Commands:
  search <query> [-r|--regex] [-o FILE] [-j|--json] [--from DATE] [--to DATE] [--count] [-C N|--context N]
      Search memory + session logs (text or regex; --count shows ranked match counts; -C sets context lines, default 1)
  hot [N] [-n N] [--from DATE] [--to DATE] [-j|--json]
      Top-N most frequent terms across memory logs (default N=10; English words, min length 3)
  today                      Show today's daily notes + session activity
  date YYYY-MM-DD            Show notes for a specific date
  summary [DAYS] [-k|--keyword KW] [-t|--types] [--csv] [--md] [-j|--json]
      Activity summary with line counts per day
  trend [DAYS] [-j|--json]   Activity sparkline trend
  stats [--md] [-j|--json]   Workspace statistics
  sessions [-j|--json]       List recent session files
  session <id> [-j|--json]   Show one session by name/pattern
  find <pattern> [-a DATE] [-b DATE] [-j|--json]
      Find sessions by pattern and/or date range
  grep <pattern>             Grep across session logs
  tail [-n N] [-f]           Tail the most recent session
  cron                       List OpenClaw cron jobs
  clean [-n|--dry-run] [-a|--age DAYS]
      Remove empty / old daily note files
  help                       Show this help

Environment:
  OPENCLAW_WORKSPACE         Workspace root (default: ~/.openclaw/workspace)
EOF
}

case "${1:-help}" in
  search)  shift; cmd_search "$@" ;;
  hot)     shift; cmd_hot "$@" ;;
  today)   cmd_today ;;
  date)    [[ -z "${2:-}" ]] && die "Usage: agent-log date YYYY-MM-DD"; cmd_date "$2" ;;
  summary) shift; cmd_summary "$@" ;;
  cron)    shift; cmd_cron "$@" ;;
  stats)   shift; cmd_stats "$@" ;;
  clean)   shift; cmd_clean "$@" ;;
  sessions) shift; cmd_sessions "$@" ;;
  session) shift; cmd_session "$@" ;;
  find)    shift; cmd_find "$@" ;;
  grep)    shift; cmd_grep "$@" ;;
  tail)    shift; cmd_tail "$@" ;;
  trend)   shift; cmd_trend "$@" ;;
  help|*)  usage ;;
esac
