"""The MCP server agents talk to: one endpoint, every spoke's tools, filtered per client.

Agents see tools named `<spoke>__<tool>` (for example `linear__list_issues`).
Each call is checked by policy.decide(), forwarded if allowed, and written to
the audit log either way.
"""

from __future__ import annotations

import json
import time

import mcp_types as types
from mcp.server.lowlevel import Server

from ayman_hub import __version__
from ayman_hub.config import HubConfig
from ayman_hub.policy import ALLOW, decide
from ayman_hub.state import AuditLog, KillSwitch
from ayman_hub.upstream import Upstream

SEP = "__"
MAX_TOOL_NAME = 64
HUB_SPOKE = "hub"

STATUS_TOOL = types.Tool(
    name=f"{HUB_SPOKE}{SEP}status",
    title="Hub status",
    description="Which spokes are connected, how many tools each offers you, and whether the hub is switched off.",
    input_schema={"type": "object", "properties": {}},
    annotations=types.ToolAnnotations(read_only_hint=True, destructive_hint=False),
)


def _text(message: str, *, error: bool) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=message)], is_error=error)


def client_from_ctx(ctx) -> str:
    """The client name set by the key middleware in app.py."""
    request = getattr(ctx, "request", None)
    state = getattr(request, "scope", {}).get("state", {}) if request is not None else {}
    return state.get("hub_client", "unknown")


class Gateway:
    def __init__(self, config: HubConfig, upstreams: dict[str, Upstream], kill: KillSwitch, audit: AuditLog):
        self.config = config
        self.upstreams = upstreams
        self.kill = kill
        self.audit = audit

    # Tool listing -------------------------------------------------------
    def visible_tools(self, client: str) -> list[types.Tool]:
        tools = [STATUS_TOOL]
        if self.kill.is_off():
            return tools
        for name, up in self.upstreams.items():
            for tool in up.tools.values():
                exposed = f"{name}{SEP}{tool.name}"
                if len(exposed) > MAX_TOOL_NAME:
                    continue
                if decide(spoke=up.spoke, tool=tool, client=client, hub_off=False) is not ALLOW:
                    continue
                desc = f"[{name}] {tool.description or ''}".strip()
                tools.append(tool.model_copy(update={"name": exposed, "description": desc}))
        return tools

    def status(self, client: str) -> dict:
        return {
            "hub": self.config.name,
            "version": __version__,
            "switched_off": self.kill.is_off(),
            "client": client,
            "spokes": {
                name: {
                    "connected": up.session is not None,
                    "error": up.error,
                    "mode": up.spoke.mode,
                    "tools_for_you": sum(
                        1 for t in up.tools.values()
                        if decide(spoke=up.spoke, tool=t, client=client, hub_off=False) is ALLOW
                    ),
                }
                for name, up in self.upstreams.items()
            },
        }

    # Tool calls ---------------------------------------------------------
    async def call(self, client: str, name: str, arguments: dict | None) -> types.CallToolResult:
        started = time.monotonic()
        if name == STATUS_TOOL.name:
            self.audit.write(client=client, spoke=HUB_SPOKE, tool="status", allowed=True, reason="allowed", started=started)
            return _text(json.dumps(self.status(client), indent=2), error=False)

        spoke_name, sep, tool_name = name.partition(SEP)
        up = self.upstreams.get(spoke_name) if sep else None
        tool = up.tools.get(tool_name) if up else None
        if up is None or tool is None:
            self.audit.write(client=client, spoke=spoke_name or "?", tool=tool_name or name,
                             allowed=False, reason="unknown tool", started=started)
            return _text(f"Unknown tool '{name}'. Call hub__status to see what is connected.", error=True)

        decision = decide(spoke=up.spoke, tool=tool, client=client, hub_off=self.kill.is_off())
        if not decision.allowed:
            self.audit.write(client=client, spoke=spoke_name, tool=tool_name, allowed=False,
                             reason=decision.reason, started=started)
            return _text(f"Blocked by the hub: {decision.reason}.", error=True)

        try:
            result = await up.call(tool_name, arguments)
        except Exception as e:
            self.audit.write(client=client, spoke=spoke_name, tool=tool_name, allowed=True,
                             reason="allowed", started=started, error=type(e).__name__)
            return _text(f"The {spoke_name} service failed: {type(e).__name__}. Nothing was retried.", error=True)
        self.audit.write(client=client, spoke=spoke_name, tool=tool_name, allowed=True,
                         reason="allowed", started=started,
                         error="service returned an error" if result.is_error else None)
        return result

    # MCP server ---------------------------------------------------------
    def build_server(self) -> Server:
        async def on_list_tools(ctx, params):
            return types.ListToolsResult(tools=self.visible_tools(client_from_ctx(ctx)))

        async def on_call_tool(ctx, params: types.CallToolRequestParams):
            return await self.call(client_from_ctx(ctx), params.name, params.arguments)

        return Server(
            self.config.name,
            version=__version__,
            instructions=(
                "Ayman's hub: one door to his work services. Tools are named <service>__<tool>. "
                "Send, pay and delete-type tools don't exist here. Call hub__status to see what's connected."
            ),
            on_list_tools=on_list_tools,
            on_call_tool=on_call_tool,
        )
