# Eval & baseline plan — "agent writes correct SQL against a rotting schema"

The graded unit is NOT "did StackAtlas produce a good catalog." It is:
**does an agent do a real downstream task better because of StackAtlas?**
Task = answer a business question by writing SQL against `vibeshop`.

## The two arms (same task, same 12 cases, same model)

- **Baseline** — agent gets only a raw schema dump (`pg_dump --schema-only` or
  `\d` output) as text, plus the question. No docs, no health, no MCP.
- **Solution** — same agent + the StackAtlas MCP server (`get_table_context`,
  `explain_column`, `list_broken_relationships`, `get_health_report`).

Keep everything else identical (model, temperature, prompt shell). The only
variable is the context layer. That is what makes the improvement attributable.

## Scoring (deterministic, executable — not string matching)

For each case: run the agent's SQL against the dockerized `vibeshop`
(`make db-up`), compare the **result set** to the gold result (the result of a
hand-written reference query). Score = fraction of cases whose result set
matches gold. Executable correctness ("baseline returns $0, solution returns
$239.00") is far stronger evidence than "the query looks right."
A few cases are *judgment* cases (correct answer = recognizing an impossibility);
score those on whether the agent surfaced the broken relationship instead of
fabricating a join.

## ⚠ Seed hardening first (do this before scoring)

The current `db/seed.sql` has coincidences that mute the contrast. Fix so every
trap yields a CLEARLY wrong baseline number:
1. **Legacy `orders` totals coincide with correct revenue** ($49+$190 = $239,
   same as orders_v2 status='c'). Change legacy `orders.total` values to stale
   numbers (e.g. 99.00, 250.00) so an agent that uses the legacy table is
   visibly wrong.
2. **`order_items` is empty.** That is realistic (the app stuffs line items into
   `orders_v2.meta`), and it powers the flagship trap — keep it empty, and add a
   case that asks for line items so the baseline joins `order_items -> orders`
   (legacy) and returns nothing.
3. Add ~10-15 more `orders_v2` rows across statuses so cents-vs-dollars and
   status-code errors produce distinctive wrong totals.
Regenerate gold by running each reference query after hardening.

## Case set (12) — trap → correct source

| # | Question | Trap | Correct source / reference |
|---|----------|------|----------------------------|
| 1 | Total completed revenue (USD) | legacy `orders` vs `orders_v2`; status 'c' not 'completed'; cents not dollars | `sum(amount_cents)/100.0 FROM orders_v2 WHERE status='c'` |
| 2 | Total refunded (USD) | refunds in two places: `orders_v2.status='r'` and `payments.state='refunded'` | define canonical source (payments); avoid double count |
| 3 | # paying customers | `users.plan` free vs pro/team, undocumented | `count(*) FROM users WHERE plan IN ('pro','team')` |
| 4 | # active products | orphan `product_catalog_old` (float money, stale) | `count(*) FROM products WHERE active` |
| 5 | Revenue by workspace | `orders_v2.workspace_id` has no FK | group by workspace_id, status='c' |
| 6 | Line items for an order (NASTY) | `order_items.order_id -> orders` (legacy), real data in `orders_v2.meta` | judgment: agent must flag broken FK / use meta, not fabricate |
| 7 | # cancelled orders | status 'x' not 'cancelled' | `WHERE status='x'` on orders_v2 |
| 8 | Signups per day | `users.created_at` timestamptz vs `analytics_events.ts` epoch int | use users.created_at |
| 9 | Events per user | `analytics_events.uid` means user_id (naming drift) | group by uid -> users.id |
| 10 | Workspace owner name | `workspaces."ownerId"` camelCase, no FK | join "ownerId" = users.id |
| 11 | Avg product price (USD) | `products.price_cents` int vs `product_catalog_old.price` float | products.price_cents/100.0 |
| 12 | Users with duplicate emails | `users.email` has no unique index | group by email having count>1 |

Case 1 is the headline number for the video. Case 6 is the "one challenging
case" the brief asks for.

## Deliverable outputs this produces
- `evals/tasks_sql.jsonl` — 12 cases (question, reference SQL, trap tag).
- A results table: baseline score vs solution score, per case + overall.
- Per-case query pairs (baseline SQL vs solution SQL) for the changelog/video.
