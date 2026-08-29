# Improvement Changelog

Format per the brief: one entry per meaningful experiment. Add the result using
the SAME 12 cases each time. Include experiments you later removed.

## Baseline — raw schema dump, no context
- **Tried / why:** give the agent only the schema DDL + the question.
- **Result:** [X / 12 correct]  (fill after run)
- **Learning:** where it fails — [wrong table / status codes / cents / broken FK]

## Iteration 1 — + StackAtlas docs (get_table_context)
- **Tried / why:** expose table/column docs so the agent stops guessing.
- **Result:** [Y / 12]
- **Decision:** [kept / revised]

## Iteration 2 — + list_broken_relationships & health
- **Tried / why:** after observing the order_items -> orders failure (case 6).
- **Result:** [Z / 12]
- **Decision:** [kept / revised]

## Iteration 3 — + self-verification re-prompt
- **Tried / why:** agent re-checks its own query against invariants before answering.
- **Result:** [W / 12]
- **Decision:** [kept / revised]

## Removed experiment — [e.g. dumping full catalog JSON into the prompt]
- **Tried / why:** [context stuffing instead of tool calls]
- **Result:** [worse / more tokens / same]
- **Learning:** [why targeted tool calls beat context stuffing] — good hot-take material.

## Final — combination that worked
- **Result:** [final / 12]
- **Main contribution:** [the single change that moved the number most]
