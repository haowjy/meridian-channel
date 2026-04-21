# Streaming

Connection abstractions for harness subprocess output. Isolates the mechanics of reading from a live process (PTY, pipe, or socket) from the routing and storage logic in the spawn runner.

## Module Map

```
src/meridian/lib/streaming/
└── (files: connection types, runner, buffer utilities)
```

## Core Abstraction

```python
class HarnessConnection(Protocol):
    def read_events(self) -> Iterator[dict]: ...
    def close(self) -> None: ...
```

Each harness produces output in a different format and via a different channel:
- **Claude**: PTY capture (required for session-ID extraction from TUI output). See harness observability note in CLAUDE.md — PTY is the minimum-intrusive mechanism for a specific unobservable-otherwise constraint.
- **Codex / OpenCode**: Pipe or socket connection to the harness process.

Each adapter implements `HarnessConnection` and hides the transport details. The streaming runner consumes the protocol — it doesn't know or care which harness it's reading from.

## Streaming Runner

Reads from a `HarnessConnection` and routes events:

```
HarnessConnection.read_events()
    → parse/normalize event
    → OutputSink.write(event)       # persist to output.jsonl
    → signal check (SignalCoordinator.stop_requested())
    → continue or break
```

Signal integration: the runner polls `stop_requested()` per iteration so SIGINT/SIGTERM from [core/signals](../core/overview.md) propagates cleanly without async-unsafe handler writes.

## Why This Layer Exists

Without it, harness adapter code conflates "how to launch" with "how to read output." Separating them means:
1. Launch adapters stay focused on command building and process start.
2. Streaming behavior (buffering, event normalization, signal handling) is testable without a live harness process.
3. The app server's `MemorySink` path and the CLI's `FileSink` path share the same streaming runner — only the sink differs.

## Relationship to Other Layers

- **Harness adapters** ([harness](../harness/overview.md)): Build the launch spec; streaming picks up after process start.
- **Core sink** ([core](../core/overview.md)): Receives each parsed event from the runner.
- **Core signals** ([core](../core/overview.md)): Provides the stop flag the runner polls.
