"""/health/live and /health/ready (criterion 4, T3-09, T3-10, NT3-09, NT3-10, NT3-12)."""

from __future__ import annotations

import copy
import logging
import time
from collections.abc import Iterator

import pytest
from django.db import connections
from django.db.utils import ConnectionHandler
from django.test import Client

from rms.core import health
from rms.core.logging import JsonFormatter

OK = {"status": "ok"}


def test_live_ok_without_db(client: Client) -> None:
    # No django_db mark: any DB access here would raise.
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == OK
    assert response["Cache-Control"] == "no-store"


@pytest.mark.django_db
def test_ready_ok(client: Client) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == OK
    assert response["Cache-Control"] == "no-store"


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/health/live", "/health/ready"])
def test_head_is_allowed(client: Client, path: str) -> None:
    response = client.head(path)
    assert response.status_code == 200
    assert response.content == b""


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete", "options"])
@pytest.mark.parametrize("path", ["/health/live", "/health/ready"])
def test_other_methods_are_405(client: Client, path: str, method: str) -> None:
    response = getattr(client, method)(path)
    assert response.status_code == 405
    body = response.json()
    assert body["error"]["code"] == "method_not_allowed"
    assert set(body["error"]) == {"code", "message", "request_id"}


def test_trailing_slash_is_not_found(client: Client) -> None:
    assert client.get("/health/live/").status_code == 404


def test_default_alias_has_connect_timeout() -> None:
    assert connections["default"].settings_dict["OPTIONS"]["connect_timeout"] == 5


@pytest.fixture
def broken_db(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, object]]:
    """Point the readiness check at a different server; the real handler is untouched."""
    db_settings = copy.deepcopy(connections.settings["default"])
    handler = ConnectionHandler({"default": db_settings})
    monkeypatch.setattr(health, "connections", handler)
    yield db_settings
    handler.close_all()


@pytest.mark.django_db
def test_ready_503_when_db_unreachable(
    client: Client, broken_db: dict[str, object], caplog: pytest.LogCaptureFixture
) -> None:
    broken_db.update(HOST="127.0.0.1", PORT=1)
    with caplog.at_level(logging.WARNING, logger="rms.core.health"):
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "not_ready",
            "message": "The service is not ready.",
            "request_id": response["X-Request-ID"],
        }
    }
    assert response["Cache-Control"] == "no-store"
    [record] = [r for r in caplog.records if r.name == "rms.core.health"]
    assert record.error_class == "OperationalError"  # type: ignore[attr-defined]
    line = JsonFormatter().format(record)
    for leak in ("refused", "127.0.0.1", "port 1", "connection"):
        assert leak not in line.lower()
        assert leak not in response.content.decode().lower()


@pytest.mark.slow
@pytest.mark.django_db
def test_ready_returns_within_connect_timeout(client: Client, broken_db: dict[str, object]) -> None:
    # 10.255.255.1 is non-routable here: the connect either times out or fails fast.
    broken_db.update(HOST="10.255.255.1", PORT=5432)
    timeout = broken_db["OPTIONS"]["connect_timeout"]  # type: ignore[index]
    started = time.monotonic()
    response = client.get("/health/ready")
    elapsed = time.monotonic() - started
    assert response.status_code == 503
    assert elapsed < timeout + 1
