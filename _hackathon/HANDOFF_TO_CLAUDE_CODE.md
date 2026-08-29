# Hand-off to Claude Code

Cowork (this planning session) produced: docker-compose + Makefile db targets,
this eval/baseline plan, the changelog scaffold. Claude Code does the parts that
must RUN on your machine with your ANTHROPIC_API_KEY, Docker, and long agent runs.

## Do these in Claude Code (in the stackatlas repo)
1. `make db-up` — confirm vibeshop comes up on :5433 from a clean clone.
2. `make pipeline` — regenerate `mcp_server/catalog.json` from the live DB.
3. Harden `db/seed.sql` per EVAL_AND_BASELINE_PLAN.md (§ seed hardening), re-run pipeline.
4. Build `evals/tasks_sql.jsonl` (12 cases) + a runner that:
   - runs the BASELINE agent (schema dump only) and the SOLUTION agent (MCP),
   - executes each produced query against vibeshop, compares result set to gold,
   - writes a per-case + overall scoreboard.
5. Capture **agent trajectories** for every agent used (baseline + solution):
   full instruction -> tool calls -> responses -> retries -> final. Save raw logs.
6. Fill IMPROVEMENT_CHANGELOG.md numbers as you run each iteration.

## Bring back to Cowork (this session) for the write-ups
- The scoreboard + query pairs  -> I turn them into the changelog prose + a chart.
- The raw trajectories          -> I curate them into the submission artifact.
- Final commands + versions     -> I write the Reproduction guide.
- The story                     -> I write the 5-minute video script + shot list.

## The rule of thumb
Runs code / calls agents / needs Docker or API key  -> Claude Code.
Turns results into a deliverable (prose, guide, script, chart) -> Cowork.
