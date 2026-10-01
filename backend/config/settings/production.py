"""Production settings (``wsgi.py`` default, so a misconfigured deploy fails closed).

Must end with ``validate_production(globals())`` (SC-07). There is no
``migrator`` alias: migration-job settings arrive with 0004 (C3-6).
"""

from __future__ import annotations

from config import env
from config.validation import validate_production

from .base import *

DEBUG = False
SECRET_KEY = env.require_str("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.get_list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.get_list("DJANGO_CSRF_TRUSTED_ORIGINS")

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_NAME = "__Host-rms_session"
CSRF_COOKIE_NAME = "__Host-rms_csrf"

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# HSTS preload is a separate decision (change 0003, 6.2); silence only that check.
SECURE_HSTS_PRELOAD = False
SILENCED_SYSTEM_CHECKS = ["security.W021"]

# Only behind a proxy that overwrites this header (operations.md, SC-06).
SECURE_PROXY_SSL_HEADER = env.get_proxy_ssl_header("DJANGO_SECURE_PROXY_SSL_HEADER")

validate_production(globals())
