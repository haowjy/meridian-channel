"""Reaper timing configuration with validated bounds."""

_MIN_STALE_THRESHOLD_SECS = 60
_MAX_STALE_THRESHOLD_SECS = 86_400  # 24 hours


def validate_stale_threshold_secs(value: object) -> int:
    """Parse and validate a stale-threshold value. Raises ValueError if out of bounds."""

    parsed = int(value)  # type: ignore[arg-type]
    if parsed < _MIN_STALE_THRESHOLD_SECS or parsed > _MAX_STALE_THRESHOLD_SECS:
        raise ValueError(
            f"stale_threshold_secs must be between {_MIN_STALE_THRESHOLD_SECS} "
            f"and {_MAX_STALE_THRESHOLD_SECS}, got {parsed}"
        )
    return parsed
