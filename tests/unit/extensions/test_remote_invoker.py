"""Unit tests for remote_invoker._parse_response — pure function, real httpx.Response objects."""

from __future__ import annotations

import httpx

from meridian.lib.extensions.remote_invoker import RemoteInvokeResult, _parse_response


def _make_response(
    status_code: int,
    *,
    json_payload: object | None = None,
    text: str = "",
) -> httpx.Response:
    request = httpx.Request("POST", "http://example.test/invoke")
    if json_payload is not None:
        return httpx.Response(status_code, json=json_payload, request=request)
    return httpx.Response(status_code, text=text, request=request)


def test_error_response_with_json_body_extracts_code_and_detail() -> None:
    response = _make_response(
        422,
        json_payload={"code": "args_invalid", "detail": "spawn_id is required"},
    )

    result = _parse_response(response)

    assert result == RemoteInvokeResult(
        success=False,
        error_code="args_invalid",
        error_message="spawn_id is required",
        http_status=422,
    )


def test_error_response_with_non_json_body_falls_back_to_text() -> None:
    response = _make_response(500, text="Internal Server Error")

    result = _parse_response(response)

    assert result == RemoteInvokeResult(
        success=False,
        error_code="http_error",
        error_message="Internal Server Error",
        http_status=500,
    )


def test_success_response_with_result_key_unwraps() -> None:
    response = _make_response(
        200,
        json_payload={"result": {"archived": True, "spawn_id": "p1"}},
    )

    result = _parse_response(response)

    assert result == RemoteInvokeResult(
        success=True,
        payload={"archived": True, "spawn_id": "p1"},
    )


def test_success_response_without_json_returns_raw_text() -> None:
    response = _make_response(200, text="OK plain text")

    result = _parse_response(response)

    assert result == RemoteInvokeResult(
        success=True,
        payload={"raw": "OK plain text"},
    )
