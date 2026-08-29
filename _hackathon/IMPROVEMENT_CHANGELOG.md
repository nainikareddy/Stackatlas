# Improvement Changelog

Format per the brief: one entry per meaningful experiment. Same 12 cases
(`evals/tasks_sql.jsonl`) every time, scored by `python -m evals.run_sql_eval`
(deterministic: agent SQL executed against the dockerized vibeshop, result
set compared to a gold reference query, not string matching). Full
per-case trajectories (instruction -> tool calls -> tool results -> final
answer) are in `evals/trajectories/*.jsonl`; the raw scoreboard this run
produced is `evals/sql_eval_results.json`.

## Baseline — raw schema dump, no context
- **Tried / why:** agent gets a real `pg_dump --schema-only` text dump of
  vibeshop plus the question. No docs, no health, no MCP, no tools at all
  (`--tools ""`).
- **Result:** 8 / 12 correct
- **Learning:** every failure is exactly where the schema is genuinely
  undocumented, not where the agent is careless:
  - **Case 1** (total completed revenue) — correctly notices `orders` and
    `orders_v2` disagree and neither table's status vocabulary is
    documented, and *declines to guess* rather than answering wrong. Scored
    as a failure (no queryable SQL), but arguably the more honest response
    than cases 5/7.
  - **Case 5** (revenue by workspace) — guesses `status = 'completed'`
    (borrowed from the *legacy* `orders` table's vocabulary), matches zero
    rows against `orders_v2`, returns nothing.
  - **Case 7** (cancelled orders) — guesses via `ILIKE '%cancel%'` plus
    `status = 'c'`, sums both legacy and v2 tables, gets 8 instead of 3.
  - **Case 6** (line items, judgment case) — silently joins `order_items` to
    `products` filtered by `order_id = 5` with zero caveat that the FK
    targets the deprecated `orders` table, not `orders_v2` — exactly the
    fabricated-join failure mode the case is designed to catch.

## Final — full StackAtlas MCP (search_tables, get_table_context,
  explain_column, list_broken_relationships, get_health_report)
- **Tried / why:** same 12 questions, no schema dump at all — the agent has
  to discover tables/columns/relationships itself via the 5 MCP tools
  before it can write anything.
- **Result:** 12 / 12 correct
- **Main contribution:** turned out not to be `list_broken_relationships`
  (though it does directly fix case 6) — it was a *pipeline* fix made
  because the first real run of this eval failed cases 1/5/7 on the
  solution side too. `introspect.py` originally only ever exposed a
  column's `DEFAULT` value to docgen, never real observed data, so
  `orders_v2.status` could only be documented as "presumably pending" —
  not enough to answer with confidence. Added `sample_distinct_values()` (a
  real, guarded `SELECT DISTINCT` query for low-cardinality columns) so
  docgen could write "observed values are 'p' (pending), 'c' (completed),
  'r' (refunded), 'x' (canceled)" instead of hedging. That one change is
  what took cases 1/5/7 from failing to passing on the solution side.
- **Decision:** kept — both the tool bundle and the sampling fix.

## Not run this pass — incremental tool ablation (docs-only vs
  +broken-relationships vs +self-verification re-prompt)
The MCP server exposes all 5 tools as one bundle rather than gated stages,
so isolating "docs alone" from "+broken-relationships" would mean 2 more
full 12-case runs with a narrower `--allowedTools` each, and a
self-verification re-prompt loop isn't implemented in `run_sql_eval.py`
yet. Given the baseline/solution contrast was already the graded task and
clearly attributable (see above), only the two endpoints were run this
pass. `evals/run_sql_eval.py`'s `MCP_TOOLS` list and `_run_claude(...,
tools_mode=...)` already support scoping to a subset, so this is a
straightforward follow-up, not a redesign.

## Removed experiment — none this pass
No context strategy was tried and discarded here (that's a natural
candidate for a *next* iteration, e.g. dumping the full `catalog.json`
into the prompt instead of tool calls, to make the "targeted tool calls
beat context stuffing" case explicitly). Two runner bugs were found and
fixed while getting a trustworthy baseline number, not context-strategy
experiments: `claude -p`'s arg parser was misreading the `pg_dump` schema
dump as an unknown CLI flag (it starts with `--`, SQL-comment syntax) and
silently failing every baseline call before a single case actually ran;
and the result-set comparison was exact-match, which incorrectly failed
several solution-arm answers that were fully correct but included extra
descriptive columns (e.g. a workspace's name alongside its id). Both are
covered by `evals/test_run_sql_eval.py` now.

## Final — combination that worked
- **Result:** 12 / 12 (solution) vs 8 / 12 (baseline)
- **Main contribution:** the StackAtlas MCP tools, backed by a catalog
  whose magic-value documentation is grounded in real sampled data instead
  of guesses.
