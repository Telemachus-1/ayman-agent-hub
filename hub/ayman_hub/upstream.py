"""Connections from the hub to each spoke's own MCP server."""

from __future__ import annotations

import logging
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path

import mcp_types as types
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from ayman_hub.config import Spoke, hub_home
from ayman_hub.oauth import FileTokenStorage, HubOAuthProvider, NeedsLogin

log = logging.getLogger("ayman_hub.upstream")


def root_error(e: BaseException) -> BaseException:
    """The real error inside task-group wrappers, so messages say what went wrong."""
    while isinstance(e, BaseExceptionGroup) and len(e.exceptions) == 1:
        e = e.exceptions[0]
    return e


def describe_error(e: BaseException) -> str:
    e = root_error(e)
    return f"{type(e).__name__}: {e}"[:300]


def problem_category(e: BaseException, spoke: str) -> str:
    """A fixed message for agents. Raw errors can carry token-endpoint replies or setting names."""
    from ayman_hub.oauth import NeedsLogin

    root = root_error(e)
    if isinstance(root, NeedsLogin):
        return f"needs sign-in: run `ayman-hub login {spoke}`"
    if isinstance(root, MissingSetting):
        return "missing settings on the hub server (see `ayman-hub doctor`)"
    return "could not connect (details in the hub's server log)"


class MissingSetting(RuntimeError):
    """An environment variable the spoke needs is not set."""


class Upstream:
    """One live session to one spoke. If it fails to start, the spoke is marked down and offers no tools."""

    def __init__(self, spoke: Spoke, home: Path | None = None):
        self.spoke = spoke
        self.home = home
        self.session: ClientSession | None = None
        self.tools: dict[str, types.Tool] = {}
        self.error: str | None = None    # detail, for the server log only
        self.problem: str | None = None  # fixed wording that agents may see

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.spoke.auth == "bearer" and self.spoke.auth_env:
            token = os.environ.get(self.spoke.auth_env)
            if not token:
                raise MissingSetting(f"environment variable {self.spoke.auth_env} is not set")
            headers["Authorization"] = f"Bearer {token}"
        for header, env_name in self.spoke.header_env.items():
            value = os.environ.get(env_name)
            if not value:
                raise MissingSetting(f"environment variable {env_name} is not set")
            headers[header] = value
        return headers

    async def start(self, stack: AsyncExitStack) -> None:
        try:
            if self.spoke.transport == "http":
                auth = None
                if self.spoke.auth == "oauth":
                    storage = FileTokenStorage(self.home or hub_home(), self.spoke)
                    if not storage.signed_in():
                        raise NeedsLogin(f"not signed in: run `ayman-hub login {self.spoke.name}`")
                    auth = HubOAuthProvider(self.spoke, storage)
                client = create_mcp_http_client(headers=self._headers(), auth=auth)
                await stack.enter_async_context(client)
                read, write = await stack.enter_async_context(
                    streamable_http_client(self.spoke.url, http_client=client)
                )
            else:
                home = self.home or hub_home()
                env = {k: os.environ[k] for k in ("PATH", "HOME", "LANG") if k in os.environ}
                env["AYMAN_HUB_HOME"] = str(home)  # hub-owned spokes keep their sign-in here
                for name in self.spoke.secret_env_names():
                    if name not in os.environ:
                        raise MissingSetting(f"environment variable {name} is not set")
                    env[name] = os.environ[name]
                # "@python" means this hub's own interpreter, so PATH can't swap it. The working
                # folder is the owner-only hub home, so nothing planted beside the hub is imported.
                command = sys.executable if self.spoke.command == "@python" else self.spoke.command
                params = StdioServerParameters(
                    command=command, args=list(self.spoke.args), env=env, cwd=str(home)
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
            self.error = describe_error(e)
            self.problem = problem_category(e, self.spoke.name)
            log.warning("spoke %s down: %s", self.spoke.name, self.error)

    async def refresh_tools(self) -> None:
        assert self.session is not None
        tools: dict[str, types.Tool] = {}
        cursor = None
        seen: set[str] = set()
        for _ in range(50):  # a service that keeps paging must not hang the hub
            params = types.PaginatedRequestParams(cursor=cursor) if cursor else None
            result = await self.session.list_tools(params=params)
            for tool in result.tools:
                tools[tool.name] = tool
            cursor = result.next_cursor
            if not cursor or cursor in seen:
                break
            seen.add(cursor)
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
