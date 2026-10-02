"""Errors of the tenancy context (change 0004).

They signal programming errors, not client errors: none is mapped to an API
response, so one that escapes a view becomes the generic ``500 server_error``.
Client-facing tenant failures are always the uniform ``404 not_found``.
"""

from __future__ import annotations


class TenantContextError(RuntimeError):
    """Base class for misuse of the tenant (or identity) context."""


class TenantContextMissing(TenantContextError):  # noqa: N818 - name fixed by the 0004 design
    """Tenant-owned data was accessed outside an active ``tenant_transaction``.

    Also raised by ``current_user_id()`` outside an ``identity_transaction``.
    """


class TenantContextActive(TenantContextError):  # noqa: N818 - name fixed by the 0004 design
    """A context entry point was entered while a context is already set.

    Covers nesting (a tenant inside a tenant, or a tenant switched mid-transaction),
    mixing the tenant and identity planes, and a setting leaked into the
    connection from an earlier transaction (C-1(b), C-1(f)).
    """


class TenantMismatch(TenantContextError):  # noqa: N818 - named like its siblings
    """A write names a tenant other than the active one (C-7(b), C-7(d))."""
