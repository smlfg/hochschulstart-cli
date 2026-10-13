"""Configuration: environment variables override file and optional keyring."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hochschulstart_cli import exit_codes as ec
from hochschulstart_cli.errors import CliError
from hochschulstart_cli.json_util import loads


ENV_PREFIX = "HOCHSCHULSTART_"
ENV_BASE_URL = f"{ENV_PREFIX}BASE_URL"
ENV_API_TOKEN = f"{ENV_PREFIX}API_TOKEN"
CONFIG_FILE_ENV = f"{ENV_PREFIX}CONFIG"


@dataclass
class ResolvedConfig:
    base_url: str | None
    api_token: str | None
    sources: dict[str, str]


def _load_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise CliError(f"invalid config file: {path}", code=ec.PARSE, details={"reason": str(e)}) from e
    if not isinstance(data, dict):
        raise CliError(f"config file must be a JSON object: {path}", code=ec.PARSE)
    return data


def _load_keyring(service: str) -> str | None:
    try:
        import keyring
    except ImportError:
        return None
    try:
        return keyring.get_password(service, "api_token")
    except Exception:
        return None


def resolve_config(
    *,
    config_path: Path | None = None,
    keyring_service: str = "hochschulstart",
) -> ResolvedConfig:
    """Merge config with precedence: env > config file > keyring."""
    sources: dict[str, str] = {}
    file_path = Path(os.environ.get(CONFIG_FILE_ENV, "")) if os.environ.get(CONFIG_FILE_ENV) else None
    if config_path is not None:
        file_path = config_path
    elif file_path is None:
        file_path = Path.home() / ".config" / "hochschulstart" / "config.json"

    file_data = _load_file(file_path) if file_path else {}
    if file_data:
        sources["file"] = str(file_path)

    base_url = os.environ.get(ENV_BASE_URL)
    if base_url:
        sources["base_url"] = "env"
    elif file_data.get("base_url"):
        base_url = str(file_data["base_url"])
        sources["base_url"] = "file"

    api_token = os.environ.get(ENV_API_TOKEN)
    if api_token:
        sources["api_token"] = "env"
    elif file_data.get("api_token"):
        api_token = str(file_data["api_token"])
        sources["api_token"] = "file"
    else:
        kr = _load_keyring(keyring_service)
        if kr:
            api_token = kr
            sources["api_token"] = "keyring"

    return ResolvedConfig(base_url=base_url, api_token=api_token, sources=sources)


def require_auth(cfg: ResolvedConfig) -> str:
    if not cfg.api_token:
        raise CliError("missing API token (set env or config)", code=ec.AUTH)
    return cfg.api_token
