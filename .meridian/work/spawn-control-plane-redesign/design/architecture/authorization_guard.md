# Authorization Guard (v2r2)

Realizes `spec/authorization.md` (AUTH-001..AUTH-007).

## Module

New file: `src/meridian/lib/ops/spawn/authorization.py`.

Under `ops/spawn/` — this is policy, not mechanism. The guard reads the
existing `spawns.jsonl` projection; never writes.

```python
_AUTH_ANCESTRY_MAX_DEPTH = 32

@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason: str          # "operator" | "self" | "ancestor" |
                         # "not_in_ancestry" | "missing_target" |
                         # "missing_caller_in_spawn"
    caller_id: SpawnId | None
    target_id: SpawnId

def authorize(
    *,
    state_root: Path,
    target: SpawnId,
    caller: SpawnId | None,
    depth: int = 0,
) -> AuthorizationDecision:
    """Pure function. No side effects."""
    # --- D-14: depth > 0 with missing caller is deny ---
    if (caller is None or str(caller) == "") and depth > 0:
        return AuthorizationDecision(
            False, "missing_caller_in_spawn", None, target)

    # --- AUTH-002: operator at depth 0 ---
    if caller is None or str(caller) == "":
        return AuthorizationDecision(True, "operator", None, target)

    target_record = spawn_store.get_spawn(state_root, target)
    if target_record is None:
        return AuthorizationDecision(False, "missing_target", caller, target)

    if caller == target:
        return AuthorizationDecision(True, "self", caller, target)

    # Walk parent chain from target upward.
    current = target_record
    for _ in range(_AUTH_ANCESTRY_MAX_DEPTH):
        if current.parent_id is None:
            break
        if current.parent_id == caller:
            return AuthorizationDecision(True, "ancestor", caller, target)
        current = spawn_store.get_spawn(state_root, current.parent_id)
        if current is None:
            break

    return AuthorizationDecision(False, "not_in_ancestry", caller, target)


def caller_from_env() -> tuple[SpawnId | None, int]:
    """Return (caller_id, depth) from the process environment."""
    raw = os.environ.get("MERIDIAN_SPAWN_ID", "").strip()
    depth = int(os.environ.get("MERIDIAN_DEPTH", "0").strip() or "0")
    return (SpawnId(raw) if raw else None, depth)
```

**v2 changes from v1:**
- `authorize()` takes a `depth` parameter (D-14).
- `depth > 0` with missing caller returns DENY with reason
  `"missing_caller_in_spawn"` instead of allowing as operator.
- `caller_from_env()` returns `(caller_id, depth)` tuple.

## Surface composition

**CLI** (`spawn_cancel.py`, `spawn_inject.py` for `--interrupt`):

```python
caller, depth = caller_from_env()

# --operator-override bypasses depth check for debugging
if args.operator_override:
    depth = 0

decision = authorize(state_root=paths.state_root(),
                     target=spawn_id,
                     caller=caller,
                     depth=depth)
logger.info("spawn_auth", extra={"decision": asdict(decision)})
if not decision.allowed:
    typer.echo(f"Error: caller {decision.caller_id} is not authorized "
               f"to {action} {spawn_id}", err=True)
    raise typer.Exit(code=2)
```

**HTTP** — FastAPI dependency via AF_UNIX SO_PEERCRED:

```python
async def require_authorization(spawn_id: str, request: Request):
    caller, depth = _caller_from_peercred(request)
    decision = authorize(
        state_root=app_state.state_root,
        target=SpawnId(spawn_id),
        caller=caller,
        depth=depth,
    )
    request.state.auth = decision
    if not decision.allowed:
        raise HTTPException(403, detail="caller is not authorized")
```

**Control socket** — AF_UNIX `SO_PEERCRED`:

```python
caller, depth = _caller_from_socket_peer(peer_creds)
decision = authorize(state_root=self._state_root,
                     target=self._spawn_id,
                     caller=caller,
                     depth=depth)
if not decision.allowed:
    await self._write(writer, {"ok": False,
                               "error": "interrupt requires caller authorization"})
    return
```

## How caller id reaches each surface (v2 — AF_UNIX transport)

| Surface | Source |
|---|---|
| CLI (user, cron) | `MERIDIAN_SPAWN_ID` + `MERIDIAN_DEPTH` env |
| CLI spawned by another spawn | Same, inherited via `command.py` |
| HTTP (AF_UNIX) | `SO_PEERCRED` → PID → `/proc/<pid>/environ` for `MERIDIAN_SPAWN_ID` + `MERIDIAN_DEPTH` |
| Control socket (AF_UNIX) | `SO_PEERCRED` → PID → `/proc/<pid>/environ` |

**v2 change from v1.** All HTTP/socket identification uses AF_UNIX
`SO_PEERCRED`. No TCP loopback peercred attempt (BL-3 resolved).

**v2r2 change (D-19): peercred failure → DENY.** When `SO_PEERCRED` fails
(macOS, peer exited before `/proc/<pid>/environ` read, permission denied),
the auth surface returns DENY for lifecycle operations. Operator mode is
only available via the CLI env path (`MERIDIAN_DEPTH == 0`,
`MERIDIAN_SPAWN_ID` unset, checked in the process's own environment).

This resolves two review findings:
- p1794 blocker: macOS operator fallback was fail-open.
- p1795 blocker: peer-exit race between `SO_PEERCRED` and `/proc` read.

**No header fallback.** This design does not define a peercred-unavailable
header override for HTTP. Supporting platforms without usable peer
credentials would require a different caller-identity transport, not an
exception path inside the deny branch.

## `_caller_from_peercred` implementation sketch (v2r2)

```python
import socket
import struct

class PeercredFailure(Exception):
    """Raised when caller identity cannot be extracted."""
    pass

def _caller_from_peercred(request: Request) -> tuple[SpawnId | None, int]:
    """Extract caller identity from AF_UNIX SO_PEERCRED.

    v2r2 (D-19): raises PeercredFailure on extraction failure.
    Callers must catch this and DENY, not fall through to operator.
    """
    transport = request.scope.get("transport")
    if transport is None:
        raise PeercredFailure("no transport in request scope")

    sock = transport.get_extra_info("socket")
    if sock is None or sock.family != socket.AF_UNIX:
        raise PeercredFailure("not an AF_UNIX socket")

    try:
        # Linux: SO_PEERCRED returns struct ucred (pid, uid, gid)
        creds = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED,
                                struct.calcsize("iII"))
        pid, uid, gid = struct.unpack("iII", creds)
    except (OSError, AttributeError):
        # macOS or unsupported — D-19: DENY, no fallback header
        raise PeercredFailure("SO_PEERCRED unavailable")

    # Read caller's env from /proc/<pid>/environ
    try:
        environ_path = Path(f"/proc/{pid}/environ")
        environ_data = environ_path.read_bytes()
        env = dict(
            entry.split(b"=", 1) for entry in environ_data.split(b"\0")
            if b"=" in entry
        )
        spawn_id_raw = env.get(b"MERIDIAN_SPAWN_ID", b"").decode().strip()
        depth_raw = env.get(b"MERIDIAN_DEPTH", b"0").decode().strip()
        return (
            SpawnId(spawn_id_raw) if spawn_id_raw else None,
            int(depth_raw or "0"),
        )
    except (OSError, ValueError) as exc:
        # Peer exited before /proc read, or permission denied — D-19: DENY
        raise PeercredFailure(f"environ read failed: {exc}")
```

**v2r2 calling pattern in surfaces:**

```python
# HTTP (require_authorization dependency)
try:
    caller, depth = _caller_from_peercred(request)
except PeercredFailure as exc:
    logger.warning("spawn_auth_peercred_failure", extra={"error": str(exc)})
    raise HTTPException(403, detail="caller identity unavailable")

# Control socket (_caller_from_socket_peer)
try:
    caller, depth = _caller_from_socket_peer(peer_creds)
except PeercredFailure as exc:
    await self._write(writer, {"ok": False,
                               "error": "caller identity unavailable"})
    return
```

## Why not tokens (D-06, v2 reaffirmed)

Per-spawn API tokens would add rotation, storage, revocation — a full
auth lifecycle for a problem the threat model says is honest-actors.
`SO_PEERCRED` on AF_UNIX is unforgeable (kernel-provided), zero-config,
and matches meridian's existing env-based identity model.

If a future deployment needs hostile-actor resistance, replace the
`caller_from_*` helpers without touching `authorize()`.

## Agent profiles and allowlists

Profile that wants to deny lifecycle control: remove `spawn-cancel` /
`spawn-interrupt` from tool allowlist. Guard is the suspenders; allowlist
is the belt.

## Test plan

### Unit tests
- `authorize()` for: caller=None depth=0 (operator), caller=None depth=1
  (deny — D-14), caller=self, caller=parent, caller=grandparent,
  caller=sibling (deny), caller=stranger (deny), target=missing (deny),
  cycle in chain, max-depth walk.
- `caller_from_env()` handles unset, empty, padded strings, missing depth.

### Smoke tests
- Scenario 16: child cancels itself → allowed. Child cancels sibling →
  403 / exit 2.
- Scenario 17: operator shell cancels any spawn → allowed.
- Scenario 18: control-socket interrupt from non-ancestor → rejected.

### Fault-injection tests
- **Env-drop at depth > 0**: verify deny, not operator.
- **Deep ancestry (30+ levels)**: walk reaches root, authorizes correctly.
- **SO_PEERCRED unavailable (D-19)**: verify DENY, not operator fallback.
- **Peer exit before /proc read (D-19)**: verify DENY with
  `PeercredFailure`, HTTP returns 403.
