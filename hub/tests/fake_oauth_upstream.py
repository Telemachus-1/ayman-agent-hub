"""A stand-in service that needs OAuth sign-in, like Notion, Granola or Slack.

Run:  python fake_oauth_upstream.py <port> <state-dir>
It registers clients (DCR), approves every sign-in at once, issues short-lived access
tokens and rotating refresh tokens, and records what it did in <state-dir>/log.jsonl so
tests can check refreshes, registrations and which client secret was used.
A pre-registered confidential client "slackapp" / "slack-secret" also exists.
"""

import json
import secrets
import sys
import time
from pathlib import Path

import mcp_types as types
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.mcpserver import MCPServer
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

PORT = int(sys.argv[1])
STATE = Path(sys.argv[2])
ACCESS_TTL = 2  # seconds: short, so tests see a refresh
BASE = f"http://127.0.0.1:{PORT}"


def record(event: str, **fields) -> None:
    with (STATE / "log.jsonl").open("a") as f:
        f.write(json.dumps({"event": event, **fields}) + "\n")


class Provider:
    def __init__(self):
        self.clients = {
            "slackapp": OAuthClientInformationFull(
                client_id="slackapp",
                client_secret="slack-secret",
                redirect_uris=["http://127.0.0.1:8743/callback"],
                token_endpoint_auth_method="client_secret_post",
                grant_types=["authorization_code", "refresh_token"],
            )
        }
        self.codes: dict[str, AuthorizationCode] = {}
        self.access: dict[str, AccessToken] = {}
        self.refresh: dict[str, RefreshToken] = {}

    async def get_client(self, client_id):
        return self.clients.get(client_id)

    async def register_client(self, client_info):
        self.clients[client_info.client_id] = client_info
        record("register", client_id=client_info.client_id)

    async def authorize(self, client, params: AuthorizationParams) -> str:
        code = secrets.token_urlsafe(16)
        self.codes[code] = AuthorizationCode(
            code=code, scopes=params.scopes or [], expires_at=time.time() + 300, client_id=client.client_id,
            code_challenge=params.code_challenge, redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly, resource=params.resource,
        )
        record("authorize", client_id=client.client_id, scopes=params.scopes or [])
        return construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state, iss=BASE)

    async def load_authorization_code(self, client, code):
        return self.codes.get(code)

    def _issue(self, client_id, scopes, resource) -> OAuthToken:
        at, rt = "at_" + secrets.token_urlsafe(16), "rt_" + secrets.token_urlsafe(16)
        self.access[at] = AccessToken(token=at, client_id=client_id, scopes=scopes,
                                      expires_at=int(time.time()) + ACCESS_TTL, resource=resource)
        self.refresh[rt] = RefreshToken(token=rt, client_id=client_id, scopes=scopes, resource=resource)
        return OAuthToken(access_token=at, expires_in=ACCESS_TTL, refresh_token=rt, scope=" ".join(scopes) or None)

    async def exchange_authorization_code(self, client, code):
        self.codes.pop(code.code, None)
        record("token", client_id=client.client_id, secret_used=bool(client.client_secret))
        return self._issue(client.client_id, code.scopes, code.resource)

    async def load_refresh_token(self, client, token):
        return self.refresh.get(token)

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        self.refresh.pop(refresh_token.token, None)  # rotate
        record("refresh", client_id=client.client_id)
        return self._issue(client.client_id, scopes or refresh_token.scopes, refresh_token.resource)

    async def load_access_token(self, token):
        at = self.access.get(token)
        if at and at.expires_at and at.expires_at < time.time():
            return None
        return at

    async def revoke_token(self, token):
        self.access.pop(getattr(token, "token", ""), None)


server = MCPServer(
    "fake-oauth",
    auth_server_provider=Provider(),
    auth=AuthSettings(
        issuer_url=BASE,
        resource_server_url=f"{BASE}/mcp",
        client_registration_options=ClientRegistrationOptions(enabled=True, valid_scopes=["read", "write"],
                                                              default_scopes=["read"]),
        required_scopes=[],
    ),
)


@server.tool(annotations=types.ToolAnnotations(read_only_hint=True))
def search_pages(query: str) -> str:
    """Search pages."""
    return f"found 2 pages for {query}"


@server.tool(annotations=types.ToolAnnotations(read_only_hint=False))
def delete_page(page_id: str) -> str:
    """Delete a page (must never be reachable through the hub)."""
    return f"DELETED {page_id}"


if __name__ == "__main__":
    import uvicorn

    STATE.mkdir(parents=True, exist_ok=True)
    uvicorn.run(server.streamable_http_app(), host="127.0.0.1", port=PORT, log_level="warning")
