"""``make migrations-roundtrip`` (change 0004, 6.10, C-17, T4-23).

Applies every migration, reverses every app with migrations to ``zero``, applies
them again and ends with the catalog check. It proves that every RLS, grant and
composite-FK operation is reversible and that a full reverse leaves nothing
behind.

It runs only on a throwaway database, never on the dev DB:

- the target name must match ``rms_roundtrip`` (optionally ``_<suffix>``) and
  must differ from ``DB_NAME``, the test DB name and the template name;
- the migrator creates it from ``rms_template``, locks its ACL down like the
  test DB (no PUBLIC; CONNECT for the app role and the migrator only) and drops
  it at the end, also after a failure;
- both aliases are pointed at it before Django opens any connection, and the
  script checks that before the first query;
- it always uses ``config.settings.test``, so the test-only probe tenant tables
  are included (D6: they never reach the dev DB).

Usage: ``python -m config.tests.roundtrip [target]`` (``make migrations-roundtrip``).
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Sequence
from typing import Any

SETTINGS_MODULE = "config.settings.test"
DEFAULT_TARGET = "rms_roundtrip"
TARGET_PATTERN = re.compile(r"^rms_roundtrip(_[a-z0-9]{1,20})?$")
ALIASES = ("default", "migrator")
# What a full reverse may leave: the migration history itself.
RESIDUE_ALLOWED = frozenset({"django_migrations", "django_migrations_id_seq"})


def target_problem(target: str, *, dev_db: str, test_db: str, template_db: str) -> str | None:
    """Why ``target`` must not be used, or ``None`` (C-17)."""
    if not TARGET_PATTERN.match(target):
        return f"the round-trip database name must match {TARGET_PATTERN.pattern}"
    if target in (dev_db, test_db, template_db):
        return "the round-trip database must not be the dev, test or template database"
    return None


def _say(message: str) -> None:
    print(f"migrations-roundtrip: {message}", flush=True)


def _admin_connection(settings_dict: dict[str, Any]) -> Any:
    """An autocommit connection to the ``postgres`` maintenance DB as the migrator."""
    import psycopg

    return psycopg.connect(
        host=settings_dict["HOST"],
        port=settings_dict["PORT"],
        user=settings_dict["USER"],
        password=settings_dict["PASSWORD"],
        dbname="postgres",
        connect_timeout=5,
        autocommit=True,
    )


def _create(admin: Any, target: str, template: str, app_role: str, migrator_role: str) -> None:
    from psycopg import sql

    db = sql.Identifier(target)
    # A leftover from an interrupted run; only a name that passed target_problem.
    admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(db))
    admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(db, sql.Identifier(template)))
    admin.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(db))
    admin.execute(
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}, {}").format(
            db, sql.Identifier(app_role), sql.Identifier(migrator_role)
        )
    )


def _drop(admin: Any, target: str) -> None:
    from psycopg import sql

    admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(target)))


def _apps_in_dependency_order() -> list[str]:
    """App labels with migrations, in the order a full forward plan applies them."""
    from django.db import connections
    from django.db.migrations.loader import MigrationLoader

    graph = MigrationLoader(connections["migrator"]).graph
    order: list[str] = []
    # Each forwards plan lists dependencies first, so first appearances are in order.
    for leaf in sorted(graph.leaf_nodes()):
        for app_label, _ in graph.forwards_plan(leaf):
            if app_label not in order:
                order.append(app_label)
    return order


def _residue() -> list[str]:
    """Relations, policies and history rows left after every app was reversed."""
    from django.db import connections

    problems: list[str] = []
    with connections["migrator"].cursor() as cursor:
        cursor.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
            " WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')"
            " ORDER BY 1"
        )
        problems += [
            f"relation {name} left behind"
            for (name,) in cursor.fetchall()
            if name not in RESIDUE_ALLOWED
        ]
        cursor.execute("SELECT count(*) FROM pg_policy")
        row = cursor.fetchone()
        if row and row[0]:
            problems.append(f"{row[0]} policies left behind")
        cursor.execute("SELECT count(*) FROM django_migrations")
        row = cursor.fetchone()
        if row and row[0]:
            problems.append(f"{row[0]} applied migrations still recorded")
    return problems


def _catalog(stage: str) -> list[str]:
    from rms.tenancy.tests.catalog import catalog_failures

    # Strict: the probe tenant tables must exist, or the check would be vacuous.
    return [f"{stage}: {failure}" for failure in catalog_failures("default")]


def _round_trip() -> list[str]:
    from django.core.management import call_command
    from django.db import connections

    def migrate(*args: str) -> None:
        call_command("migrate", *args, database="migrator", interactive=False, verbosity=1)

    _say("applying every migration")
    migrate()
    failures = _catalog("after the first migrate")
    connections["default"].close()
    apps = _apps_in_dependency_order()
    for app_label in reversed(apps):
        _say(f"reversing {app_label} to zero")
        migrate(app_label, "zero")
    failures += [f"after reversing to zero: {p}" for p in _residue()]
    _say("applying every migration again")
    migrate()
    failures += _catalog("after the second migrate")
    return failures


def main(argv: Sequence[str]) -> int:
    os.environ["DJANGO_SETTINGS_MODULE"] = SETTINGS_MODULE
    from django.conf import settings

    target = argv[0] if argv else DEFAULT_TARGET
    # Reading settings opens no connection.
    databases: dict[str, dict[str, Any]] = settings.DATABASES
    problem = target_problem(
        target,
        dev_db=str(databases["default"]["NAME"]),
        test_db=str(settings.TEST_DB_NAME),
        template_db=str(settings.TEST_DB_TEMPLATE),
    )
    if problem:
        print(f"migrations-roundtrip: {problem}", file=sys.stderr)
        return 2
    template = str(settings.TEST_DB_TEMPLATE)
    app_role = str(databases["default"]["USER"])
    migrator_role = str(databases["migrator"]["USER"])
    # Before django.setup() and before the connection handler reads DATABASES.
    for alias in ALIASES:
        databases[alias]["NAME"] = target

    import django

    django.setup()
    from django.db import connections

    for alias in ALIASES:
        if connections[alias].settings_dict["NAME"] != target:
            print(f"migrations-roundtrip: {alias} is not on the round-trip DB", file=sys.stderr)
            return 2

    with _admin_connection(databases["migrator"]) as admin:
        _say(f"creating {target} from {template}")
        _create(admin, target, template, app_role, migrator_role)
        try:
            failures = _round_trip()
        finally:
            connections.close_all()
            _say(f"dropping {target}")
            _drop(admin, target)
    for failure in failures:
        print(f"migrations-roundtrip: {failure}", file=sys.stderr)
    if failures:
        return 1
    _say("forward, reverse to zero and forward again passed; catalog check clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
