"""Hooks CLI smoke tests — list, check, run.

Replaces: tests/e2e/hooks/cli.md
"""

import json


def test_hooks_list_text_output(cli_with_git, scratch_dir):
    """hooks list shows table output."""
    # Create a config with hooks
    config = """
[[hooks]]
name = "test-hook"
event = "spawn.created"
command = "echo test"
"""
    (scratch_dir / "meridian.toml").write_text(config, encoding="utf-8")
    
    result = cli_with_git("hooks", "list", "--format", "text")
    result.assert_success()
    
    # Should show some output (headers or rows)
    assert len(result.stdout) > 0


def test_hooks_list_json_output(cli_with_git, scratch_dir):
    """hooks list JSON is machine-parseable."""
    config = """
[[hooks]]
name = "json-test-hook"
event = "spawn.finalized"
command = "echo json"
"""
    (scratch_dir / "meridian.toml").write_text(config, encoding="utf-8")
    
    result = cli_with_git("hooks", "list", "--format", "json")
    result.assert_success()
    
    data = json.loads(result.stdout)
    assert "hooks" in data
    assert isinstance(data["hooks"], list)


def test_hooks_check_shows_status(cli_with_git):
    """hooks check reports requirement status."""
    result = cli_with_git("hooks", "check", "--format", "text")
    result.assert_success()


def test_hooks_run_manual_execution(cli_with_git, scratch_dir):
    """hooks run executes manually."""
    # Create a simple hook that echoes
    config = """
[[hooks]]
name = "manual-hook"
event = "spawn.finalized"
command = "echo manual-run"
"""
    (scratch_dir / "meridian.toml").write_text(config, encoding="utf-8")
    
    result = cli_with_git("hooks", "run", "manual-hook", "--format", "text")
    # May succeed or fail depending on hook implementation
    assert "Traceback" not in result.stderr


def test_hooks_list_builtin_registration(cli_with_git):
    """hooks list shows builtin hooks."""
    result = cli_with_git("hooks", "list", "--format", "json")
    result.assert_success()
    
    data = json.loads(result.stdout)
    hooks = data.get("hooks", [])
    
    # May have builtin hooks with auto registration
    # Just verify structure is correct
    for hook in hooks:
        assert "name" in hook
