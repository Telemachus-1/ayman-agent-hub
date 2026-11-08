# ayman-hub

One MCP endpoint in front of every service Ayman's agents use. Claude and Grokbot each get **one URL and their own key** (Paradev's Claude Code uses Claude's), instead of a separate connector per service. The real service keys live only in the hub.

Modelled on Basil's `basil-hub` (systems onboarding guide, 25 Oct 2026), with one difference: this hub is built to run on a public HTTPS address, because Ayman's agents run in the cloud.

## What it does on every call

1. **Key check.** Every path except `/healthz` needs a valid, unrevoked hub key, or it gets a 401 before anything else runs.
2. **Policy** (`ayman_hub/policy.py`). **Writes are blocked unless listed.**
   - Is the kill switch off? Is the spoke switched on, and is this client allowed on it?
   - Is the name plain ASCII? Is it a send, pay, delete, share, invite, post, merge, schedule, submit or cancel-type tool? Those are **blocked in code**, however the name is spelt (`HTTPSend`, `resend`, look-alike letters), and can't be unblocked in config.
   - Is it a read? Only if its name starts with a read verb and has no write verb. A service marking a tool "read-only" isn't enough on its own.
   - Anything else is a write: it must be in the spoke's `allow_tools`, and in `allow_destructive` unless the service marks it safe.
   - **Arguments:** a menu tool's `action` gets the same blocked-in-code check and must be in `allow_actions`; a `confirm`-type argument is refused unless the client is in `confirm_clients`, which is empty, so agents preview and Ayman confirms.
3. **Forward** to the service, if allowed.
4. **Audit:** one JSON line per call, recording who, which spoke, which tool, allowed or blocked, and how long it took. **Never arguments or results.** It rolls over at 20 MB.

Agents only *see* the tools they're allowed to call. Tools are named `<spoke>__<tool>`, for example `linear__list_issues`. `hub__status` shows what's connected and, under `hidden_tools`, what is held back and why: use it to tune each spoke on its first day. Agents never see raw connection errors; those go to the server log.

## Files

| Path | What |
|---|---|
| `spokes.toml` | The services, in the agreed order, with each one's rules. All switched off until their step |
| `ayman_hub/` | The hub: `config`, `policy`, `state` (keys, audit log, kill switch), `oauth` (sign-in), `upstream`, `gateway`, `app`, `cli`, and `spokes/` (the hub's own Google and Gmail spokes) |
| `tests/` | 100 tests, including end-to-end runs through a real hub against a fake service, a fake sign-in service and a fake Google |

Runtime state lives **outside the repo**, in `AYMAN_HUB_HOME` (default `~/.ayman-hub`), all owner-only:

| File | What |
|---|---|
| `clients.json` | The hash of each client key, never the key itself |
| `audit.jsonl` | The audit log |
| `OFF` | Present when the kill switch is on |
| `oauth/google-account.json` | The one Google sign-in (refresh token only) shared by the Google and Gmail spokes |
| `oauth/<spoke>.json` | A sign-in spoke's tokens and the service's token address. A pre-registered app's secret (Slack) is never written here |

## Commands

```bash
python3 -m ayman_hub doctor                 # check setup; never prints secret values
python3 -m ayman_hub client add claude      # prints a new key ONCE
python3 -m ayman_hub client revoke grokbot  # cut off one app
python3 -m ayman_hub off                    # kill switch: refuse every call
python3 -m ayman_hub on
python3 -m ayman_hub status                 # switch, clients, last audit lines
python3 -m ayman_hub login notion           # one-time sign-in for auth = "oauth" spokes
python3 -m ayman_hub logout notion          # forget that sign-in
python3 -m ayman_hub google-login           # one Google sign-in for the google and gmail spokes
python3 -m ayman_hub serve --port 8742      # run it
python3 -m pytest                           # tests
```

## Adding a spoke

1. Fill in its block in `spokes.toml`. Real keys never go there: `auth_env` names the environment variable that holds the key.
2. Key spokes: put the key in the server's owner-only environment file. Sign-in spokes (`auth = "oauth"`): run `login <spoke>` on the server, open the link, approve as Ayman, and paste back the address the browser lands on (an error page is fine; the code is in the address). The hub then refreshes the sign-in on its own. If it ever lapses, the spoke shows "run `ayman-hub login <spoke>`" in `hub__status`; the hub never waits for a person.
3. Run `doctor`. Switch the spoke on (`enabled = true`), restart, and check `hub__status`.
4. Test a read, an allowed write and a blocked call from each client, and check the audit log.
5. Remove that service's direct connector from each tool.

Changing what's blocked in code (`HARD_DENY_TOKENS` in `policy.py`) needs a reviewed code change, deliberately.

## Build order (agreed 8 Nov 2026)

| Step | Spoke | Status |
|---|---|---|
| 0 | Hub skeleton: keys, policy, audit, kill switch, doctor | **Built and tested** |
| 0b | Sign-in (`login`) for services without API keys, with automatic refresh | **Built and tested** |
| 1 | Linear | Config ready; API key as bearer (confirmed). Needs `LINEAR_API_KEY` on the server |
| 2 | Notion | Config ready; sign-in only (confirmed). `login notion` on deploy day |
| 3 | Granola | Config ready; sign-in only (confirmed). `login granola` on deploy day |
| 4 | Google: Drive, Docs, Sheets, Slides, Calendar | **Built and tested** against a fake Google. Needs the Google OAuth client and `google-login` on deploy day |
| 5 | Gmail: ayman@ plus six logistics@ group mailboxes | **Built and tested** (read, search by mailbox, label, archive; no send or draft). Same Google sign-in |
| 6 | Slack | Read config ready (sign-in through our own Slack app with MCP on: needs its client id and secret). Still to build: the reviewed two-step post to bot channels |
| 7 | Helm | Config ready: https://apothekon.io/mcp, sign-in approved by Ayman (no refresh token, so re-sign-in when it lapses). Allowed actions set from Helm's own menus; money, PO, invoice-issuing, ledger, warehouse-job and outside-email actions left out |
| 8 | WhatsApp (optional) | Separate decision |
| — | Hosting on a company server, public HTTPS, `allowed_hosts` | At the end |

## Security review (8 Nov 2026)

An independent review found that the first policy trusted service markings and allowed every write that wasn't denied, and that Helm's menu tools could reach payments through their `action` argument. Fixed: writes blocked unless listed, argument checks, stricter name matching, fixed-wording status, outside-sharing checks and raw values in the Google spoke, a stricter Google sign-in, id checks, the hub's own Python and an owner-only working folder for its spokes, https-only spokes, and audit limits.

Still open, by design or for later: TLS comes from the proxy in front; no rate limiting yet; a spoke that drops mid-run isn't reconnected until restart; run the CLI with the same `AYMAN_HUB_HOME` as the service, or `off` won't reach it (`doctor` prints the home it uses).

## Before it goes public

- Set `[hub].allowed_hosts` to the public host name. This turns on DNS-rebinding protection.
- Put it behind HTTPS (for example Cloudflare, or a reverse proxy with a certificate).
- Run it as its own user, with `AYMAN_HUB_HOME` and the env file readable by that user only.
- Issue one key per client (`claude`, `grokbot`; Paradev uses Claude's) and store them in each app's connector settings.
