---
name: linear-daily-check
description: Each weekday morning, summarise Ayman's Linear asks in five lines — what's in Triage, what's waiting for his accept, what's stale — as a section of the daily update. Proposal only; not live until Ayman approves.
---

# Proposal: daily Linear check

*Status: **Proposed** (7 Nov 2026). Source: Arthur's "How to ask S&L" guide, "a permanent agent with a loop". Ayman said "no other admin for now", so this waits for his yes.*

## What it would do

Add one section to the daily sweep, read-only:

1. **Awaiting Ayman's accept:** cards he requested that are In Review (`list_issues`, creator = me, state In Review). Oldest first, with how long each has waited.
2. **Owed by Ayman:** cards in Backlog that say `Owed by Ayman`.
3. **His asks still in Triage**, or past half their clock (`sla:at-risk`, `sla:breached`).
4. **Cards assigned to him** with no update in 5 days.

Five lines at most, each with the card link.

## What it would never do

Accept, close, comment on, reprioritise or reassign anything. Only report.
