from pathlib import Path
from types import SimpleNamespace

import meridian.lib.ops.spawn.api as spawn_api
from meridian.lib.ops.spawn.models import SpawnCreateInput


def test_spawn_create_validates_model_against_resolved_runtime_root(
    monkeypatch,
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "nested" / "cwd"
    resolved_root = tmp_path / "repo-root"
    call_order: list[str] = []
    seen_validation_root: str | None = None

    def _fake_resolve_runtime_root_and_config(repo_root: str | None):
        nonlocal call_order
        _ = repo_root
        call_order.append("resolve")
        return resolved_root, object()

    def _fake_validate_create_input(payload: SpawnCreateInput):
        nonlocal call_order, seen_validation_root
        call_order.append("validate")
        seen_validation_root = payload.repo_root
        return payload, "preflight warning"

    def _fake_build_create_payload(
        payload: SpawnCreateInput,
        *,
        runtime=None,
        preflight_warning: str | None = None,
        ctx=None,
    ):
        _ = (payload, runtime, ctx)
        return SimpleNamespace(
            model="gpt-5.3-codex",
            harness_id="codex",
            warning=preflight_warning,
            agent_name=None,
            agent_path=None,
            skills=(),
            skill_paths=(),
            reference_files=(),
            template_vars={},
            context_from_resolved=(),
            prompt="prompt",
            cli_command=(),
        )

    monkeypatch.setattr(
        spawn_api,
        "resolve_runtime_root_and_config",
        _fake_resolve_runtime_root_and_config,
    )
    monkeypatch.setattr(spawn_api, "validate_create_input", _fake_validate_create_input)
    monkeypatch.setattr(spawn_api, "build_create_payload", _fake_build_create_payload)

    result = spawn_api.spawn_create_sync(
        SpawnCreateInput(
            prompt="run",
            model="gpt-5.3-codex",
            repo_root=raw_root.as_posix(),
            dry_run=True,
        )
    )

    assert result.status == "dry-run"
    assert result.warning == "preflight warning"
    assert call_order == ["resolve", "validate"]
    assert seen_validation_root == resolved_root.as_posix()
