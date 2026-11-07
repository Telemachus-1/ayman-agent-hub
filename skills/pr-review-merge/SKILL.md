---
name: pr-review-merge
description: Review and merge a pull request in a Telemachus repo — independent review on the exact head, SHIP / FIX FIRST, and merging Apothekon (Mothership) only through the merge queue. Use when Ayman reviews, approves or merges a PR, or asks an agent to.
---

# Reviewing and merging a PR

*Sources: Arthur's Technical playbook v6.1 §4–5 (Arthur's rules of 16 Oct 2026) and "Apothekon CI checks, and how each engineer works with them" (Linear, 6 Nov 2026).*

## Review

- **Every PR gets one independent review on the exact head sha.** The reviewer is a separate session that never saw the author's conversation. Give it the diff, the card and the tests, not the author's argument.
- **Risky changes** (money, stock, customer contact, data, auth/security, migrations) need **SHIP** before they join the queue. Review them with the most careful model available (Opus). Routine reviews can use a faster model (Sonnet).
- **FIX FIRST blocks the merge.** If auto-merge is armed and the review says FIX FIRST, disarm it at once. Fix, push, and get a new review on the new head.
- **Check an objection before acting on it.** Reviewers are sometimes wrong; a second look confirms it first.
- **No answer is not approval.** A reviewer that errors or stops to ask is not a pass.
- Reviewers read the diff and may write a targeted probe. They don't re-run suites CI already ran.
- On Apothekon, also read the **review-on-push** agent's SHIP / FIX FIRST comment and fix its FIX FIRST items.
- The aim is **"help refine, then fix"**, never "break, then fix" after it's live.

## Merge Apothekon (Mothership)

- `main` accepts changes **only through the merge queue**. The ruleset requires three checks: **CI gate**, **Validate, gate, and generate clients**, and **preview**.
- To queue a green, reviewed PR:
  `gh pr merge <n> --repo Telemachus-1/mothership --match-head-commit <full sha>`
- **Never** use `--admin`, never merge any other way, and never push to `main`.
- **Never push to, rebase, dequeue or jump a PR that is already queued.** Each change rebuilds every running group. If you must push to a queued PR, dequeue it first, push, then queue it again.
- **Ejected from the queue?** For a flake or infra fault, re-queue. For a real failure, fix it locally and push. For a conflict, rebase. Never re-run CI by hand, and never push to "kick" it.
- **"Fixed" or "ready" always names the pushed head sha**, checked on GitHub.
- `risk review` isn't enforced by the ruleset yet (gap 1 in the CI doc), so SHIP on risky changes is still required by company rule even though CI won't stop you.

## Other repos

- **Ajax:** releases belong to Arthur's `deployer` lane. Ayman's agents never deploy Ajax or push to production.
- Other repos: follow their own `CLAUDE.md` / `AGENTS.md`. Without a merge queue, still review on the exact head first.

## Finish

Post a **Result** on the Linear card with the PR link and the merged sha (see `linear-card-work`).
