"""Two tenant-owned probe tables: a parent with a per-tenant natural key and a
child with a composite tenant FK to it. They follow every rule a real
tenant-owned table must follow (``docs/conventions/backend.md``)."""

from __future__ import annotations

from typing import ClassVar

from django.db import models

from rms.tenancy.data.models import TenantOwnedModel


class ProbeParent(TenantOwnedModel):
    code = models.CharField(max_length=32)

    class Meta(TenantOwnedModel.Meta):
        constraints: ClassVar[list[models.BaseConstraint]] = [
            *TenantOwnedModel.Meta.constraints,
            # Per-tenant uniqueness leads with the tenant (TM-17).
            models.UniqueConstraint(
                fields=["tenant", "code"], name="probe_parent_tenant_code_uniq"
            ),
        ]

    def __str__(self) -> str:
        return self.code


class ProbeChild(TenantOwnedModel):
    # db_constraint=False: the only DB constraint is the composite tenant FK
    # added in the migration (D5); the (tenant, parent) index serves it.
    parent = models.ForeignKey(
        ProbeParent,
        on_delete=models.PROTECT,
        db_constraint=False,
        db_index=False,
        related_name="children",
    )
    label = models.CharField(max_length=32, default="child")

    class Meta(TenantOwnedModel.Meta):
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["tenant", "parent"], name="probe_child_tenant_parent_idx"),
        ]

    def __str__(self) -> str:
        return self.label
