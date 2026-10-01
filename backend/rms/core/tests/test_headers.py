"""Security headers on success and error responses (SC-16, NT3-16, NT3-12)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from django.test import Client

pytestmark = pytest.mark.urls("rms.core.tests.urls")

EXPECTED = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

Request = Callable[[Client], Any]

CASES: dict[str, tuple[int, Request]] = {
    "200": (200, lambda c: c.get("/health/live")),
    "404": (404, lambda c: c.get("/nope")),
    "405": (405, lambda c: c.post("/health/live")),
    "500": (500, lambda c: c.get("/t/raise")),
    "400-bad-host": (400, lambda c: c.get("/health/live", HTTP_HOST="bad.example")),
    "403-csrf": (403, lambda c: c.post("/t/csrf")),
    "403-deny-all": (403, lambda c: c.get("/t/undeclared")),
}


@pytest.mark.parametrize(("status", "request_fn"), CASES.values(), ids=CASES.keys())
def test_security_headers(status: int, request_fn: Request) -> None:
    client = Client(enforce_csrf_checks=True, raise_request_exception=False)
    response = request_fn(client)
    assert response.status_code == status
    for header, value in EXPECTED.items():
        assert response[header] == value, header
    assert uuid.UUID(response["X-Request-ID"]).version == 4
