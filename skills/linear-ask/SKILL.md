---
name: linear-ask
description: File a request (an "ask") in Telemachus's Linear the way the company expects, including handing work to the technical team. Use whenever Ayman wants something done by someone else, or a job needs a system change, a bug fix, a report, a data correction or warehouse work.
---

# File an ask in Linear

*Sources: "Asking for something — the two-minute guide" (Linear, updated 22 Oct 2026), "How Telemachus works — the contract" (21 Oct 2026), Arthur's BU lead playbook v6.1 §5, and Arthur's agent contract and ask skeleton (29 Aug 2026, in `reference/arthur-linear-2026-08-29/`). Where they disagree, the newest dated one wins; this skill already follows it. The reference README lists what changed.*

## 1. Before you file

- **Search first.** `list_issues` with keywords on TEL, SYS, LOG and WHS. If the same ask exists, comment on it or link it instead of filing a duplicate.
- **One ask per card.** Two deliverables are two cards.
- Never file on **LUS** (Lush Lobster), **ART** (Arthur's private board) or anything off-limits.

## 2. Where to file

**File in TEL (Telemachus), the front door.** Anyone files there, for anyone. If it needs Systems & Logistics, they pull it into SYS or LOG within about a minute and post the outcome back on the TEL card.

| Team | What it is | Who |
|---|---|---|
| TEL | Front door. File here. | Anyone |
| SYS | Code, data, automation, Apothekon, integrations | Arthur, Dimitri |
| LOG | Shipments, carriers, POs, deliveries, stock someone can't see | Basil, Arthur |
| WHS | The physical warehouse: racking, kit, SOPs, the floor | Lawrence runs the floor |
| ATH | The Athena portal | Danny's team |

Route by **what the work is**, not who asked. The team says who does it; the **BU label** says who it's for.

## 3. Fill the template

Use the team's template (`list_templates`, then `get_template`): **Ask Telemachus** on TEL (the light ask), or **Ask Systems** / **Ask Warehousing** / **Ask Logistics** / **Ask Athena** on those teams. **Through the API or MCP, a template does not fill itself in.** Pass it to `save_issue`, or reproduce its sections yourself in order. A nightly lint (07:00 London) moves asks with missing sections to Backlog.

For anything substantial, use the full nine sections (the Ask Systems shape) even on TEL. Keep every section:

- **Action:** one concrete, finishable deliverable, verb first. Title verb-first too.
- **What for:** what it unlocks, who asked, who benefits.
- **Urgency:** priority, size label, needed-by date.
- **Why urgent:** required for High, Urgent or Drop everything. "The customer is holding payment" is a reason; "it's important" is not.
- **Done when:** the checklist Ayman will use to accept it.
- **Discussed with:** who has already been spoken to, or "no one yet".
- **Best person:** Arthur, Dimitri, Basil, or "don't know".
- **Notes and Files:** everything needed to start without chasing.
- End with the footer line, keeping the HTML comment: `<!-- requester: Ayman | agent: <tool> | session: <name> -->`.
- **Never invent numbers, dates or deadlines** Ayman didn't give. If one is needed, ask.
- **Attach files and links in the same step** as creating the card.
- **Project:** leave it blank. S&L put every SYS and LOG issue in a project with one lead.

**Labels:**
- **BU label** (one): TopCo, Toysellers, Booksellers, Valen Trading, Valen & Co, Athena, or Systems & Logistics. Since Ayman helps every BU, use the BU the work is *for*. Never Lush Lobster.
- **Size label** (one): 5 min · 10 min · 20 min · 45 min · 1 hr · 2 hrs · 4 hrs · half-day · 1 day · 1-2 days · week+. Size is **human** focus time; agents do the paperwork, so size small when unsure.
- `larger` if it is more than a week of work. `Drop everything` only when it is literally that, which is rare.

**Priority means a date.** Use **Medium** unless Ayman says otherwise. Use Urgent or High only when "Why urgent" says why. It's a suggestion; S&L may move it and will say why.

| Priority | Means |
|---|---|
| Urgent | A deadline, money, stock or a customer affected within a day (24 h) |
| High | A stated reason, within about 3 days (48 h on the SYS/WHS clock) |
| Medium | The default, within about 5 days (96 h) |
| Low | Within two weeks (240 h): "we should think about this" |

Who is working on something, or when, never makes it Urgent.

**Owner:** if you know who should do it, assign them and file as **Todo**. If not, leave it unassigned: it waits in **Triage** up to 90 minutes, then the triage agent assigns it.

## 4. Asks for the technical team

Hand work over when the answer needs **a change to a system**, not a document or a draft:
- a new screen, report, field or button;
- something in Helm or Apothekon that doesn't work, or works wrongly;
- a job the product can't do, so it has to be done by hand each time (label `capability-gap` if you file on SYS);
- a wrong record that needs correcting in the database.

Rules:
- **Ask for the outcome, not the method.** Say what must be true, not how to build it.
- **Features are generic for every BU.** If one BU needs something different, say what is different; it becomes a setting.
- **Data corrections:** ask for them. They run as reviewed data packs. Agents never fix rows themselves and never sign an approval line.
- **New features are tried locally first.** The feature may come back for Ayman to try before it goes live.

## 5. After filing

- Don't chase with comments. Bump the priority **once** instead.
- Questions, blockers and answers stay on the card, not in Slack.
- Link related cards (blocks, blocked by, related). Links work across teams.
- When the Result comes back **In Review**, check it against "Done when". Either mark it Done or say exactly what is missing. Accepting is Ayman's call: tell him what you checked, don't accept for him.
- **Backlog** means the requester owes something, and only when the card says `Owed by <name>: <the one thing>`. If nothing is owed by name, say so on the card.
