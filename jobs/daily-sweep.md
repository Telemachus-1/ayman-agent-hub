# Job: daily sweep

**When:** weekdays, time to be confirmed (proposed 07:30 London).
**Runs in:** a fresh cloud session, so this text must stand alone.

## Prompt

Read and follow `AGENTS.md` and `rules/connectors.md` in `aym183/ayman-agent-hub`. Then:

1. Run the `inbox-triage` skill on ayman@telemachus.io.
2. Gather any knowledge base proposals created since the last sweep.
3. Write the daily update (format below) as the final message of this scheduled-task session. Ayman gets a push notification, reads it, and replies in the same chat. When he replies "approve 1, 3; reject 2", set those Notion entries to Approved or Rejected.

You may only label and archive mail. Never send, reply, draft, trash, unsubscribe or mark as spam. Post nothing in Slack.

## Daily update format

```
Daily update, <date>

Action items (n)
- <who>: <what> (<due>) <link>

Inbox: n must respond · n archived · n not sure

KB proposals (n): reply "approve 1, 3; reject 2"
1. <title>: <one line> (source)
```
