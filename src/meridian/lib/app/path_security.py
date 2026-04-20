"""Path validation for project-scoped file operations.

All file endpoints validate paths through this module to ensure
they stay within the project root boundary. This is scope containment
(UX guardrail), not security — the user already has shell access.
"""

from __future__ import annotations

import re
from pathlib import Path


class PathSecurityError(Exception):
    """Raised when a path fails validation.
    
    Route handlers should catch this and return 400 status codes.
    """
    pass


# Matches "C:" with or without slash — absolute and drive-relative forms
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def validate_project_path(
    project_root: Path,
    relative_path: str,
) -> Path:
    """Validate and resolve a project-root-relative path.
    
    Args:
        project_root: The project root directory (must be absolute)
        relative_path: User-provided path (relative to project root)
    
    Returns:
        Resolved absolute Path within project root
        
    Raises:
        PathSecurityError: If path escapes project root or is invalid
    """
    # Input validation
    if not project_root.is_absolute():
        raise PathSecurityError("project_root must be absolute")
    
    if "\x00" in relative_path:
        raise PathSecurityError("Path contains null bytes")
    
    if not relative_path or not relative_path.strip():
        raise PathSecurityError("Path cannot be empty")
    
    # Reject obviously absolute paths before any processing
    if relative_path.startswith("\\\\"):  # UNC paths
        raise PathSecurityError(f"UNC paths not allowed: {relative_path}")
    
    if _WINDOWS_DRIVE_RE.match(relative_path):  # Windows drives
        raise PathSecurityError(f"Windows absolute paths not allowed: {relative_path}")
    
    # Normalize separators and check for POSIX absolute
    normalized = relative_path.replace("\\", "/")
    if normalized.startswith("/"):
        raise PathSecurityError(f"Absolute paths not allowed: {relative_path}")
    
    # Resolve everything and check it's under project root
    try:
        resolved_root = project_root.resolve()
        candidate = (resolved_root / normalized).resolve()
        candidate.relative_to(resolved_root)
        return candidate
    except ValueError:
        raise PathSecurityError(
            f"Path escapes project root: {relative_path}"
        ) from None
    except (OSError, RuntimeError) as e:
        raise PathSecurityError(f"Invalid path: {e}") from e


def is_safe_relative_path(relative_path: str) -> bool:
    """Quick check if a path string looks safe (no escapes, not absolute).
    
    Fast pre-check that doesn't require a project root.
    Use validate_project_path() for actual validation.
    """
    if not relative_path:
        return False
    
    if "\x00" in relative_path:
        return False
    
    if relative_path.startswith("\\\\"):
        return False
    
    if _WINDOWS_DRIVE_RE.match(relative_path):
        return False
    
    normalized = relative_path.replace("\\", "/")
    if normalized.startswith("/"):
        return False
    
    # Check for obvious parent escapes
    parts = normalized.split("/")
    depth = 0
    for part in parts:
        if part == "..":
            depth -= 1
            if depth < 0:
                return False
        elif part and part != ".":
            depth += 1
    
    return True


__all__ = [
    "PathSecurityError",
    "is_safe_relative_path",
    "validate_project_path",
]
