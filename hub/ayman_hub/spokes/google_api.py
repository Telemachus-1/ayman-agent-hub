"""Shared Google access for the hub's own Google and Gmail spokes.

One Google sign-in (as ayman@telemachus.io) serves both spokes:

    ayman-hub google-login [--listen]

It needs the hub's Google OAuth client (a "Desktop app" client in Telemachus's Google
Cloud project) in the environment: GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET.
The refresh token is stored owner-only in <hub home>/oauth/google-account.json.

Calendar is signed in read-only (the scope itself can't change events). Gmail uses the
modify scope, which Google ties to sending too, so "never send" is enforced by the Gmail
spoke having no send tool and the hub blocking send-type names in code.

Rate limits: a 429 is never retried. The call stops and says so (Basil's Gmail rule).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urlencode

import anyio
import httpx2
from mcp.server.mcpserver.exceptions import ToolError

from ayman_hub.state import _write_private

EXPECTED_ACCOUNT = "ayman@telemachus.io"
SCOPES = [
    "openid",
    "email",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]
REDIRECT = "http://127.0.0.1:8743/callback"
ACCOUNT_FILE = "google-account.json"


def _hosts() -> dict[str, str]:
    """Google's API addresses. GOOGLE_API_BASE points them all at a stand-in for tests."""
    base = os.environ.get("GOOGLE_API_BASE")
    if base:
        base = base.rstrip("/")
        return {
            "auth": f"{base}/o/oauth2/v2/auth",
            "token": f"{base}/token",
            "userinfo": f"{base}/oauth2/v3/userinfo",
            "drive": f"{base}/drive/v3",
            "docs": f"{base}/docs/v1",
            "sheets": f"{base}/sheets/v4",
            "slides": f"{base}/slides/v1",
            "calendar": f"{base}/calendar/v3",
            "gmail": f"{base}/gmail/v1",
        }
    return {
        "auth": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "userinfo": "https://openidconnect.googleapis.com/v1/userinfo",
        "drive": "https://www.googleapis.com/drive/v3",
        "docs": "https://docs.googleapis.com/v1",
        "sheets": "https://sheets.googleapis.com/v4",
        "slides": "https://slides.googleapis.com/v1",
        "calendar": "https://www.googleapis.com/calendar/v3",
        "gmail": "https://gmail.googleapis.com/gmail/v1",
    }


def seg(value: str) -> str:
    """Encode one URL path segment (ids, ranges, calendar ids)."""
    return quote(str(value), safe="")


class GoogleError(ToolError):
    """A Google call failed. The message is safe to show (it never holds tokens), so it is
    passed to the agent as the tool's error instead of being hidden as a crash."""


class RateLimited(GoogleError):
    """Google said 429. Never retried."""


def _home() -> Path:
    return Path(os.environ.get("AYMAN_HUB_HOME", "~/.ayman-hub")).expanduser()


def _client_creds() -> tuple[str, str]:
    cid, secret = os.environ.get("GOOGLE_OAUTH_CLIENT_ID"), os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    if not cid or not secret:
        raise GoogleError("GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET must be set")
    return cid, secret


class GoogleClient:
    """Authorised calls to Google APIs with the stored sign-in."""

    def __init__(self, home: Path | None = None):
        self.path = (home or _home()) / "oauth" / ACCOUNT_FILE
        self._access: str | None = None
        self._expires = 0.0
        self.hosts = _hosts()
        self._http = httpx2.AsyncClient(timeout=60)

    async def aclose(self) -> None:
        await self._http.aclose()

    def _refresh_token(self) -> str:
        try:
            token = json.loads(self.path.read_text()).get("refresh_token")
        except FileNotFoundError:
            token = None
        if not token:
            raise GoogleError("not signed in to Google: run `ayman-hub google-login`")
        return token

    async def _token(self, force: bool = False) -> str:
        if self._access and not force and time.time() < self._expires - 60:
            return self._access
        cid, secret = _client_creds()
        r = await self._http.post(self.hosts["token"], data={
            "grant_type": "refresh_token", "refresh_token": self._refresh_token(),
            "client_id": cid, "client_secret": secret,
        })
        if r.status_code == 429:
            raise RateLimited("Google rate limit (429) while refreshing the sign-in. Stopped, not retried.")
        if r.status_code != 200:
            err = _error_text(r)
            try:
                code = r.json().get("error")
            except Exception:
                code = None
            if code == "invalid_grant":
                raise GoogleError("the Google sign-in was revoked or expired: run `ayman-hub google-login`")
            raise GoogleError(f"Google sign-in refresh failed ({r.status_code}): {err}")
        body = r.json()
        self._access = body["access_token"]
        self._expires = time.time() + int(body.get("expires_in", 3600))
        return self._access

    async def request(self, method: str, api: str, path: str, *, params: dict | None = None,
                      json_body: Any = None, raw: bool = False) -> Any:
        url = self.hosts[api] + path
        for attempt in (1, 2):
            headers = {"Authorization": f"Bearer {await self._token(force=attempt == 2)}"}
            r = await self._http.request(method, url, params=params, json=json_body, headers=headers)
            if r.status_code == 401 and attempt == 1:
                continue  # access token lapsed early: refresh once (this is not a rate-limit retry)
            break
        if r.status_code == 429:
            raise RateLimited(f"Google rate limit (429) on {api}. Stopped, not retried. Try again later.")
        if r.status_code >= 400:
            raise GoogleError(f"Google {api} said {r.status_code}: {_error_text(r)}")
        if raw:
            return r
        return r.json() if r.content else {}


def _error_text(r: httpx2.Response) -> str:
    try:
        body = r.json()
    except Exception:
        return r.text[:200]
    err = body.get("error")
    if isinstance(err, dict):
        return str(err.get("message", err))[:200]
    return str(body.get("error_description") or err or body)[:200]


# --- one-time sign-in -----------------------------------------------------

def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


async def google_login(
    home: Path,
    *,
    account: str = EXPECTED_ACCOUNT,
    listen: bool = False,
    say: Callable[[str], None] = print,
    ask: Callable[[str], str] = input,
    open_url: Callable | None = None,
) -> str:
    """Sign in once as `account`. Refuses any other account. Returns the account signed in."""
    from ayman_hub.oauth import _listen_for_redirect, parse_redirect

    hosts = _hosts()
    cid, secret = _client_creds()
    verifier, challenge = _pkce()
    state = secrets.token_urlsafe(24)
    url = hosts["auth"] + "?" + urlencode({
        "client_id": cid, "redirect_uri": REDIRECT, "response_type": "code",
        "scope": " ".join(SCOPES), "access_type": "offline", "prompt": "consent",
        "code_challenge": challenge, "code_challenge_method": "S256", "state": state,
        "login_hint": account, "include_granted_scopes": "true",
    })
    if open_url is not None:
        landed = parse_redirect(await open_url(url))
    else:
        say(f"\nSign in to Google as {account}. Open this link in your browser:\n\n  {url}\n")
        if listen:
            landed = await _listen_for_redirect(REDIRECT)
        else:
            landed = parse_redirect(await anyio.to_thread.run_sync(
                ask, "After approving, paste the full address your browser landed on: "))
    if not landed.state or not secrets.compare_digest(landed.state, state):
        raise GoogleError("sign-in state did not match; start again")

    async with httpx2.AsyncClient(timeout=60) as http:
        r = await http.post(hosts["token"], data={
            "grant_type": "authorization_code", "code": landed.code, "redirect_uri": REDIRECT,
            "client_id": cid, "client_secret": secret, "code_verifier": verifier,
        })
        if r.status_code != 200:
            raise GoogleError(f"Google refused the sign-in ({r.status_code}): {_error_text(r)}")
        tokens = r.json()
        if not tokens.get("refresh_token"):
            raise GoogleError("Google gave no refresh token; remove the hub's access in your Google account and retry")
        granted = set(tokens.get("scope", "").split())
        missing = [s for s in SCOPES if s not in granted and s not in ("openid", "email")]
        who = await http.get(hosts["userinfo"], headers={"Authorization": f"Bearer {tokens['access_token']}"})
        email = who.json().get("email", "") if who.status_code == 200 else ""
    if email.lower() != account.lower():
        raise GoogleError(f"signed in as {email or 'an unknown account'}, not {account}; nothing was stored")
    if missing:
        raise GoogleError(f"these permissions were not granted, so nothing was stored: {', '.join(missing)}")
    _write_private(home / "oauth" / ACCOUNT_FILE, json.dumps({
        "account": email, "refresh_token": tokens["refresh_token"], "scopes": sorted(granted),
        "updated": int(time.time()),
    }, indent=2))
    return email


def google_signed_in(home: Path) -> str | None:
    try:
        data = json.loads((home / "oauth" / ACCOUNT_FILE).read_text())
    except FileNotFoundError:
        return None
    return data.get("account") if data.get("refresh_token") else None
