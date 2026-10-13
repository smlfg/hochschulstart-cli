import json
import os
from pathlib import Path

from hochschulstart_cli.config import ENV_API_TOKEN, ENV_BASE_URL, resolve_config


def test_env_overrides_file(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(
        json.dumps({"base_url": "https://file.example", "api_token": "file-token"}),
        encoding="utf-8",
    )
    monkeypatch.setenv(ENV_BASE_URL, "https://env.example")
    monkeypatch.setenv(ENV_API_TOKEN, "env-token")
    cfg = resolve_config(config_path=cfg_file)
    assert cfg.base_url == "https://env.example"
    assert cfg.api_token == "env-token"
    assert cfg.sources["base_url"] == "env"
    assert cfg.sources["api_token"] == "env"


def test_file_used_when_no_env(tmp_path: Path, monkeypatch):
    monkeypatch.delenv(ENV_BASE_URL, raising=False)
    monkeypatch.delenv(ENV_API_TOKEN, raising=False)
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({"base_url": "https://file.example"}), encoding="utf-8")
    cfg = resolve_config(config_path=cfg_file)
    assert cfg.base_url == "https://file.example"
    assert cfg.sources["base_url"] == "file"
