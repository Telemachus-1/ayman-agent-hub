# Telemachus company rules

*Adopted 2026-11-07 from Arthur's playbooks (v6.1, 16 Oct 2026) as company-wide practice. Arthur's fleet mechanics (account 1, `tell`, herdr, watchers, lanes) are not adopted: they are for his setup only.*

## Linear

*Updated 7 Nov 2026 from the live Linear docs ("Asking for something — the two-minute guide", 22 Oct; "How Telemachus works", 21 Oct), which are newer than Arthur's 16 Oct playbook. Full procedures are in the `linear-ask` and `linear-card-work` skills.*

| Key | Team | Use it for |
|---|---|---|
| TEL | Telemachus | **The front door. File asks here.** S&L pull theirs into SYS or LOG and post the outcome back on the TEL card. |
| SYS | Systems | Code, data, automation, Apothekon, integrations (Arthur, Dimitri). |
| LOG | Logistics | Shipments, carriers, POs, deliveries, stock someone can't see (Basil, Arthur). |
| WHS | Warehousing | The physical warehouse: racking, kit, SOPs, the floor (Lawrence runs the floor). |
| ATH | Athena | The Athena portal (Danny's team). |
| DIR | Direct to consumer | D2C planning. |
| SOC | Socials and marketing | Socials and marketing. |
| ART | Arthur | Arthur's private board. **Never file here.** |
| LUS | Lush Lobster | **Off-limits. Never touch.** |

- **One ask per card, one owner.** Search before you create.
- **Ask for the outcome, not the method:** Action (verb first), What for, Urgency, Why urgent, Done when, Discussed with, Best person, Notes, Files.
- **BU label on every card:** TopCo, Toysellers, Booksellers, Valen Trading, Valen & Co, Athena or Systems & Logistics.
- **Priority means a date:** Urgent = a deadline, money, stock or a customer within a day (24 h); High = within about 3 days (48 h); Medium = within about 5 days (96 h); Low = within two weeks (240 h). Give a reason for High or Urgent.
- **Hand-back:** a **Result** comment (what was done, where it is, what to check), then **In Review** assigned to the requester. Nobody reviews their own work. Objectively done work can go straight to Done.
- **Backlog** only when the card says `Owed by <name>: <the one thing>`. Waiting on a named person is a blocking sub-issue, not a comment.
- **Everything is readable in Linear:** plans, reports and evidence are uploaded and linked, never a path on an agent's machine.
- PRs say "Refs <card>", never "Fixes" or "Closes", and are attached to their card.
- **Leads (22 Oct 2026):** Arthur, Dimitri and Basil. Alessa has left.

## Who decides

- Money leaving, legal and tax sign-off, access grants and production settings are Arthur's calls company-wide.
- Never decide a question that is already open with Arthur or a BU owner. Check first.

## Data and systems

- **Data fixes are never done by hand or as code.** Ask for them (file on TEL; S&L pull them into SYS). They run as reviewed data packs. Ayman's agents never sign an approval line (`msdb-ok`, `lyt-ok`).
- **Features are generic for every BU.** A BU difference is a setting, never code that names one BU.
- **Helm:** every write previews first and returns a confirm token. Show the summary, wait for Ayman, then confirm with the same arguments. Never invent or reuse a token. Money is a decimal string. Products are identified by EAN within a BU, never by title alone.
- **Helm cannot operate the warehouse** without the warehouse grant. Without it, say it is warehouse work and escalate.

## Code

Ayman rarely ships code, but whenever his agents do, the `code-change` and `pr-review-merge` skills apply in full. The essentials:

- **Mothership (Apothekon) merges only through GitHub's merge queue.** Never a direct merge, never `--admin`, and never push to, rebase or jump a queued PR.
- **Risky changes** (money, stock, customer contact, data, security, migrations) need an independent review that says SHIP before the queue. A FIX FIRST blocks the merge.
- **New features are tried locally first**, by Ayman, before any PR. No draft PRs.
- **Test once:** targeted tests locally; CI on the exact head is the full run. Never bare `pytest` in Apothekon.
- **Small PRs, one area, no BU named in code.**
- **Repo access** is need-to-know and granted by Arthur.

## Secrets

- Never paste or print a password, key or token anywhere. Check a secret only by its length.
- Never snapshot a web page that shows a password field.

## From Basil's onboarding guide (25 Oct 2026)

*Rules Basil marks as company policy, plus the lessons behind them. Adopted 8 Nov 2026. Where they repeat `AGENTS.md`, `AGENTS.md` is the short form.*

### Money (when preparing a payment for a person)
- Agents never pay. When preparing one, first check it isn't already paid on **every** rail (bank, Stripe payouts, Helm payables), by reference **and** amount.
- Bank details come only from a saved payee, never from an email (least of all one from today).
- Payments go through Helm or Revolut, never a browser dashboard.

### Correcting live data
- Live data (Supabase, Apothekon) is read-only to agents.
- A correction needs evidence: a count plus a photo, a supplier document, or a BU lead's written words. It then goes through the supported preview → confirm route, followed by a read-back.

### Reviews
- Never call a PR "reviewed" until the review is actually posted on GitHub.
- Review by a different company's agent (Codex reviewing Claude) is on hold (Ayman, 8 Nov). A separate Claude session reviews.

### Browsers and passwords
- Use your own tab, and close it after. Never change browser settings or export cookies.
- **Money sites:** a person signs in on a visible screen; the agent only reads and clicks. Never type credentials into a money site, and never replay session headers.
- **Scope browser briefs tightly:** the outcome, the exact system, the allowed actions and the hard limits. "Or the equivalent" once let an agent press the wrong button on a live store.
- A fallback route (another agent, another browser) never relaxes a send, money or delete limit.
- Passwords: copy the one login a job needs from your own vault into the agents' vault. Never bulk-copy.

### Gmail
- Never retry a "too many requests" (429) error. The mailbox cools down: wait, and say the sweep was cut short.
- Keep sweeps light: at most one sweep per 30 minutes on a shared mailbox, and one per 3 hours on a person's own.

### Hard-won lessons
- Kill processes by exact process ID only. Never `pkill`, `killall` or a pattern.
- Never press Enter on text you didn't type, and never treat suggested text as the person's answer.
- On a usage-limit menu, never pick the option that buys credits. Move the work instead.
- Never search the whole home folder (`find ~`). Search named folders, with `timeout 60`.
- One owner per thread of work. If three agents report the same thing, the owner reports it once.
