"""The graded task: does an agent write correct SQL against vibeshop better
with StackAtlas than without? See _hackathon/EVAL_AND_BASELINE_PLAN.md.

    make db-up                      # dockerized vibeshop on :5433
    python -m evals.run_sql_eval    # runs both arms, all 12 cases

Two arms, same 12 cases (evals/tasks_sql.jsonl), same model, same prompt
shell -- the only variable is the context layer:

  BASELINE  question + a raw `pg_dump --schema-only` text dump. No tools.
  SOLUTION  question only + the StackAtlas MCP tools (search_tables,
            get_table_context, explain_column, list_broken_relationships,
            get_health_report). No schema dump -- it has to go find the
            schema itself, the way an agent actually would.

Both arms run through `claude -p` (Claude Code CLI, headless print mode),
which authenticates with your Claude subscription login -- no API key.
Scoring is deterministic and executable, not string matching: the agent's
SQL is run against the live vibeshop DB and the result set is compared to
a gold reference query executed fresh each run (evals/tasks_sql.jsonl only
stores the reference SQL, never a baked-in expected value, so this stays
correct if the seed data changes again). Case 6 is a judgment case -- there
is no correct result set to compare against, only whether the agent
surfaced the broken order_items -> orders relationship instead of
fabricating a join; see `_score_judgment` for the (documented, heuristic)
criteria.

Every `claude -p` call's full stream-json trajectory (instruction -> tool
calls -> tool results -> retries -> final answer) is saved under
evals/trajectories/<case_id>_<arm>.jsonl for the write-up.
"""
from __future__ import annotations

import argparse
import decimal
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import psycopg2

_ROOT = Path(__file__).resolve().parent.parent
_TASKS = _ROOT / "evals" / "tasks_sql.jsonl"
_TRAJECTORIES = _ROOT / "evals" / "trajectories"
_MCP_SERVER = _ROOT / "mcp_server" / "server.py"

MODEL = os.environ.get("STACKATLAS_MODEL", "sonnet")
DSN = os.environ.get("DSN", "postgresql://stackatlas:stackatlas@localhost:5433/vibeshop")

MCP_TOOLS = [
    "search_tables", "get_table_context", "explain_column",
    "list_broken_relationships", "get_health_report",
]

BASELINE_SYSTEM = """You are a data analyst. You will be given a raw PostgreSQL \
schema dump (DDL only, no data, no documentation) and a business question. \
Using ONLY the schema shown, write a single PostgreSQL query that answers the \
question as accurately as you can. You have no tools, no live data samples, \
and no documentation beyond the schema text below -- work from it alone, the \
way a raw pg_dump --schema-only output would read to a new engineer. \
Respond with ONLY the final SQL query in a ```sql fenced code block. If you \
believe the schema genuinely cannot answer the question reliably, say so in \
one sentence before the code block instead of guessing silently."""

SOLUTION_SYSTEM = """You are a data analyst with access to the StackAtlas MCP \
tools for this database: search_tables, get_table_context, explain_column, \
list_broken_relationships, get_health_report. You do NOT have a schema dump -- \
use these tools to discover the tables, columns, relationships, and known \
data-integrity issues you need before writing SQL. Call get_table_context on \
any table before querying it, and check list_broken_relationships before \
writing a join. Once you're confident, respond with ONLY the final SQL query \
in a ```sql fenced code block. If the tools reveal the question can't be \
answered reliably (e.g. a broken relationship or an empty table), say so in \
one or two sentences instead of fabricating a query."""

_JUDGMENT_OK_PHRASES = [
    "meta", "broken", "deprecated", "empty", "no rows", "no data",
    "not reliable", "unreliable", "doesn't have", "does not have",
    "isn't populated", "not populated", "no line item", "unenforced",
    "not enforced", "can't reliably", "cannot reliably", "stale",
    "wrong table", "legacy",
]


def _load_tasks():
    tasks = []
    with open(_TASKS) as f:
        for line in f:
            line = line.strip()
            if line:
                tasks.append(json.loads(line))
    return tasks


def _schema_dump() -> str:
    """A raw `pg_dump --schema-only` text dump -- exactly what the baseline
    arm sees. Falls back to an information_schema-built DDL sketch if pg_dump
    isn't reachable (e.g. no Docker), so the eval still runs somewhere."""
    try:
        proc = subprocess.run(
            ["docker", "compose", "exec", "-T", "db", "pg_dump",
             "-U", "stackatlas", "-d", "vibeshop",
             "--schema-only", "--no-owner", "--no-privileges"],
            cwd=_ROOT, capture_output=True, text=True, timeout=30, check=True,
        )
        lines = [l for l in proc.stdout.splitlines()
                 if not l.startswith("\\restrict") and not l.startswith("\\unrestrict")]
        return "\n".join(lines)
    except Exception as e:  # noqa: BLE001 - fall back below either way
        print(f"[run_sql_eval] pg_dump via docker compose failed ({e}); "
              f"falling back to an information_schema sketch", file=sys.stderr)
        return _schema_sketch()


def _schema_sketch() -> str:
    conn = psycopg2.connect(DSN)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT table_name, column_name, data_type, is_nullable, column_default
            FROM information_schema.columns WHERE table_schema='public'
            ORDER BY table_name, ordinal_position;
        """)
        by_table: dict[str, list[str]] = {}
        for table, col, dtype, nullable, default in cur.fetchall():
            bits = f'"{col}" {dtype}'
            if nullable == "NO":
                bits += " NOT NULL"
            if default:
                bits += f" DEFAULT {default}"
            by_table.setdefault(table, []).append(bits)
        return "\n\n".join(
            f"CREATE TABLE {t} (\n  " + ",\n  ".join(cols) + "\n);"
            for t, cols in by_table.items()
        )
    finally:
        conn.close()


def _mcp_config_path(tmpdir: Path) -> Path:
    cfg = {"mcpServers": {"stackatlas": {
        "command": sys.executable, "args": [str(_MCP_SERVER)],
    }}}
    path = tmpdir / "stackatlas_mcp.json"
    path.write_text(json.dumps(cfg))
    return path


def _run_claude(prompt: str, system_prompt: str, *, tools_mode: str,
                 mcp_config: Path | None, cwd: Path, trajectory_path: Path) -> dict:
    """Invoke `claude -p` in headless print mode and capture the full
    stream-json trajectory to trajectory_path. Returns
    {"text": final answer text, "is_error": bool, "raw_events": [...]}."""
    args = [
        "claude", "-p",
        "--model", MODEL,
        "--system-prompt", system_prompt,
        "--setting-sources", "",
        "--output-format", "stream-json", "--verbose",
        "--no-session-persistence",
    ]
    if tools_mode == "none":
        args += ["--tools", ""]
    elif tools_mode == "mcp_only":
        assert mcp_config is not None
        allowed = ",".join(f"mcp__stackatlas__{t}" for t in MCP_TOOLS)
        args += [
            "--mcp-config", str(mcp_config),
            "--strict-mcp-config",
            "--restricted",
            "--allowedTools", allowed,
        ]
    # "--" end-of-options marker before the prompt: a positional argument
    # that happens to start with "-" (e.g. a pg_dump schema dump starts with
    # "--" SQL-comment syntax) is otherwise misparsed as an unknown option
    # instead of the prompt text -- silently fails every such call. Verified
    # against this build; see commit history for how this was found.
    args += ["--", prompt]

    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=240)

    events = []
    final_text, is_error = "", True
    with open(trajectory_path, "w") as tf:
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            tf.write(line + "\n")
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            events.append(evt)
            if evt.get("type") == "result":
                final_text = evt.get("result", "")
                is_error = bool(evt.get("is_error"))
    if proc.returncode != 0 and not events:
        # claude itself failed to start (bad flags, etc.) -- surface stderr
        with open(trajectory_path, "a") as tf:
            tf.write(json.dumps({"type": "launch_error", "stderr": proc.stderr}) + "\n")
        return {"text": "", "is_error": True, "raw_events": []}
    return {"text": final_text, "is_error": is_error, "raw_events": events}


_SQL_FENCE = re.compile(r"```sql\s*(.*?)```", re.S | re.I)
_ANY_FENCE = re.compile(r"```\w*\s*(.*?)```", re.S)


def _extract_sql(text: str) -> str | None:
    m = _SQL_FENCE.search(text)
    if m:
        return m.group(1).strip()
    m = _ANY_FENCE.search(text)
    if m:
        return m.group(1).strip()
    stripped = text.strip()
    if re.match(r"(?i)^(select|with)\b", stripped):
        return stripped
    return None


def _normalize_value(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return round(v, 2)
    if isinstance(v, decimal.Decimal):
        return round(float(v), 2)
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    if isinstance(v, (list, tuple)):
        return str(sorted(_normalize_value(x) for x in v))
    if v is None:
        return None
    return str(v).strip().lower()


def _row_valueset(row) -> frozenset:
    return frozenset(_normalize_value(v) for v in row)


def _rows_match(predicted_rows, gold_rows) -> bool:
    """True iff every gold row can be matched to a distinct predicted row
    whose value set is a SUPERSET of it (via bipartite backtracking -- row
    counts here are small, at most ~20). Deliberately lenient about column
    labels/order/aliases and about the agent including extra descriptive
    columns (e.g. a workspace's name alongside its id): what matters is
    whether the agent's query surfaced the right values, not whether it
    matched the gold query's exact column list. Row *count* still must
    match, so a query that's missing a WHERE filter (extra rows) or an
    accidental DISTINCT/aggregation (missing rows) is still caught."""
    if len(predicted_rows) != len(gold_rows):
        return False
    pred_sets = [_row_valueset(r) for r in predicted_rows]
    gold_sets = [_row_valueset(r) for r in gold_rows]
    used = [False] * len(pred_sets)

    def backtrack(i):
        if i == len(gold_sets):
            return True
        for j, ps in enumerate(pred_sets):
            if not used[j] and gold_sets[i] <= ps:
                used[j] = True
                if backtrack(i + 1):
                    return True
                used[j] = False
        return False

    return backtrack(0)


def _execute(sql: str) -> tuple[list | None, str | None]:
    conn = psycopg2.connect(DSN)
    try:
        cur = conn.cursor()
        cur.execute("SET statement_timeout = '5s'")
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute(sql)
        rows = cur.fetchall()
        return rows, None
    except Exception as e:  # noqa: BLE001 - report to the scoreboard, don't crash the run
        return None, str(e)
    finally:
        conn.rollback()
        conn.close()


def _score_judgment(response_text: str, sql: str | None) -> tuple[bool, str]:
    """Case 6 only: correct = the agent surfaced the broken order_items ->
    orders relationship / empty table instead of confidently fabricating a
    join. Heuristic on the response prose (see _JUDGMENT_OK_PHRASES) --
    documented, not hidden: a real semantic judge is future work."""
    text = response_text.lower()
    hit = next((p for p in _JUDGMENT_OK_PHRASES if p in text), None)
    if hit:
        return True, f"surfaced the issue (matched phrase: {hit!r})"
    if sql and re.search(r"\border_items\b", sql, re.I):
        return False, "produced a query against order_items with no caveat in the response"
    return False, "no SQL and no acknowledgement of the broken relationship"


def run_case(task: dict, arm: str, schema_dump: str, mcp_config: Path, work_dir: Path) -> dict:
    if arm == "baseline":
        # Leading sentence is load-bearing, not decorative: pg_dump output
        # starts with "--" (SQL comment syntax), and `claude -p`'s arg
        # parser treats a positional argument starting with "--" as an
        # unknown option rather than the prompt text -- every baseline call
        # failed to even launch until this was added (see commit history).
        prompt = f"Here is the raw schema dump:\n\n{schema_dump}\n\nQuestion: {task['question']}"
        result = _run_claude(
            prompt, BASELINE_SYSTEM, tools_mode="none", mcp_config=None,
            cwd=work_dir,
            trajectory_path=_TRAJECTORIES / f"{task['id']}_baseline.jsonl",
        )
    else:
        result = _run_claude(
            task["question"], SOLUTION_SYSTEM, tools_mode="mcp_only", mcp_config=mcp_config,
            cwd=work_dir,
            trajectory_path=_TRAJECTORIES / f"{task['id']}_solution.jsonl",
        )

    sql = _extract_sql(result["text"])
    out = {"arm": arm, "response_text": result["text"], "sql": sql,
           "claude_is_error": result["is_error"]}

    if task["judgment"]:
        correct, why = _score_judgment(result["text"], sql)
        out.update(correct=correct, why=why)
        return out

    if not sql:
        out.update(correct=False, why="no SQL extracted from response", rows=None, error=None)
        return out

    rows, err = _execute(sql)
    if err:
        out.update(correct=False, why=f"execution error: {err}", rows=None, error=err)
        return out

    gold_rows, gold_err = _execute(task["reference_sql"])
    if gold_err:
        raise RuntimeError(f"gold reference_sql failed for case {task['id']}: {gold_err}")

    match = _rows_match(rows, gold_rows)
    out.update(correct=match, why="matches gold" if match else "result set differs from gold",
               rows=rows, gold_rows=gold_rows, error=None)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case", type=int, help="run only this case id (for iterating)")
    ap.add_argument("--arm", choices=["baseline", "solution"], help="run only this arm")
    ap.add_argument("--json", action="store_true", help="emit the full result JSON, not just the table")
    args = ap.parse_args()

    _TRAJECTORIES.mkdir(parents=True, exist_ok=True)
    tasks = _load_tasks()
    if args.case is not None:
        tasks = [t for t in tasks if t["id"] == args.case]
        if not tasks:
            sys.exit(f"no case with id {args.case}")

    print("[run_sql_eval] fetching schema dump for the baseline arm...", file=sys.stderr)
    schema_dump = _schema_dump()
    arms = [args.arm] if args.arm else ["baseline", "solution"]

    results = []
    with tempfile.TemporaryDirectory(prefix="stackatlas_eval_") as tmp:
        work_dir = Path(tmp)
        mcp_config = _mcp_config_path(work_dir)
        for task in tasks:
            for arm in arms:
                print(f"[run_sql_eval] case {task['id']} / {arm} ...", file=sys.stderr)
                r = run_case(task, arm, schema_dump, mcp_config, work_dir)
                r["id"] = task["id"]
                r["question"] = task["question"]
                results.append(r)

    if args.json:
        print(json.dumps(results, indent=2, default=str))
        return 0

    _print_scoreboard(tasks, results, arms)
    return 0


def _print_scoreboard(tasks, results, arms):
    by_case = {}
    for r in results:
        by_case.setdefault(r["id"], {})[r["arm"]] = r

    print(f"{'#':<3} {'baseline':<10} {'solution':<10} question")
    print("-" * 80)
    totals = {a: 0 for a in arms}
    n = 0
    for task in tasks:
        if task["id"] not in by_case:
            continue
        n += 1
        row = by_case[task["id"]]
        cells = []
        for a in arms:
            r = row.get(a)
            mark = "PASS" if (r and r["correct"]) else ("FAIL" if r else "-")
            if r and r["correct"]:
                totals[a] += 1
            cells.append(f"{mark:<10}")
        print(f"{task['id']:<3} " + " ".join(cells) + f" {task['question'][:50]}")

    print("-" * 80)
    for a in arms:
        print(f"{a}: {totals[a]}/{n} correct")


if __name__ == "__main__":
    raise SystemExit(main())
