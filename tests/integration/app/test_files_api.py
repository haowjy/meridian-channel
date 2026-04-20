"""Integration tests for the Files API endpoints.

Tests cover:
- Tree listing (root and nested directories)
- File reading (full and range)
- File search
- File metadata
- Path security (escape attempts should fail)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from meridian.lib.app.file_routes import (
    DiffResponse,
    MetaResponse,
    ReadResponse,
    SearchResponse,
    TreeResponse,
    register_file_routes,
)
from meridian.lib.app.file_service import FileService


class FakeHTTPException(Exception):
    """Fake HTTPException for testing."""

    def __init__(self, status_code: int, detail: str | None = None) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def http_exception(
    status_code: int,
    detail: str | None = None,
    headers: dict[str, str] | None = None,
) -> FakeHTTPException:
    """Fake HTTPException factory."""
    _ = headers
    return FakeHTTPException(status_code, detail)


class FakeApp:
    """Fake FastAPI app that captures registered routes."""

    def __init__(self) -> None:
        self.routes: dict[str, Any] = {}

    def get(self, path: str, **kwargs: object) -> Any:
        def decorator(func: Any) -> Any:
            self.routes[path] = func
            return func
        return decorator


@pytest.fixture
def project_with_files(tmp_path: Path) -> Path:
    """Create a test project with files."""
    project = tmp_path / "project"
    project.mkdir()
    
    # Create directory structure
    (project / "src").mkdir()
    (project / "src" / "lib").mkdir()
    (project / "tests").mkdir()
    
    # Create files
    (project / "README.md").write_text("# Test Project\n\nHello, world!\n")
    (project / "src" / "main.py").write_text(
        "def main():\n    print('Hello')\n\nif __name__ == '__main__':\n    main()\n"
    )
    (project / "src" / "lib" / "utils.py").write_text("def helper(): pass\n")
    (project / "tests" / "test_main.py").write_text(
        "def test_main():\n    assert True\n"
    )
    
    # Create a hidden file
    (project / ".gitignore").write_text("__pycache__/\n*.pyc\n")
    
    return project


@pytest.fixture
def file_service(project_with_files: Path) -> FileService:
    """Create a FileService for the test project."""
    return FileService(project_with_files)


@pytest.fixture
def app_routes(file_service: FileService) -> dict[str, Any]:
    """Register file routes and return the route handlers."""
    app = FakeApp()
    register_file_routes(app, file_service, http_exception=http_exception)
    return app.routes


class TestTreeEndpoint:
    """Tests for GET /api/files/tree."""

    @pytest.mark.asyncio
    async def test_list_root_directory(
        self,
        app_routes: dict[str, Any],
    ) -> None:
        """List root directory contents."""
        handler = app_routes["/api/files/tree"]
        response: TreeResponse = await handler(
            path=".",
            include_hidden=False,
            include_git_status=False,
        )
        
        assert response.path == "."
        names = [e.name for e in response.entries]
        assert "src" in names
        assert "tests" in names
        assert "README.md" in names
        # Hidden files should be excluded
        assert ".gitignore" not in names

    @pytest.mark.asyncio
    async def test_list_with_hidden_files(
        self,
        app_routes: dict[str, Any],
    ) -> None:
        """List directory including hidden files."""
        handler = app_routes["/api/files/tree"]
        response: TreeResponse = await handler(
            path=".",
            include_hidden=True,
            include_git_status=False,
        )
        
        names = [e.name for e in response.entries]
        assert ".gitignore" in names

    @pytest.mark.asyncio
    async def test_list_nested_directory(
        self,
        app_routes: dict[str, Any],
    ) -> None:
        """List nested directory contents."""
        handler = app_routes["/api/files/tree"]
        response: TreeResponse = await handler(
            path="src",
            include_hidden=False,
            include_git_status=False,
        )
        
        assert response.path == "src"
        names = [e.name for e in response.entries]
        assert "lib" in names
        assert "main.py" in names

    @pytest.mark.asyncio
    async def test_list_nonexistent_directory(
        self,
        app_routes: dict[str, Any],
    ) -> None:
        """List nonexistent directory returns 404."""
        handler = app_routes["/api/files/tree"]
        
        with pytest.raises(FakeHTTPException) as exc_info:
            await handler(
                path="nonexistent",
                include_hidden=False,
                include_git_status=False,
            )
        
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_escape_attempt_rejected(
        self,
        app_routes: dict[str, Any],
    ) -> None:
        """Path escape attempts should be rejected."""
        handler = app_routes["/api/files/tree"]
        
        with pytest.raises(FakeHTTPException) as exc_info:
            await handler(
                path="../..",
                include_hidden=False,
                include_git_status=False,
            )
        
        assert exc_info.value.status_code == 400


class TestReadEndpoint:
    """Tests for GET /api/files/read."""

    @pytest.mark.asyncio
    async def test_read_full_file(
        self,
        app_routes: dict[str, Any],
    ) -> None:
        """Read complete file content."""
        handler = app_routes["/api/files/read"]
        response: ReadResponse = await handler(
            path="README.md",
            start_line=None,
            end_line=None,
        )
        
        assert response.path == "README.md"
        assert "Test Project" in response.content
        assert response.total_lines > 0

    @pytest.mark.asyncio
    async def test_read_file_range(
        self,
        app_routes: dict[str, Any],
    ) -> None:
        """Read specific line range from file."""
        handler = app_routes["/api/files/read"]
        response: ReadResponse = await handler(
            path="src/main.py",
            start_line=1,
            end_line=2,
        )
        
        assert "def main():" in response.content
        assert response.start_line == 1
        assert response.end_line == 2
        # Total lines should be the full file count
        assert response.total_lines >= 2

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(
        self,
        app_routes: dict[str, Any],
    ) -> None:
        """Read nonexistent file returns 404."""
        handler = app_routes["/api/files/read"]
        
        with pytest.raises(FakeHTTPException) as exc_info:
            await handler(
                path="nonexistent.txt",
                start_line=None,
                end_line=None,
            )
        
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_read_directory_fails(
        self,
        app_routes: dict[str, Any],
    ) -> None:
        """Reading a directory should fail."""
        handler = app_routes["/api/files/read"]
        
        with pytest.raises(FakeHTTPException) as exc_info:
            await handler(
                path="src",
                start_line=None,
                end_line=None,
            )
        
        assert exc_info.value.status_code == 400


class TestSearchEndpoint:
    """Tests for GET /api/files/search."""

    @pytest.mark.asyncio
    async def test_search_by_filename(
        self,
        app_routes: dict[str, Any],
    ) -> None:
        """Search for files by name."""
        handler = app_routes["/api/files/search"]
        response: SearchResponse = await handler(
            q="main",
            path_prefix="",
            limit=50,
            include_hidden=False,
        )
        
        assert response.query == "main"
        # Should find main.py and test_main.py
        assert any("main.py" in r for r in response.results)

    @pytest.mark.asyncio
    async def test_search_with_prefix(
        self,
        app_routes: dict[str, Any],
    ) -> None:
        """Search within a specific directory."""
        handler = app_routes["/api/files/search"]
        response: SearchResponse = await handler(
            q="py",
            path_prefix="src",
            limit=50,
            include_hidden=False,
        )
        
        # All results should be under src/
        for result in response.results:
            assert result.startswith("src/")

    @pytest.mark.asyncio
    async def test_search_no_results(
        self,
        app_routes: dict[str, Any],
    ) -> None:
        """Search with no matches returns empty list."""
        handler = app_routes["/api/files/search"]
        response: SearchResponse = await handler(
            q="xyznonexistent",
            path_prefix="",
            limit=50,
            include_hidden=False,
        )
        
        assert response.results == []
        assert response.truncated is False


class TestMetaEndpoint:
    """Tests for GET /api/files/meta."""

    @pytest.mark.asyncio
    async def test_get_file_metadata(
        self,
        app_routes: dict[str, Any],
    ) -> None:
        """Get metadata for a file."""
        handler = app_routes["/api/files/meta"]
        response: MetaResponse = await handler(
            path="README.md",
            include_history=False,
            history_limit=10,
        )
        
        assert response.path == "README.md"
        assert response.kind == "file"
        assert response.size > 0
        assert response.mtime > 0

    @pytest.mark.asyncio
    async def test_get_directory_metadata(
        self,
        app_routes: dict[str, Any],
    ) -> None:
        """Get metadata for a directory."""
        handler = app_routes["/api/files/meta"]
        response: MetaResponse = await handler(
            path="src",
            include_history=False,
            history_limit=10,
        )
        
        assert response.path == "src"
        assert response.kind == "directory"

    @pytest.mark.asyncio
    async def test_metadata_nonexistent(
        self,
        app_routes: dict[str, Any],
    ) -> None:
        """Metadata for nonexistent path returns 404."""
        handler = app_routes["/api/files/meta"]
        
        with pytest.raises(FakeHTTPException) as exc_info:
            await handler(
                path="nonexistent",
                include_history=False,
                history_limit=10,
            )
        
        assert exc_info.value.status_code == 404


class TestDiffEndpoint:
    """Tests for GET /api/files/diff."""

    @pytest.mark.asyncio
    async def test_diff_clean_file(
        self,
        app_routes: dict[str, Any],
        project_with_files: Path,
    ) -> None:
        """Diff on unchanged file returns empty diff.
        
        Note: This test may fail if the project is not a git repo,
        which is expected in the test fixture.
        """
        handler = app_routes["/api/files/diff"]
        
        # Initialize git repo for diff to work
        import subprocess
        subprocess.run(
            ["git", "init"],
            cwd=project_with_files,
            capture_output=True,
        )
        subprocess.run(
            ["git", "add", "."],
            cwd=project_with_files,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=project_with_files,
            capture_output=True,
            env={
                **dict(subprocess.os.environ),
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@test.com",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@test.com",
            },
        )
        
        response: DiffResponse = await handler(
            path="README.md",
            ref_a="HEAD",
            ref_b=None,
        )
        
        assert response.path == "README.md"
        assert response.ref_a == "HEAD"
        # Clean file should have empty diff
        assert response.diff == ""

    @pytest.mark.asyncio
    async def test_diff_modified_file(
        self,
        app_routes: dict[str, Any],
        project_with_files: Path,
    ) -> None:
        """Diff on modified file shows changes."""
        handler = app_routes["/api/files/diff"]
        
        # Initialize git repo and make a change
        import subprocess
        subprocess.run(
            ["git", "init"],
            cwd=project_with_files,
            capture_output=True,
        )
        subprocess.run(
            ["git", "add", "."],
            cwd=project_with_files,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=project_with_files,
            capture_output=True,
            env={
                **dict(subprocess.os.environ),
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@test.com",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@test.com",
            },
        )
        
        # Modify the file
        readme = project_with_files / "README.md"
        readme.write_text("# Modified Project\n\nThis was changed.\n")
        
        response: DiffResponse = await handler(
            path="README.md",
            ref_a="HEAD",
            ref_b=None,
        )
        
        assert "Modified" in response.diff or "changed" in response.diff


class TestPathSecurityIntegration:
    """Integration tests for path security across all endpoints."""

    @pytest.mark.asyncio
    async def test_absolute_path_rejected_tree(
        self,
        app_routes: dict[str, Any],
    ) -> None:
        """Absolute paths rejected in tree endpoint."""
        handler = app_routes["/api/files/tree"]
        
        with pytest.raises(FakeHTTPException) as exc_info:
            await handler(
                path="/etc/passwd",
                include_hidden=False,
                include_git_status=False,
            )
        
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_parent_escape_rejected_read(
        self,
        app_routes: dict[str, Any],
    ) -> None:
        """Parent escape rejected in read endpoint."""
        handler = app_routes["/api/files/read"]
        
        with pytest.raises(FakeHTTPException) as exc_info:
            await handler(
                path="src/../../etc/passwd",
                start_line=None,
                end_line=None,
            )
        
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_windows_path_rejected_meta(
        self,
        app_routes: dict[str, Any],
    ) -> None:
        """Windows absolute paths rejected in meta endpoint."""
        handler = app_routes["/api/files/meta"]
        
        with pytest.raises(FakeHTTPException) as exc_info:
            await handler(
                path="C:\\Windows\\System32\\cmd.exe",
                include_history=False,
                history_limit=10,
            )
        
        assert exc_info.value.status_code == 400
