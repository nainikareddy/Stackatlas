"""Gold labels for the `vibeshop` demo schema — the answer key.

Each table maps to the set of canonical issue tags a correct catalog MUST
surface, plus the expected health status. These were authored by hand from
`db/seed.sql`, where every flaw is deliberate and known, which is exactly why
vibeshop works as an eval fixture: the ground truth is knowable.

`GOLD_HEALTH` is the reference database health score (0-100). The scorer
rewards predictions within a tolerance band rather than demanding an exact
match, because the score is a heuristic roll-up, not a hard invariant.

To add a new fixture DB: introspect it, label it here (or in a sibling
module), and it drops straight into the eval + RL environment.
"""
from __future__ import annotations

from .taxonomy import TAG_SET

# table -> {"tags": {...}, "status": "healthy|warning|critical"}
GOLD: dict[str, dict] = {
    "users":                 {"status": "healthy",  "tags": {"no_unique_index"}},
    "user_prefs":            {"status": "warning",  "tags": {"missing_fk", "undocumented_jsonb", "no_primary_key"}},
    "workspaces":            {"status": "warning",  "tags": {"missing_fk", "naming_drift"}},
    "orders":                {"status": "critical", "tags": {"deprecated_table", "zero_writes"}},
    "orders_v2":             {"status": "warning",  "tags": {"missing_fk", "magic_values"}},
    "order_items":           {"status": "critical", "tags": {"broken_fk", "empty_but_hot"}},
    "products":              {"status": "healthy",  "tags": set()},
    "product_catalog_old":   {"status": "critical", "tags": {"orphan_table", "money_as_float"}},
    "payments":              {"status": "warning",  "tags": {"missing_fk", "status_vocab_drift"}},
    "stripe_events":         {"status": "warning",  "tags": {"unbounded_growth", "undocumented_jsonb"}},
    "sessions":              {"status": "healthy",  "tags": set()},
    "analytics_events":      {"status": "warning",  "tags": {"missing_fk", "naming_drift", "epoch_timestamp"}},
    "feature_flags":         {"status": "healthy",  "tags": set()},
    "tmp_backfill_20250811": {"status": "critical", "tags": {"orphan_table"}},
}

GOLD_HEALTH = 61                # reference health score for vibeshop
HEALTH_TOLERANCE = 15          # points of slack before health reward decays to 0

# Relationships that a correct catalog must flag as broken (enforced FK whose
# target is deprecated/wrong). Used by the broken-FK detection eval.
GOLD_BROKEN_EDGES = {("order_items", "orders")}


def _validate_labels() -> None:
    """Fail loudly if a label uses a tag outside the taxonomy."""
    for table, spec in GOLD.items():
        bad = spec["tags"] - TAG_SET
        assert not bad, f"{table}: unknown tags {bad}"
        assert spec["status"] in {"healthy", "warning", "critical"}, table


_validate_labels()
