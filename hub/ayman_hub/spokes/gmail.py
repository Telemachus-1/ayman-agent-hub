"""The hub's own Gmail spoke: ayman@telemachus.io and the six logistics@ group mailboxes.

Run by the hub over stdio:  python -m ayman_hub.spokes.gmail

The logistics@ addresses are Google Groups that deliver into ayman@ under the "Logistics"
label, so one sign-in covers all seven. Pick a mailbox with `mailbox`.

What it can do: search, read threads, list and create labels, label, and archive.
What it cannot do, because the tools don't exist: send, reply, forward, draft (not allowed
yet), trash, delete, unsubscribe, mark as spam, filters or auto-replies.
A 429 from Gmail is never retried.
"""

from __future__ import annotations

import base64
import html
import json
import re
from typing import Any

import mcp_types as types
from mcp.server.mcpserver import MCPServer

from ayman_hub.spokes.google_api import GoogleClient, ident

MAX_TEXT = 40_000
MAX_SEARCH = 25
LOGISTICS_LABEL = "Logistics"
MAILBOXES = {
    "ayman": "ayman@telemachus.io",
    "athena": "logistics@athenawholesale.co",
    "valen_cosmetics": "logistics@valencosmetics.co",
    "valen_trading": "logistics@valentrading.com",
    "tallon": "logistics@tallontrading.co",
    "toysellers": "logistics@foxandfabletoysellers.com",
    "foxandfable": "logistics@foxandfable.com",
}
# Labels agents may never add or remove: they would send, delete or hide mail.
SYSTEM_BLOCKED = {"TRASH", "SPAM", "DRAFT", "SENT", "CHAT"}

READ = types.ToolAnnotations(read_only_hint=True, open_world_hint=True)
ORGANISE = types.ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True,
                                 open_world_hint=True)

server = MCPServer(
    "ayman-hub-gmail",
    instructions="Gmail for ayman@telemachus.io and six logistics@ mailboxes. Read, search, label and "
    "archive only: nothing here sends, replies, forwards, drafts, trashes, deletes or unsubscribes. "
    "If Gmail returns 429, stop and say so; never retry.",
)
_client: GoogleClient | None = None


def client() -> GoogleClient:
    global _client
    if _client is None:
        _client = GoogleClient()
    return _client


def _api(method: str, path: str, **kw) -> Any:
    return client().request(method, "gmail", "/users/me" + path, **kw)


def _cap(text: str) -> str:
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT] + f"\n\n[cut at {MAX_TEXT} characters]"


def mailbox_query(mailbox: str) -> str:
    """The Gmail search that selects one mailbox."""
    if mailbox in ("", "all"):
        return ""
    if mailbox == "ayman":
        return f"-label:{LOGISTICS_LABEL}"
    if mailbox == "logistics":
        return f"label:{LOGISTICS_LABEL}"
    address = MAILBOXES.get(mailbox)
    if not address:
        raise ValueError(f"mailbox must be one of: all, logistics, {', '.join(MAILBOXES)}")
    return f"(to:{address} OR cc:{address} OR list:{address})"


def _headers(payload: dict) -> dict[str, str]:
    return {h["name"].lower(): h["value"] for h in payload.get("headers", [])}


def _b64(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")


def _strip_html(text: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", "", text)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", text)
    return html.unescape(re.sub(r"<[^>]+>", "", text))


def _body(payload: dict) -> tuple[str, list[str]]:
    """Plain text of a message (HTML as a fallback) and its attachment names."""
    plain, rich, files = [], [], []

    def walk(part: dict) -> None:
        mime = part.get("mimeType", "")
        if part.get("filename"):
            files.append(part["filename"])
        elif mime == "text/plain" and part.get("body", {}).get("data"):
            plain.append(_b64(part["body"]["data"]))
        elif mime == "text/html" and part.get("body", {}).get("data"):
            rich.append(_b64(part["body"]["data"]))
        for sub in part.get("parts", []):
            walk(sub)

    walk(payload)
    text = "\n".join(plain) if plain else _strip_html("\n".join(rich))
    return re.sub(r"\n{3,}", "\n\n", text).strip(), files


async def _labels() -> dict[str, str]:
    """Label name -> id."""
    body = await _api("GET", "/labels")
    return {lab["name"]: lab["id"] for lab in body.get("labels", [])}


@server.tool(annotations=READ)
async def gmail_list_mailboxes() -> str:
    """The mailboxes this spoke covers and the names to pass as `mailbox`."""
    return json.dumps({"mailboxes": MAILBOXES, "also": {"all": "everything", "logistics": "all six logistics@"},
                       "note": "The logistics@ addresses are Google Groups delivered into ayman@ "
                               f"under the '{LOGISTICS_LABEL}' label."}, indent=2)


@server.tool(annotations=READ)
async def gmail_search(query: str = "", mailbox: str = "all", max_results: int = 10, page_token: str = "") -> str:
    """Search threads with Gmail search syntax (e.g. "is:unread newer_than:2d from:dhl.com"),
    in one mailbox: all, ayman, logistics, or one of athena, valen_cosmetics, valen_trading,
    tallon, toysellers, foxandfable. Returns subject, from, date, snippet and labels.
    At most 25 per call, to stay inside Gmail's limits."""
    try:
        box = mailbox_query(mailbox)
        # Brackets keep the mailbox filter in force whatever the query says (e.g. "OR in:anywhere").
        q = f"({box}) ({query})" if box and query else (box or query)
    except ValueError as e:
        return str(e)
    params: dict = {"maxResults": max(1, min(max_results, MAX_SEARCH))}
    if q:
        params["q"] = q
    if page_token:
        params["pageToken"] = page_token
    listing = await _api("GET", "/threads", params=params)
    out = []
    for t in listing.get("threads", []):
        full = await _api("GET", f"/threads/{ident(t['id'])}", params={
            "format": "metadata", "metadataHeaders": ["Subject", "From", "To", "Date"]})
        msgs = full.get("messages", [])
        first, last = (msgs[0], msgs[-1]) if msgs else ({}, {})
        h = _headers(first.get("payload", {}))
        out.append({
            "thread_id": t["id"], "subject": h.get("subject", ""), "from": h.get("from", ""),
            "to": h.get("to", ""), "last_date": _headers(last.get("payload", {})).get("date", h.get("date", "")),
            "messages": len(msgs), "snippet": t.get("snippet") or last.get("snippet", ""),
            "labels": sorted({lab for m in msgs for lab in m.get("labelIds", [])}),
        })
    return _cap(json.dumps({"query": q, "threads": out, "next_page_token": listing.get("nextPageToken")},
                           indent=2, ensure_ascii=False))


@server.tool(annotations=READ)
async def gmail_get_thread(thread_id: str) -> str:
    """Read a whole thread: each message's from, to, date, text and attachment names.
    Attachments are listed, not opened."""
    full = await _api("GET", f"/threads/{ident(thread_id)}", params={"format": "full"})
    parts = []
    for m in full.get("messages", []):
        h = _headers(m.get("payload", {}))
        text, files = _body(m.get("payload", {}))
        parts.append(
            f"From: {h.get('from', '')}\nTo: {h.get('to', '')}\n" + (f"Cc: {h['cc']}\n" if h.get("cc") else "")
            + f"Date: {h.get('date', '')}\nSubject: {h.get('subject', '')}\nLabels: {', '.join(m.get('labelIds', []))}\n"
            + (f"Attachments: {', '.join(files)}\n" if files else "") + f"\n{text}"
        )
    return _cap(f"Thread {thread_id} ({len(parts)} messages)\n\n" + "\n\n-----\n\n".join(parts))


@server.tool(annotations=READ)
async def gmail_list_labels() -> str:
    """All labels, with their ids."""
    body = await _api("GET", "/labels")
    return json.dumps(sorted(({"name": lab["name"], "id": lab["id"], "type": lab.get("type")}
                              for lab in body.get("labels", [])), key=lambda x: x["name"]), indent=2)


@server.tool(annotations=ORGANISE)
async def gmail_create_label(name: str) -> str:
    """Create a label (e.g. "Triage/Waiting"). Does nothing if it already exists."""
    labels = await _labels()
    if name in labels:
        return f"Label '{name}' already exists ({labels[name]})."
    body = await _api("POST", "/labels", json_body={
        "name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"})
    return f"Created label '{name}' ({body.get('id')})."


async def _modify(thread_id: str, add: list[str], remove: list[str]) -> str:
    labels = await _labels()
    system = {"INBOX", "UNREAD", "STARRED", "IMPORTANT"}

    def resolve(names: list[str]) -> list[str]:
        ids = []
        for n in names:
            if n.upper() in SYSTEM_BLOCKED:
                raise ValueError(f"the {n.upper()} label can't be changed through the hub")
            if n.upper() in system:
                ids.append(n.upper())
            elif n in labels:
                ids.append(labels[n])
            elif n in labels.values():
                ids.append(n)
            else:
                raise ValueError(f"no label called '{n}' (create it first with gmail_create_label)")
        return ids

    try:
        add_ids, remove_ids = resolve(add), resolve(remove)
    except ValueError as e:
        return str(e)
    await _api("POST", f"/threads/{ident(thread_id)}/modify",
               json_body={"addLabelIds": add_ids, "removeLabelIds": remove_ids})
    return f"Thread {thread_id}: added {add or 'nothing'}, removed {remove or 'nothing'}."


@server.tool(annotations=ORGANISE)
async def gmail_label_thread(thread_id: str, add_labels: list[str] | None = None,
                             remove_labels: list[str] | None = None) -> str:
    """Add or remove labels on a thread, by name (e.g. "Triage/Must respond") or id. INBOX,
    UNREAD, STARRED and IMPORTANT work too. Trash, spam, drafts and sent can't be touched."""
    return await _modify(thread_id, add_labels or [], remove_labels or [])


@server.tool(annotations=ORGANISE)
async def gmail_archive_thread(thread_id: str) -> str:
    """Archive a thread: take it out of the inbox. It stays in All Mail with its labels."""
    return await _modify(thread_id, [], ["INBOX"])


if __name__ == "__main__":
    server.run("stdio")
