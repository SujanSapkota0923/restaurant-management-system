"""Request-ID middleware (T3-17, T3-18, SC-18, NT3-17, NT3-18)."""

from __future__ import annotations

import io
import json
import logging
import uuid

import pytest
from django.test import Client

from rms.core.context import request_id_var
from rms.core.logging import ContextFilter, JsonFormatter, RedactionFilter

pytestmark = pytest.mark.urls("rms.core.tests.urls")


def is_uuid4(value: str) -> bool:
    try:
        return uuid.UUID(value).version == 4 and str(uuid.UUID(value)) == value
    except ValueError:
        return False


def test_response_has_uuid4_request_id(client: Client) -> None:
    assert is_uuid4(client.get("/health/live")["X-Request-ID"])


@pytest.mark.parametrize(
    "inbound",
    [
        "chosen-id",
        str(uuid.uuid4()),
        "abc\r\nX-Injected: 1",
        "x" * 10_240,
    ],
    ids=["chosen", "valid-uuid", "crlf", "10kB"],
)
def test_inbound_request_id_is_ignored(client: Client, inbound: str) -> None:
    response = client.get("/health/live", HTTP_X_REQUEST_ID=inbound)
    returned = response["X-Request-ID"]
    assert returned != inbound
    assert is_uuid4(returned)
    assert "X-Injected" not in response.headers


def test_sequential_requests_get_different_ids(client: Client) -> None:
    first = client.get("/health/live")["X-Request-ID"]
    second = client.get("/health/live")["X-Request-ID"]
    assert first != second


def test_context_is_reset_after_request(client: Client) -> None:
    assert request_id_var.get() is None
    client.get("/health/live")
    assert request_id_var.get() is None


def test_context_is_reset_after_raising_request() -> None:
    client = Client(raise_request_exception=False)
    response = client.get("/t/raise")
    assert response.status_code == 500
    assert request_id_var.get() is None


def test_500_envelope_request_id_matches_header() -> None:
    response = Client(raise_request_exception=False).get("/t/drf-raise")
    assert response.json()["error"]["request_id"] == response["X-Request-ID"]


def test_log_outside_request_has_null_request_id() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(ContextFilter())
    handler.addFilter(RedactionFilter())
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("rms.test.outside")
    logger.addHandler(handler)
    try:
        logger.warning("outside any request")
    finally:
        logger.removeHandler(handler)
    assert json.loads(stream.getvalue())["request_id"] is None


def test_request_log_line_carries_request_id(
    client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    # pytest >= 9 captures non-propagating loggers such as "django" too.
    caplog.handler.addFilter(ContextFilter())
    response = client.get("/nope")
    [record] = [r for r in caplog.records if r.name == "django.request"]
    assert record.request_id == response["X-Request-ID"]  # type: ignore[attr-defined]
