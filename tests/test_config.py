import json
from pathlib import Path

import pytest

from hochschulstart_cli import config as config_mod
from hochschulstart_cli.config import (
    ENV_BASE_URL,
    ENV_PASSWORD,
    ENV_USERNAME,
    resolve_config,
)


@pytest.fixture(autouse=True)
def no_keyring(monkeypatch):
    monkeypatch.setattr(config_mod, "_from_keyring", lambda item: None)


def test_env_overrides_file(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(
        json.dumps({"base_url": "https://file.example", "username": "file-user", "password": "file-pass"}),
        encoding="utf-8",
    )
    monkeypatch.setenv(ENV_BASE_URL, "https://env.example")
    monkeypatch.setenv(ENV_USERNAME, "env-user")
    monkeypatch.setenv(ENV_PASSWORD, "env-pass")
    cfg = resolve_config(config_path=cfg_file)
    assert cfg.base_url == "https://env.example"
    assert cfg.username == "env-user"
    assert cfg.password == "env-pass"
    assert cfg.sources["base_url"] == "env"
    assert cfg.sources["username"] == "env"
    assert cfg.sources["password"] == "env"


def test_file_used_when_no_env(tmp_path: Path, monkeypatch):
    for name in (ENV_BASE_URL, ENV_USERNAME, ENV_PASSWORD):
        monkeypatch.delenv(name, raising=False)
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(
        json.dumps({"base_url": "https://file.example", "username": "file-user"}),
        encoding="utf-8",
    )
    cfg = resolve_config(config_path=cfg_file)
    assert cfg.base_url == "https://file.example"
    assert cfg.username == "file-user"
    assert cfg.sources["base_url"] == "file"
    assert cfg.password is None


def test_defaults_when_nothing_set(tmp_path: Path, monkeypatch):
    for name in (ENV_BASE_URL, ENV_USERNAME, ENV_PASSWORD):
        monkeypatch.delenv(name, raising=False)
    cfg = resolve_config(config_path=tmp_path / "missing.json")
    assert cfg.base_url.startswith("https://dosv.hochschulstart.de")
    assert cfg.public_url.endswith("/bewerben-beobachten/termine")
    assert cfg.username is None
