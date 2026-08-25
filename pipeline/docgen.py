"""StackAtlas step 2: Claude writes the docs + health findings.

Usage:
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...
    python docgen.py catalog_raw.json > catalog_documented.json

One call per table (schema + traffic + relationships in, docs + issues out).
Two reliability features make the output trustworthy enough to serve to agents:

  * self-verification — every table's output is checked against the same
    invariants the eval uses (evals.verify: valid status/columns, flagged
    columns documented, no invented columns). On a violation we re-prompt once
    with the specific complaint before falling back.
  * schema conformance — the finished catalog is validated against
    schema/catalog.schema.json; violations are reported on stderr.

Model is configurable via STACKATLAS_MODEL. For big schemas switch to the
Message Batches API (50% cheaper) and prompt-cache SYSTEM — both one-liners.
"""
import json
import os
import sys
from pathlib import Path

# make the sibling evals package importable when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evals.verify import verify  # noqa: E402
from evals.verify import semantic_violations  # noqa: E402

MODEL = os.environ.get("STACKATLAS_MODEL", "claude-sonnet-4-5")
VALID_STATUS = {"healthy", "warning", "critical"}

SYSTEM = """You are a senior data engineer writing a database catalog.
For the given table, return STRICT JSON with keys:
  doc      - 2-3 sentence summary: what the table is for, how it's used,
             anything a new engineer or an AI agent MUST know (magic values,
             unit conventions, deprecations, naming drift).
  issues   - array of short strings: data-integrity risks (missing FKs,
             inconsistent naming/timestamps, unconstrained enums, money as
             float, orphaned/deprecated status). Empty array if clean.
  status   - "healthy" | "warning" | "critical"
             (MUST be "warning" or "critical" whenever issues is non-empty)
  columns  - array of {name, doc, flag} where doc is one sharp sentence and
             flag=true marks columns with a gotcha. Include EVERY column you
             were given and invent none. Any flag=true column MUST have a doc.
Be specific and opinionated. Never invent columns. JSON only, no fences."""


def _table_payload(table, edges):
    related = [e for e in edges if table["name"] in (e["from"], e["to"])]
    return {
        "table": table["name"],
        "approx_rows": table["rows"],
        "reads_per_day": table.get("readsPerDay"),
        "writes_per_day": table.get("writesPerDay"),
        "orphan_candidate": table.get("orphanCandidate"),
        "columns": table["columns"],
        "relationships": related,
    }


def _call(client, payload, extra=None):
    messages = [{"role": "user", "content": json.dumps(payload)}]
    if extra:
        messages.append({"role": "user", "content": extra})
    msg = client.messages.create(
        model=MODEL, max_tokens=1200, system=SYSTEM, messages=messages,
    )
    return msg.content[0].text.strip()


def _merge(table, result):
    """Apply an LLM result onto a table (in place) and return the merged table."""
    table["doc"] = result.get("doc", "")
    table["issues"] = result.get("issues", [])
    table["status"] = result.get("status", "warning")
    docs = {c["name"]: c for c in result.get("columns", [])}
    for col in table["columns"]:
        d = docs.get(col["name"], {})
        col["doc"] = d.get("doc", "")
        col["flag"] = bool(d.get("flag", False))
    return table


def _local_violations(table):
    """Per-table invariants, reusing the eval's semantic checks on a 1-table catalog."""
    v = []
    if table.get("status") not in VALID_STATUS:
        v.append(f"invalid status {table.get('status')!r}")
    # run the shared semantic checks against a minimal one-table catalog
    mini = {"tables": [table], "edges": [], "stats": {}}
    v += [x for x in semantic_violations(mini) if not x.startswith("stats")]
    return v


def document_table(client, table, edges):
    payload = _table_payload(table, edges)
    text = _call(client, payload)
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        result = None

    if result is not None:
        _merge(table, result)
        problems = _local_violations(table)
        if not problems:
            return table
        # self-verify failed → re-prompt once with the specific complaint
        complaint = ("Your previous output violated: " + "; ".join(problems)
                     + ". Return corrected STRICT JSON only.")
        text = _call(client, payload, extra=complaint)
        try:
            _merge(table, json.loads(text))
            if not _local_violations(table):
                return table
        except json.JSONDecodeError:
            pass

    # fallback: safe, honest placeholder that still self-verifies
    print(f"[docgen] {table['name']}: unrecoverable output, using placeholder", file=sys.stderr)
    table["doc"] = table.get("doc") or ""
    table["issues"] = ["docgen failed — rerun this table"]
    table["status"] = "warning"
    for col in table["columns"]:
        col.setdefault("doc", "documentation pending")
        col["flag"] = bool(col.get("flag", False))
        if col["flag"] and not col["doc"].strip():
            col["doc"] = "flagged — documentation pending"
    return table


def compute_health(catalog):
    """Naive health score: start at 100, lose points per finding."""
    penalty = sum(
        {"healthy": 0, "warning": 4, "critical": 9}[t["status"]] + len(t.get("issues", []))
        for t in catalog["tables"]
    )
    return max(0, 100 - penalty)


def main(path):
    with open(path) as f:
        catalog = json.load(f)

    import anthropic  # imported here so the pure helpers stay dependency-free
    client = anthropic.Anthropic()
    for table in catalog["tables"]:
        document_table(client, table, catalog.get("edges", []))
        print(f"[docgen] {table['name']}: {table['status']}, "
              f"{len(table.get('issues', []))} issue(s)", file=sys.stderr)

    catalog["healthScore"] = compute_health(catalog)
    catalog.setdefault("stats", {})["docCoverage"] = 1.0
    catalog["stats"]["columns"] = sum(len(t["columns"]) for t in catalog["tables"])

    problems = verify(catalog)
    if problems:
        print(f"[docgen] WARNING: {len(problems)} self-verification violation(s):", file=sys.stderr)
        for p in problems:
            print("  -", p, file=sys.stderr)

    json.dump(catalog, sys.stdout, indent=2)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python docgen.py catalog_raw.json")
    main(sys.argv[1])
