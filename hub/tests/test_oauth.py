"""Sign-in spokes: login, owner-only storage, refresh after restart, pre-registered apps."""

import json
import socket
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path

import anyio
import httpx2
import mcp_types as types
import pytest
import uvicorn
from mcp.client.session import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from ayman_hub.app import create_app
from ayman_hub.config import ConfigError, load_config
from ayman_hub.oauth import FileTokenStorage, _listen_for_redirect, login, parse_redirect
from ayman_hub.state import ClientStore

FAKE = Path(__file__).resolve().parent / "fake_oauth_upstream.py"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def service(tmp_path_factory):
    state = tmp_path_factory.mktemp("fakeoauth")
    port = _free_port()
    proc = subprocess.Popen([sys.executable, str(FAKE), str(port), str(state)])
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            httpx2.get(base + "/.well-known/oauth-authorization-server", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    else:
        proc.kill()
        pytest.fail("fake OAuth service did not start")
    yield {"base": base, "log": state / "log.jsonl"}
    proc.terminate()
    proc.wait(timeout=10)


def events(service, name):
    if not service["log"].exists():
        return []
    rows = [json.loads(line) for line in service["log"].read_text().splitlines()]
    return [r for r in rows if r["event"] == name]


def write_config(tmp_path, service, extra=""):
    path = tmp_path / "spokes.toml"
    path.write_text(f"""
[spokes.docs]
enabled = true
transport = "http"
url = "{service['base']}/mcp"
auth = "oauth"
mode = "read-write"
{extra}
""")
    return load_config(path)


async def browser(url: str) -> str:
    """Plays the person: opens the sign-in link, approves, returns where the browser lands."""
    async with httpx2.AsyncClient() as c:
        r = await c.get(url, follow_redirects=False)
        assert r.status_code in (302, 307), r.text
        return r.headers["location"]


def do_login(spoke, home, said):
    return anyio.run(lambda: login(spoke, home, say=said.append, open_url=browser))


def test_login_stores_signin_owner_only_and_never_prints_it(tmp_path, service):
    spoke = write_config(tmp_path, service).spokes["docs"]
    home = tmp_path / "home"
    said = []
    before = len(events(service, "register"))
    assert do_login(spoke, home, said) == 2
    path = home / "oauth" / "docs.json"
    data = json.loads(path.read_text())
    assert data["tokens"]["access_token"].startswith("at_")
    assert "expires_at" in data["tokens"] and data["metadata"]["oauth"]["token_endpoint"]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert len(events(service, "register")) == before + 1  # dynamic registration
    printed = "\n".join(said)
    assert "at_" not in printed and "rt_" not in printed
    assert FileTokenStorage(home, spoke).signed_in()


def _serve(app):
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    assert server.started
    return server, thread, f"http://127.0.0.1:{port}"


def _call(url, key, tool, args):
    async def go():
        async with create_mcp_http_client(headers={"X-Hub-Key": key}) as http:
            async with streamable_http_client(url + "/mcp", http_client=http) as (read, write):
                async with ClientSession(read, write) as s:
                    await s.initialize()
                    names = sorted(t.name for t in (await s.list_tools()).tools)
                    result = await s.call_tool(tool, args)
                    text = " ".join(c.text for c in result.content if getattr(c, "type", "") == "text")
                    return names, result.is_error, text

    return anyio.run(go)


def test_hub_uses_stored_signin_and_refreshes_after_restart(tmp_path, service):
    config = write_config(tmp_path, service)
    home = tmp_path / "home"
    do_login(config.spokes["docs"], home, [])
    key = ClientStore(home).add("claude")
    registers, authorizes = len(events(service, "register")), len(events(service, "authorize"))

    server, thread, url = _serve(create_app(config, home=home))
    try:
        names, err, text = _call(url, key, "docs__search_pages", {"query": "brand rules"})
        assert not err and "found 2 pages" in text
        assert "docs__delete_page" not in names  # hard-denied in code
        refreshes = len(events(service, "refresh"))
        time.sleep(3)  # access token lives 2 seconds
        names, err, text = _call(url, key, "docs__search_pages", {"query": "again"})
        assert not err and "found 2 pages" in text
        assert len(events(service, "refresh")) > refreshes
    finally:
        server.should_exit = True
        thread.join(timeout=10)

    # A restart after expiry refreshes from storage; it never registers or signs in again.
    time.sleep(3)
    server, thread, url = _serve(create_app(config, home=home))
    try:
        _, err, text = _call(url, key, "docs__search_pages", {"query": "after restart"})
        assert not err and "found 2 pages" in text
    finally:
        server.should_exit = True
        thread.join(timeout=10)
    assert len(events(service, "register")) == registers
    assert len(events(service, "authorize")) == authorizes
    stored = (home / "oauth" / "docs.json").read_text()
    assert "at_" in stored  # the rotated tokens were saved


def test_spoke_without_signin_says_how_to_fix(tmp_path, service):
    config = write_config(tmp_path, service)
    home = tmp_path / "home2"
    key = ClientStore(home).add("claude")
    server, thread, url = _serve(create_app(config, home=home))
    try:
        names, err, text = _call(url, key, "hub__status", {})
    finally:
        server.should_exit = True
        thread.join(timeout=10)
    assert names == ["hub__status"]
    assert "ayman-hub login docs" in text


def test_preregistered_app_secret_stays_out_of_the_hub_home(tmp_path, service, monkeypatch):
    monkeypatch.setenv("TEST_SLACK_ID", "slackapp")
    monkeypatch.setenv("TEST_SLACK_SECRET", "slack-secret")
    spoke = write_config(tmp_path, service, extra="""
oauth_client_id_env = "TEST_SLACK_ID"
oauth_client_secret_env = "TEST_SLACK_SECRET"
""").spokes["docs"]
    home = tmp_path / "home3"
    registers = len(events(service, "register"))
    assert do_login(spoke, home, []) == 2
    assert len(events(service, "register")) == registers  # no dynamic registration
    tokens = [e for e in events(service, "token") if e["client_id"] == "slackapp"]
    assert tokens and tokens[-1]["secret_used"]
    stored = (home / "oauth" / "docs.json").read_text()
    assert "slack-secret" not in stored and "client" not in json.loads(stored)


def test_preregistered_app_without_env_fails_clearly(tmp_path, service, monkeypatch):
    monkeypatch.delenv("TEST_SLACK_ID", raising=False)
    spoke = write_config(tmp_path, service, extra="""
oauth_client_id_env = "TEST_SLACK_ID"
oauth_client_secret_env = "TEST_SLACK_SECRET"
""").spokes["docs"]
    with pytest.raises(BaseException) as e:
        do_login(spoke, tmp_path / "home4", [])
    print("RAISED", type(e.value), repr(e.value))
    assert "TEST_SLACK_ID" in _flatten(e.value)


def _flatten(exc: BaseException) -> str:
    parts = [repr(exc)]
    for sub in getattr(exc, "exceptions", ()):
        parts.append(_flatten(sub))
    if exc.__cause__:
        parts.append(_flatten(exc.__cause__))
    if exc.__context__ and exc.__context__ is not exc.__cause__:
        parts.append(_flatten(exc.__context__))
    return " ".join(parts)


def test_parse_redirect():
    r = parse_redirect("http://127.0.0.1:8743/callback?code=abc&state=xyz&iss=https%3A%2F%2Fa.b")
    assert (r.code, r.state, r.iss) == ("abc", "xyz", "https://a.b")
    with pytest.raises(RuntimeError, match="refused"):
        parse_redirect("http://127.0.0.1:8743/callback?error=access_denied")
    with pytest.raises(RuntimeError, match="no \\?code"):
        parse_redirect("http://127.0.0.1:8743/callback")


def test_listen_catches_the_browser_return():
    port = _free_port()
    redirect = f"http://127.0.0.1:{port}/callback"

    async def go():
        async with anyio.create_task_group() as tg:
            result = {}

            async def wait():
                result["r"] = await _listen_for_redirect(redirect, timeout=10)

            tg.start_soon(wait)
            await anyio.sleep(0.3)
            async with httpx2.AsyncClient() as c:
                miss = await c.get(f"http://127.0.0.1:{port}/favicon.ico")
                assert miss.status_code == 404
                ok = await c.get(redirect + "?code=c1&state=s1")
                assert "Signed in" in ok.text
        return result["r"]

    r = anyio.run(go)
    assert (r.code, r.state) == ("c1", "s1")


@pytest.mark.parametrize("body, message", [
    ('auth = "oauth"\nauth_env = "X"', "not both"),
    ('auth = "oauth"\ntransport = "stdio"\ncommand = "x"', "only works on http"),
    ('oauth_scope = "read"', "need auth"),
    ('auth = "oauth"\noauth_client_id_env = "A"', "both"),
    ('auth = "oauth"\noauth_redirect_uri = "http://127.0.0.1.evil.com/cb"', "loopback"),
    ('auth = "bearer"', "needs auth_env"),
])
def test_config_rejects_bad_signin_settings(tmp_path, body, message):
    path = tmp_path / "spokes.toml"
    lines = ['[spokes.x]', 'enabled = true', 'url = "https://a.example/mcp"']
    if 'transport = "stdio"' not in body:
        lines.insert(2, 'transport = "http"')
    path.write_text("\n".join(lines) + "\n" + body + "\n")
    with pytest.raises(ConfigError, match=message):
        load_config(path)
