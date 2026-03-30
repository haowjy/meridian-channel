# Config Layer Unification — Decisions Log

## Execution Start
- Following plan's 4-round execution schedule
- Round 1: Steps 1 + 2 in parallel (different files)
- Using meridian spawn for all substantive work

## Step 3: Direct implementation
- Spawn p428 (gpt-5.4) completed in 2s with no file changes - likely failed silently
- Implementing Step 3 directly via harness-native Agent tool since this is the critical integration step

## Review findings addressed
- **CRITICAL fix**: timeout in spawn prepare.py used raw payload.timeout instead of resolved.timeout — ENV/config/profile timeout values were silently ignored
- **HIGH fix**: Pre-resolve included config_overrides which made config.primary.model beat profile.model — changed to only include CLI + ENV in pre-resolve, preserving CLI > ENV > profile > config precedence
- **HIGH fix**: Deduplicated frozensets — agent.py and permissions.py now import from overrides.py canonical definitions
- **MEDIUM fix**: Simplified redundant autocompact fallback in from_config — PrimaryConfig model_validator already handles migration
- **MEDIUM fix**: Added from_config round-trip test to verify all 9 fields are actually wired through
- **Deferred**: deprecation warning for autocompact_pct (LOW), budget/max_turns CLI flags (LOW, by design)
