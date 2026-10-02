"""Migration operations for tenant-owned tables and the tenant registry
(change 0004, 6.5, 6.7, C-11, C-15).

Every tenant-owned table's ``CreateModel`` migration also contains, in this order:

    enable_tenant_rls("<db_table>"),
    restrict_tenant_key_update("<ModelName>", ["<updatable field>", ...]),
    composite_tenant_fk("<db_table>", "<fk column>", "<parent db_table>"),  # per tenant FK

A migration-graph test fails if any of them is missing or in another migration.

Role names are never literals: the app role comes from ``settings.RMS_DB_APP_ROLE``
(``DB_APP_USER``), is checked against the bootstrap name pattern and against
``pg_roles``, and is composed only with ``psycopg.sql.Identifier`` (C-11).
Table and column names come from constants in migration files or from the
historical model's ``_meta``; they are checked against the same pattern.

This module and ``context.py`` are the only files allowed to write ``app.*``
settings (C-3): ``for_each_tenant`` and ``migration_tenant_context`` set the
tenant context on a *migration* connection, never on ``default``.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager, suppress
from typing import Any

from django.apps.registry import Apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.operations.base import Operation
from django.db.migrations.operations.special import RunSQL
from django.db.migrations.recorder import MigrationRecorder
from django.db.migrations.state import ProjectState
from django.db.models import Model
from django.db.transaction import TransactionManagementError
from psycopg import sql

from rms.tenancy.data.context import DEFAULT_ALIAS

# Same rule as scripts/db/bootstrap.sh.
NAME_PATTERN = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")

# The single policy expression of every tenant table (C3-3). Changing it is APPROVAL.
TENANT_POLICY_NAME = "tenant_isolation"
TENANT_POLICY_EXPRESSION = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"
# As PostgreSQL 16 stores it (pg_get_expr); the catalog check pins this literal.
TENANT_POLICY_DEPARSED = (
    "(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)"
)

REGISTRY_TABLE = "tenancy_restaurant"
REGISTRY_POLICY_NAME = "restaurant_tenant_read"
REGISTRY_POLICY_EXPRESSION = "id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"
REGISTRY_POLICY_DEPARSED = (
    "(id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)"
)

_KEY_COLUMNS = frozenset({"id", "tenant_id"})
_KEY_FIELDS = frozenset({"id", "pk", "tenant", "tenant_id"})


def checked_name(name: str) -> str:
    """A table, column or role name that matches ``NAME_PATTERN``; raises otherwise."""
    if not isinstance(name, str) or not NAME_PATTERN.match(name):
        raise ImproperlyConfigured(f"a database name does not match {NAME_PATTERN.pattern}")
    return name


def _ident(name: str) -> str:
    return sql.Identifier(checked_name(name)).as_string(None)


# --- the app role (C-11) ---------------------------------------------------------


def configured_app_role() -> str:
    """``settings.RMS_DB_APP_ROLE``, checked against the name pattern (C-11(a))."""
    role = getattr(settings, "RMS_DB_APP_ROLE", None)
    if not isinstance(role, str) or not NAME_PATTERN.match(role):
        raise ImproperlyConfigured(
            f"RMS_DB_APP_ROLE (DB_APP_USER) must be set and match {NAME_PATTERN.pattern}"
        )
    return role


def checked_app_role(connection: BaseDatabaseWrapper) -> str:
    """The app role, after checking it in ``pg_roles`` (C-11(b)).

    It must exist, must not be the connected (migrating) role, and must have
    neither SUPERUSER nor BYPASSRLS. Messages never contain the name.
    """
    role = configured_app_role()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolname = current_user, rolsuper, rolbypassrls FROM pg_roles"
            " WHERE rolname = %s",
            [role],
        )
        row = cursor.fetchone()
    if row is None:
        raise ImproperlyConfigured("RMS_DB_APP_ROLE names a role that does not exist")
    is_current, is_super, bypasses_rls = row
    if is_current:
        raise ImproperlyConfigured("RMS_DB_APP_ROLE must not be the role running the migration")
    if is_super or bypasses_rls:
        raise ImproperlyConfigured("RMS_DB_APP_ROLE must have neither SUPERUSER nor BYPASSRLS")
    return role


def _execute(schema_editor: BaseDatabaseSchemaEditor, statement: sql.Composable) -> None:
    schema_editor.execute(statement.as_string(None))


def _privileges(
    connection: BaseDatabaseWrapper, role: str, table: str, checks: Sequence[tuple[str, str]]
) -> list[bool]:
    """``has_table_privilege``/``has_column_privilege`` results, in order.

    Each check is ``("", privilege)`` for the table or ``(column, privilege)``.
    """
    results: list[bool] = []
    with connection.cursor() as cursor:
        for column, privilege in checks:
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
            results.append(bool(row and row[0]))
    return results


class _RoleOperation(Operation):
    """Base for operations that grant or revoke on the app role."""

    reversible = True
    reduces_to_sql = False

    def state_forwards(self, app_label: str, state: ProjectState) -> None:
        """Privileges are not part of the model state."""

    @staticmethod
    def _role(schema_editor: BaseDatabaseSchemaEditor) -> str:
        return checked_app_role(schema_editor.connection)


def _historical_columns(
    state: ProjectState, app_label: str, model_name: str, fields: Sequence[str]
) -> tuple[str, list[str]]:
    model: type[Model] = state.apps.get_model(app_label, model_name)
    table = checked_name(model._meta.db_table)
    columns: list[str] = []
    for name in fields:
        if name in _KEY_FIELDS:
            raise ImproperlyConfigured("id and tenant can never be updatable (C3-9)")
        field = model._meta.get_field(name)
        column = getattr(field, "column", None)
        if not getattr(field, "concrete", False) or not column or column in _KEY_COLUMNS:
            raise ImproperlyConfigured("updatable columns must be concrete non-key columns")
        columns.append(checked_name(column))
    return table, columns


class RestrictTenantKeyUpdate(_RoleOperation):
    """Replace the app role's table-level UPDATE with UPDATE on the given columns.

    Forward: ``REVOKE UPDATE ON t``; ``GRANT UPDATE (cols) ON t``; then assert
    that the role has no table-level UPDATE and no UPDATE on ``tenant_id`` or
    ``id`` (C-11(c)). Reverse: back to table-level UPDATE (the default privilege).
    A column added later stays non-updatable until ``grant_update_columns``.
    """

    def __init__(self, model_name: str, updatable_fields: Sequence[str]) -> None:
        self.model_name = model_name
        self.updatable_fields = list(updatable_fields)
        if _KEY_FIELDS.intersection(self.updatable_fields):
            raise ImproperlyConfigured("id and tenant can never be updatable (C3-9)")

    def deconstruct(self) -> tuple[str, list[Any], dict[str, Any]]:
        return (self.__class__.__name__, [self.model_name, self.updatable_fields], {})

    def describe(self) -> str:
        return f"Restrict app-role UPDATE on {self.model_name} to its updatable columns"

    def database_forwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ) -> None:
        table, columns = _historical_columns(
            to_state, app_label, self.model_name, self.updatable_fields
        )
        role = self._role(schema_editor)
        _execute(
            schema_editor,
            sql.SQL("REVOKE UPDATE ON {} FROM {}").format(
                sql.Identifier(table), sql.Identifier(role)
            ),
        )
        if columns:
            _execute(
                schema_editor,
                sql.SQL("GRANT UPDATE ({}) ON {} TO {}").format(
                    sql.SQL(", ").join(sql.Identifier(c) for c in columns),
                    sql.Identifier(table),
                    sql.Identifier(role),
                ),
            )
        if schema_editor.collect_sql:
            return
        if any(
            _privileges(
                schema_editor.connection,
                role,
                table,
                [("", "UPDATE"), ("tenant_id", "UPDATE"), ("id", "UPDATE")],
            )
        ):
            raise ImproperlyConfigured("the app role can still UPDATE the tenant key (C-11(c))")

    def database_backwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ) -> None:
        table, _ = _historical_columns(from_state, app_label, self.model_name, [])
        role = self._role(schema_editor)
        # A table-level REVOKE also removes the column-level grants.
        _execute(
            schema_editor,
            sql.SQL("REVOKE UPDATE ON {} FROM {}").format(
                sql.Identifier(table), sql.Identifier(role)
            ),
        )
        _execute(
            schema_editor,
            sql.SQL("GRANT UPDATE ON {} TO {}").format(sql.Identifier(table), sql.Identifier(role)),
        )


class GrantUpdateColumns(_RoleOperation):
    """Add UPDATE on new columns of a table restricted by ``RestrictTenantKeyUpdate``."""

    def __init__(self, model_name: str, fields: Sequence[str]) -> None:
        self.model_name = model_name
        self.fields = list(fields)
        if not self.fields or _KEY_FIELDS.intersection(self.fields):
            raise ImproperlyConfigured("grant_update_columns needs non-key fields")

    def deconstruct(self) -> tuple[str, list[Any], dict[str, Any]]:
        return (self.__class__.__name__, [self.model_name, self.fields], {})

    def describe(self) -> str:
        return f"Grant app-role UPDATE on new columns of {self.model_name}"

    def _statement(
        self,
        verb: str,
        state: ProjectState,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
    ) -> None:
        table, columns = _historical_columns(state, app_label, self.model_name, self.fields)
        role = self._role(schema_editor)
        template = (
            "GRANT UPDATE ({}) ON {} TO {}"
            if verb == "grant"
            else ("REVOKE UPDATE ({}) ON {} FROM {}")
        )
        _execute(
            schema_editor,
            sql.SQL(template).format(
                sql.SQL(", ").join(sql.Identifier(c) for c in columns),
                sql.Identifier(table),
                sql.Identifier(role),
            ),
        )

    def database_forwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ) -> None:
        self._statement("grant", to_state, app_label, schema_editor)

    def database_backwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ) -> None:
        self._statement("revoke", from_state, app_label, schema_editor)


class RestrictToColumnRead(_RoleOperation):
    """Platform tables the app may only read in part (the registry, C3-1a).

    Forward: ``REVOKE ALL`` (it undoes the default privileges), then
    ``GRANT SELECT (cols)``; asserts that no table-level privilege remains.
    Reverse: back to the default DML privileges.
    """

    def __init__(self, model_name: str, readable_fields: Sequence[str]) -> None:
        self.model_name = model_name
        self.readable_fields = list(readable_fields)

    def deconstruct(self) -> tuple[str, list[Any], dict[str, Any]]:
        return (self.__class__.__name__, [self.model_name, self.readable_fields], {})

    def describe(self) -> str:
        return f"Restrict the app role to reading some columns of {self.model_name}"

    def _table_and_columns(self, state: ProjectState, app_label: str) -> tuple[str, list[str]]:
        model: type[Model] = state.apps.get_model(app_label, self.model_name)
        table = checked_name(model._meta.db_table)
        columns = [
            checked_name(str(getattr(model._meta.get_field(f), "column", "")))
            for f in self.readable_fields
        ]
        return table, columns

    def database_forwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ) -> None:
        table, columns = self._table_and_columns(to_state, app_label)
        role = self._role(schema_editor)
        _execute(
            schema_editor,
            sql.SQL("REVOKE ALL ON {} FROM {}").format(sql.Identifier(table), sql.Identifier(role)),
        )
        _execute(
            schema_editor,
            sql.SQL("GRANT SELECT ({}) ON {} TO {}").format(
                sql.SQL(", ").join(sql.Identifier(c) for c in columns),
                sql.Identifier(table),
                sql.Identifier(role),
            ),
        )
        if schema_editor.collect_sql:
            return
        table_level = [("", p) for p in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE")]
        if any(_privileges(schema_editor.connection, role, table, table_level)):
            raise ImproperlyConfigured("the app role still holds a table-level privilege")

    def database_backwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ) -> None:
        table, _ = self._table_and_columns(from_state, app_label)
        role = self._role(schema_editor)
        _execute(
            schema_editor,
            sql.SQL("REVOKE ALL ON {} FROM {}").format(sql.Identifier(table), sql.Identifier(role)),
        )
        _execute(
            schema_editor,
            sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON {} TO {}").format(
                sql.Identifier(table), sql.Identifier(role)
            ),
        )


class LockDownMigrationTable(_RoleOperation):
    """``django_migrations`` is read-only for the app role (0003 follow-up 1, 6.7).

    The app role keeps SELECT (``runserver``'s pending-migration check) and loses
    INSERT, UPDATE, DELETE, TRUNCATE, and every privilege on the ID sequence.
    Lives here, not in ``rms.core``, because it needs the checked role name.
    """

    def deconstruct(self) -> tuple[str, list[Any], dict[str, Any]]:
        return (self.__class__.__name__, [], {})

    def describe(self) -> str:
        return "Make the migration history read-only for the app role"

    @staticmethod
    def _names(connection: BaseDatabaseWrapper) -> tuple[str, str | None]:
        table = checked_name(MigrationRecorder.Migration._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT s.relname FROM pg_class s"
                " WHERE s.oid = pg_get_serial_sequence(%s, 'id')::regclass",
                [table],
            )
            row = cursor.fetchone()
        return table, checked_name(row[0]) if row else None

    def database_forwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ) -> None:
        role = self._role(schema_editor)
        table, sequence = self._names(schema_editor.connection)
        _execute(
            schema_editor,
            sql.SQL("REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON {} FROM {}").format(
                sql.Identifier(table), sql.Identifier(role)
            ),
        )
        if sequence:
            _execute(
                schema_editor,
                sql.SQL("REVOKE ALL ON SEQUENCE {} FROM {}").format(
                    sql.Identifier(sequence), sql.Identifier(role)
                ),
            )
        if schema_editor.collect_sql:
            return
        writes = [("", p) for p in ("INSERT", "UPDATE", "DELETE", "TRUNCATE")]
        if any(_privileges(schema_editor.connection, role, table, writes)):
            raise ImproperlyConfigured("the app role can still write the migration history")

    def database_backwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ) -> None:
        role = self._role(schema_editor)
        table, sequence = self._names(schema_editor.connection)
        _execute(
            schema_editor,
            sql.SQL("GRANT INSERT, UPDATE, DELETE ON {} TO {}").format(
                sql.Identifier(table), sql.Identifier(role)
            ),
        )
        if sequence:
            _execute(
                schema_editor,
                sql.SQL("GRANT USAGE, SELECT ON SEQUENCE {} TO {}").format(
                    sql.Identifier(sequence), sql.Identifier(role)
                ),
            )


# --- RLS and composite FKs (RunSQL, reversible) ------------------------------------


class EnableTenantRLS(RunSQL):
    """``ENABLE`` + ``FORCE ROW LEVEL SECURITY`` and the one ``tenant_isolation``
    policy (no ``TO``: it binds every role, the migrator included)."""

    def __init__(self, table: str) -> None:
        self.table = checked_name(table)
        t = _ident(table)
        policy = _ident(TENANT_POLICY_NAME)
        expr = TENANT_POLICY_EXPRESSION
        super().__init__(
            sql=[
                f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY",
                f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY",
                f"CREATE POLICY {policy} ON {t} USING ({expr}) WITH CHECK ({expr})",
            ],
            reverse_sql=[
                f"DROP POLICY {policy} ON {t}",
                f"ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY",
                f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY",
            ],
        )

    def deconstruct(self) -> tuple[str, list[Any], dict[str, Any]]:
        return (self.__class__.__name__, [self.table], {})

    def describe(self) -> str:
        return f"Enable and force tenant RLS on {self.table}"


class EnableRegistryRLS(RunSQL):
    """Registry RLS: ``ENABLE`` without ``FORCE`` (D4) and a SELECT-only policy
    for the current tenant's row. The owner (migrator) sees every row."""

    def __init__(self) -> None:
        t = _ident(REGISTRY_TABLE)
        policy = _ident(REGISTRY_POLICY_NAME)
        super().__init__(
            sql=[
                f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY",
                f"CREATE POLICY {policy} ON {t} FOR SELECT USING ({REGISTRY_POLICY_EXPRESSION})",
            ],
            reverse_sql=[
                f"DROP POLICY {policy} ON {t}",
                f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY",
            ],
        )

    def deconstruct(self) -> tuple[str, list[Any], dict[str, Any]]:
        return (self.__class__.__name__, [], {})

    def describe(self) -> str:
        return "Enable registry RLS (current tenant only, not forced)"


class CompositeTenantFK(RunSQL):
    """``(tenant_id, column) -> parent (tenant_id, id) ON DELETE RESTRICT``.

    The ORM ``ForeignKey`` keeps ``db_constraint=False``; this is the only DB
    constraint, and it rejects cross-tenant references (RI checks ignore RLS,
    so a single-column FK would accept them, change 0004 F3).
    """

    def __init__(self, table: str, column: str, parent_table: str) -> None:
        self.table = checked_name(table)
        self.column = checked_name(column)
        self.parent_table = checked_name(parent_table)
        self.constraint = checked_name(f"{table}_{column}_tenant_fk")
        t, c, p, k = (_ident(n) for n in (table, column, parent_table, self.constraint))
        super().__init__(
            sql=[
                f"ALTER TABLE {t} ADD CONSTRAINT {k} FOREIGN KEY (tenant_id, {c})"
                f" REFERENCES {p} (tenant_id, id) ON DELETE RESTRICT"
            ],
            reverse_sql=[f"ALTER TABLE {t} DROP CONSTRAINT {k}"],
        )

    def deconstruct(self) -> tuple[str, list[Any], dict[str, Any]]:
        return (self.__class__.__name__, [self.table, self.column, self.parent_table], {})

    def describe(self) -> str:
        return f"Add composite tenant FK {self.table}.{self.column} -> {self.parent_table}"


def enable_tenant_rls(table: str) -> EnableTenantRLS:
    return EnableTenantRLS(table)


def composite_tenant_fk(table: str, column: str, parent_table: str) -> CompositeTenantFK:
    return CompositeTenantFK(table, column, parent_table)


def restrict_tenant_key_update(
    model_name: str, updatable_fields: Sequence[str]
) -> RestrictTenantKeyUpdate:
    return RestrictTenantKeyUpdate(model_name, updatable_fields)


def grant_update_columns(model_name: str, fields: Sequence[str]) -> GrantUpdateColumns:
    return GrantUpdateColumns(model_name, fields)


# --- tenant context on migration connections (C3-6, C-15) ---------------------------

_SET_TENANT_SQL = "SELECT set_config('app.tenant_id', %s, true)"
_CLEAR_TENANT_SQL = "SELECT set_config('app.tenant_id', '', true)"


@contextmanager
def migration_tenant_context(
    connection: BaseDatabaseWrapper, tenant_id: uuid.UUID
) -> Iterator[None]:
    """Set ``app.tenant_id`` on a migration connection for the block.

    Never on ``default``: runtime code uses ``tenant_transaction``. Needs an
    open transaction (transaction-local setting); the setting is cleared in
    ``finally``. After an error the enclosing transaction is rolled back,
    which restores it in any case.
    """
    if type(tenant_id) is not uuid.UUID:
        raise TypeError("migration_tenant_context needs a uuid.UUID instance")
    if connection.alias == DEFAULT_ALIAS:
        raise ImproperlyConfigured("use tenant_transaction on the default connection")
    if not connection.in_atomic_block:
        raise TransactionManagementError("migration_tenant_context needs an atomic block")
    with connection.cursor() as cursor:
        cursor.execute(_SET_TENANT_SQL, [str(tenant_id)])
    failed = True
    try:
        yield
        failed = False
    finally:
        if failed:
            # The transaction may already be aborted; its rollback clears the setting.
            with suppress(DatabaseError), connection.cursor() as cursor:
                cursor.execute(_CLEAR_TENANT_SQL)
        else:
            with connection.cursor() as cursor:
                cursor.execute(_CLEAR_TENANT_SQL)


def for_each_tenant(
    apps: Apps, schema_editor: BaseDatabaseSchemaEditor, fn: Callable[[uuid.UUID], None]
) -> None:
    """Data migrations over tenant tables (C3-6): call ``fn(tenant_id)`` once per
    registry row, with that tenant's context set on the migration connection.

    ``fn`` uses historical models (``apps.get_model``) and must still filter
    by ``tenant_id`` explicitly; FORCE RLS applies to the migrator too. The
    migration must be atomic (the default), so a failure leaves nothing behind.
    The registry is read on the migration connection, as its owner (D4: not
    forced, so every row is visible).
    """
    connection = schema_editor.connection
    if not connection.in_atomic_block:
        raise TransactionManagementError("for_each_tenant needs an atomic migration")
    registry = checked_name(apps.get_model("tenancy", "Restaurant")._meta.db_table)
    with connection.cursor() as cursor:
        cursor.execute(
            sql.SQL("SELECT id FROM {} ORDER BY id")
            .format(sql.Identifier(registry))
            .as_string(None)
        )
        tenant_ids = [row[0] for row in cursor.fetchall()]
    for tenant_id in tenant_ids:
        with migration_tenant_context(connection, tenant_id):
            fn(tenant_id)
