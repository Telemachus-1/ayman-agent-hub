"""End to end: a real hub on a local port, a fake service behind it, an MCP client in front."""

import json
import socket
import sys
import threading
import time
from pathlib import Path

import anyio
import mcp_types as types
import pytest
import uvicorn
from mcp.client.session import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from ayman_hub.app import create_app
from ayman_hub.config import load_config
from ayman_hub.state import ClientStore, KillSwitch

FAKE = Path(__file__).resolve().parent / "fake_upstream.py"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def hub(tmp_path_factory):
    home = tmp_path_factory.mktemp("hubhome")
    cfg_path = home / "spokes.toml"
    cfg_path.write_text(f"""
[hub]
name = "test-hub"

[spokes.fake]
enabled = true
transport = "stdio"
command = "{sys.executable}"
args = ["{FAKE}"]
mode = "read-write"
allow_tools = ["create_item", "archive_item"]

[spokes.fakero]
enabled = true
transport = "stdio"
command = "{sys.executable}"
args = ["{FAKE}"]
mode = "read-only"
clients = ["claude"]

[spokes.broken]
enabled = true
transport = "http"
url = "https://example.invalid/mcp"
auth_env = "AYMAN_HUB_TEST_MISSING_TOKEN"
""")
    store = ClientStore(home)
    keys = {"claude": store.add("claude"), "grokbot": store.add("grokbot"), "old": store.add("old")}
    store.revoke("old")
    port = _free_port()
    app = create_app(load_config(cfg_path), home=home)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    assert server.started, "hub did not start"
    yield {"url": f"http://127.0.0.1:{port}", "keys": keys, "home": home}
    server.should_exit = True
    thread.join(timeout=10)


async def _session_run(url, key, fn):
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    async with create_mcp_http_client(headers=headers) as http:
        async with streamable_http_client(url + "/mcp", http_client=http) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await fn(session)


def run(url, key, fn):
    return anyio.run(_session_run, url, key, fn)


def text(result: types.CallToolResult) -> str:
    return " ".join(c.text for c in result.content if getattr(c, "type", "") == "text")


def test_health_needs_no_key(hub):
    import httpx2
    r = httpx2.get(hub["url"] + "/healthz")
    assert r.status_code == 200 and r.json() == {"ok": True, "switched_off": False}


@pytest.mark.parametrize("key", [None, "ahk_wrong", "not-a-hub-key"])
def test_mcp_refuses_missing_bad_and_revoked_keys(hub, key):
    import httpx2
    r = httpx2.post(hub["url"] + "/mcp", headers={"Authorization": f"Bearer {key}"} if key else {},
                    json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert r.status_code == 401
    r = httpx2.post(hub["url"] + "/mcp", headers={"X-Hub-Key": hub["keys"]["old"]},
                    json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert r.status_code == 401


def test_tool_list_is_filtered_per_client(hub):
    async def names(s):
        return sorted(t.name for t in (await s.list_tools()).tools)

    claude = run(hub["url"], hub["keys"]["claude"], names)
    assert claude == sorted([
        "hub__status",
        "fake__list_items", "fake__create_item",
        "fakero__list_items",
    ])
    # grokbot isn't on the read-only spoke's client list; nobody sees send or destructive tools.
    grok = run(hub["url"], hub["keys"]["grokbot"], names)
    assert grok == sorted(["hub__status", "fake__list_items", "fake__create_item"])


def test_calls_are_forwarded_or_blocked(hub):
    async def calls(s):
        out = {}
        out["read"] = text(await s.call_tool("fake__list_items", {}))
        out["write"] = text(await s.call_tool("fake__create_item", {"name": "gamma"}))
        sent = await s.call_tool("fake__send_message", {"to": "x@y.z", "body": "secret body"})
        out["send"] = (sent.is_error, text(sent))
        ro = await s.call_tool("fakero__create_item", {"name": "nope"})
        out["readonly"] = (ro.is_error, text(ro))
        out["unknown"] = (await s.call_tool("nothing__here", {})).is_error
        return out

    out = run(hub["url"], hub["keys"]["claude"], calls)
    assert "alpha" in out["read"]
    assert out["write"] == "created gamma"
    assert out["send"][0] and "blocked in code" in out["send"][1] and "SENT" not in out["send"][1]
    assert out["readonly"][0] and "read-only" in out["readonly"][1]
    assert out["unknown"] is True


def test_status_reports_a_broken_spoke_without_secrets(hub):
    async def status(s):
        return json.loads(text(await s.call_tool("hub__status", {})))

    st = run(hub["url"], hub["keys"]["claude"], status)
    assert st["client"] == "claude"
    assert st["spokes"]["fake"]["connected"] is True
    assert st["spokes"]["broken"]["connected"] is False
    # Agents get a fixed category, never raw error text or setting names.
    assert st["spokes"]["broken"]["problem"].startswith("missing settings")
    assert "AYMAN_HUB_TEST_MISSING_TOKEN" not in json.dumps(st)
    # ...and can see what is held back and why.
    hidden = st["spokes"]["fake"]["hidden_tools"]
    assert any("send_message" in names for names in hidden.values())


def test_audit_log_records_who_and_what_but_never_content(hub):
    lines = [json.loads(l) for l in (hub["home"] / "audit.jsonl").read_text().splitlines()]
    blocked = [l for l in lines if l["tool"] == "send_message"]
    assert blocked and blocked[0]["decision"] == "blocked" and blocked[0]["client"] == "claude"
    raw = (hub["home"] / "audit.jsonl").read_text()
    assert "secret body" not in raw and "x@y.z" not in raw and "gamma" not in raw


def test_kill_switch_refuses_everything_then_recovers(hub):
    kill = KillSwitch(hub["home"])

    async def try_read(s):
        tools = [t.name for t in (await s.list_tools()).tools]
        r = await s.call_tool("fake__list_items", {})
        return tools, r.is_error, text(r)

    kill.set_off(True)
    try:
        tools, err, msg = run(hub["url"], hub["keys"]["claude"], try_read)
        assert tools == ["hub__status"] and err and "kill switch" in msg
    finally:
        kill.set_off(False)
    tools, err, _ = run(hub["url"], hub["keys"]["claude"], try_read)
    assert "fake__list_items" in tools and not err


def test_files_are_owner_only(hub):
    for name in ("clients.json", "audit.jsonl"):
        assert (hub["home"] / name).stat().st_mode & 0o077 == 0
    assert "ahk_" not in (hub["home"] / "clients.json").read_text()
