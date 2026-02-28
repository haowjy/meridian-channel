#!/usr/bin/env bash
# Extract likely touched files from a single agent run log.
# Uses structured JSON extraction when possible, with text-pattern fallback.
#
# Usage:
#   extract-files-touched.sh <output-log> [output-file] [--nul]
#
# When --nul is passed, output is NUL-delimited (canonical machine-readable format).
# Otherwise output is newline-delimited (human-readable).

set -euo pipefail

OUTPUT_LOG="${1:?Usage: extract-files-touched.sh <output-log> [output-file] [--nul]}"
OUTPUT_FILE="${2:-/dev/stdout}"
NUL_MODE=false
if [[ "${3:-}" == "--nul" ]] || [[ "${2:-}" == "--nul" ]]; then
  NUL_MODE=true
  # If --nul was the second arg, output goes to stdout
  if [[ "${2:-}" == "--nul" ]]; then
    OUTPUT_FILE="/dev/stdout"
  fi
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || echo "$SCRIPT_DIR")"

TMP_TEXT="$(mktemp)"
TMP_RAW_PATHS="$(mktemp)"
TMP_SORTED="$(mktemp)"
trap 'rm -f "$TMP_TEXT" "$TMP_RAW_PATHS" "$TMP_SORTED"' EXIT

# Seed with raw log text (handles non-JSON and error output).
cat "$OUTPUT_LOG" > "$TMP_TEXT"

# If output is JSON or JSONL, flatten all string values for better extraction.
if command -v jq >/dev/null 2>&1; then
  jq -r '.. | strings' "$OUTPUT_LOG" 2>/dev/null >> "$TMP_TEXT" || true
  jq -Rr 'fromjson? | .. | strings' "$OUTPUT_LOG" 2>/dev/null >> "$TMP_TEXT" || true
fi

# Extract candidates from common tool/log formats.
perl -ne '
  while (/\*\*\* (?:Add|Update|Delete) File:\s*([^\r\n]+)/g) { print "$1\n"; }
  while (/\*\*\* Move to:\s*([^\r\n]+)/g) { print "$1\n"; }
  while (/"(?:path|file_path|filepath|filename|target_file|source_file|new_path|old_path|file)"\s*:\s*"((?:\\.|[^"\\])+)"/g) {
    print "$1\n";
  }
  while (/(?:^|[\s`\x22\x27])(\.gitignore|AGENTS\.md|CLAUDE\.md|README\.md)(?=$|[\s`\x22\x27,:;])/g) {
    print "$1\n";
  }
' "$TMP_TEXT" > "$TMP_RAW_PATHS"

# Normalize and filter to repo-relevant paths.
awk -v root="$REPO_ROOT/" '
{
  path = $0
  gsub(/\r/, "", path)
  sub(/^[[:space:]]+/, "", path)
  sub(/[[:space:]]+$/, "", path)

  sub(/\\n.*/, "", path)
  sub(/\\r.*/, "", path)
  gsub(/\\\//, "/", path)
  gsub(/\\\\/, "\\", path)

  gsub(/^["`]+/, "", path)
  gsub(/["`]+$/, "", path)
  sub(/:[0-9]+(:[0-9]+)?$/, "", path)
  sub(/^\.\//, "", path)

  if (index(path, root) == 1) {
    path = substr(path, length(root) + 1)
  }

  if (path == "") next
  if (path ~ /^https?:\/\//) next
  if (path ~ /^[A-Za-z]+:\/\//) next
  if (path ~ /^\/(tmp|dev|proc|sys)\//) next
  if (path ~ /[<>|*?]/) next
  if (path ~ /( \(|\)$)/) next
  if (path ~ /[[:space:]]/) next
  if (path ~ /^(true|false|null)$/) next

  if (path ~ /^\//) next
  if (path ~ /^(node_modules|vendor|\.git|__pycache__|dist|build|target)\//) next

  if (path ~ /\// || path ~ /\.[a-zA-Z0-9]+$/) { print path; next }
}
' "$TMP_RAW_PATHS" | sort -u > "$TMP_SORTED"

# Output in requested format
if [[ "$NUL_MODE" == true ]]; then
  # NUL-delimited output
  tr '\n' '\0' < "$TMP_SORTED" > "$OUTPUT_FILE"
else
  cat "$TMP_SORTED" > "$OUTPUT_FILE"
fi
