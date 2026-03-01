"""Budget configuration and incremental cost tracking."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

COST_KEYS: tuple[str, ...] = (
    "total_cost_usd",
    "cost_usd",
    "cost",
    "total_cost",
    "totalCostUsd",
)


@dataclass(frozen=True, slots=True)
class Budget:
    """Budget limits in USD."""

    per_run_usd: float | None = None
    per_space_usd: float | None = None


@dataclass(frozen=True, slots=True)
class BudgetBreach:
    """Observed budget breach metadata."""

    scope: Literal["run", "space"]
    observed_usd: float
    limit_usd: float


@dataclass(slots=True)
class LiveBudgetTracker:
    """Streaming budget tracker fed by harness stdout events."""

    budget: Budget
    space_spent_usd: float = 0.0
    run_cost_usd: float = 0.0

    def observe_cost(self, cost_usd: float) -> BudgetBreach | None:
        """Update the current run cost and return breach details when exceeded."""

        if cost_usd < 0:
            return None
        if cost_usd > self.run_cost_usd:
            self.run_cost_usd = cost_usd
        return self.check()

    def observe_json_line(self, raw_line: bytes) -> BudgetBreach | None:
        """Parse one JSONL output line and update tracker if a cost field is present."""

        cost = extract_cost_usd_from_json_line(raw_line)
        if cost is None:
            return None
        return self.observe_cost(cost)

    def check(self) -> BudgetBreach | None:
        """Evaluate per-run and per-space limits."""

        per_run = self.budget.per_run_usd
        if per_run is not None and self.run_cost_usd > per_run:
            return BudgetBreach(scope="run", observed_usd=self.run_cost_usd, limit_usd=per_run)

        per_space = self.budget.per_space_usd
        if per_space is not None:
            observed_space = self.space_spent_usd + self.run_cost_usd
            if observed_space > per_space:
                return BudgetBreach(
                    scope="space",
                    observed_usd=observed_space,
                    limit_usd=per_space,
                )
        return None


def normalize_budget(
    *,
    per_run_usd: float | None,
    per_space_usd: float | None,
) -> Budget | None:
    """Validate numeric limits and build a Budget object."""

    def _validate(name: str, value: float | None) -> float | None:
        if value is None:
            return None
        if value <= 0:
            raise ValueError(f"{name} must be > 0 when provided.")
        return float(value)

    budget = Budget(
        per_run_usd=_validate("per-run budget", per_run_usd),
        per_space_usd=_validate("per-space budget", per_space_usd),
    )
    if budget.per_run_usd is None and budget.per_space_usd is None:
        return None
    return budget


def extract_cost_usd_from_json_line(raw_line: bytes) -> float | None:
    """Extract the first recognized cost field from one JSON line payload."""

    # Import lazily to avoid package init cycles:
    # safety -> budget -> harness._common -> harness.adapter -> safety.permissions.
    from meridian.lib.harness._common import _coerce_optional_float, _iter_dicts

    try:
        payload_obj = json.loads(raw_line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None

    for payload in _iter_dicts(payload_obj):
        for key in COST_KEYS:
            value = _coerce_optional_float(payload.get(key))
            if value is not None:
                return value
    return None
