"""Session-Cookie-Verwaltung: env > keyring > Datei (0600).

Die Session-Cookie ist ein Geheimnis: sie wird nie gedruckt, nie geloggt und
nicht im Watch-State abgelegt. Reihenfolge der Quellen:
1. ``HOCHSCHULSTART_SESSION`` (z. B. für CI/Tests)
2. keyring (falls installiert)
3. Session-Datei im Config-Verzeichnis (0600)
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from hochschulstart_cli import exit_codes as ec
from hochschulstart_cli.config import config_dir
from hochschulstart_cli.errors import CliError

KEYRING_SERVICE = "hochschulstart"
KEYRING_ITEM = "session"
SESSION_FILE = "session.json"


def session_path() -> Path:
    return config_dir() / SESSION_FILE


def _read_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise CliError(f"ungültige Session-Datei: {path}", code=ec.PARSE, details={"reason": str(e)}) from e
    if not isinstance(data, dict):
        raise CliError(f"Session-Datei muss ein JSON-Objekt sein: {path}", code=ec.PARSE)
    cookie = data.get("session_cookie")
    if cookie is not None and not isinstance(cookie, str):
        raise CliError(f"session_cookie muss ein String sein: {path}", code=ec.PARSE)
    return cookie or None


def _write_file(path: Path, cookie: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"session_cookie": cookie}) + "\n", encoding="utf-8")
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    tmp.replace(path)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def _from_keyring() -> str | None:
    try:
        import keyring
    except ImportError:
        return None
    try:
        return keyring.get_password(KEYRING_SERVICE, KEYRING_ITEM) or None
    except Exception:
        return None


def load_session() -> tuple[str | None, str]:
    """Liefert (Cookie, Quelle). Quelle ist env/keyring/file/none."""
    cookie = os.environ.get("HOCHSCHULSTART_SESSION")
    if cookie:
        return cookie, "env"
    cookie = _from_keyring()
    if cookie:
        return cookie, "keyring"
    cookie = _read_file(session_path())
    if cookie:
        return cookie, "file"
    return None, "none"


def save_session(cookie: str, *, dry_run: bool = False) -> str:
    """Speichert die Session-Cookie; liefert die verwendete Quelle."""
    if not cookie:
        raise CliError("leere Session-Cookie wird nicht gespeichert", code=ec.INPUT)
    if dry_run:
        return "dry-run"
    try:
        import keyring

        keyring.set_password(KEYRING_SERVICE, KEYRING_ITEM, cookie)
        return "keyring"
    except Exception:
        pass
    _write_file(session_path(), cookie)
    return "file"


def clear_session() -> None:
    try:
        import keyring

        keyring.delete_password(KEYRING_SERVICE, KEYRING_ITEM)
    except Exception:
        pass
    session_path().unlink(missing_ok=True)
