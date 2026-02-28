#!/usr/bin/env bash
# scratch.sh — Session-scoped scratch file management.
#
# Usage:
#   scratch.sh write [OPTIONS] [-p "CONTENT" | -f FILE | stdin]
#   scratch.sh list  [OPTIONS]
#   scratch.sh read  <REF>
#
# Session resolution (priority):
#   --session NAME > $SCRATCH_SESSION > $ORCHESTRATE_RUN_ID > adhoc-YYYYMMDD

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─── Helpers ─────────────────────────────────────────────────────────────────

# Find repo root by walking up to .git
_find_repo_root() {
  local dir="${1:-$PWD}"
  while [[ "$dir" != "/" ]]; do
    if [[ -d "$dir/.git" || -f "$dir/.git" ]]; then
      echo "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  echo "$PWD"
}

# Sanitize session name: lowercase, invalid chars → -, reject path traversal
_sanitize_session() {
  local name="$1"
  # Reject absolute paths and traversal
  if [[ "$name" == /* ]] || [[ "$name" == *..* ]]; then
    echo "ERROR: Session name must not contain '..' or start with '/': $name" >&2
    return 1
  fi
  echo "$name" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9._-]/-/g; s/--*/-/g; s/^-//; s/-$//'
}

# Resolve session name from flags/env/fallback
_resolve_session() {
  local explicit="${1:-}"
  if [[ -n "$explicit" ]]; then
    _sanitize_session "$explicit"
  elif [[ -n "${SCRATCH_SESSION:-}" ]]; then
    _sanitize_session "$SCRATCH_SESSION"
  elif [[ -n "${ORCHESTRATE_RUN_ID:-}" ]]; then
    echo "$ORCHESTRATE_RUN_ID"
  else
    echo "adhoc-$(date -u +%Y%m%d)"
  fi
}

# Scratch root: .scratch/ in repo root
_scratch_root() {
  local repo_root
  repo_root="$(_find_repo_root)"
  echo "$repo_root/.scratch"
}

# Generate timestamp-based filename: YYYYMMDDTHHMMSSZ-<tag>-<pid>.<ext>
_generate_filename() {
  local tag="$1" ext="$2"
  local ts
  ts="$(date -u +"%Y%m%dT%H%M%SZ")"
  echo "${ts}-${tag}-$$.${ext}"
}

# Update session-local latest symlink
_update_latest() {
  local session_dir="$1" filename="$2"
  local link="$session_dir/latest"
  local tmp="$session_dir/.latest-tmp-$$"
  ln -sf "$filename" "$tmp"
  mv -f "$tmp" "$link"
}

# ─── Write ───────────────────────────────────────────────────────────────────

_usage_write() {
  cat <<'EOF'
Usage: scratch.sh write [OPTIONS] [-p "CONTENT" | -f FILE | stdin]

Options:
  --session NAME   Session name (default: auto-detect)
  --tag TAG        Auto-generate filename with tag (e.g. --tag research)
  --ext EXT        File extension for --tag mode (default: md)
  --append         Append instead of overwrite
  --json           Output JSON instead of plain path
  -p "CONTENT"     Inline content
  -f FILE          Copy file content
  <path>           Explicit relative path (mutually exclusive with --tag)
  -h, --help       Show this help
EOF
}

cmd_write() {
  local session="" tag="" ext="md" append=false json_output=false
  local content="" content_file="" explicit_path=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --session)  session="$2"; shift 2 ;;
      --tag)      tag="$2"; shift 2 ;;
      --ext)      ext="$2"; shift 2 ;;
      --append)   append=true; shift ;;
      --json)     json_output=true; shift ;;
      -p)         content="$2"; shift 2 ;;
      -f)         content_file="$2"; shift 2 ;;
      -h|--help)  _usage_write; return 0 ;;
      -*)         echo "ERROR: Unknown flag: $1" >&2; return 1 ;;
      *)
        # Positional = explicit path
        if [[ -n "$explicit_path" ]]; then
          echo "ERROR: Unexpected argument: $1" >&2
          return 1
        fi
        explicit_path="$1"; shift ;;
    esac
  done

  # Validate: tag and explicit_path are mutually exclusive
  if [[ -n "$tag" ]] && [[ -n "$explicit_path" ]]; then
    echo "ERROR: --tag and explicit path are mutually exclusive." >&2
    return 1
  fi
  if [[ -z "$tag" ]] && [[ -z "$explicit_path" ]]; then
    echo "ERROR: Provide --tag TAG or an explicit path." >&2
    return 1
  fi

  # Resolve session and build target path
  local resolved_session
  resolved_session="$(_resolve_session "$session")" || return 1

  local scratch_root session_dir filename dest
  scratch_root="$(_scratch_root)"
  session_dir="$scratch_root/$resolved_session"

  if [[ -n "$tag" ]]; then
    local sanitized_tag
    sanitized_tag="$(echo "$tag" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9._-]/-/g; s/--*/-/g; s/^-//; s/-$//')"
    filename="$(_generate_filename "$sanitized_tag" "$ext")"
    dest="$session_dir/$filename"
  else
    # Guard against path traversal in explicit path
    if [[ "$explicit_path" == /* ]] || [[ "$explicit_path" == *..* ]]; then
      echo "ERROR: Path must be relative and not contain '..': $explicit_path" >&2
      return 1
    fi
    filename="$explicit_path"
    dest="$session_dir/$explicit_path"
  fi

  # Ensure parent directory exists
  mkdir -p "$(dirname "$dest")"

  # Write content
  if [[ -n "$content_file" ]]; then
    if [[ ! -f "$content_file" ]]; then
      echo "ERROR: File not found: $content_file" >&2
      return 1
    fi
    if [[ "$append" == true ]]; then
      cat "$content_file" >> "$dest"
    else
      cp "$content_file" "$dest"
    fi
  elif [[ -n "$content" ]]; then
    if [[ "$append" == true ]]; then
      printf '%s\n' "$content" >> "$dest"
    else
      printf '%s\n' "$content" > "$dest"
    fi
  else
    # Read from stdin
    if [[ "$append" == true ]]; then
      cat >> "$dest"
    else
      cat > "$dest"
    fi
  fi

  # Update latest symlink (use basename for tag mode, full relative for explicit)
  _update_latest "$session_dir" "$filename"

  # Output
  if [[ "$json_output" == true ]]; then
    printf '{"path":"%s","session":"%s"}\n' "$dest" "$resolved_session"
  else
    echo "$dest"
  fi
}

# ─── List ────────────────────────────────────────────────────────────────────

_usage_list() {
  cat <<'EOF'
Usage: scratch.sh list [OPTIONS]

Options:
  --session NAME   List files in specific session
  --all            List all sessions with file counts
  --ext EXT        Filter by file extension
  --last N         Show only last N entries
  --json           Machine-readable output
  -h, --help       Show this help

Default: list files in latest session.
EOF
}

cmd_list() {
  local session="" show_all=false ext_filter="" last_n=0 json_output=false

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --session)  session="$2"; shift 2 ;;
      --all)      show_all=true; shift ;;
      --ext)      ext_filter="$2"; shift 2 ;;
      --last)     last_n="$2"; shift 2 ;;
      --json)     json_output=true; shift ;;
      -h|--help)  _usage_list; return 0 ;;
      -*)         echo "ERROR: Unknown flag: $1" >&2; return 1 ;;
      *)          echo "ERROR: Unexpected argument: $1" >&2; return 1 ;;
    esac
  done

  local scratch_root
  scratch_root="$(_scratch_root)"

  if [[ ! -d "$scratch_root" ]]; then
    echo "No scratch files found." >&2
    return 0
  fi

  if [[ "$show_all" == true ]]; then
    _list_all_sessions "$scratch_root" "$json_output"
    return 0
  fi

  # Resolve which session to list
  local target_session
  if [[ -n "$session" ]]; then
    target_session="$(_resolve_session "$session")" || return 1
  else
    # Find latest: most recently modified session dir
    target_session="$(_find_latest_session "$scratch_root")" || {
      echo "No sessions found." >&2
      return 0
    }
  fi

  local session_dir="$scratch_root/$target_session"
  if [[ ! -d "$session_dir" ]]; then
    echo "Session not found: $target_session" >&2
    return 1
  fi

  _list_session_files "$session_dir" "$target_session" "$ext_filter" "$last_n" "$json_output"
}

_find_latest_session() {
  local scratch_root="$1"
  # Find most recently modified session directory
  local latest=""
  local latest_mtime=0
  for dir in "$scratch_root"/*/; do
    [[ -d "$dir" ]] || continue
    local name
    name="$(basename "$dir")"
    local mtime
    mtime="$(stat -c %Y "$dir" 2>/dev/null || stat -f %m "$dir" 2>/dev/null || echo 0)"
    if [[ "$mtime" -gt "$latest_mtime" ]]; then
      latest_mtime="$mtime"
      latest="$name"
    fi
  done
  if [[ -z "$latest" ]]; then
    return 1
  fi
  echo "$latest"
}

_list_all_sessions() {
  local scratch_root="$1" json_output="$2"

  if [[ "$json_output" == true ]]; then
    printf '['
    local first=true
    for dir in "$scratch_root"/*/; do
      [[ -d "$dir" ]] || continue
      local name count
      name="$(basename "$dir")"
      count="$(find "$dir" -maxdepth 1 -type f ! -name 'latest' ! -name '.*' 2>/dev/null | wc -l)"
      [[ "$first" == true ]] && first=false || printf ','
      printf '{"session":"%s","files":%d}' "$name" "$count"
    done
    printf ']\n'
  else
    for dir in "$scratch_root"/*/; do
      [[ -d "$dir" ]] || continue
      local name count
      name="$(basename "$dir")"
      count="$(find "$dir" -maxdepth 1 -type f ! -name 'latest' ! -name '.*' 2>/dev/null | wc -l)"
      printf '  %-40s %d files\n' "$name" "$count"
    done
  fi
}

_list_session_files() {
  local session_dir="$1" session_name="$2" ext_filter="$3" last_n="$4" json_output="$5"

  # Collect files (sorted lexicographically = chronologically for timestamped names)
  local -a files=()
  while IFS= read -r -d '' f; do
    local base
    base="$(basename "$f")"
    [[ "$base" == "latest" || "$base" == .* ]] && continue
    if [[ -n "$ext_filter" ]]; then
      [[ "$base" == *."$ext_filter" ]] || continue
    fi
    files+=("$base")
  done < <(find "$session_dir" -maxdepth 1 -type f -print0 2>/dev/null | sort -z)

  # Apply --last
  if [[ "$last_n" -gt 0 ]] && [[ ${#files[@]} -gt "$last_n" ]]; then
    files=("${files[@]: -$last_n}")
  fi

  if [[ ${#files[@]} -eq 0 ]]; then
    echo "No files in session: $session_name" >&2
    return 0
  fi

  if [[ "$json_output" == true ]]; then
    printf '{"session":"%s","files":[' "$session_name"
    local first=true
    for f in "${files[@]}"; do
      [[ "$first" == true ]] && first=false || printf ','
      printf '"%s"' "$f"
    done
    printf ']}\n'
  else
    echo "session: $session_name (${#files[@]} files)"
    for f in "${files[@]}"; do
      echo "  $f"
    done
  fi
}

# ─── Read ────────────────────────────────────────────────────────────────────

_usage_read() {
  cat <<'EOF'
Usage: scratch.sh read [OPTIONS] <REF>

REF can be:
  @latest          Latest file in latest session
  <filename>       Exact filename in latest session
  <prefix>         Prefix match in latest session

Options:
  --session NAME   Read from specific session
  -h, --help       Show this help
EOF
}

cmd_read() {
  local session="" ref=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --session)  session="$2"; shift 2 ;;
      -h|--help)  _usage_read; return 0 ;;
      -*)         echo "ERROR: Unknown flag: $1" >&2; return 1 ;;
      *)
        if [[ -n "$ref" ]]; then
          echo "ERROR: Unexpected argument: $1" >&2
          return 1
        fi
        ref="$1"; shift ;;
    esac
  done

  if [[ -z "$ref" ]]; then
    echo "ERROR: Provide a file reference (filename, prefix, or @latest)." >&2
    return 1
  fi

  local scratch_root
  scratch_root="$(_scratch_root)"

  # Resolve session
  local target_session
  if [[ -n "$session" ]]; then
    target_session="$(_resolve_session "$session")" || return 1
  else
    target_session="$(_find_latest_session "$scratch_root")" || {
      echo "ERROR: No sessions found." >&2
      return 1
    }
  fi

  local session_dir="$scratch_root/$target_session"
  if [[ ! -d "$session_dir" ]]; then
    echo "ERROR: Session not found: $target_session" >&2
    return 1
  fi

  # Resolve ref
  local target_file=""
  if [[ "$ref" == "@latest" ]]; then
    local link="$session_dir/latest"
    if [[ -L "$link" ]]; then
      local link_target
      link_target="$(readlink "$link")"
      target_file="$session_dir/$link_target"
    else
      echo "ERROR: No latest symlink in session: $target_session" >&2
      return 1
    fi
  else
    # Try exact match first
    if [[ -f "$session_dir/$ref" ]]; then
      target_file="$session_dir/$ref"
    else
      # Prefix match
      local -a matches=()
      for f in "$session_dir"/"$ref"*; do
        [[ -f "$f" ]] && matches+=("$f")
      done
      if [[ ${#matches[@]} -eq 0 ]]; then
        echo "ERROR: No file matching '$ref' in session $target_session." >&2
        return 1
      fi
      if [[ ${#matches[@]} -gt 1 ]]; then
        echo "ERROR: Ambiguous ref '$ref'. Matches:" >&2
        for m in "${matches[@]}"; do echo "  $(basename "$m")" >&2; done
        return 1
      fi
      target_file="${matches[0]}"
    fi
  fi

  if [[ ! -f "$target_file" ]]; then
    echo "ERROR: File not found: $target_file" >&2
    return 1
  fi

  cat "$target_file"
}

# ─── Main ────────────────────────────────────────────────────────────────────

_usage() {
  cat <<'EOF'
Usage: scratch.sh <command> [OPTIONS]

Commands:
  write   Write a scratch file (note, smoke test, artifact)
  list    List scratch files by session
  read    Read a scratch file by reference

Run 'scratch.sh <command> --help' for command-specific options.
EOF
}

main() {
  if [[ $# -eq 0 ]]; then
    _usage
    return 1
  fi

  local cmd="$1"; shift
  case "$cmd" in
    write)  cmd_write "$@" ;;
    list)   cmd_list "$@" ;;
    read)   cmd_read "$@" ;;
    -h|--help) _usage ;;
    *)
      echo "ERROR: Unknown command: $cmd" >&2
      _usage
      return 1
      ;;
  esac
}

main "$@"
