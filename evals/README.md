# Evals & the RL environment

StackAtlas turns a messy database into a catalog: docs, issue findings, and a
health call per table. That is a *generation* task with a *verifiable* answer —
which makes it a clean fit for evaluation and for reinforcement learning. This
directory is the machinery that makes the task legible: a fixed answer key, a
deterministic reward, self-verification invariants, and a gym-style environment.

## Why this task is RL-legible

Three properties have to hold before you can optimise against a signal. This
task has all three:

| Property | How StackAtlas gets it |
|---|---|
| **Knowable ground truth** | `db/seed.sql` is a *deliberately* broken schema. Every flaw — the broken FK, the camelCase drift, the float-for-money, the epoch timestamps — was planted on purpose, so the answer key in `labels.py` is authoritative, not guessed. |
| **Deterministic reward** | Free-text findings are reduced to a closed **tag taxonomy** (`taxonomy.py`) by pure regex, then scored as set overlap. Same catalog in → same reward out, every time. No judge model in the loop. |
| **Cheap verification** | Scoring is milliseconds of Python. An RL trainer can call it on every rollout without a rate limit or an API bill. |

## The reward

`scorer.score(catalog)` returns a scalar in `[0, 1]`, gated by
self-verification:

```
reward = valid_gate × ( 0.50 · issue_f1          # did it find the real flaws?
                      + 0.25 · status_accuracy   # right health call per table?
                      + 0.15 · health_reward     # global score within tolerance
                      + 0.10 · (1 − hallucination) )
```

`valid_gate` is **0** when the catalog fails a structural invariant
(`verify.py`) and 1 otherwise: a malformed catalog is worthless to a downstream
agent no matter how sharp its prose, and the reward says so. This is the
anti-reward-hacking backstop — a policy can't win by emitting confident
garbage, because garbage doesn't validate.

Run it:

```bash
python -m evals.run_eval                  # score the shipped catalog  -> ~0.8 (see note)
python -m evals.run_eval --baseline empty # everything "healthy"       -> ~0.1
python -m evals.run_eval --baseline half  # half the findings dropped  -> ~0.5
python -m evals.run_eval --threshold 0.70 # CI gate: exit 1 if below
```

The exact numbers move with the shipped catalog (docgen's LLM output is
non-deterministic — a same-catalog regeneration was observed to swing
0.883 → 0.814 with no real accuracy change, see `labels.py`'s
`HEALTH_TOLERANCE` note and `IMPROVEMENT_CHANGELOG.md`), so don't expect
these to third-decimal-match on your machine. The spread itself is the
point, and it's stable: shipped catalog **≈0.8**, half the findings
dropped **≈0.5**, empty **≈0.1** — the reward *separates* signal from
noise, monotonically, every time it's run. A reward that can't tell a
good catalog from an empty one is useless for training; this one is
tested to do so (`test_reward_separates_signal`).

## Two levels of verification

- **`verify.py` — no answer key needed.** Schema conformance (draft-07 against
  `schema/catalog.schema.json`) plus semantic invariants: every flagged column
  is documented, every non-healthy table names an issue, edges reference real
  tables, stats match the table array. These run in **production**, on real
  customer schemas where there is no gold set, and the generator (`docgen.py`)
  runs them on its own output and re-prompts once on a violation. This is the
  self-verification loop.
- **`scorer.py` — graded against gold.** Used for eval and RL, where the
  fixture's labels are known.

## The environment

`env.CatalogEnv` wraps the task in a gym-style loop. The observation is the
schema *skeleton* — tables, columns, traffic, enforced FKs — with the docs,
issues, statuses, and column flags stripped out, because those are exactly what
the policy must produce.

```python
from evals import CatalogEnv
import json

catalog = json.load(open("mcp_server/catalog.json"))

# whole-database (bandit): one observation, one catalog, one reward
env = CatalogEnv(catalog, mode="whole")
obs = env.reset()                 # skeleton only — no answers leaked
result = env.step(my_catalog)     # full reward breakdown
print(result["reward"])

# per-table (episodic): finer credit assignment, one table per step
env = CatalogEnv(catalog, mode="per_table")
obs = env.reset()
done = False
while not done:
    action = policy(obs)          # {status, issues, doc?, columns?}
    obs, reward, done, info = env.step_table(action)
```

## The portable task set

`build_tasks.py` emits `tasks.jsonl` — one row per table plus a whole-database
row, each pairing an observation with its reference tags and reward spec. It is
self-contained: an external trainer replays it with only `taxonomy.tag_issues`
to score predictions, no other StackAtlas code required.

```bash
python -m evals.build_tasks   # -> evals/tasks.jsonl (15 tasks)
```

## Files

| File | Role |
|---|---|
| `taxonomy.py` | closed issue-tag vocabulary + deterministic prose→tag tagger |
| `labels.py` | gold tags + status + health score for the `vibeshop` fixture |
| `verify.py` | self-verification invariants (schema + semantic), no gold needed |
| `scorer.py` | the composite reward function |
| `env.py` | `CatalogEnv` — gym-style whole-DB and per-table interfaces |
| `build_tasks.py` | writes the portable `tasks.jsonl` dataset |
| `run_eval.py` | CLI: score a catalog, print the reward card, CI gate |
| `test_evals.py` | the suite that proves all of the above holds |

## Extending to a new database

Introspect it, add its labels alongside `vibeshop` in `labels.py` (or a sibling
module), and it drops straight into the scorer, the environment, and the task
set. The harness is fixture-agnostic; only the answer key is per-DB.
