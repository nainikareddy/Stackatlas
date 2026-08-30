# Solution Video — Script & Shot List

Target runtime: **4:45** (brief caps at 5:00). Every number below is pulled
directly from `evals/sql_eval_results.json` and `_hackathon/IMPROVEMENT_CHANGELOG.md`
— nothing here is invented for the video. Re-verify against those files if
the eval is re-run before recording, since the numbers can move (see
REPRODUCTION.md, "On non-determinism").

Format: **[time] VISUAL** — what's on screen. **VO** — spoken narration,
read close to verbatim. Bracketed stage directions are not spoken.

---

### [0:00–0:25] The problem

**VISUAL:** Dashboard open on `vibeshop`, health score 45/100 visible, schema
graph on screen.

**VO:**
"This is vibeshop — a typical AI-generated SaaS backend, live in Postgres.
It looks fine from the app. Underneath, its schema has rotted the way every
vibe-coded app's schema rots: a foreign key that still points at a table
nobody uses anymore, status codes with no documented meaning, money stored
two different ways in two different tables. A human developer works around
that quietly. An AI agent writing SQL against it doesn't — it hallucinates
a join and hands back a wrong number with full confidence. That's the
problem StackAtlas solves, for a team with no data team about to put agents
on top of a database they haven't looked at closely in months."

---

### [0:25–0:55] The baseline

**VISUAL:** Terminal — a plain Claude session given a `pg_dump --schema-only`
text dump of vibeshop and nothing else. No tools.

**VO:**
"Our baseline is the honest floor: an agent gets a schema-only dump —
table and column names, no docs, no tools — plus 12 real business
questions against this database. Same 12 questions, same database, every
arm we test. Baseline scores 8 out of 12, and it's worth watching *how*
it fails: not carelessly, but exactly where the schema stays silent."

---

### [0:55–2:35] One real execution, start to finish — case 6

**VISUAL:** Split or sequential: first the *db_access* arm (raw read-only
SQL tool, no catalog) asked live: **"List the line items — product,
quantity, price — for order id 5."** Then the same question against Claude
Desktop with the StackAtlas MCP server wired in.

**VO:**
"Watch the same question answered two ways. First, an agent with raw,
read-only access to the live database and nothing else. It looks for order
5, finds only three rows in the `orders` table, and gives up: 'there is no
order with id 5.' That's not a careless answer — it's the wrong answer,
because order 5 exists in `orders_v2`, and the foreign key it just checked
points at the *deprecated* table.

[SCREEN: type the same question into Claude Desktop with StackAtlas
connected. Show the `get_table_context` / `list_broken_relationships` tool
calls firing.]

Now the same question with StackAtlas wired in. It calls
`get_table_context`, and immediately learns two things: `order_items`
carries zero rows, and its `order_id` foreign key — enforced, not
optional — still points at `orders`, a table superseded months ago by
`orders_v2`. Nobody wrote that down anywhere else. StackAtlas found it from
schema structure and traffic alone, before a single LLM call. So instead of
fabricating a join, the agent tells you exactly why the question can't be
answered as asked. That's the correct behavior, and it's the flagship
finding this whole project is built around."

---

### [2:35–3:15] The final comparison

**VISUAL:** Scoreboard on screen:

| Arm | Score |
|---|---|
| Baseline — schema dump only | 8 / 12 |
| db_access — raw live DB, no catalog | 10 / 12 |
| StackAtlas MCP — solution | 12 / 12 |

**VO:**
"We didn't stop at baseline versus solution. We added a third arm on
purpose — an agent with raw, read-only access to the live database itself,
no catalog, no docs — to answer the obvious objection before a judge asks
it: couldn't the agent just query the database and work this out on its
own? It gets partway there: 10 out of 12. But *which* two it misses changes
every time you run it. Across three independent runs of the same 12
questions, solution held 12 out of 12 every single time. Baseline and
db_access never reproduced the same score twice."

---

### [3:15–4:00] The changelog — what actually moved the number, and what we caught

**VISUAL:** `IMPROVEMENT_CHANGELOG.md` scrolled briefly to Iteration 1, then
to the case 5 entry.

**VO:**
"The single highest-leverage fix wasn't adding more tools — it was one
change in the pipeline. Originally, the introspector only ever saw a
column's *default* value, so `orders_v2.status` could only be documented as
'presumably pending.' We added a guarded `SELECT DISTINCT` to sample real
observed values, so it could say: 'p' means pending, 'c' means completed,
'r' means refunded — grounded in actual data, not a guess. That one change
took three failing cases straight to passing.

And one thing we caught rather than reported: an earlier run scored
solution 11 out of 12, not 12. Before accepting that number, we checked the
failing case — the question itself was ambiguous two different ways at
once: 'grouped by workspace' could mean the id or the name, and 'in USD'
was never actually stated. We fixed the question, re-ran it three times,
and confirmed the agent had been right both times — the eval was wrong."

---

### [4:00–4:40] Hot take + close

**VISUAL:** Back to the dashboard, then the MCP config JSON.

**VO:**
"Here's the real lesson: giving an agent more freedom to go explore isn't
automatically safer. Raw database access sometimes closes the gap on its
own — and sometimes it silently drops a row on a bad join, or quietly
redefines what 'paying customer' means mid-task. What a shared context
layer buys you isn't a right answer once — it's the *same* right answer,
every run, which a non-deterministic model can't promise on its own no
matter how much access you hand it.

That's StackAtlas: one catalog, generated once, served two ways — a
dashboard for humans, an MCP server for agents — so every agent stops
guessing what the schema means, and starts querying what it actually
means."

**[END — 4:40]**

---

## Notes for whoever records this

- The dashboard's "Agent Context Query" panel is a scripted keyword-matcher
  over canned answers, labeled as such in its own header — **do not use it
  as the live-agent proof.** The case 6 walkthrough above, run against the
  real MCP server in Claude Desktop/Code, is the actual live demo.
- Record a Loom/screen-capture fallback per PITCH.md's advice — live MCP
  has moving parts.
- If the eval is re-run before recording and numbers shift (expected —
  see REPRODUCTION.md), update the scoreboard and case 6 walkthrough to
  match the fresh `evals/sql_eval_results.json`, don't reuse these numbers
  blind.
