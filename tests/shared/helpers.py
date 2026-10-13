"""Parse MCP test configuration from environment variables."""

from __future__ import annotations

import json
import os
import shlex
from typing import Any


def server_command_from_env() -> list[str] | None:
    """Return argv to start the MCP server, or ``None`` if not configured.

    ``MCP_TEST_SERVER_COMMAND`` — JSON array, e.g. ``["uv","run","my-mcp"]``.
    ``MCP_TEST_SERVER_CMD`` — shell-quoted string (fallback).
    """

    raw = os.environ.get("MCP_TEST_SERVER_COMMAND")
    if raw:
        parsed = json.loads(raw)
        if not isinstance(parsed, list) or not parsed:
            raise ValueError("MCP_TEST_SERVER_COMMAND must be a non-empty JSON array")
        return [str(x) for x in parsed]
    cmd = os.environ.get("MCP_TEST_SERVER_CMD")
    if cmd:
        return shlex.split(cmd)
    return None


def server_name_from_env() -> str | None:
    return os.environ.get("MCP_TEST_SERVER_NAME")


def error_tool_from_env() -> str | None:
    return os.environ.get("MCP_TEST_ERROR_TOOL")


def error_tool_arguments_from_env() -> dict[str, Any]:
    raw = os.environ.get("MCP_TEST_ERROR_TOOL_ARGS", "{}")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("MCP_TEST_ERROR_TOOL_ARGS must be a JSON object")
    return data


def stdio_env_from_env() -> dict[str, str] | None:
    """Optional extra env for the server subprocess (JSON object)."""

    raw = os.environ.get("MCP_TEST_SERVER_ENV")
    if not raw:
        return None
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("MCP_TEST_SERVER_ENV must be a JSON object")
    return {str(k): str(v) for k, v in data.items()}
