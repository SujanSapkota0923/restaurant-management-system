"""Tenant resolution (ADR-0006 C6-1/C6-2, change 0004 6.6).

Runs inside the tenant transaction for the path tenant. Under that context the
registry policy shows at most that one row, so a tenant that does not exist and
one that exists but is not active take the same single query and both give
``None``. The view turns ``None`` into the uniform 404.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from rms.tenancy.data.context import current_tenant_id
from rms.tenancy.data.models import Restaurant, RestaurantStatus
from rms.tenancy.domain.errors import TenantMismatch


@dataclass(frozen=True)
class ResolvedTenant:
    """The active tenant of the current request. Carries no other registry data."""

    id: uuid.UUID
    status: str


def resolve_active_tenant(tenant_id: uuid.UUID) -> ResolvedTenant | None:
    """The tenant if it exists and is active, else ``None``. One query."""
    if current_tenant_id() != tenant_id:
        raise TenantMismatch("resolution must run in the path tenant's transaction")
    rows = list(Restaurant.objects.filter(pk=tenant_id).values("id", "status")[:1])
    if not rows or rows[0]["status"] != RestaurantStatus.ACTIVE:
        return None
    return ResolvedTenant(id=rows[0]["id"], status=rows[0]["status"])
