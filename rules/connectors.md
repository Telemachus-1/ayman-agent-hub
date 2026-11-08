# Connector rules

*Version 2026-11-08. Each tool (Paradev, Grokbot, Claude) has its own connectors. Where a tool lets us switch a capability off in its settings, it is switched off there too; these rules are the floor, not the only guard.*

| Connector | Allowed | Never (unless Ayman asks for that exact action) |
|---|---|---|
| Gmail (ayman@telemachus.io, and the six logistics@ group mailboxes that arrive in it) | Read, search, label, archive, create labels | Send, reply, forward, draft (not yet), trash, delete, unsubscribe, mark as spam; retrying a 429 |
| Google Calendar | Read | Accept, decline, create, move or delete events |
| Slack | Read and search | Posting, unless Ayman says so for that message (then bot channels only, signed `_sent by bot_`); posting or reacting in team and logistics channels; DMs to anyone but Ayman |
| Linear | Read; create and update cards and comments for work longer than a session | Anything on LUS; deleting cards or comments |
| Notion | Read; create **Proposed** KB entries; edit pages Ayman asks for | Edit **Approved** KB entries; delete pages |
| Google Drive, Docs, Sheets, Slides | Read; create or edit files Ayman asks for | Share files, change permissions, trash files |
| Granola | Read notes and transcripts | Editing notes; quoting transcripts as exact words |
| GitHub | Read; call a PR reviewed only once the review is posted; push to `Telemachus-1/ayman-agent-hub` and to branches for a task Ayman set | Merge Mothership outside the merge queue; push to `main` of any other company repo |
| Supabase | Read only | Any write |
| Helm, Lytheron | Read; **preview** writes | Confirming a write without Ayman's yes |
