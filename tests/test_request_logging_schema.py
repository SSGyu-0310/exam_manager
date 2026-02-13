from __future__ import annotations

import io
import json
import logging

import app as app_module


def test_log_request_payload_has_required_fields():
    stream = io.StringIO()
    logger = logging.getLogger("test.request.log.schema")
    logger.handlers = []
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    app_module._log_request(
        logger,
        request_id="req-123",
        route="/api/example",
        status=200,
        latency=12.34,
        error_code=None,
    )

    payload = json.loads(stream.getvalue().strip())
    assert set(payload.keys()) == {
        "request_id",
        "route",
        "status",
        "latency",
        "error_code",
    }
    assert payload["request_id"] == "req-123"
    assert payload["route"] == "/api/example"
    assert payload["status"] == 200
    assert payload["latency"] == 12.34
    assert payload["error_code"] is None


class _MockResponse:
    def __init__(self, status_code: int, payload=None):
        self.status_code = status_code
        self._payload = payload
        self.is_json = payload is not None

    def get_json(self, silent: bool = True):
        return self._payload


def test_resolve_error_code_from_json_payload_code():
    response = _MockResponse(400, {"code": "INVALID_INPUT"})
    assert app_module._resolve_error_code_from_response(response) == "INVALID_INPUT"


def test_resolve_error_code_falls_back_to_http_status():
    response = _MockResponse(500, payload=None)
    assert app_module._resolve_error_code_from_response(response) == "HTTP_500"


def test_resolve_error_code_is_none_for_success():
    response = _MockResponse(204, {"code": "IGNORED"})
    assert app_module._resolve_error_code_from_response(response) is None
