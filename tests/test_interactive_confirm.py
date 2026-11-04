"""Interaktive Bestätigung bei annehmen/absagen (Terminal, ohne --confirm).

Ohne TTY und ohne --confirm: Abbruch vor jedem Request (Exit 1). Mit
Terminal-Fake-stdin: 'n' beendet ohne schreibenden Request (Exit 0), 'j' sendet
alle Formularschritte. Offline gegen den Fake-Portal-Server.
"""

from __future__ import annotations

import pytest

from fake_portal import SYNTH_SESSION
from hochschulstart_cli import cli as cli_mod
from hochschulstart_cli import exit_codes as ec
from test_interactive_login import FakeTty, _run


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


def test_annehmen_negativ_n_sends_no_request(
    monkeypatch: pytest.MonkeyPatch, session_env, patched_client, portal
):
    monkeypatch.setattr("sys.stdin", FakeTty("n\n"))
    code, _out, err, error = _run(["annehmen", "B-1001"])
    assert code == ec.OK, error
    assert "Abgebrochen" in err
    assert not [r for r in portal.requests if r["method"] == "POST"], (
        "Antwort 'n' darf keinen schreibenden Request auslösen"
    )


def test_annehmen_nein_text_sends_no_request(
    monkeypatch: pytest.MonkeyPatch, session_env, patched_client, portal
):
    monkeypatch.setattr("sys.stdin", FakeTty("nein\n"))
    code, _out, err, error = _run(["absagen", "B-1002"])
    assert code == ec.OK, error
    assert "Abgebrochen" in err
    assert not [r for r in portal.requests if r["method"] == "POST"]


def test_annehmen_ja_continues_and_posts(
    monkeypatch: pytest.MonkeyPatch, session_env, patched_client, portal
):
    portal.username = "testuser"
    portal.password = "testpass"
    monkeypatch.setattr("sys.stdin", FakeTty("j\n"))
    code, out, err, error = _run(["annehmen", "B-1001"])
    assert code == ec.OK, error
    assert "Annahme verbindlich? [j/N]" in err
    assert "Angenommen: B-1001" in out
    posts = [r for r in portal.requests if r["method"] == "POST" and r["path"] == "/bewerber/bewerbungen/B-1001/annehmen"]
    assert len(posts) == 1


def test_confirm_without_tty_still_exit_1_before_request(
    monkeypatch: pytest.MonkeyPatch, session_env, portal
):
    code, _out, _err, error = _run(["annehmen", "B-1001", "--json"])
    assert code == ec.INPUT
    assert error is not None
    assert "--confirm" in error.message
    assert portal.requests == []


def test_confirm_eof_aborts_130_no_request(
    monkeypatch: pytest.MonkeyPatch, session_env, patched_client, portal
):
    monkeypatch.setattr("sys.stdin", FakeTty(""))

    def run() -> int:
        from hochschulstart_cli.errors import run_main

        return run_main(lambda argv: cli_mod._main(argv), ["absagen", "B-1002"])

    code = run()
    assert code == ec.ABORT
    assert not [r for r in portal.requests if r["method"] == "POST"]
