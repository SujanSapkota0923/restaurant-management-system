"""Structured JSON logging with request context and secret redaction.

One JSON object per line. Defence in layers (SC-19, SC-20):

1. ``RedactionFilter`` replaces the value of any secret-like key in ``args`` and
   ``extra``, recursively, on copies (the caller's objects are never mutated).
   It cannot see positional ``%s`` arguments: never pass a secret positionally.
2. ``JsonFormatter`` serialises only JSON-native types; anything else becomes its
   type name, and Django's ``request`` extra becomes ``{method, path}``.
3. As its last step the formatter replaces exact occurrences of the configured
   secret values (secret key, database passwords) anywhere in the line.

Neither the filter nor the formatter ever raises: a broken field becomes a
marker string and the record is still emitted.
"""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from rms.core.context import membership_id_var, request_id_var, tenant_id_var

REDACTED = "[REDACTED]"
REDACTION_ERROR = "[REDACTION_ERROR]"
MAX_DEPTH = 8
_DEPTH_MARKER = "[MAX_DEPTH]"
_CYCLE_MARKER = "[CYCLE]"

# A key is secret-like when it contains any of these, case-insensitively.
# Over-redaction (e.g. "author", "shipping") is accepted.
SENSITIVE_KEY_PARTS: tuple[str, ...] = (
    "password",
    "passwd",
    "secret",
    "token",
    "key",
    "authorization",
    "cookie",
    "session",
    "csrf",
    "pin",
    "otp",
    "credential",
    "auth",
    "bearer",
    "signature",
    "dsn",
    "salt",
    "hash",
    "private",
)

# Attributes every LogRecord has; anything else on a record came from ``extra``.
_RECORD_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys()
    | {"message", "asctime", "taskName", "request_id", "tenant_id", "membership_id"}
)


def is_sensitive_key(key: object) -> bool:
    lowered = str(key).lower() if isinstance(key, str | int) else ""
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def redact(value: Any, _depth: int = 0, _seen: frozenset[int] = frozenset()) -> Any:
    """Return a copy of ``value`` with secret-like keys replaced. Never mutates."""
    if isinstance(value, Mapping | list | tuple | set | frozenset):
        if id(value) in _seen:
            return _CYCLE_MARKER
        if _depth >= MAX_DEPTH:
            return _DEPTH_MARKER
        seen = _seen | {id(value)}
        if isinstance(value, Mapping):
            out: dict[Any, Any] = {}
            for key, item in value.items():
                try:
                    out[key] = REDACTED if is_sensitive_key(key) else redact(item, _depth + 1, seen)
                except Exception:
                    out[key] = REDACTION_ERROR
            return out
        items = []
        for item in value:
            try:
                items.append(redact(item, _depth + 1, seen))
            except Exception:
                items.append(REDACTION_ERROR)
        return tuple(items) if isinstance(value, tuple) else items
    return value


class ContextFilter(logging.Filter):
    """Copy the request context into every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.tenant_id = tenant_id_var.get()
        record.membership_id = membership_id_var.get()
        return True


class RedactionFilter(logging.Filter):
    """Redact secret-like keys in ``args`` and ``extra``."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.args, Mapping):
                record.args = redact(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(redact(arg) for arg in record.args)
        except Exception:
            record.args = None
            record.msg = REDACTION_ERROR
        for key in list(record.__dict__):
            if key in _RECORD_ATTRS:
                continue
            try:
                value = record.__dict__[key]
                record.__dict__[key] = REDACTED if is_sensitive_key(key) else redact(value)
            except Exception:
                record.__dict__[key] = REDACTION_ERROR
        return True


def _json_key(key: object) -> str:
    if isinstance(key, str):
        return key
    return str(key) if isinstance(key, int) else type(key).__name__


def _jsonable(value: Any, _depth: int = 0, _seen: frozenset[int] = frozenset()) -> Any:
    """Keep JSON-native values; reduce anything else to its type name."""
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    from django.http import HttpRequest

    if isinstance(value, HttpRequest):
        # Never the query string, headers, cookies or body.
        return {"method": value.method, "path": value.path}
    if isinstance(value, Mapping | list | tuple):
        if id(value) in _seen:
            return _CYCLE_MARKER
        if _depth >= MAX_DEPTH:
            return _DEPTH_MARKER
        seen = _seen | {id(value)}
        if isinstance(value, Mapping):
            return {
                _json_key(key): _jsonable(item, _depth + 1, seen) for key, item in value.items()
            }
        return [_jsonable(item, _depth + 1, seen) for item in value]
    return type(value).__name__


def _known_secrets() -> list[str]:
    """The configured secret values, longest first. Empty if settings are not ready."""
    try:
        from django.conf import settings

        if not settings.configured:
            return []
        values = [settings.SECRET_KEY, *getattr(settings, "SECRET_KEY_FALLBACKS", [])]
        values += [db.get("PASSWORD") for db in settings.DATABASES.values()]
    except Exception:
        return []
    found = {value for value in values if isinstance(value, str) and value}
    return sorted(found, key=len, reverse=True)


def scrub_known_secrets(line: str) -> str:
    for secret in _known_secrets():
        # Both the raw and the JSON-escaped form can appear in a serialised line.
        escaped = json.dumps(secret)[1:-1]
        line = line.replace(secret, REDACTED).replace(escaped, REDACTED)
    return line


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        try:
            return scrub_known_secrets(self._format(record))
        except Exception:
            fallback = {
                "level": getattr(record, "levelname", "ERROR"),
                "logger": str(getattr(record, "name", "")),
                "message": "[FORMAT_ERROR]",
            }
            return scrub_known_secrets(json.dumps(fallback))

    def _format(self, record: logging.LogRecord) -> str:
        try:
            message = record.getMessage()
        except Exception:
            message = "[FORMAT_ERROR]"
        extra = {
            key: _jsonable(value)
            for key, value in record.__dict__.items()
            if key not in _RECORD_ATTRS
        }
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
            "request_id": getattr(record, "request_id", None),
            "tenant_id": getattr(record, "tenant_id", None),
            "membership_id": getattr(record, "membership_id", None),
            "extra": extra,
            "exc_type": None,
        }
        if record.exc_info and record.exc_info[0] is not None:
            payload["exc_type"] = record.exc_info[0].__name__
            try:
                payload["exc"] = self.formatException(record.exc_info)
            except Exception:
                payload["exc"] = "[FORMAT_ERROR]"
        # ensure_ascii keeps the line ASCII; json escapes newlines, so one record
        # is always exactly one line (no log forging).
        return json.dumps(payload, ensure_ascii=True, allow_nan=False)


def build_logging_config(level: str) -> dict[str, Any]:
    """The ``LOGGING`` dict. ``django.db.backends`` never logs below WARNING (SC-19a)."""
    db_level = logging.getLevelName(max(logging.getLevelName(level), logging.WARNING))
    handler = ["console"]
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "context": {"()": "rms.core.logging.ContextFilter"},
            "redact": {"()": "rms.core.logging.RedactionFilter"},
        },
        "formatters": {"json": {"()": "rms.core.logging.JsonFormatter"}},
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "json",
                "filters": ["context", "redact"],
            }
        },
        "root": {"handlers": handler, "level": level},
        "loggers": {
            # Replace Django's default handlers (plain-text console, mail_admins).
            "django": {"handlers": handler, "level": level, "propagate": False},
            "django.server": {"handlers": handler, "level": level, "propagate": False},
            "django.db.backends": {"level": db_level, "propagate": True},
        },
    }
