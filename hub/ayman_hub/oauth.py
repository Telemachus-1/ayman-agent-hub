"""One-time sign-in for spokes whose service uses OAuth (Notion, Granola, Slack).

    ayman-hub login <spoke>     prints a sign-in link; you open it, approve, and paste
                                back the address the browser lands on (works on a
                                headless server). `--listen` catches it on a local port.

What is stored, per spoke, in <hub home>/oauth/<spoke>.json (owner-only, 0600):
  - the access and refresh tokens, with the time the access token expires;
  - the client registration the service gave the hub (dynamic registration only);
  - the service's token endpoint, so refreshes go to the right place after a restart.

A pre-registered app's client secret (Slack) is read from the environment each time and
never written to disk. Tokens are never printed or logged.

At serve time the hub reuses the stored sign-in and refreshes it on its own. If the
sign-in is gone or revoked, the spoke goes down with "run `ayman-hub login <spoke>`";
the hub never opens a browser or waits for a person.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlparse

import anyio
from mcp.client.auth import OAuthClientProvider
from mcp.shared.auth import (
    AuthorizationCodeResult,
    OAuthClientInformationFull,
    OAuthClientMetadata,
    OAuthMetadata,
    OAuthToken,
    ProtectedResourceMetadata,
)

from ayman_hub.config import Spoke
from ayman_hub.state import _write_private


class NeedsLogin(RuntimeError):
    """The spoke has no usable sign-in. A person must run `ayman-hub login <spoke>`."""


class FileTokenStorage:
    """The SDK's TokenStorage, backed by one owner-only JSON file per spoke."""

    def __init__(self, home: Path, spoke: Spoke):
        self.spoke = spoke
        self.path = Path(home) / "oauth" / f"{spoke.name}.json"

    # --- file -------------------------------------------------------------
    def _read(self) -> dict:
        try:
            return json.loads(self.path.read_text())
        except FileNotFoundError:
            return {}

    def _write(self, data: dict) -> None:
        _write_private(self.path, json.dumps(data, indent=2))

    def signed_in(self) -> bool:
        return bool(self._read().get("tokens", {}).get("access_token"))

    def forget(self) -> bool:
        """Remove the stored sign-in. Returns False if there was none."""
        try:
            self.path.unlink()
            return True
        except FileNotFoundError:
            return False

    # --- pre-registered app (client id + secret from the environment) -----
    def _preregistered(self) -> OAuthClientInformationFull | None:
        if not self.spoke.oauth_client_id_env:
            return None
        client_id = os.environ.get(self.spoke.oauth_client_id_env)
        secret = os.environ.get(self.spoke.oauth_client_secret_env or "")
        if not client_id or not secret:
            raise NeedsLogin(
                f"environment variables {self.spoke.oauth_client_id_env} and "
                f"{self.spoke.oauth_client_secret_env} must be set"
            )
        return OAuthClientInformationFull(
            client_id=client_id,
            client_secret=secret,
            redirect_uris=[self.spoke.oauth_redirect_uri],
            token_endpoint_auth_method=self.spoke.oauth_token_auth,
            grant_types=["authorization_code", "refresh_token"],
            scope=self.spoke.oauth_scope,
        )

    # --- TokenStorage protocol --------------------------------------------
    async def get_tokens(self) -> OAuthToken | None:
        raw = self._read().get("tokens")
        if not raw or not raw.get("access_token"):
            return None
        expires_at = raw.pop("expires_at", None)
        token = OAuthToken.model_validate(raw)
        if expires_at is not None:
            # The SDK only knows expires_in; hand it the time that is actually left.
            token.expires_in = max(0, int(expires_at - time.time()))
        return token

    async def set_tokens(self, tokens: OAuthToken) -> None:
        data = self._read()
        raw = tokens.model_dump(mode="json", exclude_none=True)
        if tokens.expires_in is not None:
            raw["expires_at"] = time.time() + tokens.expires_in
        raw.pop("expires_in", None)
        data["tokens"] = raw
        data["updated"] = int(time.time())
        self._write(data)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        pre = self._preregistered()
        if pre is not None:
            return pre
        raw = self._read().get("client")
        return OAuthClientInformationFull.model_validate(raw) if raw else None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        if self.spoke.oauth_client_id_env:
            return  # a pre-registered app's secret stays in the environment only
        data = self._read()
        data["client"] = client_info.model_dump(mode="json", exclude_none=True)
        self._write(data)

    # --- discovered metadata, so refresh works after a restart -----------
    def save_metadata(self, provider: OAuthClientProvider) -> None:
        ctx = provider.context
        data = self._read()
        meta = {}
        if ctx.oauth_metadata is not None:
            meta["oauth"] = ctx.oauth_metadata.model_dump(mode="json", exclude_none=True)
        if ctx.protected_resource_metadata is not None:
            meta["resource"] = ctx.protected_resource_metadata.model_dump(mode="json", exclude_none=True)
        if ctx.auth_server_url:
            meta["auth_server_url"] = ctx.auth_server_url
        data["metadata"] = meta
        self._write(data)

    def load_metadata(self) -> dict:
        return self._read().get("metadata", {})


class HubOAuthProvider(OAuthClientProvider):
    """The SDK's OAuth provider with three hub changes:

    - restores the token's real expiry and the service's endpoints after a restart,
      so a lapsed access token is refreshed instead of starting a new sign-in;
    - a scope set in spokes.toml wins over what the service advertises;
    - outside `ayman-hub login` it never starts a browser sign-in (raises NeedsLogin).
    """

    def __init__(
        self,
        spoke: Spoke,
        storage: FileTokenStorage,
        redirect_handler: Callable | None = None,
        callback_handler: Callable | None = None,
    ):
        interactive = redirect_handler is not None
        if not interactive:
            async def redirect_handler(url: str) -> None:  # noqa: ARG001
                raise NeedsLogin(f"no valid sign-in for '{spoke.name}': run `ayman-hub login {spoke.name}`")

            async def callback_handler() -> AuthorizationCodeResult:
                raise NeedsLogin(f"no valid sign-in for '{spoke.name}': run `ayman-hub login {spoke.name}`")

        super().__init__(
            server_url=spoke.url,
            client_metadata=OAuthClientMetadata(
                client_name="Ayman agent hub",
                redirect_uris=[spoke.oauth_redirect_uri],
                grant_types=["authorization_code", "refresh_token"],
                response_types=["code"],
                scope=spoke.oauth_scope,
                token_endpoint_auth_method=spoke.oauth_token_auth if spoke.oauth_client_id_env else "none",
                application_type="native" if urlparse(spoke.oauth_redirect_uri).scheme == "http" else "web",
            ),
            storage=storage,
            redirect_handler=redirect_handler,
            callback_handler=callback_handler,
        )
        self._spoke = spoke
        self._storage = storage

    async def _initialize(self) -> None:
        await super()._initialize()
        if self.context.current_tokens is not None:
            self.context.update_token_expiry(self.context.current_tokens)
        meta = self._storage.load_metadata()
        if meta.get("oauth") and self.context.oauth_metadata is None:
            self.context.oauth_metadata = OAuthMetadata.model_validate(meta["oauth"])
        if meta.get("resource") and self.context.protected_resource_metadata is None:
            self.context.protected_resource_metadata = ProtectedResourceMetadata.model_validate(meta["resource"])
        if meta.get("auth_server_url") and not self.context.auth_server_url:
            self.context.auth_server_url = meta["auth_server_url"]

    async def _perform_authorization_code_grant(self) -> tuple[str, str]:
        if self._spoke.oauth_scope:
            self.context.client_metadata.scope = self._spoke.oauth_scope
        return await super()._perform_authorization_code_grant()


def parse_redirect(pasted: str) -> AuthorizationCodeResult:
    """Read code, state and issuer from the address the browser landed on."""
    query = parse_qs(urlparse(pasted.strip()).query)
    if "error" in query:
        raise RuntimeError(f"sign-in was refused: {query['error'][0]}")
    if "code" not in query:
        raise RuntimeError("that address has no ?code=…; paste the whole address from the browser bar")
    return AuthorizationCodeResult(
        code=query["code"][0],
        state=query.get("state", [None])[0],
        iss=query.get("iss", [None])[0],
    )


async def _listen_for_redirect(redirect_uri: str, timeout: float = 600) -> AuthorizationCodeResult:
    """Serve one request on the loopback redirect address and read the code from it."""
    parsed = urlparse(redirect_uri)
    result: dict = {}
    done = anyio.Event()

    async def handle(stream) -> None:
        async with stream:
            head = b""
            while b"\r\n\r\n" not in head and len(head) < 16384:
                chunk = await stream.receive(4096)
                if not chunk:
                    break
                head += chunk
            line = head.split(b"\r\n", 1)[0].decode("latin-1")
            target = line.split(" ")[1] if line.count(" ") >= 2 else "/"
            if urlparse(target).path != (parsed.path or "/"):
                await stream.send(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
                return
            try:
                result["value"] = parse_redirect(target)
                body = b"Signed in. You can close this tab and go back to the terminal."
            except RuntimeError as e:
                result["error"] = e
                body = str(e).encode()
            await stream.send(
                b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: "
                + str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n" + body
            )
            done.set()

    listener = await anyio.create_tcp_listener(local_host=parsed.hostname, local_port=parsed.port or 80)
    async with listener, anyio.create_task_group() as tg:
        tg.start_soon(listener.serve, handle)
        with anyio.fail_after(timeout):
            await done.wait()
        tg.cancel_scope.cancel()
    if "error" in result:
        raise result["error"]
    return result["value"]


async def login(
    spoke: Spoke,
    home: Path,
    *,
    listen: bool = False,
    say: Callable[[str], None] = print,
    ask: Callable[[str], str] = input,
    open_url: Callable[[str], object] | None = None,
) -> int:
    """Run the sign-in for one spoke and confirm it by listing the service's tools.

    `open_url` is for tests (it plays the browser); people get the link printed.
    Returns the number of tools the service offers once signed in.
    """
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

    if spoke.auth != "oauth":
        raise ValueError(f"'{spoke.name}' does not use sign-in (auth = \"{spoke.auth}\")")
    storage = FileTokenStorage(home, spoke)
    pending: dict = {}

    async def redirect_handler(url: str) -> None:
        pending["url"] = url
        if open_url is not None:
            pending["landed"] = await open_url(url)
            return
        say(f"\nSign in to {spoke.name} as Ayman. Open this link in your browser:\n\n  {url}\n")

    async def callback_handler() -> AuthorizationCodeResult:
        if "landed" in pending:
            return parse_redirect(pending["landed"])
        if listen:
            say(f"Waiting for the browser to come back to {spoke.oauth_redirect_uri} …")
            return await _listen_for_redirect(spoke.oauth_redirect_uri)
        pasted = await anyio.to_thread.run_sync(
            ask, "After approving, paste the full address your browser landed on (it may show an error page): "
        )
        return parse_redirect(pasted)

    provider = HubOAuthProvider(spoke, storage, redirect_handler, callback_handler)
    async with create_mcp_http_client(auth=provider) as http:
        async with streamable_http_client(spoke.url, http_client=http) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
    storage.save_metadata(provider)
    return len(tools.tools)
