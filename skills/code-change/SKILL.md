---
name: code-change
description: Make a code change in a Telemachus repo (Apothekon/Mothership, Ajax, Lytheron or others) from branch to PR, the way the company's engineers do. Use whenever an agent writes or changes code for Ayman, for example in a Paradev (Superset) workspace.
---

# Making a code change

*Sources: Arthur's Technical playbook v6.1 §2–4, 6–8, and "Apothekon CI checks, and how each engineer works with them" (Linear, 6 Nov 2026). Arthur's machine-only tools (`pr-open`, `pr-push`, `suite-slot`, `folder-lock`, `tell`, `msro`, `msdb`) don't exist in Paradev or Grokbot; the laptop path below replaces them.*

## Access

GitHub access to company repos is need-to-know and granted by Arthur. On 7 Nov 2026 Ayman's account could not see `Telemachus-1/mothership` or `Telemachus-1/ajax-wms`. If a task needs one, ask Ayman to request access from Arthur. Don't work around it.

## Before writing code

1. **Linear first.** One card per outcome (see `linear-ask` / `linear-card-work`). The card key goes in the branch and the PR title.
2. **Ask first.** Confirm the outcome and the "done when" with Ayman.
3. **Product first.** If a job can be done through Helm or the app, do it there. Code is for what the product can't do.
4. **Data fixes are never code.** Correcting specific rows (a job's counts, an order's status, an invoice link) is not a PR or a migration. Ask for a data pack (see `linear-ask`).

## Branch

- Branch from **current `main`**: `git fetch origin main && git switch -c <agent>/<card-key>-<topic> origin/main`.
- Never commit on `main`, and never work in someone else's checkout or branch.
- **Never use `git stash`.** To set work aside, make a work-in-progress commit on your own branch.

## Build

- **Less code. Read before you write.** Find the existing route or seam before adding a new one. No second entry point for the same job.
- **Generic for every BU.** Never name a BU (or hard-code its ID) in code. A BU difference is a setting in the data.
- **No new cross-area imports.** One business area per PR; go through shared core or an existing seam.
- **Parked features stay**, fully behind their switch, with no side effects while off. Delete only what is truly dead (no caller, not parked, nobody wants it).
- **Never print a secret.** Check a value only by its length. Never put a secret on a command line.

## Test once, locally

CI on the PR's exact head is **the** test run. While building, run only the tests for the code you change:

- Backend (Apothekon): `cd app/backend && ./run_local_tests.sh tests/test_x.py -q`. **Never bare `pytest`:** it truncates whatever database `.env` points at. Check that `.env` does **not** point at production before running anything (`.env.example` does; see SYS-6749).
- Frontend: `cd app/frontend && npx tsc --noEmit && npx vitest run <file>`.
- Format: `make format`. Everything CI's fast checks do, plus affected tests: `make preflight`.
- Money, stock and security changes need tests that **prove the business rule**.
- Stop your own dev servers and throwaway databases when finished. Never kill processes by pattern.

## Local first

**New features run locally first, for Ayman to try, before any PR.** Give him how to see it. No PR until he says "ship it". (Staging runs `main` only today, so a branch can't be tried there yet; SYS-6748.)

## Open the PR (only when ready to merge)

- **No draft PRs.** Unfinished work stays a branch.
- `gh pr create --repo Telemachus-1/<repo> --title "<CARD-KEY> <outcome>"`. In the body:
  - `Refs <CARD-KEY>` (never "Fixes" or "Closes");
  - what changed and why;
  - how it was tested;
  - a `Why-large:` line if it's over 400 meaningful lines (aim for 50–200);
  - a `One-change:` line, or `Depends-on: #n`, if it spans areas;
  - a `HOLD: <reason>` line if it waits on an approval. Holds live on the PR, never only in chat.
- Attach the PR link to the Linear card.
- **Push less often.** Each Mothership push runs about 60 CI jobs. Batch your pushes.
- If you poll GitHub, poll no faster than every 2 minutes, pause below 2,500 remaining API calls, and stop on a 403 or 429.

Then follow `pr-review-merge`.
