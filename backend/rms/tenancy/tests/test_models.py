"""Model introspection (C-8): every concrete model is tenant-owned and follows
the tenant rules, or is on the platform allow-list."""

from __future__ import annotations

from typing import ClassVar

import pytest
from django.apps import apps
from django.db import connections, models
from django.test.utils import isolate_apps

from rms.tenancy.data.models import Restaurant, TenantManager, TenantOwnedModel

# Platform-level models (no tenant_id). Adding one is a security review item.
PLATFORM_MODELS: frozenset[type[models.Model]] = frozenset({Restaurant})


def tenant_model_problems(model: type[models.Model]) -> list[str]:
    name = model._meta.label
    problems: list[str] = []
    managers = model._meta.managers
    if len(managers) != 1 or not isinstance(managers[0], TenantManager):
        problems.append(f"{name}: must have exactly one manager, a TenantManager")
    if not isinstance(model._meta.base_manager, TenantManager):
        problems.append(f"{name}: the base manager must be the TenantManager")
    if not isinstance(model._meta.default_manager, TenantManager):
        problems.append(f"{name}: the default manager must be the TenantManager")
    for m2m in model._meta.many_to_many:
        through = getattr(m2m.remote_field, "through", None)
        if (
            isinstance(through, type)
            and issubclass(through, models.Model)
            and through._meta.auto_created
        ):
            problems.append(f"{name}.{m2m.name}: M2M with an auto-created through table")
    for field in model._meta.get_fields():
        related = getattr(field, "related_model", None)
        if not getattr(field, "concrete", False) or related is None:
            continue
        if related is Restaurant and field.name != "tenant":
            problems.append(f"{name}.{field.name}: only the tenant field may reference Restaurant")
        if (
            isinstance(related, type)
            and issubclass(related, TenantOwnedModel)
            and getattr(field, "db_constraint", True)
        ):
            problems.append(f"{name}.{field.name}: tenant FK must use db_constraint=False")
    if not any(
        isinstance(c, models.UniqueConstraint) and tuple(c.fields) == ("tenant", "id")
        for c in model._meta.constraints
    ):
        problems.append(f"{name}: missing UniqueConstraint(tenant, id)")
    return problems


def concrete_models() -> list[type[models.Model]]:
    return [m for m in apps.get_models() if not m._meta.abstract and not m._meta.proxy]


def test_every_concrete_model_is_tenant_owned_or_platform() -> None:
    other = [
        m._meta.label
        for m in concrete_models()
        if not issubclass(m, TenantOwnedModel) and m not in PLATFORM_MODELS
    ]
    assert other == []


def test_tenant_models_follow_the_rules() -> None:
    tenant_models = [m for m in concrete_models() if issubclass(m, TenantOwnedModel)]
    assert {m._meta.label for m in tenant_models} == {
        "tenancy_probe.ProbeParent",
        "tenancy_probe.ProbeChild",
    }
    assert [p for m in tenant_models for p in tenant_model_problems(m)] == []


@pytest.mark.django_db
def test_every_tenant_fk_has_its_composite_constraint() -> None:
    missing: list[str] = []
    for model in concrete_models():
        if not issubclass(model, TenantOwnedModel):
            continue
        for field in model._meta.concrete_fields:
            related = field.related_model
            if not (isinstance(related, type) and issubclass(related, TenantOwnedModel)):
                continue
            with connections["default"].cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM pg_constraint con"
                    " WHERE con.contype = 'f' AND con.conrelid = %s::regclass"
                    " AND con.confrelid = %s::regclass"
                    " AND con.conkey = ARRAY[(SELECT attnum FROM pg_attribute"
                    "   WHERE attrelid = con.conrelid AND attname = 'tenant_id'),"
                    "  (SELECT attnum FROM pg_attribute"
                    "   WHERE attrelid = con.conrelid AND attname = %s)]::int2[]"
                    " AND con.confkey = ARRAY[(SELECT attnum FROM pg_attribute"
                    "   WHERE attrelid = con.confrelid AND attname = 'tenant_id'),"
                    "  (SELECT attnum FROM pg_attribute"
                    "   WHERE attrelid = con.confrelid AND attname = 'id')]::int2[]",
                    [model._meta.db_table, related._meta.db_table, field.column],
                )
                row = cursor.fetchone()
            if not row or row[0] != 1:
                missing.append(f"{model._meta.label}.{field.name}")
    assert missing == []


@isolate_apps("rms.tenancy.tests.probe")
def test_introspection_flags_a_bad_model() -> None:
    """Self-test: a second manager, a constrained tenant FK, an auto M2M and an
    extra Restaurant FK are all reported."""

    class Good(TenantOwnedModel):
        class Meta(TenantOwnedModel.Meta):
            app_label = "tenancy_probe"

    class Bad(TenantOwnedModel):
        unscoped = models.Manager()
        good = models.ForeignKey(Good, on_delete=models.PROTECT)
        others = models.ManyToManyField(Good, related_name="+")
        home = models.ForeignKey(Restaurant, on_delete=models.PROTECT, related_name="+")

        class Meta:
            app_label = "tenancy_probe"
            constraints: ClassVar[list[models.BaseConstraint]] = []

    problems = "\n".join(tenant_model_problems(Bad))
    assert tenant_model_problems(Good) == []
    for expected in (
        "exactly one manager",
        "Bad.good: tenant FK must use db_constraint=False",
        "Bad.others: M2M with an auto-created through table",
        "Bad.home: only the tenant field may reference Restaurant",
        "missing UniqueConstraint(tenant, id)",
    ):
        assert expected in problems
