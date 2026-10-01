"""Liveness and readiness endpoints.

Public by explicit declaration (threat-modelled in change 0003, T3-09/T3-10;
listed in the route-scan ``PUBLIC_ROUTES``). Fixed bodies: no version, commit,
host name or error detail. Not rate-limited until Phase 10 (R25, accepted).
"""

from __future__ import annotations

import logging

from django.db import connections
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from rms.core.api.errors import envelope

logger = logging.getLogger("rms.core.health")

OK_BODY = {"status": "ok"}


class _HealthView(APIView):
    authentication_classes = []  # noqa: RUF012 - DRF declares these as class lists
    permission_classes = [AllowAny]  # noqa: RUF012
    # No OPTIONS: DRF's metadata response would describe the view.
    http_method_names = ["get", "head"]  # noqa: RUF012


class LiveView(_HealthView):
    def get(self, request: Request) -> Response:
        return Response(OK_BODY)


class ReadyView(_HealthView):
    def get(self, request: Request) -> Response:
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception as exc:
            # The exception class only: DB error text can carry host names.
            logger.warning("readiness check failed", extra={"error_class": type(exc).__name__})
            return Response(envelope("not_ready"), status=503)
        return Response(OK_BODY)
