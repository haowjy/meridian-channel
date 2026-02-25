"""Slice 5b MCP integration checks via SDK stdio client."""

from __future__ import annotations

import json
import sys
from typing import Any

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def _payload_from_call_result(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured

    for block in getattr(result, "content", []):
        text = getattr(block, "text", None)
        if isinstance(text, str) and text.strip():
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload

    raise AssertionError("Call result did not include a JSON object payload")


@pytest.mark.asyncio
async def test_mcp_tools_registered_and_callable(package_root, cli_env) -> None:
    env = dict(cli_env)
    env["MERIDIAN_REPO_ROOT"] = str(package_root.parent)

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "meridian", "serve"],
        env=env,
        cwd=package_root,
    )

    async with stdio_client(params) as (read_stream, write_stream), ClientSession(
        read_stream, write_stream
    ) as session:
        await session.initialize()

        listed = await session.list_tools()
        names = {tool.name for tool in listed.tools}
        expected = {
            "run_create",
            "run_list",
            "workspace_start",
            "skills_search",
            "models_list",
            "context_pin",
            "diag_doctor",
        }
        assert expected.issubset(names)

        doctor = await session.call_tool("diag_doctor", {})
        assert doctor.isError is False
        doctor_payload = _payload_from_call_result(doctor)
        assert doctor_payload["ok"] is True

        created = await session.call_tool(
            "run_create",
            {
                "prompt": "MCP non-blocking run_create verification",
                "model": "gpt-5.3-codex",
                "timeout_secs": 5,
            },
        )
        assert created.isError is False
        created_payload = _payload_from_call_result(created)
        assert created_payload["status"] == "running"
        run_id = created_payload["run_id"]
        assert isinstance(run_id, str) and run_id

        waited = await session.call_tool(
            "run_wait",
            {
                "run_id": run_id,
                "timeout_secs": 30,
            },
        )
        assert waited.isError is False
        waited_payload = _payload_from_call_result(waited)
        assert waited_payload["status"] in {"succeeded", "failed", "cancelled"}
