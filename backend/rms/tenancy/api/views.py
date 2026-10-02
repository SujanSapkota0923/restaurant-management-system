"""``TenantAPIView``: the base of every ``/api/v1/r/<uuid:tenant_id>/...`` view
(ADR-0006 C6-1/C6-2; change 0004 D1-D3, C-4, C-5, C-6).

``dispatch`` runs the whole DRF request cycle inside ``tenant_transaction`` for
the path tenant, which is taken only from ``self.kwargs["tenant_id"]`` (C-5(d)).
``initial`` then authenticates, resolves the tenant, checks the principal,
permissions and throttles, in that order. Every tenant failure is the same
``404 not_found`` and happens before any tenant-table access.

The response decides the transaction (D2, C-4):

- status >= 400: the transaction is rolled back;
- status < 400 while the transaction is marked for rollback: error (500);
- a streaming response: error (500), nothing may run outside the transaction;
- the response is rendered inside the transaction.

``check_principal`` is closed (always 404) until 0005/0006 add the membership
check in ``access``. ``dispatch``, ``initial``, ``resolve_active_tenant`` and
``check_principal`` are ``@final``; a test fails on any override outside test
packages and the reviewed allow-list (empty in 0004).
"""

from __future__ import annotations

import uuid
from contextvars import Token
from typing import Any, final

from django.core.exceptions import ImproperlyConfigured
from django.db import connections, transaction
from django.db.transaction import TransactionManagementError
from django.http import HttpRequest
from django.http.response import HttpResponseBase
from django.template.response import SimpleTemplateResponse
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.views import APIView

from rms.core.context import tenant_id_var
from rms.tenancy.data.context import DEFAULT_ALIAS, tenant_transaction
from rms.tenancy.services.resolution import ResolvedTenant
from rms.tenancy.services.resolution import resolve_active_tenant as resolve_tenant


class TenantAPIView(APIView):
    """Base view for the tenant plane. Subclasses declare ``permission_classes``."""

    tenant: ResolvedTenant
    _tenant_log_token: Token[str | None] | None = None

    @final
    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
        tenant_id = self.kwargs.get("tenant_id")
        if type(tenant_id) is not uuid.UUID:
            raise ImproperlyConfigured("a TenantAPIView must be routed with <uuid:tenant_id>")
        with tenant_transaction(tenant_id, bind_log_context=False):
            try:
                response = super().dispatch(request, *args, **kwargs)
                self._finish_in_transaction(response)
            finally:
                # Inside the block (C-1(c)): on_commit callbacks run without log context too.
                token, self._tenant_log_token = self._tenant_log_token, None
                if token is not None:
                    tenant_id_var.reset(token)
        return response

    @staticmethod
    def _finish_in_transaction(response: HttpResponseBase) -> None:
        if response.streaming:
            raise ImproperlyConfigured("tenant views must not return streaming responses")
        if response.status_code >= 400:
            transaction.set_rollback(True, using=DEFAULT_ALIAS)
        elif connections[DEFAULT_ALIAS].needs_rollback:
            raise TransactionManagementError("a success response for a rolled-back transaction")
        if isinstance(response, SimpleTemplateResponse) and not response.is_rendered:
            response.render()

    @final
    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        # DRF's APIView.initial, with tenant resolution and the principal check
        # between authentication and permissions.
        self.format_kwarg = self.get_format_suffix(**kwargs)
        neg = self.perform_content_negotiation(request)
        request.accepted_renderer, request.accepted_media_type = neg
        version, scheme = self.determine_version(request, *args, **kwargs)
        request.version, request.versioning_scheme = version, scheme

        self.perform_authentication(request)
        tenant = self.resolve_active_tenant(self.kwargs["tenant_id"])
        self.tenant = tenant
        # Log context only once the path tenant is known to be valid (C-1(g)).
        self._tenant_log_token = tenant_id_var.set(str(tenant.id))
        self.check_principal(request, tenant)
        self.check_permissions(request)
        self.check_throttles(request)

    @final
    def resolve_active_tenant(self, tenant_id: uuid.UUID) -> ResolvedTenant:
        tenant = resolve_tenant(tenant_id)
        if tenant is None:
            raise NotFound()
        return tenant

    @final
    def check_principal(self, request: Request, tenant: ResolvedTenant) -> None:
        """Membership (0005) or device-session (0006) check. Closed in 0004: always 404."""
        raise NotFound()
