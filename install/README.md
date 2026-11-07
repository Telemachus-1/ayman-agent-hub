# Installing the hub into each tool

The goal: every tool loads `AGENTS.md` on every task, and can reach `skills/` and `rules/`. One copy, in this repo; tools read it rather than keeping their own copies.

## Claude Code in Paradev (formerly Superset, cloud)

- Paradev workspaces run Claude Code against a repo. Add this repo to each workspace, or clone it alongside the work repo.
- Claude Code loads `CLAUDE.md`, which imports `AGENTS.md`.
- Skills: point Claude Code at `skills/` (copy or link into `.claude/skills/` in the workspace).
- *To confirm in Phase 2:* whether Paradev lets us set a global `~/.claude/CLAUDE.md` for all workspaces. If it does, put a one-line pointer to this repo there.

## Grokbot

- Give it read access to this repo.
- Store `AGENTS.md` as its standing instructions, and each `skills/*/SKILL.md` as a skill.
- *To confirm in Phase 2:* whether Grokbot re-reads the repo on each task or keeps a copy. If it keeps a copy, the weekly review re-syncs it.

## Claude (this Project, desktop and mobile)

- Put `AGENTS.md` in the Project's docs so every chat in the Project reads it.
- Scheduled jobs (daily sweep, weekly skill miner) run as Claude scheduled tasks, and each one reads this repo first.

## Drift check (Phase 2)

Each tool, asked "what are your never-dos and which version are you on?", must answer with the version date at the top of `AGENTS.md`. The weekly review asks every tool.
