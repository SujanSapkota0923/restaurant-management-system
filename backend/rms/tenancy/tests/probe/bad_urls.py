"""Self-test URLconf for the tenant route scan (C-5(c), N-02): every route here
breaks one rule and must be flagged."""

from typing import Any

from django.urls import path
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from rms.tenancy.tests.probe import views


class OpenTenantView(views.ProbeClosedView):
    permission_classes = [AllowAny]  # noqa: RUF012


class PlainView(APIView):
    permission_classes = [views.AllowProbe]  # noqa: RUF012

    def get(self, request: Request, **kwargs: Any) -> Response:
        return Response({})


urlpatterns = [
    # A str converter accepts any tenant value.
    path("api/v1/r/<str:tenant_id>/bad/str", views.ProbeClosedView.as_view()),
    # A TenantAPIView routed without a tenant.
    path("api/v1/bad/no-tenant", views.ProbeClosedView.as_view()),
    # A tenant route outside the api/v1/r/ prefix.
    path("v2/<uuid:tenant_id>/bad/prefix", views.ProbeClosedView.as_view()),
    # A tenant route whose view is not a TenantAPIView.
    path("api/v1/r/<uuid:tenant_id>/bad/plain", PlainView.as_view()),
    # A tenant route that declares AllowAny.
    path("api/v1/r/<uuid:tenant_id>/bad/open", OpenTenantView.as_view()),
]
