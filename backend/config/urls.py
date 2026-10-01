"""Root URLconf. No Django admin is mounted (criterion 3).

Every route must be either in the route-scan ``PUBLIC_ROUTES`` allow-list (with
a threat-model entry) or a view that declares a non-``AllowAny`` permission
(SC-11, ``config/tests/test_routes.py``). Test-only views never go here (SC-14).
"""

from django.urls import path

from rms.core.health import LiveView, ReadyView

urlpatterns = [
    path("health/live", LiveView.as_view(), name="health-live"),
    path("health/ready", ReadyView.as_view(), name="health-ready"),
]

handler400 = "rms.core.api.errors.bad_request"
handler403 = "rms.core.api.errors.permission_denied"
handler404 = "rms.core.api.errors.page_not_found"
handler500 = "rms.core.api.errors.server_error"
