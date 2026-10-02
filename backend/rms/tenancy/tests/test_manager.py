"""``TenantManager`` / ``TenantQuerySet`` / ``TenantOwnedModel.save`` (C-7, C-10; N-06, N-10).

Outside a tenant transaction every access path raises ``TenantContextMissing``
(layer 2). Under tenant A, B's rows are unreachable through the manager, and
RLS (layer 3) also holds when the app layer is bypassed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from django.core.exceptions import FieldError
from django.db import NotSupportedError, ProgrammingError, connections, transaction
from django.db.models import Count
from psycopg import errors as pg_errors

from rms.tenancy.data.context import tenant_transaction
from rms.tenancy.data.rls import migration_tenant_context
from rms.tenancy.domain.errors import TenantContextMissing, TenantMismatch
from rms.tenancy.tests.factories import make_child, make_parent
from rms.tenancy.tests.harness import ISOLATION_DB, TwoTenants, raw_count, rows_visible_to
from rms.tenancy.tests.probe.models import ProbeChild, ProbeParent

pytestmark = ISOLATION_DB


@dataclass(frozen=True)
class Rows:
    a_parent: ProbeParent
    a_child: ProbeChild
    b_parent: ProbeParent
    b_child: ProbeChild


@pytest.fixture
def rows(two_tenants: TwoTenants) -> Rows:
    """Overlapping data: the same codes exist in A and B."""
    with tenant_transaction(two_tenants.a.id):
        a_child = make_child(parent=make_parent(code="same"), label="same")
    with tenant_transaction(two_tenants.b.id):
        b_child = make_child(parent=make_parent(code="same"), label="same")
    return Rows(a_child.parent, a_child, b_child.parent, b_child)


def _codes(tenant: Any) -> list[str]:
    with tenant_transaction(tenant.id):
        return sorted(ProbeParent.objects.values_list("code", flat=True))


OUTSIDE: dict[str, Callable[[Rows], Any]] = {
    "all": lambda r: list(ProbeParent.objects.all()),
    "filter": lambda r: list(ProbeParent.objects.filter(code="same")),
    "get": lambda r: ProbeParent.objects.get(pk=r.a_parent.pk),
    "values": lambda r: list(ProbeParent.objects.values("id")),
    "count": lambda r: ProbeParent.objects.count(),
    "aggregate": lambda r: ProbeParent.objects.aggregate(n=Count("id")),
    "exists": lambda r: ProbeParent.objects.exists(),
    "in_bulk": lambda r: ProbeParent.objects.in_bulk([r.a_parent.pk]),
    "iterator": lambda r: list(ProbeParent.objects.iterator()),
    "update": lambda r: ProbeParent.objects.update(code="x"),
    "delete": lambda r: ProbeParent.objects.all().delete(),
    "bulk_create": lambda r: ProbeParent.objects.bulk_create([ProbeParent(code="new")]),
    "bulk_update": lambda r: ProbeParent.objects.bulk_update([r.a_parent], ["code"]),
    "get_or_create": lambda r: ProbeParent.objects.get_or_create(code="new"),
    "raw": lambda r: ProbeParent.objects.raw("SELECT * FROM tenancy_probe_probeparent"),
    "extra": lambda r: ProbeParent.objects.extra(where=["true"]),
    # A fresh instance: the parent is not cached, so the descriptor must query.
    "forward related": lambda r: (
        ProbeChild(id=r.a_child.id, tenant_id=r.a_child.tenant_id, parent_id=r.a_parent.id).parent
    ),
    "reverse related": lambda r: list(r.a_parent.children.all()),
    "refresh_from_db": lambda r: r.a_parent.refresh_from_db(),
    "save update": lambda r: r.a_parent.save(),
    "save insert": lambda r: ProbeParent(code="new").save(),
    "instance delete": lambda r: r.a_child.delete(),
}


@pytest.mark.parametrize("operation", sorted(OUTSIDE))
def test_every_access_path_raises_outside_context(rows: Rows, operation: str) -> None:
    with pytest.raises(TenantContextMissing):
        OUTSIDE[operation](rows)


def test_nothing_changed_by_the_refused_operations(rows: Rows) -> None:
    for operation in OUTSIDE.values():
        with pytest.raises(TenantContextMissing):
            operation(rows)
    assert rows_visible_to(rows.a_parent.tenant_id, ProbeParent) == 1
    assert rows_visible_to(rows.b_parent.tenant_id, ProbeParent) == 1
    assert rows_visible_to(rows.a_parent.tenant_id, ProbeChild) == 1


# --- under tenant A, against B's IDs (N-06) ----------------------------------------


def test_get_of_b_raises_does_not_exist(rows: Rows, two_tenants: TwoTenants) -> None:
    with tenant_transaction(two_tenants.a.id):
        assert ProbeParent.objects.get(pk=rows.a_parent.pk) == rows.a_parent  # control
        with pytest.raises(ProbeParent.DoesNotExist):
            ProbeParent.objects.get(pk=rows.b_parent.pk)


def test_pk_in_returns_only_own_rows(rows: Rows, two_tenants: TwoTenants) -> None:
    with tenant_transaction(two_tenants.a.id):
        found = set(ProbeParent.objects.filter(pk__in=[rows.a_parent.pk, rows.b_parent.pk]))
    assert found == {rows.a_parent}


def test_update_and_delete_of_b_affect_nothing(rows: Rows, two_tenants: TwoTenants) -> None:
    with tenant_transaction(two_tenants.a.id):
        assert ProbeParent.objects.filter(pk=rows.b_parent.pk).update(code="hijacked") == 0
        deleted, _ = ProbeChild.objects.filter(pk=rows.b_child.pk).delete()
        assert deleted == 0
        assert ProbeParent.objects.filter(pk=rows.a_parent.pk).update(code="own") == 1  # control
    assert rows_visible_to(two_tenants.b.id, ProbeChild) == 1
    assert _codes(two_tenants.b) == ["same"]
    assert _codes(two_tenants.a) == ["own"]


def test_bulk_create_naming_b_raises_in_the_app(rows: Rows, two_tenants: TwoTenants) -> None:
    with tenant_transaction(two_tenants.a.id):
        with pytest.raises(TenantMismatch):
            ProbeParent.objects.bulk_create([ProbeParent(code="b-row", tenant_id=two_tenants.b.id)])
        created = ProbeParent.objects.bulk_create([ProbeParent(code="a-row")])  # control
        assert created[0].tenant_id == two_tenants.a.id
    assert _codes(two_tenants.b) == ["same"]


def test_save_naming_b_raises_in_the_app(rows: Rows, two_tenants: TwoTenants) -> None:
    with tenant_transaction(two_tenants.a.id):
        with pytest.raises(TenantMismatch):
            ProbeParent(code="b-row", tenant_id=two_tenants.b.id).save()
        with pytest.raises(TenantMismatch):
            rows.b_parent.save()  # loaded under B, saved under A
        with pytest.raises(TenantMismatch):
            rows.b_child.delete()
    assert _codes(two_tenants.b) == ["same"]
    assert rows_visible_to(two_tenants.b.id, ProbeChild) == 1


def test_bulk_update_naming_b_raises(rows: Rows, two_tenants: TwoTenants) -> None:
    with tenant_transaction(two_tenants.a.id), pytest.raises(TenantMismatch):
        ProbeParent.objects.bulk_update([rows.b_parent], ["code"])


def test_raw_insert_naming_b_is_rejected_by_with_check(rows: Rows, two_tenants: TwoTenants) -> None:
    with tenant_transaction(two_tenants.a.id), connections["default"].cursor() as cursor:
        with pytest.raises(ProgrammingError) as exc, transaction.atomic():
            cursor.execute(
                "INSERT INTO tenancy_probe_probeparent (id, tenant_id, code)"
                " VALUES (gen_random_uuid(), %s, 'raw-b')",
                [two_tenants.b.id],
            )
        assert isinstance(exc.value.__cause__, pg_errors.InsufficientPrivilege)
    assert _codes(two_tenants.b) == ["same"]


def test_select_related_tenant_fails_closed(rows: Rows, two_tenants: TwoTenants) -> None:
    """C-10 / F5: the join selects ungranted registry columns; never returns them."""
    with tenant_transaction(two_tenants.a.id):
        assert ProbeParent.objects.get(pk=rows.a_parent.pk).tenant.name == "Tenant A"  # control
        with pytest.raises(ProgrammingError) as exc, transaction.atomic():
            list(ProbeParent.objects.select_related("tenant"))
        assert isinstance(exc.value.__cause__, pg_errors.InsufficientPrivilege)


def test_tenant_fk_traversal_selects_only_granted_columns(
    rows: Rows, two_tenants: TwoTenants
) -> None:
    with tenant_transaction(two_tenants.a.id):
        tenant = ProbeParent.objects.get(pk=rows.a_parent.pk).tenant
        assert tenant.get_deferred_fields() == {"created_at", "updated_at"}
        with pytest.raises(ProgrammingError), transaction.atomic():
            tenant.created_at  # noqa: B018 - loading the deferred column is the test


def test_raw_and_extra_raise_under_context(two_tenants: TwoTenants) -> None:
    with tenant_transaction(two_tenants.a.id):
        with pytest.raises(NotSupportedError):
            ProbeParent.objects.raw("SELECT 1")
        with pytest.raises(NotSupportedError):
            ProbeParent.objects.extra(where=["true"])


# --- C-7(c), C-7(d), N-10: immutable keys -----------------------------------------------


@pytest.mark.parametrize("field", ["tenant", "tenant_id", "id", "pk"])
def test_update_of_key_fields_raises_in_the_app(
    rows: Rows, two_tenants: TwoTenants, field: str
) -> None:
    value: Any = two_tenants.b.id if field.startswith("tenant") else rows.b_parent.id
    if field == "tenant":
        value = two_tenants.b
    with tenant_transaction(two_tenants.a.id):
        with pytest.raises(FieldError):
            ProbeParent.objects.filter(pk=rows.a_parent.pk).update(**{field: value})
        with pytest.raises(FieldError):
            ProbeParent.objects.bulk_update([rows.a_parent], [field])
        with pytest.raises(FieldError):
            rows.a_parent.save(update_fields=[field])
    assert _codes(two_tenants.a) == ["same"]


def test_save_update_never_writes_the_tenant_key(rows: Rows, two_tenants: TwoTenants) -> None:
    """The default update_fields exclude tenant and id, so the app role's column
    grant (code only) is enough; a changed tenant_id raises before any SQL."""
    with tenant_transaction(two_tenants.a.id):
        parent = ProbeParent.objects.get(pk=rows.a_parent.pk)
        parent.code = "renamed"
        parent.save()
        parent.tenant_id = two_tenants.b.id
        with pytest.raises(TenantMismatch):
            parent.save()
    assert _codes(two_tenants.a) == ["renamed"]
    assert _codes(two_tenants.b) == ["same"]


def test_insert_fills_the_tenant_from_context(two_tenants: TwoTenants) -> None:
    with tenant_transaction(two_tenants.a.id):
        parent = ProbeParent(code="filled")
        parent.save()
        assert parent.tenant_id == two_tenants.a.id
    assert rows_visible_to(two_tenants.a.id, ProbeParent) == 1
    assert rows_visible_to(two_tenants.b.id, ProbeParent) == 0


# --- gate 8 additions (QA) ---------------------------------------------------------


def test_manager_filter_holds_when_rls_would_allow_the_row(
    rows: Rows, two_tenants: TwoTenants
) -> None:
    """Layer 2 on its own. The app context is A; the migrator connection has
    B's context, so RLS there shows B's row. The manager must still add
    tenant_id = A and return nothing. Without the app filter this returns B."""
    migrator = connections["migrator"]
    with (
        tenant_transaction(two_tenants.a.id),
        transaction.atomic(using="migrator"),
        migration_tenant_context(migrator, two_tenants.b.id),
    ):
        assert raw_count(ProbeParent, alias="migrator") == 1  # positive control: RLS shows B
        assert list(ProbeParent.objects.using("migrator").values_list("id", flat=True)) == []
        assert ProbeParent.objects.db_manager("migrator").count() == 0
        assert not ProbeChild.objects.using("migrator").filter(pk=rows.b_child.pk).exists()


@pytest.mark.parametrize("call", ["create", "get_or_create", "update_or_create"])
def test_create_paths_naming_b_raise_in_the_app(
    rows: Rows, two_tenants: TwoTenants, call: str
) -> None:
    b = two_tenants.b.id
    with tenant_transaction(two_tenants.a.id), pytest.raises(TenantMismatch):
        if call == "create":
            ProbeParent.objects.create(code="b-row", tenant_id=b)
        elif call == "get_or_create":
            ProbeParent.objects.get_or_create(code="b-row", defaults={"tenant_id": b})
        else:
            ProbeParent.objects.update_or_create(code="b-row", defaults={"tenant_id": b})
    assert _codes(two_tenants.b) == ["same"]
    assert _codes(two_tenants.a) == ["same"]


def test_update_or_create_cannot_move_a_row_to_b(rows: Rows, two_tenants: TwoTenants) -> None:
    # save() sees the changed tenant_id first (TenantMismatch), before any SQL.
    with tenant_transaction(two_tenants.a.id), pytest.raises(TenantMismatch):
        ProbeParent.objects.update_or_create(code="same", defaults={"tenant_id": two_tenants.b.id})
    assert rows_visible_to(two_tenants.a.id, ProbeParent) == 1
    assert rows_visible_to(two_tenants.b.id, ProbeParent) == 1
