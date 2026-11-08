"""Decide whether a client may see or call a tool. Writes are blocked unless listed.

Order of checks (first failure wins):
1. kill switch          - the hub is off: nothing is allowed
2. spoke enabled        - a switched-off spoke offers nothing
3. spoke clients        - a spoke can be limited to named clients
4. plain names only     - tool names with non-ASCII characters are refused
5. HARD DENY (code)     - send, pay, delete, share, invite, post, merge... whatever the config says
6. deny_tools (config)  - glob patterns, per spoke, case-insensitive
7. reads                - a tool is a read only if its name starts with a read verb, has no
                          write verb, and the service doesn't mark it as a write
8. writes               - anything else needs allow_tools; read-only spokes take no writes
9. destructive          - a write the service doesn't mark safe needs allow_destructive
                          (no marking counts as destructive, as the MCP spec says)

At call time, decide_call() also checks the arguments:
- an `action` argument (menu tools such as Helm's) gets the hard-deny check, and must be
  in allow_actions for that tool when the spoke lists them;
- a confirm-type argument (Helm's `confirm=true`) is refused unless the client is in
  confirm_clients: agents preview, Ayman confirms.

The hard-deny lists are deliberately in code, not config: loosening them takes a
reviewed code change.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Any

import mcp_types as types

from ayman_hub.config import Spoke

# Whole words that make a tool a one-way door.
HARD_DENY_TOKENS = frozenset({
    "send", "sends", "forward", "forwards", "reply", "replies", "refund", "refunds",
    "delete", "deletes", "destroy", "purge", "trash", "unsubscribe",
    "pay", "pays", "paid", "payment", "payments", "payout", "payouts", "prepay", "autopay", "repay",
    "post", "posts", "publish", "invite", "invites", "share", "shares", "unshare",
    "merge", "schedule", "submit", "cancel",
})
# Matched anywhere in the lowercased name, so "resend", "sendmail" or "HTTPSend" can't slip by.
HARD_DENY_SUBSTRINGS = ("send", "delete", "trash", "unsubscribe", "forward", "refund", "purge")
READ_VERBS = frozenset({
    "get", "list", "search", "read", "find", "query", "fetch", "view", "show",
    "lookup", "describe", "count", "check", "whoami", "download",
})
WRITE_VERBS = frozenset({
    "create", "update", "edit", "add", "set", "save", "insert", "append", "write", "remove",
    "move", "modify", "label", "archive", "mark", "upload", "copy", "duplicate", "rename",
    "restore", "resolve", "apply", "complete", "approve", "release", "transfer", "clear",
    "convert", "generate", "spawn", "stop", "start", "run", "execute", "sync", "import",
    "upsert", "patch", "put", "enable", "disable", "assign", "unassign", "link", "unlink",
    "react", "retire", "revoke", "sign", "login", "logout", "toggle", "close", "reset",
    "accept", "decline", "respond", "book", "confirm", "prepare", "unarchive", "untrash",
    "unmark", "register", "report", "manage", "edit", "change", "replace", "attach",
})
CONFIRM_VALUES_OFF = (None, False, 0, "", "false", "False", "0", "no")

_SPLIT = re.compile(
    r"[^A-Za-z0-9]+"
    r"|(?<=[a-z0-9])(?=[A-Z])"          # camelCase
    r"|(?<=[A-Z])(?=[A-Z][a-z])"        # HTTPSend -> HTTP Send
    r"|(?<=[A-Za-z])(?=[0-9])|(?<=[0-9])(?=[A-Za-z])"  # send2 -> send 2
)


def plain_name(name: str) -> str | None:
    """The name in plain ASCII after Unicode normalisation, or None if it isn't plain."""
    nfkc = unicodedata.normalize("NFKC", name)
    return nfkc if nfkc.isascii() and nfkc.isprintable() else None


def tool_words(name: str) -> list[str]:
    return [w.lower() for w in _SPLIT.split(name) if w]


def hard_denied(name: str) -> bool:
    plain = plain_name(name)
    if plain is None:
        return True
    lowered = plain.lower()
    if any(s in lowered for s in HARD_DENY_SUBSTRINGS):
        return True
    return any(w in HARD_DENY_TOKENS or w.startswith("payment") for w in tool_words(plain))


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


ALLOW = Decision(True, "allowed")


def _annotation(tool: types.Tool, attr: str) -> bool | None:
    ann = tool.annotations
    if ann is None:
        return None
    return getattr(ann, attr, None)


def looks_read_only(tool: types.Tool) -> bool:
    """A read: one of the first two words is a read verb (e.g. list_issues, slack_read_channel),
    no word is a write verb, and the service doesn't mark it as a write. A service marking a
    tool read-only is not enough on its own."""
    if _annotation(tool, "read_only_hint") is False:
        return False
    words = tool_words(tool.name)
    if not words or any(w in WRITE_VERBS for w in words):
        return False
    return any(w in READ_VERBS for w in words[:2])


def _matches(name: str, patterns: tuple[str, ...]) -> bool:
    lowered = name.lower()
    return any(fnmatchcase(lowered, p.lower()) for p in patterns)


def _destructive(tool: types.Tool) -> bool:
    if _annotation(tool, "read_only_hint") is True:
        return False
    marked = _annotation(tool, "destructive_hint")
    return True if marked is None else bool(marked)


def decide(*, spoke: Spoke, tool: types.Tool, client: str, hub_off: bool) -> Decision:
    if hub_off:
        return Decision(False, "hub is switched off (kill switch)")
    if not spoke.enabled:
        return Decision(False, f"spoke '{spoke.name}' is switched off")
    if spoke.clients and client not in spoke.clients:
        return Decision(False, f"client '{client}' may not use spoke '{spoke.name}'")
    if plain_name(tool.name) is None:
        return Decision(False, "tool names must be plain ASCII")
    if hard_denied(tool.name):
        return Decision(False, "send, pay, delete, share, invite, post and merge-type tools are blocked in code")
    if _matches(tool.name, spoke.deny_tools):
        return Decision(False, f"blocked by deny_tools on spoke '{spoke.name}'")
    if looks_read_only(tool):
        return ALLOW
    listed = _matches(tool.name, spoke.allow_tools)
    if spoke.mode == "read-only":
        # allow_tools may vouch for reads whose names don't say so (e.g. stock_levels), never for writes.
        if listed and not any(w in WRITE_VERBS for w in tool_words(tool.name)) \
                and _annotation(tool, "read_only_hint") is not False:
            return ALLOW
        return Decision(False, f"spoke '{spoke.name}' is read-only")
    if not listed:
        return Decision(False, f"writes are blocked unless listed in allow_tools on spoke '{spoke.name}'")
    if _destructive(tool) and not _matches(tool.name, spoke.allow_destructive):
        return Decision(False, "not marked safe by the service (needs allow_destructive)")
    return ALLOW


def _truthy_keys(value: Any, keys: tuple[str, ...], depth: int = 0) -> bool:
    """True if any of `keys` is set to a true-ish value anywhere in the arguments."""
    if depth > 6:
        return True  # unreasonably deep: refuse rather than miss a nested confirm
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(k, str) and k.lower() in keys and v not in CONFIRM_VALUES_OFF:
                return True
            if _truthy_keys(v, keys, depth + 1):
                return True
    elif isinstance(value, list):
        return any(_truthy_keys(v, keys, depth + 1) for v in value)
    return False


def decide_call(*, spoke: Spoke, tool: types.Tool, client: str, arguments: dict | None) -> Decision:
    """Argument checks, after decide() has allowed the tool itself."""
    args = arguments or {}
    confirm_keys = tuple(k.lower() for k in spoke.confirm_args)
    if confirm_keys and client not in spoke.confirm_clients and _truthy_keys(args, confirm_keys):
        return Decision(False, "agents may preview this write, not confirm it; Ayman confirms")
    action = args.get("action")
    if action is not None:
        if not isinstance(action, str) or hard_denied(action):
            return Decision(False, "that action is a send, pay or delete-type action, blocked in code")
        patterns = spoke.allow_actions.get(tool.name)
        if patterns is not None and not _matches(action, tuple(patterns)):
            return Decision(False, f"action '{action[:60]}' is not in allow_actions for {tool.name}")
    return ALLOW
