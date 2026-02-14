from __future__ import annotations

from typing import Any, Mapping

from flask import jsonify

_SUCCESS_CODE_BY_STATUS = {
    200: "OK",
    201: "CREATED",
    202: "ACCEPTED",
    204: "NO_CONTENT",
}

_SUCCESS_MESSAGE_BY_CODE = {
    "OK": "OK",
    "CREATED": "Created.",
    "ACCEPTED": "Accepted.",
    "NO_CONTENT": "No content.",
}


def _merge_legacy_fields(
    payload: dict[str, Any],
    legacy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not legacy:
        return payload
    for key, value in legacy.items():
        if key not in payload:
            payload[key] = value
    return payload


def success_response(
    *,
    data: Any = None,
    status: int = 200,
    code: str | None = None,
    message: str | None = None,
    legacy: Mapping[str, Any] | None = None,
):
    normalized_code = code or _SUCCESS_CODE_BY_STATUS.get(status, "OK")
    normalized_message = message or _SUCCESS_MESSAGE_BY_CODE.get(
        normalized_code, "Success."
    )
    payload = {
        "ok": True,
        "code": normalized_code,
        "message": normalized_message,
        "data": data,
    }
    payload = _merge_legacy_fields(payload, legacy)
    return jsonify(payload), status


def error_response(
    *,
    message: str,
    code: str = "BAD_REQUEST",
    status: int = 400,
    data: Any = None,
    legacy: Mapping[str, Any] | None = None,
):
    payload = {
        "ok": False,
        "code": code,
        "message": message,
        "data": data,
    }
    payload = _merge_legacy_fields(payload, legacy)
    return jsonify(payload), status
