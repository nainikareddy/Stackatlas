"""Reward function — turn a produced catalog into a scalar in [0, 1].

The composite reward is a weighted blend of four verifiable signals, gated by
self-verification:

    reward = valid_gate * ( 0.50 * issue_f1        # did it find the real flaws?
                          + 0.25 * status_accuracy # per-table health call
                          + 0.15 * health_reward   # global score within tolerance
                          + 0.10 * (1 - halluc)  ) # penalise invented columns

`valid_gate` is 0 when the catalog fails a structural invariant (see verify.py)
and 1 otherwise — a malformed catalog is worthless to a downstream agent no
matter how good its prose, so the reward says so.

Everything here is deterministic: same catalog in, same reward out. That is
the property an RL loop needs.
"""
from __future__ import annotations

from .labels import GOLD, GOLD_HEALTH, HEALTH_TOLERANCE
from .taxonomy import tag_issues
from .verify import verify

WEIGHTS = {"issue_f1": 0.50, "status_accuracy": 0.25, "health": 0.15, "hallucination": 0.10}


def _prf(pred: set, gold: set) -> tuple[float, float, float]:
    """precision, recall, f1 for two tag sets. Empty/empty is a perfect score."""
    if not pred and not gold:
        return 1.0, 1.0, 1.0
    tp = len(pred & gold)
    precision = tp / len(pred) if pred else (1.0 if not gold else 0.0)
    recall = tp / len(gold) if gold else (1.0 if not pred else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def _hallucination_rate(catalog: dict) -> float:
    """Fraction of tables whose extraction invented a column name.

    The pipeline is forbidden from inventing columns (the introspection step
    already knows the real ones). We can't recompute the true column set from a
    documented catalog alone, so this proxy flags the observable failure mode:
    a `flag=true` column with no doc, or a table documented with zero columns.
    verify.py catches the former structurally; here we score its density.
    """
    tables = catalog.get("tables", [])
    if not tables:
        return 1.0
    bad = 0
    for t in tables:
        cols = t.get("columns", [])
        if not cols:
            bad += 1
            continue
        if any(c.get("flag") and not (c.get("doc") or "").strip() for c in cols):
            bad += 1
    return bad / len(tables)


def score(catalog: dict, gold: dict = GOLD, gold_health: int = GOLD_HEALTH) -> dict:
    """Score a catalog against gold labels. Returns a reward breakdown dict."""
    violations = verify(catalog)
    valid = not violations

    by_name = {t.get("name"): t for t in catalog.get("tables", [])}

    # --- per-table issue tagging + status ---
    per_table = []
    f1s, status_hits = [], 0
    covered = 0
    for name, spec in gold.items():
        t = by_name.get(name)
        if t is None:
            per_table.append({"table": name, "present": False, "f1": 0.0, "status_ok": False})
            f1s.append(0.0)
            continue
        covered += 1
        pred_tags = tag_issues(t.get("issues", []))
        p, r, f1 = _prf(pred_tags, spec["tags"])
        status_ok = t.get("status") == spec["status"]
        status_hits += int(status_ok)
        f1s.append(f1)
        per_table.append({
            "table": name, "present": True,
            "gold_tags": sorted(spec["tags"]), "pred_tags": sorted(pred_tags),
            "precision": round(p, 3), "recall": round(r, 3), "f1": round(f1, 3),
            "gold_status": spec["status"], "pred_status": t.get("status"),
            "status_ok": status_ok,
        })

    n = len(gold)
    issue_f1 = sum(f1s) / n if n else 0.0
    status_accuracy = status_hits / n if n else 0.0

    # --- global health score reward (linear decay over the tolerance band) ---
    pred_health = catalog.get("healthScore", 0)
    err = abs(pred_health - gold_health)
    health_reward = max(0.0, 1.0 - err / HEALTH_TOLERANCE)

    halluc = _hallucination_rate(catalog)

    components = {
        "issue_f1": round(issue_f1, 4),
        "status_accuracy": round(status_accuracy, 4),
        "health": round(health_reward, 4),
        "hallucination": round(1 - halluc, 4),
    }
    weighted = sum(WEIGHTS[k] * components[k] for k in WEIGHTS)
    reward = round(weighted if valid else 0.0, 4)

    return {
        "reward": reward,
        "valid": valid,
        "valid_gate": 1 if valid else 0,
        "violations": violations,
        "components": components,
        "weights": WEIGHTS,
        "coverage": {"tables_scored": covered, "tables_expected": n},
        "health": {"predicted": pred_health, "gold": gold_health, "abs_error": err},
        "per_table": per_table,
    }


def format_report(result: dict) -> str:
    """Human-readable reward card."""
    lines = []
    lines.append(f"REWARD  {result['reward']:.3f}   (valid={result['valid']})")
    lines.append("-" * 52)
    for k, w in result["weights"].items():
        c = result["components"][k]
        lines.append(f"  {k:<16} {c:>6.3f}  × {w:<4}  = {c * w:.3f}")
    lines.append("-" * 52)
    h = result["health"]
    lines.append(f"  health: predicted {h['predicted']} vs gold {h['gold']} (err {h['abs_error']})")
    if result["violations"]:
        lines.append(f"  ! {len(result['violations'])} self-verification violation(s):")
        for v in result["violations"][:8]:
            lines.append(f"      - {v}")
    lines.append("")
    lines.append(f"  {'table':<24} {'F1':>5}  {'status':>16}  tags")
    for row in result["per_table"]:
        if not row["present"]:
            lines.append(f"  {row['table']:<24} {'MISS':>5}")
            continue
        st = f"{row['pred_status']}=={row['gold_status']}" if row["status_ok"] else f"{row['pred_status']}!={row['gold_status']}"
        miss = set(row["gold_tags"]) - set(row["pred_tags"])
        extra = set(row["pred_tags"]) - set(row["gold_tags"])
        note = ""
        if miss:
            note += f" missed={sorted(miss)}"
        if extra:
            note += f" extra={sorted(extra)}"
        lines.append(f"  {row['table']:<24} {row['f1']:>5.2f}  {st:>16} {note}")
    return "\n".join(lines)
