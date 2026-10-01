"""Startup validation for every non-local, non-test settings module.

``validate_production(globals())`` must be the last statement of any such module
(SC-07). It collects every failure into one ``ImproperlyConfigured`` whose
message names settings and rules only, never values (SC-01).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from config import env

MIN_HSTS_SECONDS = 31_536_000
MIN_SECRET_KEY_LENGTH = 50
MIN_SECRET_KEY_UNIQUE_CHARS = 5
# The env example uses this marker for every value that must be replaced.
PLACEHOLDER_MARKER = "change-me"
_ALLOWED_SAMESITE = frozenset({"Lax", "Strict"})


def _weak_secret_key(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return True
    return (
        len(value) < MIN_SECRET_KEY_LENGTH
        or len(set(value)) < MIN_SECRET_KEY_UNIQUE_CHARS
        or value.startswith("django-insecure-")
        or PLACEHOLDER_MARKER in value
    )


def _as_list(value: object) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list | tuple | set | frozenset):
        return list(value)
    return [value]


def _origin_problem(origin: object, allowed_hosts: set[str]) -> list[str]:
    """Return the rule numbers (5, 11) a CSRF trusted origin breaks."""
    if not isinstance(origin, str):
        return ["5"]
    problems = []
    if not origin.startswith("https://") or "*" in origin:
        problems.append("5")
    try:
        parts = urlsplit(origin)
        hostname = parts.hostname
    except ValueError:
        return [*problems, "11"]
    if (
        hostname is None
        or hostname.lower() not in allowed_hosts
        or parts.path
        or parts.query
        or parts.fragment
        or parts.username is not None
        or parts.password is not None
    ):
        problems.append("11")
    return problems


def validate_production(settings: Mapping[str, Any]) -> None:
    failures: list[str] = []

    # 1. Debug off, in the module and in the environment.
    if settings.get("DEBUG"):
        failures.append("DEBUG must be false")
    try:
        if env.get_bool("DJANGO_DEBUG"):
            failures.append("DJANGO_DEBUG must be false")
    except ImproperlyConfigured as exc:
        failures.append(str(exc))

    # 2. A strong secret key.
    if _weak_secret_key(settings.get("SECRET_KEY")):
        failures.append(
            "SECRET_KEY must be set, at least 50 characters with 5 distinct characters, "
            "not start with django-insecure- and not contain the placeholder marker"
        )

    # 3. A single explicit host.
    allowed_hosts = _as_list(settings.get("ALLOWED_HOSTS"))
    if not allowed_hosts or any(
        not isinstance(host, str) or not host or host == "*" or "*" in host or host.startswith(".")
        for host in allowed_hosts
    ):
        failures.append("ALLOWED_HOSTS must list explicit host names without wildcards")

    # 4. No wildcard CORS with credentials (tripwire; no CORS package is installed).
    if settings.get("CORS_ALLOW_CREDENTIALS") and (
        settings.get("CORS_ALLOW_ALL_ORIGINS")
        or "*" in _as_list(settings.get("CORS_ALLOWED_ORIGINS"))
    ):
        failures.append("CORS must not allow all origins while allowing credentials")

    # 5 and 11. Trusted origins: https only, same host as ALLOWED_HOSTS, no path.
    host_set = {host.lower() for host in allowed_hosts if isinstance(host, str)}
    origin_rules: set[str] = set()
    for origin in _as_list(settings.get("CSRF_TRUSTED_ORIGINS")):
        origin_rules.update(_origin_problem(origin, host_set))
    if "5" in origin_rules:
        failures.append("CSRF_TRUSTED_ORIGINS entries must use https:// and contain no wildcard")
    if "11" in origin_rules:
        failures.append(
            "CSRF_TRUSTED_ORIGINS entries must name a host in ALLOWED_HOSTS and have no path"
        )

    # 6. Secure cookies and HSTS.
    if not settings.get("SESSION_COOKIE_SECURE") or not settings.get("CSRF_COOKIE_SECURE"):
        failures.append("SESSION_COOKIE_SECURE and CSRF_COOKIE_SECURE must be true")
    hsts = settings.get("SECURE_HSTS_SECONDS")
    if not isinstance(hsts, int) or isinstance(hsts, bool) or hsts < MIN_HSTS_SECONDS:
        failures.append("SECURE_HSTS_SECONDS must be at least 31536000")

    # 7. HttpOnly session cookie, SameSite on both cookies.
    if not settings.get("SESSION_COOKIE_HTTPONLY"):
        failures.append("SESSION_COOKIE_HTTPONLY must be true")
    if (
        settings.get("SESSION_COOKIE_SAMESITE") not in _ALLOWED_SAMESITE
        or settings.get("CSRF_COOKIE_SAMESITE") not in _ALLOWED_SAMESITE
    ):
        failures.append("SESSION_COOKIE_SAMESITE and CSRF_COOKIE_SAMESITE must be Lax or Strict")

    # 8. __Host- cookies: prefixed name, no domain, path "/".
    for prefix in ("SESSION", "CSRF"):
        name = settings.get(f"{prefix}_COOKIE_NAME")
        if (
            not isinstance(name, str)
            or not name.startswith("__Host-")
            or settings.get(f"{prefix}_COOKIE_DOMAIN") is not None
            or settings.get(f"{prefix}_COOKIE_PATH") != "/"
        ):
            failures.append(
                f"{prefix}_COOKIE_NAME must start with __Host-, "
                f"{prefix}_COOKIE_DOMAIN must be None and {prefix}_COOKIE_PATH must be /"
            )

    # 9. SSL redirect, nosniff, frame denial.
    if not settings.get("SECURE_SSL_REDIRECT"):
        failures.append("SECURE_SSL_REDIRECT must be true")
    if not settings.get("SECURE_CONTENT_TYPE_NOSNIFF"):
        failures.append("SECURE_CONTENT_TYPE_NOSNIFF must be true")
    if settings.get("X_FRAME_OPTIONS") != "DENY":
        failures.append("X_FRAME_OPTIONS must be DENY")

    # 10. Never trust forwarded host or port headers.
    if settings.get("USE_X_FORWARDED_HOST") or settings.get("USE_X_FORWARDED_PORT"):
        failures.append("USE_X_FORWARDED_HOST and USE_X_FORWARDED_PORT must be false")

    # 12. Every fallback key is as strong as the main key.
    if any(_weak_secret_key(key) for key in _as_list(settings.get("SECRET_KEY_FALLBACKS"))):
        failures.append("SECRET_KEY_FALLBACKS entries must each meet the SECRET_KEY rule")

    if failures:
        raise ImproperlyConfigured("Invalid production settings: " + "; ".join(failures))
