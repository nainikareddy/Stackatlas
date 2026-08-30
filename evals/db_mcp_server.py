"""Single-tool MCP server for the db_access eval arm (see run_sql_eval.py).

Exists to replace a Bash-glob permission pattern (`Bash(python3
evals/query_db.py *)`) with an exact-name-matched MCP tool
(`mcp__vibeshop_db__run_sql`). The glob had to pattern-match arbitrary
shell text the agent itself wrote -- any quoting/chaining variation either
silently auto-denied in headless mode (a spurious FAIL unrelated to the
agent's reasoning) or depended on ambient venv state inherited through the
Bash tool. A named tool has neither failure mode: the interface is fixed
and its subprocess is launched with sys.executable directly, exactly like
mcp_server/server.py.

The read-only-transaction logic itself (statement_timeout, SET TRANSACTION
READ ONLY, guaranteed rollback) is unchanged from query_db.py's `main()`
-- this only changes how the capability is exposed to the agent, not what
the capability does.

Usage: python db_mcp_server.py   # stdio transport
"""
import os

import psycopg2
from mcp.server.fastmcp import FastMCP

DSN = os.environ.get("DSN", "postgresql://stackatlas:stackatlas@localhost:5433/vibeshop")
mcp = FastMCP("vibeshop_db")


@mcp.tool()
def run_sql(query: str) -> str:
    """Run a single read-only SQL query against the live vibeshop database
    and return the result as a text table (first 200 rows). Use this to
    discover tables, columns, foreign keys (information_schema, pg_catalog)
    and to sample real values (SELECT DISTINCT ...) -- there is no schema
    dump or documentation provided; this is the only source of truth."""
    conn = psycopg2.connect(DSN)
    try:
        cur = conn.cursor()
        cur.execute("SET statement_timeout = '5s'")
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute(query)
        if not cur.description:
            return "OK (no rows returned)"
        cols = [d.name for d in cur.description]
        rows = cur.fetchmany(200)
        lines = [" | ".join(cols), "-" * 40]
        lines += [" | ".join(str(v) for v in row) for row in rows]
        if cur.rowcount and cur.rowcount > 200:
            lines.append(f"... ({cur.rowcount} rows total, showing first 200)")
        return "\n".join(lines)
    except Exception as e:  # noqa: BLE001 - surface any DB error to the agent, don't crash the tool
        return f"ERROR: {e}"
    finally:
        conn.rollback()
        conn.close()


if __name__ == "__main__":
    mcp.run()
