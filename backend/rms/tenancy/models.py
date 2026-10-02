"""Django model discovery for the tenancy app; the models live in ``data.models``."""

from rms.tenancy.data.models import Restaurant, TenantOwnedModel

__all__ = ["Restaurant", "TenantOwnedModel"]
