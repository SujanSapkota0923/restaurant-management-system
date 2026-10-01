"""Test-database lock-down and guards (C3-7, SC-24, SC-25).

``conftest.py`` runs ``lock_down_test_database`` right after the test DB is
created, then ``database_guard_failures``; any failure aborts the whole run
before a single test executes. ``test_db_guards.py`` asserts the same checks
individually so a failure is visible by name.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import DatabaseError, connections, transaction
from psycopg import sql

APP_ALIAS = "default"
MIGRATOR_ALIAS = "migrator"
SETUP_ALIASES = frozenset({APP_ALIAS, MIGRATOR_ALIAS})


def _one(alias: str, query: str, params: tuple[Any, ...] = ()) -> Any:
    with connections[alias].cursor() as cursor:
        cursor.execute(query, params)
        row = cursor.fetchone()
    return None if row is None else row[0]


def lock_down_test_database() -> None:
    """Database ACLs are not copied from the template: Django's new test DB
    grants PUBLIC CONNECT and TEMP. Revoke them, as the owner (migrator)."""
    test_db = str(settings.DATABASES[MIGRATOR_ALIAS]["NAME"])
    app_user = str(settings.DATABASES[APP_ALIAS]["USER"])
    migrator_user = str(settings.DATABASES[MIGRATOR_ALIAS]["USER"])
    connection = connections[MIGRATOR_ALIAS]
    connection.ensure_connection()
    raw = connection.connection
    statements = [
        sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(test_db)),
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}, {}").format(
            sql.Identifier(test_db), sql.Identifier(app_user), sql.Identifier(migrator_user)
        ),
    ]
    with connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement.as_string(raw))


def database_guard_failures() -> list[str]:
    """Every reason the suite must not run. Empty means safe."""
    failures: list[str] = []
    expected_db = getattr(settings, "TEST_DB_NAME", None)
    app_user = settings.DATABASES[APP_ALIAS]["USER"]
    migrator_user = settings.DATABASES[MIGRATOR_ALIAS]["USER"]

    if settings.SETTINGS_MODULE != "config.settings.test":
        failures.append("tests must run with config.settings.test")
    if _one(MIGRATOR_ALIAS, "SELECT current_database()") != expected_db:
        failures.append("the migrator alias is not connected to the test DB")
    if _one(APP_ALIAS, "SELECT current_database()") != expected_db:
        failures.append("the default alias is not connected to the test DB")
    if _one(APP_ALIAS, "SELECT current_user") != app_user:
        failures.append("the default alias is not connected as the app role")

    role_flags = (
        "SELECT rolsuper, rolbypassrls, rolinherit, rolcreatedb, rolcreaterole, rolreplication "
        "FROM pg_roles WHERE rolname = current_user"
    )
    with connections[APP_ALIAS].cursor() as cursor:
        cursor.execute(role_flags)
        flags = cursor.fetchone()
    names = ("SUPERUSER", "BYPASSRLS", "INHERIT", "CREATEDB", "CREATEROLE", "REPLICATION")
    for name, value in zip(names, flags or (True,) * len(names), strict=True):
        if value:
            failures.append(f"the app role has {name}")

    checks = {
        "the app role is a member of a role": (
            "SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.member "
            "WHERE r.rolname = current_user",
            (),
        ),
        "the app role is a member of the migrator role": (
            "SELECT pg_has_role(current_user, %s, 'MEMBER')::int",
            (migrator_user,),
        ),
        "the app role has CREATE on the database": (
            "SELECT has_database_privilege(current_user, current_database(), 'CREATE')::int",
            (),
        ),
        "the app role has TEMP on the database": (
            "SELECT has_database_privilege(current_user, current_database(), 'TEMP')::int",
            (),
        ),
        "the app role has CREATE on schema public": (
            "SELECT has_schema_privilege(current_user, 'public', 'CREATE')::int",
            (),
        ),
        "the app role owns a database": (
            "SELECT count(*) FROM pg_database d JOIN pg_roles r ON r.oid = d.datdba "
            "WHERE r.rolname = current_user",
            (),
        ),
        "the app role owns a schema": (
            "SELECT count(*) FROM pg_namespace n JOIN pg_roles r ON r.oid = n.nspowner "
            "WHERE r.rolname = current_user",
            (),
        ),
        "the app role owns a relation": (
            "SELECT count(*) FROM pg_class c JOIN pg_roles r ON r.oid = c.relowner "
            "WHERE r.rolname = current_user",
            (),
        ),
    }
    for message, (query, params) in checks.items():
        if _one(APP_ALIAS, query, params):
            failures.append(message)

    if app_role_can_create_table():
        failures.append("the app role can CREATE TABLE in schema public")
    return failures


def app_role_can_create_table() -> bool:
    """Try it for real; a success is cleaned up and reported."""
    try:
        # A savepoint (or a transaction in autocommit) keeps a failure contained.
        with transaction.atomic(using=APP_ALIAS), connections[APP_ALIAS].cursor() as cursor:
            cursor.execute("CREATE TABLE public.rms_guard_probe (id integer)")
            cursor.execute("DROP TABLE public.rms_guard_probe")
    except DatabaseError:
        return False
    return True
