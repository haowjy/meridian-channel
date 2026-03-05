"""Slice B space launch regressions."""

from __future__ import annotations

import json
import os
from pathlib import Path
import time

import pytest

from meridian.lib.harness.registry import get_default_harness_registry
from meridian.lib.ops.space import SpaceStartInput, space_start_sync
from meridian.lib.types import SpaceId
from meridian.lib.harness.codex import CodexAdapter
from meridian.lib.harness.opencode import OpenCodeAdapter
from meridian.lib.space.launch import (
    SpaceLaunchRequest,
    _build_space_env,
    _build_harness_command,
    build_primary_prompt,
    cleanup_orphaned_locks,
)
from meridian.lib.space.space_file import create_space, get_space


def _install_config(repo_root: Path, content: str) -> None:
    config_path = repo_root / ".meridian" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content, encoding="utf-8")


def test_build_interactive_command_uses_system_prompt_model_and_passthrough(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("MERIDIAN_HARNESS_COMMAND", raising=False)

    request = SpaceLaunchRequest(
        space_id=SpaceId("s42"),
        model="claude-opus-4-6",
        fresh=True,
        passthrough_args=("--permission-mode", "acceptEdits"),
    )
    prompt = build_primary_prompt(request)

    command = _build_harness_command(
        repo_root=tmp_path,
        request=request,
        prompt=prompt,
        harness_registry=get_default_harness_registry(),
        chat_id="c1",
    )

    assert command[0] == "claude"
    assert "-p" not in command
    # Bundled profile materializes to a harness-native --agent entry.
    assert "--agents" not in command
    assert "--agent" in command
    assert command[command.index("--agent") + 1] == "_meridian-c1-primary"
    assert "--append-system-prompt" in command
    appended_prompt = command[command.index("--append-system-prompt") + 1]
    assert "# Meridian Space Session" in appended_prompt
    assert "Space: s42" in appended_prompt
    assert "# Skill:" in appended_prompt
    assert "--model" in command
    assert command[command.index("--model") + 1] == "claude-opus-4-6"
    assert "--permission-mode" in command
    assert "acceptEdits" in command


def test_build_space_env_sanitizes_parent_env_and_keeps_space_overrides(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("PATH", "/usr/local/bin:/usr/bin")
    monkeypatch.setenv("HOME", "/home/sliceb")
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("MY_SECRET_TOKEN", "do-not-forward")
    monkeypatch.setenv("RANDOM_PARENT_VALUE", "drop-me")
    monkeypatch.setenv("MERIDIAN_DEPTH", "5")

    request = SpaceLaunchRequest(
        space_id=SpaceId("s99"),
        autocompact=80,
    )
    env = _build_space_env(tmp_path, request, "space prompt", spawn_id="p88")

    assert env["PATH"] == "/usr/local/bin:/usr/bin"
    assert env["HOME"] == "/home/sliceb"
    assert env["LANG"] == "C.UTF-8"
    assert "MY_SECRET_TOKEN" not in env
    assert "RANDOM_PARENT_VALUE" not in env
    assert env["MERIDIAN_SPACE_ID"] == "s99"
    assert env["MERIDIAN_SPAWN_ID"] == "p88"
    assert env["MERIDIAN_DEPTH"] == "5"
    assert env["MERIDIAN_SPACE_PROMPT"] == "space prompt"
    assert env["MERIDIAN_STATE_ROOT"] == (tmp_path / ".meridian").as_posix()
    assert env["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"] == "80"


def test_primary_settings_apply_to_harness_command_and_env(tmp_path: Path) -> None:
    _install_config(
        tmp_path,
        (
            "[permissions]\n"
            "default_tier = 'read-only'\n"
            "\n"
            "[primary]\n"
            "autocompact_pct = 67\n"
            "permission_tier = 'workspace-write'\n"
        ),
    )
    request = SpaceLaunchRequest(space_id=SpaceId("s100"))

    command = _build_harness_command(
        repo_root=tmp_path,
        request=request,
        prompt="space prompt",
        harness_registry=get_default_harness_registry(),
    )

    assert "--autocompact" not in command
    assert "--allowedTools" in command
    allowed_tools = command[command.index("--allowedTools") + 1]
    assert "Edit" in allowed_tools
    assert "Write" in allowed_tools

    env = _build_space_env(
        tmp_path,
        request,
        "space prompt",
        default_autocompact_pct=67,
    )
    assert env["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"] == "67"
    assert env["MERIDIAN_STATE_ROOT"] == (tmp_path / ".meridian").as_posix()


def test_cleanup_orphaned_locks_removes_stale_lock(tmp_path: Path) -> None:
    space = create_space(tmp_path, name="orphaned")

    lock_path = tmp_path / ".meridian" / "active-spaces" / f"{space.id}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps(
            {
                "space_id": str(space.id),
                "child_pid": 999_999,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    cleaned = cleanup_orphaned_locks(tmp_path)

    assert cleaned == (SpaceId(space.id),)
    assert not lock_path.exists()

    refreshed = get_space(tmp_path, space.id)
    assert refreshed is not None


def test_space_start_dry_run_returns_interactive_command(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("MERIDIAN_HARNESS_COMMAND", raising=False)

    result = space_start_sync(
        SpaceStartInput(
            repo_root=tmp_path.as_posix(),
            dry_run=True,
        )
    )

    assert result.exit_code == 0
    assert result.message == "Launch dry-run."
    assert result.lock_path is not None
    assert not Path(result.lock_path).exists()
    assert result.command[0] == "claude"
    assert "-p" not in result.command
    assert "--agent" in result.command
    assert result.command[result.command.index("--agent") + 1] == "_meridian-dry-run-primary"
    assert "--append-system-prompt" in result.command
    appended_prompt = result.command[result.command.index("--append-system-prompt") + 1]
    assert "# Meridian Space Session" in appended_prompt


def test_build_interactive_command_merges_passthrough_system_prompt_flags(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("MERIDIAN_HARNESS_COMMAND", raising=False)

    request = SpaceLaunchRequest(
        space_id=SpaceId("s77"),
        model="claude-opus-4-6",
        fresh=True,
        passthrough_args=(
            "--append-system-prompt",
            "first passthrough",
            "--system-prompt=second passthrough",
            "--permission-mode",
            "acceptEdits",
        ),
    )
    prompt = build_primary_prompt(request)

    command = _build_harness_command(
        repo_root=tmp_path,
        request=request,
        prompt=prompt,
        harness_registry=get_default_harness_registry(),
        chat_id="c77",
    )

    assert command.count("--append-system-prompt") == 1
    assert "--system-prompt" not in command
    assert not any(token.startswith("--system-prompt=") for token in command)
    assert command[command.index("--permission-mode") + 1] == "acceptEdits"
    appended_prompt = command[command.index("--append-system-prompt") + 1]
    assert "# Meridian Space Session" in appended_prompt
    assert "Space: s77" in appended_prompt
    assert "first passthrough" in appended_prompt
    assert "second passthrough" in appended_prompt


def test_build_interactive_command_rejects_missing_system_prompt_passthrough_value(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("MERIDIAN_HARNESS_COMMAND", raising=False)

    with pytest.raises(ValueError, match="--append-system-prompt requires a value"):
        _build_harness_command(
            repo_root=tmp_path,
            request=SpaceLaunchRequest(
                space_id=SpaceId("s88"),
                model="claude-opus-4-6",
                fresh=True,
                passthrough_args=("--append-system-prompt",),
            ),
            prompt="space prompt",
            harness_registry=get_default_harness_registry(),
            chat_id="c88",
        )


def test_build_interactive_command_supports_codex_harness_override(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("MERIDIAN_HARNESS_COMMAND", raising=False)

    request = SpaceLaunchRequest(
        space_id=SpaceId("s99"),
        model="gpt-5.3-codex",
        harness="codex",
        fresh=True,
    )
    prompt = build_primary_prompt(request)

    command = _build_harness_command(
        repo_root=tmp_path,
        request=request,
        prompt=prompt,
        harness_registry=get_default_harness_registry(),
        chat_id="c99",
    )

    assert command[0] == "codex"
    assert "exec" not in command[:2]
    assert "--model" in command
    assert command[command.index("--model") + 1] == "gpt-5.3-codex"
    assert "# Meridian Space Session" in command[-1]


def test_build_interactive_command_harness_override_uses_harness_default_over_profile_model(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("MERIDIAN_HARNESS_COMMAND", raising=False)

    request = SpaceLaunchRequest(
        space_id=SpaceId("s99b"),
        harness="codex",
        fresh=True,
    )
    prompt = build_primary_prompt(request)

    command = _build_harness_command(
        repo_root=tmp_path,
        request=request,
        prompt=prompt,
        harness_registry=get_default_harness_registry(),
        chat_id="c99b",
    )

    assert command[0] == "codex"
    assert "--model" in command
    # Even though bundled primary profile has a Claude model, harness override
    # should drive default model selection when --model is omitted.
    assert command[command.index("--model") + 1] == "gpt-5.3-codex"


def test_build_interactive_command_uses_harness_default_model_when_profile_has_none(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("MERIDIAN_HARNESS_COMMAND", raising=False)
    _install_config(
        tmp_path,
        "[harness]\n"
        "codex = 'gpt-5.2-high'\n",
    )
    profile_path = tmp_path / ".agents" / "agents" / "primary.md"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        "---\n"
        "name: primary\n"
        "description: primary without model\n"
        "---\n"
        "\n"
        "Primary body.\n",
        encoding="utf-8",
    )

    request = SpaceLaunchRequest(
        space_id=SpaceId("s101"),
        harness="codex",
        fresh=True,
    )
    prompt = build_primary_prompt(request)

    command = _build_harness_command(
        repo_root=tmp_path,
        request=request,
        prompt=prompt,
        harness_registry=get_default_harness_registry(),
        chat_id="c101",
    )

    assert command[0] == "codex"
    assert "--model" in command
    assert command[command.index("--model") + 1] == "gpt-5.2-high"


def test_build_interactive_command_rejects_incompatible_harness_override(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("MERIDIAN_HARNESS_COMMAND", raising=False)

    request = SpaceLaunchRequest(
        space_id=SpaceId("s100"),
        model="claude-opus-4-6",
        harness="codex",
        fresh=True,
    )
    prompt = build_primary_prompt(request)

    with pytest.raises(ValueError, match="incompatible with model"):
        _build_harness_command(
            repo_root=tmp_path,
            request=request,
            prompt=prompt,
            harness_registry=get_default_harness_registry(),
            chat_id="c100",
        )


def test_build_interactive_command_uses_catalog_harness_for_custom_model(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("MERIDIAN_HARNESS_COMMAND", raising=False)
    models_path = tmp_path / ".meridian" / "models.toml"
    models_path.parent.mkdir(parents=True, exist_ok=True)
    models_path.write_text(
        (
            "[[models]]\n"
            "model_id = 'custom-model-v1'\n"
            "aliases = ['customv1']\n"
            "harness = 'opencode'\n"
        ),
        encoding="utf-8",
    )

    request = SpaceLaunchRequest(
        space_id=SpaceId("s-catalog"),
        model="custom-model-v1",
        fresh=True,
    )
    prompt = build_primary_prompt(request)

    command = _build_harness_command(
        repo_root=tmp_path,
        request=request,
        prompt=prompt,
        harness_registry=get_default_harness_registry(),
        chat_id="c-catalog",
    )

    assert command[0] == "opencode"
    assert "--model" in command
    assert command[command.index("--model") + 1] == "custom-model-v1"


def testdetect_primary_harness_session_id_from_codex_rollout_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", home_dir.as_posix())

    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    other_repo = tmp_path / "other-repo"
    other_repo.mkdir(parents=True, exist_ok=True)

    session_id = "019cb8d4-8d62-79d3-a925-d329f8310c5d"
    other_session_id = "019cb8d4-8d62-79d3-a925-d329f8310c5e"
    sessions_dir = home_dir / ".codex" / "sessions" / "2026" / "03" / "04"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    other_rollout = sessions_dir / f"rollout-2026-03-04T06-31-04-{other_session_id}.jsonl"
    other_rollout.write_text(
        json.dumps(
            {
                "type": "session_meta",
                "payload": {"id": other_session_id, "cwd": other_repo.as_posix()},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rollout = sessions_dir / f"rollout-2026-03-04T06-31-03-{session_id}.jsonl"
    rollout.write_text(
        "\n".join(
            (
                json.dumps(
                    {
                        "type": "session_meta",
                        "payload": {"id": session_id, "cwd": repo_root.as_posix()},
                    }
                ),
                json.dumps(
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "working"}],
                        },
                    }
                ),
            )
        )
        + "\n",
        encoding="utf-8",
    )

    started_at = time.time()
    os.utime(other_rollout, (started_at + 2, started_at + 2))
    os.utime(rollout, (started_at + 3, started_at + 3))

    adapter = CodexAdapter()
    resolved = adapter.detect_primary_session_id(
        repo_root=repo_root,
        started_at_epoch=started_at,
        started_at_local_iso="2026-03-04T06:31:00",
    )

    assert resolved == session_id


def testdetect_primary_harness_session_id_skips_codex_aborted_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", home_dir.as_posix())

    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)

    valid_session_id = "019cb8d4-8d62-79d3-a925-d329f8310c5d"
    aborted_session_id = "019cb8ef-c55a-7782-a75e-0c9dc798cd35"
    sessions_dir = home_dir / ".codex" / "sessions" / "2026" / "03" / "04"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    valid_rollout = sessions_dir / f"rollout-2026-03-04T06-31-03-{valid_session_id}.jsonl"
    valid_rollout.write_text(
        "\n".join(
            (
                json.dumps(
                    {
                        "type": "session_meta",
                        "payload": {"id": valid_session_id, "cwd": repo_root.as_posix()},
                    }
                ),
                json.dumps(
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "hello"}],
                        },
                    }
                ),
            )
        )
        + "\n",
        encoding="utf-8",
    )

    aborted_rollout = sessions_dir / f"rollout-2026-03-04T06-31-04-{aborted_session_id}.jsonl"
    aborted_rollout.write_text(
        "\n".join(
            (
                json.dumps(
                    {
                        "type": "session_meta",
                        "payload": {"id": aborted_session_id, "cwd": repo_root.as_posix()},
                    }
                ),
                json.dumps(
                    {
                        "type": "event_msg",
                        "payload": {"type": "turn_aborted"},
                    }
                ),
            )
        )
        + "\n",
        encoding="utf-8",
    )

    started_at = time.time()
    os.utime(valid_rollout, (started_at + 2, started_at + 2))
    os.utime(aborted_rollout, (started_at + 3, started_at + 3))

    adapter = CodexAdapter()
    resolved = adapter.detect_primary_session_id(
        repo_root=repo_root,
        started_at_epoch=started_at,
        started_at_local_iso="2026-03-04T06:31:00",
    )

    assert resolved == valid_session_id


def testdetect_primary_harness_session_id_from_opencode_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", home_dir.as_posix())

    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    other_repo = tmp_path / "other-repo"
    other_repo.mkdir(parents=True, exist_ok=True)

    logs_dir = home_dir / ".local" / "share" / "opencode" / "log"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "2026-03-04T120000.log"
    log_file.write_text(
        "\n".join(
            (
                (
                    "INFO  2026-03-04T12:50:00 +2ms service=session "
                    f"id=ses_old123 directory={repo_root.as_posix()} created"
                ),
                (
                    "INFO  2026-03-04T12:50:05 +2ms service=session "
                    f"id=ses_other directory={other_repo.as_posix()} created"
                ),
                (
                    "INFO  2026-03-04T12:50:10 +2ms service=session "
                    f"id=ses_new456 directory={repo_root.as_posix()} created"
                ),
            )
        )
        + "\n",
        encoding="utf-8",
    )

    started_at = time.time()
    os.utime(log_file, (started_at + 2, started_at + 2))

    adapter = OpenCodeAdapter()
    resolved = adapter.detect_primary_session_id(
        repo_root=repo_root,
        started_at_epoch=started_at,
        started_at_local_iso="2026-03-04T12:50:01",
    )

    assert resolved == "ses_new456"
