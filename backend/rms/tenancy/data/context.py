"""The single tenant-transaction entry point (ADR-0003 C3-2, C3-4; change 0004 D1, C-1).

``tenant_transaction(tenant_id)`` is the only runtime path that puts a tenant
into the database context. ``identity_transaction(user_id)`` does the same for
the identity plane (its policies arrive in 0005). This module and
``rms/tenancy/data/rls.py`` are the only files allowed to write ``app.*``
settings; a source scan enforces that (C-3).

How a block runs:

1. Preconditions, before any SQL (C-1(a)): the argument is exactly a
   ``uuid.UUID``; no tenant or identity context is active in this context; the
   ``default`` connection is in autocommit, or every enclosing atomic block was
   opened by a Django test case.
2. A durable ``atomic`` on ``default`` (outermost: Django refuses to nest it).
3. One statement reads both planes' previous values and sets the new one,
   transaction-local, with the UUID bound as a parameter (C3-2, C-1(b)). A
   non-empty previous value is a leak and raises ``TenantContextActive``.
4. The contextvar is set only after that statement succeeded and is reset in a
   ``finally`` *inside* the atomic block (C-1(c)), so ``on_commit`` callbacks
   and code after the block run without context.
5. On a normal exit the setting is cleared while still inside the block
   (C-1(d)). In a test case the block is only a savepoint, and a
   transaction-local setting survives ``RELEASE SAVEPOINT`` (change 0004 F1).
   When the block is marked for rollback the clear is skipped: the rollback
   restores the previous value.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from django.db import connections, transaction
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.transaction import Atomic, TransactionManagementError

from rms.core.context import tenant_id_var
from rms.tenancy.domain.errors import TenantContextActive, TenantContextMissing

DEFAULT_ALIAS = "default"
TENANT_SETTING = "app.tenant_id"
USER_SETTING = "app.user_id"


@dataclass(frozen=True)
class _ActiveContext:
    value: uuid.UUID
    atomic: Atomic


_active_tenant: ContextVar[_ActiveContext | None] = ContextVar("rms_active_tenant", default=None)
_active_user: ContextVar[_ActiveContext | None] = ContextVar("rms_active_user", default=None)

# Static SQL only. Each entry statement returns (own previous value, other
# plane's value) and then sets its own setting; the value is always bound.
_ENTER_SQL = {
    TENANT_SETTING: (
        "SELECT current_setting('app.tenant_id', true), current_setting('app.user_id', true),"
        " set_config('app.tenant_id', %s, true)"
    ),
    USER_SETTING: (
        "SELECT current_setting('app.user_id', true), current_setting('app.tenant_id', true),"
        " set_config('app.user_id', %s, true)"
    ),
}
_CLEAR_SQL = {
    TENANT_SETTING: "SELECT set_config('app.tenant_id', '', true)",
    USER_SETTING: "SELECT set_config('app.user_id', '', true)",
}


def _require_uuid(value: object) -> uuid.UUID:
    # Exactly UUID: a str, None or a subclass (which could override __str__) is refused.
    if type(value) is not uuid.UUID:
        raise TypeError("the context entry point needs a uuid.UUID instance")
    return value


def _require_outermost(connection: BaseDatabaseWrapper) -> None:
    blocks = connection.atomic_blocks
    if blocks:
        if not all(getattr(block, "_from_testcase", False) for block in blocks):
            raise TransactionManagementError(
                "the context entry point must open the outermost transaction"
            )
    elif not connection.get_autocommit():
        raise TransactionManagementError("the context entry point needs autocommit to be on")


@contextmanager
def _context_transaction(
    setting: str,
    value: uuid.UUID,
    own: ContextVar[_ActiveContext | None],
    other: ContextVar[_ActiveContext | None],
    bind_log_context: bool,
) -> Iterator[None]:
    if own.get() is not None or other.get() is not None:
        raise TenantContextActive("a tenant or identity context is already active")
    connection = connections[DEFAULT_ALIAS]
    _require_outermost(connection)
    atomic = transaction.atomic(using=DEFAULT_ALIAS, durable=True)
    with atomic:
        with connection.cursor() as cursor:
            cursor.execute(_ENTER_SQL[setting], [str(value)])
            row = cursor.fetchone()
        previous, other_value = (row[0], row[1]) if row else (None, None)
        if previous or other_value:
            # Raised inside the block: the rollback undoes the new value too.
            raise TenantContextActive("a context setting leaked into this connection")
        token = own.set(_ActiveContext(value, atomic))
        log_token = tenant_id_var.set(str(value)) if bind_log_context else None
        try:
            yield
            if not connection.needs_rollback:
                with connection.cursor() as cursor:
                    cursor.execute(_CLEAR_SQL[setting])
        finally:
            if log_token is not None:
                tenant_id_var.reset(log_token)
            own.reset(token)


@contextmanager
def tenant_transaction(tenant_id: uuid.UUID, *, bind_log_context: bool = True) -> Iterator[None]:
    """Run the block in one transaction with ``app.tenant_id`` set to ``tenant_id``.

    ``bind_log_context=False`` leaves the log context unset; ``TenantAPIView``
    binds it only after the tenant was resolved (C-1(g)).
    """
    _require_uuid(tenant_id)
    with _context_transaction(
        TENANT_SETTING, tenant_id, _active_tenant, _active_user, bind_log_context
    ):
        yield


@contextmanager
def identity_transaction(user_id: uuid.UUID) -> Iterator[None]:
    """Run the block in one transaction with ``app.user_id`` set (identity plane, C3-1a).

    Never combined with a tenant context. Its policies arrive with 0005.
    """
    _require_uuid(user_id)
    with _context_transaction(USER_SETTING, user_id, _active_user, _active_tenant, False):
        yield


def _current(var: ContextVar[_ActiveContext | None], message: str) -> uuid.UUID:
    active = var.get()
    if active is None:
        raise TenantContextMissing(message)
    connection = connections[DEFAULT_ALIAS]
    # The block that set the context must still be open on *this* thread's
    # connection (C-1(e)); a copied contextvar in another thread fails here.
    if not connection.in_atomic_block or not any(
        block is active.atomic for block in connection.atomic_blocks
    ):
        raise TenantContextMissing(message)
    return active.value


def current_tenant_id() -> uuid.UUID:
    """The active tenant; raises ``TenantContextMissing`` outside ``tenant_transaction``."""
    return _current(_active_tenant, "no active tenant transaction")


def current_user_id() -> uuid.UUID:
    """The active identity-plane user; raises outside ``identity_transaction``."""
    return _current(_active_user, "no active identity transaction")
