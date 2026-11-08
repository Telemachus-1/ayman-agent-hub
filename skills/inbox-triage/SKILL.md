---
name: inbox-triage
description: Sweep Ayman's Gmail inbox (ayman@telemachus.io) — label must-respond and irrelevant mail, archive newsletters, promotions and accepted invites, and collect action items for the daily update. Use for the daily sweep or when Ayman asks to clean up his inbox.
---

# Inbox triage

Mailbox: **ayman@telemachus.io only.**

## Hard limits

Never send, reply, forward, draft, trash, delete, unsubscribe or mark as spam. The only writes allowed are **adding or removing labels** and **archiving** (removing the INBOX label).

## Labels

Create these once if they are missing (check with `list_labels` first):

- `Triage/Must respond`: needs Ayman to reply or act. High priority. Stays in the inbox.
- `Triage/Irrelevant`: no action and no value. Archived.

## Steps

1. Search the inbox for threads that do not yet have a `Triage/` label.
2. Read each thread (sender, subject, the latest message) before deciding. If unsure, leave it in the inbox and list it under "Not sure" in the update.
3. Apply the rules:

| Kind of mail | Action |
|---|---|
| A person (colleague, supplier, customer) who asks Ayman something, needs a decision, or is waiting on him | `Triage/Must respond`. Keep in inbox. Add the action item to the update. |
| Newsletters, digests, product updates | Archive. |
| Promotions and marketing | Archive. |
| Calendar invite **accepted** by someone | Archive. |
| Calendar invite **declined** by someone | Keep in inbox. |
| Calendar invite proposing a new time, or a tentative reply | Keep in inbox (treated like a decline). |
| Automated notices with no action (receipts, shipping updates, sign-in alerts) | `Triage/Irrelevant`, archive. Receipts also keep the existing `Receipts` label. |
| Anything that mentions Lush Lobster | Leave untouched. |
| *Added 7 Nov after the dry run, approved by Ayman:* | |
| Invitation for a meeting that has already happened | Archive. |
| Meeting-recap mail with action items (for example Calendly notes) | Copy the action items into the update, then archive. |
| Thread where Ayman sent the last message | Keep in inbox, no label. List under "Waiting on others". |
| Account set-up or invite that needs Ayman to act (sign-up, join an organisation, confirm email) | `Triage/Must respond`. |

**Do not trust Gmail's category alone.** Gmail filed a real Dun & Bradstreet D-U-N-S notice under Promotions. Read the message before archiving it.

**Never copy a password, login code or verification code** into the update or anywhere else. Say only "contains a login credential, see the thread".

4. **Rate limits:** if Gmail returns a "too many requests" (429) error, stop. Never retry it. Report the sweep as cut short and carry on next time.
5. **Action items:** for every must-respond thread, write one line: who, what they need, by when if stated, and the Gmail link.
6. **Read back:** re-list the inbox and confirm the counts match what you did.

## Output for the daily update

```
Inbox sweep, <date>
Must respond (n):
- <Sender>: <what they need> (<due>) <link>
Archived: n newsletters, n promotions, n accepted invites, n irrelevant
Not sure, left in inbox (n):
- <Sender>: <subject> <link>
```

No personal content in the update beyond what the thread needs to be identified.
