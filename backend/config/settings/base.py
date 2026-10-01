"""Shared, secure-by-default settings. Never used directly: import a concrete
module (``local``, ``test``, ``production``).

No value here is a secret and nothing has a secret default (SC-02). Values come
from environment variables through ``config.env``; bad values stop startup.
"""

from __future__ import annotations

from pathlib import Path

from config import env
from rms.core.logging import build_logging_config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Overridden by each concrete module; base never defaults to debug.
DEBUG = False

INSTALLED_APPS = [
    "rest_framework",
    "rms.core",
]

MIDDLEWARE = [
    "rms.core.middleware.RequestIDMiddleware",
    "rms.core.middleware.ApiSecurityHeadersMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES: list[dict[str, object]] = []

DATABASES: dict[str, dict[str, object]] = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": env.require_str("DB_HOST"),
        "PORT": env.require_int("DB_PORT"),
        "NAME": env.require_str("DB_NAME"),
        "USER": env.require_str("DB_APP_USER"),
        "PASSWORD": env.require_str("DB_APP_PASSWORD"),
        # No persistent connections until the C3-2 reuse test exists (0004).
        "CONN_MAX_AGE": 0,
        # Bounded connect time: an unreachable DB must not hang workers (SC-10).
        "OPTIONS": {"connect_timeout": 5},
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

APPEND_SLASH = False

# Headers and cookies.
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
CSRF_COOKIE_HTTPONLY = False  # the SPA reads it and sends X-CSRFToken (api.md)
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_PATH = "/"
CSRF_COOKIE_DOMAIN = None
CSRF_FAILURE_VIEW = "rms.core.api.errors.csrf_failure"
CSRF_TRUSTED_ORIGINS: list[str] = []
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_PATH = "/"
SESSION_COOKIE_DOMAIN = None
USE_X_FORWARDED_HOST = False
USE_X_FORWARDED_PORT = False

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    # No authentication until 0005; no contrib.auth, so no AnonymousUser.
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "UNAUTHENTICATED_TOKEN": None,
    "DEFAULT_PERMISSION_CLASSES": ["rms.core.api.permissions.DenyAll"],
    "DEFAULT_THROTTLE_CLASSES": [],
    "EXCEPTION_HANDLER": "rms.core.api.errors.exception_handler",
}

LOG_LEVEL = env.get_choice(
    "LOG_LEVEL", ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"), default="INFO"
)
LOGGING = build_logging_config(LOG_LEVEL)
