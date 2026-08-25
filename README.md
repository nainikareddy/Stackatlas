# StackAtlas

**The context layer for AI agents.** Point it at a database; get a living catalog — schema graph, AI-written docs, health signals — plus an MCP server so AI agents stop guessing what `orders_v2.status = 'c'` means.

Built by a data/GTM engineer (Datalogz): enterprise BI observability, rebuilt for the long tail of AI-generated apps.

## Why now

Millions of vibe-coded apps shipped since 2024. Their schemas rot: dropped FKs, magic status values, orphaned tables, three timestamp conventions in one database. Humans suffer quietly; AI agents fail loudly — an agent writing SQL against an undocumented schema hallucinates joins. Every agent needs this context layer. Nobody serving the long tail sells one.

## Repo map

```
app/, components/       Next.js dashboard (futuristic UI, flickering-numbers canvas)
data/catalog.js         Pre-generated catalog powering the UI (zero-setup demo)
db/seed.sql             "vibeshop" — a deliberately messy vibe-coded Postgres schema
schema/catalog.schema.json  The one catalog contract every stage validates against
pipeline/introspect.py  Postgres → catalog skeleton; detects soft + broken FKs
pipeline/docgen.py      Claude writes docs + health findings, self-verifies output
mcp_server/server.py    FastMCP server: the catalog as agent-queryable context
mcp_server/catalog.json Same catalog, JSON, consumed by the MCP server
evals/                  Eval harness + RL environment (see evals/README.md)
PITCH.md                Investor presentation script + the ask
```

## Run the dashboard (2 minutes)

```bash
rm -rf node_modules   # if a partial install is present
npm install
npm run dev           # → http://localhost:3000
```

No env vars, no database — the demo catalog is baked in.

## Run the full pipeline (optional, ~15 min)

```bash
pip install -r requirements.txt

# 1. Create the messy demo DB
createdb vibeshop && psql vibeshop -f db/seed.sql

# 2. Introspect it → skeleton with soft-FK inference + broken-FK detection
python pipeline/introspect.py "postgresql://localhost/vibeshop" > catalog_raw.json

# 3. Let Claude document it (validates its own output against the schema)
export ANTHROPIC_API_KEY=sk-ant-...
export STACKATLAS_MODEL=claude-sonnet-4-5     # optional; this is the default
python pipeline/docgen.py catalog_raw.json > mcp_server/catalog.json
```

Introspection alone (no LLM) already reproduces the flagship finding: the
`order_items → orders` foreign key still points at a table `orders_v2`
superseded — detectable from structure plus traffic.

## Wire the MCP server into Claude (the money demo)

Claude Desktop → Settings → Developer → Edit Config:

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

Restart Claude, then ask:

- *"What does orders_v2.status mean?"*
- *"Why is order_items empty?"*
- *"Which tables are safe to drop?"*
- *"Write me a monthly revenue query for this database."*  ← watch it use the catalog instead of hallucinating

Tools exposed: `search_tables`, `get_table_context`, `explain_column`, `list_broken_relationships`, `get_health_report`.

## Evals & RL environment

Cataloguing a known-broken schema is a task with a verifiable answer, so it
ships with a graded eval, self-verification invariants, and a gym-style RL
environment. The reward separates a correct catalog (1.000) from an empty one
(0.279), and a malformed catalog is gated to zero.

```bash
pip install -r requirements-dev.txt
make eval    # score the shipped catalog against gold labels  -> reward 1.000
make test    # full suite: self-verification + reward + pipeline (40 tests)
```

Full write-up — reward function, environment interface, anti-reward-hacking
design, and how to extend to a new database — in [`evals/README.md`](evals/README.md).

## Roadmap

Done: dashboard, messy demo schema, catalog + JSON-Schema contract, pipeline
(introspection with broken-FK detection + self-verifying docgen), MCP server,
and the eval + RL harness with CI.

Next: run the pipeline end-to-end on a real Supabase instance → migration
drift alerts (diff catalogs across runs) → hosted multi-tenant version.

See `PITCH.md` for how to present this and what to ask for.
