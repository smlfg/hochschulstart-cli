"""JSON helpers: reject NaN/Infinity in output."""

from __future__ import annotations

import json
from typing import Any


def dumps(obj: Any, **kwargs: Any) -> str:
    kwargs.setdefault("allow_nan", False)
    return json.dumps(obj, **kwargs)


def loads(text: str) -> Any:
    return json.loads(text)


def parse_json_object(text: str, *, name: str = "JSON") -> dict[str, Any]:
    """Parse JSON text as an object; never return ``None`` silently."""
    from hochschulstart_cli import exit_codes as ec
    from hochschulstart_cli.errors import CliError

    try:
        data = loads(text)
    except ValueError as e:
        raise CliError(f"invalid {name}", code=ec.PARSE, details={"reason": str(e)}) from e
    if data is None:
        raise CliError(f"{name} must not be null", code=ec.PARSE)
    if not isinstance(data, dict):
        raise CliError(f"{name} must be a JSON object", code=ec.PARSE)
    return data
