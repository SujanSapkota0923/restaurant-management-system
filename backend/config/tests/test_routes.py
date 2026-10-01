"""Route inventory (SC-11, SC-14, NT3-11): no default-open drift.

Every resolvable route is either in ``PUBLIC_ROUTES`` (each entry needs a
threat-model entry in a change record) or a DRF view that itself declares a
non-``AllowAny`` permission. Relying on the DenyAll default does not count as
declaring.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

import pytest
from django.conf import settings
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.views import APIView

# Adding an entry needs a threat-model entry (change 0003, T3-09/T3-10).
PUBLIC_ROUTES = frozenset({"health/live", "health/ready"})


def iter_routes(
    patterns: Sequence[URLPattern | URLResolver], prefix: str = ""
) -> Iterator[tuple[str, Any]]:
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            yield from iter_routes(pattern.url_patterns, prefix + str(pattern.pattern))
        else:
            yield prefix + str(pattern.pattern), pattern.callback


def _declared(view_cls: type[APIView], initkwargs: dict[str, Any], attr: str) -> Any:
    """The attribute value if the view (not DRF's APIView base) declares it, else None."""
    if attr in initkwargs:
        return initkwargs[attr]
    for klass in view_cls.__mro__:
        if attr in vars(klass):
            return None if klass is APIView else vars(klass)[attr]
    return None


def _is_plain_non_allowany(permission: Any) -> bool:
    return (
        isinstance(permission, type)
        and issubclass(permission, BasePermission)
        and not issubclass(permission, AllowAny)
    )


def route_violations(urlconf: str) -> list[str]:
    violations: list[str] = []
    seen_public: set[str] = set()
    for route, callback in iter_routes(get_resolver(urlconf).url_patterns):
        view_cls = getattr(callback, "cls", None)
        initkwargs = getattr(callback, "initkwargs", {}) or {}
        if not (isinstance(view_cls, type) and issubclass(view_cls, APIView)):
            violations.append(f"{route}: not a DRF view, so it declares no permission")
            continue
        permissions = _declared(view_cls, initkwargs, "permission_classes")
        if route in PUBLIC_ROUTES:
            seen_public.add(route)
            authentication = _declared(view_cls, initkwargs, "authentication_classes")
            if list(permissions or []) != [AllowAny] or authentication != []:
                violations.append(f"{route}: public route must declare [AllowAny] and no auth")
            continue
        if not permissions or not all(_is_plain_non_allowany(p) for p in permissions):
            violations.append(f"{route}: must declare a non-AllowAny permission")
    violations.extend(
        f"{route}: listed in PUBLIC_ROUTES but not routed"
        for route in sorted(PUBLIC_ROUTES - seen_public)
    )
    return violations


def test_root_urlconf_has_no_open_routes() -> None:
    assert route_violations(settings.ROOT_URLCONF) == []


def test_scan_flags_unlisted_and_test_only_routes() -> None:
    """Self-test: the test URLconf adds routes that the scan must reject."""
    violations = route_violations("rms.core.tests.urls")
    flagged = {v.split(":")[0] for v in violations}
    assert flagged == {
        "t/raise",
        "t/drf-raise",
        "t/parse",
        "t/validation",
        "t/undeclared",
        "t/csrf",
        "t/rollback/<outcome>",
    }


def test_root_urlconf_has_no_test_views() -> None:
    for _, callback in iter_routes(get_resolver(settings.ROOT_URLCONF).url_patterns):
        module = getattr(getattr(callback, "cls", callback), "__module__", "")
        assert ".tests" not in module


def test_drf_default_permission_is_deny_all() -> None:
    assert settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] == [
        "rms.core.api.permissions.DenyAll"
    ]


@pytest.mark.urls("rms.core.tests.urls")
def test_undeclared_drf_view_is_denied(client: Client) -> None:
    response = client.get("/t/undeclared")
    assert response.status_code == 403
    assert response["Content-Type"] == "application/json"
    assert response.json()["error"]["code"] == "permission_denied"
    assert "reached" not in response.content.decode()


def test_admin_is_not_mounted(client: Client) -> None:
    response = client.get("/admin/")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_no_contrib_apps_installed() -> None:
    assert not [app for app in settings.INSTALLED_APPS if app.startswith("django.contrib")]
