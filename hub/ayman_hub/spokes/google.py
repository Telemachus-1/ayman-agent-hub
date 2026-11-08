"""The hub's own Google spoke: Drive, Docs, Sheets, Slides and Calendar.

Run by the hub over stdio:  python -m ayman_hub.spokes.google

What it can do: search and read anything Ayman can open; create Docs, Sheets and Slides;
add to and edit them. Calendar is read-only.
What it cannot do, because the tools don't exist: share, change who has access, move,
trash or delete anything, or create, change or answer calendar events.

Tools that overwrite existing content are marked destructive, so the hub only offers them
when spokes.toml lists them in allow_destructive.

Writing into a file, or creating one in a folder, is refused when that file or folder is
shared with anyone outside the company domains (`--internal-domains`, default
telemachus.io) or with anyone who has the link: an edit there would reach outside people.
Sheets values are stored exactly as given (no formulas), so nothing written can make
Google fetch an outside address.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

import mcp_types as types
from mcp.server.mcpserver import MCPServer

from ayman_hub.spokes.google_api import GoogleClient, GoogleError, calendar_ident, ident, seg

MAX_TEXT = 50_000

READ = types.ToolAnnotations(read_only_hint=True, open_world_hint=True)
ADD = types.ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=True)
OVERWRITE = types.ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=True)

server = MCPServer(
    "ayman-hub-google",
    instructions="Google Drive, Docs, Sheets, Slides and Calendar for ayman@telemachus.io. "
    "No sharing, access changes, moves, trash or calendar changes exist here. "
    "Brand discretion: a brand's documents carry only that brand's names.",
)
_client: GoogleClient | None = None
INTERNAL_DOMAINS: set[str] = {"telemachus.io"}


def client() -> GoogleClient:
    global _client
    if _client is None:
        _client = GoogleClient()
    return _client


def _cap(text: str) -> str:
    if len(text) <= MAX_TEXT:
        return text
    return text[:MAX_TEXT] + f"\n\n[cut at {MAX_TEXT} characters of {len(text)}]"


def _dump(value: Any) -> str:
    return _cap(json.dumps(value, indent=2, ensure_ascii=False))


def _q(text: str) -> str:
    """Quote a value inside a Drive query."""
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


FILE_FIELDS = "id,name,mimeType,modifiedTime,webViewLink,owners(emailAddress),driveId,parents"
MIME = {
    "doc": "application/vnd.google-apps.document",
    "sheet": "application/vnd.google-apps.spreadsheet",
    "slides": "application/vnd.google-apps.presentation",
    "folder": "application/vnd.google-apps.folder",
    "pdf": "application/pdf",
}


# --- Drive ------------------------------------------------------------------

@server.tool(annotations=READ)
async def drive_search(query: str = "", name: str = "", kind: str = "", folder_id: str = "",
                       page_size: int = 20, page_token: str = "") -> str:
    """Search Google Drive, including shared drives. `query` matches file contents and names;
    `name` matches names only; `kind` is one of doc, sheet, slides, folder, pdf; `folder_id`
    limits to one folder. Returns id, name, type, link and owner; pass next_page_token for more."""
    parts = ["trashed = false"]
    if query:
        parts.append(f"fullText contains {_q(query)}")
    if name:
        parts.append(f"name contains {_q(name)}")
    if kind:
        if kind not in MIME:
            return f"kind must be one of {', '.join(MIME)}"
        parts.append(f"mimeType = {_q(MIME[kind])}")
    if folder_id:
        parts.append(f"{_q(folder_id)} in parents")
    params = {
        "q": " and ".join(parts), "pageSize": max(1, min(page_size, 100)),
        "fields": f"nextPageToken,files({FILE_FIELDS})", "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true", "corpora": "allDrives",
    }
    if page_token:
        params["pageToken"] = page_token
    body = await client().request("GET", "drive", "/files", params=params)
    return _dump({"files": body.get("files", []), "next_page_token": body.get("nextPageToken")})


@server.tool(annotations=READ)
async def drive_get_file(file_id: str) -> str:
    """Details of one Drive file: name, type, link, owner, folder, last change."""
    return _dump(await client().request("GET", "drive", f"/files/{ident(file_id)}",
                                        params={"fields": FILE_FIELDS, "supportsAllDrives": "true"}))


@server.tool(annotations=READ)
async def drive_read_file(file_id: str) -> str:
    """Read a Drive file as text: Docs and Slides as plain text, Sheets as CSV (first tab),
    and plain-text files as they are. Other files (images, PDFs, Office files) return their
    details only."""
    meta = await client().request("GET", "drive", f"/files/{ident(file_id)}",
                                  params={"fields": "id,name,mimeType,size", "supportsAllDrives": "true"})
    mime = meta.get("mimeType", "")
    export = {MIME["doc"]: "text/plain", MIME["slides"]: "text/plain", MIME["sheet"]: "text/csv"}
    if mime in export:
        r = await client().request("GET", "drive", f"/files/{ident(file_id)}/export",
                                   params={"mimeType": export[mime]}, raw=True)
        return _cap(f"# {meta.get('name')}\n\n{r.text}")
    if mime.startswith("text/") or mime in ("application/json", "text/csv"):
        if int(meta.get("size") or 0) > 2_000_000:
            return f"{meta.get('name')} is too large to read here ({meta.get('size')} bytes)."
        r = await client().request("GET", "drive", f"/files/{ident(file_id)}",
                                   params={"alt": "media", "supportsAllDrives": "true"}, raw=True)
        return _cap(f"# {meta.get('name')}\n\n{r.text}")
    return _dump({"note": "This file type can't be read as text here.", **meta})


# --- Docs -------------------------------------------------------------------

def _doc_text(elements: list) -> str:
    out = []
    for el in elements or []:
        if "paragraph" in el:
            for pe in el["paragraph"].get("elements", []):
                out.append(pe.get("textRun", {}).get("content", ""))
        elif "table" in el:
            for row in el["table"].get("tableRows", []):
                cells = [_doc_text(c.get("content", [])).strip() for c in row.get("tableCells", [])]
                out.append(" | ".join(cells) + "\n")
        elif "tableOfContents" in el:
            out.append(_doc_text(el["tableOfContents"].get("content", [])))
    return "".join(out)


@server.tool(annotations=READ)
async def docs_read(document_id: str) -> str:
    """Read a Google Doc's title and text, tables included."""
    doc = await client().request("GET", "docs", f"/documents/{ident(document_id)}")
    return _cap(f"# {doc.get('title', '')}\n\n{_doc_text(doc.get('body', {}).get('content', []))}")


@server.tool(annotations=ADD)
async def docs_create(title: str, text: str = "", folder_id: str = "") -> str:
    """Create a Google Doc in Ayman's Drive (or in `folder_id`), optionally with starting text.
    The new doc is private to Ayman: this spoke can't share it."""
    if folder_id:
        await _check_internal(folder_id, "folder")
    doc = await client().request("POST", "docs", "/documents", json_body={"title": title})
    doc_id = doc["documentId"]
    if text:
        await client().request("POST", "docs", f"/documents/{ident(doc_id)}:batchUpdate", json_body={
            "requests": [{"insertText": {"endOfSegmentLocation": {}, "text": text}}]})
    if folder_id:
        await _move_new_file(doc_id, folder_id)
    return _dump({"document_id": doc_id, "link": f"https://docs.google.com/document/d/{doc_id}/edit"})


@server.tool(annotations=ADD)
async def docs_append_text(document_id: str, text: str) -> str:
    """Add text to the end of a Google Doc. Nothing already there changes."""
    await _check_internal(document_id, "doc")
    await client().request("POST", "docs", f"/documents/{ident(document_id)}:batchUpdate", json_body={
        "requests": [{"insertText": {"endOfSegmentLocation": {}, "text": text}}]})
    return f"Added {len(text)} characters to the end of the doc."


@server.tool(annotations=OVERWRITE)
async def docs_replace_text(document_id: str, find: str, replace_with: str, match_case: bool = True) -> str:
    """Replace every occurrence of `find` in a Google Doc. Read the doc first; this changes
    existing text."""
    if not find:
        return "find can't be empty."
    await _check_internal(document_id, "doc")
    body = await client().request("POST", "docs", f"/documents/{ident(document_id)}:batchUpdate", json_body={
        "requests": [{"replaceAllText": {"containsText": {"text": find, "matchCase": match_case},
                                         "replaceText": replace_with}}]})
    n = (body.get("replies") or [{}])[0].get("replaceAllText", {}).get("occurrencesChanged", 0)
    return f"Replaced {n} occurrence(s)."


# --- Sheets -----------------------------------------------------------------

@server.tool(annotations=READ)
async def sheets_get(spreadsheet_id: str) -> str:
    """A spreadsheet's title and its tabs with their sizes."""
    body = await client().request("GET", "sheets", f"/spreadsheets/{ident(spreadsheet_id)}", params={
        "fields": "properties.title,sheets.properties(sheetId,title,gridProperties(rowCount,columnCount))"})
    return _dump({"title": body.get("properties", {}).get("title"),
                  "tabs": [s.get("properties", {}) for s in body.get("sheets", [])]})


@server.tool(annotations=READ)
async def sheets_read_range(spreadsheet_id: str, range: str, as_csv: bool = False) -> str:
    """Read cells, e.g. range "Orders!A1:F200" or "Orders". Values come back as shown in the
    sheet; set as_csv for CSV text."""
    body = await client().request("GET", "sheets",
                                  f"/spreadsheets/{ident(spreadsheet_id)}/values/{seg(range)}")
    values = body.get("values", [])
    if as_csv:
        buf = io.StringIO()
        csv.writer(buf).writerows(values)
        return _cap(buf.getvalue())
    return _dump({"range": body.get("range"), "values": values})


@server.tool(annotations=ADD)
async def sheets_create(title: str, tabs: list[str] | None = None, folder_id: str = "") -> str:
    """Create a spreadsheet in Ayman's Drive (or in `folder_id`), with optional tab names.
    Private to Ayman: this spoke can't share it."""
    if folder_id:
        await _check_internal(folder_id, "folder")
    body: dict = {"properties": {"title": title}}
    if tabs:
        body["sheets"] = [{"properties": {"title": t}} for t in tabs]
    sheet = await client().request("POST", "sheets", "/spreadsheets", json_body=body)
    sid = sheet["spreadsheetId"]
    if folder_id:
        await _move_new_file(sid, folder_id)
    return _dump({"spreadsheet_id": sid, "link": f"https://docs.google.com/spreadsheets/d/{sid}/edit"})


@server.tool(annotations=ADD)
async def sheets_append_rows(spreadsheet_id: str, range: str, rows: list[list[Any]]) -> str:
    """Add rows after the last row of a table, e.g. range "Orders!A:F". Existing rows don't change.
    Values are stored exactly as given: text starting with "=" stays text, not a formula."""
    await _check_internal(spreadsheet_id, "sheet")
    body = await client().request(
        "POST", "sheets", f"/spreadsheets/{ident(spreadsheet_id)}/values/{seg(range)}:append",
        params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
        json_body={"values": rows})
    updated = body.get("updates", {})
    return f"Added {updated.get('updatedRows', len(rows))} row(s) at {updated.get('updatedRange', range)}."


@server.tool(annotations=OVERWRITE)
async def sheets_update_range(spreadsheet_id: str, range: str, values: list[list[Any]]) -> str:
    """Write values into cells, replacing what is there, e.g. range "Prices!B2:C10".
    Read the range first. Values are stored exactly as given (no formulas)."""
    await _check_internal(spreadsheet_id, "sheet")
    body = await client().request(
        "PUT", "sheets", f"/spreadsheets/{ident(spreadsheet_id)}/values/{seg(range)}",
        params={"valueInputOption": "RAW"}, json_body={"values": values})
    return f"Updated {body.get('updatedCells', 0)} cell(s) in {body.get('updatedRange', range)}."


# --- Slides -----------------------------------------------------------------

def _shape_text(element: dict) -> str:
    out = []
    for te in element.get("shape", {}).get("text", {}).get("textElements", []):
        out.append(te.get("textRun", {}).get("content", ""))
    for row in element.get("table", {}).get("tableRows", []):
        cells = []
        for cell in row.get("tableCells", []):
            cells.append("".join(te.get("textRun", {}).get("content", "")
                                 for te in cell.get("text", {}).get("textElements", [])).strip())
        out.append(" | ".join(cells) + "\n")
    for child in element.get("elementGroup", {}).get("children", []):
        out.append(_shape_text(child))
    return "".join(out)


@server.tool(annotations=READ)
async def slides_read(presentation_id: str) -> str:
    """Read a Google Slides deck: title, then each slide's text and speaker notes."""
    deck = await client().request("GET", "slides", f"/presentations/{ident(presentation_id)}")
    parts = [f"# {deck.get('title', '')}"]
    for i, slide in enumerate(deck.get("slides", []), 1):
        text = "".join(_shape_text(el) for el in slide.get("pageElements", []))
        notes_page = slide.get("slideProperties", {}).get("notesPage", {})
        notes = "".join(_shape_text(el) for el in notes_page.get("pageElements", []))
        parts.append(f"\n## Slide {i}\n{text.strip()}" + (f"\n\nNotes: {notes.strip()}" if notes.strip() else ""))
    return _cap("\n".join(parts))


@server.tool(annotations=ADD)
async def slides_create(title: str, folder_id: str = "") -> str:
    """Create an empty Google Slides deck in Ayman's Drive (or in `folder_id`). Private to Ayman."""
    if folder_id:
        await _check_internal(folder_id, "folder")
    deck = await client().request("POST", "slides", "/presentations", json_body={"title": title})
    pid = deck["presentationId"]
    if folder_id:
        await _move_new_file(pid, folder_id)
    return _dump({"presentation_id": pid, "link": f"https://docs.google.com/presentation/d/{pid}/edit"})


@server.tool(annotations=OVERWRITE)
async def slides_replace_text(presentation_id: str, find: str, replace_with: str, match_case: bool = True) -> str:
    """Replace every occurrence of `find` across a deck (fill a template's {{placeholders}}, fix a
    name). Read the deck first; this changes existing text."""
    if not find:
        return "find can't be empty."
    await _check_internal(presentation_id, "deck")
    body = await client().request("POST", "slides", f"/presentations/{ident(presentation_id)}:batchUpdate",
                                  json_body={"requests": [{"replaceAllText": {
                                      "containsText": {"text": find, "matchCase": match_case},
                                      "replaceText": replace_with}}]})
    n = (body.get("replies") or [{}])[0].get("replaceAllText", {}).get("occurrencesChanged", 0)
    return f"Replaced {n} occurrence(s)."


async def _check_internal(file_id: str, what: str = "file") -> None:
    """Refuse when the file or folder is shared outside the company or by link."""
    try:
        body = await client().request("GET", "drive", f"/files/{ident(file_id)}/permissions", params={
            "fields": "permissions(type,domain,emailAddress,role)", "supportsAllDrives": "true",
            "pageSize": 100})
    except GoogleError as e:
        raise GoogleError(f"couldn't check who the {what} is shared with, so nothing was changed ({e})") from e
    outside = []
    for perm in body.get("permissions", []):
        kind = perm.get("type")
        if kind == "anyone":
            outside.append("anyone with the link")
        elif kind == "domain" and str(perm.get("domain", "")).lower() not in INTERNAL_DOMAINS:
            outside.append(f"the {perm.get('domain')} domain")
        elif kind in ("user", "group"):
            domain = str(perm.get("emailAddress", "")).rpartition("@")[2].lower()
            if domain not in INTERNAL_DOMAINS:
                outside.append(f"someone at {domain or 'an unknown address'}")
    if outside:
        raise GoogleError(f"this {what} is shared with {', '.join(sorted(set(outside)))}, so the hub won't write "
                          "to it: an edit there reaches people outside the company. Ask Ayman to do it himself.")


async def _move_new_file(file_id: str, folder_id: str) -> None:
    """Put a file this spoke just created into a folder (only ever used on new files).
    The folder was checked before the file was made."""
    meta = await client().request("GET", "drive", f"/files/{ident(file_id)}",
                                  params={"fields": "parents", "supportsAllDrives": "true"})
    await client().request("PATCH", "drive", f"/files/{ident(file_id)}", params={
        "addParents": folder_id, "removeParents": ",".join(meta.get("parents", [])),
        "supportsAllDrives": "true", "fields": "id"}, json_body={})


# --- Calendar (read-only) ---------------------------------------------------

EVENT_FIELDS = ("id", "summary", "start", "end", "location", "attendees", "organizer", "htmlLink",
                "status", "description", "hangoutLink", "conferenceData")


def _event(e: dict) -> dict:
    out = {k: e[k] for k in EVENT_FIELDS if k in e}
    if "attendees" in out:
        out["attendees"] = [{"email": a.get("email"), "response": a.get("responseStatus")} for a in out["attendees"]]
    if "description" in out:
        out["description"] = out["description"][:2000]
    return out


@server.tool(annotations=READ)
async def calendar_list_events(time_min: str, time_max: str, query: str = "", calendar_id: str = "primary",
                               max_results: int = 50) -> str:
    """Events between two times (RFC 3339, e.g. 2026-11-09T00:00:00Z), optionally matching
    `query`. Read-only: this spoke can't create, change or answer events."""
    params = {"timeMin": time_min, "timeMax": time_max, "singleEvents": "true", "orderBy": "startTime",
              "maxResults": max(1, min(max_results, 250))}
    if query:
        params["q"] = query
    body = await client().request("GET", "calendar", f"/calendars/{calendar_ident(calendar_id)}/events", params=params)
    return _dump({"events": [_event(e) for e in body.get("items", [])]})


@server.tool(annotations=READ)
async def calendar_get_event(event_id: str, calendar_id: str = "primary") -> str:
    """One calendar event in full."""
    e = await client().request("GET", "calendar", f"/calendars/{calendar_ident(calendar_id)}/events/{ident(event_id)}")
    return _dump(_event(e))


def main(argv: list[str] | None = None) -> None:
    import argparse

    p = argparse.ArgumentParser(prog="ayman_hub.spokes.google")
    p.add_argument("--internal-domains", default="telemachus.io",
                   help="comma-separated company domains; files shared beyond these are not written to")
    args = p.parse_args(argv)
    INTERNAL_DOMAINS.clear()
    INTERNAL_DOMAINS.update(d.strip().lower() for d in args.internal_domains.split(",") if d.strip())
    server.run("stdio")


if __name__ == "__main__":
    main()
