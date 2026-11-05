"""Ausgabemodus: JSON automatisch, sobald stdout kein Terminal ist."""

from __future__ import annotations

import contextlib
import io
import json

import pytest

from fake_portal import SYNTH_SESSION
from hochschulstart_cli import cli as cli_mod
from hochschulstart_cli import exit_codes as ec
from test_interactive_login import FakeTty


@pytest.fixture
def session_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("HOCHSCHULSTART_SESSION", SYNTH_SESSION)
    monkeypatch.setenv("HOCHSCHULSTART_CONFIG_DIR", str(tmp_path / "config"))
    for name in ("HOCHSCHULSTART_USERNAME", "HOCHSCHULSTART_PASSWORD"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def patched_client(monkeypatch: pytest.MonkeyPatch, portal):
    from hochschulstart_cli.http_client import PortalClient

    def _client(cfg, require_session: bool = True) -> PortalClient:
        return PortalClient(portal.base_url, session_cookie=SYNTH_SESSION, polite_delay=0.0)

    monkeypatch.setattr(cli_mod, "_client", _client)


def test_status_auto_json_when_stdout_is_pipe(
    monkeypatch: pytest.MonkeyPatch, session_env, patched_client, portal
):
    monkeypatch.setattr("sys.stdin", FakeTty(""))
    out = io.StringIO()  # isatty() -> False, wie eine Pipe
    with contextlib.redirect_stdout(out):
        code = cli_mod._main(["status"])
    assert code == ec.OK
    lines = [line for line in out.getvalue().splitlines() if line.strip()]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["ok"] is True
    assert payload["count"] == 2
    assert "Bewerbungen (" not in out.getvalue()
