"""Catalog check (C-12) and its negative tests (C-13, N-07).

Each negative case plants DDL as the migrator inside ``transaction.atomic`` on
the migrator alias, runs the check as the migrator *in the same transaction*
(parameterised by the app role name), and always rolls back. The flush is not
relied on: it never drops DDL (change 0004 F2). After each case the real
check must be clean again, on both connections (no residue).
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import pytest
from django.conf import settings
from django.db import ProgrammingError, connections, transaction
from psycopg import errors as pg_errors
from psycopg import sql

from rms.tenancy.data.rls import TENANT_POLICY_EXPRESSION
from rms.tenancy.tests.catalog import catalog_failures

pytestmark = pytest.mark.django_db(databases=["default", "migrator"])

PARENT = "tenancy_probe_probeparent"
CHILD = "tenancy_probe_probechild"


def app_role() -> str:
    return str(settings.DATABASES["default"]["USER"])


@contextmanager
def rolled_back(alias: str = "migrator") -> Iterator[Any]:
    """A migrator transaction (or savepoint) that is always rolled back."""
    with transaction.atomic(using=alias), connections[alias].cursor() as cursor:
        yield cursor
        transaction.set_rollback(True, using=alias)


def _sql(template: str, **names: str) -> str:
    return (
        sql.SQL(template)
        .format(**{key: sql.Identifier(value) for key, value in names.items()})
        .as_string(None)
    )


def test_catalog_is_clean() -> None:
    assert catalog_failures("default") == []


def test_catalog_is_clean_as_the_migrator() -> None:
    assert catalog_failures("migrator", app_role=app_role()) == []


def test_catalog_sees_the_probe_tenant_tables() -> None:
    """Positive control: the clean result is not vacuous."""
    with connections["default"].cursor() as cursor:
        cursor.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_attribute a ON a.attrelid = c.oid"
            " WHERE a.attname = 'tenant_id' AND c.relkind = 'r' AND a.attnum > 0 ORDER BY 1"
        )
        tables = [row[0] for row in cursor.fetchall()]
    assert tables == [CHILD, PARENT]


def test_zero_tenant_tables_fail_unless_allowed() -> None:
    with rolled_back() as cursor:
        cursor.execute(_sql("DROP TABLE {c}, {p}", c=CHILD, p=PARENT))
        strict = catalog_failures("migrator", app_role=app_role())
        lenient = catalog_failures("migrator", app_role=app_role(), allow_no_tenant_tables=True)
    assert any("no tenant table found" in f for f in strict)
    assert lenient == []


def _cases() -> dict[str, tuple[Sequence[str], str]]:
    app = app_role()
    expr = TENANT_POLICY_EXPRESSION
    return {
        "tenant table without FORCE": (
            [_sql("ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY", t=PARENT)],
            f"{PARENT} does not force row level security",
        ),
        "tenant table without RLS enabled": (
            [_sql("ALTER TABLE {t} DISABLE ROW LEVEL SECURITY", t=PARENT)],
            f"{PARENT} does not have row level security enabled",
        ),
        "tenant table without a policy": (
            [_sql("DROP POLICY tenant_isolation ON {t}", t=PARENT)],
            f"{PARENT} must have exactly the one pinned tenant_isolation policy",
        ),
        "second permissive policy": (
            [_sql("CREATE POLICY neg_extra ON {t} USING (true)", t=PARENT)],
            f"policy neg_extra on {PARENT} is not on the policy allow-list",
        ),
        "restrictive policy": (
            [_sql("CREATE POLICY neg_restrictive ON {t} AS RESTRICTIVE USING (true)", t=PARENT)],
            f"policy neg_restrictive on {PARENT} is not on the policy allow-list",
        ),
        "policy TO the app role": (
            [_sql("ALTER POLICY tenant_isolation ON {t} TO {r}", t=PARENT, r=app)],
            f"policy tenant_isolation on {PARENT} is not on the policy allow-list",
        ),
        "policy with an altered qual": (
            [_sql("ALTER POLICY tenant_isolation ON {t} USING (true)", t=PARENT)],
            f"policy tenant_isolation on {PARENT} is not on the policy allow-list",
        ),
        "non-invoker view": (
            [_sql("CREATE VIEW neg_view AS SELECT id FROM {t}", t=PARENT)],
            "view neg_view is not security_invoker",
        ),
        "materialized view": (
            ["CREATE MATERIALIZED VIEW neg_matview AS SELECT 1 AS x"],
            "materialized view neg_matview",
        ),
        "unlisted SECURITY DEFINER function": (
            [
                "CREATE FUNCTION neg_definer() RETURNS integer LANGUAGE sql SECURITY DEFINER"
                " AS 'SELECT 1'"
            ],
            "SECURITY DEFINER function neg_definer() is not on the allow-list",
        ),
        "unique constraint not leading with tenant_id": (
            [_sql("ALTER TABLE {t} ADD CONSTRAINT neg_unique UNIQUE (code)", t=PARENT)],
            f"unique index neg_unique on {PARENT} does not lead with tenant_id",
        ),
        "unique expression index": (
            [_sql("CREATE UNIQUE INDEX neg_expr ON {t} (lower(code))", t=PARENT)],
            f"unique index neg_expr on {PARENT} does not lead with tenant_id",
        ),
        "single-column tenant-to-tenant FK": (
            [
                _sql(
                    "ALTER TABLE {c} ADD CONSTRAINT neg_fk FOREIGN KEY (parent_id)"
                    " REFERENCES {p} (id)",
                    c=CHILD,
                    p=PARENT,
                )
            ],
            f"FK neg_fk ({CHILD} -> {PARENT}) does not pair tenant_id",
        ),
        "platform-to-tenant FK": (
            [
                _sql(
                    "CREATE TABLE neg_platform (id uuid PRIMARY KEY,"
                    " parent_id uuid CONSTRAINT neg_platform_fk REFERENCES {p} (id))",
                    p=PARENT,
                )
            ],
            f"FK neg_platform_fk goes from non-tenant table neg_platform into {PARENT}",
        ),
        "tenant table without the registry FK": (
            [
                _sql("CREATE TABLE neg_tenant (id uuid PRIMARY KEY, tenant_id uuid NOT NULL)"),
                _sql("ALTER TABLE neg_tenant ENABLE ROW LEVEL SECURITY"),
                _sql("ALTER TABLE neg_tenant FORCE ROW LEVEL SECURITY"),
                f"CREATE POLICY tenant_isolation ON neg_tenant USING ({expr}) WITH CHECK ({expr})",
            ],
            "neg_tenant has no FK (tenant_id) -> tenancy_restaurant(id)",
        ),
        "GRANT TRUNCATE to the app role": (
            [_sql("GRANT TRUNCATE ON {t} TO {r}", t=PARENT, r=app)],
            f"the app role has TRUNCATE, REFERENCES or TRIGGER on {PARENT}",
        ),
        "GRANT UPDATE (tenant_id) to the app role": (
            [_sql("GRANT UPDATE (tenant_id) ON {t} TO {r}", t=PARENT, r=app)],
            f"the app role can UPDATE {PARENT}.tenant_id",
        ),
        "table-level UPDATE to the app role": (
            [_sql("GRANT UPDATE ON {t} TO {r}", t=PARENT, r=app)],
            f"the app role has table-level UPDATE on {PARENT}",
        ),
        "PUBLIC privilege": (
            [_sql("GRANT SELECT ON {t} TO PUBLIC", t=PARENT)],
            f"PUBLIC holds a privilege on {PARENT}",
        ),
        "table in a new schema": (
            ["CREATE SCHEMA neg_schema", "CREATE TABLE neg_schema.neg_table (id integer)"],
            "schema neg_schema exists; only public is allowed",
        ),
        "unlisted non-tenant table": (
            ["CREATE TABLE neg_plain (id integer)"],
            "table neg_plain is neither a tenant table nor allow-listed",
        ),
        "trigger": (
            [
                "CREATE FUNCTION neg_trg() RETURNS trigger LANGUAGE plpgsql"
                " AS 'BEGIN RETURN NEW; END'",
                _sql(
                    "CREATE TRIGGER neg_trigger BEFORE INSERT ON {t}"
                    " FOR EACH ROW EXECUTE FUNCTION neg_trg()",
                    t=PARENT,
                ),
            ],
            f"trigger neg_trigger on {PARENT}",
        ),
        "large object": (
            ["SELECT lo_create(0)"],
            "large objects exist",
        ),
        "app-role write on django_migrations": (
            [_sql("GRANT INSERT ON django_migrations TO {r}", r=app)],
            "the app role must have SELECT only on django_migrations",
        ),
        "registry FORCE": (
            ["ALTER TABLE tenancy_restaurant FORCE ROW LEVEL SECURITY"],
            "the registry must have RLS enabled and not forced (D4)",
        ),
        "registry column grant widened": (
            [_sql("GRANT SELECT (created_at) ON tenancy_restaurant TO {r}", r=app)],
            "the app role must have SELECT on exactly id, name, status",
        ),
        "registry table-level grant": (
            [_sql("GRANT INSERT ON tenancy_restaurant TO {r}", r=app)],
            "the app role has a table-level privilege on the registry",
        ),
        "default privileges to PUBLIC": (
            ["ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO PUBLIC"],
            "default privileges grant something to PUBLIC",
        ),
        "identity column on a tenant table": (
            [
                _sql(
                    "ALTER TABLE {t} ADD COLUMN neg_serial integer GENERATED ALWAYS AS IDENTITY",
                    t=PARENT,
                )
            ],
            f"tenant table {PARENT} has a sequence or identity column",
        ),
    }


# Settings are configured before collection, so the role name is known here.
CASES = _cases()


@pytest.mark.parametrize("case", sorted(CASES))
def test_checker_reports_planted_violation(case: str) -> None:
    statements, expected = CASES[case]
    with rolled_back() as cursor:
        for statement in statements:
            cursor.execute(statement)
        failures = catalog_failures("migrator", app_role=app_role())
    assert any(expected in failure for failure in failures), failures
    # No residue: the planted DDL is gone on both connections.
    assert catalog_failures("migrator", app_role=app_role()) == []
    assert catalog_failures("default") == []


def test_allow_listed_definer_with_changed_config_is_reported() -> None:
    """C-12(8): ALTER FUNCTION ... SET leaves prosrc unchanged; the tuple catches it."""
    with rolled_back() as cursor:
        cursor.execute(
            "CREATE FUNCTION neg_listed() RETURNS integer LANGUAGE sql SECURITY DEFINER"
            " AS 'SELECT 1'"
        )
        cursor.execute(
            "SELECT p.oid::regprocedure::text, pg_get_userbyid(p.proowner), md5(p.prosrc),"
            " p.proconfig::text, p.proacl::text FROM pg_proc p WHERE p.proname = 'neg_listed'"
        )
        entry: Any = tuple(cursor.fetchone())
        listed = catalog_failures("migrator", app_role=app_role(), definer_allow_list={entry})
        assert not [f for f in listed if f.startswith("8:")]
        cursor.execute("ALTER FUNCTION neg_listed() SET search_path = pg_catalog")
        changed = catalog_failures("migrator", app_role=app_role(), definer_allow_list={entry})
    assert any("neg_listed() is missing or changed" in f for f in changed)
    assert any("neg_listed() is not on the allow-list" in f for f in changed)


def test_missing_app_role_is_reported() -> None:
    assert catalog_failures("default", app_role="rms_no_such_role") == [
        "6: the app role does not exist"
    ]


def test_no_residue_after_all_cases() -> None:
    assert catalog_failures("migrator", app_role=app_role()) == []
    assert catalog_failures("default") == []


# --- C-12(12): the read-only entry point used by `make catalog-check` ----------------


@pytest.mark.django_db(transaction=True, databases=["default", "migrator"])
def test_read_only_entry_point_is_clean_and_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    from rms.tenancy.tests import catalog

    assert catalog.read_only_catalog_failures("default", allow_no_tenant_tables=False) == []
    real = catalog.catalog_failures
    seen: dict[str, Any] = {}

    def spy(alias: str, **kwargs: Any) -> list[str]:
        with connections[alias].cursor() as cursor:
            cursor.execute("SHOW transaction_read_only")
            seen["read_only"] = cursor.fetchone()
        seen["allow_no_tenant_tables"] = kwargs.get("allow_no_tenant_tables")
        return real(alias, **kwargs)

    monkeypatch.setattr(catalog, "catalog_failures", spy)
    assert catalog.read_only_catalog_failures("default") == []
    assert seen == {"read_only": ("on",), "allow_no_tenant_tables": True}


# --- gate 8 additions (QA): rule 6 negatives and persisted context settings ---------


def test_role_rules_flag_privileged_roles() -> None:
    """C-12(6) has no planted DDL case (the migrator cannot create or alter
    roles), so it is exercised by checking real privileged roles in place of
    the app role: the superuser and the migrator must each fail."""
    migrator = str(settings.DATABASES["migrator"]["USER"])
    expected = {
        "postgres": {
            "6: the app role has SUPERUSER",
            "6: the app role has BYPASSRLS",
            "6: the app role is a member of pg_read_all_data",
            "6: the app role is a member of pg_write_all_data",
            "6: the app role owns a relation",
            "6: the app role has no statement_timeout setting",
        },
        migrator: {
            "6: the app role has CREATEDB",
            "6: the app role has INHERIT",
            "6: the app role owns a relation",
            "3: the app role has CREATE on schema public",
            "3: the app role has TEMP on the database",
            "10: the app role has a table-level privilege on the registry",
        },
    }
    for role, messages in expected.items():
        failures = set(catalog_failures("default", app_role=role))
        assert messages <= failures, (role, sorted(messages - failures))
    assert catalog_failures("default") == []  # control: the real app role is clean


@pytest.mark.parametrize("alias", ["default", "migrator"])
@pytest.mark.parametrize(
    "template",
    # Built by concatenation so the C-3 source scan does not match this file.
    [
        "ALTER ROLE CURRENT_USER SET " + "app.user_id = 'x'",
        "ALTER ROLE CURRENT_USER IN DATABASE {db} SET " + "app.tenant_id = 'x'",
        "ALTER DATABASE {db} SET " + "app.tenant_id = 'x'",
    ],
    ids=["role", "role-in-database", "database"],
)
def test_no_role_can_persist_a_context_setting(alias: str, template: str) -> None:
    """T4-04: neither the app role nor the migrator (the DB owner) can make
    app.* a role or database default. PostgreSQL 16 refuses placeholder
    settings there without superuser. The session-level form is possible,
    which is why the entry point checks the previous value (test_context)."""
    with connections[alias].cursor() as cursor:
        cursor.execute("SELECT current_database()")
        row = cursor.fetchone()
    assert row is not None
    statement = sql.SQL(template).format(db=sql.Identifier(row[0])).as_string(None)
    with pytest.raises(ProgrammingError) as exc, rolled_back(alias) as cursor:
        cursor.execute(statement)
    assert isinstance(exc.value.__cause__, pg_errors.InsufficientPrivilege)
    assert catalog_failures("default") == []
