"""Two-tenant isolation harness (change 0004, 6.8, C-2, C-14, C-20; SC-29).

Use it for every test that touches tenant data::

    from rms.tenancy.tests.harness import ISOLATION_DB, TwoTenants, rows_visible_to

    @ISOLATION_DB
    def test_something(two_tenants: TwoTenants) -> None: ...

Why transactional tests with the ``migrator`` alias (verified in change 0004):

- ``default`` (app role) mirrors ``migrator``. Django never flushes a mirror,
  so a transactional test that declares only ``default`` leaves its committed
  rows behind (SC-29). With ``migrator`` declared, the flush runs on it, as the
  table owner (TRUNCATE is not subject to RLS).
- A non-transactional test wraps both aliases in uncommitted transactions on
  separate connections, so registry rows created by the migrator are invisible
  to ``default``; and the durable ``tenant_transaction`` is then only a
  savepoint (F1). Context-sensitive tests are therefore transactional (C-2).

Why an empty registry proves that no tenant row was left behind (C-20(b)). It
holds only because of all three of:

1. D4: the registry has RLS enabled but not forced, so the migrator (owner)
   sees every registry row;
2. C-12(5): every tenant table has an FK ``(tenant_id) -> tenancy_restaurant(id)``,
   so no tenant row can exist without its registry row;
3. C-12(10): the app role cannot INSERT into the registry, so only the migrator
   creates registry rows.

A change to any of the three must change ``two_tenants`` too. Under FORCE
without a migrator policy, both this check and ``for_each_tenant`` would
silently see nothing.

Assertions about "no row" are never made through the migrator without context:
the tenant policy binds the migrator too, so such a read is always 0 (F4). Use
``rows_visible_to`` and pair it with a positive control in the same test (C-14).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from django.db import connections, models, transaction
from django.test import TestCase, TransactionTestCase
from psycopg import sql

from rms.tenancy.data.context import tenant_transaction
from rms.tenancy.data.models import Restaurant
from rms.tenancy.data.rls import migration_tenant_context
from rms.tenancy.tests.factories import make_restaurant

APP_ALIAS = "default"
MIGRATOR_ALIAS = "migrator"

ISOLATION_DB = pytest.mark.django_db(transaction=True, databases=[APP_ALIAS, MIGRATOR_ALIAS])

# Fixtures that make a test transactional (C-20(a)).
TRANSACTIONAL_FIXTURES = frozenset(
    {"transactional_db", "live_server", "django_db_serialized_rollback"}
)


@dataclass(frozen=True)
class TwoTenants:
    a: Restaurant
    b: Restaurant


def _declared_databases(item: pytest.Item) -> set[str] | str:
    marker = item.get_closest_marker("django_db")
    if marker is None:
        return {APP_ALIAS}
    databases = marker.kwargs.get("databases")
    if databases == "__all__":
        return "__all__"
    return set(databases) if databases else {APP_ALIAS}


def _is_transactional(item: pytest.Item) -> bool:
    marker = item.get_closest_marker("django_db")
    if marker is not None:
        transactional = marker.kwargs.get("transaction", marker.args[0] if marker.args else False)
        if transactional:
            return True
    fixturenames = getattr(item, "fixturenames", ())
    if TRANSACTIONAL_FIXTURES.intersection(fixturenames):
        return True
    cls = getattr(item, "cls", None)
    return (
        isinstance(cls, type)
        and issubclass(cls, TransactionTestCase)
        and not issubclass(cls, TestCase)
    )


def transactional_guard_failure(item: pytest.Item) -> str | None:
    """Why ``item`` must not run (SC-29, C-20(a)), or ``None``.

    A transactional test must include the ``migrator`` alias, otherwise its
    committed rows are never flushed.
    """
    if not _is_transactional(item):
        return None
    cls = getattr(item, "cls", None)
    if isinstance(cls, type) and issubclass(cls, TransactionTestCase):
        databases: Any = cls.databases
        declared: set[str] | str = "__all__" if databases == "__all__" else set(databases)
    else:
        declared = _declared_databases(item)
    if declared == "__all__" or MIGRATOR_ALIAS in declared:
        return None
    return (
        f"{item.nodeid}: a transactional test must declare the {MIGRATOR_ALIAS!r} alias "
        "(use rms.tenancy.tests.harness.ISOLATION_DB), or its committed rows are never flushed"
    )


def _require_committing_migrator() -> None:
    if connections[MIGRATOR_ALIAS].in_atomic_block:
        raise AssertionError(
            "two_tenants needs a transactional test (ISOLATION_DB): inside a test "
            "transaction the registry rows are invisible to the app role"
        )


def registry_count() -> int:
    """All registry rows, as the owner (D4: the registry is not forced)."""
    return Restaurant.objects.using(MIGRATOR_ALIAS).count()


@pytest.fixture
def two_tenants() -> TwoTenants:
    """Tenants A and B, committed by the migrator, in an empty registry."""
    _require_committing_migrator()
    leftover = registry_count()
    assert leftover == 0, f"the registry has {leftover} rows left by an earlier test (SC-29)"
    return TwoTenants(a=make_restaurant(name="Tenant A"), b=make_restaurant(name="Tenant B"))


def _count_sql(model: type[models.Model]) -> str:
    return (
        sql.SQL("SELECT count(*) FROM {}")
        .format(sql.Identifier(model._meta.db_table))
        .as_string(None)
    )


def rows_visible_to(tenant_id: uuid.UUID, model: type[models.Model], alias: str = APP_ALIAS) -> int:
    """Rows of ``model`` visible under ``tenant_id``'s context (C-14).

    ``default``: inside a ``tenant_transaction`` (app role, RLS and the scoped
    manager both apply). ``migrator``: the tenant context set on the migrator
    connection inside an atomic block (RLS is forced, so it applies there too).
    """
    if alias == APP_ALIAS:
        with tenant_transaction(tenant_id), connections[APP_ALIAS].cursor() as cursor:
            cursor.execute(_count_sql(model))
            row = cursor.fetchone()
    else:
        connection = connections[alias]
        with (
            transaction.atomic(using=alias),
            migration_tenant_context(connection, tenant_id),
            connection.cursor() as cursor,
        ):
            cursor.execute(_count_sql(model))
            row = cursor.fetchone()
    return int(row[0]) if row else 0


def raw_count(model: type[models.Model], alias: str = APP_ALIAS) -> int:
    """``count(*)`` on the table with whatever context the connection has now."""
    with connections[alias].cursor() as cursor:
        cursor.execute(_count_sql(model))
        row = cursor.fetchone()
    return int(row[0]) if row else 0


def current_setting(name: str, alias: str = APP_ALIAS) -> str | None:
    """``current_setting(name, true)`` on the connection (read only)."""
    with connections[alias].cursor() as cursor:
        cursor.execute("SELECT current_setting(%s, true)", [name])
        row = cursor.fetchone()
    value: str | None = row[0] if row else None
    return value
