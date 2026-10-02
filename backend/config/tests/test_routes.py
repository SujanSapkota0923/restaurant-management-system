"""Route inventory (SC-11, SC-14, NT3-11): no default-open drift.

Every resolvable route is either in ``PUBLIC_ROUTES`` (each entry needs a
threat-model entry in a change record) or a DRF view that itself declares a
non-``AllowAny`` permission. Relying on the DenyAll default does not count as
declaring.

Tenant routes (change 0004, C-5(c)): every route with ``tenant_id`` is exactly
``api/v1/r/<uuid:tenant_id>/...``, served by a ``TenantAPIView`` that declares a
non-``AllowAny`` permission; a ``TenantAPIView`` is never routed without it; and
``config.urls`` has no tenant route at all in 0004.
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

from rms.tenancy.api.views import TenantAPIView

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


TENANT_ROUTE_PREFIX = "api/v1/r/<uuid:tenant_id>/"


def tenant_route_violations(urlconf: str) -> list[str]:
    violations: list[str] = []
    for route, callback in iter_routes(get_resolver(urlconf).url_patterns):
        view_cls = getattr(callback, "cls", None)
        initkwargs = getattr(callback, "initkwargs", {}) or {}
        is_tenant_view = isinstance(view_cls, type) and issubclass(view_cls, TenantAPIView)
        if "tenant_id" not in route:
            if is_tenant_view:
                violations.append(f"{route}: TenantAPIView routed without <uuid:tenant_id>")
            continue
        if not route.startswith(TENANT_ROUTE_PREFIX) or route.count("tenant_id") != 1:
            violations.append(f"{route}: tenant routes must start with {TENANT_ROUTE_PREFIX}")
        if not is_tenant_view:
            violations.append(f"{route}: tenant routes must be served by a TenantAPIView")
            continue
        assert isinstance(view_cls, type)
        permissions = _declared(view_cls, initkwargs, "permission_classes")
        if not permissions or not all(_is_plain_non_allowany(p) for p in permissions):
            violations.append(f"{route}: must declare a non-AllowAny permission")
    return violations


def tenant_routes(urlconf: str) -> list[str]:
    return [r for r, _ in iter_routes(get_resolver(urlconf).url_patterns) if "tenant_id" in r]


def test_root_urlconf_has_no_tenant_routes_in_0004() -> None:
    assert tenant_routes(settings.ROOT_URLCONF) == []
    assert tenant_route_violations(settings.ROOT_URLCONF) == []


def test_probe_tenant_routes_pass_both_scans() -> None:
    assert len(tenant_routes("rms.tenancy.tests.probe.urls")) == 2
    assert tenant_route_violations("rms.tenancy.tests.probe.urls") == []
    assert route_violations("rms.tenancy.tests.probe.urls") == []


def test_tenant_route_scan_flags_bad_routes() -> None:
    """Self-test (N-02): each route in the bad URLconf breaks one rule."""
    violations = tenant_route_violations("rms.tenancy.tests.probe.bad_urls")
    flagged = {v.split(": ")[0] for v in violations}
    assert flagged == {
        "api/v1/r/<str:tenant_id>/bad/str",
        "api/v1/bad/no-tenant",
        "v2/<uuid:tenant_id>/bad/prefix",
        "api/v1/r/<uuid:tenant_id>/bad/plain",
        "api/v1/r/<uuid:tenant_id>/bad/open",
    }


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
