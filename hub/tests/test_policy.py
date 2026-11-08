import mcp_types as types
import pytest

from ayman_hub.config import ConfigError, Spoke, load_config
from ayman_hub.policy import ALLOW, decide, hard_denied, looks_read_only, tool_words


def tool(name, ro=None, destructive=None):
    ann = None if ro is None and destructive is None else types.ToolAnnotations(
        read_only_hint=ro, destructive_hint=destructive)
    return types.Tool(name=name, input_schema={"type": "object"}, annotations=ann)


def spoke(**kw):
    base = dict(name="s", enabled=True, transport="http", url="https://x", mode="read-write")
    base.update(kw)
    return Spoke(**base)


@pytest.mark.parametrize("name", [
    "send_message", "gmail_send_draft", "slack_send_message_draft", "forwardEmail", "reply_all",
    "create_payment", "list_payments", "issue_refund", "delete_issue", "trash_thread",
    "unsubscribe", "purge-cache", "payout.create",
])
def test_hard_deny_blocks_one_way_tools(name):
    assert hard_denied(name)


@pytest.mark.parametrize("name", [
    "list_issues", "save_issue", "create_draft", "label_thread", "unlabel_thread",
    "search_threads", "get_meeting_transcript", "edit_transfer_lines", "sales_invoices",
])
def test_hard_deny_leaves_ordinary_tools(name):
    assert not hard_denied(name)


def test_hard_deny_beats_config_allow():
    s = spoke(allow_tools=("send_message",), allow_destructive=("send_message",))
    d = decide(spoke=s, tool=tool("send_message", ro=False), client="c", hub_off=False)
    assert not d.allowed and "code" in d.reason


def test_kill_switch_blocks_everything():
    d = decide(spoke=spoke(), tool=tool("list_issues", ro=True), client="c", hub_off=True)
    assert not d.allowed and "kill switch" in d.reason


def test_disabled_spoke_and_client_limits():
    assert not decide(spoke=spoke(enabled=False), tool=tool("list_x", ro=True), client="c", hub_off=False).allowed
    s = spoke(clients=("claude",))
    assert not decide(spoke=s, tool=tool("list_x", ro=True), client="grokbot", hub_off=False).allowed
    assert decide(spoke=s, tool=tool("list_x", ro=True), client="claude", hub_off=False) is ALLOW


def test_read_only_mode():
    s = spoke(mode="read-only")
    assert decide(spoke=s, tool=tool("list_issues", ro=True), client="c", hub_off=False) is ALLOW
    assert not decide(spoke=s, tool=tool("save_issue", ro=False), client="c", hub_off=False).allowed
    # Unmarked tools fall back to the name: read verbs pass, others don't.
    assert decide(spoke=s, tool=tool("get_thread"), client="c", hub_off=False) is ALLOW
    assert not decide(spoke=s, tool=tool("label_thread"), client="c", hub_off=False).allowed
    # A tool marked read-only wins over its name.
    assert looks_read_only(tool("payment_runs_overview", ro=True))


def test_deny_allow_and_destructive():
    s = spoke(deny_tools=("*archive*",), allow_tools=("save_*", "list_*", "archive_*"))
    assert not decide(spoke=s, tool=tool("archive_issue", ro=False), client="c", hub_off=False).allowed
    assert not decide(spoke=s, tool=tool("create_issue", ro=False), client="c", hub_off=False).allowed
    assert decide(spoke=s, tool=tool("save_issue", ro=False), client="c", hub_off=False) is ALLOW
    d = spoke()
    assert not decide(spoke=d, tool=tool("drop_table", ro=False, destructive=True), client="c", hub_off=False).allowed
    d2 = spoke(allow_destructive=("drop_table",))
    assert decide(spoke=d2, tool=tool("drop_table", ro=False, destructive=True), client="c", hub_off=False) is ALLOW


def test_tool_words_splits_all_styles():
    assert tool_words("gmailSendDraft") == ["gmail", "send", "draft"]
    assert tool_words("notion-create.pages") == ["notion", "create", "pages"]


def test_shipped_config_is_valid_and_all_off():
    from pathlib import Path
    cfg = load_config(Path(__file__).resolve().parent.parent / "spokes.toml")
    assert list(cfg.spokes) == ["linear", "notion", "granola", "google", "gmail", "slack", "helm", "whatsapp"]
    assert cfg.enabled_spokes() == []


def test_bad_config_is_explained(tmp_path):
    p = tmp_path / "bad.toml"
    p.write_text('[spokes.Bad]\nenabled = true\ntransport = "http"\nurl = "https://x"\n')
    with pytest.raises(ConfigError, match="lowercase"):
        load_config(p)
    p.write_text('[spokes.ok]\nenabled = true\ntransport = "http"\n')
    with pytest.raises(ConfigError, match="url"):
        load_config(p)
    p.write_text('[spokes.ok]\nenabled = true\ntransport = "http"\nurl = "https://x"\nmode = "yolo"\n')
    with pytest.raises(ConfigError, match="mode"):
        load_config(p)
