# Presenting StackAtlas to investors & founders

## Positioning (one sentence)

> "Every AI agent that touches a database needs to know what the tables mean. StackAtlas is that context layer — auto-generated, always current, served over MCP."

Do NOT pitch it as "a cheaper Alation." Data catalogs for humans are a known, crowded category. Context infrastructure for agents is an open one, and the same artifact serves both.

## The 5-minute demo script

**1. The setup (30s).** "This is `vibeshop` — a typical AI-generated SaaS backend. Looks fine from the app. Here's what's actually inside." *(Open the dashboard. Let the flickering numbers and the 61/100 health score land.)*

**2. The reveal (90s).** Click `order_items`: "This table gets 8,800 reads a day and has zero rows. Why? Its foreign key still points at a table deprecated last August — so the app silently stuffs line items into a JSON blob. No human wrote this down anywhere. StackAtlas found it from introspection + LLM analysis in 60 seconds."

**3. The agent moment (2 min — this is the demo).** Switch to Claude with the MCP server connected. Ask live: *"Write me a monthly revenue query for this database."* Narrate what happens: Claude calls `get_table_context`, learns that revenue = `orders_v2.amount_cents` where `status='c'`, that amounts are cents not dollars, that refunds live in two places — and writes a correct query. Then say the line: **"Without StackAtlas, every agent re-guesses this. With it, the schema explains itself — to every agent, every time."**

**4. The wedge (60s).** "Datalogz sells BI observability to enterprises; I helped build it. Below the enterprise there are millions of AI-generated apps with rotting schemas and zero data governance — and every one of them is about to put agents on top. Catalog-as-context is the cheapest insertion point: read-only, one connection string, value in the first minute."

**5. Moat, preempted (30s).** "The LLM call is commodity. The moat is the accumulated layer: per-schema correction history, drift timelines across migrations, and an eval set of real messy schemas that makes extraction better than anyone starting fresh."

## The ask — one action, stated twice

**"Give me one design-partner intro: a portfolio company with a Supabase or Postgres backend and an AI feature. I'll run StackAtlas against it read-only and hand their team a health report + working MCP context server within a week. If their engineers keep it running after 30 days, let's talk about leading a pre-seed."**

Why this ask works: it's small (an intro, not money), it's falsifiable (retention after 30 days), it converts their portfolio into your pipeline, and it sets up the second meeting with data instead of promises.

Close every conversation by scheduling the follow-up before you leave: "I'll send the health report Friday — can we do 20 minutes Monday to review it?"

## Objection handling

- **"Isn't this just Alation/Atlan?"** — Those are $50k+ human-workflow tools for data teams. This is agent infrastructure for companies with no data team. Different buyer, different price point, different interface (MCP, not a web app humans forget to update).
- **"Won't the model providers build this?"** — Providers ship the protocol (MCP), not the domain layer. Someone has to own schema semantics, drift history, and QA. Protocol standardization is a tailwind: it makes this pluggable everywhere.
- **"What stops a weekend clone?"** — The demo, nothing. The product: parser/eval accumulation across real messy schemas, drift history (which requires having been installed), and workflow lock-in once agents depend on the context server.
- **"Why you?"** — Data engineering + GTM engineering at Datalogz: built the enterprise version of this observability muscle AND knows how to sell it. Solo-credible in both halves.

## Presentation logistics

- Record a 2-minute Loom of the demo as a fallback — live demos with MCP have moving parts; never let a config issue eat your meeting.
- Lead with the dashboard on screen before you say a word. The aesthetic is the hook; the `order_items` story is the proof; the agent query is the close.
- Leave-behind: this repo link + the Loom + one paragraph restating the design-partner ask.
