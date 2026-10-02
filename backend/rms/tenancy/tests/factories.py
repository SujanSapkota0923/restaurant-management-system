"""factory_boy factories for the tenancy harness (change 0004, 6.8).

``RestaurantFactory`` writes through the migrator (the app role cannot insert
into the registry). The probe factories write through the app role and must be
called inside ``tenant_transaction``: their manager fails closed otherwise.
Values are deterministic sequences; no Faker data.

factory_boy is untyped: tests call the typed ``make_*`` functions.
"""

from __future__ import annotations

from typing import Any

import factory
from factory.django import DjangoModelFactory

from rms.tenancy.data.models import Restaurant, RestaurantStatus
from rms.tenancy.tests.probe.models import ProbeChild, ProbeParent


class RestaurantFactory(DjangoModelFactory[Restaurant]):
    class Meta:
        model = Restaurant
        database = "migrator"

    name = factory.Sequence(lambda n: f"Restaurant {n}")
    status = RestaurantStatus.ACTIVE


class ProbeParentFactory(DjangoModelFactory[ProbeParent]):
    class Meta:
        model = ProbeParent

    code = factory.Sequence(lambda n: f"P{n:04d}")


class ProbeChildFactory(DjangoModelFactory[ProbeChild]):
    class Meta:
        model = ProbeChild

    parent = factory.SubFactory(ProbeParentFactory)
    label = factory.Sequence(lambda n: f"C{n:04d}")


def make_restaurant(**kwargs: Any) -> Restaurant:
    """A committed registry row (in a transactional test), created by the migrator."""
    return RestaurantFactory.create(**kwargs)


def make_parent(**kwargs: Any) -> ProbeParent:
    """A ProbeParent of the active tenant. Needs ``tenant_transaction``."""
    return ProbeParentFactory.create(**kwargs)


def make_child(**kwargs: Any) -> ProbeChild:
    """A ProbeChild (and its parent, unless given) of the active tenant."""
    return ProbeChildFactory.create(**kwargs)
