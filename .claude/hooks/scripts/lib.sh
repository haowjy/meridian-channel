#!/usr/bin/env bash
# lib.sh — Shared helpers for orchestrate hooks.
#
# Sourced by hook scripts. Provides project-root detection and hook-root
# resolution.

# find_project_root — walk up from CWD (or $1) looking for .git
find_project_root() {
  local dir="${1:-$PWD}"
  while [[ "$dir" != "/" ]]; do
    if [[ -d "$dir/.git" || -f "$dir/.git" ]]; then
      echo "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

# get_hook_root — resolve the hooks/ dir via BASH_SOURCE of the calling script
get_hook_root() {
  local caller="${BASH_SOURCE[1]}"
  local scripts_dir
  scripts_dir="$(cd "$(dirname "$caller")" && pwd)"
  # scripts/ is one level below hooks/
  dirname "$scripts_dir"
}
