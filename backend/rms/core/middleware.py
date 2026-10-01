"""Cross-cutting middleware: request ID and API security headers."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import cast

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseBase
from django.utils.log import log_response

from rms.core.context import request_id_var

REQUEST_ID_HEADER = "X-Request-ID"

GetResponse = Callable[[HttpRequest], HttpResponseBase]


class RequestIDMiddleware:
    """Outermost middleware. Generates a UUID4 per request, server-side.

    An inbound ``X-Request-ID`` is ignored (log forging, T3-17) until a trusted
    proxy exists. The ID is held in a contextvar for logs and the error
    envelope, and always reset in ``finally`` (SC-18).
    """

    def __init__(self, get_response: GetResponse) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        request_id = str(uuid.uuid4())
        token = request_id_var.set(request_id)
        try:
            response = self.get_response(request)
            response[REQUEST_ID_HEADER] = request_id
            # Django logs 4xx/5xx after the middleware chain returns, which is
            # outside this context. Log here instead so the line has the ID;
            # log_response marks the response so Django does not log it again.
            if response.status_code >= 400:
                log_response(
                    "%s: %s",
                    response.reason_phrase,
                    request.path,
                    # Only status_code/reason_phrase are read; any response type works.
                    response=cast(HttpResponse, response),
                    request=request,
                )
            return response
        finally:
            request_id_var.reset(token)


class ApiSecurityHeadersMiddleware:
    """Security headers on every backend response, error responses included.

    Sets the headers directly rather than relying on the order of Django's own
    middleware, because an exception raised inside an inner middleware (for
    example ``DisallowedHost``) skips that middleware's response processing.
    """

    CSP = "default-src 'none'; frame-ancestors 'none'"

    def __init__(self, get_response: GetResponse) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        response = self.get_response(request)
        response["Cache-Control"] = "no-store"
        response["Content-Security-Policy"] = self.CSP
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = settings.X_FRAME_OPTIONS
        response["Referrer-Policy"] = settings.SECURE_REFERRER_POLICY
        return response
