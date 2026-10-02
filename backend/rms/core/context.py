"""Per-request context for logs.

Set with ``var.set(...)`` and always restored with ``var.reset(token)`` in a
``finally`` block (SC-18), so a worker thread never carries one request's IDs
into the next request or into out-of-request logs. ``tenant_id`` is set
by the tenant view entry point (change 0004) inside the tenant transaction;
``membership_id`` stays ``None`` until change 0005.
"""

from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("rms_request_id", default=None)
tenant_id_var: ContextVar[str | None] = ContextVar("rms_tenant_id", default=None)
membership_id_var: ContextVar[str | None] = ContextVar("rms_membership_id", default=None)
