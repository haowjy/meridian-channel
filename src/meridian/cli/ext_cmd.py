"""Extension command CLI handlers."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import Annotated, cast
from urllib.parse import unquote

import httpx
from cyclopts import App, Parameter

from meridian.cli.output import OutputFormat
from meridian.lib.app.locator import (
    AppServerAuthFailed,
    AppServerLocator,
    AppServerNotRunning,
    AppServerStaleEndpoint,
    AppServerUnreachable,
    AppServerWrongProject,
)
from meridian.lib.extensions.registry import build_first_party_registry, compute_manifest_hash
from meridian.lib.ops.runtime import (
    get_project_uuid,
    resolve_runtime_root_and_config_for_read,
    resolve_runtime_root_for_read,
)

type Emitter = Callable[[object], None]
type OutputFormatResolver = Callable[[], OutputFormat]

ext_app = App(
    name="ext",
    help="Extension command discovery and invocation.",
    help_formatter="plain",
)

_emit: Emitter | None = None
_resolve_global_format: OutputFormatResolver | None = None

# Exit codes for `meridian ext run`.
EXIT_SUCCESS = 0
EXIT_GENERAL_ERROR = 1
EXIT_SERVER_NOT_RUNNING = 2
EXIT_SERVER_STALE = 3
EXIT_SERVER_WRONG_PROJECT = 4
EXIT_SERVER_UNREACHABLE = 5
EXIT_SERVER_AUTH_FAILED = 6
EXIT_ARGS_ERROR = 7


def _resolve_effective_format(
    *,
    requested: OutputFormat,
    json_output: bool = False,
) -> OutputFormat:
    if json_output:
        return "json"
    if requested == "json":
        return "json"
    if _resolve_global_format is not None:
        return _resolve_global_format()
    return requested


def _emit_text_or_json(*, text_payload: str, json_payload: object, format: OutputFormat) -> None:
    if _emit is None:
        if format == "json":
            print(json.dumps(json_payload, indent=2))
        else:
            print(text_payload)
        return
    _emit(json_payload if format == "json" else text_payload)


def _uds_socket_path(base_url: str) -> str:
    encoded = base_url.removeprefix("http+unix://").rstrip("/")
    return unquote(encoded)


@ext_app.command(name="list")
def ext_list(
    *,
    format: OutputFormat = "text",
) -> None:
    """List registered extensions.

    EB3.1: Works with no app server.
    """

    registry = build_first_party_registry()

    extensions: dict[str, list[str]] = {}
    for spec in registry.list_all():
        extensions.setdefault(spec.extension_id, []).append(spec.command_id)

    sorted_extensions: dict[str, list[str]] = {
        ext_id: sorted(command_ids)
        for ext_id, command_ids in sorted(extensions.items())
    }

    json_payload = {
        "schema_version": 1,
        "manifest_hash": compute_manifest_hash(registry)[:16],
        "extensions": [
            {"extension_id": ext_id, "command_ids": command_ids}
            for ext_id, command_ids in sorted_extensions.items()
        ],
    }
    text_payload = "\n".join(
        [
            line
            for ext_id, command_ids in sorted_extensions.items()
            for line in (ext_id, *(f"  {command_id}" for command_id in command_ids))
        ]
    )
    _emit_text_or_json(
        text_payload=text_payload,
        json_payload=json_payload,
        format=_resolve_effective_format(requested=format),
    )


@ext_app.command(name="show")
def ext_show(
    extension_id: str,
    *,
    format: OutputFormat = "text",
) -> None:
    """Show details for an extension."""

    registry = build_first_party_registry()

    commands = sorted(
        (spec for spec in registry.list_all() if spec.extension_id == extension_id),
        key=lambda spec: spec.command_id,
    )

    if not commands:
        raise ValueError(f"Extension not found: {extension_id}")

    json_payload = {
        "extension_id": extension_id,
        "commands": [
            {
                "command_id": spec.command_id,
                "summary": spec.summary,
                "surfaces": [surface.value for surface in sorted(spec.surfaces)],
                "requires_app_server": spec.requires_app_server,
            }
            for spec in commands
        ],
    }
    text_lines = [f"Extension: {extension_id}"]
    for spec in commands:
        text_lines.extend(
            [
                "",
                f"  {spec.command_id}",
                f"    {spec.summary}",
                f"    surfaces: {', '.join(surface.value for surface in sorted(spec.surfaces))}",
                f"    requires_app_server: {spec.requires_app_server}",
            ]
        )
    _emit_text_or_json(
        text_payload="\n".join(text_lines),
        json_payload=json_payload,
        format=_resolve_effective_format(requested=format),
    )


@ext_app.command(name="commands")
def ext_commands(
    *,
    format: OutputFormat = "text",
    json_output: Annotated[
        bool,
        Parameter(
            name="--json",
            help="Output as JSON (alias for --format json).",
        ),
    ] = False,
) -> None:
    """List all extension commands.

    EB3.2: Stable JSON array for agents.
    """

    effective_format = _resolve_effective_format(requested=format, json_output=json_output)
    registry = build_first_party_registry()
    commands = sorted(registry.list_all(), key=lambda spec: spec.fqid)

    json_payload = {
        "schema_version": 1,
        "manifest_hash": compute_manifest_hash(registry)[:16],
        "commands": [
            {
                "fqid": spec.fqid,
                "extension_id": spec.extension_id,
                "command_id": spec.command_id,
                "summary": spec.summary,
                "surfaces": [surface.value for surface in sorted(spec.surfaces)],
                "requires_app_server": spec.requires_app_server,
            }
            for spec in commands
        ],
    }
    text_payload = "\n".join(f"{spec.fqid}: {spec.summary}" for spec in commands)
    _emit_text_or_json(
        text_payload=text_payload,
        json_payload=json_payload,
        format=effective_format,
    )


@ext_app.command(name="run")
def ext_run(
    fqid: str,
    *,
    args: Annotated[
        str,
        Parameter(
            name="--args",
            help="JSON args for the command.",
        ),
    ] = "{}",
    work_id: Annotated[
        str | None,
        Parameter(
            name="--work-id",
            help="Work ID for context.",
        ),
    ] = None,
    spawn_id: Annotated[
        str | None,
        Parameter(
            name="--spawn-id",
            help="Spawn ID for context.",
        ),
    ] = None,
    request_id: Annotated[
        str | None,
        Parameter(
            name="--request-id",
            help="Request ID for tracing.",
        ),
    ] = None,
    format: OutputFormat = "text",
    json_output: Annotated[
        bool,
        Parameter(
            name="--json",
            help="Output as JSON (alias for --format json).",
        ),
    ] = False,
) -> None:
    """Run an extension command via app-server HTTP invoke.

    EB3.4: Locate server, authenticate with token, invoke command endpoint.
    EB3.5: Invalid JSON args exit with 7.
    EB3.6: No server exits with 2.
    EB3.7: Stale endpoint exits with 3.
    """

    _ = work_id, spawn_id
    effective_format = _resolve_effective_format(requested=format, json_output=json_output)

    try:
        parsed_args = json.loads(args)
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON args: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_ARGS_ERROR) from exc
    if not isinstance(parsed_args, dict):
        print("Invalid JSON args: expected a JSON object", file=sys.stderr)
        raise SystemExit(EXIT_ARGS_ERROR)

    registry = build_first_party_registry()
    spec = registry.get(fqid)
    if spec is None:
        print(f"Command not found: {fqid}", file=sys.stderr)
        raise SystemExit(EXIT_GENERAL_ERROR)

    project_root, _ = resolve_runtime_root_and_config_for_read(None)
    runtime_root = resolve_runtime_root_for_read(project_root)
    locator = AppServerLocator(runtime_root, get_project_uuid(project_root))

    try:
        endpoint = locator.locate(verify_reachable=True)
    except AppServerNotRunning:
        print("No app server running", file=sys.stderr)
        raise SystemExit(EXIT_SERVER_NOT_RUNNING) from None
    except AppServerStaleEndpoint:
        print("App server endpoint is stale", file=sys.stderr)
        raise SystemExit(EXIT_SERVER_STALE) from None
    except AppServerWrongProject:
        print("App server is for a different project", file=sys.stderr)
        raise SystemExit(EXIT_SERVER_WRONG_PROJECT) from None
    except AppServerUnreachable:
        print("App server is unreachable", file=sys.stderr)
        raise SystemExit(EXIT_SERVER_UNREACHABLE) from None
    except AppServerAuthFailed:
        print("App server auth failed", file=sys.stderr)
        raise SystemExit(EXIT_SERVER_AUTH_FAILED) from None

    invoke_path = f"/api/extensions/{spec.extension_id}/commands/{spec.command_id}/invoke"
    request_body: dict[str, object | None] = {
        "args": parsed_args,
        "request_id": request_id,
    }
    headers = {"Authorization": f"Bearer {endpoint.token}"}

    try:
        if endpoint.transport == "tcp":
            invoke_url = f"{endpoint.base_url.rstrip('/')}{invoke_path}"
            with httpx.Client(timeout=30.0) as client:
                response = client.post(invoke_url, json=request_body, headers=headers)
        else:
            socket_path = _uds_socket_path(endpoint.base_url)
            transport = httpx.HTTPTransport(uds=socket_path)
            with httpx.Client(transport=transport, timeout=30.0) as client:
                response = client.post(
                    f"http://localhost{invoke_path}",
                    json=request_body,
                    headers=headers,
                )
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_SERVER_UNREACHABLE) from exc

    if response.status_code >= 400:
        if effective_format == "json":
            try:
                print(json.dumps(response.json(), indent=2))
            except ValueError:
                print(response.text)
        else:
            try:
                error_payload = response.json()
            except ValueError:
                print(f"HTTP {response.status_code}: {response.text}", file=sys.stderr)
            else:
                if not isinstance(error_payload, dict):
                    print(f"HTTP {response.status_code}: {response.text}", file=sys.stderr)
                else:
                    typed_error_payload = cast("dict[str, object]", error_payload)
                    title = typed_error_payload.get("title")
                    detail = typed_error_payload.get("detail")
                    if isinstance(title, str) and title:
                        print(f"Error: {title}", file=sys.stderr)
                    else:
                        print(f"HTTP {response.status_code}: request failed", file=sys.stderr)
                    if isinstance(detail, str) and detail:
                        print(f"  {detail}", file=sys.stderr)
        raise SystemExit(EXIT_GENERAL_ERROR)

    try:
        result_payload = response.json()
    except ValueError:
        print(response.text)
        raise SystemExit(EXIT_SUCCESS) from None

    if effective_format == "json":
        print(json.dumps(result_payload, indent=2))
        return

    if isinstance(result_payload, dict) and "result" in result_payload:
        print(json.dumps(result_payload["result"], indent=2))
        return

    print(json.dumps(result_payload, indent=2))


def register_ext_commands(
    parent: App,
    *,
    emit: Emitter,
    resolve_global_format: OutputFormatResolver,
) -> None:
    """Register ext subcommands on the parent app."""

    global _emit, _resolve_global_format
    _emit = emit
    _resolve_global_format = resolve_global_format
    parent.command(ext_app)
