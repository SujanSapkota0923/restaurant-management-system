"""validate_production rules 1-12 (6.2 + SC-05) and settings-module startup.

NT3-01 (no values in messages), NT3-02, NT3-04, NT3-05, NT3-07 (subprocess part),
NT3-25 (test settings refuse a non-local DB host).
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
from django.core.exceptions import ImproperlyConfigured

from config.validation import validate_production

BACKEND_DIR = Path(__file__).resolve().parents[2]
CANARY = "CanarySecretValue-7c41e2"
GOOD_KEY = "k" + secrets.token_urlsafe(64)


def baseline() -> dict[str, Any]:
    """A configuration that passes every rule."""
    return {
        "DEBUG": False,
        "SECRET_KEY": GOOD_KEY,
        "SECRET_KEY_FALLBACKS": [],
        "ALLOWED_HOSTS": ["rms.example.test"],
        "CSRF_TRUSTED_ORIGINS": ["https://rms.example.test"],
        "SESSION_COOKIE_SECURE": True,
        "CSRF_COOKIE_SECURE": True,
        "SECURE_HSTS_SECONDS": 31_536_000,
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "CSRF_COOKIE_SAMESITE": "Strict",
        "SESSION_COOKIE_NAME": "__Host-rms_session",
        "CSRF_COOKIE_NAME": "__Host-rms_csrf",
        "SESSION_COOKIE_DOMAIN": None,
        "CSRF_COOKIE_DOMAIN": None,
        "SESSION_COOKIE_PATH": "/",
        "CSRF_COOKIE_PATH": "/",
        "SECURE_SSL_REDIRECT": True,
        "SECURE_CONTENT_TYPE_NOSNIFF": True,
        "X_FRAME_OPTIONS": "DENY",
        "USE_X_FORWARDED_HOST": False,
        "USE_X_FORWARDED_PORT": False,
    }


@pytest.fixture(autouse=True)
def _no_debug_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DJANGO_DEBUG", raising=False)


def failure_message(**overrides: Any) -> str:
    with pytest.raises(ImproperlyConfigured) as exc:
        validate_production(baseline() | overrides)
    return str(exc.value)


def test_baseline_passes() -> None:
    validate_production(baseline())


# One failing case per rule. Each case maps to the setting named in the message.
FAILING_CASES: list[tuple[str, dict[str, Any], str]] = [
    ("1-debug", {"DEBUG": True}, "DEBUG must be false"),
    ("2-missing", {"SECRET_KEY": ""}, "SECRET_KEY must be set"),
    ("2-short", {"SECRET_KEY": "a1b2c3d4e5" * 4}, "SECRET_KEY"),
    ("2-few-unique", {"SECRET_KEY": "abcd" * 20}, "SECRET_KEY"),
    ("2-insecure-prefix", {"SECRET_KEY": "django-insecure-" + GOOD_KEY}, "SECRET_KEY"),
    ("2-placeholder", {"SECRET_KEY": GOOD_KEY + "change-me"}, "SECRET_KEY"),
    ("3-empty", {"ALLOWED_HOSTS": []}, "ALLOWED_HOSTS"),
    ("3-wildcard", {"ALLOWED_HOSTS": ["*"]}, "ALLOWED_HOSTS"),
    ("3-subdomain-wildcard", {"ALLOWED_HOSTS": [".example.test"]}, "ALLOWED_HOSTS"),
    ("3-partial-wildcard", {"ALLOWED_HOSTS": ["*.example.test"]}, "ALLOWED_HOSTS"),
    (
        "4-cors-all",
        {"CORS_ALLOW_ALL_ORIGINS": True, "CORS_ALLOW_CREDENTIALS": True},
        "CORS",
    ),
    (
        "4-cors-star",
        {"CORS_ALLOWED_ORIGINS": ["*"], "CORS_ALLOW_CREDENTIALS": True},
        "CORS",
    ),
    ("5-http-origin", {"CSRF_TRUSTED_ORIGINS": ["http://rms.example.test"]}, "https://"),
    ("5-wildcard-origin", {"CSRF_TRUSTED_ORIGINS": ["https://*.example.test"]}, "wildcard"),
    ("6-session-insecure", {"SESSION_COOKIE_SECURE": False}, "SESSION_COOKIE_SECURE"),
    ("6-csrf-insecure", {"CSRF_COOKIE_SECURE": False}, "CSRF_COOKIE_SECURE"),
    ("6-hsts-short", {"SECURE_HSTS_SECONDS": 3600}, "SECURE_HSTS_SECONDS"),
    ("6-hsts-missing", {"SECURE_HSTS_SECONDS": None}, "SECURE_HSTS_SECONDS"),
    ("7-httponly", {"SESSION_COOKIE_HTTPONLY": False}, "SESSION_COOKIE_HTTPONLY"),
    ("7-samesite-none", {"SESSION_COOKIE_SAMESITE": "None"}, "SAMESITE"),
    ("7-samesite-false", {"CSRF_COOKIE_SAMESITE": False}, "SAMESITE"),
    ("8-session-prefix", {"SESSION_COOKIE_NAME": "rms_session"}, "SESSION_COOKIE_NAME"),
    ("8-csrf-prefix", {"CSRF_COOKIE_NAME": "__Secure-rms_csrf"}, "CSRF_COOKIE_NAME"),
    ("8-domain", {"SESSION_COOKIE_DOMAIN": "example.test"}, "SESSION_COOKIE_DOMAIN"),
    ("8-csrf-domain", {"CSRF_COOKIE_DOMAIN": ".example.test"}, "CSRF_COOKIE_DOMAIN"),
    ("8-path", {"CSRF_COOKIE_PATH": "/api"}, "CSRF_COOKIE_PATH"),
    ("8-session-path", {"SESSION_COOKIE_PATH": "/api"}, "SESSION_COOKIE_PATH"),
    ("9-ssl-redirect", {"SECURE_SSL_REDIRECT": False}, "SECURE_SSL_REDIRECT"),
    ("9-nosniff", {"SECURE_CONTENT_TYPE_NOSNIFF": False}, "SECURE_CONTENT_TYPE_NOSNIFF"),
    ("9-xfo", {"X_FRAME_OPTIONS": "SAMEORIGIN"}, "X_FRAME_OPTIONS"),
    ("10-forwarded-host", {"USE_X_FORWARDED_HOST": True}, "USE_X_FORWARDED_HOST"),
    ("10-forwarded-port", {"USE_X_FORWARDED_PORT": True}, "USE_X_FORWARDED_PORT"),
    (
        "11-foreign-origin",
        {"CSRF_TRUSTED_ORIGINS": ["https://other.example.test"]},
        "ALLOWED_HOSTS",
    ),
    (
        "11-origin-path",
        {"CSRF_TRUSTED_ORIGINS": ["https://rms.example.test/app"]},
        "no path",
    ),
    ("12-weak-fallback", {"SECRET_KEY_FALLBACKS": ["short-old-key"]}, "SECRET_KEY_FALLBACKS"),
]


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [(o, e) for _, o, e in FAILING_CASES],
    ids=[case_id for case_id, _, _ in FAILING_CASES],
)
def test_rule_fails(overrides: dict[str, Any], expected: str) -> None:
    assert expected in failure_message(**overrides)


def test_debug_env_var_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_DEBUG", "true")
    assert "DJANGO_DEBUG must be false" in failure_message()


def test_malformed_debug_env_var_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_DEBUG", CANARY)
    message = failure_message()
    assert "DJANGO_DEBUG" in message
    assert CANARY not in message


def test_all_failures_are_collected() -> None:
    message = failure_message(DEBUG=True, ALLOWED_HOSTS=["*"], SECURE_SSL_REDIRECT=False)
    assert "DEBUG" in message
    assert "ALLOWED_HOSTS" in message
    assert "SECURE_SSL_REDIRECT" in message


@pytest.mark.parametrize(
    "overrides",
    [
        {"SECRET_KEY": CANARY},
        {"SECRET_KEY_FALLBACKS": [CANARY]},
        {"ALLOWED_HOSTS": [f"*.{CANARY}"]},
        {"CSRF_TRUSTED_ORIGINS": [f"http://{CANARY}"]},
        {"SESSION_COOKIE_NAME": CANARY},
        {"CSRF_COOKIE_DOMAIN": CANARY},
        {"X_FRAME_OPTIONS": CANARY},
        # QA (gate 8): string-valued settings of rules 7, 8 and 11 as well.
        {"SESSION_COOKIE_SAMESITE": CANARY},
        {"CSRF_COOKIE_PATH": f"/{CANARY}"},
        {"CSRF_TRUSTED_ORIGINS": [f"https://rms.example.test/{CANARY}"]},
        {"CSRF_TRUSTED_ORIGINS": [f"https://{CANARY.lower()}.test"]},
    ],
)
def test_messages_never_contain_values(overrides: dict[str, Any]) -> None:
    assert CANARY not in failure_message(**overrides)
    assert CANARY.lower() not in failure_message(**overrides)


# --- settings modules, imported in a clean subprocess ----------------------------


def _settings_env(**extra: str) -> dict[str, str]:
    """A minimal fake environment: no value from the real env file reaches the child."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "DB_HOST": "127.0.0.1",
        "DB_PORT": "5432",
        "DB_NAME": "rms",
        "DB_APP_USER": "rms_app",
        "DB_APP_PASSWORD": "fake-app-password-for-import-test",
        "DB_MIGRATOR_USER": "rms_migrator",
        "DB_MIGRATOR_PASSWORD": "fake-migrator-password-for-import-test",
    }
    env.update(extra)
    return env


def _import_settings(module: str, **extra: str) -> subprocess.CompletedProcess[str]:
    code = (
        "import importlib, sys\n"
        f"m = importlib.import_module({module!r})\n"
        "print(m.CSRF_COOKIE_NAME, len(m.SECRET_KEY), m.DEBUG)\n"
    )
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_DIR,
        env=_settings_env(**extra),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _production_env(**extra: str) -> dict[str, str]:
    return {
        "DJANGO_SECRET_KEY": GOOD_KEY,
        "DJANGO_ALLOWED_HOSTS": "rms.example.test",
        "DJANGO_CSRF_TRUSTED_ORIGINS": "https://rms.example.test",
        **extra,
    }


def test_production_imports_with_good_env() -> None:
    result = _import_settings("config.settings.production", **_production_env())
    assert result.returncode == 0, result.stderr[-2000:]
    cookie_name, key_length, debug = result.stdout.split()
    assert cookie_name == "__Host-rms_csrf"  # frontend contract
    assert int(key_length) == len(GOOD_KEY)
    assert debug == "False"


@pytest.mark.parametrize(
    "extra",
    [
        {"DJANGO_DEBUG": "true"},
        {"DJANGO_ALLOWED_HOSTS": "*"},
        {"DJANGO_ALLOWED_HOSTS": " *"},
        {"DJANGO_ALLOWED_HOSTS": "rms.example.test,,other"},
        {"DJANGO_SECRET_KEY": CANARY},
        {"DJANGO_CSRF_TRUSTED_ORIGINS": f"https://{CANARY.lower()}.test"},
        {"DJANGO_SECURE_PROXY_SSL_HEADER": f"{CANARY}=https"},
    ],
    ids=["debug", "wildcard", "spaced-wildcard", "empty-entry", "weak-key", "origin", "proxy"],
)
def test_production_refuses_bad_env(extra: dict[str, str]) -> None:
    result = _import_settings("config.settings.production", **_production_env(**extra))
    assert result.returncode != 0
    assert "ImproperlyConfigured" in result.stderr
    assert CANARY not in result.stderr
    assert CANARY.lower() not in result.stderr


def test_production_requires_secret_key() -> None:
    env = _production_env()
    del env["DJANGO_SECRET_KEY"]
    result = _import_settings("config.settings.production", **env)
    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY must be set" in result.stderr


def test_local_requires_secret_key() -> None:
    result = _import_settings("config.settings.local")
    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY must be set" in result.stderr


def test_local_refuses_real_hostname() -> None:
    result = _import_settings(
        "config.settings.local", DJANGO_SECRET_KEY=GOOD_KEY, DJANGO_ALLOWED_HOSTS="example.com"
    )
    assert result.returncode != 0
    assert "DJANGO_ALLOWED_HOSTS may only contain" in result.stderr


def test_local_defaults_debug_off_and_dev_cookie() -> None:
    result = _import_settings("config.settings.local", DJANGO_SECRET_KEY=GOOD_KEY)
    assert result.returncode == 0, result.stderr[-2000:]
    cookie_name, _, debug = result.stdout.split()
    assert cookie_name == "rms_csrf"  # frontend contract
    assert debug == "False"


def test_test_settings_generate_a_key() -> None:
    result = _import_settings("config.settings.test")
    assert result.returncode == 0, result.stderr[-2000:]
    _, key_length, debug = result.stdout.split()
    assert int(key_length) >= 64
    assert debug == "False"


def test_test_settings_refuse_remote_db_host() -> None:
    result = _import_settings("config.settings.test", DB_HOST="db.example")
    assert result.returncode != 0
    assert "DB_HOST must be a loopback address" in result.stderr


def test_test_settings_refuse_dev_db_name() -> None:
    result = _import_settings("config.settings.test", DB_NAME="test_rms")
    assert result.returncode != 0
    assert "differ from DB_NAME" in result.stderr


def test_test_settings_refuse_real_hostname() -> None:
    result = _import_settings("config.settings.test", DJANGO_ALLOWED_HOSTS="rms.example.test")
    assert result.returncode != 0
    assert "DJANGO_ALLOWED_HOSTS may only contain" in result.stderr


def test_no_settings_module_contains_a_literal_secret() -> None:
    """SC-02: no secret key or password literal in any settings module."""
    for path in (BACKEND_DIR / "config" / "settings").glob("*.py"):
        text = path.read_text()
        assert 'SECRET_KEY = "' not in text, path.name
        assert 'PASSWORD": "' not in text, path.name
        assert "django-insecure" not in text, path.name


# --- QA (gate 8): production secure defaults and fail-closed entry points --------


def _run_python(code: str, *args: str, **extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args] if args else [sys.executable, "-c", code],
        cwd=BACKEND_DIR,
        env=_settings_env(**extra),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


_PRODUCTION_DEFAULTS = (
    "import importlib, json\n"
    "m = importlib.import_module('config.settings.production')\n"
    "names = ['SESSION_COOKIE_SECURE', 'CSRF_COOKIE_SECURE', 'SESSION_COOKIE_HTTPONLY',\n"
    "         'CSRF_COOKIE_HTTPONLY', 'SESSION_COOKIE_NAME', 'CSRF_COOKIE_NAME',\n"
    "         'SECURE_HSTS_SECONDS', 'SECURE_HSTS_INCLUDE_SUBDOMAINS', 'SECURE_HSTS_PRELOAD',\n"
    "         'SECURE_SSL_REDIRECT', 'SECURE_PROXY_SSL_HEADER', 'X_FRAME_OPTIONS',\n"
    "         'SECURE_CONTENT_TYPE_NOSNIFF', 'USE_X_FORWARDED_HOST', 'DEBUG', 'INSTALLED_APPS',\n"
    "         'SILENCED_SYSTEM_CHECKS']\n"
    "print(json.dumps({n: getattr(m, n) for n in names}))\n"
)


def test_production_secure_defaults() -> None:
    """Criterion 3: the values production actually ends up with, not the validator input."""
    result = _run_python(_PRODUCTION_DEFAULTS, **_production_env())
    assert result.returncode == 0, result.stderr[-2000:]
    values = json.loads(result.stdout)
    assert values == {
        "SESSION_COOKIE_SECURE": True,
        "CSRF_COOKIE_SECURE": True,
        "SESSION_COOKIE_HTTPONLY": True,
        "CSRF_COOKIE_HTTPONLY": False,  # the SPA reads it (api.md)
        "SESSION_COOKIE_NAME": "__Host-rms_session",
        "CSRF_COOKIE_NAME": "__Host-rms_csrf",
        "SECURE_HSTS_SECONDS": 31_536_000,
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": True,
        "SECURE_HSTS_PRELOAD": False,
        "SECURE_SSL_REDIRECT": True,
        "SECURE_PROXY_SSL_HEADER": None,  # only if configured
        "X_FRAME_OPTIONS": "DENY",
        "SECURE_CONTENT_TYPE_NOSNIFF": True,
        "USE_X_FORWARDED_HOST": False,
        "DEBUG": False,
        "INSTALLED_APPS": ["rest_framework", "rms.core"],  # no admin, auth, sessions
        "SILENCED_SYSTEM_CHECKS": ["security.W021"],  # HSTS preload only
    }


def test_production_proxy_header_only_when_configured() -> None:
    result = _run_python(
        _PRODUCTION_DEFAULTS,
        **_production_env(DJANGO_SECURE_PROXY_SSL_HEADER="HTTP_X_FORWARDED_PROTO=https"),
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert json.loads(result.stdout)["SECURE_PROXY_SSL_HEADER"] == [
        "HTTP_X_FORWARDED_PROTO",
        "https",
    ]


def test_production_ignores_debug_false_lookalikes() -> None:
    """T3-03 through the real module: a lenient value can never switch DEBUG on."""
    for value in ("no", "off", "False!", "yes"):
        result = _import_settings(
            "config.settings.production", **_production_env(DJANGO_DEBUG=value)
        )
        assert result.returncode != 0, value
        assert "DJANGO_DEBUG must be one of" in result.stderr


def test_wsgi_defaults_to_production_and_fails_closed() -> None:
    """T3-04: a deploy without DJANGO_SETTINGS_MODULE loads production validation,
    so dev-style values (no hosts, a dev secret) refuse to start."""
    result = _run_python("import config.wsgi", DJANGO_SECRET_KEY=GOOD_KEY)
    assert result.returncode != 0
    assert "ImproperlyConfigured" in result.stderr
    assert "ALLOWED_HOSTS must list explicit host names" in result.stderr


def test_wsgi_with_good_production_env_uses_production() -> None:
    result = _run_python(
        "import config.wsgi\nfrom django.conf import settings\nprint(settings.SETTINGS_MODULE)",
        **_production_env(),
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip() == "config.settings.production"


def test_manage_defaults_to_local() -> None:
    result = _run_python(
        "",
        "manage.py",
        "shell",
        "-c",
        "from django.conf import settings; print(settings.SETTINGS_MODULE)",
        DJANGO_SECRET_KEY=GOOD_KEY,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    # Django 5.2's shell prints an auto-import banner first.
    assert result.stdout.strip().splitlines()[-1] == "config.settings.local"
