"""The round-trip target guard (change 0004, C-17, T4-23).

The round trip itself runs as ``make migrations-roundtrip`` (it creates and
drops its own database). These tests prove that it refuses every database
other than a throwaway one with the fixed prefix, before any connection.
"""

from __future__ import annotations

import pytest

from config.tests.roundtrip import DEFAULT_TARGET, main, target_problem

NAMES = {"dev_db": "rms", "test_db": "test_rms", "template_db": "rms_template"}


@pytest.mark.parametrize("target", [DEFAULT_TARGET, "rms_roundtrip_ci", "rms_roundtrip_2"])
def test_throwaway_names_are_accepted(target: str) -> None:
    assert target_problem(target, **NAMES) is None


@pytest.mark.parametrize(
    "target",
    [
        "rms",
        "test_rms",
        "rms_template",
        "postgres",
        "template1",
        "roundtrip",
        "rms_roundtrip_",
        "rms_roundtripx",
        "RMS_ROUNDTRIP",
        "rms_roundtrip; DROP DATABASE rms",
        "",
    ],
)
def test_other_names_are_refused(target: str) -> None:
    assert target_problem(target, **NAMES) is not None


def test_a_dev_db_with_the_prefix_is_still_refused() -> None:
    names = {**NAMES, "dev_db": DEFAULT_TARGET}
    assert target_problem(DEFAULT_TARGET, **names) is not None


def test_main_refuses_before_connecting(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # main() sets the settings module; monkeypatch restores it afterwards.
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "config.settings.test")
    # No django_db mark: a connection attempt would raise instead of returning 2.
    assert main(["rms"]) == 2
    assert "must match" in capsys.readouterr().err
