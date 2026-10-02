"""Tenant registry and the tenant-owned base model (change 0004, 6.2, 6.4, C-7, C-10).

``Restaurant`` is the platform-level registry (no ``tenant_id``). The app role
reads only ``id``, ``name`` and ``status`` (column grants), and only the row of
the current tenant (RLS policy ``restaurant_tenant_read``). Writes happen only
through the migrator (migrations, test fixtures); there is no product write path
in 0004.

``TenantOwnedModel`` is the base of every tenant-owned table. Its only manager,
``TenantManager``, is both the default and the base manager. It raises
``TenantContextMissing`` outside ``tenant_transaction`` and filters by the
active tenant (layer 2); RLS is layer 3. Rules for subclasses are in
``docs/conventions/backend.md`` ("Tenant-owned models").
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Any, ClassVar, NoReturn, TypeVar, cast

from django.core.exceptions import FieldError
from django.db import NotSupportedError, models
from django.db.models.functions import Trim
from django.db.models.lookups import Exact

from rms.tenancy.data.context import current_tenant_id
from rms.tenancy.domain.errors import TenantMismatch


class RestaurantStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    CLOSED = "closed", "Closed"


# The columns the app role may read (C3-1a). Anything else is "permission denied".
REGISTRY_READABLE_FIELDS = ("id", "name", "status")
# OQ1: technical placeholder until the operator-console change confirms it.
RESTAURANT_NAME_MAX_LENGTH = 200


class RestaurantManager(models.Manager["Restaurant"]):
    """Selects only the granted columns, so app-role reads (and FK traversal,
    which uses the base manager) never touch an ungranted column."""

    def get_queryset(self) -> models.QuerySet[Restaurant]:
        return super().get_queryset().only(*REGISTRY_READABLE_FIELDS)


class Restaurant(models.Model):
    """The tenants registry. One row per restaurant (tenant)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=RESTAURANT_NAME_MAX_LENGTH)
    status = models.CharField(
        max_length=16,
        choices=RestaurantStatus.choices,
        default=RestaurantStatus.ACTIVE,
        db_default=RestaurantStatus.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = RestaurantManager()

    class Meta:
        db_table = "tenancy_restaurant"
        base_manager_name = "objects"
        default_manager_name = "objects"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(status__in=RestaurantStatus.values),
                name="tenancy_restaurant_status_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(Exact(Trim("name"), "")),
                name="tenancy_restaurant_name_not_blank",
            ),
        ]

    def __str__(self) -> str:
        return str(self.id)


# Bound to Model, not TenantOwnedModel: a forward-referenced bound crashes the
# django-stubs plugin. Tenant keys are read through the two helpers below.
_T = TypeVar("_T", bound=models.Model)

# Never written by the app (C3-9, C-7(c), C-7(d)).
_IMMUTABLE_FIELDS = frozenset({"id", "pk", "tenant", "tenant_id"})


def _tenant_of(obj: models.Model) -> Any:
    return getattr(obj, "tenant_id", None)


def _claim(obj: models.Model, tenant_id: uuid.UUID, message: str) -> None:
    """Fill an unset tenant key from the context; refuse another tenant."""
    current = _tenant_of(obj)
    if current is None:
        obj.tenant_id = tenant_id  # type: ignore[attr-defined]
    elif current != tenant_id:
        raise TenantMismatch(message)


def _reject_immutable(fields: Iterable[str]) -> None:
    if _IMMUTABLE_FIELDS.intersection(fields):
        raise FieldError("id and tenant are immutable on tenant-owned models")


class TenantQuerySet(models.QuerySet[_T]):
    """Querysets of tenant-owned models. Only ever created by ``TenantManager``."""

    def raw(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NotSupportedError("raw() is not available on tenant-owned models")

    def extra(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NotSupportedError("extra() is not available on tenant-owned models")

    def bulk_create(self, objs: Iterable[_T], *args: Any, **kwargs: Any) -> list[_T]:
        tenant_id = current_tenant_id()
        _reject_immutable(kwargs.get("update_fields") or ())
        objs = list(objs)
        for obj in objs:
            _claim(obj, tenant_id, "bulk_create() names another tenant")
        return super().bulk_create(objs, *args, **kwargs)

    def update(self, **kwargs: Any) -> int:
        _reject_immutable(kwargs)
        return super().update(**kwargs)

    def bulk_update(
        self, objs: Iterable[_T], fields: Iterable[str], batch_size: int | None = None
    ) -> int:
        tenant_id = current_tenant_id()
        fields = list(fields)
        _reject_immutable(fields)
        objs = list(objs)
        if any(_tenant_of(obj) != tenant_id for obj in objs):
            raise TenantMismatch("bulk_update() names another tenant")
        return super().bulk_update(objs, fields, batch_size=batch_size)


class TenantManager(models.Manager[_T]):
    """The only manager of a tenant-owned model; also its base manager.

    ``get_queryset()`` raises ``TenantContextMissing`` outside
    ``tenant_transaction``, so reads, writes, related access in both directions,
    ``refresh_from_db`` and ``save()`` updates all fail closed without context.
    Historical models in migrations get a plain manager instead
    (``use_in_migrations = False``) and stay bound by FORCE RLS.
    """

    use_in_migrations = False
    _queryset_class = TenantQuerySet

    def get_queryset(self) -> TenantQuerySet[_T]:
        tenant_id = current_tenant_id()
        queryset = cast(TenantQuerySet[_T], super().get_queryset())
        return queryset.filter(tenant_id=tenant_id)


class TenantOwnedModel(models.Model):
    """Abstract base of every tenant-owned table.

    The table also needs, in the same migration as its ``CreateModel``:
    ``enable_tenant_rls``, ``restrict_tenant_key_update`` and, for every FK to
    another tenant-owned model, ``composite_tenant_fk`` (``rms.tenancy.data.rls``).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Restaurant,
        on_delete=models.PROTECT,
        db_column="tenant_id",
        editable=False,
        db_index=False,
        related_name="+",
    )

    objects = TenantManager()

    class Meta:
        abstract = True
        base_manager_name = "objects"
        default_manager_name = "objects"
        # Parent key for composite FKs; also the tenant-leading index.
        # Subclasses that declare constraints must keep this one:
        # ``constraints = [*TenantOwnedModel.Meta.constraints, ...]``.
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["tenant", "id"], name="%(app_label)s_%(class)s_tenant_id_uniq"
            )
        ]

    def save(
        self,
        *,
        force_insert: bool | tuple[models.base.ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        tenant_id = current_tenant_id()
        if self._state.adding:
            _claim(self, tenant_id, "the new row names another tenant")
        else:
            if self.tenant_id != tenant_id:
                raise TenantMismatch("the row belongs to another tenant")
            if update_fields is None:
                # The app role has no UPDATE on tenant_id or id (C3-9).
                update_fields = [
                    field.name
                    for field in self._meta.concrete_fields
                    if not field.primary_key and field.name != "tenant"
                ]
            else:
                update_fields = list(update_fields)
                _reject_immutable(update_fields)
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def delete(
        self, using: str | None = None, keep_parents: bool = False
    ) -> tuple[int, dict[str, int]]:
        if self.tenant_id != current_tenant_id():
            raise TenantMismatch("the row belongs to another tenant")
        return super().delete(using=using, keep_parents=keep_parents)
