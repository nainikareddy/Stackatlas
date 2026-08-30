"""StackAtlas MCP server — the context layer AI agents actually query.

Usage:
    pip install "mcp[cli]"
    python server.py                      # stdio transport

Claude Desktop / Claude Code config:
    { "mcpServers": { "stackatlas": {
        "command": "python",
        "args": ["/abs/path/to/mcp_server/server.py"] } } }

Then ask Claude: "What does orders_v2.status mean?" — it answers from the
catalog instead of guessing. That moment IS the demo.
"""
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

CATALOG_PATH = Path(__file__).parent / "catalog.json"
mcp = FastMCP("stackatlas")


def load():
    with open(CATALOG_PATH) as f:
        return json.load(f)


def find_table(catalog, name):
    for t in catalog["tables"]:
        if t["name"].lower() == name.lower():
            return t
    return None


@mcp.tool()
def search_tables(query: str) -> str:
    """Search the database catalog for tables matching a keyword.
    Returns table names, summaries, and health status."""
    catalog = load()
    q = query.lower()
    hits = []
    for t in catalog["tables"]:
        haystack = " ".join(
            [t["name"], t.get("doc", "")]
            + [c["name"] for c in t["columns"]]
            + t.get("issues", [])
        ).lower()
        if q in haystack:
            hits.append({"table": t["name"], "status": t["status"],
                         "rows": t["rows"], "doc": t.get("doc", "")})
    return json.dumps(hits or {"note": f"no tables matched '{query}'"},
                      indent=2)


@mcp.tool()
def get_table_context(tables: list[str]) -> str:
    """Full context for one or more tables: purpose, columns with docs,
    known issues, traffic, and relationships. Pass every table you expect
    to need for the query in ONE call (e.g. ["orders_v2", "workspaces"])
    rather than calling this once per table -- it's the same data either
    way, just fewer round trips. Call before writing queries against any
    of them."""
    catalog = load()
    names = [x["name"] for x in catalog["tables"]]
    result = {}
    for table in tables:
        t = find_table(catalog, table)
        if not t:
            result[table] = {"error": f"unknown table '{table}'", "available": names}
            continue
        edges = [e for e in catalog["edges"]
                 if table.lower() in (e["from"].lower(), e["to"].lower())]
        result[table] = {**t, "relationships": edges}
    return json.dumps(result, indent=2)


@mcp.tool()
def explain_column(table: str, column: str) -> str:
    """Explain a single column: meaning, type, gotchas (magic values, unit
    conventions, unenforced relationships)."""
    catalog = load()
    t = find_table(catalog, table)
    if not t:
        return json.dumps({"error": f"unknown table '{table}'"})
    for c in t["columns"]:
        if c["name"].lower() == column.lower():
            return json.dumps({"table": t["name"], **c,
                               "table_issues": t.get("issues", [])}, indent=2)
    return json.dumps({"error": f"no column '{column}' on '{table}'",
                       "columns": [c["name"] for c in t["columns"]]})


@mcp.tool()
def list_broken_relationships() -> str:
    """List EVERY foreign key in the whole schema that points at a
    deprecated or wrong table — the silent joins that make an agent write
    correct-looking SQL against dead data. This is schema-wide, not
    per-table: call it once, up front, before writing any query that joins
    tables, rather than once per join you're considering."""
    catalog = load()
    broken = [
        {"from": e["from"], "to": e["to"],
         "via": e.get("via"), "note": e.get("note", "FK targets a deprecated table")}
        for e in catalog.get("edges", []) if e.get("broken")
    ]
    return json.dumps(broken or {"note": "no broken relationships detected"}, indent=2)


@mcp.tool()
def get_health_report() -> str:
    """Database health report: score, orphaned tables, missing FKs,
    naming drift, and the highest-priority integrity risks."""
    catalog = load()
    findings = []
    for t in catalog["tables"]:
        for issue in t.get("issues", []):
            findings.append({"table": t["name"], "severity": t["status"],
                             "issue": issue})
    findings.sort(key=lambda f: 0 if f["severity"] == "critical" else 1)
    return json.dumps({
        "healthScore": catalog.get("healthScore"),
        "stats": catalog.get("stats"),
        "findings": findings,
    }, indent=2)


if __name__ == "__main__":
    mcp.run()
