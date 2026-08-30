# Reproduction Guide

Written for someone starting from a clean clone of this repo. Four things
can be reproduced independently, from cheapest to most expensive: the
dashboard (no setup), the catalog-quality eval (no setup, no LLM), the full
pipeline against a live DB (needs Docker + `claude` CLI), and the graded
baseline-vs-solution SQL comparison (needs Docker + `claude` CLI, takes
real wall-clock time). Do them in that order — each one is a checkpoint
before the more expensive next step.

## Versions this was built and last verified against

| Tool | Version |
|---|---|
| Node | v24.18.0 |
| npm | 11.16.0 |
| Python | 3.11.16 |
| Docker | 29.7.2 |
| Docker Compose | 5.5.0 |
| Claude Code CLI (`claude`) | 2.1.251 |
| `psycopg2-binary` | 2.9.12 |
| `mcp` | 1.29.1 |
| `jsonschema` | 4.26.0 |
| Next.js / React | 14.2.35 / 18.3.1 (pinned in `package.json`) |

No `ANTHROPIC_API_KEY` is needed anywhere. `pipeline/docgen.py` and
`evals/run_sql_eval.py` both shell out to `claude -p` (the Claude Code CLI
in headless print mode), which authenticates with your existing Claude
subscription login (`claude auth` / already logged in to this CLI) — so the
"cost" of the LLM-calling steps below is against your subscription's usage,
not a metered API bill.

## 1. Dashboard — zero setup, ~2 minutes

```bash
npm install
npm run dev          # -> http://localhost:3000
```

No database, no env vars, no LLM calls. `data/catalog.js` is a pre-generated
artifact (see step 3 for how it's produced) baked into the bundle.
**Expected output:** a dashboard showing `vibeshop`, health score **45/100**,
14 tables / 61 columns, `order_items` selected shows the broken-FK issue
first in its issue list. The "Agent Context Query" panel is a scripted
keyword-matcher over canned answers (labeled as such in its header) — it is
not live MCP; that's step 5.

```bash
npm run build         # production build check; should complete with no errors
```

## 2. Catalog-quality eval — zero setup, no LLM, <1 second

Scores the *shipped* `mcp_server/catalog.json` against a hand-authored gold
answer key (`evals/labels.py`) for the deliberately-broken `vibeshop` fixture.
Pure Python, no network calls.

```bash
pip install -r requirements-dev.txt
make eval     # or: python -m evals.run_eval
make test     # or: python -m pytest -q
```

**Expected output:** `make eval` prints a reward around **0.8** (measured
this session: `0.814`) and `make test` reports **55 passed**. The exact
reward is *not* pinned to that digit — see "On non-determinism" below —
but `python -m evals.run_eval --baseline empty` should always score much
lower (~0.1) and `--baseline half` in between (~0.5): that separation,
not the exact digit, is what the eval is actually testing
(`test_reward_separates_signal` in `evals/test_evals.py`).

**Measured runtime:** `make eval` 0.12s, `make test` 0.34s, this session.

## 3. Full pipeline — regenerate the catalog against a live Postgres

Needs Docker running.

```bash
make db-up                                    # dockerized vibeshop on :5433, ~10-30s cold
python pipeline/introspect.py "postgresql://stackatlas:stackatlas@localhost:5433/vibeshop" > catalog_raw.json
python pipeline/docgen.py catalog_raw.json > mcp_server/catalog.json
python -m evals.verify mcp_server/catalog.json   # self-verification, no gold needed
python pipeline/render_dashboard_data.py         # regenerate data/catalog.js from the new catalog
```

Or the Makefile shortcut for the introspect+docgen steps: `make pipeline`
(reads `DSN` from the environment, defaults to the same dockerized DSN
above).

**Expected output:** `mcp_server/catalog.json` regenerated with a fresh
`generatedAt` timestamp; `evals.verify` prints `OK`; `data/catalog.js`
regenerated to match (its `healthScore` should equal the JSON's). Re-run
step 2 afterward — the exact reward will move (docgen is a non-deterministic
LLM call per table), typically within the same ~0.75-0.9 band observed so
far.

**Runtime:** not precisely measured this session (`docgen.py` makes one
`claude -p` call per table — 14 tables — so budget roughly the same
per-call latency as step 5 below, i.e. very roughly 3-5 minutes; time it
yourself with `time python pipeline/docgen.py catalog_raw.json > mcp_server/catalog.json`
for an exact number on your connection).

## 4. Wire the MCP server into Claude — the live agent demo

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

Add to Claude Desktop / Claude Code's MCP config, restart, then ask:
*"Write me a monthly revenue query for this database."* Expected: it calls
`get_table_context`, cites `orders_v2.amount_cents` where `status = 'c'`,
notes cents-not-dollars and the two refund locations, and writes a correct
query — instead of guessing.

## 5. The graded comparison — baseline vs. db_access vs. solution

This is the actual evidence behind the "does StackAtlas help" claim: the
same 12 business questions, run three ways, scored by executing the agent's
SQL against the live DB and comparing the result set to a gold reference
query (not string matching). See `evals/run_sql_eval.py`'s module docstring
and `_hackathon/IMPROVEMENT_CHANGELOG.md` for what each arm gets.

```bash
make db-up                          # if not already up
source .venv/bin/activate           # or however you activate your venv
python -m evals.run_sql_eval --json > evals/sql_eval_results.json
```

Or human-readable (no `--json`) for a scoreboard printed to stdout instead
of a file. `--case N` runs a single case; `--arm {baseline,db_access,solution}`
runs a single arm — useful for iterating without burning a full 36-call run.
Runs are parallelized (`--concurrency`, default 5 — pass `--concurrency 1`
to force the old fully-sequential behavior, e.g. if you're rate-limit
constrained).

**Expected output:** a per-case PASS/FAIL scoreboard and totals, and
per-case trajectories at `evals/trajectories/<case>_<arm>.jsonl`. `solution`
has never produced a genuine reasoning error across three runs of this
eval; the one run where it scored 11/12 rather than 12/12 was traced to a
task-definition ambiguity, not an agent mistake, and fixed (see
`_hackathon/IMPROVEMENT_CHANGELOG.md`, Iteration 3) — so **solution should
be 12/12** on a fresh run. `baseline` and `db_access` will most likely NOT
reproduce the exact same per-case results as `evals/sql_eval_results.json`
in this repo — see "On non-determinism" below, this is expected and is
itself part of the documented finding, not a sign something broke.

**Measured runtime (this session, full 36-call run — 12 cases × 3 arms,
`--concurrency 5`):** **2 minutes 4 seconds** wall-clock, timestamped from
the trajectory files themselves (`evals/trajectories/*.jsonl`, first event
to last event) — down from 8m15s on the same 36 calls run fully
sequentially (`--concurrency 1`), before the runner was parallelized.
**Cost:** $0 in metered API spend — routed through `claude -p`'s
subscription auth, not the Anthropic API — but it does consume your Claude
subscription's usage allowance for that ~2 minutes of concurrent agent
activity across 36 calls.

## On non-determinism — read this before assuming something is broken

`docgen.py` and every `claude -p` call in `run_sql_eval.py` are LLM calls.
Two independently observed effects, both already documented in the codebase
rather than hidden:

- **`evals/labels.py`'s `HEALTH_TOLERANCE`** is set to 20 (not a tighter
  number) specifically because the same catalog, regenerated, was observed
  to vary the health score by ~7-10 points with no real change in accuracy.
- **The SQL eval's `baseline`/`db_access` arms varied across all three runs**
  captured in this repo's history (`_hackathon/IMPROVEMENT_CHANGELOG.md`,
  Iterations 2 and 3): `baseline` 8/12, 7/12, 8/12; `db_access` 10/12,
  9/12, 10/12. `solution` scored 12/12, 12/12, then 11/12 — but that one
  miss was independently verified as objectively correct data reported
  under a different (equally valid) key column, not a reasoning error;
  the underlying task ambiguity is now fixed. That stability gap between
  `solution` and the other two arms — not any single run's exact digit —
  is the claim being made.

If you reproduce step 5 and get, say, `baseline 8/12, db_access 9/12,
solution 12/12` instead of the exact numbers in `evals/sql_eval_results.json`,
that is consistent with everything documented above, not a regression.
If `solution` scores below 12/12 on a fresh run, check the specific
failing case against `_hackathon/IMPROVEMENT_CHANGELOG.md` first — it may
be a task ambiguity like case 5 or 11 that hasn't surfaced yet, in which
case the right fix is the question, not the agent.

## Cleanup

```bash
make db-down    # stops and deletes the dockerized vibeshop (fresh next time)
```
