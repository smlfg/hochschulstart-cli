"""Repo-weite Fixtures. Alle Tests laufen offline gegen den Fake-Portal-Server.

Kein Test darf das echte Netz berühren. Der ``cli_runner`` startet die CLI als
Subprozess mit isoliertem Config-Verzeichnis und Fake-Portal-URLs.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from fake_portal import FakePortal

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def sample_state(fixtures_dir: Path) -> Path:
    return fixtures_dir / "sample_state.json"


@pytest.fixture
def portal() -> FakePortal:
    server = FakePortal()
    server.start()
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture
def cli_runner(portal: FakePortal, tmp_path: Path):
    def run(*args: str, env_extra: dict[str, str | None] | None = None, base_url: str | None = None):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        env["HOCHSCHULSTART_CONFIG_DIR"] = str(tmp_path / "config")
        env["HOCHSCHULSTART_BASE_URL"] = base_url or portal.base_url
        env["HOCHSCHULSTART_PUBLIC_URL"] = f"{portal.base_url}/terminuebersicht"
        env["HOCHSCHULSTART_USERNAME"] = "testuser"
        env["HOCHSCHULSTART_PASSWORD"] = "testpass"
        env.pop("HOCHSCHULSTART_SESSION", None)
        env.pop("HOCHSCHULSTART_CONFIG", None)
        for key, value in (env_extra or {}).items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        return subprocess.run(
            [sys.executable, "-m", "hochschulstart_cli", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=env,
        )

    run.config_dir = tmp_path / "config"  # type: ignore[attr-defined]
    return run


def json_out(proc: subprocess.CompletedProcess[str]) -> dict:
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(lines) == 1, f"erwartet genau 1 JSON-Zeile, bekam {len(lines)}: {proc.stdout!r}"
    return json.loads(lines[0])
