"""``tenant_transaction`` / ``identity_transaction`` (C3-2, C3-4, C-1; N-04, N-05).

Context-sensitive tests are transactional (C-2). The TestCase-mode tests at the
end prove C-1(d): inside a test transaction the durable block is only a
savepoint, and the setting must still be gone after the block.
"""

from __future__ import annotations

import contextvars
import threading
import uuid
from typing import Any

import pytest
from django.db import connections, transaction
from django.db.transaction import TransactionManagementError

from rms.core.context import tenant_id_var
from rms.tenancy.data import context
from rms.tenancy.data.context import (
    current_tenant_id,
    current_user_id,
    identity_transaction,
    tenant_transaction,
)
from rms.tenancy.domain.errors import TenantContextActive, TenantContextMissing
from rms.tenancy.tests.factories import make_parent
from rms.tenancy.tests.harness import (
    ISOLATION_DB,
    TwoTenants,
    current_setting,
    raw_count,
    rows_visible_to,
)
from rms.tenancy.tests.probe.models import ProbeParent


def backend_pid() -> int:
    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid()")
        row = cursor.fetchone()
    assert row is not None
    return int(row[0])


class UUIDSubclass(uuid.UUID):
    pass


# --- N-05: arguments and nesting -------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [str(uuid.uuid4()), None, UUIDSubclass(int=1), 1, uuid.uuid4().bytes],
    ids=["str", "none", "uuid-subclass", "int", "bytes"],
)
@pytest.mark.parametrize(
    "entry", [tenant_transaction, identity_transaction], ids=["tenant", "user"]
)
def test_non_uuid_arguments_raise_before_any_sql(entry: Any, value: Any) -> None:
    # No django_db mark: any SQL (or even a connection) would raise RuntimeError
    # here, so a TypeError proves the check runs before the database is touched.
    with pytest.raises(TypeError), entry(value):
        pass  # pragma: no cover


@ISOLATION_DB
@pytest.mark.parametrize(
    ("outer", "inner"),
    [
        ("tenant-a", "tenant-a"),
        ("tenant-a", "tenant-b"),
        ("tenant-a", "identity"),
        ("identity", "tenant-a"),
        ("identity", "identity"),
    ],
)
def test_nesting_and_plane_mixing_raise(outer: str, inner: str) -> None:
    a, b, user = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    entries = {
        "tenant-a": lambda: tenant_transaction(a),
        "tenant-b": lambda: tenant_transaction(b),
        "identity": lambda: identity_transaction(user),
    }
    with entries[outer]():
        with pytest.raises(TenantContextActive), entries[inner]():
            pass  # pragma: no cover
        # The outer context is intact after the refused nesting.
        expected = a if outer.startswith("tenant") else user
        name = "app.tenant_id" if outer.startswith("tenant") else "app.user_id"
        assert current_setting(name) == str(expected)


@ISOLATION_DB
def test_entry_inside_a_non_test_atomic_raises() -> None:
    with (
        transaction.atomic(),
        pytest.raises(TransactionManagementError),
        tenant_transaction(uuid.uuid4()),
    ):
        pass  # pragma: no cover


@ISOLATION_DB
def test_entry_with_autocommit_off_raises() -> None:
    connection = connections["default"]
    connection.set_autocommit(False)
    try:
        with pytest.raises(TransactionManagementError), tenant_transaction(uuid.uuid4()):
            pass  # pragma: no cover
    finally:
        connection.rollback()
        connection.set_autocommit(True)


# --- C3-2 / N-04: no context leaks -----------------------------------------------


@ISOLATION_DB
def test_reused_connection_carries_no_tenant_context(two_tenants: TwoTenants) -> None:
    """C3-2: after a committed A block, the same connection has no context."""
    a = two_tenants.a.id
    with tenant_transaction(a):
        make_parent()
        pid = backend_pid()
        assert current_setting("app.tenant_id") == str(a)
        assert raw_count(ProbeParent) == 1  # positive control under A
    assert backend_pid() == pid  # the same server connection was reused
    assert current_setting("app.tenant_id") in ("", None)
    assert raw_count(ProbeParent) == 0
    assert rows_visible_to(a, ProbeParent) == 1  # the row was committed


@ISOLATION_DB
def test_reused_connection_carries_no_user_context() -> None:
    user = uuid.uuid4()
    with identity_transaction(user):
        pid = backend_pid()
        assert current_setting("app.user_id") == str(user)
        assert current_user_id() == user
    assert backend_pid() == pid
    assert current_setting("app.user_id") in ("", None)
    with pytest.raises(TenantContextMissing):
        current_user_id()


@ISOLATION_DB
def test_rolled_back_block_carries_no_context(two_tenants: TwoTenants) -> None:
    with pytest.raises(RuntimeError), tenant_transaction(two_tenants.a.id):
        assert raw_count(ProbeParent) == 0
        raise RuntimeError("abort")
    assert current_setting("app.tenant_id") in ("", None)
    with pytest.raises(TenantContextMissing):
        current_tenant_id()


@ISOLATION_DB
def test_on_commit_callback_runs_without_context(two_tenants: TwoTenants) -> None:
    seen: dict[str, Any] = {}

    def callback() -> None:
        try:
            ProbeParent.objects.count()
        except TenantContextMissing:
            seen["manager"] = "raised"
        seen["raw"] = raw_count(ProbeParent)
        seen["setting"] = current_setting("app.tenant_id")

    with tenant_transaction(two_tenants.a.id):
        make_parent()
        transaction.on_commit(callback, using="default")
        assert raw_count(ProbeParent) == 1  # positive control
    assert seen == {"manager": "raised", "raw": 0, "setting": ""}


@ISOLATION_DB
def test_copied_context_in_another_thread_has_no_tenant(two_tenants: TwoTenants) -> None:
    results: dict[str, str] = {}

    def worker() -> None:
        for name, call in (("current", current_tenant_id), ("manager", ProbeParent.objects.count)):
            try:
                call()
                results[name] = "no error"
            except TenantContextMissing:
                results[name] = "missing"
        connections.close_all()

    with tenant_transaction(two_tenants.a.id):
        assert current_tenant_id() == two_tenants.a.id
        copied = contextvars.copy_context()
        thread = threading.Thread(target=copied.run, args=(worker,))
        thread.start()
        thread.join(timeout=30)
    assert results == {"current": "missing", "manager": "missing"}


@ISOLATION_DB
def test_contextvar_is_reset_and_log_context_bound() -> None:
    tenant = uuid.uuid4()
    with tenant_transaction(tenant):
        assert current_tenant_id() == tenant
        assert tenant_id_var.get() == str(tenant)
    assert tenant_id_var.get() is None
    with pytest.raises(TenantContextMissing):
        current_tenant_id()
    with tenant_transaction(tenant, bind_log_context=False):
        assert tenant_id_var.get() is None


def test_current_tenant_id_outside_context_raises() -> None:
    with pytest.raises(TenantContextMissing):
        current_tenant_id()


# --- TestCase mode: the durable block is a savepoint (F1, C-1(d)) ----------------


@pytest.mark.django_db
def test_setting_is_cleared_after_exit_in_test_case_mode() -> None:
    tenant = uuid.uuid4()
    assert connections["default"].in_atomic_block  # inside the test transaction
    with tenant_transaction(tenant):
        assert current_setting("app.tenant_id") == str(tenant)
    assert current_setting("app.tenant_id") == ""
    # A second block is not refused: nothing leaked.
    with tenant_transaction(uuid.uuid4()):
        pass


@pytest.mark.django_db
def test_planted_leak_makes_entry_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    """C-1(b): with the C-1(d) clear disabled, the savepoint leaks the setting
    (F1). The next entry must detect it, independently of the clear."""
    monkeypatch.setitem(context._CLEAR_SQL, context.TENANT_SETTING, "SELECT 1")
    leaked = uuid.uuid4()
    with tenant_transaction(leaked):
        pass
    assert current_setting("app.tenant_id") == str(leaked)  # the planted leak
    with pytest.raises(TenantContextActive), tenant_transaction(uuid.uuid4()):
        pass  # pragma: no cover
    # The refused entry rolled back its own set_config: the leak is unchanged.
    assert current_setting("app.tenant_id") == str(leaked)


@pytest.mark.django_db
def test_planted_tenant_leak_blocks_identity_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    """C-1(f): the other plane's DB setting is checked too, not only the contextvar."""
    monkeypatch.setitem(context._CLEAR_SQL, context.TENANT_SETTING, "SELECT 1")
    with tenant_transaction(uuid.uuid4()):
        pass
    with pytest.raises(TenantContextActive), identity_transaction(uuid.uuid4()):
        pass  # pragma: no cover


# --- gate 8 additions (QA) ---------------------------------------------------------


@ISOLATION_DB
def test_commit_clears_the_setting_even_without_the_exit_clear(
    two_tenants: TwoTenants, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C3-2 holds on its own: the entry point's setting is transaction-local
    (is_local = true), so the commit resets it even if the C-1(d) clear never
    ran. A session-level setting would leak here."""
    monkeypatch.setitem(context._CLEAR_SQL, context.TENANT_SETTING, "SELECT 1")
    a = two_tenants.a.id
    with tenant_transaction(a):
        make_parent()
        pid = backend_pid()
        assert current_setting("app.tenant_id") == str(a)  # positive control
    assert backend_pid() == pid
    assert current_setting("app.tenant_id") in ("", None)
    assert raw_count(ProbeParent) == 0
    assert rows_visible_to(a, ProbeParent) == 1
    # Nothing leaked, so the next entry is not refused.
    with tenant_transaction(two_tenants.b.id):
        assert raw_count(ProbeParent) == 0


@ISOLATION_DB
def test_concurrent_tenant_transactions_stay_isolated(two_tenants: TwoTenants) -> None:
    """The race named in section 5.3: A and B open at the same time on two
    connections. Each sees only its own context and rows, while both
    transactions are open."""
    a, b = two_tenants.a.id, two_tenants.b.id
    with tenant_transaction(a):
        make_parent(code="a-only")
    with tenant_transaction(b):
        make_parent(code="b-one")
        make_parent(code="b-two")
    barrier = threading.Barrier(2, timeout=30)
    results: dict[str, tuple[Any, ...]] = {}
    errors: list[str] = []

    def worker(name: str, tenant: uuid.UUID) -> None:
        try:
            with tenant_transaction(tenant):
                barrier.wait()  # both transactions are open now
                seen = (
                    current_tenant_id(),
                    current_setting("app.tenant_id"),
                    sorted(ProbeParent.objects.values_list("code", flat=True)),
                    raw_count(ProbeParent),
                    backend_pid(),
                )
                barrier.wait()  # neither commits before both have read
            results[name] = seen
        except BaseException as exc:  # reported below; never hangs the other thread
            errors.append(f"{name}: {exc!r}")
            barrier.abort()
        finally:
            connections.close_all()

    threads = [
        threading.Thread(target=worker, args=("a", a)),
        threading.Thread(target=worker, args=("b", b)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert errors == []
    assert results["a"][:4] == (a, str(a), ["a-only"], 1)
    assert results["b"][:4] == (b, str(b), ["b-one", "b-two"], 2)
    assert results["a"][4] != results["b"][4]  # two server connections
    # The main thread never had a context.
    with pytest.raises(TenantContextMissing):
        current_tenant_id()


@ISOLATION_DB
def test_planted_session_level_leak_on_a_reused_connection_makes_entry_raise(
    two_tenants: TwoTenants,
) -> None:
    """R13 / C-1(b) in the production shape (real commits, reused connection):
    a session-level app.tenant_id set outside the entry point, for example by
    pooled-connection misuse, is detected at the next entry, and nothing is
    read under it."""
    a, b = two_tenants.a.id, two_tenants.b.id
    with tenant_transaction(b):
        make_parent()
    connection = connections["default"]
    # Built by concatenation so the C-3 source scan does not match this test file.
    plant = "SET " + "app.tenant_id = %s"
    try:
        with connection.cursor() as cursor:
            cursor.execute(plant.replace("%s", f"'{b}'"))  # constant UUID from the fixture
        assert current_setting("app.tenant_id") == str(b)  # the planted leak
        assert raw_count(ProbeParent) == 1  # positive control: the leak would expose B
        with pytest.raises(TenantContextActive), tenant_transaction(a):
            pass  # pragma: no cover
    finally:
        connection.close()  # a session-level setting must not survive this test
    assert current_setting("app.tenant_id") in ("", None)
    assert rows_visible_to(a, ProbeParent) == 0
    assert rows_visible_to(b, ProbeParent) == 1
