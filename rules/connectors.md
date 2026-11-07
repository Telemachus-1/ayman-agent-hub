# Connector rules

*Version 2026-11-07. Each tool (Superset, Grokbot, Claude) has its own connectors. Where a tool lets us switch a capability off in its settings, it is switched off there too; these rules are the floor, not the only guard.*

| Connector | Allowed | Never (unless Ayman asks for that exact action) |
|---|---|---|
| Gmail (ayman@telemachus.io only) | Read, search, label, archive, create labels | Send, reply, forward, draft (not yet), trash, delete, unsubscribe, mark as spam |
| Google Calendar | Read | Accept, decline, create, move or delete events |
| Slack | Read and search | Post anywhere, DM anyone, react |
| Linear | Read; create and update cards and comments for work longer than a session | Anything on LUS; deleting cards or comments |
| Notion | Read; create **Proposed** KB entries; edit pages Ayman asks for | Edit **Approved** KB entries; delete pages |
| Google Drive, Docs, Sheets | Read; create or edit files Ayman asks for | Share files, change permissions, trash files |
| Granola | Read notes and transcripts | Editing notes; quoting transcripts as exact words |
| GitHub | Read; push to `aym183/ayman-agent-hub` and to branches for a task Ayman set | Merge Mothership outside the merge queue; push to `main` of a company repo |
| Supabase | Read only | Any write |
| Helm, Lytheron | Read; **preview** writes | Confirming a write without Ayman's yes |
