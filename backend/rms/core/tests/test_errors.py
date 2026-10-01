"""Error envelope and CSRF (criterion 5, SC-13, SC-15, NT3-13, NT3-15).

All with DEBUG=False (test settings), all responses application/json.
"""

from __future__ import annotations

import logging

import pytest
from django.conf import settings
from django.db import connection, transaction
from django.middleware.csrf import CSRF_ALLOWED_CHARS, CSRF_SECRET_LENGTH
from django.test import Client
from django.utils.crypto import get_random_string
from rest_framework.exceptions import ValidationError

from rms.core.api.errors import MESSAGES, exception_handler
from rms.core.tests.views import EXCEPTION_TEXT, ROLLBACK_PROBE

pytestmark = pytest.mark.urls("rms.core.tests.urls")


def assert_envelope(response, status: int, code: str) -> dict:  # type: ignore[no-untyped-def, type-arg]
    assert response.status_code == status
    assert response["Content-Type"] == "application/json"
    body = response.json()
    assert set(body) == {"error"}
    error = body["error"]
    assert error["code"] == code
    assert error["message"] == MESSAGES[code]
    assert error["request_id"] == response["X-Request-ID"]
    return error  # type: ignore[no-any-return]


@pytest.fixture
def quiet_client() -> Client:
    """A client that returns 500 responses instead of re-raising."""
    return Client(raise_request_exception=False)


def test_debug_is_off() -> None:
    assert settings.DEBUG is False


def test_404_does_not_echo_path(client: Client) -> None:
    response = client.get("/missing-Path-Canary-81f2?q=Query-Canary")
    error = assert_envelope(response, 404, "not_found")
    assert "fields" not in error
    body = response.content.decode()
    assert "Canary" not in body


def test_bad_host_is_400_envelope(client: Client) -> None:
    response = client.get("/health/live", HTTP_HOST="evil-host-canary.example")
    assert_envelope(response, 400, "bad_request")
    assert "evil-host-canary" not in response.content.decode()


@pytest.mark.parametrize("path", ["/t/raise", "/t/drf-raise"])
def test_500_is_generic(quiet_client: Client, path: str) -> None:
    response = quiet_client.get(path)
    assert_envelope(response, 500, "server_error")
    body = response.content.decode()
    assert EXCEPTION_TEXT not in body
    assert "RuntimeError" not in body
    assert "Traceback" not in body


def test_malformed_json_is_generic_400(client: Client) -> None:
    response = client.post("/t/parse", data=b'{"a": ', content_type="application/json")
    error = assert_envelope(response, 400, "parse_error")
    assert "fields" not in error
    body = response.content.decode()
    assert "JSON" not in body
    assert "Expecting" not in body


def test_valid_json_reaches_view(client: Client) -> None:
    response = client.post("/t/parse", data={"b": 1, "a": 2}, content_type="application/json")
    assert response.status_code == 200
    assert response.json() == {"keys": ["a", "b"]}


def test_unsupported_media_type(client: Client) -> None:
    response = client.post("/t/parse", data="a=1", content_type="application/x-www-form-urlencoded")
    assert_envelope(response, 415, "unsupported_media_type")
    assert "x-www-form-urlencoded" not in response.content.decode()


def test_not_acceptable(client: Client) -> None:
    response = client.get("/health/live", HTTP_ACCEPT="text/html")
    assert_envelope(response, 406, "not_acceptable")


def test_validation_error_has_fields(client: Client) -> None:
    response = client.post("/t/validation", data={}, content_type="application/json")
    error = assert_envelope(response, 400, "validation_error")
    assert error["fields"] == {"name": ["This field is required."]}


def test_405_has_allow_header(client: Client) -> None:
    response = client.post("/health/live")
    assert_envelope(response, 405, "method_not_allowed")
    assert response["Allow"] == "GET, HEAD"


# --- CSRF -------------------------------------------------------------------------


def test_csrf_middleware_is_installed() -> None:
    assert "django.middleware.csrf.CsrfViewMiddleware" in settings.MIDDLEWARE
    assert settings.CSRF_FAILURE_VIEW == "rms.core.api.errors.csrf_failure"


def test_csrf_failure_without_token() -> None:
    client = Client(enforce_csrf_checks=True)
    response = client.post("/t/csrf")
    assert_envelope(response, 403, "csrf_failed")


def test_csrf_failure_does_not_echo_origin(caplog: pytest.LogCaptureFixture) -> None:
    client = Client(enforce_csrf_checks=True)
    # pytest >= 9 captures non-propagating loggers such as "django" too.
    with caplog.at_level(logging.WARNING, logger="django.security.csrf"):
        response = client.post("/t/csrf", HTTP_ORIGIN="https://evil-origin-canary.example")
    assert_envelope(response, 403, "csrf_failed")
    assert "evil-origin-canary" not in response.content.decode()
    # The reason goes to the log only, at WARNING.
    [record] = [r for r in caplog.records if r.name == "django.security.csrf"]
    assert record.levelno == logging.WARNING
    assert "evil-origin-canary" in record.getMessage()


def test_csrf_failure_does_not_echo_referer(caplog: pytest.LogCaptureFixture) -> None:
    """NT3-13: over HTTPS without Origin, Django checks the Referer, and its reason
    carries the attacker's Referer. A valid token makes the Referer the only fault."""
    client = Client(enforce_csrf_checks=True)
    token = get_random_string(CSRF_SECRET_LENGTH, allowed_chars=CSRF_ALLOWED_CHARS)
    client.cookies[settings.CSRF_COOKIE_NAME] = token
    with caplog.at_level(logging.WARNING, logger="django.security.csrf"):
        response = client.post(
            "/t/csrf",
            secure=True,
            HTTP_X_CSRFTOKEN=token,
            HTTP_REFERER="https://evil-referer-canary.example/page",
        )
    assert_envelope(response, 403, "csrf_failed")
    assert "evil-referer-canary" not in response.content.decode()
    [record] = [r for r in caplog.records if r.name == "django.security.csrf"]
    assert "evil-referer-canary" in record.getMessage()  # proves the Referer path ran


def test_csrf_passes_with_matching_cookie_and_header() -> None:
    """Control: the probe is reachable, so the 403s above come from the CSRF check."""
    client = Client(enforce_csrf_checks=True)
    token = get_random_string(CSRF_SECRET_LENGTH, allowed_chars=CSRF_ALLOWED_CHARS)
    client.cookies[settings.CSRF_COOKIE_NAME] = token
    response = client.post("/t/csrf", HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 200


# --- handled errors roll back the request transaction (code review m3) -------


@pytest.fixture
def atomic_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turn on ATOMIC_REQUESTS for ``default``: one shape 0004/0005 may take."""
    monkeypatch.setitem(connection.settings_dict, "ATOMIC_REQUESTS", True)


def _probe_value() -> str | None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting(%s, true)", [ROLLBACK_PROBE])
        value: str | None = cursor.fetchone()[0]
    return value


@pytest.mark.django_db
@pytest.mark.usefixtures("atomic_requests")
def test_successful_request_commits_probe(client: Client) -> None:
    """Control: without an error the probe's write survives the request."""
    response = client.post("/t/rollback/ok")
    assert response.status_code == 200
    assert _probe_value() == "written"


@pytest.mark.django_db
@pytest.mark.usefixtures("atomic_requests")
@pytest.mark.parametrize(
    ("outcome", "status", "code"),
    [("validation", 400, "validation_error"), ("not-found", 404, "not_found")],
)
def test_handled_4xx_rolls_back_request_transaction(
    client: Client, outcome: str, status: int, code: str
) -> None:
    response = client.post(f"/t/rollback/{outcome}")
    assert_envelope(response, status, code)
    assert _probe_value() in (None, "")


@pytest.mark.django_db
@pytest.mark.usefixtures("atomic_requests")
def test_exception_handler_marks_atomic_block_for_rollback() -> None:
    with transaction.atomic():
        assert transaction.get_rollback() is False
        response = exception_handler(ValidationError({"name": ["x"]}), {})
        assert response is not None
        assert response.status_code == 400
        assert transaction.get_rollback() is True
