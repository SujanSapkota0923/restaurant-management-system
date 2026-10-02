"""Test-only tenant views (SC-14). Mounted only through ``probe.urls`` with
``@pytest.mark.urls``; the route scan fails if one reaches config/urls.py.

``ProbeClosedView`` keeps the closed default hook (always 404).
``ProbeWriteView`` opens ``check_principal``, which only a test package may do
(C-5), so the D2 rollback matrix can reach a handler that writes.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.db import DatabaseError, connection, transaction
from django.http import StreamingHttpResponse
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response

from rms.core.context import tenant_id_var
from rms.tenancy.api.views import TenantAPIView
from rms.tenancy.data.context import current_tenant_id
from rms.tenancy.domain.errors import TenantContextMissing
from rms.tenancy.services.resolution import ResolvedTenant
from rms.tenancy.tests.probe.models import ProbeParent

# What the "on-commit" outcome's callback saw (read by test_views.py).
ON_COMMIT_SEEN: list[dict[str, Any]] = []


def _record_on_commit() -> None:
    try:
        current_tenant_id()
        tenant = "active"
    except TenantContextMissing:
        tenant = "missing"
    ON_COMMIT_SEEN.append({"tenant": tenant, "log_tenant_id": tenant_id_var.get()})


class AllowProbe(BasePermission):
    """Test-only stand-in until 0006 adds permission codes."""

    def has_permission(self, request: Request, view: Any) -> bool:
        return True


class ProbeClosedView(TenantAPIView):
    authentication_classes = []  # noqa: RUF012
    permission_classes = [AllowProbe]  # noqa: RUF012

    def get(self, request: Request, tenant_id: uuid.UUID) -> Response:
        return Response({"reached": True})

    def post(self, request: Request, tenant_id: uuid.UUID) -> Response:
        return Response({"reached": True, "keys": sorted(request.data)})


class ProbeWriteView(TenantAPIView):
    """Writes one ProbeParent, then ends with the outcome named in the path."""

    authentication_classes = []  # noqa: RUF012
    permission_classes = [AllowProbe]  # noqa: RUF012

    def check_principal(self, request: Request, tenant: ResolvedTenant) -> None:  # type: ignore[misc]
        # Test-only open hook (allowed in .tests. packages, C-5(b)).
        return None

    def post(self, request: Request, tenant_id: uuid.UUID, outcome: str) -> Any:
        ProbeParent(code=str(request.data.get("code", "probe"))).save()
        if outcome == "validation":
            raise ValidationError({"code": ["Rejected after the write."]})
        if outcome == "not-found":
            raise NotFound()
        if outcome == "permission":
            raise PermissionDenied()
        if outcome == "conflict":
            return Response({"conflict": True}, status=409)
        if outcome == "crash":
            raise RuntimeError("probe crash after the write")
        if outcome == "swallow":
            try:
                with transaction.atomic(savepoint=False), connection.cursor() as cursor:
                    cursor.execute("SELECT 1 / 0")
            except DatabaseError:
                pass  # deliberately swallowed: the view must still not return 2xx
            return Response({"swallowed": True})
        if outcome == "stream":
            return StreamingHttpResponse(iter([b"streamed"]))
        if outcome == "on-commit":
            transaction.on_commit(_record_on_commit, using="default")
        return Response(
            {"id": str(ProbeParent.objects.get(code=request.data.get("code")).id)}, status=201
        )
