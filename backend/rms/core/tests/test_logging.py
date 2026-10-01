"""JSON logging and redaction (criterion 6, SC-19, SC-20, NT3-19, NT3-20, NT3-21)."""

from __future__ import annotations

import copy
import io
import json
import logging
import logging.config
from collections.abc import Iterator
from typing import Any

import pytest
from django.conf import settings
from django.db import connection
from django.test import RequestFactory

from rms.core.logging import (
    REDACTED,
    REDACTION_ERROR,
    ContextFilter,
    JsonFormatter,
    RedactionFilter,
    build_logging_config,
)


class Capture:
    def __init__(self) -> None:
        self.stream = io.StringIO()

    def lines(self) -> list[str]:
        return [line for line in self.stream.getvalue().split("\n") if line]

    def records(self) -> list[dict[str, Any]]:
        return [json.loads(line) for line in self.lines()]

    def one(self) -> dict[str, Any]:
        [record] = self.records()
        return record


@pytest.fixture
def log() -> Iterator[tuple[logging.Logger, Capture]]:
    """A logger wired exactly like the console handler, writing to a buffer."""
    capture = Capture()
    handler = logging.StreamHandler(capture.stream)
    handler.addFilter(ContextFilter())
    handler.addFilter(RedactionFilter())
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("rms.test.logging")
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    yield logger, capture
    logger.removeHandler(handler)
    logger.propagate = True


def test_line_shape(log: tuple[logging.Logger, Capture]) -> None:
    logger, capture = log
    logger.info("hello %s", "world", extra={"count": 3})
    record = capture.one()
    assert set(record) == {
        "ts",
        "level",
        "logger",
        "message",
        "request_id",
        "tenant_id",
        "membership_id",
        "extra",
        "exc_type",
    }
    assert record["message"] == "hello world"
    assert record["level"] == "INFO"
    assert record["logger"] == "rms.test.logging"
    assert record["ts"].endswith("+00:00")
    assert record["tenant_id"] is None
    assert record["membership_id"] is None
    assert record["extra"] == {"count": 3}
    assert record["exc_type"] is None


@pytest.mark.parametrize(
    "key",
    [
        "password",
        "new_passwd",
        "client_secret",
        "access_token",
        "api_key",
        "Authorization",
        "cookie",
        "session_id",
        "csrfmiddlewaretoken",
        "pin",
        "otp_code",
        "credentials",
        "auth",
        "bearer",
        "signature",
        "sentry_dsn",
        "salt",
        "password_hash",
        "private_key",
    ],
)
def test_sensitive_extra_keys_are_redacted(log: tuple[logging.Logger, Capture], key: str) -> None:
    logger, capture = log
    logger.info("event", extra={key: "Sensitive-Canary"})
    line = capture.lines()[0]
    assert "Sensitive-Canary" not in line
    assert capture.one()["extra"][key] == REDACTED


def test_nested_dicts_and_lists_are_redacted(log: tuple[logging.Logger, Capture]) -> None:
    logger, capture = log
    payload = {"user": {"name": "x", "profile": {"pin": "1234"}}, "items": [{"token": "t1"}, 7]}
    logger.info("event", extra={"payload": payload})
    extra = capture.one()["extra"]["payload"]
    assert extra["user"]["name"] == "x"
    assert extra["user"]["profile"]["pin"] == REDACTED
    assert extra["items"] == [{"token": REDACTED}, 7]


def test_percent_mapping_args_are_redacted(log: tuple[logging.Logger, Capture]) -> None:
    logger, capture = log
    logger.info("login %(user)s %(password)s", {"user": "alice", "password": "hunter2-canary"})
    record = capture.one()
    assert record["message"] == f"login alice {REDACTED}"
    assert "hunter2-canary" not in capture.lines()[0]


def test_percent_tuple_args_redact_dicts(log: tuple[logging.Logger, Capture]) -> None:
    logger, capture = log
    logger.info("payload %s", {"secret": "Tuple-Canary"})
    assert "Tuple-Canary" not in capture.lines()[0]


def test_caller_objects_are_not_mutated(log: tuple[logging.Logger, Capture]) -> None:
    logger, _ = log
    payload = {"password": "p", "nested": {"token": "t", "list": [{"key": "k"}]}}
    original = copy.deepcopy(payload)
    args = {"secret": "s"}
    logger.info("x %(secret)s", args, extra={"payload": payload})
    assert payload == original
    assert args == {"secret": "s"}


def test_self_referencing_dict(log: tuple[logging.Logger, Capture]) -> None:
    logger, capture = log
    loop: dict[str, Any] = {"name": "loop"}
    loop["self"] = loop
    logger.info("cycle", extra={"loop": loop})
    assert len(capture.lines()) == 1
    assert capture.one()["extra"]["loop"]["name"] == "loop"


def test_deep_nesting(log: tuple[logging.Logger, Capture]) -> None:
    logger, capture = log
    deep: dict[str, Any] = {}
    node = deep
    for _ in range(50):
        node["child"] = {}
        node = node["child"]
    node["password"] = "Deep-Canary"  # noqa: S105 - test canary
    logger.info("deep", extra={"deep": deep})
    assert len(capture.lines()) == 1
    assert "Deep-Canary" not in capture.lines()[0]


class RaisingRepr:
    def __repr__(self) -> str:
        raise RuntimeError("repr exploded")

    __str__ = __repr__


def test_object_with_raising_repr(log: tuple[logging.Logger, Capture]) -> None:
    logger, capture = log
    logger.info("odd", extra={"thing": RaisingRepr()})
    assert capture.one()["extra"]["thing"] == "RaisingRepr"


def test_raising_repr_in_message_args() -> None:
    # Formatted directly: pytest's own capture handler deliberately fails a test
    # whose log message cannot be formatted, before ours is reached.
    record = logging.LogRecord(
        "rms.test", logging.INFO, __file__, 1, "odd %s", (RaisingRepr(),), None
    )
    assert RedactionFilter().filter(record)
    line = JsonFormatter().format(record)
    assert json.loads(line)["message"] == "[FORMAT_ERROR]"


def test_redaction_error_marker(
    log: tuple[logging.Logger, Capture], monkeypatch: pytest.MonkeyPatch
) -> None:
    logger, capture = log

    def explode(value: Any, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("redaction exploded")

    monkeypatch.setattr("rms.core.logging.redact", explode)
    logger.info("still emitted", extra={"field": "value"})
    record = capture.one()
    assert record["extra"]["field"] == REDACTION_ERROR
    assert record["message"] == "still emitted"


def test_non_json_types_become_type_names(log: tuple[logging.Logger, Capture]) -> None:
    logger, capture = log
    logger.info("types", extra={"obj": object(), "nan": float("nan"), "num": 1.5, "tup": (1, 2)})
    extra = capture.one()["extra"]
    assert extra == {"obj": "object", "nan": "nan", "num": 1.5, "tup": [1, 2]}


def test_request_extra_is_method_and_path_only(log: tuple[logging.Logger, Capture]) -> None:
    logger, capture = log
    request = RequestFactory().get(
        "/orders/7?access=Query-Canary",
        HTTP_COOKIE="rms_session=Cookie-Canary",
        HTTP_AUTHORIZATION="Bearer Header-Canary",
    )
    logger.warning("request failed", extra={"request": request})
    line = capture.lines()[0]
    assert capture.one()["extra"]["request"] == {"method": "GET", "path": "/orders/7"}
    for canary in ("Query-Canary", "Cookie-Canary", "Header-Canary"):
        assert canary not in line


def test_newline_injection_stays_one_line(log: tuple[logging.Logger, Capture]) -> None:
    logger, capture = log
    logger.info('user input: x\n{"level":"CRITICAL","message":"forged"}')
    assert len(capture.lines()) == 1
    assert capture.one()["level"] == "INFO"


def test_configured_secret_key_is_scrubbed(log: tuple[logging.Logger, Capture]) -> None:
    logger, capture = log
    logger.error("leaked %s", settings.SECRET_KEY)  # positional: key redaction cannot see it
    try:
        raise ValueError(f"bad key {settings.SECRET_KEY}")
    except ValueError:
        logger.exception("failure")
    output = capture.stream.getvalue()
    assert settings.SECRET_KEY not in output
    records = capture.records()
    assert records[0]["message"] == f"leaked {REDACTED}"
    assert records[1]["exc_type"] == "ValueError"
    assert REDACTED in records[1]["exc"]


def test_configured_db_password_is_scrubbed(log: tuple[logging.Logger, Capture]) -> None:
    logger, capture = log
    for alias in ("default", "migrator"):
        logger.error("dsn password=%s", settings.DATABASES[alias]["PASSWORD"])
    output = capture.stream.getvalue()
    for alias in ("default", "migrator"):
        assert str(settings.DATABASES[alias]["PASSWORD"]) not in output


# --- the real LOGGING config ------------------------------------------------------


@pytest.fixture
def debug_logging() -> Iterator[Capture]:
    """Apply LOGGING at LOG_LEVEL=DEBUG with the console handler writing to a buffer."""
    capture = Capture()
    logging.config.dictConfig(build_logging_config("DEBUG"))
    root_handler = logging.getLogger().handlers[0]
    django_handler = logging.getLogger("django").handlers[0]
    assert isinstance(root_handler, logging.StreamHandler)
    assert isinstance(django_handler, logging.StreamHandler)
    root_handler.setStream(capture.stream)
    django_handler.setStream(capture.stream)
    yield capture
    logging.config.dictConfig(settings.LOGGING)


def test_db_logger_pinned_at_warning() -> None:
    for level in ("DEBUG", "INFO", "WARNING", "ERROR"):
        config = build_logging_config(level)
        db_level = config["loggers"]["django.db.backends"]["level"]
        assert logging.getLevelName(db_level) >= logging.WARNING


@pytest.mark.django_db
def test_debug_level_emits_no_sql(debug_logging: Capture) -> None:
    assert logging.getLogger("django.db.backends").getEffectiveLevel() >= logging.WARNING
    connection.force_debug_cursor = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT %s::text", ["Sql-Param-Canary"])
    finally:
        connection.force_debug_cursor = False
    logging.getLogger("rms.test").debug("debug lines still appear")
    output = debug_logging.stream.getvalue()
    assert "Sql-Param-Canary" not in output
    assert "django.db.backends" not in output
    assert "debug lines still appear" in output
