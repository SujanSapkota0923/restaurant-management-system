"""Typed readers for environment variables.

Every reader raises ``ImproperlyConfigured`` on a bad value. Messages name the
variable and the rule only, never the value (SC-01): a secret that was put in
the wrong variable must not end up in a CI log or a crash report.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Sequence

from django.core.exceptions import ImproperlyConfigured

_TRUE = frozenset({"true", "1"})
_FALSE = frozenset({"false", "0"})
_PROXY_HEADER_NAME = re.compile(r"^HTTP_[A-Z0-9_]+$")

# Hosts a local or test settings module may serve (SC-04).
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "[::1]"})


def _raw(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def get_str(name: str, default: str | None = None) -> str | None:
    """Return the stripped value, or ``default`` when unset or blank."""
    value = _raw(name)
    return default if value is None else value


def require_str(name: str) -> str:
    """Return the stripped value; raise when unset or blank. There is no default."""
    value = _raw(name)
    if value is None:
        raise ImproperlyConfigured(f"{name} must be set")
    return value


def get_bool(name: str, default: bool = False) -> bool:
    """Accept exactly true/false/1/0 (case-insensitive, stripped); anything else raises (SC-03)."""
    value = _raw(name)
    if value is None:
        return default
    lowered = value.lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise ImproperlyConfigured(f"{name} must be one of: true, false, 1, 0")


def get_int(name: str, default: int | None = None) -> int | None:
    value = _raw(name)
    if value is None:
        return default
    try:
        return int(value, 10)
    except ValueError:
        raise ImproperlyConfigured(f"{name} must be an integer") from None


def require_int(name: str) -> int:
    value = get_int(name)
    if value is None:
        raise ImproperlyConfigured(f"{name} must be set")
    return value


def get_list(name: str, default: Sequence[str] = ()) -> list[str]:
    """Comma-separated list. Entries are stripped; an empty entry raises (SC-05)."""
    value = _raw(name)
    if value is None:
        return list(default)
    entries = [entry.strip() for entry in value.split(",")]
    if any(not entry for entry in entries):
        raise ImproperlyConfigured(f"{name} must not contain empty entries")
    return entries


def get_choice(name: str, choices: Iterable[str], default: str) -> str:
    allowed = tuple(choices)
    value = _raw(name)
    if value is None:
        return default
    upper = value.upper()
    if upper not in allowed:
        raise ImproperlyConfigured(f"{name} must be one of: {', '.join(allowed)}")
    return upper


def get_proxy_ssl_header(name: str) -> tuple[str, str] | None:
    """Parse ``HTTP_<NAME>=https`` strictly (SC-06). Unset means no proxy header."""
    value = _raw(name)
    if value is None:
        return None
    header, sep, expected = value.partition("=")
    if not sep or expected != "https" or not _PROXY_HEADER_NAME.match(header):
        raise ImproperlyConfigured(f"{name} must have the form HTTP_<HEADER_NAME>=https")
    return (header, expected)


def restrict_to_local_hosts(
    name: str, hosts: Sequence[str], extra: Iterable[str] = ()
) -> list[str]:
    """Raise unless every host is a loopback name (SC-04).

    A development or test settings module selected by mistake in a deployment
    then cannot serve a real hostname.
    """
    allowed = LOCAL_HOSTS | frozenset(extra)
    if any(host not in allowed for host in hosts):
        raise ImproperlyConfigured(
            f"{name} may only contain {', '.join(sorted(allowed))} in this settings module"
        )
    return list(hosts)
