"""Pipeline unit tests — no database, no network.

Covers the structural logic that runs before any LLM: soft-edge inference,
broken-FK detection, layout, and the docgen self-verification helpers. The
broken-FK case is StackAtlas's flagship finding, so it gets a dedicated test.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.introspect import build_catalog, mark_broken_edges, infer_soft_edges
from pipeline import docgen


# rows: (name, approx_rows, read_ops, write_ops)
ROWS = [
    ("orders", 2, 30, 2),          # legacy, low write traffic
    ("orders_v2", 5, 24600, 340),  # live
    ("order_items", 0, 8800, 0),
    ("users", 4, 18400, 120),
    ("workspaces", 2, 9200, 15),
]
COLUMNS = [
    ("order_items", "order_id", "bigint", "NO", None),
    ("order_items", "product_id", "bigint", "YES", None),
    ("orders_v2", "user_id", "bigint", "YES", None),
    ("workspaces", "ownerId", "bigint", "YES", None),
]
FKS = [("order_items", "order_id", "orders", "id")]  # enforced FK -> legacy table


def _catalog():
    return build_catalog(ROWS, COLUMNS, FKS, "vibeshop", window_days=1)


def test_flagship_broken_fk_detected():
    cat = _catalog()
    broken = [(e["from"], e["to"]) for e in cat["edges"] if e.get("broken")]
    assert ("order_items", "orders") in broken


def test_soft_edges_inferred():
    cat = _catalog()
    soft = {(e["from"], e["to"]) for e in cat["edges"] if not e["enforced"]}
    assert ("orders_v2", "users") in soft     # user_id -> users
    assert ("workspaces", "users") in soft     # ownerId -> users
    assert ("order_items", "orders_v2") in soft  # order_id alias points at live table


def test_no_false_positive_broken_fk():
    # a normal enforced FK to a live table with no _v2 sibling stays intact
    rows = [("users", 4, 100, 10), ("sessions", 3, 500, 40)]
    fks = [("sessions", "user_id", "users", "id")]
    cat = build_catalog(rows, [], fks, "db", 1)
    assert not any(e.get("broken") for e in cat["edges"])


def test_layout_and_field_names():
    cat = _catalog()
    assert all("pos" in t for t in cat["tables"])
    t0 = cat["tables"][0]
    assert {"readsPerDay", "writesPerDay"} <= set(t0)   # canonical schema names


def test_stats_window_scales_traffic():
    a = build_catalog(ROWS, COLUMNS, FKS, "db", 1)
    b = build_catalog(ROWS, COLUMNS, FKS, "db", 10)
    ra = next(t["readsPerDay"] for t in a["tables"] if t["name"] == "orders_v2")
    rb = next(t["readsPerDay"] for t in b["tables"] if t["name"] == "orders_v2")
    assert rb == ra // 10


# ---- docgen self-verification helpers (no anthropic import needed) ----------
def test_compute_health_penalises_findings():
    # penalty is averaged per table (not summed across the catalog) so the
    # score doesn't saturate to 0 once a thorough docgen pass finds several
    # real issues on every table of a larger schema — see compute_health().
    catalog = {"tables": [
        {"status": "healthy", "issues": []},
        {"status": "critical", "issues": ["a", "b"]},
    ]}
    avg_penalty = (0 + (9 + 2)) / 2
    assert docgen.compute_health(catalog) == round(100 - avg_penalty * 5)


def test_local_violations_flags_undocumented_flag():
    table = {"name": "t", "status": "warning", "issues": ["x"],
             "columns": [{"name": "c", "flag": True, "doc": ""}]}
    assert any("flagged" in v for v in docgen._local_violations(table))


def test_local_violations_flags_bad_status():
    table = {"name": "t", "status": "green", "issues": [], "columns": []}
    assert any("status" in v for v in docgen._local_violations(table))


def test_merge_applies_docs_and_flags():
    table = {"name": "t", "columns": [{"name": "a"}, {"name": "b"}]}
    docgen._merge(table, {"doc": "d", "issues": ["i"], "status": "warning",
                          "columns": [{"name": "a", "doc": "x", "flag": True}]})
    assert table["status"] == "warning" and table["doc"] == "d"
    assert table["columns"][0]["flag"] is True and table["columns"][1]["flag"] is False
