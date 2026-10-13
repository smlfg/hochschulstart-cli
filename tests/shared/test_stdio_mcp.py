"""MCP stdio smoke tests: initialize, tools/list, tool metadata."""

from __future__ import annotations

import pytest

mcp_client = pytest.importorskip("mcp").client  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_stdio_initialize_and_tools_not_empty(
    mcp_server_command: list[str],
    mcp_server_name: str | None,
    mcp_stdio_env: dict[str, str] | None,
) -> None:
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    params = StdioServerParameters(
        command=mcp_server_command[0],
        args=mcp_server_command[1:],
        env=mcp_stdio_env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init_result = await session.initialize()
            if mcp_server_name is not None:
                assert init_result.serverInfo.name == mcp_server_name
            tools = await session.list_tools()
            assert tools.tools, "tools/list must not be empty"


@pytest.mark.asyncio
async def test_each_tool_has_description_and_input_schema(
    mcp_server_command: list[str],
    mcp_stdio_env: dict[str, str] | None,
) -> None:
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
            tools = await session.list_tools()
            for tool in tools.tools:
                assert tool.description and tool.description.strip(), (
                    f"{tool.name}: missing description"
                )
                assert tool.inputSchema is not None, f"{tool.name}: missing inputSchema"
                assert isinstance(tool.inputSchema, dict), (
                    f"{tool.name}: inputSchema must be a JSON schema object"
                )
