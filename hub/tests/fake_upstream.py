"""A stand-in service for tests: one read tool, one write tool, one send tool, one destructive tool."""

import mcp_types as types
from mcp.server.mcpserver import MCPServer

server = MCPServer("fake")
ITEMS = ["alpha", "beta"]


@server.tool(annotations=types.ToolAnnotations(read_only_hint=True))
def list_items() -> str:
    """List items."""
    return ", ".join(ITEMS)


@server.tool(annotations=types.ToolAnnotations(read_only_hint=False, destructive_hint=False))
def create_item(name: str) -> str:
    """Create an item."""
    ITEMS.append(name)
    return f"created {name}"


@server.tool(annotations=types.ToolAnnotations(read_only_hint=False))
def send_message(to: str, body: str) -> str:
    """Send a message (must never be reachable through the hub)."""
    return f"SENT to {to}"


@server.tool(annotations=types.ToolAnnotations(read_only_hint=False, destructive_hint=True))
def archive_item(name: str) -> str:
    """Archive an item (destructive)."""
    return f"archived {name}"


if __name__ == "__main__":
    server.run("stdio")
