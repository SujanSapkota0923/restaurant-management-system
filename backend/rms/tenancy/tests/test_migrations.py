"""Migration operations and patterns (6.5, C-11, C-15, C-17; N-10, N-11)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import pytest
from django.apps import apps as global_apps
from django.core.exceptions import ImproperlyConfigured
from django.db import connections, migrations, models, transaction
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.state import ProjectState
from django.db.models.functions import Upper
from django.db.transaction import TransactionManagementError
from django.test import override_settings
from psycopg import sql

from rms.tenancy.data.context import tenant_transaction
from rms.tenancy.data.rls import (
    CompositeTenantFK,
    EnableTenantRLS,
    RestrictTenantKeyUpdate,
    checked_app_role,
    for_each_tenant,
    grant_update_columns,
    migration_tenant_context,
    restrict_tenant_key_update,
)
from rms.tenancy.tests.factories import make_parent
from rms.tenancy.tests.harness import ISOLATION_DB, TwoTenants, current_setting
from rms.tenancy.tests.probe.models import ProbeParent

PARENT = "tenancy_probe_probeparent"
REGISTRY_MODEL = "tenancy.restaurant"


def loader() -> MigrationLoader:
    # From the migration files only; no database access.
    return MigrationLoader(None, ignore_no_migrations=True)


def project_state() -> ProjectState:
    return loader().project_state()


def has_privilege(table: str, privilege: str, column: str | None = None) -> bool:
    role = str(connections["default"].settings_dict["USER"])
    with connections["migrator"].cursor() as cursor:
        if column:
            cursor.execute(
                "SELECT has_column_privilege(%s, %s::regclass, %s, %s)",
                [role, table, column, privilege],
            )
        else:
            cursor.execute(
                "SELECT has_table_privilege(%s, %s::regclass, %s)", [role, table, privilege]
            )
        row = cursor.fetchone()
    return bool(row and row[0])


@contextmanager
def rolled_back_migrator() -> Iterator[Any]:
    with transaction.atomic(using="migrator"), connections["migrator"].cursor() as cursor:
        yield cursor
        transaction.set_rollback(True, using="migrator")


# --- N-11: for_each_tenant ------------------------------------------------------------


@ISOLATION_DB
def test_for_each_tenant_refuses_a_non_atomic_migration() -> None:
    editor = SimpleNamespace(connection=connections["migrator"])
    assert not connections["migrator"].in_atomic_block
    with pytest.raises(TransactionManagementError):
        for_each_tenant(project_state().apps, editor, lambda tenant_id: None)  # type: ignore[arg-type]


@ISOLATION_DB
def test_for_each_tenant_scopes_each_call(two_tenants: TwoTenants) -> None:
    a, b = two_tenants.a.id, two_tenants.b.id
    with tenant_transaction(a):
        make_parent(code="a1")
        make_parent(code="a2")
    with tenant_transaction(b):
        make_parent(code="b1")
    historical = project_state().apps
    parent = historical.get_model("tenancy_probe", "ProbeParent")
    seen: dict[uuid.UUID, dict[str, Any]] = {}

    def fn(tenant_id: uuid.UUID) -> None:
        manager = parent.objects.using("migrator")
        with connections["migrator"].cursor() as cursor:
            cursor.execute(f"SELECT count(*) FROM {PARENT}")  # noqa: S608 - constant
            unfiltered = cursor.fetchone()[0]
        seen[tenant_id] = {
            "setting": current_setting("app.tenant_id", alias="migrator"),
            "unfiltered": unfiltered,
            "filtered": manager.filter(tenant_id=tenant_id).count(),
            # Another tenant's rows cannot be touched even when named explicitly.
            "other_updated": manager.exclude(tenant_id=tenant_id).update(code="hijacked"),
        }
        manager.filter(tenant_id=tenant_id).update(code=Upper("code"))

    editor = SimpleNamespace(connection=connections["migrator"])
    with transaction.atomic(using="migrator"):
        for_each_tenant(historical, editor, fn)  # type: ignore[arg-type]
        after = current_setting("app.tenant_id", alias="migrator")
    assert seen == {
        a: {"setting": str(a), "unfiltered": 2, "filtered": 2, "other_updated": 0},
        b: {"setting": str(b), "unfiltered": 1, "filtered": 1, "other_updated": 0},
    }
    assert after == ""
    # Each tenant's own rows were updated, and only those.
    with tenant_transaction(a):
        assert sorted(ProbeParent.objects.values_list("code", flat=True)) == ["A1", "A2"]
    with tenant_transaction(b):
        assert list(ProbeParent.objects.values_list("code", flat=True)) == ["B1"]


@ISOLATION_DB
def test_migration_tenant_context_guards() -> None:
    migrator, default = connections["migrator"], connections["default"]
    not_a_uuid: Any = str(uuid.uuid4())
    with (
        pytest.raises(TypeError),
        transaction.atomic(using="migrator"),
        migration_tenant_context(migrator, not_a_uuid),
    ):
        pass  # pragma: no cover
    with (
        pytest.raises(TransactionManagementError),
        migration_tenant_context(migrator, uuid.uuid4()),
    ):
        pass  # pragma: no cover
    with (
        pytest.raises(ImproperlyConfigured),
        transaction.atomic(using="default"),
        migration_tenant_context(default, uuid.uuid4()),
    ):
        pass  # pragma: no cover


@ISOLATION_DB
def test_migration_tenant_context_clears_after_an_error() -> None:
    with transaction.atomic(using="migrator"):
        with (
            pytest.raises(RuntimeError),
            migration_tenant_context(connections["migrator"], uuid.uuid4()),
        ):
            raise RuntimeError("fn failed")
        assert current_setting("app.tenant_id", alias="migrator") == ""


# --- C-11 / N-10: the role name ------------------------------------------------------------


@pytest.mark.django_db(databases=["default", "migrator"])
@pytest.mark.parametrize(
    ("role", "message"),
    [
        (None, "must be set"),
        ("", "must be set"),
        ("Rms_App", "must be set and match"),
        ('rms_app"; DROP TABLE x; --', "must be set and match"),
        ("rms_no_such_role", "does not exist"),
        ("postgres", "neither SUPERUSER nor BYPASSRLS"),
        ("__migrator__", "must not be the role running the migration"),
    ],
    ids=["unset", "blank", "upper-case", "injection", "unknown", "superuser", "migrator"],
)
def test_checked_app_role_refuses(role: str | None, message: str) -> None:
    connection = connections["migrator"]
    if role == "__migrator__":
        role = str(connection.settings_dict["USER"])
    with override_settings(RMS_DB_APP_ROLE=role), pytest.raises(ImproperlyConfigured) as exc:
        checked_app_role(connection)
    assert message in str(exc.value)


@pytest.mark.django_db(databases=["default", "migrator"])
def test_checked_app_role_accepts_the_app_role() -> None:
    expected = str(connections["default"].settings_dict["USER"])
    assert checked_app_role(connections["migrator"]) == expected


@pytest.mark.parametrize("field", ["id", "pk", "tenant", "tenant_id"])
def test_key_fields_can_never_be_made_updatable(field: str) -> None:
    with pytest.raises(ImproperlyConfigured):
        restrict_tenant_key_update("ProbeParent", ["code", field])
    with pytest.raises(ImproperlyConfigured):
        grant_update_columns("ProbeParent", [field])


@pytest.mark.django_db(databases=["default", "migrator"])
def test_restrict_tenant_key_update_round_trip_and_post_check() -> None:
    state = project_state()
    op = RestrictTenantKeyUpdate("ProbeParent", ["code"])
    assert not has_privilege(PARENT, "UPDATE")  # as migrated
    assert has_privilege(PARENT, "UPDATE", "code")
    with rolled_back_migrator() as cursor:
        with connections["migrator"].schema_editor(atomic=False) as editor:
            op.database_backwards("tenancy_probe", editor, state, state)
        assert has_privilege(PARENT, "UPDATE")  # reverse restored table-level UPDATE
        with connections["migrator"].schema_editor(atomic=False) as editor:
            op.database_forwards("tenancy_probe", editor, state, state)
        assert not has_privilege(PARENT, "UPDATE")
        assert not has_privilege(PARENT, "UPDATE", "tenant_id")
        # C-11(c): a grant that survives the revoke (here via PUBLIC) fails the migration.
        cursor.execute(
            sql.SQL("GRANT UPDATE ON {} TO PUBLIC").format(sql.Identifier(PARENT)).as_string(None)
        )
        with (
            pytest.raises(ImproperlyConfigured, match="can still UPDATE"),
            connections["migrator"].schema_editor(atomic=False) as editor,
        ):
            op.database_forwards("tenancy_probe", editor, state, state)
    assert not has_privilege(PARENT, "UPDATE")


@pytest.mark.django_db(databases=["default", "migrator"])
def test_enable_tenant_rls_and_composite_fk_are_reversible() -> None:
    state = project_state()
    rls = EnableTenantRLS(PARENT)
    fk = CompositeTenantFK("tenancy_probe_probechild", "parent_id", PARENT)
    with rolled_back_migrator() as cursor:
        with connections["migrator"].schema_editor(atomic=False) as editor:
            fk.database_backwards("tenancy_probe", editor, state, state)
            rls.database_backwards("tenancy_probe", editor, state, state)
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity,"
            " (SELECT count(*) FROM pg_policy WHERE polrelid = c.oid),"
            " (SELECT count(*) FROM pg_constraint WHERE conname = %s)"
            " FROM pg_class c WHERE relname = %s",
            [fk.constraint, PARENT],
        )
        assert cursor.fetchone() == (False, False, 0, 0)
        with connections["migrator"].schema_editor(atomic=False) as editor:
            rls.database_forwards("tenancy_probe", editor, state, state)
            fk.database_forwards("tenancy_probe", editor, state, state)
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity,"
            " (SELECT count(*) FROM pg_policy WHERE polrelid = c.oid),"
            " (SELECT count(*) FROM pg_constraint WHERE conname = %s)"
            " FROM pg_class c WHERE relname = %s",
            [fk.constraint, PARENT],
        )
        assert cursor.fetchone() == (True, True, 1, 1)


@pytest.mark.parametrize("name", ["Upper", "a-b", "x" * 64, "1abc", 'a"b'])
def test_operations_refuse_bad_names(name: str) -> None:
    with pytest.raises(ImproperlyConfigured):
        EnableTenantRLS(name)
    with pytest.raises(ImproperlyConfigured):
        CompositeTenantFK(PARENT, name, PARENT)


# --- C-17: tenant CreateModel and its RLS ops live in one migration ---------------------


def _rms_migrations() -> list[migrations.Migration]:
    rms_labels = {c.label for c in global_apps.get_app_configs() if c.name.startswith("rms.")}
    return [
        migration
        for (label, _), migration in sorted(loader().disk_migrations.items())
        if label in rms_labels
    ]


def _tenant_models() -> set[str]:
    found: set[str] = set()
    for migration in _rms_migrations():
        for op in migration.operations:
            if isinstance(op, migrations.CreateModel):
                fields = dict(op.fields)
                tenant = fields.get("tenant")
                if (
                    isinstance(tenant, models.ForeignKey)
                    and str(tenant.remote_field.model).lower() == REGISTRY_MODEL
                ):
                    found.add(f"{migration.app_label}.{op.name_lower}")
    return found


def test_migration_graph_keeps_tenant_tables_with_their_rls() -> None:
    tenant_models = _tenant_models()
    assert tenant_models == {"tenancy_probe.probeparent", "tenancy_probe.probechild"}
    problems: list[str] = []
    for migration in _rms_migrations():
        rls_tables = {op.table for op in migration.operations if isinstance(op, EnableTenantRLS)}
        restricted = {
            op.model_name.lower()
            for op in migration.operations
            if isinstance(op, RestrictTenantKeyUpdate)
        }
        fks = {
            (op.table, op.column)
            for op in migration.operations
            if isinstance(op, CompositeTenantFK)
        }
        created: set[str] = set()
        for op in migration.operations:
            if isinstance(op, migrations.AddField) and op.name == "tenant":
                problems.append(f"{migration.app_label}.{migration.name}: tenant added later")
            if not isinstance(op, migrations.CreateModel):
                continue
            label = f"{migration.app_label}.{op.name_lower}"
            if label not in tenant_models:
                continue
            table = op.options.get("db_table") or f"{migration.app_label}_{op.name_lower}"
            created.add(table)
            if table not in rls_tables:
                problems.append(f"{label}: enable_tenant_rls missing from {migration.name}")
            if op.name_lower not in restricted:
                problems.append(
                    f"{label}: restrict_tenant_key_update missing from {migration.name}"
                )
            for name, field in op.fields:
                if not isinstance(field, models.ForeignKey) or name == "tenant":
                    continue
                if str(field.remote_field.model).lower() not in tenant_models:
                    continue
                if getattr(field, "db_constraint", True):
                    problems.append(f"{label}.{name}: tenant FK must use db_constraint=False")
                if (table, field.db_column or f"{name}_id") not in fks:
                    problems.append(f"{label}.{name}: composite_tenant_fk missing")
        problems.extend(
            f"{migration.name}: enable_tenant_rls on {t} without its CreateModel"
            for t in sorted(rls_tables - created)
        )
    assert problems == []
