"""Test-only views. Mounted only through ``rms.core.tests.urls`` with
``@pytest.mark.urls`` (SC-14); the route scan fails if one reaches config/urls.py."""

from __future__ import annotations

from django.db import connection
from django.http import HttpRequest, JsonResponse
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

EXCEPTION_TEXT = "boom-exception-text-CANARY"
# A transaction-local setting: the probe's "write", visible only if committed.
ROLLBACK_PROBE = "rms.rollback_probe"


def raising_view(request: HttpRequest) -> JsonResponse:
    raise RuntimeError(EXCEPTION_TEXT)


def csrf_probe(request: HttpRequest) -> JsonResponse:
    """A plain Django view (not DRF, so not csrf_exempt): real CSRF checks apply."""
    return JsonResponse({"ok": True})


class _Open(APIView):
    authentication_classes = []  # noqa: RUF012
    permission_classes = [AllowAny]  # noqa: RUF012


class DrfRaisingView(_Open):
    def get(self, request: Request) -> Response:
        raise RuntimeError(EXCEPTION_TEXT)


class ParseView(_Open):
    def post(self, request: Request) -> Response:
        return Response({"keys": sorted(request.data)})


class ValidationView(_Open):
    def post(self, request: Request) -> Response:
        raise ValidationError({"name": ["This field is required."]})


class UndeclaredView(APIView):
    """Declares no permission: the DenyAll default applies."""

    def get(self, request: Request) -> Response:
        return Response({"reached": True})


class RollbackProbeView(_Open):
    """Writes transaction-local state, then succeeds or raises a handled 4xx."""

    def post(self, request: Request, outcome: str) -> Response:
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config(%s, %s, true)", [ROLLBACK_PROBE, "written"])
        if outcome == "validation":
            raise ValidationError({"name": ["This field is required."]})
        if outcome == "not-found":
            raise NotFound()
        return Response({"ok": True})
