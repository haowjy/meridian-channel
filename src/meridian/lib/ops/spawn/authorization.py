"""Authorization policy helpers for spawn lifecycle operations."""

from __future__ import annotations

import os
import socket
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from meridian.lib.core.types import SpawnId
from meridian.lib.state import spawn_store

_AUTH_ANCESTRY_MAX_DEPTH = 32


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason: str
    caller_id: SpawnId | None
    target_id: SpawnId


class PeercredFailure(Exception):
    """Raised when caller identity cannot be extracted from peer credentials."""


class _TransportLike(Protocol):
    def get_extra_info(self, name: str, default: object | None = None) -> object | None: ...


def authorize(
    *,
    state_root: Path,
    target: SpawnId,
    caller: SpawnId | None,
    depth: int = 0,
) -> AuthorizationDecision:
    """Authorize lifecycle operations by spawn ancestry."""

    if (caller is None or str(caller) == "") and depth > 0:
        return AuthorizationDecision(False, "missing_caller_in_spawn", None, target)
    if caller is None or str(caller) == "":
        return AuthorizationDecision(True, "operator", None, target)

    target_record = spawn_store.get_spawn(state_root, target)
    if target_record is None:
        return AuthorizationDecision(False, "missing_target", caller, target)
    if caller == target:
        return AuthorizationDecision(True, "self", caller, target)

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
    """Return caller identity from process environment."""

    raw = os.environ.get("MERIDIAN_SPAWN_ID", "").strip()
    depth = int(os.environ.get("MERIDIAN_DEPTH", "0").strip() or "0")
    return (SpawnId(raw) if raw else None, depth)


def _read_caller_from_pid(pid: int) -> tuple[SpawnId | None, int]:
    if pid <= 0:
        raise PeercredFailure("invalid peer pid")
    try:
        environ_data = Path(f"/proc/{pid}/environ").read_bytes()
    except OSError as exc:
        raise PeercredFailure(f"environ read failed: {exc}") from exc

    env_bytes: dict[bytes, bytes] = {}
    for entry in environ_data.split(b"\0"):
        if not entry or b"=" not in entry:
            continue
        key, value = entry.split(b"=", 1)
        env_bytes[key] = value
    try:
        spawn_id_raw = env_bytes.get(b"MERIDIAN_SPAWN_ID", b"").decode().strip()
        depth_raw = env_bytes.get(b"MERIDIAN_DEPTH", b"0").decode().strip()
        depth = int(depth_raw or "0")
    except (UnicodeDecodeError, ValueError) as exc:
        raise PeercredFailure(f"invalid peer environment: {exc}") from exc
    return (SpawnId(spawn_id_raw) if spawn_id_raw else None, depth)


def _peer_pid_from_socket(sock: socket.socket) -> int:
    if sock.family != socket.AF_UNIX:
        raise PeercredFailure("not an AF_UNIX socket")
    if not hasattr(socket, "SO_PEERCRED"):
        raise PeercredFailure("SO_PEERCRED unavailable")
    try:
        creds = sock.getsockopt(
            socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("iII")
        )
        pid, _uid, _gid = struct.unpack("iII", creds)
    except (AttributeError, OSError, struct.error) as exc:
        raise PeercredFailure("SO_PEERCRED unavailable") from exc
    return pid


def _caller_from_socket_peer(sock: socket.socket | None) -> tuple[SpawnId | None, int]:
    """Extract caller identity from AF_UNIX socket peer credentials."""

    if sock is None:
        raise PeercredFailure("missing peer socket")
    return _read_caller_from_pid(_peer_pid_from_socket(sock))


def caller_from_socket_peer(sock: socket.socket | None) -> tuple[SpawnId | None, int]:
    """Public wrapper for extracting caller identity from control socket peers."""

    return _caller_from_socket_peer(sock)


def _caller_from_peercred(request: object) -> tuple[SpawnId | None, int]:
    """Extract caller identity from AF_UNIX SO_PEERCRED. D-19 denies on failure."""

    scope_obj = getattr(request, "scope", None)
    if not isinstance(scope_obj, dict):
        raise PeercredFailure("no transport in request scope")
    scope = cast("dict[str, object]", scope_obj)
    transport = scope.get("transport")
    if transport is None:
        raise PeercredFailure("no transport in request scope")
    socket_obj = cast("_TransportLike", transport).get_extra_info("socket")
    if not isinstance(socket_obj, socket.socket):
        raise PeercredFailure("missing peer socket")
    return _caller_from_socket_peer(socket_obj)


__all__ = [
    "_AUTH_ANCESTRY_MAX_DEPTH",
    "AuthorizationDecision",
    "PeercredFailure",
    "_caller_from_peercred",
    "_caller_from_socket_peer",
    "authorize",
    "caller_from_env",
    "caller_from_socket_peer",
]
