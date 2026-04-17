# Core

Shared primitives used across all subsystems. No business logic — types, I/O contracts, signal handling, and encoding utilities that every other layer imports.

## Module Map

```
src/meridian/lib/core/
├── types.py        — NewType aliases (ModelId, HarnessId, SpawnId, etc.)
├── overrides.py    — RuntimeOverrides model and merge semantics
├── signals.py      — SignalCoordinator: SIGINT/SIGTERM → structured lifecycle events
├── codec.py        — JSONL encode/decode, atomic write helpers
├── logging.py      — Logging configuration (structlog setup, level control)
├── sink.py         — OutputSink abstraction for routing spawn output
└── util.py         — Shared utilities (retry, time, env inspection)
```

## types.py — Opaque ID Types

`NewType` aliases prevent accidental interchange:

```python
ModelId  = NewType("ModelId",  str)
HarnessId = NewType("HarnessId", str)
SpawnId  = NewType("SpawnId",  str)
```

Why NewType over plain str: downstream code can annotate parameter types explicitly, and mypy catches pass-the-wrong-id bugs statically. Runtime cost is zero.

## overrides.py — RuntimeOverrides

```python
class RuntimeOverrides(BaseModel):
    model:    ModelId | None = None
    harness:  HarnessId | None = None
    approval: str | None = None
    timeout:  int | None = None
```

`merge(base: RuntimeOverrides, override: RuntimeOverrides) -> RuntimeOverrides` — right-hand wins field-by-field. None means "not set"; a set value on the right always beats a set or unset value on the left.

Used in config precedence chain: CLI flags build a RuntimeOverrides, then merge over profile defaults. See [config](../config/overview.md) for the full precedence stack.

## signals.py — SignalCoordinator

Centralizes POSIX signal handling so multiple subsystems don't fight over `signal.signal()`.

```python
class SignalCoordinator:
    def install(self) -> None          # register SIGINT/SIGTERM handlers
    def request_stop(self) -> None     # trigger shutdown programmatically
    def stop_requested(self) -> bool   # poll — used in streaming loops
    def wait_for_stop(self) -> None    # block until signal arrives
```

Pattern: streaming runners poll `stop_requested()` per iteration; the coordinator converts the raw OS signal into a clean boolean. Avoids async-unsafe flag writes inside signal handlers.

## codec.py — JSONL Codec

`encode(obj: dict) -> bytes` — JSON serialize + newline, no trailing whitespace.
`decode(line: bytes) -> dict` — JSON parse; raises `CodecError` on malformed input.
`atomic_append(path: Path, obj: dict) -> None` — write via tmp+rename to guarantee the JSONL event store stays consistent across crashes. Core of the crash-only write discipline (see CLAUDE.md).

## logging.py — Logging Setup

`configure_logging(level: str, json: bool) -> None` — call once at CLI startup.
- `json=True` → structlog JSON renderer (used in agent/headless mode)
- `json=False` → human-readable console renderer (interactive TTY)

No module-level handlers; all configuration is deferred to `configure_logging` so tests can control log output without import-time side effects.

## sink.py — OutputSink

Abstraction over "where spawn output goes." Implementations: `FileSink` (writes to `output.jsonl`), `StdoutSink` (for interactive mode), `NullSink` (tests).

```python
class OutputSink(Protocol):
    def write(self, event: dict) -> None: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...
```

Harness adapters receive a sink, not a file path. Swapping sink type changes output destination without touching harness code — used by the REST app server to capture spawn output in memory. See [app](../app/overview.md).

## util.py — Shared Utilities

Small helpers: `retry(fn, max_attempts, delay)`, `utcnow() -> datetime`, `env_bool(key) -> bool`. No external dependencies — only stdlib. Kept here so the same utilities don't get re-implemented across adapters.
