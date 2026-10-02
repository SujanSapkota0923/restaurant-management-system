"""The isolation harness itself (SC-29, C-2, C-20; N-14).

The proof pair at the end must stay in this order in this module: the first
test commits rows, the second (run next) proves they were flushed.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from django.test import TestCase, TransactionTestCase

from config.tests.db_guards import database_guard_failures
from rms.tenancy.data.context import tenant_transaction
from rms.tenancy.tests import harness
from rms.tenancy.tests.factories import make_child
from rms.tenancy.tests.harness import (
    ISOLATION_DB,
    TwoTenants,
    registry_count,
    rows_visible_to,
    transactional_guard_failure,
)
from rms.tenancy.tests.probe.models import ProbeChild, ProbeParent


def fake_item(
    marker: Any = None, fixturenames: tuple[str, ...] = (), cls: type | None = None
) -> Any:
    return SimpleNamespace(
        nodeid="fake::test",
        fixturenames=fixturenames,
        cls=cls,
        get_closest_marker=lambda name: marker if name == "django_db" else None,
    )


def mark(*args: Any, **kwargs: Any) -> Any:
    return pytest.mark.django_db(*args, **kwargs).mark


class _TransactionalWithoutMigrator(TransactionTestCase):
    databases = {"default"}  # noqa: RUF012
    __test__ = False  # an input to the guard, not a test


class _TransactionalWithMigrator(TransactionTestCase):
    databases = {"default", "migrator"}  # noqa: RUF012
    __test__ = False


class _PlainTestCase(TestCase):
    databases = {"default"}  # noqa: RUF012
    __test__ = False


GUARD_CASES: dict[str, tuple[Any, bool]] = {
    "transaction=True, default only": (fake_item(mark(transaction=True)), True),
    "transaction positional": (fake_item(mark(True)), True),
    "transaction=True, explicit default": (
        fake_item(mark(transaction=True, databases=["default"])),
        True,
    ),
    "ISOLATION_DB": (fake_item(ISOLATION_DB.mark), False),
    "transaction=True, __all__": (fake_item(mark(transaction=True, databases="__all__")), False),
    "transactional_db fixture": (fake_item(fixturenames=("transactional_db",)), True),
    "live_server fixture": (fake_item(fixturenames=("live_server",)), True),
    "serialized rollback fixture": (
        fake_item(fixturenames=("django_db_serialized_rollback",)),
        True,
    ),
    "transactional_db with migrator mark": (
        fake_item(mark(databases=["default", "migrator"]), ("transactional_db",)),
        False,
    ),
    "TransactionTestCase without migrator": (
        fake_item(cls=_TransactionalWithoutMigrator),
        True,
    ),
    "TransactionTestCase with migrator": (fake_item(cls=_TransactionalWithMigrator), False),
    "TestCase": (fake_item(cls=_PlainTestCase), False),
    "non-transactional django_db": (fake_item(mark()), False),
    "no database": (fake_item(), False),
}


@pytest.mark.parametrize("case", sorted(GUARD_CASES))
def test_transactional_guard(case: str) -> None:
    item, should_fail = GUARD_CASES[case]
    failure = transactional_guard_failure(item)
    assert (failure is not None) is should_fail, failure
    if should_fail:
        assert "migrator" in str(failure)


@pytest.mark.django_db(databases=["default", "migrator"])
def test_two_tenants_refuses_a_test_transaction() -> None:
    with pytest.raises(AssertionError, match="ISOLATION_DB"):
        harness._require_committing_migrator()


@pytest.mark.django_db(databases=["default", "migrator"])
def test_existing_session_guards_still_pass() -> None:
    assert database_guard_failures() == []


# --- C-20(c): the proof pair (keep together, in this order) ----------------------

_committed: dict[str, uuid.UUID] = {}


@ISOLATION_DB
def test_proof_1_commits_tenant_rows(two_tenants: TwoTenants) -> None:
    with tenant_transaction(two_tenants.a.id):
        make_child()
    assert rows_visible_to(two_tenants.a.id, ProbeParent) == 1
    assert rows_visible_to(two_tenants.a.id, ProbeChild) == 1
    assert registry_count() == 2
    _committed["a"] = two_tenants.a.id


@ISOLATION_DB
def test_proof_2_rows_were_flushed() -> None:
    if "a" not in _committed:
        pytest.skip("runs only after test_proof_1_commits_tenant_rows in the same session")
    assert registry_count() == 0
    assert rows_visible_to(_committed["a"], ProbeParent) == 0
    assert rows_visible_to(_committed["a"], ProbeChild) == 0
