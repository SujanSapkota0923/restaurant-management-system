"""Test settings (pytest ``--ds``).

Tests connect as the app role (C3-7). The ``migrator`` alias creates and
migrates the test DB from the template; ``default`` mirrors it, which copies
only ``NAME`` (verified in Django 5.2.17), so ``default`` keeps the app role's
credentials. ``conftest.py`` always sets up both aliases and aborts the run if
the session guards fail (SC-25).
"""

from __future__ import annotations

import secrets
from copy import deepcopy

from django.core.exceptions import ImproperlyConfigured

from config import env

from .base import *

DEBUG = False
# From the env file when present, otherwise per process. Never a literal (SC-02).
SECRET_KEY = env.get_str("DJANGO_SECRET_KEY") or secrets.token_urlsafe(64)

ALLOWED_HOSTS = [
    *env.restrict_to_local_hosts(
        "DJANGO_ALLOWED_HOSTS", env.get_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])
    ),
    "testserver",
]

CSRF_COOKIE_NAME = "rms_csrf"
SESSION_COOKIE_NAME = "rms_session"

TEST_DB_NAME = "test_rms"
TEST_DB_TEMPLATE = "rms_template"
_LOCAL_DB_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

# The runner drops a same-named test DB without asking: never point it at a
# non-local server, and never at the dev DB (SC-25c).
if DATABASES["default"]["HOST"] not in _LOCAL_DB_HOSTS:
    raise ImproperlyConfigured("DB_HOST must be a loopback address for the test settings")
# TEST_DB_NAME is a constant with the test_ prefix; DB_NAME comes from the env.
if DATABASES["default"]["NAME"] == TEST_DB_NAME:
    raise ImproperlyConfigured("the test DB name must differ from DB_NAME")

DATABASES["migrator"] = {
    **deepcopy(DATABASES["default"]),
    "USER": env.require_str("DB_MIGRATOR_USER"),
    "PASSWORD": env.require_str("DB_MIGRATOR_PASSWORD"),
    # DEPENDENCIES=[]: Django otherwise makes a non-default alias depend on
    # "default", which is a mirror here and is never created.
    "TEST": {"NAME": TEST_DB_NAME, "TEMPLATE": TEST_DB_TEMPLATE, "DEPENDENCIES": []},
}
DATABASES["default"]["TEST"] = {"MIRROR": "migrator"}
