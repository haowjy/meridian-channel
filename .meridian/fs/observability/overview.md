# Observability

Structured logging and debug tracing. Not metrics or alerting — lightweight context propagation for diagnosing spawn failures and harness behavior without adding external dependencies.

## Module Map

```
src/meridian/lib/observability/
└── (files: trace context, debug helpers, log enrichment)
```

## Logging Discipline

Configuration lives in [core/logging.py](../core/overview.md) — `configure_logging(level, json)` is called once at CLI startup. Observability layer adds spawn-scoped context on top:

**Bound context:** Each spawn operation binds a log context (spawn_id, model, harness) so every log line within a spawn scope carries those fields without explicit passing. Implemented via structlog's contextvars binding, not thread-locals — safe for concurrent spawns in the app server.

**Log levels in practice:**
- `INFO` — spawn lifecycle events (started, terminal state, report path)
- `DEBUG` — per-event streaming, harness command args, config resolution steps
- `WARNING` — orphan detection, reconciliation fixups, non-fatal config issues
- `ERROR` — harness exit non-zero, state write failure, unhandled exception

## Debug Tracing

`MERIDIAN_DEBUG=1` env var enables verbose trace output. Not structured spans — simple per-operation timing and arg dumps to stderr, readable without a trace viewer.

Used for: diagnosing PTY session-ID extraction failures, tracking config precedence resolution, verifying workspace root projection logic.

Trace output goes to stderr, never to `output.jsonl` — keeps spawn artifacts clean for downstream parsing.

## Why Not OpenTelemetry

Meridian is a CLI coordination layer, not a long-running service. OTEL adds: a collector, export config, SDK startup overhead, and a new failure mode (spans lost if collector unreachable). For a CLI that runs for seconds, structured logs with debug mode meet all diagnostic needs at zero infrastructure cost.

If the app server path grows into a persistent service, revisit.

## Relationship to Other Layers

- **core/logging.py** ([core](../core/overview.md)): Low-level log configuration (renderer, level) — observability layer enriches, doesn't replace.
- **state layer** ([state](../state/overview.md)): Spawn events written to JSONL are the durable record; observability logs are transient and not persisted.
