"""Per-request context for logs.

Set with ``var.set(...)`` and always restored with ``var.reset(token)`` in a
``finally`` block (SC-18), so a worker thread never carries one request's IDs
into the next request or into out-of-request logs. ``tenant_id`` and
``membership_id`` are reserved here for changes 0004/0005 and stay ``None``.
"""

from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("rms_request_id", default=None)
tenant_id_var: ContextVar[str | None] = ContextVar("rms_tenant_id", default=None)
membership_id_var: ContextVar[str | None] = ContextVar("rms_membership_id", default=None)
