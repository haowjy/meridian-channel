"""FastMCP server entry point and operation registration."""

from contextlib import asynccontextmanager
from typing import Any, cast
from urllib.parse import unquote

import httpx
from mcp.server.fastmcp import FastMCP

from meridian.lib.app.locator import (
    AppServerAuthFailed,
    AppServerLocator,
    AppServerNotRunning,
    AppServerStaleEndpoint,
    AppServerUnreachable,
    AppServerWrongProject,
)
from meridian.lib.core.codec import coerce_input_payload, signature_from_model
from meridian.lib.core.logging import configure_logging
from meridian.lib.core.util import to_jsonable
from meridian.lib.extensions.context import (
    ExtensionCommandServices,
    ExtensionInvocationContextBuilder,
)
from meridian.lib.extensions.dispatcher import ExtensionCommandDispatcher
from meridian.lib.extensions.registry import (
    build_first_party_registry,
    compute_manifest_hash,
)
from meridian.lib.extensions.types import (
    ExtensionErrorResult,
    ExtensionSurface,
)
from meridian.lib.ops.manifest import OperationSpec, get_operations_for_surface
from meridian.lib.ops.runtime import (
    get_project_uuid,
    resolve_runtime_root_and_config_for_read,
    resolve_runtime_root_for_read,
)

_REGISTERED_MCP_TOOLS: set[str] = set()
_REGISTERED_MCP_DESCRIPTIONS: dict[str, str] = {}


@asynccontextmanager
async def lifespan(_: FastMCP[Any]):
    """Initialize shared resources for MCP server lifetime."""

    configure_logging(json_mode=True)
    yield {"ready": True}


mcp = FastMCP("meridian", lifespan=lifespan)


def _uds_socket_path(base_url: str) -> str:
    encoded = base_url.removeprefix("http+unix://").rstrip("/")
    return unquote(encoded)


@mcp.tool()
async def extension_list_commands() -> dict[str, Any]:
    """List all registered extension commands.

    EB3.8: Returns same fqids as CLI discovery.
    """

    registry = build_first_party_registry()
    commands = sorted(registry.list_all(), key=lambda spec: spec.fqid)

    return {
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


@mcp.tool()
async def extension_invoke(
    fqid: str,
    args: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Invoke an extension command.

    EB3.9: Uses spec.extension_id/spec.command_id for invoke URL.
    EB3.10: In-process dispatch for requires_app_server=False.
    EB3.11: Returns structured error payload on failures.
    """

    resolved_args = args or {}

    registry = build_first_party_registry()
    spec = registry.get(fqid)
    if spec is None:
        return {
            "status": "error",
            "code": "not_found",
            "message": f"Command not found: {fqid}",
        }

    if not spec.requires_app_server:
        dispatcher = ExtensionCommandDispatcher(registry)
        context_builder = ExtensionInvocationContextBuilder(ExtensionSurface.MCP)
        if request_id is not None:
            context_builder = context_builder.with_request_id(request_id)
        result = await dispatcher.dispatch(
            fqid=fqid,
            args=resolved_args,
            context=context_builder.build(),
            services=ExtensionCommandServices(),
        )
        if isinstance(result, ExtensionErrorResult):
            return {
                "status": "error",
                "code": result.code,
                "message": result.message,
            }
        return {"status": "ok", "result": result.payload}

    project_root, _ = resolve_runtime_root_and_config_for_read(None)
    runtime_root = resolve_runtime_root_for_read(project_root)
    locator = AppServerLocator(runtime_root, get_project_uuid(project_root))

    try:
        endpoint = locator.locate(verify_reachable=True)
    except AppServerNotRunning:
        return {
            "status": "error",
            "code": "app_server_required",
            "message": "No app server running",
        }
    except AppServerStaleEndpoint:
        return {
            "status": "error",
            "code": "app_server_stale",
            "message": "App server endpoint is stale",
        }
    except AppServerWrongProject:
        return {
            "status": "error",
            "code": "app_server_wrong_project",
            "message": "App server is for a different project",
        }
    except AppServerUnreachable:
        return {
            "status": "error",
            "code": "app_server_unreachable",
            "message": "App server is unreachable",
        }
    except AppServerAuthFailed:
        return {
            "status": "error",
            "code": "app_server_auth_failed",
            "message": "App server auth failed",
        }

    invoke_path = (
        f"/api/extensions/{spec.extension_id}/commands/{spec.command_id}/invoke"
    )
    request_payload: dict[str, object | None] = {
        "args": resolved_args,
        "request_id": request_id,
    }
    headers = {"Authorization": f"Bearer {endpoint.token}"}

    try:
        if endpoint.transport == "tcp":
            invoke_url = f"{endpoint.base_url.rstrip('/')}{invoke_path}"
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    invoke_url,
                    json=request_payload,
                    headers=headers,
                )
        else:
            transport = httpx.AsyncHTTPTransport(uds=_uds_socket_path(endpoint.base_url))
            async with httpx.AsyncClient(transport=transport, timeout=30.0) as client:
                response = await client.post(
                    f"http://localhost{invoke_path}",
                    json=request_payload,
                    headers=headers,
                )
    except httpx.HTTPError as error:
        return {"status": "error", "code": "request_failed", "message": str(error)}

    if response.status_code >= 400:
        try:
            raw_error = response.json()
        except ValueError:
            return {
                "status": "error",
                "code": "http_error",
                "message": response.text,
            }
        if not isinstance(raw_error, dict):
            return {
                "status": "error",
                "code": "http_error",
                "message": response.text,
            }
        typed_error = cast("dict[str, Any]", raw_error)
        code = typed_error.get("code")
        detail = typed_error.get("detail")
        return {
            "status": "error",
            "code": code if isinstance(code, str) and code else "http_error",
            "message": (
                detail if isinstance(detail, str) and detail else response.text
            ),
        }

    try:
        payload = response.json()
    except ValueError:
        return {"status": "ok", "result": response.text}

    if isinstance(payload, dict) and "result" in payload:
        return {"status": "ok", "result": payload["result"]}
    return {"status": "ok", "result": payload}


def _build_tool_handler(op: OperationSpec[Any, Any]) -> Any:
    async def _tool(**kwargs: object) -> object:
        payload = coerce_input_payload(op.input_type, kwargs)
        result = await op.handler(payload)
        if hasattr(result, "to_wire"):
            return result.to_wire()
        return to_jsonable(result)

    _tool.__name__ = f"tool_{op.mcp_name}"
    _tool.__doc__ = op.description
    cast("Any", _tool).__signature__ = signature_from_model(op.input_type)
    return _tool


def _register_operation_tool(op: OperationSpec[Any, Any]) -> None:
    """Register one operation from the manifest as an MCP tool."""

    if op.mcp_name is None:
        raise ValueError(f"Operation '{op.name}' is missing MCP tool name")
    mcp.tool(name=op.mcp_name, description=op.description)(_build_tool_handler(op))
    _REGISTERED_MCP_TOOLS.add(op.mcp_name)
    _REGISTERED_MCP_DESCRIPTIONS[op.name] = op.description


def _register_operation_tools() -> None:
    for op in get_operations_for_surface("mcp"):
        _register_operation_tool(op)


def get_registered_mcp_tools() -> set[str]:
    """Expose MCP tool names for parity tests."""

    return set(_REGISTERED_MCP_TOOLS)


def get_registered_mcp_descriptions() -> dict[str, str]:
    """Expose MCP descriptions for parity tests."""

    return dict(_REGISTERED_MCP_DESCRIPTIONS)


def run_server() -> None:
    """Start the FastMCP stdio server."""

    mcp.run(transport="stdio")


_register_operation_tools()


if __name__ == "__main__":
    run_server()
