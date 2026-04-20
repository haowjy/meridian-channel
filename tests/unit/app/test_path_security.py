"""Comprehensive tests for path security validation.

Tests cover:
- Valid relative paths
- Absolute path rejection (POSIX and Windows)
- Parent directory escape attempts
- Symlink escape detection
- Edge cases (empty, null bytes, very long paths)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from meridian.lib.app.path_security import (
    PathSecurityError,
    is_safe_relative_path,
    validate_project_path,
)


class TestValidPaths:
    """Tests for valid relative paths that should be accepted."""

    def test_simple_relative_path(self, tmp_path: Path) -> None:
        """Simple relative paths should work."""
        project = tmp_path / "project"
        project.mkdir()
        target = project / "src" / "main.py"
        target.parent.mkdir(parents=True)
        target.touch()

        result = validate_project_path(project, "src/main.py")
        assert result == target.resolve()

    def test_nested_relative_path(self, tmp_path: Path) -> None:
        """Deeply nested paths should work."""
        project = tmp_path / "project"
        project.mkdir()
        target = project / "src" / "lib" / "utils" / "helpers.py"
        target.parent.mkdir(parents=True)
        target.touch()

        result = validate_project_path(project, "src/lib/utils/helpers.py")
        assert result == target.resolve()

    def test_path_with_dot_component(self, tmp_path: Path) -> None:
        """Paths with . components should work."""
        project = tmp_path / "project"
        project.mkdir()
        target = project / "src" / "main.py"
        target.parent.mkdir(parents=True)
        target.touch()

        result = validate_project_path(project, "./src/main.py")
        assert result == target.resolve()

    def test_internal_parent_that_stays_within_root(self, tmp_path: Path) -> None:
        """Parent references that stay within root should work."""
        project = tmp_path / "project"
        project.mkdir()
        target = project / "tests" / "test.py"
        target.parent.mkdir(parents=True)
        target.touch()
        (project / "src").mkdir()

        result = validate_project_path(project, "src/../tests/test.py")
        assert result == target.resolve()

    def test_nonexistent_path_within_root(self, tmp_path: Path) -> None:
        """Non-existent paths within root should be allowed."""
        project = tmp_path / "project"
        project.mkdir()

        result = validate_project_path(project, "does/not/exist.txt")
        assert result == (project / "does" / "not" / "exist.txt")


class TestAbsolutePathRejection:
    """Tests for absolute path rejection."""

    def test_posix_absolute_path_rejected(self, tmp_path: Path) -> None:
        """POSIX absolute paths should be rejected."""
        project = tmp_path / "project"
        project.mkdir()

        with pytest.raises(PathSecurityError) as exc_info:
            validate_project_path(project, "/etc/passwd")

        assert "Absolute paths not allowed" in str(exc_info.value)

    def test_windows_drive_letter_rejected(self, tmp_path: Path) -> None:
        """Windows drive letters should be rejected."""
        project = tmp_path / "project"
        project.mkdir()

        with pytest.raises(PathSecurityError) as exc_info:
            validate_project_path(project, "C:\\Windows\\system32")

        assert "Windows absolute paths not allowed" in str(exc_info.value)

    def test_windows_drive_with_forward_slash_rejected(self, tmp_path: Path) -> None:
        """Windows drive with forward slash should be rejected."""
        project = tmp_path / "project"
        project.mkdir()

        with pytest.raises(PathSecurityError) as exc_info:
            validate_project_path(project, "C:/Windows/system32")

        assert "Windows absolute paths not allowed" in str(exc_info.value)

    def test_unc_path_rejected(self, tmp_path: Path) -> None:
        """UNC paths should be rejected."""
        project = tmp_path / "project"
        project.mkdir()

        with pytest.raises(PathSecurityError) as exc_info:
            validate_project_path(project, "\\\\server\\share\\file.txt")

        assert "UNC paths not allowed" in str(exc_info.value)


class TestParentEscapeRejection:
    """Tests for parent directory escape attempts."""

    def test_simple_parent_escape_rejected(self, tmp_path: Path) -> None:
        """Simple .. escape should be rejected."""
        project = tmp_path / "project"
        project.mkdir()

        with pytest.raises(PathSecurityError) as exc_info:
            validate_project_path(project, "../secret.txt")

        assert "escapes project root" in str(exc_info.value)

    def test_nested_parent_escape_rejected(self, tmp_path: Path) -> None:
        """Nested .. escape should be rejected."""
        project = tmp_path / "project"
        project.mkdir()

        with pytest.raises(PathSecurityError) as exc_info:
            validate_project_path(project, "src/../../etc/passwd")

        assert "escapes project root" in str(exc_info.value)

    def test_deep_parent_escape_rejected(self, tmp_path: Path) -> None:
        """Deep .. escape should be rejected."""
        project = tmp_path / "project"
        project.mkdir()

        with pytest.raises(PathSecurityError) as exc_info:
            validate_project_path(project, "src/lib/../../../../../../../etc/passwd")

        assert "escapes project root" in str(exc_info.value)

    def test_mixed_separator_escape_rejected(self, tmp_path: Path) -> None:
        """Mixed separators with escape should be rejected."""
        project = tmp_path / "project"
        project.mkdir()

        with pytest.raises(PathSecurityError) as exc_info:
            validate_project_path(project, "src\\..\\..\\etc\\passwd")

        assert "escapes project root" in str(exc_info.value)


class TestSymlinkHandling:
    """Tests for symlink escape detection."""

    @pytest.mark.skipif(sys.platform == "win32", reason="Symlinks need admin on Windows")
    def test_symlink_within_root_allowed(self, tmp_path: Path) -> None:
        """Symlinks staying within root should work."""
        project = tmp_path / "project"
        project.mkdir()
        target = project / "real" / "file.txt"
        target.parent.mkdir(parents=True)
        target.write_text("content")
        
        link = project / "link"
        link.symlink_to(target)

        result = validate_project_path(project, "link")
        assert result == target.resolve()

    @pytest.mark.skipif(sys.platform == "win32", reason="Symlinks need admin on Windows")
    def test_symlink_escaping_root_rejected(self, tmp_path: Path) -> None:
        """Symlinks escaping root should be rejected."""
        project = tmp_path / "project"
        project.mkdir()
        
        # Create target outside project
        escape_target = tmp_path / "secret"
        escape_target.write_text("secret data")
        
        # Create symlink pointing outside
        escape_link = project / "escape"
        escape_link.symlink_to(escape_target)

        with pytest.raises(PathSecurityError) as exc_info:
            validate_project_path(project, "escape")

        assert "Symlink escapes project root" in str(exc_info.value)

    @pytest.mark.skipif(sys.platform == "win32", reason="Symlinks need admin on Windows")
    def test_nested_symlink_escape_rejected(self, tmp_path: Path) -> None:
        """Nested symlink escapes should be rejected."""
        project = tmp_path / "project"
        project.mkdir()
        
        # Create directory outside project
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("secret")
        
        # Create symlink chain
        (project / "level1").mkdir()
        link = project / "level1" / "link"
        link.symlink_to(outside)

        with pytest.raises(PathSecurityError) as exc_info:
            validate_project_path(project, "level1/link/secret.txt")

        assert "escapes project root" in str(exc_info.value)

    @pytest.mark.skipif(sys.platform == "win32", reason="Symlinks need admin on Windows")
    def test_symlink_not_resolved_when_disabled(self, tmp_path: Path) -> None:
        """Symlinks should not be resolved when resolve_symlinks=False."""
        project = tmp_path / "project"
        project.mkdir()
        
        # Create escape symlink
        escape_target = tmp_path / "secret"
        escape_target.write_text("secret")
        
        escape_link = project / "link"
        escape_link.symlink_to(escape_target)

        # Should succeed when not resolving symlinks
        result = validate_project_path(project, "link", resolve_symlinks=False)
        # Result should be the link itself, not resolved
        assert result.name == "link"


class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_empty_path_rejected(self, tmp_path: Path) -> None:
        """Empty path should be rejected."""
        project = tmp_path / "project"
        project.mkdir()

        with pytest.raises(PathSecurityError) as exc_info:
            validate_project_path(project, "")

        assert "cannot be empty" in str(exc_info.value)

    def test_whitespace_only_path_rejected(self, tmp_path: Path) -> None:
        """Whitespace-only path should be rejected."""
        project = tmp_path / "project"
        project.mkdir()

        with pytest.raises(PathSecurityError) as exc_info:
            validate_project_path(project, "   ")

        assert "cannot be empty" in str(exc_info.value)

    def test_null_bytes_rejected(self, tmp_path: Path) -> None:
        """Paths with null bytes should be rejected."""
        project = tmp_path / "project"
        project.mkdir()

        with pytest.raises(PathSecurityError) as exc_info:
            validate_project_path(project, "file\x00.txt")

        assert "null bytes" in str(exc_info.value)

    def test_only_dots_rejected(self, tmp_path: Path) -> None:
        """Path of only .. should be rejected."""
        project = tmp_path / "project"
        project.mkdir()

        with pytest.raises(PathSecurityError) as exc_info:
            validate_project_path(project, "..")

        assert "escapes project root" in str(exc_info.value)

    def test_single_dot_allowed(self, tmp_path: Path) -> None:
        """Single . should refer to project root."""
        project = tmp_path / "project"
        project.mkdir()

        result = validate_project_path(project, ".")
        assert result == project.resolve()

    def test_relative_project_root_rejected(self, tmp_path: Path) -> None:
        """Relative project root should be rejected."""
        with pytest.raises(PathSecurityError) as exc_info:
            validate_project_path(Path("relative/root"), "file.txt")

        assert "project_root must be absolute" in str(exc_info.value)

    def test_long_path(self, tmp_path: Path) -> None:
        """Very long paths should be handled."""
        project = tmp_path / "project"
        project.mkdir()
        
        # Create a moderately long path (not too long to hit OS limits)
        long_path = "/".join(["dir"] * 50 + ["file.txt"])
        
        result = validate_project_path(project, long_path)
        assert result.name == "file.txt"


class TestIsSafeRelativePath:
    """Tests for the quick-check helper function."""

    def test_simple_relative_is_safe(self) -> None:
        """Simple relative paths should be safe."""
        assert is_safe_relative_path("src/main.py") is True

    def test_absolute_not_safe(self) -> None:
        """Absolute paths should not be safe."""
        assert is_safe_relative_path("/etc/passwd") is False

    def test_windows_absolute_not_safe(self) -> None:
        """Windows absolute paths should not be safe."""
        assert is_safe_relative_path("C:\\Windows") is False

    def test_unc_not_safe(self) -> None:
        """UNC paths should not be safe."""
        assert is_safe_relative_path("\\\\server\\share") is False

    def test_parent_escape_not_safe(self) -> None:
        """Parent escapes should not be safe."""
        assert is_safe_relative_path("../secret") is False
        assert is_safe_relative_path("src/../../etc") is False

    def test_internal_parent_is_safe(self) -> None:
        """Internal parent refs that don't escape should be safe."""
        assert is_safe_relative_path("src/../tests") is True

    def test_empty_not_safe(self) -> None:
        """Empty path should not be safe."""
        assert is_safe_relative_path("") is False

    def test_null_bytes_not_safe(self) -> None:
        """Null bytes should not be safe."""
        assert is_safe_relative_path("file\x00.txt") is False


class TestCrossPlatformBehavior:
    """Tests for cross-platform path handling."""

    def test_forward_slash_normalized(self, tmp_path: Path) -> None:
        """Forward slashes should work on all platforms."""
        project = tmp_path / "project"
        project.mkdir()
        target = project / "src" / "main.py"
        target.parent.mkdir(parents=True)
        target.touch()

        result = validate_project_path(project, "src/main.py")
        assert result.exists()

    def test_backslash_normalized(self, tmp_path: Path) -> None:
        """Backslashes should be normalized to forward slashes."""
        project = tmp_path / "project"
        project.mkdir()
        target = project / "src" / "main.py"
        target.parent.mkdir(parents=True)
        target.touch()

        # This should work on all platforms by normalizing backslashes
        result = validate_project_path(project, "src\\main.py")
        assert result.exists()

    def test_mixed_separators_handled(self, tmp_path: Path) -> None:
        """Mixed separators should be normalized."""
        project = tmp_path / "project"
        project.mkdir()
        target = project / "src" / "lib" / "main.py"
        target.parent.mkdir(parents=True)
        target.touch()

        result = validate_project_path(project, "src/lib\\main.py")
        assert result.exists()
