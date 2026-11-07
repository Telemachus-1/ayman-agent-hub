# Knowledge base

The live knowledge base is the Notion database **Telemachus Knowledge Base**:
https://app.notion.com/p/37abc18af4b243398aaa0bc4b8780aeb

- Fields: Entry, Status (Approved / Proposed / Rejected), Category, Source, Why, Internal only, Added by.
- Agents read **Approved** entries only, and add new ones as **Proposed** with the `kb-propose` skill.
- **Internal only** entries (entities, tax numbers, strategy) never go into anything sent outside Telemachus.

This folder will hold a nightly export of the Approved entries, so tools without Notion access can still read them.
