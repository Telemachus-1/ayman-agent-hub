"""A stand-in for Google's sign-in and the Drive, Docs, Sheets, Slides, Calendar and Gmail APIs.

Run:  python fake_google.py <port> <state-dir>
Only the calls the hub's spokes make are implemented. Every request is recorded in
<state-dir>/log.jsonl (method, path, query; never bodies with tokens) so tests can check
what was asked for. A Gmail search for "RATELIMIT" answers 429.
"""

import base64
import hashlib
import json
import secrets
import sys
from pathlib import Path
from urllib.parse import urlencode

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse, Response
from starlette.routing import Route

PORT, STATE = int(sys.argv[1]), Path(sys.argv[2])
CLIENT_ID, CLIENT_SECRET = "hub-client", "hub-secret"

codes: dict[str, dict] = {}
access: dict[str, str] = {}  # token -> email
refresh: dict[str, dict] = {}  # token -> {email, scope}


def b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


FILES = {
    "doc1": {"id": "doc1", "name": "Brand rules", "mimeType": "application/vnd.google-apps.document",
             "parents": ["root"]},
    "sheet1": {"id": "sheet1", "name": "Price list", "mimeType": "application/vnd.google-apps.spreadsheet",
               "parents": ["root"]},
    "deck1": {"id": "deck1", "name": "Q4 review", "mimeType": "application/vnd.google-apps.presentation",
              "parents": ["root"]},
    "txt1": {"id": "txt1", "name": "notes.txt", "mimeType": "text/plain", "size": "11", "parents": ["root"]},
    "shared1": {"id": "shared1", "name": "Supplier sheet", "mimeType": "application/vnd.google-apps.spreadsheet",
                "parents": ["root"]},
    "img1": {"id": "img1", "name": "logo.png", "mimeType": "image/png", "size": "999", "parents": ["root"]},
}
DOCS = {"doc1": {"documentId": "doc1", "title": "Brand rules", "text": "Use Valen only.\nNever mention the group.\n"}}
SHEETS = {"sheet1": {"title": "Price list", "tabs": {"Prices": [["EAN", "Price"], ["5012345678900", "9.99"]]}},
          "shared1": {"title": "Supplier sheet", "tabs": {"Orders": [["PO", "Qty"]]}}}
PERMISSIONS = {"shared1": [{"type": "user", "emailAddress": "ayman@telemachus.io", "role": "owner"},
                           {"type": "user", "emailAddress": "orders@supplier.example", "role": "writer"}],
               "linkfolder": [{"type": "anyone", "role": "reader"}]}
DECKS = {"deck1": {"presentationId": "deck1", "title": "Q4 review", "slides": ["Hello {{name}}", "Numbers"]}}
EVENTS = {"ev1": {"id": "ev1", "summary": "Supplier call", "start": {"dateTime": "2026-11-09T10:00:00Z"},
                  "end": {"dateTime": "2026-11-09T10:30:00Z"},
                  "attendees": [{"email": "a@b.c", "responseStatus": "accepted", "self": True}],
                  "description": "Agenda"}}
LABELS = {"INBOX": {"id": "INBOX", "name": "INBOX", "type": "system"},
          "TRASH": {"id": "TRASH", "name": "TRASH", "type": "system"},
          "Label_L": {"id": "Label_L", "name": "Logistics", "type": "user"},
          "Label_2": {"id": "Label_2", "name": "Triage/Must respond", "type": "user"}}
THREADS = {
    "t1": {"labels": {"INBOX", "UNREAD"}, "messages": [{
        "headers": {"From": "DHL <noreply@dhl.com>", "To": "logistics@valentrading.com", "Subject": "Delivery delayed",
                    "Date": "Sun, 8 Nov 2026 09:00:00 +0000"},
        "html": "<p>Your parcel is <b>delayed</b>.</p><script>x()</script>", "file": "label.pdf"}]},
    "t2": {"labels": {"INBOX"}, "messages": [{
        "headers": {"From": "Basil <basil@telemachus.io>", "To": "ayman@telemachus.io", "Subject": "Hub",
                    "Date": "Sun, 8 Nov 2026 10:00:00 +0000"}, "text": "Looks good."}]},
}


def log(request: Request, **extra) -> None:
    with (STATE / "log.jsonl").open("a") as f:
        f.write(json.dumps({"method": request.method, "path": request.url.path,
                            "query": dict(request.query_params.multi_items()), **extra}) + "\n")


def gerr(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": status, "message": message}}, status_code=status)


async def auth(request: Request):
    q = request.query_params
    log(request)
    code = secrets.token_urlsafe(8)
    hint = q.get("login_hint", "")
    codes[code] = {"challenge": q["code_challenge"], "scope": q["scope"],
                   "email": "someone.else@gmail.com" if hint.startswith("wrong") else hint,
                   "redirect": q["redirect_uri"], "drop": "drop_scope" in hint, "extra": "extra_scope" in hint}
    return RedirectResponse(f"{q['redirect_uri']}?{urlencode({'code': code, 'state': q['state']})}", status_code=302)


async def token(request: Request):
    form = await request.form()
    log(request, grant=form.get("grant_type"))
    if form.get("client_id") != CLIENT_ID or form.get("client_secret") != CLIENT_SECRET:
        return JSONResponse({"error": "invalid_client"}, status_code=401)
    if form["grant_type"] == "authorization_code":
        c = codes.pop(form["code"], None)
        verifier = form.get("code_verifier", "")
        expect = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        if not c or c["challenge"] != expect or c["redirect"] != form.get("redirect_uri"):
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        at, rt = "ya29." + secrets.token_urlsafe(8), "1//" + secrets.token_urlsafe(8)
        scope = " ".join(s for s in c["scope"].split() if not (c["drop"] and s.endswith("gmail.modify")))
        if c["extra"]:
            scope += " https://www.googleapis.com/auth/calendar"
        access[at], refresh[rt] = c["email"], {"email": c["email"], "scope": scope}
        return JSONResponse({"access_token": at, "refresh_token": rt, "expires_in": 3599, "scope": scope,
                             "token_type": "Bearer"})
    if form["grant_type"] == "refresh_token":
        r = refresh.get(form["refresh_token"])
        if not r:
            return JSONResponse({"error": "invalid_grant", "error_description": "Token has been expired or revoked."},
                                status_code=400)
        at = "ya29." + secrets.token_urlsafe(8)
        access[at] = r["email"]
        return JSONResponse({"access_token": at, "expires_in": 3599, "token_type": "Bearer"})
    return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)


def seed(request: Request):
    """Test helper: make a refresh token without a browser."""
    rt = request.query_params["rt"]
    refresh[rt] = {"email": request.query_params.get("email", "ayman@telemachus.io"), "scope": ""}
    return PlainTextResponse("ok")


def authed(request: Request) -> str | None:
    h = request.headers.get("authorization", "")
    return access.get(h.removeprefix("Bearer ")) if h.startswith("Bearer ") else None


async def api(request: Request):
    path = request.url.path
    if path == "/token":
        return await token(request)
    if path == "/o/oauth2/v2/auth":
        return await auth(request)
    if path == "/seed":
        return seed(request)
    log(request)
    who = authed(request)
    if not who:
        return gerr(401, "Request had invalid authentication credentials.")
    q = request.query_params
    body = await request.json() if request.method in ("POST", "PUT", "PATCH") and await request.body() else {}

    if path == "/oauth2/v3/userinfo":
        return JSONResponse({"email": who, "email_verified": True, "hd": who.rpartition("@")[2]})

    # Drive
    if path == "/drive/v3/files":
        return JSONResponse({"files": [FILES["doc1"], FILES["sheet1"]], "nextPageToken": "p2"})
    if path.startswith("/drive/v3/files/"):
        rest = path.removeprefix("/drive/v3/files/")
        fid, _, sub = rest.partition("/")
        f = FILES.get(fid) or ({"id": fid, "name": fid, "mimeType": "application/vnd.google-apps.folder"}
                                if fid in ("folderX", "linkfolder") else None)
        if not f:
            return gerr(404, f"File not found: {fid}.")
        if sub == "permissions":
            return JSONResponse({"permissions": PERMISSIONS.get(fid, [
                {"type": "user", "emailAddress": "ayman@telemachus.io", "role": "owner"}])})
        if request.method == "PATCH":
            f["parents"] = [q["addParents"]]
            return JSONResponse({"id": fid})
        if sub == "export":
            if fid in DOCS:
                return PlainTextResponse(DOCS[fid]["text"])
            if fid in SHEETS:
                rows = next(iter(SHEETS[fid]["tabs"].values()))
                return PlainTextResponse("\n".join(",".join(r) for r in rows))
            return PlainTextResponse("\n".join(DECKS[fid]["slides"]))
        if q.get("alt") == "media":
            return PlainTextResponse("hello notes")
        return JSONResponse(f)

    # Docs
    if path == "/docs/v1/documents" and request.method == "POST":
        did = "doc" + secrets.token_hex(3)
        DOCS[did] = {"documentId": did, "title": body["title"], "text": ""}
        FILES[did] = {"id": did, "name": body["title"], "mimeType": "application/vnd.google-apps.document",
                      "parents": ["root"]}
        return JSONResponse({"documentId": did, "title": body["title"]})
    if path.startswith("/docs/v1/documents/"):
        rest = path.removeprefix("/docs/v1/documents/")
        did, _, action = rest.partition(":")
        d = DOCS.get(did)
        if not d:
            return gerr(404, "Requested entity was not found.")
        if action == "batchUpdate":
            replies = []
            for r in body["requests"]:
                if "insertText" in r:
                    d["text"] += r["insertText"]["text"]
                    replies.append({})
                if "replaceAllText" in r:
                    find = r["replaceAllText"]["containsText"]["text"]
                    n = d["text"].count(find)
                    d["text"] = d["text"].replace(find, r["replaceAllText"]["replaceText"])
                    replies.append({"replaceAllText": {"occurrencesChanged": n}})
            return JSONResponse({"replies": replies})
        content = [{"paragraph": {"elements": [{"textRun": {"content": line + "\n"}}]}}
                   for line in d["text"].splitlines()]
        content.append({"table": {"tableRows": [{"tableCells": [
            {"content": [{"paragraph": {"elements": [{"textRun": {"content": "Brand"}}]}}]},
            {"content": [{"paragraph": {"elements": [{"textRun": {"content": "Valen"}}]}}]}]}]}})
        return JSONResponse({"documentId": did, "title": d["title"], "body": {"content": content}})

    # Sheets
    if path == "/sheets/v4/spreadsheets" and request.method == "POST":
        sid = "sheet" + secrets.token_hex(3)
        tabs = [s["properties"]["title"] for s in body.get("sheets", [])] or ["Sheet1"]
        SHEETS[sid] = {"title": body["properties"]["title"], "tabs": {t: [] for t in tabs}}
        FILES[sid] = {"id": sid, "name": body["properties"]["title"], "parents": ["root"],
                      "mimeType": "application/vnd.google-apps.spreadsheet"}
        return JSONResponse({"spreadsheetId": sid})
    if path.startswith("/sheets/v4/spreadsheets/"):
        rest = path.removeprefix("/sheets/v4/spreadsheets/")
        sid, _, sub = rest.partition("/")
        s = SHEETS.get(sid)
        if not s:
            return gerr(404, "Requested entity was not found.")
        if not sub:
            return JSONResponse({"properties": {"title": s["title"]}, "sheets": [
                {"properties": {"sheetId": i, "title": t, "gridProperties": {"rowCount": 1000, "columnCount": 26}}}
                for i, t in enumerate(s["tabs"])]})
        rng = sub.removeprefix("values/")
        rng, _, action = rng.partition(":append") if rng.endswith(":append") else (rng, "", "")
        tab = rng.split("!")[0]
        if tab not in s["tabs"]:
            return gerr(400, f"Unable to parse range: {rng}")
        rows = s["tabs"][tab]
        if request.url.path.endswith(":append"):
            assert q["valueInputOption"] == "RAW"
            rows.extend(body["values"])
            return JSONResponse({"updates": {"updatedRows": len(body["values"]), "updatedRange": f"{tab}!A{len(rows)}"}})
        if request.method == "PUT":
            assert q["valueInputOption"] == "RAW"
            for i, row in enumerate(body["values"]):
                while len(rows) <= i:
                    rows.append([])
                rows[i] = row
            return JSONResponse({"updatedCells": sum(len(r) for r in body["values"]), "updatedRange": rng})
        return JSONResponse({"range": f"{tab}!A1:Z{len(rows)}", "values": rows})

    # Slides
    if path == "/slides/v1/presentations" and request.method == "POST":
        pid = "deck" + secrets.token_hex(3)
        DECKS[pid] = {"presentationId": pid, "title": body["title"], "slides": [""]}
        FILES[pid] = {"id": pid, "name": body["title"], "parents": ["root"],
                      "mimeType": "application/vnd.google-apps.presentation"}
        return JSONResponse({"presentationId": pid})
    if path.startswith("/slides/v1/presentations/"):
        rest = path.removeprefix("/slides/v1/presentations/")
        pid, _, action = rest.partition(":")
        d = DECKS.get(pid)
        if not d:
            return gerr(404, "Requested entity was not found.")
        if action == "batchUpdate":
            r = body["requests"][0]["replaceAllText"]
            find = r["containsText"]["text"]
            n = sum(s.count(find) for s in d["slides"])
            d["slides"] = [s.replace(find, r["replaceText"]) for s in d["slides"]]
            return JSONResponse({"replies": [{"replaceAllText": {"occurrencesChanged": n}}]})
        slides = [{"pageElements": [{"shape": {"text": {"textElements": [{"textRun": {"content": t}}]}}}],
                   "slideProperties": {"notesPage": {"pageElements": [
                       {"shape": {"text": {"textElements": [{"textRun": {"content": "say hi" if i == 0 else ""}}]}}}]}}}
                  for i, t in enumerate(d["slides"])]
        return JSONResponse({"presentationId": pid, "title": d["title"], "slides": slides})

    # Calendar
    if path.startswith("/calendar/v3/calendars/"):
        rest = path.removeprefix("/calendar/v3/calendars/")
        if request.method != "GET":
            return gerr(403, "Insufficient Permission: calendar is read-only for this sign-in.")
        cal, _, sub = rest.partition("/events")
        if sub.startswith("/"):
            return JSONResponse(EVENTS[sub[1:]])
        return JSONResponse({"items": list(EVENTS.values())})

    # Gmail
    if path.startswith("/gmail/v1/users/me/"):
        rest = path.removeprefix("/gmail/v1/users/me/")
        if rest == "labels":
            if request.method == "POST":
                lid = "Label_" + secrets.token_hex(2)
                LABELS[lid] = {"id": lid, "name": body["name"], "type": "user"}
                return JSONResponse(LABELS[lid])
            return JSONResponse({"labels": list(LABELS.values())})
        if rest == "threads":
            if "RATELIMIT" in q.get("q", ""):
                return gerr(429, "User-rate limit exceeded.")
            return JSONResponse({"threads": [{"id": t, "snippet": "..."} for t in THREADS]})
        if rest.startswith("threads/"):
            tid, _, action = rest.removeprefix("threads/").partition("/")
            t = THREADS.get(tid)
            if not t:
                return gerr(404, "Requested entity was not found.")
            if action == "modify":
                for lid in body.get("addLabelIds", []):
                    if lid not in LABELS and lid not in ("UNREAD", "STARRED", "IMPORTANT"):
                        return gerr(400, f"Invalid label: {lid}")
                t["labels"] |= set(body.get("addLabelIds", []))
                t["labels"] -= set(body.get("removeLabelIds", []))
                return JSONResponse({"id": tid})
            msgs = []
            for i, m in enumerate(t["messages"]):
                payload = {"headers": [{"name": k, "value": v} for k, v in m["headers"].items()],
                           "mimeType": "multipart/mixed", "parts": []}
                if "text" in m:
                    payload["parts"].append({"mimeType": "text/plain", "body": {"data": b64(m["text"])}})
                if "html" in m:
                    payload["parts"].append({"mimeType": "text/html", "body": {"data": b64(m["html"])}})
                if "file" in m:
                    payload["parts"].append({"mimeType": "application/pdf", "filename": m["file"], "body": {}})
                msgs.append({"id": f"{tid}m{i}", "labelIds": sorted(t["labels"]), "snippet": "s", "payload": payload})
            return JSONResponse({"id": tid, "messages": msgs})

    return gerr(404, f"fake google has no {request.method} {path}")


app = Starlette(routes=[Route("/{path:path}", api, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])])

if __name__ == "__main__":
    STATE.mkdir(parents=True, exist_ok=True)
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
