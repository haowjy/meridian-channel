"""Shared strategy-driven command builder for harness adapters."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, fields
from enum import StrEnum
from typing import cast

from meridian.lib.harness.adapter import PermissionResolver, RunParams
from meridian.lib.types import HarnessId


class FlagEffect(StrEnum):
    """Command-building effect for one RunParams field."""

    CLI_FLAG = "cli_flag"
    TRANSFORM = "transform"
    DROP = "drop"


type StrategyTransform = Callable[[object, list[str]], None]


@dataclass(frozen=True, slots=True)
class FlagStrategy:
    """Mapping rule for how one RunParams field is applied to CLI args."""

    effect: FlagEffect
    cli_flag: str | None = None
    transform: StrategyTransform | None = None


class PromptMode(StrEnum):
    """How prompt text is placed in the harness command."""

    FLAG = "flag"
    POSITIONAL = "positional"


type StrategyMap = dict[str, FlagStrategy]


_SKIP_FIELDS = frozenset({"prompt", "extra_args"})


def _append_cli_flag(*, args: list[str], flag: str, value: object) -> None:
    if isinstance(value, tuple):
        tuple_value = cast("tuple[object, ...]", value)
        if not tuple_value:
            return
        args.extend([flag, ",".join(str(item) for item in tuple_value)])
        return
    args.extend([flag, str(value)])


def build_harness_command(
    *,
    base_command: tuple[str, ...],
    prompt_mode: PromptMode,
    run: RunParams,
    strategies: StrategyMap,
    perms: PermissionResolver,
    harness_id: HarnessId,
) -> list[str]:
    """Build one harness command using field strategies."""

    strategy_args: list[str] = []
    for run_field in fields(RunParams):
        field_name = run_field.name
        if field_name in _SKIP_FIELDS:
            continue

        strategy = strategies.get(field_name)
        if strategy is None:
            continue

        value = getattr(run, field_name)
        if value is None:
            continue

        if strategy.effect is FlagEffect.CLI_FLAG:
            if strategy.cli_flag is None:
                raise ValueError(f"CLI_FLAG strategy for '{field_name}' requires cli_flag.")
            _append_cli_flag(args=strategy_args, flag=strategy.cli_flag, value=value)
            continue

        if strategy.effect is FlagEffect.TRANSFORM:
            if strategy.transform is None:
                raise ValueError(f"TRANSFORM strategy for '{field_name}' requires transform.")
            strategy.transform(value, strategy_args)
            continue

    command = list(base_command)
    if prompt_mode is PromptMode.FLAG:
        command.append(run.prompt)
    command.extend(strategy_args)
    command.extend(perms.resolve_flags(harness_id))
    if prompt_mode is PromptMode.POSITIONAL:
        command.extend(run.extra_args)
        command.append(run.prompt)
        return command
    command.extend(run.extra_args)
    return command
