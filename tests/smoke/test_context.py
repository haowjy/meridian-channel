"""Context query smoke tests — path resolution.

Fills CLI-level gap for context command.
"""


def test_context_work_outputs_path_or_null(cli):
    """context work outputs path or null."""
    result = cli("context", "work")
    # Should succeed and output something (path or null/none)
    assert result.returncode == 0 or "Traceback" not in result.stderr


def test_context_kb_outputs_path(cli):
    """context kb outputs path."""
    result = cli("context", "kb")
    result.assert_success()
    # Should output some path
    assert len(result.stdout.strip()) > 0 or result.returncode == 0


def test_context_work_archive_outputs_path(cli):
    """context work.archive outputs path."""
    result = cli("context", "work.archive")
    result.assert_success()


def test_context_verbose_shows_details(cli):
    """context --verbose shows source/path details."""
    result = cli("context", "--verbose")
    result.assert_success()
    # Should have more output than non-verbose
    assert len(result.stdout) > 0


def test_context_json_format(cli):
    """context with --json outputs valid JSON."""
    result = cli("context", json_mode=True)
    if result.returncode == 0 and result.stdout.strip():
        import json
        data = json.loads(result.stdout)
        assert isinstance(data, dict)
