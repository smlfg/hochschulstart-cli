"""Konfiguration: Umgebungsvariablen schlagen Datei und keyring.

Reihenfolge pro Feld: env > Config-Datei > keyring. Passwörter werden nie
ausgegeben; die Session-Cookie liegt getrennt (siehe ``session.py``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hochschulstart_cli import exit_codes as ec
from hochschulstart_cli.errors import CliError
from hochschulstart_cli.json_util import loads

ENV_PREFIX = "HOCHSCHULSTART_"
ENV_BASE_URL = f"{ENV_PREFIX}BASE_URL"
ENV_PUBLIC_URL = f"{ENV_PREFIX}PUBLIC_URL"
ENV_USERNAME = f"{ENV_PREFIX}USERNAME"
ENV_PASSWORD = f"{ENV_PREFIX}PASSWORD"
ENV_SESSION = f"{ENV_PREFIX}SESSION"
ENV_CONFIG = f"{ENV_PREFIX}CONFIG"
ENV_CONFIG_DIR = f"{ENV_PREFIX}CONFIG_DIR"

DEFAULT_BASE_URL = "https://dosv.hochschulstart.de"
DEFAULT_PUBLIC_URL = "https://www.hochschulstart.de/bewerben-beobachten/termine"
KEYRING_SERVICE = "hochschulstart"


def config_dir() -> Path:
    env_dir = os.environ.get(ENV_CONFIG_DIR)
    if env_dir:
        return Path(env_dir)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "hochschulstart"


def default_config_path() -> Path:
    return config_dir() / "config.json"


@dataclass
class ResolvedConfig:
    base_url: str
    public_url: str
    username: str | None
    password: str | None
    sources: dict[str, str] = field(default_factory=dict)


def _load_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise CliError(f"ungültige Config-Datei: {path}", code=ec.PARSE, details={"reason": str(e)}) from e
    if not isinstance(data, dict):
        raise CliError(f"Config-Datei muss ein JSON-Objekt sein: {path}", code=ec.PARSE)
    return data


def _from_keyring(item: str) -> str | None:
    try:
        import keyring
    except ImportError:
        return None
    try:
        return keyring.get_password(KEYRING_SERVICE, item) or None
    except Exception:
        return None


def _resolve_secret(
    *,
    env_name: str,
    file_key: str,
    keyring_item: str,
    file_data: dict[str, Any],
    sources: dict[str, str],
    field_name: str,
) -> str | None:
    value = os.environ.get(env_name)
    if value:
        sources[field_name] = "env"
        return value
    if file_data.get(file_key):
        sources[field_name] = "file"
        return str(file_data[file_key])
    kr = _from_keyring(keyring_item)
    if kr:
        sources[field_name] = "keyring"
        return kr
    return None


def resolve_config(*, config_path: Path | None = None) -> ResolvedConfig:
    """Merge mit Präzedenz: env > Config-Datei > keyring."""
    sources: dict[str, str] = {}
    file_path = Path(os.environ[ENV_CONFIG]) if os.environ.get(ENV_CONFIG) else default_config_path()
    if config_path is not None:
        file_path = config_path
    file_data = _load_file(file_path)
    if file_data:
        sources["file"] = str(file_path)

    base_url = os.environ.get(ENV_BASE_URL)
    if base_url:
        sources["base_url"] = "env"
    elif file_data.get("base_url"):
        base_url = str(file_data["base_url"])
        sources["base_url"] = "file"
    else:
        base_url = DEFAULT_BASE_URL
        sources["base_url"] = "default"

    public_url = os.environ.get(ENV_PUBLIC_URL)
    if public_url:
        sources["public_url"] = "env"
    elif file_data.get("public_url"):
        public_url = str(file_data["public_url"])
        sources["public_url"] = "file"
    else:
        public_url = DEFAULT_PUBLIC_URL
        sources["public_url"] = "default"

    username = _resolve_secret(
        env_name=ENV_USERNAME,
        file_key="username",
        keyring_item="username",
        file_data=file_data,
        sources=sources,
        field_name="username",
    )
    password = _resolve_secret(
        env_name=ENV_PASSWORD,
        file_key="password",
        keyring_item="password",
        file_data=file_data,
        sources=sources,
        field_name="password",
    )
    return ResolvedConfig(
        base_url=base_url,
        public_url=public_url,
        username=username,
        password=password,
        sources=sources,
    )


def require_credentials(cfg: ResolvedConfig) -> tuple[str, str]:
    missing = []
    if not cfg.username:
        missing.append(ENV_USERNAME)
    if not cfg.password:
        missing.append(ENV_PASSWORD)
    if missing:
        raise CliError(
            "Zugangsdaten fehlen (" + ", ".join(missing) + " setzen oder in die Config-Datei/keyring legen)",
            code=ec.AUTH,
        )
    return cfg.username, cfg.password
