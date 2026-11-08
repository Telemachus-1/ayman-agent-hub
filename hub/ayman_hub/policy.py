"""Decide whether a client may see or call a tool.

Order of checks (first failure wins):
1. kill switch          - the hub is off: nothing is allowed
2. spoke enabled        - a switched-off spoke offers nothing
3. spoke clients        - a spoke can be limited to named clients
4. HARD DENY (code)     - send / pay / delete-type tools, whatever the config says
5. deny_tools (config)  - glob patterns, per spoke
6. allow_tools (config) - if set, only these
7. mode                 - read-only spokes offer only read tools
8. destructive          - tools the upstream marks destructive need allow_destructive

The hard-deny list is deliberately in code, not config: loosening it takes a
reviewed code change (Basil's guide, "Adding a spoke").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fnmatch import fnmatchcase

import mcp_types as types

from ayman_hub.config import Spoke

# Tokens that make a tool a one-way door. Matched against the tool name split
# into words (snake_case, kebab-case, dots and camelCase all split).
HARD_DENY_TOKENS = frozenset({
    "send", "forward", "reply", "pay", "pays", "payment", "payments", "payout",
    "payouts", "refund", "refunds", "delete", "destroy", "purge", "trash",
    "unsubscribe",
})
READ_VERBS = frozenset({
    "get", "list", "search", "read", "find", "query", "fetch", "view", "show",
    "lookup", "describe", "count", "check", "whoami",
})

_SPLIT = re.compile(r"[^A-Za-z0-9]+|(?<=[a-z0-9])(?=[A-Z])")


def tool_words(name: str) -> list[str]:
    return [w.lower() for w in _SPLIT.split(name) if w]


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
    """True when the upstream marks the tool read-only, or (with no marking) its name starts with a read verb."""
    marked = _annotation(tool, "read_only_hint")
    if marked is not None:
        return bool(marked)
    words = tool_words(tool.name)
    return bool(words) and words[0] in READ_VERBS


def hard_denied(tool_name: str) -> bool:
    return any(w in HARD_DENY_TOKENS for w in tool_words(tool_name))


def _matches(name: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatchcase(name, p) for p in patterns)


def decide(*, spoke: Spoke, tool: types.Tool, client: str, hub_off: bool) -> Decision:
    if hub_off:
        return Decision(False, "hub is switched off (kill switch)")
    if not spoke.enabled:
        return Decision(False, f"spoke '{spoke.name}' is switched off")
    if spoke.clients and client not in spoke.clients:
        return Decision(False, f"client '{client}' may not use spoke '{spoke.name}'")
    if hard_denied(tool.name):
        return Decision(False, "send, pay and delete-type tools are blocked in code")
    if _matches(tool.name, spoke.deny_tools):
        return Decision(False, f"blocked by deny_tools on spoke '{spoke.name}'")
    if spoke.allow_tools and not _matches(tool.name, spoke.allow_tools):
        return Decision(False, f"not in allow_tools on spoke '{spoke.name}'")
    if spoke.mode == "read-only" and not looks_read_only(tool):
        return Decision(False, f"spoke '{spoke.name}' is read-only")
    if _annotation(tool, "destructive_hint") and not _matches(tool.name, spoke.allow_destructive):
        return Decision(False, "the service marks this tool destructive")
    return ALLOW
