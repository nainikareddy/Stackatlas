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
#
# Re-authored after switching docgen's transport from the anthropic SDK to
# `claude -p` (see pipeline/docgen.py): the new call is noticeably more
# thorough per table, which surfaced several real, true findings the original
# labels didn't credit (e.g. products.sku has no unique constraint; users is
# the unenforced target of four different FKs, not just the source of one).
# Each addition below was checked against db/seed.sql, not just rubber-
# stamped from a docgen run — see the PR/commit description for the
# table-by-table reasoning. Some legitimate docgen imprecision remains
# uncorrected on purpose (e.g. occasional severity over-escalation, a
# speculative FK suggestion with no real target) because that's the eval
# correctly catching model imprecision, not a labeling gap.
GOLD: dict[str, dict] = {
    "users":                 {"status": "warning",  "tags": {"no_unique_index", "missing_fk", "naming_drift"}},
    "user_prefs":            {"status": "warning",  "tags": {"missing_fk", "undocumented_jsonb", "no_primary_key"}},
    "workspaces":            {"status": "warning",  "tags": {"missing_fk", "naming_drift"}},
    "orders":                {"status": "critical", "tags": {"deprecated_table", "zero_writes"}},
    "orders_v2":             {"status": "critical", "tags": {"missing_fk", "magic_values"}},
    "order_items":           {"status": "critical", "tags": {"broken_fk", "empty_but_hot", "missing_fk", "zero_writes"}},
    "products":              {"status": "warning",  "tags": {"missing_fk", "no_unique_index"}},
    "product_catalog_old":   {"status": "critical", "tags": {"orphan_table", "money_as_float", "no_primary_key"}},
    "payments":              {"status": "warning",  "tags": {"missing_fk", "status_vocab_drift", "no_unique_index"}},
    "stripe_events":         {"status": "warning",  "tags": {"unbounded_growth", "undocumented_jsonb"}},
    "sessions":              {"status": "warning",  "tags": {"zero_writes"}},
    "analytics_events":      {"status": "warning",  "tags": {"missing_fk", "naming_drift", "epoch_timestamp"}},
    "feature_flags":         {"status": "healthy",  "tags": set()},
    "tmp_backfill_20250811": {"status": "critical", "tags": {"orphan_table", "no_primary_key"}},
}

# compute_health() (pipeline/docgen.py) now averages penalty per table
# instead of summing across the whole catalog — the old sum saturated to 0
# for any schema past ~10-12 tables once docgen is thorough enough to find
# the real 2-7 issues per table vibeshop actually has, which made the score
# useless (see commit history). 38 is what a genuinely accurate, thorough
# catalog of this deliberately messy schema scores under the fixed formula —
# lower than the old 61, but a more honest number for a schema built to be
# this broken.
GOLD_HEALTH = 38                # reference health score for vibeshop
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
