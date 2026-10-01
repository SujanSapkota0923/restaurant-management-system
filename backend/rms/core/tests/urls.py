"""Test URLconf: the real routes plus test-only views (SC-14)."""

from django.urls import path

from config.urls import handler400, handler403, handler404, handler500
from config.urls import urlpatterns as root_urlpatterns
from rms.core.tests import views

__all__ = ["handler400", "handler403", "handler404", "handler500", "urlpatterns"]

urlpatterns = [
    *root_urlpatterns,
    path("t/raise", views.raising_view),
    path("t/drf-raise", views.DrfRaisingView.as_view()),
    path("t/parse", views.ParseView.as_view()),
    path("t/validation", views.ValidationView.as_view()),
    path("t/undeclared", views.UndeclaredView.as_view()),
    path("t/csrf", views.csrf_probe),
    path("t/rollback/<outcome>", views.RollbackProbeView.as_view()),
]
