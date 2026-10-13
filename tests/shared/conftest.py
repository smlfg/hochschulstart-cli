"""Fixtures for the shared MCP suite.

Override any fixture in your repo's ``tests/conftest.py`` (pytest discovers both).
Alternatively set the ``MCP_TEST_*`` environment variables (see README).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from .helpers import (
    error_tool_arguments_from_env,
    error_tool_from_env,
    server_command_from_env,
    server_name_from_env,
    stdio_env_from_env,
)


@pytest.fixture(scope="session")
def mcp_server_command() -> list[str]:
    cmd = server_command_from_env()
    if not cmd:
        pytest.skip(
            "MCP server command not configured "
            "(set MCP_TEST_SERVER_COMMAND or override mcp_server_command fixture)"
        )
    return cmd


@pytest.fixture(scope="session")
def mcp_server_name(mcp_server_command: list[str]) -> str | None:
    return server_name_from_env()


@pytest.fixture(scope="session")
def mcp_stdio_env() -> dict[str, str] | None:
    return stdio_env_from_env()


@pytest.fixture(scope="session")
def mcp_error_tool() -> str:
    name = error_tool_from_env()
    if not name:
        pytest.skip(
            "MCP_TEST_ERROR_TOOL not set (tool that returns structured error JSON)"
        )
    return name


@pytest.fixture(scope="session")
def mcp_error_tool_arguments() -> dict[str, Any]:
    return error_tool_arguments_from_env()


@pytest.fixture(scope="session")
def redact_fn() -> Callable[[Any], str]:
    """Callable ``redact(text) -> str`` from env or skip."""

    spec = os.environ.get("MCP_TEST_REDACT")
    if not spec:
        pytest.skip("MCP_TEST_REDACT not set (module:function, e.g. mypkg.feedback:redact)")
    if ":" not in spec:
        pytest.skip("MCP_TEST_REDACT must be module:function")
    mod_name, attr = spec.split(":", 1)
    import importlib

    mod = importlib.import_module(mod_name)
    fn = getattr(mod, attr)
    return fn
