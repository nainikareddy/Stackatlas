"""Generate `tasks.jsonl` — the RL task dataset.

One row per table plus one whole-database row. Each row pairs an *observation*
(the schema skeleton a policy sees) with a *reference* (the gold tags/status a
verifier scores against) and the *reward spec*. This is the portable artifact
an external RL trainer consumes: no StackAtlas code required to replay it, just
the tagger in taxonomy.py to score predictions.

    python -m evals.build_tasks            # writes evals/tasks.jsonl
"""
from __future__ import annotations

import json
from pathlib import Path

from .env import build_skeleton
from .labels import GOLD, GOLD_HEALTH
from .scorer import WEIGHTS

_ROOT = Path(__file__).resolve().parent.parent
_CATALOG = _ROOT / "mcp_server" / "catalog.json"
_OUT = Path(__file__).resolve().parent / "tasks.jsonl"


def build(catalog_path: Path = _CATALOG, out_path: Path = _OUT) -> int:
    catalog = json.loads(catalog_path.read_text())
    skeleton = build_skeleton(catalog)
    by_name = {t["name"]: t for t in skeleton["tables"]}

    rows = []
    for name, spec in GOLD.items():
        table = by_name.get(name)
        if table is None:
            continue
        neighbours = [e for e in skeleton["edges"] if name in (e.get("from"), e.get("to"))]
        rows.append({
            "task_id": f"vibeshop/{name}",
            "kind": "per_table",
            "observation": {"table": table, "edges": neighbours},
            "reference": {"tags": sorted(spec["tags"]), "status": spec["status"]},
            "reward": {"scheme": "0.6*tag_f1 + 0.4*status_match", "tagger": "evals.taxonomy.tag_issues"},
        })

    rows.append({
        "task_id": "vibeshop/__whole__",
        "kind": "whole_database",
        "observation": skeleton,
        "reference": {"health": GOLD_HEALTH,
                      "tables": {n: {"tags": sorted(s["tags"]), "status": s["status"]}
                                 for n, s in GOLD.items()}},
        "reward": {"scheme": "weighted composite, gated by self-verification",
                   "weights": WEIGHTS, "scorer": "evals.scorer.score"},
    })

    out_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return len(rows)


if __name__ == "__main__":
    n = build()
    print(f"wrote {n} tasks -> {_OUT.relative_to(_ROOT)}")
