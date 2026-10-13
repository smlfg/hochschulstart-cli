"""Error-path templates: subprocess CLI, no network, relative fixtures only."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from hochschulstart_cli import exit_codes as ec

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "hochschulstart_cli", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
    )


def test_unknown_flag_exit_input():
    proc = run_cli("--nope")
    assert proc.returncode == ec.INPUT


def test_validate_negative_count_json():
    proc = run_cli("validate", "--count", "-1", "--json")
    assert proc.returncode == ec.INPUT
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == ec.INPUT
    assert len(proc.stdout.strip().splitlines()) == 1


def test_validate_missing_args_human():
    proc = run_cli("validate")
    assert proc.returncode == ec.INPUT
    assert proc.stderr.strip()


def test_state_dry_run_no_file(tmp_path: Path):
    dest = tmp_path / "nested" / "state.json"
    proc = run_cli(
        "state",
        str(dest),
        "--set",
        "k=v",
        "--dry-run",
        "--json",
    )
    assert proc.returncode == ec.OK
    assert not dest.exists()


def test_url_json_success():
    proc = run_cli("url", "https://api.example.com/v1", "users", "--json")
    assert proc.returncode == ec.OK
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["url"] == "https://api.example.com/v1/users"
