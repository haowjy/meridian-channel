#!/usr/bin/env bash
# load-skill-policy.sh — resolve orchestrate skill policy files with override precedence.
#
# Precedence:
#   1) references/*.md except default.md (if any exist)
#   2) references/default.md
#
# Usage:
#   scripts/load-skill-policy.sh [--mode concat|files|skills]
#   scripts/load-skill-policy.sh                 # default: concat

set -euo pipefail

MODE="concat"

usage() {
  cat <<'EOF'
Usage: scripts/load-skill-policy.sh [--mode concat|files|skills]

Modes:
  concat   Concatenate selected policy files to stdout (default)
  files    Print selected policy file paths, one per line
  skills   Print normalized skill names, one per line (deduped, stable order)
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
  concat|files|skills) ;;
  *)
    echo "ERROR: Unsupported mode '$MODE' (expected concat|files|skills)" >&2
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
DEFAULT_FILE="$REF_DIR/default.md"

declare -a selected=()

if [[ -d "$REF_DIR" ]]; then
  while IFS= read -r f; do
    [[ -n "$f" ]] && selected+=("$f")
  done < <(find "$REF_DIR" -maxdepth 1 -type f -name '*.md' ! -name 'default.md' ! -name 'README.md' | sort)
fi

if [[ ${#selected[@]} -eq 0 ]]; then
  if [[ -f "$DEFAULT_FILE" ]]; then
    selected+=("$DEFAULT_FILE")
  else
    echo "ERROR: No policy files found." >&2
    echo "  Checked: $REF_DIR/*.md and $DEFAULT_FILE" >&2
    exit 1
  fi
fi

if [[ "$MODE" == "files" ]]; then
  printf '%s\n' "${selected[@]}"
  exit 0
fi

if [[ "$MODE" == "skills" ]]; then
  # Extract skill names from policy files, then filter to only installed skills.
  # Installed = sibling SKILL.md exists (e.g., ../<skill-name>/SKILL.md).
  SKILLS_BASE="$(cd "$SCRIPT_DIR/../.." && pwd -P)"

  awk '
    {
      line = $0
      sub(/\r$/, "", line)
      sub(/#.*/, "", line)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", line)
      sub(/^[-*+][[:space:]]+/, "", line)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", line)
      if (line == "") next
      if (!seen[line]++) print line
    }
  ' "${selected[@]}" | while IFS= read -r skill_name; do
    if [[ -f "$SKILLS_BASE/$skill_name/SKILL.md" ]]; then
      echo "$skill_name"
    fi
  done
  exit 0
fi

# concat mode (default)
for i in "${!selected[@]}"; do
  cat "${selected[$i]}"
  if [[ "$i" -lt $((${#selected[@]} - 1)) ]]; then
    printf '\n\n'
  fi
done

