"""Read-only ad-hoc SQL tool for the db_access eval arm (see run_sql_eval.py).

The whole point of this arm is the devil's-advocate question: if an agent
just has a plain read-only connection and is told to explore first, does it
get StackAtlas's advantage for free -- SELECT DISTINCT on a status column,
a look at information_schema, a peek at pg_stat_user_tables -- without any
pre-built catalog at all? This is that connection: any SQL, executed in a
read-only transaction with a timeout, nothing pre-computed or hand-fed.

    python3 query_db.py "SELECT DISTINCT status FROM orders_v2"

Always rolled back, even for a SELECT, so a mistaken write attempt fails
loudly (`SET TRANSACTION READ ONLY`) rather than silently persisting.
"""
import os
import sys

import psycopg2

DSN = os.environ.get("DSN", "postgresql://stackatlas:stackatlas@localhost:5433/vibeshop")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: query_db.py \"<SQL>\"", file=sys.stderr)
        return 2
    sql = sys.argv[1]
    conn = psycopg2.connect(DSN)
    try:
        cur = conn.cursor()
        cur.execute("SET statement_timeout = '5s'")
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute(sql)
        if cur.description:
            cols = [d.name for d in cur.description]
            print(" | ".join(cols))
            print("-" * 40)
            rows = cur.fetchmany(200)
            for row in rows:
                print(" | ".join(str(v) for v in row))
            if cur.rowcount and cur.rowcount > 200:
                print(f"... ({cur.rowcount} rows total, showing first 200)")
        else:
            print("OK (no rows returned)")
        return 0
    except Exception as e:  # noqa: BLE001 - surface any DB error to the agent, don't crash the tool
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    finally:
        conn.rollback()
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
