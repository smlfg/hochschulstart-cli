from pathlib import Path

import pytest

from hochschulstart_cli.errors import CliError
from hochschulstart_cli.state import load_state, save_state


def test_load_missing_returns_none(tmp_path: Path):
    assert load_state(tmp_path / "missing.json") is None


def test_save_atomic_and_dry_run(tmp_path: Path, sample_state: Path):
    dest = tmp_path / "state.json"
    data = load_state(sample_state)
    assert data is not None
    save_state(dest, data, dry_run=True)
    assert not dest.exists()
    save_state(dest, data, dry_run=False)
    assert dest.read_text(encoding="utf-8").strip().startswith("{")


def test_refuse_null_state(tmp_path: Path):
    with pytest.raises(CliError):
        save_state(tmp_path / "x.json", None)  # type: ignore[arg-type]


def test_empty_file_is_parse_error(tmp_path: Path):
    p = tmp_path / "empty.json"
    p.write_text("", encoding="utf-8")
    with pytest.raises(CliError):
        load_state(p)
