# How to ask Systems & Logistics for anything — Linear, from 2026-08-29

One front door now: the **Systems & Logistics** team in Linear (key **SYS**),
run by Arthur and Alessa. The old teams (Mothership, Lytheron, AL,
Amazon/Shopify, Wholesale) are gone — old links redirect, nothing is lost.

## Filing an ask (2 minutes)

1. Create an issue on the **Systems & Logistics** team. The **Ask S&L**
   template fills itself in — use it, don't delete the sections.
2. Fill every section. The two that matter most:
   - **Discussed with** — have you already spoken to Arthur or Alessa about
     this? Say who. It stops double-briefing.
   - **Best person** — Arthur, Alessa, or "don't know". All fine; it speeds
     up routing.
3. **Add your BU as a label** (TopCo, Toysellers, Booksellers, Valen Trading,
   Valen Cosmetics, Lush Lobster, Athena). No BU label = the lint asks for it
   and the ask waits.
4. Set a priority honestly — it's a suggestion, not a demand. S&L may bump
   it up or down; they see everything in flight and you don't. What the
   priorities mean:
   - **Urgent** = within 1 day
   - **High** = within 3 days
   - **Medium** = within 5 days
   - **Low** = within 2 weeks — really an "I think we should think about this"
   - **Drop everything** (label) = literally stop everything. Rare. Real.
   Bigger than a week of work? Add the **larger** label — S&L will break it
   into a sub-project instead of one giant ask.
5. Done. It lands in **Triage** — Arthur or Alessa accepts it, usually same
   day. You'll see it move to Todo when accepted.

## Which project? (this matters)

- **General** — one-off business tasks for systems to *do*: "make a deal
  sheet for X", "pull this month's numbers for Valen", "check these 200
  listings". **The default. When in doubt, it's General.**
- **Mothership (Apothekon)** — changes to the platform *itself*: features,
  bugs, infra. "Build a deal-sheet builder into the platform" is Mothership;
  "make a deal sheet for X" is **not** — it's General.
- **Data** — the repeatable data machinery: pipelines, ETL, automated
  reporting. "Automate the weekly stocklist ingestion" is Data; "get me these
  numbers once" is General.
- **Lytheron** — changes to the Fox & Fable ops platform itself.

You never need to decide the scaling part: your General task gets done, and
if it reveals something worth making repeatable, **S&L spins off Mothership /
Data / Lytheron tasks off the back of it**. You ask once; the system gets
permanently better.

## What happens after

- Work is picked up in priority order. **Drop everything** label exists for
  real emergencies — use it sparingly, it beats everything.
- One ask per issue. Two asks = two issues.
- When it's ready for you, it goes to **In Review** and you get a **Result**
  comment: what was done, where it is, what to check. *You* accept it to Done.
  Check the shared view **"Your asks — awaiting your accept"** — after 2 days
  in review you'll get a nudge.
- Blocked or changed scope? Comment on the issue, don't open a new one.
- Don't chase with comments. Bump the priority once instead.

## If you run agents (Claude, Codex, Kimi, Cursor…)

Your agent files asks the same way, through the contract in
`linear-agent-contract.md` (in this pack — Arthur shared it with you). Point
your agent at that file once and it knows: search before creating, nine
template sections, BU label, footer line, SYS-### in every PR title or
commit so work traces to releases. Give the agent Linear access (your
workspace login, or the official Linear MCP from linear.app).
Arthur's own team (ART) is private — agents can't and shouldn't file there.

## Better: a permanent agent with a loop

Linear is the switchboard between humans and agents as independent teammates.
If you're manually touching Linear every day, you're doing your agent's job.
The setup:

1. **One-time**: point your agent (any model — Claude, Codex, Kimi, Cursor)
   at `linear-agent-contract.md` in this pack and connect it to Linear. Stuck? Ask Arthur or
   Alessa — 10 minutes.
2. **Standing loop**, in plain words: *"Every morning, check our BU's SYS
   asks — what's in Triage, what's waiting on my accept (view: 'Your asks —
   awaiting your accept'), what's stale — and give me a 5-line summary.
   During the day, anything I mention that needs S&L, file it as an Ask S&L
   with our BU label."*
3. From then on you talk, it operates: files, tracks, chases, reports.
   You never open Linear unless you want to.

## FAQ

- *Bug or feature?* Same front door, same template.
- *Which project?* Covered above — but the short version: one-off = General,
  platform change = Mothership/Lytheron, repeatable data machinery = Data.
  SellerSnap and wholesale platform work go in Mothership (SellerSnap /
  wholesale labels). Still not sure? Pick General; Triage routes it.
- *Athena portal work?* Still Danny's ATH team, unchanged.
- *Where did MOT-123 go?* Same issue, new key (SYS-###). The old link opens it.
