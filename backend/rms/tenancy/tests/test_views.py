"""``TenantAPIView`` (D1-D3, C-4, C-6; N-01, N-02, N-09, N-15; criterion 6).

Group R (resolved in the view: unknown, suspended, closed, and active with the
closed hook) must be indistinguishable: status, body bytes without the request
ID, headers without ``X-Request-ID``, and the number of queries; no query may
touch a tenant table. Group M (malformed path tenants, never routed) must give
the same status, code and message. Each with GET, a POST with an invalid body,
and an unsupported method.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from django.db import connections
from django.test import Client
from django.test.utils import CaptureQueriesContext

from rms.core.api.errors import MESSAGES
from rms.core.context import tenant_id_var
from rms.tenancy.data.context import tenant_transaction
from rms.tenancy.data.models import RestaurantStatus
from rms.tenancy.tests.factories import make_restaurant
from rms.tenancy.tests.harness import ISOLATION_DB, TwoTenants, rows_visible_to
from rms.tenancy.tests.probe import views as probe_views
from rms.tenancy.tests.probe.models import ProbeParent

pytestmark = [ISOLATION_DB, pytest.mark.urls("rms.tenancy.tests.probe.urls")]

# The test client's responses (with .json()) have no public type in the stubs.
Send = Callable[[Client, str], Any]

METHODS: dict[str, Send] = {
    "get": lambda c, path: c.get(path),
    "post-invalid-body": lambda c, path: c.generic(
        "POST", path, b'{"a": ', content_type="application/json"
    ),
    "unsupported-method": lambda c, path: c.put(path, b"{}", content_type="application/json"),
}


@pytest.fixture
def client() -> Client:
    return Client(raise_request_exception=False)


def closed_path(tenant: object) -> str:
    return f"/api/v1/r/{tenant}/probe/closed"


def write_path(tenant: object, outcome: str) -> str:
    return f"/api/v1/r/{tenant}/probe/write/{outcome}"


def fingerprint(client: Client, send: Send, path: str) -> dict[str, Any]:
    with CaptureQueriesContext(connections["default"]) as queries:
        response = send(client, path)
    request_id = response["X-Request-ID"]
    return {
        "status": response.status_code,
        "body": response.content.replace(request_id.encode(), b""),
        "headers": {k: v for k, v in response.items() if k != "X-Request-ID"},
        "queries": len(queries),
        "sql": [q["sql"] for q in queries.captured_queries],
        "json": response.json(),
    }


@pytest.fixture
def group_r(two_tenants: TwoTenants) -> dict[str, uuid.UUID]:
    return {
        "unknown": uuid.uuid4(),
        "suspended": make_restaurant(status=RestaurantStatus.SUSPENDED).id,
        "closed": make_restaurant(status=RestaurantStatus.CLOSED).id,
        "active-closed-hook": two_tenants.a.id,
    }


@pytest.mark.parametrize("method", sorted(METHODS))
def test_group_r_is_indistinguishable(
    client: Client, group_r: dict[str, uuid.UUID], method: str
) -> None:
    results = {
        case: fingerprint(client, METHODS[method], closed_path(tenant))
        for case, tenant in group_r.items()
    }
    first = results["unknown"]
    assert first["status"] == 404
    assert first["json"]["error"]["code"] == "not_found"
    assert first["json"]["error"]["message"] == MESSAGES["not_found"]
    assert b"reached" not in first["body"]
    for case, result in results.items():
        for key in ("status", "body", "headers", "queries"):
            assert result[key] == first[key], (case, key)
        assert not [sql for sql in result["sql"] if "tenancy_probe" in sql], case
    # BEGIN, set the context, one registry lookup, ROLLBACK. Nothing else.
    sql = first["sql"]
    assert len(sql) == 4, sql
    assert sql[0] == "BEGIN"
    assert sql[1].startswith(
        "SELECT current_setting('app.tenant_id', true), current_setting('app.user_id', true),"
    )
    assert sql[2].startswith(
        'SELECT "tenancy_restaurant"."id" AS "id", "tenancy_restaurant"."status"'
    )
    assert sql[3] == "ROLLBACK"


MALFORMED = {
    "not-a-uuid": "not-a-uuid",
    "upper-case": str(uuid.UUID(int=0xABCDEF)).upper(),
    "number": "12345",
    "braces": "{" + str(uuid.UUID(int=0xABCDEF)) + "}",
    "no-hyphens": uuid.UUID(int=0xABCDEF).hex,
}


@pytest.mark.parametrize("method", sorted(METHODS))
@pytest.mark.parametrize("malformed", sorted(MALFORMED))
def test_group_m_matches_group_r(
    client: Client, group_r: dict[str, uuid.UUID], method: str, malformed: str
) -> None:
    expected = fingerprint(client, METHODS[method], closed_path(group_r["unknown"]))["json"]
    result = fingerprint(client, METHODS[method], closed_path(MALFORMED[malformed]))
    assert result["status"] == 404
    assert result["json"]["error"]["code"] == expected["error"]["code"]
    assert result["json"]["error"]["message"] == expected["error"]["message"]
    assert result["queries"] == 0


def test_default_hook_gives_404_for_an_active_tenant(
    client: Client, two_tenants: TwoTenants
) -> None:
    """N-02 / D3: until 0005/0006 nothing passes check_principal."""
    response = client.get(closed_path(two_tenants.a.id))
    assert response.status_code == 404
    assert "reached" not in response.content.decode()
    assert tenant_id_var.get() is None


def test_write_view_rejects_inactive_tenant_before_writing(
    client: Client, two_tenants: TwoTenants
) -> None:
    suspended = make_restaurant(status=RestaurantStatus.SUSPENDED).id
    response = client.post(
        write_path(suspended, "ok"), {"code": "x"}, content_type="application/json"
    )
    assert response.status_code == 404
    assert rows_visible_to(suspended, ProbeParent) == 0


# --- D2 / C-4 / N-15: the response decides the transaction --------------------------


def post(client: Client, tenant: uuid.UUID, outcome: str, code: str) -> Any:
    return client.post(write_path(tenant, outcome), {"code": code}, content_type="application/json")


def codes(tenant: uuid.UUID) -> list[str]:
    with tenant_transaction(tenant):
        return sorted(ProbeParent.objects.values_list("code", flat=True))


def test_success_commits(client: Client, two_tenants: TwoTenants) -> None:
    response = post(client, two_tenants.a.id, "ok", "first")
    assert response.status_code == 201
    assert rows_visible_to(two_tenants.a.id, ProbeParent) == 1
    assert codes(two_tenants.a.id) == ["first"]
    assert rows_visible_to(two_tenants.b.id, ProbeParent) == 0


def test_on_commit_after_a_tenant_view_runs_without_context(
    client: Client, two_tenants: TwoTenants, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C-1(c): the tenant context and the log context are both reset inside the
    transaction, so an on_commit callback registered by a view sees neither."""
    seen: list[dict[str, Any]] = []
    monkeypatch.setattr(probe_views, "ON_COMMIT_SEEN", seen)
    response = post(client, two_tenants.a.id, "on-commit", "committed")
    assert response.status_code == 201
    assert seen == [{"tenant": "missing", "log_tenant_id": None}]
    assert codes(two_tenants.a.id) == ["committed"]  # positive control: it did commit


@pytest.mark.parametrize(
    ("outcome", "status", "code"),
    [
        ("validation", 400, "validation_error"),
        ("not-found", 404, "not_found"),
        ("permission", 403, "permission_denied"),
        ("conflict", 409, None),
        ("crash", 500, "server_error"),
        ("swallow", 500, "server_error"),
        ("stream", 500, "server_error"),
    ],
)
def test_failure_after_a_write_leaves_no_row(
    client: Client, two_tenants: TwoTenants, outcome: str, status: int, code: str | None
) -> None:
    """The carried "real row-write rollback test" (0003): a write followed by a
    4xx, an unhandled error, a swallowed DB error or a streaming response
    leaves nothing behind. Positive control: the earlier 201 is still there."""
    assert post(client, two_tenants.a.id, "ok", "first").status_code == 201
    response = post(client, two_tenants.a.id, outcome, "second")
    assert response.status_code == status
    if code is not None:
        assert response.json()["error"]["code"] == code
    assert rows_visible_to(two_tenants.a.id, ProbeParent) == 1
    assert codes(two_tenants.a.id) == ["first"]


def test_duplicate_code_response_reveals_no_constraint(
    client: Client, two_tenants: TwoTenants
) -> None:
    """N-09: the same code in A and B succeeds; a duplicate in A fails without
    the constraint name in the response."""
    assert post(client, two_tenants.a.id, "ok", "dup").status_code == 201
    assert post(client, two_tenants.b.id, "ok", "dup").status_code == 201
    response = post(client, two_tenants.a.id, "ok", "dup")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "server_error"
    body = response.content.decode().lower()
    for leak in ("probe_parent_tenant_code_uniq", "duplicate", "unique", "dup"):
        assert leak not in body
    assert codes(two_tenants.a.id) == ["dup"]
    assert codes(two_tenants.b.id) == ["dup"]


# --- gate 8 additions (QA) ---------------------------------------------------------


@pytest.mark.parametrize("state", ["unknown", "suspended", "closed"])
def test_write_view_rejects_every_non_active_tenant_before_writing(
    client: Client, two_tenants: TwoTenants, state: str
) -> None:
    """The open-hook view reaches the handler only for an active tenant. The
    closed-hook group R test cannot show this, because the hook gives 404
    anyway."""
    tenant = (
        uuid.uuid4() if state == "unknown" else make_restaurant(status=RestaurantStatus(state)).id
    )
    response = post(client, tenant, "ok", "x")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert rows_visible_to(tenant, ProbeParent) == 0
    # Positive control: the same request for an active tenant writes.
    assert post(client, two_tenants.a.id, "ok", "x").status_code == 201
    assert rows_visible_to(two_tenants.a.id, ProbeParent) == 1


def test_tenant_comes_only_from_the_path(client: Client, two_tenants: TwoTenants) -> None:
    """C-5(d), ADR-0006: B named in the body, the query string and a header
    is ignored; the write lands in the path tenant A only."""
    a, b = two_tenants.a.id, two_tenants.b.id
    response = client.post(
        write_path(a, "ok") + f"?tenant_id={b}&tenant={b}",
        {"code": "path-only", "tenant_id": str(b), "tenant": str(b)},
        content_type="application/json",
        headers={"X-Tenant-ID": str(b), "X-Restaurant-ID": str(b)},
    )
    assert response.status_code == 201
    assert codes(a) == ["path-only"]
    assert rows_visible_to(b, ProbeParent) == 0
    # Control: the same request on B's path lands in B.
    assert post(client, b, "ok", "b-path").status_code == 201
    assert codes(b) == ["b-path"]


def test_log_context_is_bound_only_after_resolution(
    client: Client, two_tenants: TwoTenants, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C-1(g), T4-24: an unvalidated path tenant never reaches the log
    context. It is bound only after resolution succeeded, and reset after
    the request."""
    from rms.tenancy.services.resolution import resolve_active_tenant as real_resolve

    seen: list[tuple[str, str | None]] = []

    def spy_resolve(tenant_id: uuid.UUID) -> Any:
        seen.append(("resolve", tenant_id_var.get()))
        return real_resolve(tenant_id)

    def spy_permission(self: Any, request: Any, view: Any) -> bool:
        seen.append(("permission", tenant_id_var.get()))
        return True

    # The name TenantAPIView.resolve_active_tenant calls (imported into its module).
    monkeypatch.setattr("rms.tenancy.api.views.resolve_tenant", spy_resolve)
    monkeypatch.setattr(probe_views.AllowProbe, "has_permission", spy_permission)
    suspended = make_restaurant(status=RestaurantStatus.SUSPENDED).id
    a = two_tenants.a.id
    expected = {
        uuid.uuid4(): (404, [("resolve", None)]),
        suspended: (404, [("resolve", None)]),
        a: (201, [("resolve", None), ("permission", str(a))]),  # positive control
    }
    for tenant, (status, trace) in expected.items():
        seen.clear()
        assert post(client, tenant, "ok", "logged").status_code == status
        assert seen == trace, tenant
        assert tenant_id_var.get() is None
