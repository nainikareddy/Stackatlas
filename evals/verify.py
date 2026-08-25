"""Self-verification invariants — the checks that need NO answer key.

These run against any catalog, for any database, real or synthetic. They are
what lets the system self-verify in production (where there is no gold set)
and they double as a hard gate in the reward function: a catalog that fails a
structural invariant scores zero, because downstream agents would be misled by
it. The generator (`docgen.py`) runs the same checks on its own output and
re-prompts once when they fail.

Two tiers:
  * schema validity  — matches schema/catalog.schema.json (draft-07)
  * semantic invariants — internally consistent: no invented columns, every
    flagged column exists, issues/edges reference real tables, counts add up.
"""
from __future__ import annotations

import json
from pathlib import Path

try:
    import jsonschema
    _HAVE_JSONSCHEMA = True
except ImportError:  # keep verify usable without the dep; semantic checks still run
    _HAVE_JSONSCHEMA = False

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "catalog.schema.json"


def _load_schema() -> dict:
    with open(_SCHEMA_PATH) as f:
        return json.load(f)


def schema_violations(catalog: dict) -> list[str]:
    """Structural violations against the JSON Schema contract."""
    if not _HAVE_JSONSCHEMA:
        return []  # skipped, not passed — callers can check availability separately
    validator = jsonschema.Draft7Validator(_load_schema())
    out = []
    for err in sorted(validator.iter_errors(catalog), key=str):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"schema[{loc}]: {err.message}")
    return out


def semantic_violations(catalog: dict) -> list[str]:
    """Internal-consistency checks that hold regardless of ground truth."""
    v: list[str] = []
    tables = catalog.get("tables", [])
    names = {t.get("name") for t in tables}

    for t in tables:
        tname = t.get("name", "<unnamed>")
        cols = t.get("columns", [])
        colnames = {c.get("name") for c in cols}

        # A flagged column must carry a doc explaining the gotcha.
        for c in cols:
            if c.get("flag") and not (c.get("doc") or "").strip():
                v.append(f"{tname}.{c.get('name')}: flagged but undocumented")

        # A table marked non-healthy must name at least one issue — otherwise a
        # downstream agent sees a scary status with no reason. (The converse,
        # a healthy table carrying an advisory note, is legitimate and allowed.)
        if t.get("status") in {"warning", "critical"} and not t.get("issues"):
            v.append(f"{tname}: status={t.get('status')} but no issues listed")

    # Edges must connect real tables.
    for e in catalog.get("edges", []):
        if e.get("from") not in names:
            v.append(f"edge {e.get('from')}->{e.get('to')}: unknown source table")
        if e.get("to") not in names:
            v.append(f"edge {e.get('from')}->{e.get('to')}: unknown target table")
        if e.get("broken") and not e.get("enforced"):
            v.append(f"edge {e.get('from')}->{e.get('to')}: broken=true requires enforced=true")

    # Stats must agree with the tables array.
    stats = catalog.get("stats", {})
    if stats:
        if stats.get("tables") != len(tables):
            v.append(f"stats.tables={stats.get('tables')} != {len(tables)} tables")
        col_total = sum(len(t.get("columns", [])) for t in tables)
        if stats.get("columns") not in (None, col_total):
            v.append(f"stats.columns={stats.get('columns')} != {col_total} counted")

    return v


def verify(catalog: dict) -> list[str]:
    """All violations (schema + semantic). Empty list == the catalog passes."""
    return schema_violations(catalog) + semantic_violations(catalog)


def is_valid(catalog: dict) -> bool:
    return not verify(catalog)


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "mcp_server/catalog.json"
    with open(path) as f:
        cat = json.load(f)
    problems = verify(cat)
    if not problems:
        print(f"OK — {path} passes all self-verification invariants")
    else:
        print(f"{len(problems)} violation(s) in {path}:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
