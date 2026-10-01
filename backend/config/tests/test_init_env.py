"""scripts/dev/init-env.sh (SC-26, NT3-26). Runs against a temp copy of the example."""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "dev" / "init-env.sh"
EXAMPLE = REPO_ROOT / ".env.example"
KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
SECRET_KEYS = {"POSTGRES_PASSWORD", "DB_APP_PASSWORD", "DB_MIGRATOR_PASSWORD", "DJANGO_SECRET_KEY"}


def parse(path: Path) -> dict[str, str]:
    pairs = {}
    for line in path.read_text().splitlines():
        match = KEY_RE.match(line)
        if match:
            pairs[match.group(1)] = match.group(2)
    return pairs


def run(example: Path, target: Path) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "RMS_ENV_EXAMPLE": str(example),
        "RMS_ENV_FILE": str(target),
    }
    return subprocess.run(
        ["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=30, check=False
    )


@pytest.fixture
def workdir(tmp_path: Path) -> tuple[Path, Path]:
    example = tmp_path / "example"
    shutil.copyfile(EXAMPLE, example)
    return example, tmp_path / "generated"


def test_example_has_placeholders_only() -> None:
    values = parse(EXAMPLE)
    assert values.keys() >= SECRET_KEYS
    for key in SECRET_KEYS:
        assert values[key] == "change-me"


def test_generates_file_with_random_secrets(workdir: tuple[Path, Path]) -> None:
    example, target = workdir
    result = run(example, target)
    assert result.returncode == 0, result.stderr

    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    text = target.read_text()
    assert "change-me" not in text

    generated = parse(target)
    assert generated.keys() == parse(example).keys()
    for key in SECRET_KEYS:
        value = generated[key]
        assert re.fullmatch(r"[A-Za-z0-9]+", value)
        assert len(value) >= (64 if key == "DJANGO_SECRET_KEY" else 32)
        assert value not in result.stdout
        assert value not in result.stderr
    # Non-secret values are copied unchanged.
    for key, value in parse(example).items():
        if key not in SECRET_KEYS:
            assert generated[key] == value
    # Secrets are independent.
    assert len({generated[key] for key in SECRET_KEYS}) == len(SECRET_KEYS)
    # No temp file left behind.
    assert sorted(p.name for p in target.parent.iterdir()) == ["example", "generated"]


def test_second_run_leaves_file_unchanged(workdir: tuple[Path, Path]) -> None:
    example, target = workdir
    assert run(example, target).returncode == 0
    before = target.read_bytes()
    result = run(example, target)
    assert result.returncode == 0
    assert "already exists" in result.stdout
    assert target.read_bytes() == before


def test_fails_when_example_missing(tmp_path: Path) -> None:
    result = run(tmp_path / "missing", tmp_path / "generated")
    assert result.returncode != 0
    assert not (tmp_path / "generated").exists()
