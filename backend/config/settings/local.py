"""Local development settings (``manage.py`` default)."""

from __future__ import annotations

from copy import deepcopy

from config import env

from .base import *

DEBUG = env.get_bool("DJANGO_DEBUG", default=False)
SECRET_KEY = env.require_str("DJANGO_SECRET_KEY")

# Loopback only: a mis-selected dev module cannot serve a real host (SC-04).
ALLOWED_HOSTS = env.restrict_to_local_hosts(
    "DJANGO_ALLOWED_HOSTS", env.get_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])
)
CSRF_TRUSTED_ORIGINS = env.get_list("DJANGO_CSRF_TRUSTED_ORIGINS")

CSRF_COOKIE_NAME = "rms_csrf"
SESSION_COOKIE_NAME = "rms_session"  # reserved for 0005

# Migrations and test-DB creation only (R16: local/CI hold both credentials).
DATABASES["migrator"] = {
    **deepcopy(DATABASES["default"]),
    "USER": env.require_str("DB_MIGRATOR_USER"),
    "PASSWORD": env.require_str("DB_MIGRATOR_PASSWORD"),
}
