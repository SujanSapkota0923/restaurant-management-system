"""Test URLconf: the real routes plus the tenant probe views (SC-14)."""

from django.urls import path

from config.urls import handler400, handler403, handler404, handler500
from config.urls import urlpatterns as root_urlpatterns
from rms.tenancy.tests.probe import views

__all__ = ["handler400", "handler403", "handler404", "handler500", "urlpatterns"]

urlpatterns = [
    *root_urlpatterns,
    path("api/v1/r/<uuid:tenant_id>/probe/closed", views.ProbeClosedView.as_view()),
    path("api/v1/r/<uuid:tenant_id>/probe/write/<str:outcome>", views.ProbeWriteView.as_view()),
]
