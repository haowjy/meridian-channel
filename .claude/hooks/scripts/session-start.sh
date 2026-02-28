#!/usr/bin/env bash
# session-start.sh — SessionStart hook (packaged with orchestrate plugin)
#
# Reloads sticky skills from the previous session after context loss.
#
# Triggers:
# - compact: context compressed, skills may be lost.
# - clear: only if the previous session ended with ExitPlanMode (plan acceptance).
#
# Input: JSON on stdin with { transcript_path, source, cwd, ... }
# Output: JSON with additionalContext on stdout (exit 0)

set -euo pipefail

# --- Source shared helpers ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

usage() {
  cat <<'USAGE'
Usage: session-start.sh

Reads hook payload JSON from stdin and emits optional additionalContext JSON.
USAGE
}

for arg in "$@"; do
  case "$arg" in
    -h|--help)
      usage
      exit 0
      ;;
  esac
done

# ============================================================================
# Parse hook input
# ============================================================================
INPUT=$(cat)
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty')
SOURCE=$(echo "$INPUT" | jq -r '.source // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')

# Only fire on compact or clear. startup: no prior session. resume: skills already in context.
case "$SOURCE" in
  compact|clear) ;;
  *) exit 0 ;;
esac

# Resolve project root from CWD
PROJECT_ROOT="$(find_project_root "${CWD:-$PWD}")" || exit 0

# Optional sticky-skill allowlist (repo-local customization).
ALLOWLIST_FILE="$PROJECT_ROOT/.orchestrate/config/sticky-skills.json"
declare -A ALLOWED_SKILLS=()
if [[ -f "$ALLOWLIST_FILE" ]]; then
  if command -v jq >/dev/null 2>&1; then
    while IFS= read -r skill || [[ -n "$skill" ]]; do
      skill="$(echo "$skill" | tr '[:upper:]' '[:lower:]' | xargs)"
      skill="${skill#/}"  # Allow "/skill" syntax in file.
      [[ -n "$skill" ]] || continue
      ALLOWED_SKILLS["$skill"]=1
    done < <(jq -r '.allowlist // [] | .[] | select(type=="string")' "$ALLOWLIST_FILE" 2>/dev/null || true)
  fi
fi

# On clear, use the previous transcript saved by session-end.sh.
# Only reload if the previous session ended with ExitPlanMode (plan acceptance).
# Manual /clear has no ExitPlanMode — treated as intentional reset.
BREADCRUMB="$PROJECT_ROOT/.orchestrate/session/prev-transcript"
if [[ "$SOURCE" == "clear" ]]; then
  if [[ -f "$BREADCRUMB" ]]; then
    PREV_TRANSCRIPT="$(cat "$BREADCRUMB")"
    rm -f "$BREADCRUMB"
    # Check last ~20 lines for ExitPlanMode — plan acceptance signal
    if [[ -f "$PREV_TRANSCRIPT" ]] && tail -20 "$PREV_TRANSCRIPT" | grep -qE '"name"\s*:\s*"ExitPlanMode"' 2>/dev/null; then
      TRANSCRIPT_PATH="$PREV_TRANSCRIPT"
    else
      exit 0  # Manual /clear — no reload
    fi
  else
    exit 0  # No breadcrumb — no reload
  fi
fi

# Need a transcript to scan
if [[ -z "$TRANSCRIPT_PATH" || ! -f "$TRANSCRIPT_PATH" ]]; then
  exit 0
fi

# For compact hooks, only scan the most recent segment:
# previous SessionStart:compact -> current SessionStart:compact.
SCOPED_TRANSCRIPT="$TRANSCRIPT_PATH"
TMP_SCOPE=""
cleanup_scope() {
  if [[ -n "$TMP_SCOPE" && -f "$TMP_SCOPE" ]]; then
    rm -f "$TMP_SCOPE"
  fi
}
trap cleanup_scope EXIT

compute_compact_scope() {
  local transcript_path="$1"
  awk '
    /"hookEvent":"SessionStart"/ && /"hookName":"SessionStart:compact"/ {
      prev=last
      last=NR
    }
    END {
      if (last == 0) {
        print "1 0"
      } else if (prev == 0) {
        print "1 " (last - 1)
      } else {
        print (prev + 1) " " (last - 1)
      }
    }
  ' "$transcript_path"
}

if [[ "$SOURCE" == "compact" ]]; then
  read -r SCOPE_START SCOPE_END < <(compute_compact_scope "$TRANSCRIPT_PATH")
  if [[ -n "${SCOPE_START:-}" && -n "${SCOPE_END:-}" ]] && (( SCOPE_END >= SCOPE_START )); then
    TMP_SCOPE="$(mktemp)"
    sed -n "${SCOPE_START},${SCOPE_END}p" "$TRANSCRIPT_PATH" > "$TMP_SCOPE"
    SCOPED_TRANSCRIPT="$TMP_SCOPE"
  fi
fi

# ============================================================================
# Extract and replay sticky skill events from transcript
# ============================================================================
extract_skill_events() {
  local transcript_path="$1"
  awk '
    function emit(action, value, token) {
      token = value
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", token)
      gsub(/^\/+/, "", token)
      if (token == "") {
        return
      }
      seq += 1
      printf "%d\t%d\t%s\t%s\n", NR, seq, action, tolower(token)
    }

    {
      line = $0

      rest = line
      while (match(rest, /Launching skill:[[:space:]]*[A-Za-z0-9._-]+/)) {
        token = substr(rest, RSTART, RLENGTH)
        sub(/^Launching skill:[[:space:]]*/, "", token)
        emit("add", token)
        rest = substr(rest, RSTART + RLENGTH)
      }

      rest = line
      while (match(rest, /Base directory for this skill:.*skills\/[A-Za-z0-9._-]+/)) {
        token = substr(rest, RSTART, RLENGTH)
        sub(/^.*skills\//, "", token)
        emit("add", token)
        rest = substr(rest, RSTART + RLENGTH)
      }

      if (line ~ /"name"[[:space:]]*:[[:space:]]*"Skill"/) {
        rest = line
        while (match(rest, /"skill"[[:space:]]*:[[:space:]]*"[A-Za-z0-9._-]+"/)) {
          token = substr(rest, RSTART, RLENGTH)
          sub(/^"skill"[[:space:]]*:[[:space:]]*"/, "", token)
          sub(/"$/, "", token)
          emit("add", token)
          rest = substr(rest, RSTART + RLENGTH)
        }
      }

      rest = line
      while (match(rest, /\/unpin[[:space:]]+[A-Za-z0-9._-]+/)) {
        token = substr(rest, RSTART, RLENGTH)
        sub(/^\/unpin[[:space:]]+/, "", token)
        emit("remove", token)
        rest = substr(rest, RSTART + RLENGTH)
      }

      rest = line
      while (match(rest, /[Uu]npin[[:space:]]+skill:[[:space:]]*[A-Za-z0-9._-]+/)) {
        token = substr(rest, RSTART, RLENGTH)
        sub(/^[Uu]npin[[:space:]]+skill:[[:space:]]*/, "", token)
        emit("remove", token)
        rest = substr(rest, RSTART + RLENGTH)
      }

      rest = line
      while (match(rest, /SKILL_UNPIN:[A-Za-z0-9._-]+/)) {
        token = substr(rest, RSTART, RLENGTH)
        sub(/^SKILL_UNPIN:/, "", token)
        emit("remove", token)
        rest = substr(rest, RSTART + RLENGTH)
      }
    }
  ' "$transcript_path"
}

declare -A ACTIVE_SKILLS=()
declare -A SEEN_SKILLS=()
ORDERED_SKILLS=()

while IFS=$'\t' read -r _line _seq action skill; do
  [[ -n "$skill" ]] || continue
  case "$action" in
    add)
      ACTIVE_SKILLS["$skill"]=1
      if [[ -z "${SEEN_SKILLS[$skill]+x}" ]]; then
        ORDERED_SKILLS+=("$skill")
        SEEN_SKILLS["$skill"]=1
      fi
      ;;
    remove)
      unset 'ACTIVE_SKILLS[$skill]'
      ;;
  esac
done < <(extract_skill_events "$SCOPED_TRANSCRIPT")

DETECTED_SKILLS=()
for skill in "${ORDERED_SKILLS[@]}"; do
  if [[ -n "${ACTIVE_SKILLS[$skill]+x}" ]]; then
    if [[ ${#ALLOWED_SKILLS[@]} -gt 0 && -z "${ALLOWED_SKILLS[$skill]+x}" ]]; then
      continue
    fi
    DETECTED_SKILLS+=("$skill")
  fi
done

if [[ ${#DETECTED_SKILLS[@]} -eq 0 ]]; then
  exit 0
fi

# ============================================================================
# Check for active orchestration session (non-complete) as extra context
# ============================================================================
ACTIVE_PLAN=""
SESSION_DIR="$PROJECT_ROOT/.orchestrate/session/plans"
if [[ -d "$SESSION_DIR" ]]; then
  while IFS= read -r handoff; do
    if [[ -f "$handoff" ]] && ! grep -q "PLAN COMPLETE" "$handoff" 2>/dev/null; then
      ACTIVE_PLAN=$(echo "$handoff" | sed "s|$SESSION_DIR/||" | sed 's|/handoffs/.*||')
      break
    fi
  done < <(find "$SESSION_DIR" -name "latest.md" -type f 2>/dev/null | sort -r)
fi

# ============================================================================
# Build additionalContext
# ============================================================================
LINES=()
LINES+=("**Sticky skills from previous session — load these before proceeding:**")
for skill in "${DETECTED_SKILLS[@]}"; do
  LINES+=("- \`/$skill\` remains in the sticky reload set from the previous conversation.")
done

if [[ -n "$ACTIVE_PLAN" ]]; then
  LINES+=("")
  LINES+=("**Active orchestration plan:** \`$ACTIVE_PLAN\` (not yet complete). Check handoff at \`.orchestrate/session/plans/$ACTIVE_PLAN/handoffs/latest.md\`.")
fi

# Join lines
CONTEXT=""
for line in "${LINES[@]}"; do
  CONTEXT+="$line\n"
done

jq -n --arg ctx "$(echo -e "$CONTEXT")" '{ "additionalContext": $ctx }'
