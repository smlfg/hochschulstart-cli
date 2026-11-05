"""Interaktives Login: Terminal-Prompts, keyring-Angebot, TTY-/EOF-Verhalten.

Läuft in-process mit monkeypatch — kein echter Netzzugriff (Fake-Portal via
``portal``-Fixture) und kein echter getpass/keyring-Import.
"""

from __future__ import annotations

import contextlib
import io
import sys
import types

import pytest

from fake_portal import SYNTH_SESSION
from hochschulstart_cli import cli as cli_mod
from hochschulstart_cli import exit_codes as ec
from hochschulstart_cli.errors import CliError, run_main


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    for name in ("HOCHSCHULSTART_USERNAME", "HOCHSCHULSTART_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOCHSCHULSTART_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("HOCHSCHULSTART_PUBLIC_URL", "http://example.invalid/termine")


@pytest.fixture
def patched_client(monkeypatch: pytest.MonkeyPatch, portal):
    from hochschulstart_cli.http_client import PortalClient

    def _client(cfg, require_session: bool = True) -> PortalClient:
        return PortalClient(portal.base_url, polite_delay=0.0)

    monkeypatch.setattr(cli_mod, "_client", _client)


class FakeTty(io.StringIO):
    def isatty(self) -> bool:
        return True


class FakeStdout(FakeTty):
    """Pipe-freier stdout, damit die CLI im Test den Menschenmodus wählt."""


def _run(argv: list[str]):
    """CLI in-process ausführen; CliError wird als (code, Fehler) abgefangen."""
    out, err = FakeStdout(), io.StringIO()
    code: int = 0
    error: CliError | None = None
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli_mod._main(list(argv))
    except CliError as exc:
        code, error = exc.code, exc
    except SystemExit as exc:  # argparse
        code = exc.code if isinstance(exc.code, int) else 1
    return code, out.getvalue(), err.getvalue(), error


def test_login_prompts_tty_and_saves_keyring(
    monkeypatch: pytest.MonkeyPatch, clean_env, patched_client, portal
):
    portal.username = "mein-benutzer"
    portal.password = "geheim-123"
    monkeypatch.setattr("sys.stdin", FakeTty("mein-benutzer\nja\n"))
    saved: dict[tuple[str, str], str] = {}

    def set_password(service, item, value):
        saved[(service, item)] = value

    fake = types.ModuleType("keyring")
    fake.set_password = set_password  # type: ignore[attr-defined]
    fake.get_password = lambda service, item: saved.get((service, item))  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "keyring", fake)
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "geheim-123")

    code, out, err, error = _run(["login"])
    assert code == ec.OK, error
    posts = [r for r in portal.requests if r["method"] == "POST" and r["path"] == "/bewerber/login"]
    assert len(posts) == 1
    assert "benutzername=mein-benutzer" in posts[0]["body"]
    assert "passwort=geheim-123" in posts[0]["body"]
    assert saved[("hochschulstart", "password")] == "geheim-123"
    assert saved[("hochschulstart", "username")] == "mein-benutzer"
    assert "Schlüsselbund" in out + err
    assert saved[("hochschulstart", "session")] == SYNTH_SESSION  # Session via fake-keyring abgelegt


def test_login_prompt_decline_n_leaves_keyring_untouched(
    monkeypatch: pytest.MonkeyPatch, clean_env, patched_client, portal
):
    monkeypatch.setattr("sys.stdin", FakeTty("mein-benutzer\nn\n"))
    set_calls: list[tuple[str, str]] = []
    fake = types.ModuleType("keyring")
    fake.set_password = lambda s, i, v: set_calls.append((i, v))  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "keyring", fake)
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "geheim-123")
    portal.username = "mein-benutzer"
    portal.password = "geheim-123"

    code, _out, _err, error = _run(["login"])
    assert code == ec.OK, error
    assert set_calls == [("session", SYNTH_SESSION)], "nur die Session, nicht das Passwort im keyring"
    posts = [r for r in portal.requests if r["method"] == "POST" and r["path"] == "/bewerber/login"]
    assert len(posts) == 1


def test_login_prompt_unknown_password_field_filled_by_getpass(
    monkeypatch: pytest.MonkeyPatch, clean_env, patched_client, portal
):
    """Nur Passwort fehlt: getpass wird genutzt, kein Passwort-Prompt über input()."""
    monkeypatch.setenv("HOCHSCHULSTART_USERNAME", "env-user")
    portal.username = "env-user"
    portal.password = "geheim-tty"
    monkeypatch.setattr("sys.stdin", FakeTty("\nn\n"))  # zweite Zeile: keyring-Angebot ablehnen
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "geheim-tty")
    code, _out, _err, error = _run(["login"])
    assert code == ec.OK, error
    posts = [r for r in portal.requests if r["method"] == "POST" and r["path"] == "/bewerber/login"]
    assert "passwort=geheim-tty" in posts[0]["body"]


def test_login_missing_credentials_no_tty_keeps_error_message(
    monkeypatch: pytest.MonkeyPatch, clean_env, portal
):
    """Ohne TTY: kein Prompt, klarer Fehler mit Hinweis auf das Terminal."""
    monkeypatch.delenv("HOCHSCHULSTART_SESSION", raising=False)
    code, _out, err, error = _run(["login"])
    assert code == ec.AUTH
    assert error is not None
    assert "--username" in error.message
    assert "`hochschulstart login` im Terminal ausführen" in error.message
    assert portal.requests == []


def test_login_prompt_eof_exits_130_without_request(
    monkeypatch: pytest.MonkeyPatch, clean_env, patched_client, portal
):
    monkeypatch.setattr("sys.stdin", FakeTty(""))
    argv = ["login"]

    def run() -> int:
        with contextlib.redirect_stdout(FakeStdout()):
            return run_main(lambda _argv: cli_mod._main(argv))  # run_main fängt EOFError

    code = run()
    assert code == ec.ABORT
    assert portal.requests == []
