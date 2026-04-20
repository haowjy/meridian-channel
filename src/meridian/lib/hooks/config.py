"""Hook config loading and normalization."""

from __future__ import annotations

import re
import tomllib
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import cast, get_args

from meridian.lib.config.project_config_state import resolve_project_config_state
from meridian.lib.config.settings import (
    normalize_hooks_array,
    normalize_work_table,
    resolve_user_config_path,
)
from meridian.lib.hooks.types import (
    EVENT_CLASS,
    FailurePolicy,
    Hook,
    HookEventName,
    HookWhen,
    SpawnStatus,
)

HOOK_SOURCE_PRECEDENCE: tuple[str, ...] = ("builtin", "user", "project", "local")
_LOCAL_CONFIG_FILENAME = "meridian.local.toml"
_INTERVAL_PATTERN = re.compile(r"^\d+[smhd]$")
_KNOWN_FAILURE_POLICIES = frozenset({"fail", "warn", "ignore"})
_KNOWN_SPAWN_STATUSES = frozenset(get_args(SpawnStatus))


@dataclass(frozen=True)
class BuiltinHookDefaults:
    """Static builtin hook defaults used before runtime builtin loading exists."""

    default_events: tuple[HookEventName, ...]
    interval: str | None = None


BUILTIN_HOOK_DEFAULTS: dict[str, BuiltinHookDefaults] = {
    "git-autosync": BuiltinHookDefaults(
        default_events=("spawn.finalized", "work.done"),
        interval="10m",
    )
}


@dataclass(frozen=True)
class HooksConfig:
    """Resolved hook config after source layering and override semantics."""

    hooks: tuple[Hook, ...]


def _read_toml(path: Path) -> dict[str, object]:
    payload_obj = tomllib.loads(path.read_text(encoding="utf-8"))
    return cast("dict[str, object]", payload_obj)


def _parse_event(raw: str, *, source: str) -> HookEventName:
    if raw not in EVENT_CLASS:
        valid = ", ".join(sorted(EVENT_CLASS.keys()))
        raise ValueError(
            f"Invalid value for '{source}': expected one of [{valid}], got {raw!r}."
        )
    return raw


def _parse_interval(raw: str | None, *, source: str) -> str | None:
    if raw is None:
        return None
    if not _INTERVAL_PATTERN.fullmatch(raw):
        raise ValueError(
            f"Invalid value for '{source}': expected interval format '\\d+[smhd]', got {raw!r}."
        )
    return raw


def _parse_when(raw: object, *, source: str) -> HookWhen | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid value for '{source}': expected table.")

    raw_dict = cast("dict[str, object]", raw)

    status_values: tuple[str, ...] | None = None
    status = raw_dict.get("status")
    if status is not None:
        if not isinstance(status, tuple):
            raise ValueError(f"Invalid value for '{source}.status': expected array[str].")
        for value in cast("tuple[object, ...]", status):
            if not isinstance(value, str):
                raise ValueError(f"Invalid value for '{source}.status': expected array[str].")
            if value not in _KNOWN_SPAWN_STATUSES:
                valid = ", ".join(sorted(_KNOWN_SPAWN_STATUSES))
                raise ValueError(
                    f"Invalid value for '{source}.status': expected values in [{valid}], "
                    f"got {value!r}."
                )
        status_values = cast("tuple[str, ...]", status)

    agent_obj = raw_dict.get("agent")
    if agent_obj is not None and not isinstance(agent_obj, str):
        raise ValueError(
            f"Invalid value for '{source}.agent': expected str, got "
            f"{type(agent_obj).__name__} ({agent_obj!r})."
        )
    agent = agent_obj

    if status_values is None and agent is None:
        return None
    return HookWhen(
        status=cast("tuple[SpawnStatus, ...] | None", status_values),
        agent=agent,
    )


def _hook_from_row(
    row: dict[str, object],
    *,
    source: str,
    row_source: str,
    auto_registered: bool = False,
) -> Hook:
    command = cast("str | None", row.get("command"))
    builtin = cast("str | None", row.get("builtin"))

    if command is not None and builtin is not None:
        raise ValueError(
            f"Invalid hook config '{row_source}': 'command' and 'builtin' are mutually exclusive."
        )
    if command is None and builtin is None:
        raise ValueError(
            f"Invalid hook config '{row_source}': expected either 'command' or 'builtin'."
        )

    name = cast("str | None", row.get("name"))
    if name is None:
        if builtin is not None:
            name = builtin
        else:
            raise ValueError(f"Invalid hook config '{row_source}': 'name' is required.")

    if builtin is not None and builtin not in BUILTIN_HOOK_DEFAULTS:
        valid = ", ".join(sorted(BUILTIN_HOOK_DEFAULTS.keys()))
        raise ValueError(
            f"Invalid value for '{row_source}.builtin': expected one of [{valid}], got {builtin!r}."
        )

    default_event = (
        BUILTIN_HOOK_DEFAULTS[builtin].default_events[0] if builtin is not None else None
    )
    raw_event = cast("str | None", row.get("event"))
    if raw_event is None:
        if default_event is None:
            raise ValueError(f"Invalid hook config '{row_source}': 'event' is required.")
        event = default_event
    else:
        event = _parse_event(raw_event, source=f"{row_source}.event")

    default_interval = BUILTIN_HOOK_DEFAULTS[builtin].interval if builtin is not None else None
    interval = _parse_interval(
        cast("str | None", row.get("interval")) or default_interval,
        source=f"{row_source}.interval",
    )

    timeout_secs = cast("int | None", row.get("timeout_secs"))
    if timeout_secs is not None and timeout_secs <= 0:
        raise ValueError(
            f"Invalid value for '{row_source}.timeout_secs': expected int > 0, "
            f"got {timeout_secs!r}."
        )

    failure_policy = cast("str | None", row.get("failure_policy"))
    if failure_policy is not None and failure_policy not in _KNOWN_FAILURE_POLICIES:
        valid = ", ".join(sorted(_KNOWN_FAILURE_POLICIES))
        raise ValueError(
            f"Invalid value for '{row_source}.failure_policy': expected one of [{valid}], "
            f"got {failure_policy!r}."
        )
    resolved_failure_policy: FailurePolicy | None = None
    if failure_policy is not None:
        resolved_failure_policy = cast("FailurePolicy", failure_policy)

    exclude = cast("tuple[str, ...] | None", row.get("exclude")) or ()
    when = _parse_when(row.get("when"), source=f"{row_source}.when")

    return Hook(
        name=name,
        event=event,
        source=source,
        command=command,
        builtin=builtin,
        timeout_secs=timeout_secs,
        interval=interval,
        enabled=cast("bool", row.get("enabled", True)),
        priority=cast("int", row.get("priority", 0)),
        failure_policy=resolved_failure_policy,
        require_serial=cast("bool", row.get("require_serial", False)),
        when=when,
        exclude=exclude,
        auto_registered=auto_registered,
    )


def _hooks_from_payload(payload: dict[str, object], *, source: str) -> tuple[Hook, ...]:
    hooks: list[Hook] = []

    work = payload.get("work")
    if work is not None:
        normalized_work = normalize_work_table(work, source=f"{source}.work")
        artifacts = normalized_work.get("artifacts")
        artifacts_dict = (
            cast("dict[str, object]", artifacts) if isinstance(artifacts, dict) else None
        )
        if artifacts_dict is not None and artifacts_dict.get("sync") == "git":
            defaults = BUILTIN_HOOK_DEFAULTS["git-autosync"]
            for event in defaults.default_events:
                hooks.append(
                    Hook(
                        name="git-autosync",
                        event=event,
                        source=source,
                        builtin="git-autosync",
                        interval=defaults.interval,
                        auto_registered=True,
                    )
                )

    raw_hooks = payload.get("hooks")
    if raw_hooks is None:
        return tuple(hooks)

    rows = normalize_hooks_array(raw_hooks, source=f"{source}.hooks")
    for index, row in enumerate(rows, start=1):
        hooks.append(
            _hook_from_row(
                row,
                source=source,
                row_source=f"{source}.hooks[{index}]",
            )
        )
    return tuple(hooks)


def _apply_name_overrides(hooks: tuple[Hook, ...]) -> tuple[Hook, ...]:
    effective: OrderedDict[tuple[str, HookEventName | None], Hook] = OrderedDict()
    for hook in hooks:
        if hook.builtin is not None and not hook.auto_registered:
            to_remove = [
                key
                for key, existing in effective.items()
                if existing.auto_registered and existing.builtin == hook.builtin
            ]
            for key in to_remove:
                del effective[key]

        if hook.auto_registered and hook.builtin is not None:
            key = (hook.name, hook.event)
            if key in effective:
                del effective[key]
            effective[key] = hook
            continue

        to_remove_by_name = [
            key for key, existing in effective.items() if existing.name == hook.name
        ]
        for key in to_remove_by_name:
            del effective[key]
        effective[(hook.name, None)] = hook
    return tuple(effective.values())


def load_hooks_config(repo_root: Path, *, user_config: Path | None = None) -> HooksConfig:
    """Load hook config with precedence: builtin defaults < user < project < local."""

    resolved_repo_root = repo_root.expanduser().resolve()
    resolved_user_config = resolve_user_config_path(user_config)
    project_config = resolve_project_config_state(resolved_repo_root).path
    local_config = resolved_repo_root / _LOCAL_CONFIG_FILENAME

    hooks: list[Hook] = []
    hooks.extend(_hooks_from_payload({}, source="builtin"))

    if resolved_user_config is not None:
        hooks.extend(_hooks_from_payload(_read_toml(resolved_user_config), source="user"))

    if project_config is not None:
        hooks.extend(_hooks_from_payload(_read_toml(project_config), source="project"))

    if local_config.is_file():
        hooks.extend(_hooks_from_payload(_read_toml(local_config), source="local"))

    return HooksConfig(hooks=_apply_name_overrides(tuple(hooks)))
