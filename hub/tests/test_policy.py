import mcp_types as types
import pytest

from ayman_hub.config import ConfigError, Spoke, load_config
from ayman_hub.policy import ALLOW, decide, decide_call, hard_denied, looks_read_only, tool_words


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
    # names the review found slipping through before
    "SENDMessage", "HTTPSend", "sendmail", "resend", "send2", "DELETEIssue", "prepay", "autopay",
    "\u0455end_email", "ｓｅｎｄ_mail", "payment_runs",
    # one-way verbs added after the review
    "slack_schedule_message", "merge_diff", "share_issue", "ShareFile", "notion-calendar-cancel-events",
    "invite_user", "publish_page", "post_message", "submit_form", "unshare_issue", "transmit_po",
])
def test_hard_deny_blocks_one_way_tools(name):
    assert hard_denied(name)


@pytest.mark.parametrize("name", [
    "list_issues", "save_issue", "create_draft", "label_thread", "unlabel_thread",
    "search_threads", "get_meeting_transcript", "edit_transfer_lines", "sales_invoices",
    "invoice_payables", "list_shared_drives", "notion-list-shared-pages", "display_settings",
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
    assert decide(spoke=s, tool=tool("slack_read_channel"), client="c", hub_off=False) is ALLOW
    assert not decide(spoke=s, tool=tool("save_issue", ro=False), client="c", hub_off=False).allowed
    assert not decide(spoke=s, tool=tool("label_thread"), client="c", hub_off=False).allowed
    # The service saying "read-only" is not enough on its own any more.
    assert not looks_read_only(tool("payment_runs_overview", ro=True))
    assert not decide(spoke=s, tool=tool("approve_order", ro=True), client="c", hub_off=False).allowed
    # ...and a read verb with a write verb in the name is a write.
    assert not looks_read_only(tool("get_or_create_label"))
    # A service marking a read-named tool as a write wins.
    assert not looks_read_only(tool("list_and_mark", ro=False))
    # allow_tools may vouch for odd-named reads, never for writes, on a read-only spoke.
    s2 = spoke(mode="read-only", allow_tools=("stock_levels", "update_order"))
    assert decide(spoke=s2, tool=tool("stock_levels"), client="c", hub_off=False) is ALLOW
    assert not decide(spoke=s2, tool=tool("update_order"), client="c", hub_off=False).allowed


def test_writes_are_blocked_unless_listed():
    s = spoke()
    assert not decide(spoke=s, tool=tool("create_issue", ro=False, destructive=False), client="c", hub_off=False).allowed
    assert not decide(spoke=s, tool=tool("stock_levels"), client="c", hub_off=False).allowed
    s = spoke(allow_tools=("save_*", "archive_*"), deny_tools=("*ARCHIVE*",))
    assert decide(spoke=s, tool=tool("save_issue", ro=False, destructive=False), client="c", hub_off=False) is ALLOW
    # deny wins over allow, in any case
    assert not decide(spoke=s, tool=tool("Archive_Issue", ro=False, destructive=False), client="c", hub_off=False).allowed


def test_unmarked_writes_count_as_destructive():
    s = spoke(allow_tools=("save_issue", "drop_table"))
    assert not decide(spoke=s, tool=tool("save_issue"), client="c", hub_off=False).allowed
    assert not decide(spoke=s, tool=tool("drop_table", ro=False, destructive=True), client="c", hub_off=False).allowed
    s2 = spoke(allow_tools=("save_issue", "drop_table"), allow_destructive=("save_issue", "drop_table"))
    assert decide(spoke=s2, tool=tool("save_issue"), client="c", hub_off=False) is ALLOW
    assert decide(spoke=s2, tool=tool("drop_table", ro=False, destructive=True), client="c", hub_off=False) is ALLOW


def test_non_ascii_names_are_refused():
    s = spoke(allow_tools=("*",), allow_destructive=("*",))
    d = decide(spoke=s, tool=tool("cre\u0430te_issue", ro=False, destructive=False), client="c", hub_off=False)
    assert not d.allowed


def test_helm_menu_actions_and_confirm_are_checked():
    s = spoke(allow_tools=("helm_finance", "update_order"), allow_destructive=("helm_finance", "update_order"),
              allow_actions={"helm_finance": ("help", "margin_*")}, confirm_args=("confirm",),
              confirm_clients=("claude",))
    menu = tool("helm_finance")
    assert decide_call(spoke=s, tool=menu, client="grokbot", arguments={"action": "help"}) is ALLOW
    assert decide_call(spoke=s, tool=menu, client="grokbot", arguments={"action": "margin_report"}) is ALLOW
    for action in ("payment_runs", "Payment_Runs", "issue_refund", "send_remittance", "delete_bill"):
        assert not decide_call(spoke=s, tool=menu, client="grokbot", arguments={"action": action}).allowed
    assert not decide_call(spoke=s, tool=menu, client="grokbot", arguments={"action": "write_off"}).allowed
    assert not decide_call(spoke=s, tool=menu, client="grokbot", arguments={"action": ["help"]}).allowed
    # sub-actions inside args get the same check
    assert not decide_call(spoke=s, tool=menu, client="grokbot",
                           arguments={"action": "margin_x", "args": {"action": "record_payment"}}).allowed
    assert decide_call(spoke=s, tool=menu, client="grokbot",
                       arguments={"action": "margin_x", "args": {"action": "amazon_link"}}) is ALLOW
    upd = tool("update_order")
    assert decide_call(spoke=s, tool=upd, client="grokbot", arguments={"order": "1"}) is ALLOW
    assert decide_call(spoke=s, tool=upd, client="grokbot", arguments={"confirm": False}) is ALLOW
    for args in ({"confirm": True}, {"Confirm": "true"}, {"args": {"confirm": 1}},
                 {"args": [{"nested": {"confirm": True}}]}):
        assert not decide_call(spoke=s, tool=upd, client="grokbot", arguments=args).allowed, args
    assert decide_call(spoke=s, tool=upd, client="claude", arguments={"confirm": True}) is ALLOW


def test_tool_words_splits_all_styles():
    assert tool_words("gmailSendDraft") == ["gmail", "send", "draft"]
    assert tool_words("notion-create.pages") == ["notion", "create", "pages"]
    assert tool_words("HTTPSendV2") == ["http", "send", "v", "2"]


def test_shipped_helm_config_keeps_one_way_actions_out():
    from pathlib import Path
    helm = load_config(Path(__file__).resolve().parent.parent / "spokes.toml").spokes["helm"]
    listed = {a for acts in helm.allow_actions.values() for a in acts}
    for never in ("pay_po", "pay_invoice", "mark_paid", "record_payment", "refund_b2c_order", "cancel_order",
                  "transmit_po", "manage_po", "procure_shortfall", "issue_sales_invoice", "credit_order_line",
                  "grant_customer_credit", "set_credit_limit", "add_supplier_bank_account", "create_journal",
                  "void_journal", "execute_batch", "plan_batch", "screen_action", "label_units_only",
                  "kitting_run_start", "set_build", "ste_request_certificate", "draft_mail_reply", "grant_bu_role"):
        assert never not in listed, never
    menu = types.Tool(name="helm_buying", input_schema={"type": "object"})
    d = decide_call(spoke=helm, tool=menu, client="claude", arguments={"action": "manage_po", "args": {}})
    assert not d.allowed


LYTHERON_TOOLS = """acknowledge_backorders add_catalogue_entry add_note adjust_lot_cost
amazon_fba_customer_placement_options amazon_fba_inbound_status amazon_fba_labels amazon_fba_placement_options
amazon_fba_transport_quotes analytics_query approve_purchase_order approve_queued_price approve_restock_alert
approve_wholesale_order assess_draft_order backend_health bundle_detail cancel_amazon_fba_shipment
cancel_exclusivity_group cancel_oplog_sales_order cancel_wholesale_order catalogue_entry change_po_destination
change_po_supplier channel_breakdown clear_landed_override complete_amazon_fba_shipment
confirm_amazon_fba_customer_placement confirm_amazon_fba_placement confirm_amazon_fba_transport confirm_delivery
correct_product_title correct_supplier_invoice create_delivery_invoice create_draft_order create_exclusivity_group
create_order_sheet create_purchase_order create_ungating_invoice customer_lookup delete_ungating_invoice
dispatch_invoice dispatch_to_oplog distributor_offer edit_catalogue_entry edit_customer edit_customer_terms
edit_exclusivity_group edit_order_lines edit_order_sheet edit_po_lines email_amazon_fba_labels email_invoice
exclusivity_group exclusivity_groups exclusivity_live exclusivity_proposed finalize_amazon_fba_inbound
finalize_order_sheet fulfilment_status goods_to_arrive inventory_status inventory_status_bulk invoice_document
invoice_summaries_by_customer list_ungating_invoices listing_status lot_detail materialize_lots order_lookup
orders_by_state pin_tier_price pricing_lookup pricing_lookup_bulk print_run_shipment print_run_status
profit_summary promote_exclusivity_group purchase_order_status push_amazon_fba_inbound receive_goods
receive_transfer record_negotiated_price record_publisher_terms recreate_preliminary regenerate_invoice_pdf
reject_queued_price reject_wholesale_order reprice_eans repricer_explain resend_shopify_order_to_oplog
restock_suggestions review_queue save_amazon_fba_boxes save_amazon_fba_pallets send_invoice_to_floor
send_notification send_purchase_order_inbound set_amazon_fba_ship_from set_fba_line_pack set_labelling
set_landed_override set_order_line_warehouse ship_transfer shipment_tracking split_trade_order sql_read
stage_customer_amazon_fba_inbound start_customer_amazon_fba_inbound stock_by_warehouse submit_wholesale_order
sync_goods_receiving tier_prices transfer_status transition_purchase_order transmit_purchase_order trigger_sync
ungating_invoice ungating_order_lines unpin_tier_price update_tracking update_ungating_invoice_lines""".split()


def test_shipped_lytheron_config_offers_only_reads_and_commercial_edits():
    from pathlib import Path
    ly = load_config(Path(__file__).resolve().parent.parent / "spokes.toml").spokes["lytheron"]
    ly = Spoke(**{**ly.__dict__, "enabled": True})
    offered = {t for t in LYTHERON_TOOLS if decide(spoke=ly, tool=tool(t), client="claude", hub_off=False).allowed}
    writes = {"add_note", "edit_customer", "add_catalogue_entry", "edit_catalogue_entry", "correct_product_title",
              "create_draft_order", "edit_order_lines", "pin_tier_price", "unpin_tier_price",
              "record_negotiated_price", "approve_queued_price", "reject_queued_price"}
    assert writes <= offered
    for never in ("create_purchase_order", "approve_purchase_order", "transmit_purchase_order", "email_invoice",
                  "dispatch_invoice", "dispatch_to_oplog", "send_notification", "receive_goods", "ship_transfer",
                  "cancel_wholesale_order", "approve_wholesale_order", "submit_wholesale_order", "edit_customer_terms",
                  "confirm_amazon_fba_transport", "push_amazon_fba_inbound", "trigger_sync", "reprice_eans",
                  "set_landed_override", "delete_ungating_invoice", "send_invoice_to_floor", "update_tracking"):
        assert never not in offered, never
    # every listed tool exists in Lytheron's list (catches typos)
    assert set(ly.allow_tools) <= set(LYTHERON_TOOLS)


def test_shipped_config_is_valid_and_all_off():
    from pathlib import Path
    cfg = load_config(Path(__file__).resolve().parent.parent / "spokes.toml")
    assert list(cfg.spokes) == ["linear", "notion", "granola", "google", "gmail", "slack", "helm", "lytheron",
                                "whatsapp"]
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
    p.write_text('[spokes.ok]\nenabled = true\ntransport = "http"\nurl = "http://linear.example/mcp"\n')
    with pytest.raises(ConfigError, match="https"):
        load_config(p)
