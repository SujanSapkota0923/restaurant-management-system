"""Database layer (RLS, composite FK, grants) as the app role, with the app
layer bypassed: raw SQL and ORM querysets (C3-3, C3-9, D4, D5; N-08, N-09,
N-10, N-12, N-13; criterion 5).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from django.db import DatabaseError, IntegrityError, ProgrammingError, connections, transaction
from psycopg import errors as pg_errors

from rms.tenancy.data.context import tenant_transaction
from rms.tenancy.data.models import Restaurant, RestaurantStatus
from rms.tenancy.tests.factories import make_child, make_parent, make_restaurant
from rms.tenancy.tests.harness import (
    ISOLATION_DB,
    TwoTenants,
    raw_count,
    registry_count,
    rows_visible_to,
)
from rms.tenancy.tests.probe.models import ProbeChild, ProbeParent

pytestmark = ISOLATION_DB

PARENT = "tenancy_probe_probeparent"


@pytest.fixture
def parents(two_tenants: TwoTenants) -> dict[str, ProbeParent]:
    with tenant_transaction(two_tenants.a.id):
        a = make_parent(code="same")
    with tenant_transaction(two_tenants.b.id):
        b = make_parent(code="same")
    return {"a": a, "b": b}


def execute(query: str, params: list[Any] | None = None) -> int:
    """Run ``query`` on ``default`` inside a savepoint; return the row count."""
    with transaction.atomic(), connections["default"].cursor() as cursor:
        cursor.execute(query, params or [])
        return int(cursor.rowcount)


def assert_denied(query: str, params: list[Any] | None = None) -> None:
    with pytest.raises(ProgrammingError) as exc:
        execute(query, params)
    assert isinstance(exc.value.__cause__, pg_errors.InsufficientPrivilege)


# --- no context: 0 rows, writes rejected ---------------------------------------


def test_no_context_reads_nothing_and_cannot_write(
    parents: dict[str, ProbeParent], two_tenants: TwoTenants
) -> None:
    assert rows_visible_to(two_tenants.a.id, ProbeParent) == 1  # positive control
    assert raw_count(ProbeParent) == 0
    assert execute(f"UPDATE {PARENT} SET code = 'x'") == 0  # noqa: S608 - constant table name
    assert execute(f"DELETE FROM {PARENT}") == 0  # noqa: S608
    assert_denied(
        f"INSERT INTO {PARENT} (id, tenant_id, code) VALUES (gen_random_uuid(), %s, 'x')",  # noqa: S608
        [two_tenants.a.id],
    )
    assert rows_visible_to(two_tenants.a.id, ProbeParent) == 1


def test_migrator_without_context_reads_nothing_under_force(
    parents: dict[str, ProbeParent], two_tenants: TwoTenants
) -> None:
    """F4: why assertions never read tenant tables through the migrator without context."""
    assert raw_count(ProbeParent, alias="migrator") == 0
    assert rows_visible_to(two_tenants.a.id, ProbeParent, alias="migrator") == 1


# --- tenant A against B's rows ------------------------------------------------------


def test_a_cannot_read_or_write_b(parents: dict[str, ProbeParent], two_tenants: TwoTenants) -> None:
    b_id = parents["b"].id
    with tenant_transaction(two_tenants.a.id):
        assert raw_count(ProbeParent) == 1  # A's own row
        with connections["default"].cursor() as cursor:
            cursor.execute(f"SELECT count(*) FROM {PARENT} WHERE id = %s", [b_id])  # noqa: S608
            assert cursor.fetchone() == (0,)
        assert execute(f"UPDATE {PARENT} SET code = 'hijacked' WHERE id = %s", [b_id]) == 0  # noqa: S608
        assert execute(f"DELETE FROM {PARENT} WHERE id = %s", [b_id]) == 0  # noqa: S608
        assert_denied(
            f"INSERT INTO {PARENT} (id, tenant_id, code) VALUES (gen_random_uuid(), %s, 'x')",  # noqa: S608
            [two_tenants.b.id],
        )
    assert rows_visible_to(two_tenants.b.id, ProbeParent) == 1
    with tenant_transaction(two_tenants.b.id):
        assert ProbeParent.objects.get().code == "same"


# --- N-08: composite FK ---------------------------------------------------------------


def _assert_fk_violation(exc: pytest.ExceptionInfo[IntegrityError]) -> None:
    assert isinstance(exc.value.__cause__, pg_errors.ForeignKeyViolation)


def test_cross_tenant_child_insert_fails_at_the_db(
    parents: dict[str, ProbeParent], two_tenants: TwoTenants
) -> None:
    with tenant_transaction(two_tenants.a.id):
        make_child(parent=parents["a"])  # control: same tenant works
        with pytest.raises(IntegrityError) as orm, transaction.atomic():
            # No app check on the FK value: only the composite FK stops it.
            ProbeChild(parent_id=parents["b"].id).save()
        _assert_fk_violation(orm)
        with pytest.raises(IntegrityError) as raw, transaction.atomic():
            execute(
                "INSERT INTO tenancy_probe_probechild (id, tenant_id, parent_id, label)"
                " VALUES (gen_random_uuid(), %s, %s, 'x')",
                [two_tenants.a.id, parents["b"].id],
            )
        _assert_fk_violation(raw)
    assert rows_visible_to(two_tenants.a.id, ProbeChild) == 1


def test_cross_tenant_child_update_fails_at_the_db(
    parents: dict[str, ProbeParent], two_tenants: TwoTenants
) -> None:
    with tenant_transaction(two_tenants.a.id):
        child = make_child(parent=parents["a"])
        with pytest.raises(IntegrityError) as orm, transaction.atomic():
            ProbeChild.objects.filter(pk=child.pk).update(parent_id=parents["b"].id)
        _assert_fk_violation(orm)
        with pytest.raises(IntegrityError) as raw, transaction.atomic():
            execute(
                "UPDATE tenancy_probe_probechild SET parent_id = %s WHERE id = %s",
                [parents["b"].id, child.id],
            )
        _assert_fk_violation(raw)
        assert ProbeChild.objects.get(pk=child.pk).parent_id == parents["a"].id


def test_parent_with_children_cannot_be_deleted(
    parents: dict[str, ProbeParent], two_tenants: TwoTenants
) -> None:
    with tenant_transaction(two_tenants.a.id):
        make_child(parent=parents["a"])
        with pytest.raises(IntegrityError), transaction.atomic():
            execute(f"DELETE FROM {PARENT} WHERE id = %s", [parents["a"].id])  # noqa: S608
    assert rows_visible_to(two_tenants.a.id, ProbeParent) == 1


# --- N-09: per-tenant uniqueness --------------------------------------------------------


def test_same_code_in_both_tenants_and_duplicate_in_one(
    parents: dict[str, ProbeParent], two_tenants: TwoTenants
) -> None:
    assert parents["a"].code == parents["b"].code == "same"  # same code in A and B worked
    with tenant_transaction(two_tenants.a.id):
        with pytest.raises(IntegrityError) as exc, transaction.atomic():
            ProbeParent(code="same").save()
        assert isinstance(exc.value.__cause__, pg_errors.UniqueViolation)
    assert rows_visible_to(two_tenants.a.id, ProbeParent) == 1


# --- N-10: the tenant key cannot be updated by the app role --------------------------


@pytest.mark.parametrize("column", ["tenant_id", "id"])
def test_app_role_cannot_update_key_columns(
    parents: dict[str, ProbeParent], two_tenants: TwoTenants, column: str
) -> None:
    new_value = two_tenants.b.id if column == "tenant_id" else uuid.uuid4()
    with tenant_transaction(two_tenants.a.id):
        assert execute(f"UPDATE {PARENT} SET code = 'ok' WHERE id = %s", [parents["a"].id]) == 1  # noqa: S608
        assert_denied(
            f"UPDATE {PARENT} SET {column} = %s WHERE id = %s",  # noqa: S608 - parametrized constant
            [new_value, parents["a"].id],
        )
    with tenant_transaction(two_tenants.a.id):
        assert ProbeParent.objects.get(pk=parents["a"].id).code == "ok"


# --- N-12: django_migrations is read-only for the app role ---------------------------


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO django_migrations (app, name, applied) VALUES ('x', 'x', now())",
        "UPDATE django_migrations SET name = name",
        "DELETE FROM django_migrations",
        "TRUNCATE django_migrations",
    ],
    ids=["insert", "update", "delete", "truncate"],
)
def test_app_role_cannot_write_django_migrations(statement: str) -> None:
    assert execute("SELECT 1 FROM django_migrations LIMIT 1") >= 0  # SELECT stays
    assert_denied(statement)


# --- N-13: the registry as the app role ---------------------------------------------------


def test_registry_as_the_app_role(two_tenants: TwoTenants) -> None:
    a, b = two_tenants.a.id, two_tenants.b.id
    assert registry_count() == 2  # positive control, as the owner
    assert list(Restaurant.objects.values_list("id", flat=True)) == []  # no context
    with tenant_transaction(a):
        assert list(Restaurant.objects.values_list("id", flat=True)) == [a]
        assert not Restaurant.objects.filter(pk=b).exists()
        assert_denied("SELECT created_at FROM tenancy_restaurant")
        assert_denied(
            "INSERT INTO tenancy_restaurant (id, name, status, created_at, updated_at)"
            " VALUES (gen_random_uuid(), 'x', 'active', now(), now())"
        )
        assert_denied("UPDATE tenancy_restaurant SET status = 'closed' WHERE id = %s", [a])
        assert_denied("DELETE FROM tenancy_restaurant WHERE id = %s", [a])
    assert Restaurant.objects.using("migrator").get(pk=a).status == RestaurantStatus.ACTIVE


def test_registry_constraints(two_tenants: TwoTenants) -> None:
    for values in ({"name": "   "}, {"status": "deleted"}):
        with pytest.raises(IntegrityError), transaction.atomic(using="migrator"):
            make_restaurant(**values)
    with pytest.raises(DatabaseError), transaction.atomic(using="migrator"):
        make_restaurant(name="x" * 201)
    assert registry_count() == 2


# --- gate 8 additions (QA) ---------------------------------------------------------


@pytest.mark.parametrize("assignment", ["tenant_id = tenant_id", "tenant_id = %s", "id = id"])
def test_key_column_grant_denies_even_a_same_value_rewrite(
    parents: dict[str, ProbeParent], two_tenants: TwoTenants, assignment: str
) -> None:
    """C3-9 grant on its own. Rewriting tenant_id to B is also stopped by the
    policy's WITH CHECK (same SQLSTATE), so that case cannot show the column
    grant. A same-value rewrite passes WITH CHECK; only the missing column
    privilege can deny it, and the message says so."""
    a = two_tenants.a.id
    params: list[Any] = [a] if "%s" in assignment else []
    with tenant_transaction(a):
        with pytest.raises(ProgrammingError) as exc:
            execute(
                f"UPDATE {PARENT} SET {assignment} WHERE id = %s",  # noqa: S608 - constant
                [*params, parents["a"].id],
            )
        assert isinstance(exc.value.__cause__, pg_errors.InsufficientPrivilege)
        assert "permission denied for table" in str(exc.value)
        # Control: an updatable column on the same row works.
        assert execute(f"UPDATE {PARENT} SET code = code WHERE id = %s", [parents["a"].id]) == 1  # noqa: S608
