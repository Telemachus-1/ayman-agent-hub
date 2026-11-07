# Telemachus company rules

*Adopted 2026-11-07 from Arthur's playbooks (v6.1, 16 Oct 2026) as company-wide practice. Arthur's fleet mechanics (account 1, `tell`, herdr, watchers, lanes) are not adopted: they are for his setup only.*

## Linear

Live teams (checked 7 Nov 2026):

| Key | Team | Use it for |
|---|---|---|
| SYS | Systems | Systems, data, integrations, ops. File with the **Ask S&L** template, add the BU label. |
| WHS | Warehousing | Warehouse build-out, equipment, process. File with **Ask Warehousing**. |
| LOG | Logistics | Shipments, carriers, chasing, orders people can't see. |
| TEL | Telemachus | Catch-all for anything not on SYS. |
| ATH | Athena | Athena work. |
| DIR | Direct to consumer | D2C planning. |
| SOC | Socials and marketing | Socials and marketing. |
| LUS | Lush Lobster | **Off-limits. Never touch.** |

- **One ask per card, one owner.** Check for an existing card before you create one.
- **Ask for the outcome, not the method.** Action (verb first), what for, urgency, size, "done when".
- **Urgency clock on SYS and WHS** (from the team descriptions): Urgent 24 h, High 48 h, Medium 96 h, Low 240 h. Give a reason for High or Urgent.
- **Done** only when the result is clear and checkable. If it needs a person's judgement, it goes to **In Review**.
- **Results** say what was done, where it is, what to check and who reviewed it.
- PRs say "Refs <card>", never "Fixes" or "Closes".

## Who decides

- Money leaving, legal and tax sign-off, access grants and production settings are Arthur's calls company-wide.
- Never decide a question that is already open with Arthur or a BU owner. Check first.

## Data and systems

- **Data fixes are never done by hand or as code.** Ask for them on SYS. They run as reviewed data packs. Ayman's agents never sign an approval line (`msdb-ok`, `lyt-ok`).
- **Features are generic for every BU.** A BU difference is a setting, never code that names one BU.
- **Helm:** every write previews first and returns a confirm token. Show the summary, wait for Ayman, then confirm with the same arguments. Never invent or reuse a token. Money is a decimal string. Products are identified by EAN within a BU, never by title alone.
- **Helm cannot operate the warehouse** without the warehouse grant. Without it, say it is warehouse work and escalate.

## Code

- Ayman does not ship code to Mothership or Ajax. When he reviews and merges a PR:
  - **Mothership merges only through GitHub's merge queue.** Never a direct merge (it would skip the tests), and never push to, rebase or jump a queued PR.
  - Risky changes (money, stock, customer contact, data, security) need an independent review that says SHIP before the queue. A FIX FIRST blocks the merge.
- New features are tried locally before any PR.

## Secrets

- Never paste or print a password, key or token anywhere. Check a secret only by its length.
- Never snapshot a web page that shows a password field.
