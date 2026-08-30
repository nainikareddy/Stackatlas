<div align="center">

# StackAtlas

### The context layer for AI agents

Point it at a database. Get a living catalog — schema graph, AI-written docs, health signals — and an MCP server, so agents stop guessing what `orders_v2.status = 'c'` means and start querying what it *actually* means.

[![CI](https://github.com/nainikareddy/stackatlas/actions/workflows/ci.yml/badge.svg)](https://github.com/nainikareddy/stackatlas/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-black.svg)](LICENSE)
![Next.js](https://img.shields.io/badge/Next.js-14-black)
![Python](https://img.shields.io/badge/Python-3.11-black)
![MCP](https://img.shields.io/badge/MCP-server-black)

</div>

---

## The problem

Millions of vibe-coded apps shipped since 2024, and their schemas rot: dropped foreign keys, magic status codes, orphaned tables, three timestamp conventions in one database. Humans work around it quietly. **AI agents fail loudly** — an agent writing SQL against an undocumented schema hallucinates joins, sums the wrong column, and joins to a table that's been dead since last August.

Enterprise data catalogs (Alation, Atlan) solve this for humans with data teams and $50k budgets. StackAtlas solves it for the long tail — companies with no data team that are about to put agents on top of a Supabase they haven't looked at in months. One connection string, read-only, value in the first minute.

## What it does

```
   Postgres                introspect + LLM              served two ways
  ┌─────────┐   ┌──────────────────────────────┐   ┌────────────────────┐
  │ messy   │──▶│ schema skeleton  →  Claude    │──▶│ ▸ dashboard (UI)   │
  │ schema  │   │ + traffic + FKs    docs+health│   │ ▸ MCP server (agents)│
  └─────────┘   └──────────────────────────────┘   └────────────────────┘
                         one catalog, one schema contract
```

StackAtlas introspects a live Postgres database, has Claude document every table and column, detects the structural landmines (broken FKs, orphans, naming drift, money-as-float), and serves the result **two ways from one artifact**: a dashboard for humans and an MCP server for agents.

The flagship trick is detectable from structure alone: an *enforced* foreign key on `order_items` still points at `orders` — a table superseded by `orders_v2` months ago. The app silently worked around it; nobody wrote it down; every agent rediscovers the bug the hard way. StackAtlas surfaces it in the first pass.

## The agent demo

Wire the MCP server into Claude Desktop / Claude Code:

```json
{
  "mcpServers": {
    "stackatlas": {
      "command": "python",
      "args": ["/ABSOLUTE/PATH/stackatlas/mcp_server/server.py"]
    }
  }
}
```

Then ask Claude *"Write me a monthly revenue query for this database."* Instead of guessing, it calls `get_table_context`, learns that revenue is `orders_v2.amount_cents` where `status = 'c'`, that amounts are cents not dollars, that refunds live in two places — and writes a correct query.

**Tools exposed:** `search_tables` · `get_table_context` · `explain_column` · `list_broken_relationships` · `get_health_report`

## Evals & the RL environment

Cataloguing a *known-broken* schema is a generation task with a *verifiable* answer — so StackAtlas ships with a graded eval, self-verification invariants, and a gym-style RL environment, not just a demo.

- **Deterministic reward.** Free-text findings are reduced to a closed issue-tag taxonomy and scored as set overlap against a hand-authored answer key — same catalog in, same reward out, no judge model.
- **Gated by self-verification.** A malformed catalog scores **zero** no matter how good its prose: garbage that doesn't validate is worthless to a downstream agent. This is the anti-reward-hacking backstop.
- **The reward separates signal**, monotonically: shipped catalog **0.814** · half the findings dropped **0.507** · empty **0.100** (current `make eval` output — regenerates with the catalog, so expect it to move modestly run to run rather than pin to these digits forever; see `evals/labels.py`'s `HEALTH_TOLERANCE` note for why).
- **Self-verification runs in production too** — the same invariants that grade the eval run on real customer schemas (where there's no answer key), and the generator checks its own output and re-prompts on a violation.
- **A gym-style `CatalogEnv`** (whole-database and per-table modes) plus a portable `tasks.jsonl` an external trainer can replay.

```bash
make eval    # score the shipped catalog against gold labels  →  reward ≈0.8 (see note above)
make test    # self-verification + reward + pipeline suite     →  55 tests
```

Full write-up — reward design, environment interface, extending to a new database — in **[`evals/README.md`](evals/README.md)**.

## Quickstart

**Dashboard (2 minutes, zero setup):**

```bash
npm install
npm run dev          # → http://localhost:3000
```

The demo catalog is baked in — no database, no env vars.

**Full pipeline against your own Postgres:**

```bash
pip install -r requirements.txt
python pipeline/introspect.py "postgresql://localhost/yourdb" > catalog_raw.json
export ANTHROPIC_API_KEY=sk-ant-...
python pipeline/docgen.py catalog_raw.json > mcp_server/catalog.json
```

## Repo structure

```
app/, components/            Next.js dashboard (schema graph, agent console, live UI)
db/seed.sql                  vibeshop — a deliberately messy demo schema
schema/catalog.schema.json   the one catalog contract every stage validates against
pipeline/introspect.py       Postgres → skeleton; soft-FK inference + broken-FK detection
pipeline/docgen.py           Claude writes docs + health, self-verifies its output
pipeline/render_dashboard_data.py  regenerates data/catalog.js from mcp_server/catalog.json
mcp_server/                  FastMCP server: the catalog as agent-queryable context
evals/                       eval harness + RL environment (taxonomy, reward, CatalogEnv)
```

Full clean-environment setup, exact commands for every step above, expected
output, versions, and measured runtime/cost: **[`REPRODUCTION.md`](REPRODUCTION.md)**.

## Tech

Next.js 14 · React · Python 3.11 · Postgres (`information_schema` + `pg_stat`) · Anthropic Claude · Model Context Protocol · pytest · GitHub Actions.

---

<div align="center">

Built by **Nainika Reddy Mula** — data & GTM engineering.
Enterprise BI observability, rebuilt for the long tail of AI-generated apps.

<sub>A founder-facing pitch for this project lives in <a href="PITCH.md"><code>PITCH.md</code></a>. Licensed under <a href="LICENSE">MIT</a>.</sub>

</div>
