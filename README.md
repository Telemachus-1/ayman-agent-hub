# Ayman's agent hub

Shared rules, skills and company knowledge for every agent Ayman runs: Claude Code in Paradev (formerly Superset), Grokbot, and Claude (desktop, mobile and scheduled jobs). Inspired by Arthur's Agent Hub & AI Team Playbook v6.1.

## Install

In Claude Code: `/plugin install ayman-hub --marketplace Telemachus-1/ayman-agent-hub`. For Claude chats, Paradev and Grokbot, see `install/README.md`.

## Load order

1. `AGENTS.md`: always on. The never-dos and how to work. Short on purpose.
2. `rules/`: read when relevant: company rules, connector rules, the decisions log.
3. `skills/`: procedures, loaded when a task needs them.
4. Knowledge base: Notion (Approved entries). `kb/` holds the seed now, and later a nightly export.

## Folders

| Folder | What it holds |
|---|---|
| `rules/` | `company-rules.md`, `connectors.md`, `decisions.md` |
| `skills/` | Live skills (9), loaded by the `ayman-hub` plugin |
| `.claude-plugin/`, `hooks/` | Plugin and marketplace files, and the start-up hook that loads `AGENTS.md` |
| `proposals/` | Draft skills from agents, reviewed weekly. Not live. |
| `jobs/` | Prompts for scheduled jobs: daily sweep, weekly skill miner |
| `kb/` | Knowledge base seed and export |
| `reference/` | Source documents the skills were built from (for example Arthur's Linear files). Agents follow the skills, not these. |
| `install/` | How each tool loads the hub |
| `hub/` | The hub MCP: one endpoint for every service, with keys, policy, audit log and kill switch (see `hub/README.md`) |

## Changing a rule

Edit the file, add a dated line to `rules/decisions.md`, and bump the version date in `AGENTS.md`. Newest dated rule wins. Keep `AGENTS.md` under 10,000 characters.
