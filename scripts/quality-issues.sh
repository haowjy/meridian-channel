#!/usr/bin/env bash
# List open quality/immediate GitHub issues for triage.

set -euo pipefail

REPO="meridian-flow/meridian-cli"
LIMIT="${QUALITY_ISSUES_LIMIT:-200}"
COMMON_SEARCH="-label:future"

usage() {
  cat <<'USAGE'
Usage:
  scripts/quality-issues.sh [--limit N]

Lists open meridian-flow/meridian-cli issues for the quality/immediate board.
Excludes issues labelled `future`.

Environment:
  QUALITY_ISSUES_LIMIT  Max issues per group (default: 200)
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --limit)
      [[ $# -ge 2 ]] || { echo "missing value for --limit" >&2; exit 2; }
      LIMIT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

print_group() {
  local title="$1"
  local label="$2"
  local search="$COMMON_SEARCH"

  if [[ -n "$label" ]]; then
    search="$search label:$label"
  fi

  echo
  echo "==> $title"
  gh issue list \
    --repo "$REPO" \
    --state open \
    --limit "$LIMIT" \
    --search "$search" \
    --json number,title,labels,url \
    --template '{{if not .}}  (none){{"\n"}}{{else}}{{range .}}{{printf "  #%-5v %s\n" .number .title}}{{printf "         labels: "}}{{range $i, $l := .labels}}{{if $i}}, {{end}}{{.name}}{{end}}{{printf "\n         %s\n" .url}}{{end}}{{end}}'
}

print_other_group() {
  local search="$COMMON_SEARCH -label:bug -label:unexpected -label:tech-debt -label:improvement -label:enhancement"

  echo
  echo "==> Other immediate"
  gh issue list \
    --repo "$REPO" \
    --state open \
    --limit "$LIMIT" \
    --search "$search" \
    --json number,title,labels,url \
    --template '{{if not .}}  (none){{"\n"}}{{else}}{{range .}}{{printf "  #%-5v %s\n" .number .title}}{{printf "         labels: "}}{{range $i, $l := .labels}}{{if $i}}, {{end}}{{.name}}{{end}}{{printf "\n         %s\n" .url}}{{end}}{{end}}'
}

echo "Quality/immediate issues for $REPO"
echo "Excluding label: future"

print_group "Bugs" "bug"
print_group "Unexpected" "unexpected"
print_group "Tech debt" "tech-debt"
print_group "Improvements" "improvement"
print_group "Enhancements" "enhancement"
print_other_group
