---
name: linear-card-work
description: Work a Linear card from claim to hand-back the Telemachus way — claim, progress comments, blockers, the Result comment and In Review. Use for any task that lasts longer than one session, or when Ayman's agents pick up a card.
---

# Work a Linear card

*Sources: "How S&L works — the contract" Part 3 (updated 30 Oct 2026), "How Telemachus works" (21 Oct 2026), Arthur's playbooks v6.1, and Arthur's agent contract §3–5 (29 Aug 2026, in `reference/arthur-linear-2026-08-29/`). Quick admin that fits in one session needs no card (Ayman, 7 Nov 2026).*

Everything starts and ends in Linear. If it's not on the card, it didn't happen.

## Start

1. **Read before you write.** Read the card, its comments (`list_comments`), linked cards and the knowledge base. Check whether the work already exists, here or in another BU.
2. **Ask first.** If the "Done when" is unclear, ask Ayman before starting.
3. **Claim:** move it to **In Progress** and comment `Claimed — <agent>/<session>. Plan: <one line>.` One claim at a time.
4. **The gate:** a card must be In Progress **before** any implementation, external write or deploy. Finding or creating the card is the only thing allowed before it.

## While working

- Comment only on **material decisions, blockers, hand-offs and evidence**. No "still working" comments, and never repeat a comment. To chase, bump the priority once.
- **Blocked outside our control:** comment `Blocked: <exact blocker>` and add `blocked-external`.
- **Blocked on a named person** (bank details, an approval, a file, a decision): create a **sub-issue** for that deliverable, assign it to them, mark it **blocking** the parent, and file it in **Todo**, never Backlog. Comments do not block; sub-issues do. If their work is on another team, use a **blocked-by** relation instead (sub-issues don't cross teams).
- **Everything is readable in Linear** (Arthur, 30 Oct 2026). Upload plans, reports, evidence and documents as a Linear document or an attached file, and link them. A path on an agent's machine (`~/...`, `/tmp/...`) is never where something "is".
- Put long agent detail (plans, file lists, logs) in a collapsible `+++ Agent notes` section, so the card stays readable for people.
- Every PR is attached to its card: the key in the PR title and a link on the card.

## Hand back

1. Post the **Result** comment. It starts with the word **Result** and says:
   - what was done;
   - where it is (links);
   - what to check, and what is left;
   - who reviewed it, if anyone.
2. **Objectively done** (a receipt, a number that matches, or code that is merged **and live**, with the version): it can go straight to **Done**, saying so in the Result. Merged but not live is not done.
3. **Needs judgement** (taste, a commercial call, wording that goes outside): move it to **In Review** and **assign the requester**. Nobody reviews their own work. On a card Ayman filed himself, he is the reviewer.
4. **Canceled** or **Duplicate** always carry a comment saying why.

## Statuses, in one line each

- **Triage:** no owner yet.
- **Todo:** owned, not started.
- **In Progress:** yours.
- **In Review:** the reviewer's.
- **Backlog:** the requester owes something, stated as `Owed by <name>: <the one thing>`. Never a parking space.
- **Done:** accepted, or objectively complete.

## Minimum on every card you create, including sub-issues

Assignee, priority, BU label and a verb-first title that states the outcome.

## Platform or engineering cards (when an agent does code work)

- **Assignee:** the accountable human (Ayman, unless S&L own it). Priority set, project set, one **Area** label.
- **Title** states the outcome. **Description** states the evidence that will prove it: tests, migration numbers, production checks.
- Add `spec-ready` only when another agent could build it from the text alone.
- Put the issue key (for example `SYS-123`) in the **PR title or commit body**. Every push to `main` is recorded as a Linear release, and a card is attached to it only if its key is in the commits. No key, no trace.

## What enforces this

The `linear-lint` runs at 07:00 London. It:
- bounces In Review without a Result back to In Progress;
- asks Triage cards for their missing sections;
- nudges stale reviews;
- silently assigns and prioritises anything forgotten.
The triage agent assigns unowned asks after 90 minutes.
