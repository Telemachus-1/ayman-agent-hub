# Linear work gate — the agent contract

Every task starts and ends in Linear. This file is the contract for agents
(Claude, Codex, Kimi, Grok, Cursor) acting for any person in the workspace.
The "Ask S&L" template applies automatically in the UI; through the API/MCP
you must reproduce it yourself — the skeleton is in
`linear-ask-skeleton.md` (same folder as this file). A nightly lint enforces this
contract and bounces what does not comply.

## 1. Before doing anything

1. Search Linear for the ask (`list_issues` with the key terms, all teams).
   Reuse a matching open issue; create one only when none exists.
2. Route by what the work is, not who asked:
   - **Systems & Logistics (SYS)** — anything a person needs Arthur, Alessa
     (or their agents) to do: systems, data, integrations, logistics, ops,
     Mothership platform, Lytheron, SellerSnap, wholesale fulfilment, AL.
     Use the Ask S&L shape. Lands in Triage; Arthur/Alessa accept.
   - **Wholesale Ordering - Athena (ATH)** — the Athena portal (Danny's team).
   - **Arthur (ART)** — Arthur's PRIVATE team. Do not file here; only Arthur
     and agents acting as Arthur can see it.
   - **Telemachus-1 (TEL)** — archived legacy. Never create here.
3. Set it to **In Progress** before implementation, external writes or deploys.
   Discovery needed to find or create the issue is the only pre-gate action.

## 2. Creating an ask on Systems & Logistics (agent filing for a person)

Required, or the lint moves it to Backlog with one comment:

- **Title**: an action — verb first, one finishable deliverable. One ask per issue.
- **Description**: the nine sections of the skeleton, in order —
  `### Action`, `### What for`, `### Urgency`, `### Why urgent`, `### Done when`
  (at least one checklist item), `### Discussed with` (who in S&L the
  requester has already spoken to, or "no one yet"), `### Best person`
  (Arthur, Alessa, or "don't know" — who should pick it up), `### Notes`,
  `### Files`.
- **Footer line** (last line of the description, keep the HTML comment):
  `<!-- requester: <person> | agent: <tool> | session: <name> -->`
- **Project**: one of the four SYS projects — Mothership (Apothekon), Data,
  General, Lytheron. Leave blank when unsure; Triage routes it. Finer
  grouping uses labels (SellerSnap, wholesale, AL), not extra projects.
- **Label**: the BU the ask is for — TopCo, Toysellers, Booksellers,
  Valen Trading, Valen Cosmetics, Lush Lobster, Athena, or
  Systems & Logistics. The triage helper bounces asks with no BU label.
- **Priority**: set (Medium if unstated; Urgent/High only when *Why urgent*
  says why). Priority meanings: Urgent = 1 day · High = 3 days ·
  Medium = 5 days · Low = 2 weeks (an "I think we should think about this")
  · Drop everything label = literally stop everything. Work bigger than a
  week gets the **larger** label and S&L breaks it into a sub-project rather
  than one big ask. The requester's priority is a suggestion — S&L may bump
  it up or down with full oversight of everything in flight.
  **Assignee**: Arthur, or Alessa when the ask is clearly hers.
- **Status**: `Triage` when filed by someone outside S&L (Arthur/Alessa
  accept); `Todo` when all of the above is present and it is ready for
  pickup; `Backlog` when the requester still owes something (say what, in
  *Notes*).
- Attach files and links in the same step. Never invent numbers, dates or
  deadlines the person did not give.

## 3. Creating a platform/engineering issue on SYS (agent doing platform work)

- **Assignee** = the accountable human (Arthur unless told otherwise).
  **Priority** set. **Project** set. One area label.
- Title states the outcome; description states the evidence that will prove
  it (tests, migration numbers, prod checks). Add label `spec-ready` only when
  another agent could build it from the text alone.
- The lint assigns and prioritises anything you forget, silently.
- Put the issue key (`SYS-123`) in the PR title or in the commit body. Every
  push to main is recorded as a Linear release, and an issue is attached to
  that release only if its key appears in the commits. No key, no trace.

## 4. Picking up work (agent acting for the assignee)

- The queue is the view **"SYS — ready for pickup"** (SYS, Todo, priority
  set). Highest priority first; `Drop everything` label beats everything.
- **Claim**: move to **In Progress** and comment
  `Claimed — <agent>/<session>. Plan: <one line>.` Do not claim two at once.
- **While working**: comment on material decisions, blockers, handoffs and
  production evidence. No "still working" comments.
- **Hand back**: post a **Result** comment, then move to **In Review**.
  The Result comment starts with the word `Result` and answers three things:
  *what was done*, *where it is* (link or attachment), *what to check*.
  In Review without a Result comment is bounced back to In Progress.
- **Done**: only when the requester accepts, or you are certain and say so in
  the Result. **Canceled / Duplicate**: always with a comment saying why.
- **Blocked**: comment `Blocked: <exact blocker>`, add `blocked-external` if
  it is outside our control, leave the status as it is.
- Never repeat a comment. Bump priority once instead of chasing.
- Cross-team references (e.g. ATH work that depends on SYS work): use issue
  relations (`relatedTo` / `blocks` / `blockedBy`) — they work across teams.
  Sub-issues cannot cross teams; use relations instead.

## 5. What enforces this (so you know what will happen)

- Triage on SYS is on and auto-assigns Arthur (same as ART did). A priority
  is required before an issue can leave Triage. Auto-close and auto-archive
  after 6 months, mirroring ART.
- Lint at 07:00 London (`linear-lint` on arthur-vm): bounces In Review
  without a Result comment back to In Progress, asks Triage issues for their
  missing sections, nudges stale In Review after 5 days, and silently
  assigns/prioritises anything forgotten.
- Loops: *Triage helper* asks the creator for missing sections (including
  *Discussed with* and *Best person*); *In Review reminder* nudges after
  2 days.
- Danny's chaser is retired; do not build another.

## 6. IDs (workspace telemachus-1)

- Teams: Systems & Logistics `f77bed45-e9ee-4bf1-af43-a499324f3963` ·
  Arthur (private) `3f56cb2b-7895-47fe-a8e3-5a8dd803d5bc` ·
  Athena `0aa05224-2c83-4915-a097-083a824c29bf` ·
  Telemachus-1 (legacy) `6c3c8373-e4b3-4929-a99e-b731de2fa609`
- SYS states: Triage `f190c7a3-5834-4ecc-b829-0911e57d29e8` ·
  Backlog `6fc168c1-9c18-4eae-b9ff-fb993b252776` ·
  Todo `1e612381-c6c9-44cd-8750-a46ceaad5f91` ·
  In Progress `e8166624-181b-45de-88b7-a63c58794891` ·
  In Review `c69c33c3-61ab-4b1e-b539-38167e019452` ·
  Done `8e5523c8-cd78-4ac1-998f-9caa3acfcd60` ·
  Canceled `f4aacec6-ceb5-4b41-b211-53363b1c7651` ·
  Duplicate `f5251c80-14a1-4130-a432-e2ae9492e3c4`
- Arthur states: Triage `9c2cc5dd-3984-4029-b221-ffb86a5077d8` · Backlog `9d58c29b-5c15-4405-a0b7-88bb961bbac2` · Todo `86bcbee1-ad0f-4c84-99ac-a7096296e4eb` · In Progress `1c8c823c-a9ee-4b13-92eb-cdbc2f1b806d` · In Review `b3ee5621-cdb0-4481-8972-37bdcfe85c3c` · Done `3ae62ecb-ed6d-428b-a1d7-bc08e77a6bfa`
- Users: Arthur `9f0f3f91-0776-4185-94b9-eed3aec6dee7` · Danny `d4d05804-be3e-4a66-9080-c7ccd5bed584` · Jack `54432521-9c6d-4cd3-bee0-8e3f4c6942ae` · Robin `b076add4-ff2f-41b0-a045-dc910d4af65b` · Giorgia `a6f17c99-e7fb-4a08-866b-8bc485747c42` · Alessa `bc3ac7ca-ab24-470e-8d26-c0ec57c71738` · Alex `e4a4aabc-27b0-4f3d-ad44-74f78ffc1212` · Ajwad `b20a4e0f-9f7f-423c-912d-ae253dd5edca`
- Labels: Drop everything `016664a5-adb8-4e07-910a-36e6599c0f44` · blocked-external `e505e622-d7c9-48a6-8c3a-29efc942b202`
- SYS BU labels: TopCo `36bc3c18-29ee-4854-807e-abd879f3231f` · Toysellers `bb0da81e-013c-4943-90f5-ba3437ec0180` · Booksellers `679c878e-3861-42eb-975b-9baa507b0932` · Valen Trading `57b3e14f-8106-44c2-83dc-669b7e51f3d2` · Valen Cosmetics `9f5b9aca-b48c-433d-be91-2e877d1e6500` · Lush Lobster `b4c6aeac-5dbe-497e-ac94-83e8b69204eb` · Athena `4215df4f-b6c4-449f-b173-a4ce44f546e4` · Systems & Logistics `09cde9b6-1c12-4c96-a13c-b78a23e5173a`
- SYS projects (the only four): Mothership (Apothekon) `a1597d12-e90f-4e9e-b808-27b47a760477` · Lytheron `6ee6af66-9848-491c-b76c-a66123807135` · Data `d50adc11-5549-476f-b9a4-71aa2e602413` · General `e8534e4a-eda3-4c03-8879-d9af92c49f7b`
- SYS grouping labels (finer than projects): SellerSnap `1bde24ad-1120-4971-8532-1af975c6909c` · wholesale `4d5f78b5-586b-4e94-9fa6-771f254dcd00` (workspace) · AL `d66e64dd-7ae6-4ad8-a535-449c58bbcd65` · larger `10081320-0964-40a0-a075-b2cd16a58fba` (work > 1 week — becomes a sub-project)
- ART projects (BU, unchanged): TopCo `25ebe8f8-469f-412c-827b-b4cd1db3db70` · Logistics `18f87e7d-d4d7-43e8-87a3-b32b1eda3fe7` · Systems `fc40ca9f-5f40-4951-bd2f-a7534c040e7a` · Toysellers `cab1e62b-3278-4760-8be2-889567482793` · Booksellers `49d2cd2d-d6a3-4d74-9b3c-3845a5e84a38` · Valen Trading `9386c849-6731-4fc1-a3a1-5cffea255d26` · Valen Cosmetics `aaa2254f-d3af-4e5c-ade0-1ed0830d0754` · Lush Lobster `e56866dc-b21c-469d-8587-2e96882d0694`
- Initiatives (BU lanes, attach projects on any team): TopCo `efd7601c-adb5-4330-85a1-f6364d6fc830` · Toysellers `651ac60c-727f-4ccd-97fc-bcd7a51a8e25` · Booksellers `718125a9-2b6a-45be-a7fe-b87c80d05180` · Valen Trading `714cfbca-6160-462f-a8fb-ac074cd47a10` · Valen Cosmetics `8d1c9e91-4f8d-4315-8f61-710d8730902f` · Lush Lobster `402fc4b4-6dee-4d5a-ac1a-17cd6cad85c3` · Logistics `9c9b1b04-6ed6-42c6-91bb-2b454ede759d` · Systems `0c1f1708-efae-48ce-806b-c7556a459fc5` · Athena Wholesale `e6a9456d-6543-4270-a0cf-54e4a33dd18c` · Mothership platform `86609642-c9b7-435e-bcb4-c45cebcf440c`

## 7. Retired 2026-08-29 (the SYS restructure)

- Teams deleted: Mothership (MOT), Lytheron (LYT), AL, Amazon/Shopify,
  Wholesale, Lush Lobster. Their open issues moved to SYS projects; old issue
  keys (MOT-123 etc.) redirect to the new SYS keys.
- AL team's completed history (243 issues, AL-00…AL-04 and AL-Ops projects)
  was deleted with the team — deliberate, Arthur's call.
- Arthur team is now private: Arthur's personal queue, not an intake.
