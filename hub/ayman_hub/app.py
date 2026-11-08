"""The web app: key check in front of the MCP endpoint, plus a health check.

    GET  /healthz   no key needed; says only whether the hub is up and switched on
    POST /mcp       MCP (Streamable HTTP); needs a hub key as `Authorization: Bearer <key>`
                    or `X-Hub-Key: <key>`
"""

from __future__ import annotations

import json
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from ayman_hub.config import HubConfig, hub_home
from ayman_hub.gateway import Gateway
from ayman_hub.state import AuditLog, ClientStore, KillSwitch
from ayman_hub.upstream import Upstream

log = logging.getLogger("ayman_hub")


class KeyAuth:
    """Pure ASGI middleware: every /mcp request needs a valid hub key. Sets scope['state']['hub_client']."""

    def __init__(self, app, clients: ClientStore, protected_prefix: str = "/mcp"):
        self.app = app
        self.clients = clients
        self.prefix = protected_prefix

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith(self.prefix):
            return await self.app(scope, receive, send)
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        key = headers.get("x-hub-key")
        auth = headers.get("authorization", "")
        if not key and auth.lower().startswith("bearer "):
            key = auth[7:].strip()
        client = self.clients.verify(key)
        if client is None:
            body = json.dumps({"error": "missing or invalid hub key"}).encode()
            await send({"type": "http.response.start", "status": 401,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"www-authenticate", b'Bearer realm="ayman-hub"')]})
            await send({"type": "http.response.body", "body": body})
            return
        scope.setdefault("state", {})["hub_client"] = client
        return await self.app(scope, receive, send)


def create_app(config: HubConfig, home: Path | None = None) -> Starlette:
    home = home or hub_home()
    clients, kill, audit = ClientStore(home), KillSwitch(home), AuditLog(home)
    upstreams = {s.name: Upstream(s) for s in config.enabled_spokes()}
    gateway = Gateway(config, upstreams, kill, audit)
    server = gateway.build_server()

    security = (
        TransportSecuritySettings(enable_dns_rebinding_protection=True,
                                  allowed_hosts=list(config.allowed_hosts),
                                  allowed_origins=[])
        if config.allowed_hosts
        else TransportSecuritySettings(enable_dns_rebinding_protection=False)
    )
    mcp_app = server.streamable_http_app(streamable_http_path="/mcp", transport_security=security)

    async def healthz(request: Request):
        return JSONResponse({"ok": True, "switched_off": kill.is_off()})

    @asynccontextmanager
    async def lifespan(app):
        async with AsyncExitStack() as stack:
            for up in upstreams.values():
                await up.start(stack)
            async with mcp_app.router.lifespan_context(mcp_app):
                yield

    app = Starlette(
        routes=[Route("/healthz", healthz), Mount("/", app=mcp_app)],
        lifespan=lifespan,
    )
    app.state.gateway = gateway
    return KeyAuth(app, clients)  # type: ignore[return-value]
