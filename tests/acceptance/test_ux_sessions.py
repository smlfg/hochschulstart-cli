"""Akzeptanztests aus den drei UX-Sitzungen in docs/UX.md.

Jede Sitzung läuft als Subprozess gegen den Fake-Server aus
``tests/harness/fake_server.py``. Die Basis-URL kommt über
``HOCHSCHULSTART_BASE_URL`` aus ``ux-meta``; Login, Status und Annahme nutzen die
Routen und Formsteps aus ``ux-routes``/``ux-formsteps``.

Die Tests dürfen bis zum Bau in Schritt 4 rot sein. Sie beschreiben den
Zielzustand aus ``docs/UX.md`` und ``INTERFACE.md``, nicht den Ist-Code.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "tests" / "harness"
sys.path.insert(0, str(HARNESS))

from fake_server import FakeServer  # noqa: E402
from ux_session import PtySession, strip_ansi  # noqa: E402
from ux_spec import parse  # noqa: E402

SPEC = parse(ROOT / "docs" / "UX.md")
SESSION_COOKIE = "SYNTH-SESSION-0001"


def _cli_env(tmp_path: Path, server: FakeServer, *, session: bool = False) -> dict[str, str]:
    """Isolierte Umgebung: Fake-Server, Config unter tmp, kein echter keyring."""
    fake_keyring = tmp_path / "no-keyring"
    fake_keyring.mkdir(parents=True, exist_ok=True)
    (fake_keyring / "keyring.py").write_text(
        "raise ImportError('keyring ist in Akzeptanztests deaktiviert')\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(fake_keyring), str(ROOT / "src")])
    env["HOCHSCHULSTART_CONFIG_DIR"] = str(tmp_path / "config")
    env["HOCHSCHULSTART_BASE_URL"] = server.base_url
    env["HOCHSCHULSTART_PUBLIC_URL"] = f"{server.base_url}/termine"
    env["PYTHONUNBUFFERED"] = "1"
    for name in (
        "HOCHSCHULSTART_USERNAME",
        "HOCHSCHULSTART_PASSWORD",
        "HOCHSCHULSTART_SESSION",
        "HOCHSCHULSTART_CONFIG",
    ):
        env.pop(name, None)
    if session:
        env["HOCHSCHULSTART_SESSION"] = SESSION_COOKIE
    return env


def _run(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "hochschulstart_cli", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=30,
    )


def _pty(env: dict[str, str], *args: str) -> PtySession:
    return PtySession(
        [sys.executable, "-m", "hochschulstart_cli", *args],
        env=env,
        cwd=ROOT,
    )


def _close(session: PtySession) -> None:
    session.close()


def test_login_sitzung_fragt_interaktiv_und_speichert_session(tmp_path: Path) -> None:
    """UX-Sitzung „Installation und Login“: Prompts, POST auf Formular-action, 0600."""
    with FakeServer(SPEC, ROOT) as server:
        env = _cli_env(tmp_path, server, session=False)
        session = _pty(env, "login")
        try:
            assert session.expect("Benutzername:", timeout=10), strip_ansi(session.transcript)
            session.send_line("testuser")
            assert session.expect("Passwort:", timeout=10), strip_ansi(session.transcript)
            session.send_line("geheim")
            assert session.expect("Login erfolgreich", timeout=10), strip_ansi(session.transcript)
            assert session.wait_exit(10) == 0
        finally:
            _close(session)

        posts = [
            request
            for request in server.requests
            if request.method == "POST" and request.path == "/bewerber/2376"
        ]
        assert len(posts) == 1, [request.path for request in server.requests]
        assert "j_username" in posts[0].fields
        assert "j_password" in posts[0].fields

        session_file = tmp_path / "config" / "session.json"
        assert session_file.is_file()
        assert stat.S_IMODE(session_file.stat().st_mode) == 0o600


def test_status_sitzung_zeigt_bewerbungen_lesbar(tmp_path: Path) -> None:
    """UX-Sitzung „Bewerbungen ansehen“: lesbare Zeilen im Terminal."""
    with FakeServer(SPEC, ROOT) as server:
        env = _cli_env(tmp_path, server, session=True)
        session = _pty(env, "status")
        try:
            assert session.expect("Bewerbungen (2):", timeout=10), strip_ansi(session.transcript)
            assert session.expect("Musterstudiengang", timeout=10)
            assert session.expect("Musteruniversität", timeout=10)
            assert session.expect("Zulassungsangebot", timeout=10)
            assert session.expect("B-1001", timeout=10)
            assert session.wait_exit(10) == 0
        finally:
            _close(session)


def test_status_filtert_positional_nach_studiengang(tmp_path: Path) -> None:
    """Suchbegriff positional statt ID; nur der passende Treffer bleibt übrig."""
    with FakeServer(SPEC, ROOT) as server:
        env = _cli_env(tmp_path, server, session=True)
        session = _pty(env, "status", "Synthetisches")
        try:
            assert session.expect("Bewerbungen (1):", timeout=10), strip_ansi(session.transcript)
            assert session.expect("B-1002", timeout=10)
            transcript = strip_ansi(session.transcript)
            assert "B-1001" not in transcript
            assert session.wait_exit(10) == 0
        finally:
            _close(session)


def test_annehmen_sitzung_fragt_jn_und_sendet_alle_formsteps(tmp_path: Path) -> None:
    """UX-Sitzung „Zulassungsangebot annehmen“: [j/N] auf stderr, j sendet alle Schritte."""
    with FakeServer(SPEC, ROOT) as server:
        env = _cli_env(tmp_path, server, session=True)
        session = _pty(env, "annehmen", "Musterstudiengang")
        try:
            assert session.expect("Annahme verbindlich? [j/N]", timeout=10), strip_ansi(
                session.transcript
            )
            session.send_line("j")
            assert session.expect("Angenommen: B-1001", timeout=10), strip_ansi(
                session.transcript
            )
            assert session.wait_exit(10) == 0
        finally:
            _close(session)

        sent = [step_id for step_id, _record in server.sent_formsteps()]
        assert sent == [step.id for step in SPEC.formsteps]
        assert server.missing_formsteps() == []


def test_annehmen_ohne_tty_und_ohne_confirm_sendet_keinen_request(tmp_path: Path) -> None:
    """Ohne TTY und ohne Flag: Abbruch vor jedem Request, kein Formstep."""
    with FakeServer(SPEC, ROOT) as server:
        env = _cli_env(tmp_path, server, session=True)
        result = _run(env, "annehmen", "Musterstudiengang")
        assert result.returncode != 0
        assert server.requests == []
        assert server.sent_formsteps() == []
        assert "confirm" in (result.stdout + result.stderr).lower()
