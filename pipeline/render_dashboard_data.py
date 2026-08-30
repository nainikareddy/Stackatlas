"""Regenerate data/catalog.js from mcp_server/catalog.json.

The dashboard (app/, components/) reads data/catalog.js as a bundled JS
module -- no server, no fetch, zero-setup demo per the README. That's a
deliberate simplification for the "npm install && npm run dev" quickstart.
But data/catalog.js was previously hand-maintained separately from the
pipeline's actual output, and the two drifted: the dashboard was showing a
healthScore and issue set from a stale, pre-seed-hardening run while the
real catalog (mcp_server/catalog.json, what the MCP server and evals use)
had moved on. That directly contradicted the README's "one catalog, one
schema contract" claim.

This script is the fix: data/catalog.js is now a generated artifact, not a
hand-authored one. Run it after any `python pipeline/docgen.py` run that
should also update the dashboard.

    python pipeline/render_dashboard_data.py

The canned agentAnswers Q&A block (narrative copy for the AgentConsole
demo panel) is NOT derivable from the catalog -- it's kept as a small
hand-authored constant below and re-emitted as-is, except for the one
answer that quotes the live health score, which is filled in from the
real catalog so it can't drift again either.
"""
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_CATALOG_JSON = _ROOT / "mcp_server" / "catalog.json"
_OUT = _ROOT / "data" / "catalog.js"

# Column/edge/table fields the dashboard (app/page.js, components/*.js)
# actually reads. mcp_server/catalog.json carries extra fields (nullable,
# default, primaryKey, sampleValues, orphanCandidate, via, ...) that the UI
# never touches -- dropped here to keep the bundled JS lean, not because
# they're wrong.
_TABLE_KEYS = ["name", "rows", "status", "pos", "readsPerDay", "writesPerDay", "doc", "issues"]
_COLUMN_KEYS = ["name", "type", "doc", "flag"]
_EDGE_KEYS = ["from", "to", "enforced", "broken", "note"]

# Hand-authored narrative Q&A for the AgentConsole demo panel (a scripted
# keyword-matcher, not live MCP -- see components/AgentConsole.js). Kept
# separate from the catalog because it's presentation copy, not derived
# data; {health} is filled in from the real catalog below so the one
# number it quotes can't go stale again.
_AGENT_ANSWERS_TEMPLATE = [
    {
        "match": ["status", "orders_v2"],
        "q": "What does orders_v2.status mean?",
        "a": "orders_v2.status uses magic single-character values: 'p' = pending, 'c' = complete, 'x' = cancelled, 'r' = refunded. There is no CHECK constraint — values are enforced only in app code. Note: this is one of THREE status vocabularies in this schema (legacy orders uses full words like 'completed'; payments uses Stripe's 'succeeded'/'refunded'). For revenue, filter status = 'c'.",
    },
    {
        "match": ["drop", "safe"],
        "q": "Which tables are safe to drop?",
        "a": "Two candidates. (1) tmp_backfill_20250811 — empty scratch table from a one-off script, unreferenced, drop immediately. (2) product_catalog_old — zero reads in 90 days, superseded by products; archive then drop. NOT safe: legacy `orders` — it looks dead (0 writes) but order_items.order_id still holds an enforced FK to it. Re-point that FK to orders_v2 first.",
    },
    {
        "match": ["revenue"],
        "q": "Where does revenue come from?",
        "a": "Revenue lives in orders_v2.amount_cents filtered to status='c' (complete), cross-checked against payments.amount_cents where state='succeeded'. Caveats: amounts are in cents (legacy orders used dollar numerics — don't union them naively), refunds appear as status='r' in orders_v2 AND state='refunded' in payments, and the payments↔orders_v2 join is unenforced (no FK), so expect stragglers.",
    },
    {
        "match": ["join", "analytics", "users"],
        "q": "How do I join analytics_events to users?",
        "a": "analytics_events.uid is users.id under a drifted name (no FK). Join: analytics_events.uid = users.id. Timestamp caution: analytics_events.ts is unix epoch seconds, so use to_timestamp(ts) before comparing against timestamptz columns like users.created_at.",
    },
    {
        "match": ["order_items", "empty"],
        "q": "Why is order_items empty?",
        "a": "order_items.order_id has an enforced FK to the DEPRECATED orders table, not orders_v2. Inserts with v2 order ids violate the constraint, so app code worked around it by stuffing line items into orders_v2.meta. Fix: re-point the FK to orders_v2, backfill from meta, then delete the workaround. This is the highest-priority integrity bug in the schema.",
    },
    {
        "match": ["health", "worst", "risk"],
        "q": "What are the biggest risks in this schema?",
        "a": "Health score {health}/100. Top risks: (1) order_items FK points at a deprecated table — line-item data is hiding in a jsonb blob; (2) FK coverage is {fk_pct}% — several tables have unenforced joins; (3) multiple competing status vocabularies invite mis-filtered revenue queries; (4) users.email has no unique index; (5) stripe_events grows unboundedly with no retention policy.",
    },
]


def _js_string(s: str) -> str:
    return json.dumps(s)  # JSON string escaping is a valid JS string literal


def _render_column(c: dict) -> str:
    parts = [f'name: {_js_string(c["name"])}', f'type: {_js_string(c["type"])}',
              f'doc: {_js_string(c.get("doc", ""))}']
    if c.get("flag"):
        parts.append("flag: true")
    return "{ " + ", ".join(parts) + " }"


def _render_table(t: dict) -> str:
    cols = ",\n        ".join(_render_column(c) for c in t["columns"])
    issues = ", ".join(_js_string(i) for i in t.get("issues", []))
    return f"""    {{
      name: {_js_string(t["name"])}, rows: {t["rows"]}, status: {_js_string(t["status"])}, pos: {{ x: {t["pos"]["x"]}, y: {t["pos"]["y"]} }},
      readsPerDay: {t["readsPerDay"]}, writesPerDay: {t["writesPerDay"]},
      doc: {_js_string(t.get("doc", ""))},
      issues: [{issues}],
      columns: [
        {cols}
      ],
    }}"""


def _render_edge(e: dict) -> str:
    parts = [f'from: {_js_string(e["from"])}', f'to: {_js_string(e["to"])}',
              f'enforced: {"true" if e.get("enforced") else "false"}']
    if e.get("broken"):
        parts.append("broken: true")
    if e.get("note"):
        parts.append(f'note: {_js_string(e["note"])}')
    return "{ " + ", ".join(parts) + " }"


def render(catalog: dict, generated_at: str) -> str:
    tables_js = ",\n".join(_render_table(t) for t in catalog["tables"])
    edges_js = ",\n    ".join(_render_edge(e) for e in catalog.get("edges", []))
    health = catalog.get("healthScore", 0)
    fk_pct = round(catalog.get("stats", {}).get("fkCoverage", 0) * 100)
    answers_js = []
    for a in _AGENT_ANSWERS_TEMPLATE:
        text = a["a"].format(health=health, fk_pct=fk_pct)
        match = ", ".join(_js_string(m) for m in a["match"])
        answers_js.append(
            f'  {{\n    match: [{match}],\n    q: {_js_string(a["q"])},\n    a: {_js_string(text)},\n  }}'
        )

    stats = catalog.get("stats", {})
    answers_block = ",\n".join(answers_js)
    return f"""// StackAtlas catalog — GENERATED from mcp_server/catalog.json by
// pipeline/render_dashboard_data.py. Do not hand-edit; re-run the script
// after regenerating the catalog so the dashboard and the MCP server never
// tell two different stories again.

export const catalog = {{
  database: {_js_string(catalog.get("database", ""))},
  generatedAt: {_js_string(generated_at)},
  healthScore: {health},
  stats: {{ tables: {stats.get("tables", 0)}, columns: {stats.get("columns", 0)}, fkCoverage: {stats.get("fkCoverage", 0)}, docCoverage: {stats.get("docCoverage", 0)}, orphans: {stats.get("orphans", 0)} }},
  tables: [
{tables_js}
  ],
  edges: [
    {edges_js}
  ],
}};

// Canned agent answers — identical in substance to what the MCP server
// returns, so the UI console and a live Claude-over-MCP session tell the
// same story. Hand-authored narrative copy (pipeline/render_dashboard_data.py
// docstring), not derived from the catalog, except the health/FK-coverage
// figures quoted below, which are filled in from the real catalog.
export const agentAnswers = [
{answers_block},
];
"""


def main() -> int:
    if not _CATALOG_JSON.exists():
        sys.exit(f"{_CATALOG_JSON} not found — run the pipeline first (make pipeline)")
    catalog = json.loads(_CATALOG_JSON.read_text())
    import datetime
    generated_at = catalog.get("generatedAt") or datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _OUT.write_text(render(catalog, generated_at))
    print(f"wrote {_OUT} from {_CATALOG_JSON} "
          f"(healthScore={catalog.get('healthScore')}, tables={len(catalog['tables'])})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
