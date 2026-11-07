# Installing the hub into each tool

This repo is a **Claude plugin marketplace**. It holds one plugin, `ayman-hub`. Installing the plugin gives Claude:
- **all the skills** in `skills/`, named `ayman-hub:<skill>` (for example `/ayman-hub:linear-ask`);
- **a start-up hook** that loads `AGENTS.md` into every Claude Code session.

One copy lives in this repo. Tools pull it from here instead of keeping their own.

## 1. Claude (web and desktop), with sync to Claude Code

Install it once in your Claude account:

1. Open **Customize** in the left sidebar, then the **Plugins** tab.
2. Click **Add**, then **Add marketplace**. Choose **Add from a repository** and enter `Telemachus-1/ayman-agent-hub`.
3. Install **ayman-hub** from it.

Installed plugins also **sync to Claude Code** wherever it is signed in with the same Claude account (Claude Code v2.1.273 or later). They don't sync when Claude Code uses an API key.

**Not yet confirmed:** whether a personal marketplace can read a private repo, and how often it picks up new commits. If the add fails, use section 2, or ask a Claude org owner to add the repo under **Organization settings > Plugins & skills > Marketplaces** with GitHub sync. That needs the Claude GitHub App on the repo.

## 2. Claude Code directly (terminal, or a Paradev workspace)

```
/plugin install ayman-hub --marketplace Telemachus-1/ayman-agent-hub
```

On Claude Code older than 2.1.275, run it in two steps:

```
/plugin marketplace add Telemachus-1/ayman-agent-hub
/plugin install ayman-hub@ayman-agent-hub
```

- **Private repo:** Claude Code clones with the machine's own git credentials. On a new machine, run `gh auth login`, then `gh auth setup-git`, first.
- **Updates:** open `/plugin`, go to **Marketplaces**, select `ayman-agent-hub` and choose **Enable auto-update**. Otherwise run `/plugin marketplace update ayman-agent-hub`. The plugin has no `version` field, so every new commit counts as an update.
- **Check it worked:** `claude plugin details ayman-hub` should list 9 skills and 1 hook.

**Paradev:** if its Claude Code signs in with your Claude account, section 1 covers it. If it doesn't, run the commands above once in a workspace. For a repo whose workspaces should always have the hub, commit this to that repo's `.claude/settings.json` (company repos change through a PR):

```json
{
  "extraKnownMarketplaces": {
    "ayman-agent-hub": { "source": { "source": "github", "repo": "Telemachus-1/ayman-agent-hub" } }
  },
  "enabledPlugins": { "ayman-hub@ayman-agent-hub": true }
}
```

## 3. Always-on rules in Claude chats

Plugin hooks run only in Claude Code, so Claude chats don't get the start-up hook. There:
- **This Project** already has `AGENTS.md` in its docs, so every chat in the Project follows it.
- **Outside the Project**, put a short pointer in your personal preferences in Claude's settings, for example: "Follow the rules in the ayman-hub plugin and Telemachus-1/ayman-agent-hub AGENTS.md: never send email or Slack as me, never move money, never delete, ask before starting a task."
- **Scheduled tasks** carry their rules in their own prompts.

## 4. Grokbot

- Give it read access to this repo.
- Store `AGENTS.md` as its standing instructions, and each `skills/*/SKILL.md` as a skill.
- *To confirm:* whether Grokbot re-reads the repo on each task or keeps a copy. If it keeps a copy, re-sync it at the weekly review.

## Keep these working

- `AGENTS.md` must stay **under 10,000 characters**. Above that, the start-up hook stops including it in full.
- Keep the plugin name `ayman-hub`. Renaming it breaks existing installs. To change the label people see, set `displayName` in `.claude-plugin/plugin.json`.
- After editing the plugin files, run `claude plugin validate .` (the LICENSE and icon notices only matter for Anthropic's public directory).

## Drift check

Ask each tool: "What are your never-dos, and which version are you on?" It must answer with the version date at the top of `AGENTS.md`. The weekly review asks every tool.
