#!/usr/bin/env bash
# load-model-guidance.sh — resolve model-guidance resources with override precedence.
#
# Precedence (custom replaces default):
#   1) If references/model-guidance/*.md files exist (excluding README.md),
#      concatenate those in bytewise-lexicographic order.
#   2) Otherwise, load references/default-model-guidance.md.
#
# Usage:
#   scripts/load-model-guidance.sh [--mode concat|paths]
#   scripts/load-model-guidance.sh                 # default: concat

set -euo pipefail

MODE="concat"

usage() {
  cat <<'EOF'
Usage: scripts/load-model-guidance.sh [--mode concat|paths]

Modes:
  concat   Concatenate selected guidance files to stdout (default)
  paths    Print selected guidance file paths, one per line
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      [[ $# -lt 2 ]] && { echo "ERROR: --mode requires a value" >&2; usage; exit 1; }
      MODE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

case "$MODE" in
  concat|paths) ;;
  *)
    echo "ERROR: Unsupported mode '$MODE' (expected concat|paths)" >&2
    exit 1
    ;;
esac

# Resolve through symlinks for portability.
_source="${BASH_SOURCE[0]}"
while [[ -L "$_source" ]]; do
  _dir="$(cd "$(dirname "$_source")" && pwd -P)"
  _source="$(readlink "$_source")"
  [[ "$_source" != /* ]] && _source="$_dir/$_source"
done
SCRIPT_DIR="$(cd "$(dirname "$_source")" && pwd -P)"
REF_DIR="$(cd "$SCRIPT_DIR/.." && pwd -P)/references"
DEFAULT_FILE="$REF_DIR/default-model-guidance.md"
CUSTOM_DIR="$REF_DIR/model-guidance"

declare -a selected=()
custom_found=false

# Concatenate custom files (excluding README.md)
if [[ -d "$CUSTOM_DIR" ]]; then
  while IFS= read -r f; do
    [[ -n "$f" ]] || continue
    local_name="$(basename "$f")"
    [[ "$local_name" == "README.md" ]] && continue
    selected+=("$f")
    custom_found=true
  done < <(find "$CUSTOM_DIR" -maxdepth 1 -type f -name '*.md' | sort)
fi

if [[ "$custom_found" != true ]]; then
  if [[ -f "$DEFAULT_FILE" ]]; then
    selected+=("$DEFAULT_FILE")
  else
    echo "ERROR: Default model guidance not found: $DEFAULT_FILE" >&2
    exit 1
  fi
fi

if [[ "$MODE" == "paths" ]]; then
  printf '%s\n' "${selected[@]}"
  exit 0
fi

for i in "${!selected[@]}"; do
  cat "${selected[$i]}"
  if [[ "$i" -lt $((${#selected[@]} - 1)) ]]; then
    printf '\n\n'
  fi
done
