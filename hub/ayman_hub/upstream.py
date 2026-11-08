"""Connections from the hub to each spoke's own MCP server."""

from __future__ import annotations

import logging
import os
from contextlib import AsyncExitStack

import mcp_types as types
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from ayman_hub.config import Spoke

log = logging.getLogger("ayman_hub.upstream")


class Upstream:
    """One live session to one spoke. If it fails to start, the spoke is marked down and offers no tools."""

    def __init__(self, spoke: Spoke):
        self.spoke = spoke
        self.session: ClientSession | None = None
        self.tools: dict[str, types.Tool] = {}
        self.error: str | None = None

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.spoke.auth_env:
            token = os.environ.get(self.spoke.auth_env)
            if not token:
                raise RuntimeError(f"environment variable {self.spoke.auth_env} is not set")
            headers["Authorization"] = f"Bearer {token}"
        for header, env_name in self.spoke.header_env.items():
            value = os.environ.get(env_name)
            if not value:
                raise RuntimeError(f"environment variable {env_name} is not set")
            headers[header] = value
        return headers

    async def start(self, stack: AsyncExitStack) -> None:
        try:
            if self.spoke.transport == "http":
                client = create_mcp_http_client(headers=self._headers())
                await stack.enter_async_context(client)
                read, write = await stack.enter_async_context(
                    streamable_http_client(self.spoke.url, http_client=client)
                )
            else:
                env = {k: os.environ[k] for k in ("PATH", "HOME", "LANG") if k in os.environ}
                for name in self.spoke.secret_env_names():
                    if name not in os.environ:
                        raise RuntimeError(f"environment variable {name} is not set")
                    env[name] = os.environ[name]
                params = StdioServerParameters(
                    command=self.spoke.command, args=list(self.spoke.args), env=env
                )
                read, write = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self.session = session
            await self.refresh_tools()
            log.info("spoke %s up: %d tools", self.spoke.name, len(self.tools))
        except Exception as e:  # one spoke failing must not take the hub down
            self.session = None
            self.tools = {}
            # Never echo values: the message names variables, not their contents.
            self.error = f"{type(e).__name__}: {e}"[:300]
            log.warning("spoke %s down: %s", self.spoke.name, self.error)

    async def refresh_tools(self) -> None:
        assert self.session is not None
        tools: dict[str, types.Tool] = {}
        cursor = None
        while True:
            params = types.PaginatedRequestParams(cursor=cursor) if cursor else None
            result = await self.session.list_tools(params=params)
            for tool in result.tools:
                tools[tool.name] = tool
            cursor = result.next_cursor
            if not cursor:
                break
        self.tools = tools

    async def call(self, tool: str, arguments: dict | None) -> types.CallToolResult:
        if self.session is None:
            raise RuntimeError(f"spoke '{self.spoke.name}' is not connected")
        result = await self.session.call_tool(tool, arguments or {})
        if not isinstance(result, types.CallToolResult):
            # Input-required and other multi-step results aren't relayed yet.
            return types.CallToolResult(
                content=[types.TextContent(type="text", text="The service asked for input the hub can't relay yet.")],
                is_error=True,
            )
        return result
