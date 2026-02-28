#!/usr/bin/env bash
# run-index.sh — Run explorer CLI for the orchestrate index.
#
# Provides listing, inspection, continuation, retry, and maintenance of runs
# stored in .orchestrate/index/runs.jsonl.
#
# Usage:
#   run-index.sh <command> [options]
#
# Commands:
#   list                     List runs with filtering and pagination
#   show <run-ref>           One-run metadata summary
#   report <run-ref>         Print report content
#   logs <run-ref>           Paginated log browsing
#   files <run-ref>          Print touched files
#   stats                    Aggregate statistics
#   continue <run-ref>       Continue a previous run's session
#   retry <run-ref>          Re-run with same or overridden params
#   maintain                 Archive/compact old index entries
#
# Global flags:
#   --json          Machine-readable JSON output
#   --no-color      Plain text (no ANSI escapes)
#   --quiet         Suppress non-essential output
#   --repo <path>   Target repository root

set -euo pipefail

# ─── Globals ──────────────────────────────────────────────────────────────────

JSON_MODE=false
NO_COLOR=false
QUIET=false
REPO_ROOT=""
ORCHESTRATE_ROOT=""
INDEX_FILE=""

# ─── Helpers ──────────────────────────────────────────────────────────────────

_resolve_repo() {
  if [[ -n "$REPO_ROOT" ]]; then
    return
  fi
  REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)"
  ORCHESTRATE_ROOT="$REPO_ROOT/.orchestrate"
  INDEX_FILE="$ORCHESTRATE_ROOT/index/runs.jsonl"
}

_require_index() {
  _resolve_repo
  if [[ ! -f "$INDEX_FILE" ]]; then
    _error "no_index" "No index file found at $INDEX_FILE" "Run an agent first, or check --repo path."
    exit 1
  fi
}

_require_jq() {
  if ! command -v jq >/dev/null 2>&1; then
    echo "ERROR: jq is required for run-index.sh" >&2
    exit 2
  fi
}

# JSON envelope output
_json_ok() {
  local cmd="$1" data="$2" meta="${3:-{}}"
  echo "{\"ok\":true,\"command\":\"$cmd\",\"data\":$data,\"error\":null,\"meta\":$meta}"
}

_json_error() {
  local cmd="$1" code="$2" message="$3" hint="${4:-}"
  local hint_json="null"
  [[ -n "$hint" ]] && hint_json="\"$hint\""
  echo "{\"ok\":false,\"command\":\"$cmd\",\"data\":null,\"error\":{\"code\":\"$code\",\"message\":\"$message\",\"hint\":$hint_json},\"meta\":{}}"
}

_error() {
  local code="$1" message="$2" hint="${3:-}"
  if [[ "$JSON_MODE" == true ]]; then
    _json_error "${COMMAND:-unknown}" "$code" "$message" "$hint"
  else
    echo "ERROR: $message" >&2
    [[ -n "$hint" ]] && echo "  Hint: $hint" >&2
  fi
}

_info() {
  [[ "$QUIET" == true ]] && return
  echo "$@" >&2
}

# ─── Index Locking ────────────────────────────────────────────────────────────

_LOCK_FD=""
_LOCK_DIR_PATH=""

_acquire_read_lock() {
  local lock_path="$ORCHESTRATE_ROOT/index/runs.lock"
  if command -v flock >/dev/null 2>&1; then
    exec {_LOCK_FD}<"$INDEX_FILE"
    flock -s -w 5 "$_LOCK_FD" 2>/dev/null || true
  fi
}

_release_lock() {
  if [[ -n "${_LOCK_FD:-}" ]]; then
    eval "exec ${_LOCK_FD}>&-" 2>/dev/null || true
    _LOCK_FD=""
  fi
}

# ─── Derived View ─────────────────────────────────────────────────────────────
# Group rows by run_id, merge start + finalize into a single derived object.

_build_derived_view() {
  local include_archive="${1:-false}"
  _acquire_read_lock

  # Collect input files: main index + optional archive
  local -a input_files=("$INDEX_FILE")
  if [[ "$include_archive" == true ]]; then
    local archive_dir="$ORCHESTRATE_ROOT/index/archive"
    if [[ -d "$archive_dir" ]]; then
      while IFS= read -r -d '' f; do
        input_files+=("$f")
      done < <(find "$archive_dir" -name '*.jsonl' -print0 2>/dev/null)
    fi
  fi

  jq -s '
    group_by(.run_id)
    | map(
        . as $rows
        | ($rows | map(select(.status == "running")) | first) as $start
        | ($rows | map(select(.status == "completed" or .status == "failed")) | first) as $fin
        | ($start // $rows[0])
        + (if $fin then $fin else {} end)
        + {
            effective_status: (if $fin then $fin.status else "running" end),
            started_at: ($start // $rows[0]).created_at_utc,
            finished_at: (if $fin then $fin.finished_at_utc else null end)
          }
      )
    | sort_by(.started_at) | reverse
  ' "${input_files[@]}" 2>/dev/null || echo "[]"
  _release_lock
}

# ─── Run Reference Resolution ────────────────────────────────────────────────

_resolve_run_ref() {
  local ref="$1"
  local derived="$2"

  case "$ref" in
    @latest)
      echo "$derived" | jq -r '.[0].run_id // empty'
      ;;
    @last-failed)
      echo "$derived" | jq -r '[.[] | select(.effective_status == "failed")] | .[0].run_id // empty'
      ;;
    @last-completed)
      echo "$derived" | jq -r '[.[] | select(.effective_status == "completed")] | .[0].run_id // empty'
      ;;
    *)
      # Try exact match first
      local exact
      exact="$(echo "$derived" | jq -r --arg ref "$ref" '[.[] | select(.run_id == $ref)] | .[0].run_id // empty')"
      if [[ -n "$exact" ]]; then
        echo "$exact"
        return
      fi

      # Try prefix match (min 8 chars)
      if [[ ${#ref} -lt 8 ]]; then
        _error "short_prefix" "Run reference prefix must be at least 8 characters (got ${#ref})" "Use a longer prefix or @latest/@last-failed."
        return 1
      fi

      local matches
      matches="$(echo "$derived" | jq -r --arg prefix "$ref" '[.[] | select(.run_id | startswith($prefix))] | map(.run_id)')"
      local count
      count="$(echo "$matches" | jq 'length')"

      if [[ "$count" -eq 0 ]]; then
        _error "not_found" "No run matching '$ref'" "Run 'run-index.sh list' to see available runs."
        return 1
      elif [[ "$count" -eq 1 ]]; then
        echo "$matches" | jq -r '.[0]'
      else
        _error "ambiguous" "Ambiguous run reference '$ref' matches $count runs" "Use a longer prefix. Candidates: $(echo "$matches" | jq -r 'join(", ")')"
        return 1
      fi
      ;;
  esac
}

# ─── Commands ─────────────────────────────────────────────────────────────────

cmd_list() {
  local limit=20 cursor="" session="" model="" status="" label_filter=""
  local failed_only=false since="" until_date="" include_archive=false agent=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --limit)       limit="$2"; shift 2 ;;
      --cursor)      cursor="$2"; shift 2 ;;
      --session)     session="$2"; shift 2 ;;
      --model)       model="$2"; shift 2 ;;
      --agent)       agent="$2"; shift 2 ;;
      --status)      status="$2"; shift 2 ;;
      --label)       label_filter="$2"; shift 2 ;;
      --failed)      failed_only=true; shift ;;
      --since)       since="$2"; shift 2 ;;
      --until)       until_date="$2"; shift 2 ;;
      --include-archive) include_archive=true; shift ;;
      *) echo "ERROR: Unknown list option: $1" >&2; exit 1 ;;
    esac
  done

  local derived
  derived="$(_build_derived_view "$include_archive")"

  # Apply filters
  local filter="."
  [[ -n "$session" ]] && filter+=" | select(.session_id == \"$session\")"
  [[ -n "$model" ]] && filter+=" | select(.model == \"$model\")"
  [[ -n "$agent" ]] && filter+=" | select(.agent == \"$agent\")"
  [[ -n "$status" ]] && filter+=" | select(.effective_status == \"$status\")"
  [[ "$failed_only" == true ]] && filter+=" | select(.effective_status == \"failed\")"
  [[ -n "$since" ]] && filter+=" | select(.started_at >= \"$since\")"
  [[ -n "$until_date" ]] && filter+=" | select(.started_at <= \"$until_date\")"

  if [[ -n "$label_filter" ]]; then
    local lk="${label_filter%%=*}" lv="${label_filter#*=}"
    filter+=" | select(.labels.\"$lk\" == \"$lv\")"
  fi

  local filtered
  filtered="$(echo "$derived" | jq "[.[] | $filter]")"

  # Cursor pagination
  local start_idx=0
  if [[ -n "$cursor" ]]; then
    start_idx="$(echo "$filtered" | jq --arg c "$cursor" '[.[] | .run_id] | to_entries | map(select(.value == $c)) | .[0].key // 0' 2>/dev/null || echo "0")"
    start_idx=$((start_idx + 1))
  fi

  local total
  total="$(echo "$filtered" | jq 'length')"

  local page
  page="$(echo "$filtered" | jq --argjson s "$start_idx" --argjson l "$limit" '.[$s:$s+$l]')"

  local page_count
  page_count="$(echo "$page" | jq 'length')"
  local next_idx=$((start_idx + page_count))
  local has_next=false
  local next_cursor="null"

  if [[ "$next_idx" -lt "$total" ]]; then
    has_next=true
    next_cursor="\"$(echo "$filtered" | jq -r --argjson i "$((next_idx - 1))" '.[$i].run_id')\""
  fi

  if [[ "$JSON_MODE" == true ]]; then
    local data
    data="$(echo "$page" | jq '[.[] | {run_id, model, effective_status, started_at, finished_at, duration_seconds, exit_code, session_id, labels}]')"
    local meta="{\"total\":$total,\"limit\":$limit,\"next_cursor\":$next_cursor,\"has_next\":$has_next}"
    _json_ok "list" "$data" "$meta"
  else
    if [[ "$total" -eq 0 ]]; then
      echo "No runs found."
      return
    fi

    echo "$page" | jq -r '.[] | "\(.effective_status | if . == "completed" then "✓" elif . == "failed" then "✗" else "…" end) \(.run_id)  \(.model)  \(.duration_seconds // "-")s  \(.effective_status)"'
    echo ""
    echo "Showing $page_count of $total runs."
    if [[ "$has_next" == true ]]; then
      echo "Next page: --cursor $(echo "$filtered" | jq -r --argjson i "$((next_idx - 1))" '.[$i].run_id')"
    fi
  fi
}

cmd_show() {
  local ref="${1:?Usage: run-index.sh show <run-ref>}"
  local derived run_id

  derived="$(_build_derived_view)"
  run_id="$(_resolve_run_ref "$ref" "$derived")" || exit 1

  if [[ -z "$run_id" ]]; then
    _error "not_found" "No run matching '$ref'" "Run 'run-index.sh list' to see available runs."
    exit 1
  fi

  local run
  run="$(echo "$derived" | jq --arg id "$run_id" '.[] | select(.run_id == $id)')"

  if [[ "$JSON_MODE" == true ]]; then
    _json_ok "show" "$run"
  else
    echo "$run" | jq -r '
      "Run: \(.run_id)\n" +
      "Status: \(.effective_status)\n" +
      "Agent: \(.agent // "-")\n" +
      "Model: \(.model)\n" +
      "Harness: \(.harness // "-")\n" +
      "Started: \(.started_at)\n" +
      "Finished: \(.finished_at // "-")\n" +
      "Duration: \(.duration_seconds // "-")s\n" +
      "Exit code: \(.exit_code // "-")\n" +
      "Failure reason: \(.failure_reason // "-")\n" +
      "Session: \(.session_id // "-")\n" +
      "Skills: \((.skills // []) | join(", "))\n" +
      "Labels: \((.labels // {}) | to_entries | map("\(.key)=\(.value)") | join(", "))\n" +
      "Harness session: \(.harness_session_id // "-")\n" +
      "Git: head_before=\(.head_before // "-") head_after=\(.head_after // "-") commits=\(.commit_count // 0)\n" +
      "Tokens: in=\(.input_tokens // "-") out=\(.output_tokens // "-")\n" +
      "Log dir: \(.log_dir // "-")"
    '
  fi
}

cmd_report() {
  local ref="${1:?Usage: run-index.sh report <run-ref>}"
  local derived run_id

  derived="$(_build_derived_view)"
  run_id="$(_resolve_run_ref "$ref" "$derived")" || exit 1

  if [[ -z "$run_id" ]]; then
    _error "not_found" "No run matching '$ref'"
    exit 1
  fi

  local log_dir
  log_dir="$(echo "$derived" | jq -r --arg id "$run_id" '.[] | select(.run_id == $id) | .log_dir')"
  local report="$log_dir/report.md"

  if [[ ! -f "$report" ]]; then
    _error "no_report" "No report found for run $run_id" "Check $log_dir/"
    exit 1
  fi

  if [[ "$JSON_MODE" == true ]]; then
    local content
    content="$(jq -Rs '.' "$report")"
    _json_ok "report" "{\"run_id\":\"$run_id\",\"content\":$content}"
  else
    cat "$report"
  fi
}

cmd_logs() {
  local ref="${1:?Usage: run-index.sh logs <run-ref> [--summary|--tools|--errors|--search PATTERN]}"; shift
  local mode="summary" search_pattern="" limit=200 cursor=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --summary) mode="summary"; shift ;;
      --tools)   mode="tools"; shift ;;
      --errors)  mode="errors"; shift ;;
      --search)  mode="search"; search_pattern="$2"; shift 2 ;;
      --limit)   limit="$2"; shift 2 ;;
      --cursor)  cursor="$2"; shift 2 ;;
      *) echo "ERROR: Unknown logs option: $1" >&2; exit 1 ;;
    esac
  done

  local derived run_id
  derived="$(_build_derived_view)"
  run_id="$(_resolve_run_ref "$ref" "$derived")" || exit 1

  local log_dir
  log_dir="$(echo "$derived" | jq -r --arg id "$run_id" '.[] | select(.run_id == $id) | .log_dir')"

  # Delegate to log-inspect.sh if available
  local inspector="$(dirname "$0")/log-inspect.sh"
  local output_log="$log_dir/output.jsonl"

  if [[ ! -f "$output_log" ]]; then
    _error "no_output" "No output log for run $run_id" "Check $log_dir/"
    exit 1
  fi

  if [[ -x "$inspector" ]]; then
    case "$mode" in
      summary) "$inspector" summary "$output_log" ;;
      tools)   "$inspector" tools "$output_log" ;;
      errors)  "$inspector" errors "$output_log" ;;
      search)  "$inspector" search "$output_log" "$search_pattern" ;;
    esac
  else
    # Basic fallback
    case "$mode" in
      summary) wc -l "$output_log" | awk '{print $1 " lines"}' ;;
      tools)   grep -o '"tool_name":"[^"]*"' "$output_log" 2>/dev/null | sort | uniq -c | sort -rn || echo "No tool calls found." ;;
      errors)  grep -i '"is_error":true\|"error"' "$output_log" 2>/dev/null | head -20 || echo "No errors found." ;;
      search)  grep -n "$search_pattern" "$output_log" 2>/dev/null | head -"$limit" || echo "No matches." ;;
    esac
  fi
}

cmd_files() {
  local ref="${1:?Usage: run-index.sh files <run-ref> [--txt|--nul]}"; shift
  local format="txt"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --txt) format="txt"; shift ;;
      --nul) format="nul"; shift ;;
      *) echo "ERROR: Unknown files option: $1" >&2; exit 1 ;;
    esac
  done

  local derived run_id
  derived="$(_build_derived_view)"
  run_id="$(_resolve_run_ref "$ref" "$derived")" || exit 1

  local log_dir
  log_dir="$(echo "$derived" | jq -r --arg id "$run_id" '.[] | select(.run_id == $id) | .log_dir')"

  local target_file="$log_dir/files-touched.$format"
  if [[ ! -f "$target_file" ]]; then
    # Fall back to txt if nul not available
    target_file="$log_dir/files-touched.txt"
  fi

  if [[ ! -f "$target_file" ]]; then
    _error "no_files" "No files-touched data for run $run_id"
    exit 1
  fi

  if [[ "$JSON_MODE" == true ]]; then
    local files_json
    if [[ "$format" == "nul" ]] && [[ -f "$log_dir/files-touched.nul" ]]; then
      files_json="$(tr '\0' '\n' < "$log_dir/files-touched.nul" | jq -R '.' | jq -s '.')"
    else
      files_json="$(jq -R '.' "$target_file" | jq -s '.')"
    fi
    _json_ok "files" "{\"run_id\":\"$run_id\",\"files\":$files_json}"
  else
    cat "$target_file"
  fi
}

cmd_stats() {
  local session="" include_archive=false

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --session)         session="$2"; shift 2 ;;
      --include-archive) include_archive=true; shift ;;
      *) echo "ERROR: Unknown stats option: $1" >&2; exit 1 ;;
    esac
  done

  local derived
  derived="$(_build_derived_view "$include_archive")"

  if [[ -n "$session" ]]; then
    derived="$(echo "$derived" | jq --arg s "$session" '[.[] | select(.session_id == $s)]')"
  fi

  local stats
  stats="$(echo "$derived" | jq '
    {
      total_runs: length,
      completed: [.[] | select(.effective_status == "completed")] | length,
      failed: [.[] | select(.effective_status == "failed")] | length,
      running: [.[] | select(.effective_status == "running")] | length,
      fail_reasons: ([.[] | select(.effective_status == "failed") | .failure_reason // "unknown"] | group_by(.) | map({(.[0]): length}) | add // {}),
      models: ([.[] | .model] | group_by(.) | map({(.[0]): length}) | add // {}),
      total_duration_seconds: ([.[] | .duration_seconds // 0] | add // 0),
      avg_duration_seconds: (if length > 0 then ([.[] | .duration_seconds // 0] | add // 0) / length | floor else 0 end)
    }
  ')"

  if [[ "$JSON_MODE" == true ]]; then
    _json_ok "stats" "$stats"
  else
    echo "$stats" | jq -r '
      "Runs: \(.total_runs) total (\(.completed) completed, \(.failed) failed, \(.running) running)\n" +
      "Pass rate: \(if .total_runs > 0 then ((.completed / .total_runs * 100) | floor | tostring) + "%" else "N/A" end)\n" +
      "Failure reasons: \(.fail_reasons | to_entries | map("\(.key): \(.value)") | join(", ") | if . == "" then "none" else . end)\n" +
      "Models: \(.models | to_entries | map("\(.key): \(.value)") | join(", "))\n" +
      "Total duration: \(.total_duration_seconds)s\n" +
      "Avg duration: \(.avg_duration_seconds)s"
    '
  fi
}

cmd_continue() {
  local ref="${1:?Usage: run-index.sh continue <run-ref> -p 'follow-up' [--model override] [--fork|--in-place]}"; shift
  local prompt="" model_override="" extra_skills="" extra_labels=()
  local continuation_mode_arg=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -p|--prompt) prompt="$2"; shift 2 ;;
      --model)     model_override="$2"; shift 2 ;;
      --skills)    extra_skills="$2"; shift 2 ;;
      --label)     extra_labels+=("$2"); shift 2 ;;
      --fork)      continuation_mode_arg="--fork"; shift ;;
      --in-place)  continuation_mode_arg="--in-place"; shift ;;
      *) echo "ERROR: Unknown continue option: $1" >&2; exit 1 ;;
    esac
  done

  if [[ -z "$prompt" ]]; then
    _error "missing_prompt" "Continue requires a follow-up prompt (-p)"
    exit 1
  fi

  local derived run_id
  derived="$(_build_derived_view)"
  run_id="$(_resolve_run_ref "$ref" "$derived")" || exit 1

  local run
  run="$(echo "$derived" | jq --arg id "$run_id" '.[] | select(.run_id == $id)')"

  # Validate: run must be finalized
  local eff_status
  eff_status="$(echo "$run" | jq -r '.effective_status')"
  if [[ "$eff_status" == "running" ]]; then
    _error "still_running" "Cannot continue run $run_id: still running or crashed (no finalize row)"
    exit 1
  fi

  # Get original model and agent
  local orig_model orig_agent
  orig_model="$(echo "$run" | jq -r '.model')"
  orig_agent="$(echo "$run" | jq -r '.agent // empty')"
  local target_model="${model_override:-$orig_model}"

  # Build run-agent command
  local runner="$(dirname "$0")/run-agent.sh"
  local cmd=("$runner" --model "$target_model" -p "$prompt" --continue-run "$run_id")
  [[ -n "$orig_agent" ]] && cmd+=(--agent "$orig_agent")
  [[ -n "$continuation_mode_arg" ]] && cmd+=("$continuation_mode_arg")

  if [[ -n "$extra_skills" ]]; then
    cmd+=(--skills "$extra_skills")
  fi

  for lbl in "${extra_labels[@]}"; do
    cmd+=(--label "$lbl")
  done

  _info "Continuing run $run_id with model $target_model..."
  exec "${cmd[@]}"
}

cmd_retry() {
  local ref="${1:?Usage: run-index.sh retry <run-ref> [--undo-first] [--model override]}"; shift
  local undo_first=false model_override="" prompt_override="" extra_skills=""
  local dry_run=false force=false yes=false

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --undo-first) undo_first=true; shift ;;
      --model)      model_override="$2"; shift 2 ;;
      -p|--prompt)  prompt_override="$2"; shift 2 ;;
      --skills)     extra_skills="$2"; shift 2 ;;
      --dry-run)    dry_run=true; shift ;;
      --force)      force=true; shift ;;
      --yes)        yes=true; shift ;;
      *) echo "ERROR: Unknown retry option: $1" >&2; exit 1 ;;
    esac
  done

  local derived run_id
  derived="$(_build_derived_view)"
  run_id="$(_resolve_run_ref "$ref" "$derived")" || exit 1

  local run
  run="$(echo "$derived" | jq --arg id "$run_id" '.[] | select(.run_id == $id)')"

  local log_dir
  log_dir="$(echo "$run" | jq -r '.log_dir')"

  # Undo handling
  if [[ "$undo_first" == true ]]; then
    local git_available in_git head_before
    git_available="$(echo "$run" | jq -r '.git_available // false')"
    in_git="$(echo "$run" | jq -r '.in_git_repo // false')"
    head_before="$(echo "$run" | jq -r '.head_before // ""')"

    if [[ "$git_available" != "true" ]] || [[ "$in_git" != "true" ]]; then
      _error "no_git" "--undo-first requires git in a git repository"
      exit 1
    fi

    local files_nul="$log_dir/files-touched.nul"
    local files_txt="$log_dir/files-touched.txt"
    if [[ ! -f "$files_nul" ]] && [[ ! -f "$files_txt" ]]; then
      _error "no_files" "No files-touched data for surgical undo" "Suggest manual revert."
      exit 1
    fi
    if [[ -z "$head_before" ]]; then
      _error "no_head" "No head_before recorded for surgical undo" "Suggest manual revert."
      exit 1
    fi

    # Read files list
    local files_list
    if [[ -f "$files_nul" ]]; then
      files_list="$(tr '\0' '\n' < "$files_nul")"
    else
      files_list="$(cat "$files_txt")"
    fi

    local file_count
    file_count="$(echo "$files_list" | grep -c . || echo "0")"

    if [[ "$dry_run" == true ]]; then
      echo "DRY RUN: Would undo $file_count files from run $run_id"
      echo "  head_before: $head_before"
      echo "  Files:"
      echo "$files_list" | sed 's/^/    /'
      echo ""
      echo "Then retry with model: ${model_override:-$(echo "$run" | jq -r '.model')}"
      exit 0
    fi

    # Stale-file safety check
    if [[ "$force" != true ]]; then
      local head_after
      head_after="$(echo "$run" | jq -r '.head_after // ""')"
      if [[ -n "$head_after" ]]; then
        local dirty_files
        dirty_files="$(echo "$files_list" | while IFS= read -r f; do
          [[ -z "$f" ]] && continue
          if git diff --quiet "$head_after" -- "$f" 2>/dev/null; then :; else echo "$f"; fi
        done)"
        if [[ -n "$dirty_files" ]]; then
          echo "WARNING: These files have been modified since the original run:" >&2
          echo "$dirty_files" | sed 's/^/  /' >&2
          echo "Use --force to proceed anyway." >&2
          exit 1
        fi
      fi
    fi

    # Confirm in non-interactive contexts
    if [[ "$yes" != true ]] && [[ ! -t 0 ]]; then
      echo "ERROR: --undo-first in non-interactive context requires --yes" >&2
      exit 1
    fi

    _info "Reverting $file_count files to head_before=$head_before..."
    echo "$files_list" | while IFS= read -r f; do
      [[ -z "$f" ]] && continue
      git checkout "$head_before" -- "$f" 2>/dev/null || echo "  Warning: could not revert $f" >&2
    done
  fi

  if [[ "$dry_run" == true ]]; then
    echo "DRY RUN: Would retry run $run_id"
    echo "  Model: ${model_override:-$(echo "$run" | jq -r '.model')}"
    echo "  Prompt: ${prompt_override:-(from original input.md)}"
    exit 0
  fi

  # Read original params
  local params_file="$log_dir/params.json"
  if [[ ! -f "$params_file" ]]; then
    _error "no_params" "Cannot find params.json for run $run_id"
    exit 1
  fi

  local orig_model orig_prompt orig_skills orig_variant orig_agent
  orig_model="$(jq -r '.model' "$params_file")"
  orig_variant="$(jq -r '.variant // .effort // "high"' "$params_file")"
  orig_skills="$(jq -r '.skills // [] | join(",")' "$params_file")"
  orig_agent="$(jq -r '.agent // empty' "$params_file" 2>/dev/null || echo "")"

  # Read original prompt from input.md
  orig_prompt=""
  if [[ -f "$log_dir/input.md" ]]; then
    orig_prompt="$(cat "$log_dir/input.md")"
  fi

  local target_model="${model_override:-$orig_model}"
  local target_prompt="${prompt_override:-$orig_prompt}"
  local target_skills="${extra_skills:-$orig_skills}"

  # Build run-agent command
  local runner="$(dirname "$0")/run-agent.sh"
  # Export retry metadata so run-agent can pick it up
  export RETRIES_RUN_ID="$run_id"

  local cmd=("$runner" --model "$target_model" --variant "$orig_variant")
  [[ -n "$orig_agent" ]] && cmd+=(--agent "$orig_agent")
  [[ -n "$target_skills" ]] && cmd+=(--skills "$target_skills")

  # Pass prompt via stdin to avoid arg length limits
  _info "Retrying run $run_id with model $target_model..."
  echo "$target_prompt" | exec "${cmd[@]}"
}

cmd_maintain() {
  local compact=false before_days=90 dry_run=false yes=false

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --compact)      compact=true; shift ;;
      --before-days)  before_days="$2"; shift 2 ;;
      --dry-run)      dry_run=true; shift ;;
      --yes)          yes=true; shift ;;
      *) echo "ERROR: Unknown maintain option: $1" >&2; exit 1 ;;
    esac
  done

  if [[ "$compact" != true ]]; then
    echo "Usage: run-index.sh maintain --compact [--before-days N] [--dry-run] [--yes]"
    exit 1
  fi

  local cutoff_date
  cutoff_date="$(date -u -d "$before_days days ago" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || \
                 date -u -v-"${before_days}d" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "")"

  if [[ -z "$cutoff_date" ]]; then
    echo "ERROR: Could not compute cutoff date" >&2
    exit 2
  fi

  local derived
  derived="$(_build_derived_view)"

  # Find finalized runs older than cutoff
  local to_archive
  to_archive="$(echo "$derived" | jq --arg cutoff "$cutoff_date" '[.[] | select(.effective_status != "running" and .started_at < $cutoff)]')"
  local archive_count
  archive_count="$(echo "$to_archive" | jq 'length')"

  local active_count
  active_count="$(echo "$derived" | jq --arg cutoff "$cutoff_date" '[.[] | select(.effective_status == "running" or .started_at >= $cutoff)] | length')"

  if [[ "$dry_run" == true ]]; then
    if [[ "$JSON_MODE" == true ]]; then
      _json_ok "maintain" "{\"dry_run\":true,\"archive_count\":$archive_count,\"active_count\":$active_count,\"cutoff\":\"$cutoff_date\"}"
    else
      echo "DRY RUN: Would archive $archive_count finalized runs older than $cutoff_date"
      echo "  Active runs remaining: $active_count"
    fi
    exit 0
  fi

  if [[ "$archive_count" -eq 0 ]]; then
    echo "Nothing to archive."
    exit 0
  fi

  if [[ "$yes" != true ]] && [[ ! -t 0 ]]; then
    echo "ERROR: Mutating maintain in non-interactive context requires --yes" >&2
    exit 1
  fi

  # Archive: extract run_ids to archive, then split the raw index
  local archive_date
  archive_date="$(date -u +"%Y%m%d")"
  local archive_dir="$ORCHESTRATE_ROOT/index/archive"
  local archive_file="$archive_dir/runs-$archive_date.jsonl"
  mkdir -p "$archive_dir"

  local archive_ids
  archive_ids="$(echo "$to_archive" | jq -r '.[].run_id')"

  # Split raw index file into archive and active
  local tmp_archive tmp_active
  tmp_archive="$(mktemp)"
  tmp_active="$(mktemp)"
  trap 'rm -f "$tmp_archive" "$tmp_active"' EXIT

  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    local line_run_id
    line_run_id="$(echo "$line" | jq -r '.run_id // empty' 2>/dev/null || echo "")"
    if echo "$archive_ids" | grep -qF "$line_run_id"; then
      echo "$line" >> "$tmp_archive"
    else
      echo "$line" >> "$tmp_active"
    fi
  done < "$INDEX_FILE"

  # Write archive and replace active index
  cat "$tmp_archive" >> "$archive_file"
  mv "$tmp_active" "$INDEX_FILE"

  if [[ "$JSON_MODE" == true ]]; then
    _json_ok "maintain" "{\"archived_rows\":$archive_count,\"active_count\":$active_count,\"archive_file\":\"$archive_file\"}"
  else
    echo "Archived $archive_count runs to $archive_file"
    echo "Active runs remaining: $active_count"
  fi
}

# ─── Main ─────────────────────────────────────────────────────────────────────

# Parse global flags first
ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --json)     JSON_MODE=true; shift ;;
    --no-color) NO_COLOR=true; shift ;;
    --quiet)    QUIET=true; shift ;;
    --repo)     REPO_ROOT="$2"; ORCHESTRATE_ROOT="$2/.orchestrate"; INDEX_FILE="$2/.orchestrate/index/runs.jsonl"; shift 2 ;;
    *)          ARGS+=("$1"); shift ;;
  esac
done

set -- "${ARGS[@]}"

COMMAND="${1:-help}"
shift || true

_require_jq

case "$COMMAND" in
  list)     _require_index; cmd_list "$@" ;;
  show)     _require_index; cmd_show "$@" ;;
  report)   _require_index; cmd_report "$@" ;;
  logs)     _require_index; cmd_logs "$@" ;;
  files)    _require_index; cmd_files "$@" ;;
  stats)    _require_index; cmd_stats "$@" ;;
  continue) _require_index; cmd_continue "$@" ;;
  retry)    _require_index; cmd_retry "$@" ;;
  maintain) _require_index; cmd_maintain "$@" ;;
  help)
    cat <<'EOF'
Usage: run-index.sh <command> [options]

Commands:
  list                     List runs with filtering and pagination
  show <run-ref>           One-run metadata summary
  report <run-ref>         Print report content
  logs <run-ref>           Paginated log browsing
  files <run-ref>          Print touched files
  stats                    Aggregate statistics
  continue <run-ref>       Continue a previous run's session
  retry <run-ref>          Re-run with same or overridden params
  maintain                 Archive/compact old index entries

Run references: full ID, unique prefix (8+ chars), @latest, @last-failed, @last-completed

Global flags:
  --json          Machine-readable JSON output
  --no-color      Plain text
  --quiet         Suppress non-essential output
  --repo <path>   Target repository root
EOF
    ;;
  *)
    echo "ERROR: Unknown command: $COMMAND" >&2
    echo "Run 'run-index.sh help' for usage." >&2
    exit 1
    ;;
esac
