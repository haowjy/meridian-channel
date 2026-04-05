#!/usr/bin/env bash
# Validate Mermaid diagrams in markdown files.
# Usage:
#   check-mermaid.sh                    # all .md files recursively from cwd
#   check-mermaid.sh path/to/file.md    # specific file(s)
#   check-mermaid.sh docs/features/     # specific directory
#
# Requires: npx @mermaid-js/mermaid-cli (auto-installed on first run)

set -euo pipefail

# Use current working directory as root for relative paths
ROOT_DIR="$(pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Temp directory for extracted diagrams
WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

# Collect files to check
files=()
if [ $# -eq 0 ]; then
  # Default: all .md files recursively from cwd
  while IFS= read -r -d '' f; do
    files+=("$f")
  done < <(find "$ROOT_DIR" -name '*.md' -not -path '*/node_modules/*' -not -path '*/.git/*' -print0 2>/dev/null || true)
else
  for arg in "$@"; do
    if [ -d "$arg" ]; then
      while IFS= read -r -d '' f; do
        files+=("$f")
      done < <(find "$arg" -name '*.md' -not -path '*/node_modules/*' -print0)
    elif [ -f "$arg" ]; then
      files+=("$arg")
    else
      echo -e "${YELLOW}WARN: skipping '$arg' (not found)${NC}"
    fi
  done
fi

if [ ${#files[@]} -eq 0 ]; then
  echo "No markdown files found."
  exit 0
fi

# Extract mermaid blocks from a file.
# Outputs: one temp file per block, prints the temp file path + source line number.
extract_mermaid_blocks() {
  local file="$1"
  local in_block=false
  local block_start=0
  local block_num=0
  local block_file=""
  local line_num=0

  while IFS= read -r line || [[ -n "$line" ]]; do
    line_num=$((line_num + 1))

    if [[ "$line" =~ ^'```mermaid' ]] && [ "$in_block" = false ]; then
      in_block=true
      block_start=$line_num
      block_num=$((block_num + 1))
      block_file="$WORK_DIR/block_${block_num}.mmd"
      > "$block_file"
      continue
    fi

    if [[ "$line" =~ ^'```' ]] && [ "$in_block" = true ]; then
      in_block=false
      echo "${block_file}:${block_start}"
      continue
    fi

    if [ "$in_block" = true ]; then
      echo "$line" >> "$block_file"
    fi
  done < "$file"
}

total=0
passed=0
failed=0
failed_details=()

for file in "${files[@]}"; do
  rel_path="${file#"$ROOT_DIR"/}"

  # Extract blocks
  while IFS= read -r block_info; do
    [ -z "$block_info" ] && continue
    block_file="${block_info%%:*}"
    block_line="${block_info##*:}"
    total=$((total + 1))

    # Validate with mmdc — render to svg to confirm parse succeeds
    if npx --yes @mermaid-js/mermaid-cli -q -i "$block_file" -o "$WORK_DIR/out.svg" 2>"$WORK_DIR/err.txt"; then
      passed=$((passed + 1))
    else
      failed=$((failed + 1))
      # Extract the useful error lines (skip npx boilerplate)
      err_msg=$(grep -v "^npm warn" "$WORK_DIR/err.txt" | head -5)
      failed_details+=("${RED}FAIL${NC}: ${rel_path}:${block_line}")
      if [ -n "$err_msg" ]; then
        failed_details+=("  $err_msg")
      fi
    fi

    # Clean up per-block files
    rm -f "$block_file" "$WORK_DIR/out.svg"
  done < <(extract_mermaid_blocks "$file")
done

echo ""
if [ $total -eq 0 ]; then
  echo "No Mermaid diagrams found."
  exit 0
fi

# Print failures
for detail in "${failed_details[@]}"; do
  echo -e "$detail"
done

if [ $failed -gt 0 ]; then
  echo ""
fi

if [ $failed -eq 0 ]; then
  echo -e "${GREEN}OK${NC}: all $total Mermaid diagrams valid"
else
  echo -e "${RED}FAILED${NC}: $failed/$total diagrams have errors"
  exit 1
fi
