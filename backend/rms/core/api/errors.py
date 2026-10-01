"""The standard API error envelope (``docs/conventions/api.md``).

Every error response, from DRF views and from Django itself (400, 403, 404,
500, CSRF failure), uses this envelope. ``message`` is a static string per
``code`` (SC-13): never the request path, method, parser detail, exception text
or CSRF reason. ``fields`` is used only for validation errors.
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404, HttpRequest, JsonResponse
from rest_framework import exceptions as drf_exceptions
from rest_framework.response import Response
from rest_framework.views import set_rollback

from rms.core.context import request_id_var

logger = logging.getLogger("rms.core.errors")

MESSAGES: dict[str, str] = {
    "bad_request": "The request could not be processed.",
    "parse_error": "The request body could not be parsed.",
    "validation_error": "The submitted data is not valid.",
    "not_authenticated": "Authentication is required.",
    "permission_denied": "You do not have permission to perform this action.",
    "csrf_failed": "The request could not be verified. Reload the page and try again.",
    "not_found": "The requested resource was not found.",
    "method_not_allowed": "This method is not allowed for this resource.",
    "not_acceptable": "The requested response format is not available.",
    "unsupported_media_type": "The request content type is not supported.",
    "throttled": "Too many requests. Try again later.",
    "server_error": "An unexpected error occurred.",
    "not_ready": "The service is not ready.",
}

# DRF exception class -> envelope code. Order matters: subclasses first.
_DRF_CODES: tuple[tuple[type[drf_exceptions.APIException], str], ...] = (
    (drf_exceptions.ValidationError, "validation_error"),
    (drf_exceptions.ParseError, "parse_error"),
    (drf_exceptions.NotAuthenticated, "not_authenticated"),
    (drf_exceptions.AuthenticationFailed, "not_authenticated"),
    (drf_exceptions.PermissionDenied, "permission_denied"),
    (drf_exceptions.NotFound, "not_found"),
    (drf_exceptions.MethodNotAllowed, "method_not_allowed"),
    (drf_exceptions.NotAcceptable, "not_acceptable"),
    (drf_exceptions.UnsupportedMediaType, "unsupported_media_type"),
    (drf_exceptions.Throttled, "throttled"),
)

# Fallback for APIException subclasses not listed above.
_STATUS_CODES: dict[int, str] = {
    400: "bad_request",
    401: "not_authenticated",
    403: "permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    406: "not_acceptable",
    415: "unsupported_media_type",
    429: "throttled",
}


def envelope(code: str, fields: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "code": code,
        "message": MESSAGES[code],
        "request_id": request_id_var.get(),
    }
    if fields:
        body["fields"] = fields
    return {"error": body}


def error_response(status: int, code: str) -> JsonResponse:
    """A plain Django JSON response with the envelope (for non-DRF paths)."""
    return JsonResponse(envelope(code), status=status)


def _validation_fields(detail: Any) -> dict[str, Any]:
    if isinstance(detail, dict):
        return {str(key): value for key, value in detail.items()}
    return {"non_field_errors": detail if isinstance(detail, list) else [detail]}


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """DRF ``EXCEPTION_HANDLER``. Unknown exceptions return ``None`` -> Django 500.

    A handled exception becomes a normal response, so the request transaction
    (``ATOMIC_REQUESTS``) would commit any partial write. ``set_rollback()``
    marks it for rollback, as DRF's own handler does.
    """
    if isinstance(exc, Http404):
        exc = drf_exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = drf_exceptions.PermissionDenied()
    if not isinstance(exc, drf_exceptions.APIException):
        return None

    code = next((c for cls, c in _DRF_CODES if isinstance(exc, cls)), None)
    if code is None:
        code = _STATUS_CODES.get(
            exc.status_code, "bad_request" if exc.status_code < 500 else "server_error"
        )
    fields = _validation_fields(exc.detail) if code == "validation_error" else None

    headers: dict[str, str] = {}
    auth_header = getattr(exc, "auth_header", None)
    if auth_header:
        headers["WWW-Authenticate"] = auth_header
    wait = getattr(exc, "wait", None)
    if wait:
        headers["Retry-After"] = str(int(wait))
    set_rollback()
    return Response(envelope(code, fields), status=exc.status_code, headers=headers)


# Django handlers (wired in config/urls.py as handler400/403/404/500).
def bad_request(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    return error_response(400, "bad_request")


def permission_denied(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    return error_response(403, "permission_denied")


def page_not_found(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    return error_response(404, "not_found")


def server_error(request: HttpRequest) -> JsonResponse:
    return error_response(500, "server_error")


def csrf_failure(request: HttpRequest, reason: str = "") -> JsonResponse:
    """``CSRF_FAILURE_VIEW``. The reason is logged by Django (WARNING), never returned."""
    return error_response(403, "csrf_failed")
