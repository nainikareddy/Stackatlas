"""StackAtlas step 1: introspect a Postgres DB into a catalog skeleton.

Usage:
    pip install psycopg2-binary
    python introspect.py "postgresql://user:pass@host:5432/dbname" > catalog_raw.json

Pulls tables, columns, enforced FKs, row estimates, and (where
pg_stat_user_tables is populated) read/write traffic. Then, without any LLM,
it derives the structural signals that make the downstream catalog useful:

  * soft edges   — columns that look like FKs but aren't enforced
                   (user_id, ownerId, uid, workspace_id ...)
  * broken edges — an *enforced* FK whose target table is deprecated/orphaned
                   while a newer sibling exists (e.g. order_items -> orders
                   when orders_v2 is the live table). This is StackAtlas's
                   flagship finding, and it's detectable from structure alone.
  * layout       — deterministic node positions so the dashboard graph renders
                   straight from pipeline output.

Output field names match schema/catalog.schema.json so docgen.py can enrich
this skeleton in place and the result is consumed unchanged by the dashboard
and the MCP server. Traffic is reported as `readsPerDay` / `writesPerDay`:
best-effort estimates derived from cumulative pg_stat counters (see
`--stats-window-days`).
"""
import argparse
import json
import sys

try:
    import psycopg2
except ImportError:  # pragma: no cover - deferred so the pure helpers stay importable
    psycopg2 = None

TABLES_SQL = """
SELECT c.relname AS table_name,
       COALESCE(s.n_live_tup, 0) AS approx_rows,
       COALESCE(s.seq_scan + s.idx_scan, 0) AS read_ops,
       COALESCE(s.n_tup_ins + s.n_tup_upd + s.n_tup_del, 0) AS write_ops
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
WHERE n.nspname = 'public' AND c.relkind = 'r'
ORDER BY c.relname;
"""

COLUMNS_SQL = """
SELECT table_name, column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;
"""

FKS_SQL = """
SELECT tc.table_name AS from_table,
       kcu.column_name AS from_column,
       ccu.table_name AS to_table,
       ccu.column_name AS to_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage ccu
  ON tc.constraint_name = ccu.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public';
"""

SOFT_FK_ALIASES = {
    "uid": "users", "user_id": "users", "ownerid": "users", "owner_id": "users",
    "workspace_id": "workspaces", "order_id": "orders_v2", "product_id": "products",
}


def infer_soft_edges(columns, fk_pairs, table_names):
    """Columns that look like FKs but aren't enforced: user_id, ownerId, uid..."""
    soft = []
    for (tbl, col, *_rest) in columns:
        key = col.lower().replace('"', "")
        target = SOFT_FK_ALIASES.get(key)
        if target and target in table_names and target != tbl:
            if (tbl, target) not in fk_pairs:
                soft.append({"from": tbl, "to": target, "enforced": False, "via": col})
    return soft


def mark_broken_edges(edges, tables_by_name):
    """Flag enforced FKs that point at a deprecated/orphaned table.

    Signal: a live sibling exists — `<target>_v2`, or (if the target ends in
    `_old`/`_legacy`) its de-suffixed base — AND that sibling carries at least
    as much write traffic as the target. The `_v2`/`_old` naming is the
    deprecation tell; the traffic comparison confirms which table is the live
    one, and stays correct on a freshly seeded DB where every table shows writes.
    That's the order_items -> orders (vs orders_v2) bug.
    """
    names = set(tables_by_name)
    for e in edges:
        if not e.get("enforced"):
            continue
        tgt = tables_by_name.get(e["to"])
        if not tgt:
            continue
        sibling = f"{e['to']}_v2"
        base = e["to"].rsplit("_", 1)[0]
        live_name = sibling if sibling in names else (base if base != e["to"] and base in names else None)
        if not live_name:
            continue
        live = tables_by_name[live_name]
        if tgt.get("writesPerDay", 0) <= live.get("writesPerDay", 0):
            e["broken"] = True
            e["note"] = f"FK targets deprecated table; live data is in {live_name}"
    return edges


def grid_layout(n, cols=4, x0=120, y0=90, dx=210, dy=150):
    """Deterministic node positions so the graph renders without a layout engine."""
    return [{"x": x0 + (i % cols) * dx, "y": y0 + (i // cols) * dy} for i in range(n)]


def build_catalog(table_rows, columns, fks, dbname, window_days):
    table_names = {t[0] for t in table_rows}
    fk_pairs = {(f[0], f[2]) for f in fks}
    positions = grid_layout(len(table_rows))

    tables = []
    for idx, (name, approx_rows, read_ops, write_ops) in enumerate(table_rows):
        cols = [
            {"name": c[1], "type": c[2], "nullable": c[3] == "YES", "default": c[4]}
            for c in columns if c[0] == name
        ]
        tables.append({
            "name": name,
            "rows": int(approx_rows),
            # cumulative counters -> rough per-day estimate over the stats window
            "readsPerDay": int(read_ops) // max(1, window_days),
            "writesPerDay": int(write_ops) // max(1, window_days),
            "orphanCandidate": read_ops == 0 and write_ops == 0,
            "pos": positions[idx],
            "columns": cols,
        })

    tables_by_name = {t["name"]: t for t in tables}
    edges = [
        {"from": f[0], "to": f[2], "enforced": True, "via": f"{f[1]} -> {f[3]}"}
        for f in fks
    ]
    edges += infer_soft_edges(columns, fk_pairs, table_names)
    mark_broken_edges(edges, tables_by_name)

    enforced = sum(1 for e in edges if e["enforced"])
    return {
        "database": dbname,
        "tables": tables,
        "edges": edges,
        "stats": {
            "tables": len(tables),
            "columns": len(columns),
            "fkCoverage": round(enforced / len(edges), 2) if edges else 1.0,
            "orphans": sum(t["orphanCandidate"] for t in tables),
        },
    }


def main():
    ap = argparse.ArgumentParser(description="Introspect a Postgres DB into a catalog skeleton")
    ap.add_argument("dsn", help="postgres connection string")
    ap.add_argument("--stats-window-days", type=int, default=1,
                    help="divide cumulative pg_stat counters by this to estimate per-day traffic")
    args = ap.parse_args()

    if psycopg2 is None:
        sys.exit("psycopg2 not installed — run: pip install psycopg2-binary")
    try:
        conn = psycopg2.connect(args.dsn)
    except psycopg2.Error as e:
        sys.exit(f"could not connect: {e}")

    try:
        cur = conn.cursor()
        cur.execute(TABLES_SQL); table_rows = cur.fetchall()
        cur.execute(COLUMNS_SQL); columns = cur.fetchall()
        cur.execute(FKS_SQL); fks = cur.fetchall()
    finally:
        conn.close()

    dbname = args.dsn.rsplit("/", 1)[-1]
    catalog = build_catalog(table_rows, columns, fks, dbname, args.stats_window_days)
    json.dump(catalog, sys.stdout, indent=2, default=str)


if __name__ == "__main__":
    main()
