"""Database settings that the tenancy design depends on (change 0004, D1, D6, C-11, C-18; N-16).

Settings modules are imported in a clean subprocess with a fake environment, as
in ``test_validation.py``: no value from the real env file reaches the child.
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from django.conf import settings
from django.db import connections

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROBE_APP = "rms.tenancy.tests.probe"
GOOD_KEY = "k" + secrets.token_urlsafe(64)

_DUMP = (
    "import importlib, json, sys\n"
    "m = importlib.import_module(sys.argv[1])\n"
    "print(json.dumps({'databases': sorted(m.DATABASES), 'apps': m.INSTALLED_APPS,"
    " 'role': getattr(m, 'RMS_DB_APP_ROLE', None)}))\n"
)


def fake_env(*, without: tuple[str, ...] = (), **extra: str) -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "DB_HOST": "127.0.0.1",
        "DB_PORT": "5432",
        "DB_NAME": "rms",
        "DB_APP_USER": "rms_app",
        "DB_APP_PASSWORD": "fake-app-password-for-import-test",
        "DB_MIGRATOR_USER": "rms_migrator",
        "DB_MIGRATOR_PASSWORD": "fake-migrator-password-for-import-test",
        "DJANGO_SECRET_KEY": GOOD_KEY,
        **extra,
    }
    for name in without:
        env.pop(name, None)
    return env


def dump(module: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", _DUMP, module],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def production_env(**extra: str) -> dict[str, str]:
    return fake_env(
        without=("DB_MIGRATOR_USER", "DB_MIGRATOR_PASSWORD"),
        DJANGO_ALLOWED_HOSTS="rms.example.test",
        DJANGO_CSRF_TRUSTED_ORIGINS="https://rms.example.test",
        **extra,
    )


def test_atomic_requests_is_off_on_every_alias() -> None:
    """D1: the tenant transaction is explicit; ATOMIC_REQUESTS would open one
    before the tenant is known and break the durable entry point."""
    for alias, config in settings.DATABASES.items():
        assert config.get("ATOMIC_REQUESTS", False) is False, alias
        assert connections[alias].settings_dict["ATOMIC_REQUESTS"] is False, alias


def test_no_libpq_options_and_no_persistent_connections() -> None:
    for alias, config in settings.DATABASES.items():
        options: Any = config.get("OPTIONS") or {}
        # libpq "options" could set a context setting for every session (C-18, T4-04).
        assert "options" not in options, alias
        assert config["CONN_MAX_AGE"] == 0, alias


def test_app_role_setting_is_the_app_user() -> None:
    assert settings.DATABASES["default"]["USER"] == settings.RMS_DB_APP_ROLE


def test_test_settings_install_the_probe_app() -> None:
    assert PROBE_APP in list(settings.INSTALLED_APPS)


def test_production_has_only_the_default_alias_and_no_probe() -> None:
    result = dump("config.settings.production", production_env())
    assert result.returncode == 0, result.stderr[-2000:]
    values = json.loads(result.stdout)
    assert values["databases"] == ["default"]
    assert PROBE_APP not in values["apps"]
    assert values["role"] == "rms_app"


def test_production_settings_never_read_migrator_variables() -> None:
    for name in ("base.py", "production.py"):
        text = (BACKEND_DIR / "config" / "settings" / name).read_text()
        assert "DB_MIGRATOR" not in text, name
        assert '"migrator"' not in text, name


def test_local_settings_do_not_install_the_probe_app() -> None:
    result = dump("config.settings.local", fake_env())
    assert result.returncode == 0, result.stderr[-2000:]
    values = json.loads(result.stdout)
    assert PROBE_APP not in values["apps"]
    assert "rms.tenancy" in values["apps"]


@pytest.mark.parametrize("module", ["config.settings.local", "config.settings.test"])
def test_unset_app_user_refuses_to_start(module: str) -> None:
    """C-11(a): no default for the role the grants go to."""
    result = dump(module, fake_env(without=("DB_APP_USER",)))
    assert result.returncode != 0
    assert "DB_APP_USER must be set" in result.stderr
