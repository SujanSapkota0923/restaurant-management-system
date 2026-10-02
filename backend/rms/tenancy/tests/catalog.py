"""CI catalog check for tenant isolation (ADR-0003 C3-5, TM-28; change 0004 6.9, C-12).

``catalog_failures(alias, app_role=...)`` returns every violated rule as a
message; an empty list means the database passes. It reads only system
catalogs and never changes anything. It is parameterised by the app role name
(not ``current_user``), so the negative tests can run it as the migrator,
inside a transaction that also holds the planted DDL (C-13).

Where it runs (C-12(12)):

- ``make test-backend``: against the migrated test DB (real + probe migrations),
  where at least one tenant table must exist (``test_catalog.py``);
- ``make catalog-check``: against the dev DB after ``make migrate``, read-only,
  as the app role; zero tenant tables is allowed there
  (``python -m rms.tenancy.tests.catalog``);
- ``make migrations-roundtrip``: at the end of the throwaway-DB round trip.

Allow-lists below are reviewed constants. Adding to any of them is a security
review item (``REVIEW``; RLS and roles are ``APPROVAL``).
"""

from __future__ import annotations

import sys
from collections.abc import Iterable, Sequence
from typing import Any

from django.conf import settings
from django.db import connections

from rms.tenancy.data.rls import (
    REGISTRY_POLICY_DEPARSED,
    REGISTRY_POLICY_NAME,
    REGISTRY_TABLE,
    TENANT_POLICY_DEPARSED,
    TENANT_POLICY_NAME,
)

MIGRATIONS_TABLE = "django_migrations"
# Every non-tenant table must be listed here (C-12(1)).
PLATFORM_TABLES = frozenset({MIGRATIONS_TABLE, REGISTRY_TABLE})
REGISTRY_READABLE_COLUMNS = frozenset({"id", "name", "status"})
EXTENSIONS = frozenset({"plpgsql"})

# (table, name, cmd, permissive, roles, qual, with_check); "*" = any tenant table.
ANY_TENANT_TABLE = "*"
TENANT_POLICY = (
    ANY_TENANT_TABLE,
    TENANT_POLICY_NAME,
    "*",
    True,
    "{0}",
    TENANT_POLICY_DEPARSED,
    TENANT_POLICY_DEPARSED,
)
REGISTRY_POLICY = (
    REGISTRY_TABLE,
    REGISTRY_POLICY_NAME,
    "r",
    True,
    "{0}",
    REGISTRY_POLICY_DEPARSED,
    None,
)
POLICY_ALLOW_LIST = frozenset({TENANT_POLICY, REGISTRY_POLICY})

# (oid::regprocedure, owner, md5(prosrc), proconfig, proacl). Empty in 0004;
# 0005 adds the C3-1c invite-lookup function.
DefinerEntry = tuple[str, str, str, str | None, str | None]
DEFINER_ALLOW_LIST: frozenset[DefinerEntry] = frozenset()
# Non-superuser roles allowed to have BYPASSRLS. Empty in 0004.
BYPASSRLS_ALLOW_LIST: frozenset[str] = frozenset()

REQUIRED_ROLE_SETTINGS = ("statement_timeout=", "idle_in_transaction_session_timeout=")
FORBIDDEN_ROLE_SETTINGS = (
    "app.",
    "row_security=",
    "search_path=",
    "role=",
    "session_authorization=",
)

# Every namespace except the system ones (toast and temp included).
_USER_NAMESPACE = (
    "n.nspname NOT IN ('pg_catalog', 'information_schema')"
    " AND n.nspname !~ '^pg_(toast|temp_[0-9]+|toast_temp_[0-9]+)$'"
)
_TRUE_OPTIONS = ("true", "on", "yes", "1")


def _rows(cursor: Any, query: str, params: Sequence[Any] = ()) -> list[tuple[Any, ...]]:
    cursor.execute(query, list(params))
    return list(cursor.fetchall())


def _value(cursor: Any, query: str, params: Sequence[Any] = ()) -> Any:
    rows = _rows(cursor, query, params)
    return rows[0][0] if rows else None


def _default_app_role() -> str:
    return str(settings.DATABASES["default"]["USER"])


def _default_owner_role() -> str:
    return str(settings.DATABASES["migrator"]["USER"])


class _Check:
    def __init__(
        self,
        cursor: Any,
        app_role: str,
        owner_role: str,
        allow_no_tenant_tables: bool,
        definer_allow_list: Iterable[DefinerEntry],
        bypassrls_allow_list: Iterable[str],
    ) -> None:
        self.cursor = cursor
        self.app = app_role
        self.owner = owner_role
        self.allow_no_tenant_tables = allow_no_tenant_tables
        self.definer_allow_list = frozenset(definer_allow_list)
        self.bypassrls_allow_list = frozenset(bypassrls_allow_list)
        self.failures: list[str] = []
        self.app_oid: int | None = None
        # oid -> (name, tenant_id attnum)
        self.tenant_tables: dict[int, tuple[str, int]] = {}
        self.platform_oids: dict[str, int] = {}

    def fail(self, message: str) -> None:
        self.failures.append(message)

    def rows(self, query: str, params: Sequence[Any] = ()) -> list[tuple[Any, ...]]:
        return _rows(self.cursor, query, params)

    def value(self, query: str, params: Sequence[Any] = ()) -> Any:
        return _value(self.cursor, query, params)

    def run(self) -> list[str]:
        self.app_oid = self.value("SELECT oid FROM pg_roles WHERE rolname = %s", [self.app])
        if self.app_oid is None:
            return ["6: the app role does not exist"]
        self.scope()
        self.tenant_rules()
        self.policies()
        self.privileges()
        self.uniqueness()
        self.foreign_keys()
        self.roles()
        self.views()
        self.definers()
        self.bypassrls()
        self.platform_tables()
        self.other_objects()
        return self.failures

    # 1. Scope --------------------------------------------------------------------
    def scope(self) -> None:
        for (schema,) in self.rows(
            "SELECT n.nspname FROM pg_namespace n"  # noqa: S608 - constant namespace filter
            f" WHERE {_USER_NAMESPACE} AND n.nspname <> 'public'"
        ):
            self.fail(f"1: schema {schema} exists; only public is allowed")
        relations = self.rows(
            "SELECT c.oid, c.relname, n.nspname, c.relkind,"  # noqa: S608 - constant namespace filter, no input
            " (SELECT a.attnum FROM pg_attribute a WHERE a.attrelid = c.oid"
            "   AND a.attname = 'tenant_id' AND a.attnum > 0 AND NOT a.attisdropped)"
            " FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
            f" WHERE {_USER_NAMESPACE} AND c.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')"
            " ORDER BY n.nspname, c.relname"
        )
        for oid, name, schema, kind, tenant_attnum in relations:
            if schema != "public":
                self.fail(f"1: relation {schema}.{name} is outside schema public")
                continue
            if kind == "f":
                self.fail(f"1: foreign table {name}")
            elif kind in ("r", "p"):
                if tenant_attnum is not None:
                    self.tenant_tables[oid] = (name, tenant_attnum)
                elif name in PLATFORM_TABLES:
                    self.platform_oids[name] = oid
                else:
                    self.fail(f"1: table {name} is neither a tenant table nor allow-listed")
        if not self.tenant_tables and not self.allow_no_tenant_tables:
            self.fail("1: no tenant table found; the check would be vacuous")
        for name in sorted(PLATFORM_TABLES - set(self.platform_oids)):
            self.fail(f"10: platform table {name} is missing")

    # 2. Tenant tables --------------------------------------------------------------
    def tenant_rules(self) -> None:
        for oid, (name, _) in sorted(self.tenant_tables.items(), key=lambda i: i[1][0]):
            column = self.rows(
                "SELECT format_type(a.atttypid, a.atttypmod), a.attnotnull FROM pg_attribute a"
                " WHERE a.attrelid = %s AND a.attname = 'tenant_id'",
                [oid],
            )
            if column != [("uuid", True)]:
                self.fail(f"2: {name}.tenant_id must be uuid NOT NULL")
            enabled, forced = self.rows(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = %s", [oid]
            )[0]
            if not enabled:
                self.fail(f"2: {name} does not have row level security enabled")
            if not forced:
                self.fail(f"2: {name} does not force row level security")
            policies = self.rows(
                "SELECT polname, polcmd, polpermissive, polroles::text,"
                " pg_get_expr(polqual, polrelid), pg_get_expr(polwithcheck, polrelid)"
                " FROM pg_policy WHERE polrelid = %s",
                [oid],
            )
            if [(ANY_TENANT_TABLE, *p) for p in policies] != [TENANT_POLICY]:
                self.fail(f"2: {name} must have exactly the one pinned {TENANT_POLICY_NAME} policy")

    def policies(self) -> None:
        tenant_names = {name for name, _ in self.tenant_tables.values()}
        rows = self.rows(
            "SELECT c.relname, p.polname, p.polcmd, p.polpermissive, p.polroles::text,"
            " pg_get_expr(p.polqual, p.polrelid), pg_get_expr(p.polwithcheck, p.polrelid)"
            " FROM pg_policy p JOIN pg_class c ON c.oid = p.polrelid ORDER BY 1, 2"
        )
        for table, *rest in rows:
            key = (ANY_TENANT_TABLE if table in tenant_names else table, *rest)
            if key not in POLICY_ALLOW_LIST:
                self.fail(f"2: policy {rest[0]} on {table} is not on the policy allow-list")

    # 3. Privileges -----------------------------------------------------------------
    def privileges(self) -> None:
        for (name,) in self.rows(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"  # noqa: S608 - constant namespace filter, no input
            f" WHERE {_USER_NAMESPACE} AND c.relkind IN ('r', 'p', 'v', 'm', 'f')"
            " AND (has_table_privilege(%s, c.oid, 'TRUNCATE')"
            "  OR has_table_privilege(%s, c.oid, 'REFERENCES')"
            "  OR has_table_privilege(%s, c.oid, 'TRIGGER')) ORDER BY 1",
            [self.app] * 3,
        ):
            self.fail(f"3: the app role has TRUNCATE, REFERENCES or TRIGGER on {name}")
        for oid, (name, _) in sorted(self.tenant_tables.items(), key=lambda i: i[1][0]):
            if self.value("SELECT has_table_privilege(%s, %s::oid, 'UPDATE')", [self.app, oid]):
                self.fail(f"3: the app role has table-level UPDATE on {name}")
            for (column,) in self.rows(
                "SELECT a.attname FROM pg_attribute a WHERE a.attrelid = %s"
                " AND a.attname IN ('id', 'tenant_id') AND a.attnum > 0 AND NOT a.attisdropped"
                " AND has_column_privilege(%s, a.attrelid, a.attnum, 'UPDATE') ORDER BY 1",
                [oid, self.app],
            ):
                self.fail(f"3: the app role can UPDATE {name}.{column}")
        for (name,) in self.rows(
            "SELECT DISTINCT c.relname FROM pg_class c"  # noqa: S608 - constant namespace filter, no input
            " JOIN pg_namespace n ON n.oid = c.relnamespace"
            " LEFT JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0"
            f" WHERE {_USER_NAMESPACE} AND ("
            "  EXISTS (SELECT 1 FROM aclexplode(c.relacl) x WHERE x.grantee = 0)"
            "  OR EXISTS (SELECT 1 FROM aclexplode(a.attacl) x WHERE x.grantee = 0)) ORDER BY 1"
        ):
            self.fail(f"3: PUBLIC holds a privilege on {name}")
        for (schema,) in self.rows(
            "SELECT nspname FROM pg_namespace WHERE has_schema_privilege(%s, oid, 'CREATE')",
            [self.app],
        ):
            self.fail(f"3: the app role has CREATE on schema {schema}")
        for privilege in ("CREATE", "TEMP"):
            if self.value(
                "SELECT has_database_privilege(%s, current_database(), %s)",
                [self.app, privilege],
            ):
                self.fail(f"3: the app role has {privilege} on the database")

    # 4. Uniqueness ---------------------------------------------------------------------
    def uniqueness(self) -> None:
        for oid, (name, tenant_attnum) in sorted(self.tenant_tables.items(), key=lambda i: i[1][0]):
            id_attnum = self.value(
                "SELECT attnum FROM pg_attribute WHERE attrelid = %s AND attname = 'id'"
                " AND attnum > 0 AND NOT attisdropped",
                [oid],
            )
            for index, primary, first, keys in self.rows(
                "SELECT ic.relname, i.indisprimary, i.indkey[0], i.indnkeyatts FROM pg_index i"
                " JOIN pg_class ic ON ic.oid = i.indexrelid"
                " WHERE i.indrelid = %s AND (i.indisunique OR i.indisexclusion) ORDER BY 1",
                [oid],
            ):
                if primary:
                    if id_attnum is None or first != id_attnum or keys != 1:
                        self.fail(f"4: the primary key of {name} must be id alone")
                elif first != tenant_attnum:
                    self.fail(f"4: unique index {index} on {name} does not lead with tenant_id")

    # 5. Foreign keys -------------------------------------------------------------------
    def foreign_keys(self) -> None:
        registry_oid = self.platform_oids.get(REGISTRY_TABLE)
        registry_id = (
            self.value(
                "SELECT attnum FROM pg_attribute WHERE attrelid = %s AND attname = 'id'",
                [registry_oid],
            )
            if registry_oid
            else None
        )
        has_registry_fk: set[int] = set()
        for name, source, source_oid, target, target_oid, keys, target_keys in self.rows(
            "SELECT con.conname, s.relname, con.conrelid, t.relname, con.confrelid,"
            " con.conkey::int2[], con.confkey::int2[] FROM pg_constraint con"
            " JOIN pg_class s ON s.oid = con.conrelid JOIN pg_class t ON t.oid = con.confrelid"
            " WHERE con.contype = 'f' ORDER BY 1"
        ):
            pairs = set(zip(keys, target_keys, strict=True))
            source_tenant = self.tenant_tables.get(source_oid)
            if target_oid in self.tenant_tables:
                if source_tenant is None:
                    self.fail(f"5: FK {name} goes from non-tenant table {source} into {target}")
                elif (source_tenant[1], self.tenant_tables[target_oid][1]) not in pairs:
                    self.fail(f"5: FK {name} ({source} -> {target}) does not pair tenant_id")
            elif (
                source_tenant is not None
                and target_oid == registry_oid
                and pairs == {(source_tenant[1], registry_id)}
            ):
                has_registry_fk.add(source_oid)
        for oid, (name, _) in sorted(self.tenant_tables.items(), key=lambda i: i[1][0]):
            if oid not in has_registry_fk:
                self.fail(f"5: {name} has no FK (tenant_id) -> {REGISTRY_TABLE}(id)")

    # 6. Roles ----------------------------------------------------------------------------
    def roles(self) -> None:
        flags = self.rows(
            "SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb, rolreplication,"
            " rolinherit, coalesce(rolconfig, '{}') FROM pg_roles WHERE rolname = %s",
            [self.app],
        )[0]
        names = ("SUPERUSER", "BYPASSRLS", "CREATEROLE", "CREATEDB", "REPLICATION", "INHERIT")
        for flag_name, flag in zip(names, flags[:6], strict=True):
            if flag:
                self.fail(f"6: the app role has {flag_name}")
        for (role,) in self.rows(
            "SELECT r.rolname FROM pg_roles r"
            " WHERE r.oid <> %s AND pg_has_role(%s, r.oid, 'MEMBER') ORDER BY 1",
            [self.app_oid, self.app],
        ):
            self.fail(f"6: the app role is a member of {role}")
        owned = {
            "relation": "SELECT count(*) FROM pg_class WHERE relowner = %s",
            "schema": "SELECT count(*) FROM pg_namespace WHERE nspowner = %s",
            "function": "SELECT count(*) FROM pg_proc WHERE proowner = %s",
            "type": "SELECT count(*) FROM pg_type WHERE typowner = %s",
            "database": "SELECT count(*) FROM pg_database WHERE datdba = %s",
            "large object": "SELECT count(*) FROM pg_largeobject_metadata WHERE lomowner = %s",
        }
        for kind, query in owned.items():
            if self.value(query, [self.app_oid]):
                self.fail(f"6: the app role owns a {kind}")
        config: list[str] = list(flags[6])
        for required in REQUIRED_ROLE_SETTINGS:
            if not any(entry.startswith(required) for entry in config):
                self.fail(f"6: the app role has no {required.rstrip('=')} setting")
        for entry in config:
            if entry.lower().startswith(FORBIDDEN_ROLE_SETTINGS):
                self.fail(f"6: the app role has a forbidden setting ({entry.split('=')[0]})")
        for (setting,) in self.rows(
            "SELECT DISTINCT split_part(s.c, '=', 1) FROM pg_db_role_setting d,"
            " unnest(d.setconfig) AS s(c)"
            " WHERE d.setdatabase IN (0, (SELECT oid FROM pg_database"
            "   WHERE datname = current_database()))"
            " AND lower(s.c) LIKE 'app.%%' ORDER BY 1"
        ):
            self.fail(f"6: a role or database setting sets {setting}")

    # 7. Views --------------------------------------------------------------------------
    def views(self) -> None:
        for name, kind, options in self.rows(
            "SELECT c.relname, c.relkind, coalesce(c.reloptions, '{}') FROM pg_class c"  # noqa: S608 - constant namespace filter, no input
            " JOIN pg_namespace n ON n.oid = c.relnamespace"
            f" WHERE {_USER_NAMESPACE} AND c.relkind IN ('v', 'm') ORDER BY 1"
        ):
            if kind == "m":
                self.fail(f"7: materialized view {name}")
            elif not any(
                option.lower() == f"security_invoker={value}"
                for option in options
                for value in _TRUE_OPTIONS
            ):
                self.fail(f"7: view {name} is not security_invoker")

    # 8. SECURITY DEFINER -----------------------------------------------------------------
    def definers(self) -> None:
        found = {
            (str(sig), str(owner), str(src), config, acl)
            for sig, owner, src, config, acl in self.rows(
                "SELECT p.oid::regprocedure::text, pg_get_userbyid(p.proowner), md5(p.prosrc),"
                " p.proconfig::text, p.proacl::text FROM pg_proc p"
                " JOIN pg_namespace n ON n.oid = p.pronamespace"
                " WHERE p.prosecdef AND p.prokind IN ('f', 'p')"
                " AND n.nspname NOT IN ('pg_catalog', 'information_schema')"
            )
        }
        for entry in sorted(found - self.definer_allow_list):
            self.fail(f"8: SECURITY DEFINER function {entry[0]} is not on the allow-list")
        for entry in sorted(self.definer_allow_list - found):
            self.fail(f"8: allow-listed SECURITY DEFINER function {entry[0]} is missing or changed")

    # 9. BYPASSRLS ------------------------------------------------------------------------
    def bypassrls(self) -> None:
        for (role,) in self.rows(
            "SELECT rolname FROM pg_roles WHERE rolbypassrls AND NOT rolsuper ORDER BY 1"
        ):
            if role not in self.bypassrls_allow_list:
                self.fail(f"9: role {role} has BYPASSRLS")

    # 10. Registry and django_migrations ------------------------------------------------
    def _grants(self, oid: int) -> tuple[set[str], set[tuple[str, str]], set[str]]:
        """(app table privileges, app (column, privilege) pairs, other grantees)."""
        table = {
            p
            for (p,) in self.rows(
                "SELECT x.privilege_type FROM pg_class c, aclexplode(c.relacl) x"
                " WHERE c.oid = %s AND x.grantee = %s",
                [oid, self.app_oid],
            )
        }
        columns = {
            (str(column), str(p))
            for column, p in self.rows(
                "SELECT a.attname, x.privilege_type FROM pg_attribute a, aclexplode(a.attacl) x"
                " WHERE a.attrelid = %s AND a.attnum > 0 AND x.grantee = %s",
                [oid, self.app_oid],
            )
        }
        others = {
            str(r)
            for (r,) in self.rows(
                "SELECT DISTINCT pg_get_userbyid(x.grantee) FROM pg_class c"
                " LEFT JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0,"
                " LATERAL (SELECT * FROM aclexplode(c.relacl)"
                "   UNION ALL SELECT * FROM aclexplode(a.attacl)) x"
                " WHERE c.oid = %s AND x.grantee NOT IN (c.relowner, %s)",
                [oid, self.app_oid],
            )
        }
        return table, columns, others

    def platform_tables(self) -> None:
        registry = self.platform_oids.get(REGISTRY_TABLE)
        if registry is not None:
            enabled, forced, owner = self.rows(
                "SELECT relrowsecurity, relforcerowsecurity, pg_get_userbyid(relowner)"
                " FROM pg_class WHERE oid = %s",
                [registry],
            )[0]
            if not enabled or forced:
                self.fail("10: the registry must have RLS enabled and not forced (D4)")
            if owner != self.owner:
                self.fail("10: the registry must be owned by the migrator role")
            policies = self.value("SELECT count(*) FROM pg_policy WHERE polrelid = %s", [registry])
            if policies != 1:
                self.fail(f"10: the registry must have exactly the {REGISTRY_POLICY_NAME} policy")
            table, columns, others = self._grants(registry)
            if table:
                self.fail("10: the app role has a table-level privilege on the registry")
            if {c for c, p in columns if p == "SELECT"} != REGISTRY_READABLE_COLUMNS or any(
                p != "SELECT" for _, p in columns
            ):
                self.fail("10: the app role must have SELECT on exactly id, name, status")
            if others:
                self.fail("10: another role holds privileges on the registry")
        migrations = self.platform_oids.get(MIGRATIONS_TABLE)
        if migrations is not None:
            table, columns, others = self._grants(migrations)
            if table != {"SELECT"} or columns:
                self.fail(f"10: the app role must have SELECT only on {MIGRATIONS_TABLE}")
            if others:
                self.fail(f"10: another role holds privileges on {MIGRATIONS_TABLE}")
        for (name,) in self.rows(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"  # noqa: S608 - constant namespace filter, no input
            f" WHERE {_USER_NAMESPACE} AND c.relkind = 'S'"
            " AND (has_sequence_privilege(%s, c.oid, 'USAGE')"
            "  OR has_sequence_privilege(%s, c.oid, 'SELECT')"
            "  OR has_sequence_privilege(%s, c.oid, 'UPDATE')) ORDER BY 1",
            [self.app] * 3,
        ):
            self.fail(f"10: the app role has a privilege on sequence {name}")

    # 11. Other objects ---------------------------------------------------------------------
    def other_objects(self) -> None:
        extensions = {e for (e,) in self.rows("SELECT extname FROM pg_extension")}
        if extensions != EXTENSIONS:
            self.fail(f"11: extensions must be exactly {sorted(EXTENSIONS)}")
        for name, table in self.rows(
            "SELECT t.tgname, c.relname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid"
            " WHERE NOT t.tgisinternal ORDER BY 1"
        ):
            self.fail(f"11: trigger {name} on {table}")
        for (name,) in self.rows("SELECT evtname FROM pg_event_trigger ORDER BY 1"):
            self.fail(f"11: event trigger {name}")
        if self.value("SELECT count(*) FROM pg_largeobject_metadata"):
            self.fail("11: large objects exist")
        for oid, (name, _) in sorted(self.tenant_tables.items(), key=lambda i: i[1][0]):
            if self.value(
                "SELECT count(*) FROM pg_attribute WHERE attrelid = %s AND attnum > 0"
                " AND NOT attisdropped AND (attidentity <> '' OR attgenerated <> '')",
                [oid],
            ) or self.value(
                "SELECT count(*) FROM pg_depend d JOIN pg_class s ON s.oid = d.objid"
                " WHERE d.classid = 'pg_class'::regclass AND d.refobjid = %s"
                " AND s.relkind = 'S'",
                [oid],
            ):
                self.fail(f"11: tenant table {name} has a sequence or identity column")
        expected = {
            ("r", "public", self.app, p) for p in ("SELECT", "INSERT", "UPDATE", "DELETE")
        } | {("S", "public", self.app, p) for p in ("USAGE", "SELECT")}
        found: set[tuple[str, str, str, str]] = set()
        for role, kind, schema, grantee, privilege in self.rows(
            "SELECT pg_get_userbyid(d.defaclrole), d.defaclobjtype, n.nspname,"
            " CASE WHEN x.grantee = 0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee) END,"
            " x.privilege_type FROM pg_default_acl d"
            " LEFT JOIN pg_namespace n ON n.oid = d.defaclnamespace,"
            " aclexplode(d.defaclacl) x"
        ):
            if role != self.owner:
                self.fail(f"11: role {role} has default privileges")
            elif grantee == "PUBLIC":
                self.fail("11: default privileges grant something to PUBLIC")
            else:
                found.add((str(kind), str(schema), str(grantee), str(privilege)))
        if found != expected:
            self.fail("11: the migrator's default privileges differ from the bootstrap set")


def catalog_failures(
    alias: str = "default",
    *,
    app_role: str | None = None,
    owner_role: str | None = None,
    allow_no_tenant_tables: bool = False,
    definer_allow_list: Iterable[DefinerEntry] = DEFINER_ALLOW_LIST,
    bypassrls_allow_list: Iterable[str] = BYPASSRLS_ALLOW_LIST,
) -> list[str]:
    """Every violated catalog rule (C-12) on the database behind ``alias``."""
    with connections[alias].cursor() as cursor:
        return _Check(
            cursor,
            app_role or _default_app_role(),
            owner_role or _default_owner_role(),
            allow_no_tenant_tables,
            definer_allow_list,
            bypassrls_allow_list,
        ).run()


def read_only_catalog_failures(
    alias: str = "default", *, allow_no_tenant_tables: bool = True
) -> list[str]:
    """``catalog_failures`` in its own ``READ ONLY`` transaction (C-12(12)).

    Opens the outermost transaction on ``alias``; ``SET TRANSACTION READ ONLY``
    must be its first statement.
    """
    from django.db import transaction

    with transaction.atomic(using=alias, durable=True), connections[alias].cursor() as cursor:
        cursor.execute("SET TRANSACTION READ ONLY")
        return catalog_failures(alias, allow_no_tenant_tables=allow_no_tenant_tables)


def main() -> int:
    """``make catalog-check``: the migrated dev DB, read-only, as the app role (C-12(12)).

    Zero tenant tables is allowed there (the probe app is test-only); every
    other rule applies.
    """
    import os

    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    django.setup()
    failures = read_only_catalog_failures("default", allow_no_tenant_tables=True)
    for failure in failures:
        print(f"catalog-check: {failure}", file=sys.stderr)
    if failures:
        return 1
    print("catalog-check: no violations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
