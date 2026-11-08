"""The hub's own Google and Gmail spokes, run through a real hub against a stand-in Google."""

import json
import os
import socket
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path

import anyio
import httpx2
import pytest
import uvicorn
from mcp.client.session import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from ayman_hub.app import create_app
from ayman_hub.config import load_config
from ayman_hub.spokes import gmail
from ayman_hub.spokes.google_api import GoogleClient, GoogleError, google_login, google_signed_in
from ayman_hub.state import ClientStore

HUB_DIR = Path(__file__).resolve().parent.parent
FAKE = Path(__file__).resolve().parent / "fake_google.py"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def google(tmp_path_factory):
    state = tmp_path_factory.mktemp("fakegoogle")
    port = _free_port()
    proc = subprocess.Popen([sys.executable, str(FAKE), str(port), str(state)])
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            httpx2.get(base + "/seed?rt=warmup", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    else:
        proc.kill()
        pytest.fail("fake Google did not start")
    saved = {k: os.environ.get(k) for k in ("GOOGLE_API_BASE", "GOOGLE_OAUTH_CLIENT_ID",
                                            "GOOGLE_OAUTH_CLIENT_SECRET", "PYTHONPATH", "AYMAN_HUB_TESTING")}
    os.environ.update(GOOGLE_API_BASE=base, GOOGLE_OAUTH_CLIENT_ID="hub-client", AYMAN_HUB_TESTING="1",
                      GOOGLE_OAUTH_CLIENT_SECRET="hub-secret", PYTHONPATH=str(HUB_DIR))
    yield {"base": base, "log": state / "log.jsonl"}
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    proc.terminate()
    proc.wait(timeout=10)


def requests(google, path_part=""):
    rows = [json.loads(x) for x in google["log"].read_text().splitlines()] if google["log"].exists() else []
    return [r for r in rows if path_part in r["path"]]


async def browser(url: str) -> str:
    async with httpx2.AsyncClient() as c:
        r = await c.get(url, follow_redirects=False)
        assert r.status_code == 302, r.text
        return r.headers["location"]


# --- sign-in ----------------------------------------------------------------

def test_google_login_stores_only_the_refresh_token(tmp_path, google):
    email = anyio.run(lambda: google_login(tmp_path, open_url=browser))
    assert email == "ayman@telemachus.io" == google_signed_in(tmp_path)
    path = tmp_path / "oauth" / "google-account.json"
    data = json.loads(path.read_text())
    assert data["refresh_token"].startswith("1//") and "ya29." not in path.read_text()
    assert "https://www.googleapis.com/auth/calendar.readonly" in data["scopes"]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    auth = requests(google, "/o/oauth2/v2/auth")[-1]["query"]
    assert auth["access_type"] == "offline" and auth["code_challenge_method"] == "S256"
    assert "calendar.readonly" in auth["scope"] and "auth/calendar " not in auth["scope"] + " "
    assert "include_granted_scopes" not in auth and auth["hd"] == "telemachus.io"


def test_google_login_refuses_another_account(tmp_path, google):
    with pytest.raises(GoogleError, match="not wrong@telemachus.io"):
        anyio.run(lambda: google_login(tmp_path, account="wrong@telemachus.io", open_url=browser))
    assert google_signed_in(tmp_path) is None


def test_google_login_refuses_missing_permissions(tmp_path, google):
    with pytest.raises(GoogleError, match="gmail.modify"):
        anyio.run(lambda: google_login(tmp_path, account="drop_scope@telemachus.io", open_url=browser))
    assert google_signed_in(tmp_path) is None


def test_google_login_refuses_wider_permissions(tmp_path, google):
    with pytest.raises(GoogleError, match="wider permissions"):
        anyio.run(lambda: google_login(tmp_path, account="extra_scope@telemachus.io", open_url=browser))
    assert google_signed_in(tmp_path) is None


def test_test_address_is_ignored_outside_tests(monkeypatch):
    from ayman_hub.spokes.google_api import _hosts
    monkeypatch.setenv("GOOGLE_API_BASE", "http://evil.example")
    monkeypatch.delenv("AYMAN_HUB_TESTING")
    assert _hosts()["token"] == "https://oauth2.googleapis.com/token"


def test_revoked_signin_says_how_to_fix(tmp_path, google):
    (tmp_path / "oauth").mkdir()
    (tmp_path / "oauth" / "google-account.json").write_text(json.dumps({"refresh_token": "1//revoked"}))

    async def go():
        c = GoogleClient(tmp_path)
        try:
            await c.request("GET", "drive", "/files")
        finally:
            await c.aclose()

    with pytest.raises(GoogleError, match="google-login"):
        anyio.run(go)


# --- through the hub --------------------------------------------------------

@pytest.fixture(scope="module")
def hub(google, tmp_path_factory):
    home = tmp_path_factory.mktemp("googlehub")
    (home / "oauth").mkdir(mode=0o700)
    (home / "oauth" / "google-account.json").write_text(
        json.dumps({"account": "ayman@telemachus.io", "refresh_token": "1//seeded"}))
    httpx2.get(google["base"] + "/seed?rt=1//seeded")
    cfg = home / "spokes.toml"
    passthrough = ('["GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_API_BASE", '
                   '"AYMAN_HUB_TESTING", "PYTHONPATH"]')
    cfg.write_text(f"""
[spokes.google]
enabled = true
transport = "stdio"
command = "@python"
args = ["-m", "ayman_hub.spokes.google", "--internal-domains", "telemachus.io"]
env_passthrough = {passthrough}
mode = "read-write"
deny_tools = ["*share*", "*permission*", "*trash*", "calendar_*create*", "calendar_*update*"]
allow_tools = ["docs_create", "docs_append_text", "docs_replace_text", "sheets_create", "sheets_append_rows",
               "sheets_update_range", "slides_create", "slides_replace_text"]
allow_destructive = ["docs_replace_text", "sheets_update_range"]

[spokes.gmail]
enabled = true
transport = "stdio"
command = "@python"
args = ["-m", "ayman_hub.spokes.gmail"]
env_passthrough = {passthrough}
mode = "read-write"
deny_tools = ["*spam*", "*filter*", "*forward*", "*vacation*"]
allow_tools = ["gmail_label_thread", "gmail_archive_thread", "gmail_create_label"]
""")
    key = ClientStore(home).add("claude")
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(load_config(cfg), home=home), host="127.0.0.1",
                                           port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(150):
        if server.started:
            break
        time.sleep(0.1)
    assert server.started
    yield {"url": f"http://127.0.0.1:{port}", "key": key}
    server.should_exit = True
    thread.join(timeout=10)


def session(hub, fn):
    async def go():
        async with create_mcp_http_client(headers={"X-Hub-Key": hub["key"]}) as http:
            async with streamable_http_client(hub["url"] + "/mcp", http_client=http) as (read, write):
                async with ClientSession(read, write) as s:
                    await s.initialize()
                    return await fn(s)
    return anyio.run(go)


def call(hub, tool, **args):
    async def fn(s):
        r = await s.call_tool(tool, args)
        return r.is_error, " ".join(c.text for c in r.content if getattr(c, "type", "") == "text")
    return session(hub, fn)


def test_tools_offered(hub):
    async def fn(s):
        return sorted(t.name for t in (await s.list_tools()).tools)

    names = session(hub, fn)
    assert "google__drive_search" in names and "gmail__gmail_search" in names
    # overwrite tools only where spokes.toml allows them
    assert "google__docs_replace_text" in names and "google__sheets_update_range" in names
    assert "google__slides_replace_text" not in names
    for word in ("send", "reply", "forward", "draft", "trash", "delete", "share", "unsubscribe", "spam"):
        assert not [n for n in names if word in n], word


def test_drive(hub, google):
    err, text = call(hub, "google__drive_search", query="O'Brien", kind="doc")
    assert not err and "Brand rules" in text and '"next_page_token": "p2"' in text
    q = requests(google, "/drive/v3/files")[-1]["query"]
    assert q["q"] == "trashed = false and fullText contains 'O\\'Brien' and mimeType = 'application/vnd.google-apps.document'"
    assert q["corpora"] == "allDrives" and q["supportsAllDrives"] == "true"
    assert "Use Valen only" in call(hub, "google__drive_read_file", file_id="doc1")[1]
    assert "5012345678900,9.99" in call(hub, "google__drive_read_file", file_id="sheet1")[1]
    assert "hello notes" in call(hub, "google__drive_read_file", file_id="txt1")[1]
    assert "can't be read as text" in call(hub, "google__drive_read_file", file_id="img1")[1]
    err, text = call(hub, "google__drive_get_file", file_id="nope")
    assert err and "404" in text


def test_docs(hub):
    text = call(hub, "google__docs_read", document_id="doc1")[1]
    assert "# Brand rules" in text and "Brand | Valen" in text
    created = json.loads(call(hub, "google__docs_create", title="Valen supplier brief", text="Intro\n")[1])
    did = created["document_id"]
    assert created["link"].endswith(f"/document/d/{did}/edit")
    call(hub, "google__docs_append_text", document_id=did, text="More\n")
    assert "Replaced 1 occurrence" in call(hub, "google__docs_replace_text", document_id=did,
                                           find="Intro", replace_with="Summary")[1]
    text = call(hub, "google__docs_read", document_id=did)[1]
    assert "Summary\nMore" in text


def test_sheets(hub, google):
    assert "Prices" in call(hub, "google__sheets_get", spreadsheet_id="sheet1")[1]
    assert "5012345678900" in call(hub, "google__sheets_read_range", spreadsheet_id="sheet1", range="Prices!A1:B5")[1]
    assert "Added 1 row" in call(hub, "google__sheets_append_rows", spreadsheet_id="sheet1",
                                 range="Prices!A:B", rows=[["5000000000001", "=1+1"]])[1]
    assert "Updated 2 cell" in call(hub, "google__sheets_update_range", spreadsheet_id="sheet1",
                                    range="Prices!A1:B1", values=[["EAN", "RRP"]])[1]
    csv_text = call(hub, "google__sheets_read_range", spreadsheet_id="sheet1", range="Prices", as_csv=True)[1]
    assert csv_text.splitlines()[0] == "EAN,RRP" and "5000000000001,=1+1" in csv_text
    created = json.loads(call(hub, "google__sheets_create", title="Tracker", tabs=["Open", "Done"],
                              folder_id="folderX")[1])
    assert created["spreadsheet_id"].startswith("sheet")
    patch = [r for r in requests(google, "/drive/v3/files/") if r["method"] == "PATCH"][-1]
    assert patch["query"]["addParents"] == "folderX"
    err, text = call(hub, "google__sheets_read_range", spreadsheet_id="sheet1", range="Nope!A1")
    assert err and "Unable to parse range" in text


def test_no_writes_to_files_shared_outside(hub, google):
    err, text = call(hub, "google__sheets_append_rows", spreadsheet_id="shared1", range="Orders!A:B",
                     rows=[["PO1", "5"]])
    assert err and "orders@supplier.example" not in text and "someone at supplier.example" in text
    assert "anyone with the link" in call(hub, "google__docs_create", title="x", folder_id="linkfolder")[1]
    assert not [r for r in requests(google, "/sheets/v4/spreadsheets/shared1/values") if r["method"] != "GET"]


def test_bad_ids_are_refused(hub):
    err, text = call(hub, "gmail__gmail_get_thread", thread_id="../modify")
    assert err and "not a valid Google id" in text
    err, text = call(hub, "google__calendar_list_events", time_min="a", time_max="b", calendar_id="../x")
    assert err and "calendar_id" in text


def test_slides(hub):
    text = call(hub, "google__slides_read", presentation_id="deck1")[1]
    assert "## Slide 1\nHello {{name}}" in text and "Notes: say hi" in text and "## Slide 2" in text
    created = json.loads(call(hub, "google__slides_create", title="Pitch")[1])
    assert created["link"].startswith("https://docs.google.com/presentation/d/")


def test_calendar_is_read_only(hub):
    text = call(hub, "google__calendar_list_events", time_min="2026-11-09T00:00:00Z",
                time_max="2026-11-10T00:00:00Z")[1]
    assert "Supplier call" in text and '"response": "accepted"' in text
    assert "Agenda" in call(hub, "google__calendar_get_event", event_id="ev1")[1]


def test_gmail_search_and_mailboxes(hub, google):
    assert "logistics@tallontrading.co" in call(hub, "gmail__gmail_list_mailboxes")[1]
    err, text = call(hub, "gmail__gmail_search", query="is:unread", mailbox="valen_trading")
    assert not err and "Delivery delayed" in text
    q = requests(google, "/gmail/v1/users/me/threads")
    listing = [r for r in q if r["path"].endswith("/threads")][-1]["query"]
    assert listing["q"] == ("((to:logistics@valentrading.com OR cc:logistics@valentrading.com OR "
                            "list:logistics@valentrading.com)) (is:unread)")
    assert listing["maxResults"] == "10"
    assert "mailbox must be one of" in call(hub, "gmail__gmail_search", mailbox="lush")[1]
    assert call(hub, "gmail__gmail_search", mailbox="ayman", max_results=500)[0] is False
    listing = [r for r in requests(google, "/gmail/v1/users/me/threads") if r["path"].endswith("/threads")][-1]
    assert listing["query"]["q"] == "-label:Logistics" and listing["query"]["maxResults"] == "25"


def test_gmail_429_is_never_retried(hub, google):
    before = len([r for r in requests(google, "/threads") if "RATELIMIT" in r["query"].get("q", "")])
    err, text = call(hub, "gmail__gmail_search", query="RATELIMIT")
    assert err and "429" in text and "not retried" in text
    after = len([r for r in requests(google, "/threads") if "RATELIMIT" in r["query"].get("q", "")])
    assert after - before == 1


def test_gmail_read_label_archive(hub):
    text = call(hub, "gmail__gmail_get_thread", thread_id="t1")[1]
    assert "Your parcel is delayed." in text and "x()" not in text and "Attachments: label.pdf" in text
    assert "added ['Triage/Must respond']" in call(hub, "gmail__gmail_label_thread", thread_id="t2",
                                                   add_labels=["Triage/Must respond"])[1]
    assert "can't be changed" in call(hub, "gmail__gmail_label_thread", thread_id="t2", add_labels=["TRASH"])[1]
    assert "can't be changed" in call(hub, "gmail__gmail_label_thread", thread_id="t2", remove_labels=["spam"])[1]
    assert "no label called" in call(hub, "gmail__gmail_label_thread", thread_id="t2", add_labels=["Nope"])[1]
    assert "removed ['INBOX']" in call(hub, "gmail__gmail_archive_thread", thread_id="t2")[1]
    assert "Created label" in call(hub, "gmail__gmail_create_label", name="Triage/Waiting")[1]
    assert "already exists" in call(hub, "gmail__gmail_create_label", name="Triage/Waiting")[1]
    labels = call(hub, "gmail__gmail_get_thread", thread_id="t2")[1]
    assert "Label_2" in labels and "INBOX" not in labels.split("Labels:")[1].split("\n")[0]


def test_no_secret_reaches_the_fake_log(google):
    raw = google["log"].read_text()
    assert "hub-secret" not in raw and "ya29." not in raw


def test_mailbox_query_units():
    assert gmail.mailbox_query("all") == ""
    assert gmail.mailbox_query("logistics") == "label:Logistics"
    assert "logistics@foxandfable.com" in gmail.mailbox_query("foxandfable")
    with pytest.raises(ValueError):
        gmail.mailbox_query("lush_lobster")
