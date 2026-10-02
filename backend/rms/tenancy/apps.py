from django.apps import AppConfig


class TenancyConfig(AppConfig):
    """Bounded context ``tenancy``: the tenant registry, tenant context, RLS
    migration operations and tenant resolution (change 0004)."""

    name = "rms.tenancy"
    label = "tenancy"
