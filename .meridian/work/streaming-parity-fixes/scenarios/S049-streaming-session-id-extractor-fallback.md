# S049: Streaming session-id fallback via `HarnessExtractor`

- **Source:** design/edge-cases.md E46 + decisions.md K6 (revision round 3) + p1385 gap
- **Added by:** @design-orchestrator (revision round 3)
- **Tester:** @smoke-tester
- **Status:** pending

## Given
A real streaming spawn for each harness (Claude, Codex, OpenCode) where the live event stream does NOT carry a session id in any frame — the harness writes its session identifier only to disk artifacts (Claude project files, Codex rollout files, OpenCode logs).

## When
The streaming runner finalizes the spawn and calls `bundle.extractor.detect_session_id_from_artifacts(child_cwd=..., state_root=...)`.

## Then
- The extractor returns the same session id that the subprocess runner would recover for the same artifact set.
- The session id is persisted on the spawn record so `meridian session log <spawn_id>` resolves the transcript.
- Subprocess and streaming reach the same session id for the same harness + artifact set (byte-identical resolution).

## Verification
- Smoke test per harness: launch a streaming spawn, verify the extractor recovers the session id, verify `meridian session log` works.
- Cross-runner test: launch the same conceptual spawn once via subprocess and once via streaming, assert the resolved session ids are identical when the underlying harness writes the same artifact.
- Negative test: empty artifacts directory → extractor returns `None`, spawn record has no session id, `meridian session log` surfaces a clear "session not detected" message rather than crashing.
- Regression: replace the streaming extractor with a no-op stub and verify the smoke test fails with "session not detected".

## Result (filled by tester)
_pending_
