"""Env readers (SC-01, SC-03, SC-04, SC-05 list reader, SC-06). NT3-01/03/06."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from django.core.exceptions import ImproperlyConfigured

from config import env

CANARY = "Canary-Value-9f3a"
VAR = "RMS_TEST_VAR"

SetEnv = Callable[[str | None], None]


@pytest.fixture
def setenv(monkeypatch: pytest.MonkeyPatch) -> SetEnv:
    def _set(value: str | None) -> None:
        if value is None:
            monkeypatch.delenv(VAR, raising=False)
        else:
            monkeypatch.setenv(VAR, value)

    return _set


def _message(exc: pytest.ExceptionInfo[ImproperlyConfigured]) -> str:
    return str(exc.value)


@pytest.mark.parametrize("raw", ["true", "TRUE", " True ", "1"])
def test_bool_true(setenv: SetEnv, raw: str) -> None:
    setenv(raw)
    assert env.get_bool(VAR) is True


# SC-03 strips before matching, so "False " is false (never truthy).
@pytest.mark.parametrize("raw", ["false", "False", "False ", "0", " 0 "])
def test_bool_false(setenv: SetEnv, raw: str) -> None:
    setenv(raw)
    assert env.get_bool(VAR, default=True) is False


def test_bool_unset_defaults_to_false(setenv: SetEnv) -> None:
    setenv(None)
    assert env.get_bool(VAR) is False


@pytest.mark.parametrize("raw", ["no", "off", "yes", "on", "2", "f", "truthy", CANARY])
def test_bool_rejects_anything_else(setenv: SetEnv, raw: str) -> None:
    setenv(raw)
    with pytest.raises(ImproperlyConfigured) as exc:
        env.get_bool(VAR)
    assert _message(exc) == f"{VAR} must be one of: true, false, 1, 0"


def test_int_rejects_non_integer_without_echoing(setenv: SetEnv) -> None:
    setenv(CANARY)
    with pytest.raises(ImproperlyConfigured) as exc:
        env.get_int(VAR)
    assert CANARY not in _message(exc)
    assert "must be an integer" in _message(exc)


def test_require_str_missing(setenv: SetEnv) -> None:
    setenv("   ")
    with pytest.raises(ImproperlyConfigured, match=f"{VAR} must be set"):
        env.require_str(VAR)


def test_require_int(setenv: SetEnv) -> None:
    setenv("5432")
    assert env.require_int(VAR) == 5432


def test_list_strips_entries(setenv: SetEnv) -> None:
    setenv(" a.example , b.example ")
    assert env.get_list(VAR) == ["a.example", "b.example"]


def test_list_strip_exposes_wildcard(setenv: SetEnv) -> None:
    setenv(" *")
    assert env.get_list(VAR) == ["*"]


@pytest.mark.parametrize("raw", ["a,,b", "a,", ",a", "a, ,b"])
def test_list_rejects_empty_entries(setenv: SetEnv, raw: str) -> None:
    setenv(raw.replace("a", CANARY))
    with pytest.raises(ImproperlyConfigured) as exc:
        env.get_list(VAR)
    assert CANARY not in _message(exc)


def test_list_unset_and_blank_use_default(setenv: SetEnv) -> None:
    setenv("")
    assert env.get_list(VAR, ["x"]) == ["x"]


def test_choice(setenv: SetEnv) -> None:
    setenv("debug")
    assert env.get_choice(VAR, ("DEBUG", "INFO"), "INFO") == "DEBUG"
    setenv(CANARY)
    with pytest.raises(ImproperlyConfigured) as exc:
        env.get_choice(VAR, ("DEBUG", "INFO"), "INFO")
    assert CANARY not in _message(exc)


def test_proxy_header_valid(setenv: SetEnv) -> None:
    setenv("HTTP_X_FORWARDED_PROTO=https")
    assert env.get_proxy_ssl_header(VAR) == ("HTTP_X_FORWARDED_PROTO", "https")


def test_proxy_header_unset(setenv: SetEnv) -> None:
    setenv(None)
    assert env.get_proxy_ssl_header(VAR) is None


@pytest.mark.parametrize(
    "raw",
    [
        "X_FORWARDED_PROTO=https",
        "HTTP_X_FORWARDED_PROTO=http",
        "HTTP_X_FORWARDED_PROTO",
        "HTTP_x_forwarded_proto=https",
        "HTTP_X-FORWARDED-PROTO=https",
        "HTTP_X_FORWARDED_PROTO=https,http",
        f"HTTP_{CANARY}=https",
    ],
)
def test_proxy_header_malformed(setenv: SetEnv, raw: str) -> None:
    setenv(raw)
    with pytest.raises(ImproperlyConfigured) as exc:
        env.get_proxy_ssl_header(VAR)
    assert raw not in _message(exc)


def test_local_hosts_allowed() -> None:
    hosts = ["localhost", "127.0.0.1", "[::1]"]
    assert env.restrict_to_local_hosts(VAR, hosts) == hosts


@pytest.mark.parametrize("host", ["example.com", "*", ".localhost", "0.0.0.0", "testserver"])  # noqa: S104
def test_local_hosts_rejects_others(host: str) -> None:
    with pytest.raises(ImproperlyConfigured) as exc:
        env.restrict_to_local_hosts(VAR, ["localhost", host])
    assert host not in _message(exc)
