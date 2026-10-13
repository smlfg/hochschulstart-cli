"""Atomic state persistence with dry-run support."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from hochschulstart_cli import exit_codes as ec
from hochschulstart_cli.errors import CliError
from hochschulstart_cli.json_util import dumps, loads


def load_state(path: Path) -> dict[str, Any] | None:
    """Load JSON state; return ``None`` if the file is missing (not an error)."""
    if not path.exists():
        return None
    if path.is_dir():
        raise CliError(f"state path is a directory: {path}", code=ec.INPUT)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise CliError(f"cannot read state: {path}", code=ec.PARSE, details={"reason": str(e)}) from e
    if not text.strip():
        raise CliError(f"state file is empty: {path}", code=ec.PARSE)
    try:
        data = loads(text)
    except ValueError as e:
        raise CliError(f"invalid state JSON: {path}", code=ec.PARSE, details={"reason": str(e)}) from e
    if data is None:
        raise CliError(f"state must be a JSON object, got null: {path}", code=ec.PARSE)
    if not isinstance(data, dict):
        raise CliError(f"state must be a JSON object: {path}", code=ec.PARSE)
    return data


def save_state(path: Path, data: dict[str, Any], *, dry_run: bool = False) -> None:
    """Write state atomically; skip all I/O when ``dry_run`` is true."""
    if data is None:
        raise CliError("refusing to write null state", code=ec.INPUT)
    if not isinstance(data, dict):
        raise CliError("state must be a JSON object", code=ec.INPUT)
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dumps(data, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=".state-", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(path)
    except OSError as e:
        tmp.unlink(missing_ok=True)
        raise CliError(f"cannot write state: {path}", code=ec.PARSE, details={"reason": str(e)}) from e
