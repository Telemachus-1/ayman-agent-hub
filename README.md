# Ayman's agent hub

Shared rules, skills and company knowledge for every agent Ayman runs: Claude Code in Paradev (formerly Superset), Grokbot, and Claude (desktop, mobile and scheduled jobs). Inspired by Arthur's Agent Hub & AI Team Playbook v6.1.

## Load order

1. `AGENTS.md`: always on. The never-dos and how to work. Short on purpose.
2. `rules/`: read when relevant: company rules, connector rules, the decisions log.
3. `skills/`: procedures, loaded when a task needs them.
4. Knowledge base: Notion (Approved entries). `kb/` holds the seed now, and later a nightly export.

## Folders

| Folder | What it holds |
|---|---|
| `rules/` | `company-rules.md`, `connectors.md`, `decisions.md` |
| `skills/` | Live skills: `inbox-triage`, `kb-propose` |
| `proposals/` | Draft skills from agents, reviewed weekly. Not live. |
| `jobs/` | Prompts for scheduled jobs: daily sweep, weekly skill miner |
| `kb/` | Knowledge base seed and export |
| `reference/` | Source documents the skills were built from (for example Arthur's Linear files). Agents follow the skills, not these. |
| `install/` | How each tool loads the hub |

## Changing a rule

Edit the file, add a dated line to `rules/decisions.md`, and bump the version date in `AGENTS.md`. Newest dated rule wins.
