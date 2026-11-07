---
name: linear-card-work
description: Work a Linear card from claim to hand-back the Telemachus way — claim, progress comments, blockers, the Result comment and In Review. Use for any task that lasts longer than one session, or when Ayman's agents pick up a card.
---

# Work a Linear card

*Sources: "How S&L works — the contract" Part 3 (updated 30 Oct 2026), "How Telemachus works" (21 Oct 2026), Arthur's playbooks v6.1. Quick admin that fits in one session needs no card (Ayman, 7 Nov 2026).*

Everything starts and ends in Linear. If it's not on the card, it didn't happen.

## Start

1. **Read before you write.** Read the card, its comments (`list_comments`), linked cards and the knowledge base. Check whether the work already exists, here or in another BU.
2. **Ask first.** If the "Done when" is unclear, ask Ayman before starting.
3. **Claim:** move it to **In Progress** and comment `Claimed — <who>. Plan: <one line>.` One claim at a time.

## While working

- Comment only on **material decisions, blockers and evidence**. No "still working" comments.
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
2. **Objectively done** (merged code, a receipt, a number that matches): it can go straight to **Done**, saying so in the Result.
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
