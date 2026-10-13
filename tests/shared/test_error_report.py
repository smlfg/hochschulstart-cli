"""Structured tool errors should embed a ``report`` field (smlfg MCP convention)."""

from __future__ import annotations

import json

import pytest

mcp_client = pytest.importorskip("mcp").client  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_error_tool_response_includes_report(
    mcp_server_command: list[str],
    mcp_stdio_env: dict[str, str] | None,
    mcp_error_tool: str,
    mcp_error_tool_arguments: dict,
) -> None:
    from mcp import types as mcp_types
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    params = StdioServerParameters(
        command=mcp_server_command[0],
        args=mcp_server_command[1:],
        env=mcp_stdio_env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(mcp_error_tool, arguments=mcp_error_tool_arguments)
            assert result.isError is False, (
                f"{mcp_error_tool} should return structured JSON, not crash the server"
            )
            assert result.content, "empty tool response"
            first = result.content[0]
            assert isinstance(first, mcp_types.TextContent)
            data = json.loads(first.text)
            assert "report" in data, "error payload must include report for agent feedback"
            report = data["report"]
            assert isinstance(report, dict)
            assert report.get("tool") or report.get("error_code"), (
                "report should identify tool or error_code"
            )
