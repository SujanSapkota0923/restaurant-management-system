"""The test run connects as the app role to the test DB (C3-7, SC-24, SC-25, NT3-24).

The same checks run in the session guard in conftest.py, which aborts the run
on failure; these tests name each check so a regression is easy to read.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from django.conf import settings
from django.db import DatabaseError, connections, transaction

from config.tests.db_guards import database_guard_failures

pytestmark = pytest.mark.django_db


def one(query: str, params: tuple[Any, ...] = (), alias: str = "default") -> Any:
    with connections[alias].cursor() as cursor:
        cursor.execute(query, params)
        row = cursor.fetchone()
    return None if row is None else row[0]


@pytest.mark.django_db(databases=["default", "migrator"])
def test_all_session_guards_pass() -> None:
    assert database_guard_failures() == []


def test_connected_to_the_test_database() -> None:
    assert one("SELECT current_database()") == "test_rms"
    assert one("SELECT current_database()") != os.environ["DB_NAME"]


def test_connected_as_the_app_role() -> None:
    assert one("SELECT current_user") == settings.DATABASES["default"]["USER"]
    assert one("SELECT current_user") != settings.DATABASES["migrator"]["USER"]


def test_app_role_has_no_elevated_attributes() -> None:
    flags = one(
        "SELECT row(rolsuper, rolbypassrls, rolinherit, rolcreatedb, rolcreaterole,"
        " rolreplication)::text FROM pg_roles WHERE rolname = current_user"
    )
    assert flags == "(f,f,f,f,f,f)"


def test_app_role_is_member_of_nothing() -> None:
    assert (
        one(
            "SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.member"
            " WHERE r.rolname = current_user"
        )
        == 0
    )


def test_app_role_has_no_create_or_temp_on_database() -> None:
    assert one("SELECT has_database_privilege(current_user, current_database(), 'CREATE')") is False
    assert one("SELECT has_database_privilege(current_user, current_database(), 'TEMP')") is False


def test_public_has_no_database_privileges() -> None:
    acl = one("SELECT datacl::text FROM pg_database WHERE datname = current_database()")
    assert acl is not None
    # An ACL entry for PUBLIC starts with "=" ({=Tc/owner,...}).
    assert not any(entry.startswith("=") for entry in acl.strip("{}").split(","))


def test_app_role_owns_nothing() -> None:
    for query in (
        "SELECT count(*) FROM pg_database d JOIN pg_roles r ON r.oid = d.datdba"
        " WHERE r.rolname = current_user",
        "SELECT count(*) FROM pg_namespace n JOIN pg_roles r ON r.oid = n.nspowner"
        " WHERE r.rolname = current_user",
        "SELECT count(*) FROM pg_class c JOIN pg_roles r ON r.oid = c.relowner"
        " WHERE r.rolname = current_user",
    ):
        assert one(query) == 0


def test_app_role_cannot_create_tables() -> None:
    with pytest.raises(DatabaseError), transaction.atomic():
        connections["default"].cursor().execute("CREATE TABLE public.rms_probe (id integer)")


def test_app_role_cannot_create_temp_tables() -> None:
    with pytest.raises(DatabaseError), transaction.atomic():
        connections["default"].cursor().execute("CREATE TEMP TABLE rms_probe (id integer)")


@pytest.mark.django_db(databases=["default", "migrator"])
def test_migrator_alias_sees_the_test_database() -> None:
    assert one("SELECT current_database()", alias="migrator") == "test_rms"
    assert one("SELECT current_user", alias="migrator") == settings.DATABASES["migrator"]["USER"]
