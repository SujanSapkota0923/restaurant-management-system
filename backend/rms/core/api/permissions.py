"""DRF permission classes shared by every context."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rest_framework.permissions import BasePermission

if TYPE_CHECKING:
    # Type-only: rest_framework.views imports DEFAULT_PERMISSION_CLASSES at load.
    from rest_framework.request import Request
    from rest_framework.views import APIView


class DenyAll(BasePermission):
    """The DRF default (``DEFAULT_PERMISSION_CLASSES``): a view that declares no
    permission is forbidden. Default deny (`authorization.md`)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return False

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        return False
