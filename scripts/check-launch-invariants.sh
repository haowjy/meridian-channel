#!/usr/bin/env bash
set -euo pipefail

FAIL=0

check() {
    local desc="$1"
    local expected="$2"
    shift 2
    local actual
    actual=$( ( "$@" 2>/dev/null || true ) | wc -l | tr -d ' ' )
    if [ "$actual" != "$expected" ]; then
        echo "FAIL: $desc (expected $expected matches, got $actual)"
        FAIL=1
    else
        echo "OK: $desc"
    fi
}

check_at_least() {
    local desc="$1"
    local minimum="$2"
    shift 2
    local actual
    actual=$( ( "$@" 2>/dev/null || true ) | wc -l | tr -d ' ' )
    if [ "$actual" -lt "$minimum" ]; then
        echo "FAIL: $desc (expected at least $minimum matches, got $actual)"
        FAIL=1
    else
        echo "OK: $desc"
    fi
}

# Pipeline — one builder per concern
check "resolve_policies definition" "1" rg "^def resolve_policies\(" src/
check "resolve_permission_pipeline definition" "1" rg "^def resolve_permission_pipeline\(" src/
check "materialize_fork definition" "1" rg "^def materialize_fork\(" src/

# Plan Object — one sum type
check "NormalLaunchContext definition" "1" rg "^class NormalLaunchContext\b" src/
check "BypassLaunchContext definition" "1" rg "^class BypassLaunchContext\b" src/
check "RuntimeContext definition" "1" rg "^class RuntimeContext\b" src/

# Executor dispatch exhaustiveness + hardening
check "match dispatch on launch_context in executors" "2" rg "match\s+.*launch_context" src/meridian/lib/launch/process.py src/meridian/lib/launch/streaming_runner.py
check_at_least "assert_never use in launch dispatch" "2" rg "assert_never\(" src/meridian/lib/launch/
check "no pyright:ignore in launch/ or ops/spawn/" "0" rg "pyright:\s*ignore" src/meridian/lib/launch/ src/meridian/lib/ops/spawn/
check "no cast(Any, in launch/ or ops/spawn/" "0" rg "cast\(Any," src/meridian/lib/launch/ src/meridian/lib/ops/spawn/

# Type split
check "SpawnRequest definition" "1" rg "^class SpawnRequest\b" src/
check "SpawnParams definition" "1" rg "^class SpawnParams\b" src/

# Result types
check "LaunchResult definition" "1" rg "^class LaunchResult\b" src/meridian/lib/launch/context.py
check "LaunchOutcome definition" "1" rg "^class LaunchOutcome\b" src/meridian/lib/launch/context.py

# Adapter boundary — no domain→concrete-harness imports
check "no concrete harness imports in launch/" "0" rg "from meridian\.lib\.harness\.(claude|codex|opencode|projections)" src/meridian/lib/launch/

# Bypass ownership
check "MERIDIAN_HARNESS_COMMAND in context factory" "1" rg "os\.getenv\(\"MERIDIAN_HARNESS_COMMAND\"" src/meridian/lib/launch/context.py
check "no MERIDIAN_HARNESS_COMMAND in plan.py" "0" rg "MERIDIAN_HARNESS_COMMAND" src/meridian/lib/launch/plan.py
check "no MERIDIAN_HARNESS_COMMAND in command.py" "0" rg "MERIDIAN_HARNESS_COMMAND" src/meridian/lib/launch/command.py

# Deletions completed
check "run_streaming_spawn deleted" "0" rg "run_streaming_spawn" src/ --type py

exit "$FAIL"
