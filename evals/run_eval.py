"""Score a catalog and print a reward card.

    python -m evals.run_eval                       # score the shipped demo catalog
    python -m evals.run_eval --catalog path.json   # score any catalog
    python -m evals.run_eval --baseline empty       # show reward floor
    python -m evals.run_eval --threshold 0.8        # CI gate: exit 1 if below

No network, no API key. Reads a produced catalog off disk and compares it to
the gold labels for vibeshop.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from .scorer import score, format_report

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT = _ROOT / "mcp_server" / "catalog.json"


def _degrade(catalog: dict, baseline: str) -> dict:
    """Build a deliberately bad catalog to demonstrate the reward separates signal."""
    c = copy.deepcopy(catalog)
    if baseline == "empty":
        # strip all semantics: no issues, everything "healthy"
        for t in c["tables"]:
            t["issues"] = []
            t["status"] = "healthy"
            for col in t["columns"]:
                col.pop("flag", None)
        c["healthScore"] = 100
    elif baseline == "half":
        # drop issues from every other table
        for i, t in enumerate(c["tables"]):
            if i % 2:
                t["issues"] = []
                t["status"] = "healthy"
    return c


def main() -> int:
    ap = argparse.ArgumentParser(description="StackAtlas catalog eval")
    ap.add_argument("--catalog", type=Path, default=_DEFAULT)
    ap.add_argument("--baseline", choices=["empty", "half"], help="degrade the catalog first")
    ap.add_argument("--threshold", type=float, default=None, help="exit 1 if reward below this")
    ap.add_argument("--json", action="store_true", help="emit raw JSON breakdown")
    args = ap.parse_args()

    catalog = json.loads(args.catalog.read_text())
    if args.baseline:
        catalog = _degrade(catalog, args.baseline)

    result = score(catalog)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_report(result))

    if args.threshold is not None and result["reward"] < args.threshold:
        print(f"\nFAIL: reward {result['reward']:.3f} < threshold {args.threshold}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
