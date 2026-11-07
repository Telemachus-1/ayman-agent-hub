---
name: helm-work
description: Look things up and make changes in Helm (the BU lead's interface to Apothekon) — customers, orders, buying, invoices, catalogue, stock and finance. Use for any data look-up or change in the company's systems.
---

# Working in Helm

*Sources: the Helm connector's own instructions, Arthur's BU lead playbook v6.1 §3 and §6.5–6.7.*

## Look-ups

- Read the **current** record before reporting it. Never answer from memory or an old result.
- Identify products by **EAN within a BU**, never by title alone.
- Helm can read delivery and warehouse state, so you can say exactly where an order is.
- For anything not in the everyday tools, call that area's menu (`helm_orders`, `helm_invoices`, `helm_customers`, `helm_catalogue`, `helm_buying`, `helm_bills`, `helm_finance`, `helm_admin`) with `action='help'`.

## Changes

1. Every write **previews first** and returns a `summary` and a `confirm_token`.
2. Show Ayman the **full** summary. Wait for his explicit yes.
3. Call the same tool with identical arguments plus `confirm=true` and that token.
4. Never invent or reuse a token. Tokens expire after 30 minutes; preview again if one lapses.
5. Read the record back after the change, and report what changed.

Money is always a decimal string, never a float.

## Never

- Move money, pay a bill, or send a purchase order.
- Do warehouse work (dispatch, pack, mark delivered, pick freight, push to the 3PL, adjust stock) unless a person has granted the warehouse grant. Without it, say it is warehouse work and hand it over.
- Fix records "around" the product. Data corrections are asked for on Linear (see `linear-ask`) and run as reviewed data packs.

## When Helm can't do the job

That is a product gap, not a reason for a workaround. Either:
- call `report_problem` once, if a tool failed unexpectedly; or
- file an ask (see `linear-ask`) describing the need, what was missing, a "done when", and the manual workaround used meanwhile. On SYS, label it `capability-gap`.
