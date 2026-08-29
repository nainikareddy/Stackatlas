"""Unit tests for the pure helpers in run_sql_eval.py -- no DB, no claude CLI.

Two of these (SQL extraction, row matching) were written specifically because
the first real run of the eval found live bugs in them: the CLI arg parser
choking on a pg_dump-shaped prompt, and an exact-match row comparison
penalizing agents for correct answers with extra descriptive columns.
"""
from __future__ import annotations

import decimal

from evals.run_sql_eval import (
    _extract_sql, _normalize_value, _row_valueset, _rows_match, _score_judgment,
)


def test_extract_sql_from_fenced_block():
    text = "Here you go:\n```sql\nSELECT 1;\n```\nDone."
    assert _extract_sql(text) == "SELECT 1;"


def test_extract_sql_from_bare_fence():
    text = "```\nSELECT 2;\n```"
    assert _extract_sql(text) == "SELECT 2;"


def test_extract_sql_from_unfenced_select():
    text = "  SELECT 3;  "
    assert _extract_sql(text) == "SELECT 3;"


def test_extract_sql_returns_none_for_prose():
    text = "I can't answer this reliably given the schema."
    assert _extract_sql(text) is None


def test_normalize_value_rounds_numerics_consistently():
    assert _normalize_value(decimal.Decimal("846.001")) == 846.0
    assert _normalize_value(1.005) == 1.0 or _normalize_value(1.005) == 1.01  # float rounding is inherently fuzzy
    assert _normalize_value(True) is True
    assert _normalize_value(None) is None
    assert _normalize_value(" Maya ") == "maya"


def test_normalize_value_hashes_list_columns():
    # postgres arrays (e.g. array_agg) come back as Python lists, which
    # aren't hashable -- must not crash building a frozenset row.
    v = _normalize_value([3, 1, 2])
    assert isinstance(v, str)


def test_rows_match_exact():
    assert _rows_match([[846.0]], [[846.0]])


def test_rows_match_allows_extra_columns():
    # the agent's row is a superset of gold's -- e.g. it included a
    # workspace name alongside the id/revenue gold actually asked for.
    predicted = [[1, "Drift Labs", 607.0], [2, "Lee Sandbox", 49.0]]
    gold = [[1, 607.0], [2, 49.0]]
    assert _rows_match(predicted, gold)


def test_rows_match_ignores_row_and_column_order():
    predicted = [[2, 49.0], [1, 607.0]]
    gold = [[1, 607.0], [2, 49.0]]
    assert _rows_match(predicted, gold)


def test_rows_match_rejects_wrong_row_count():
    # missing a WHERE filter (too many rows) or an accidental DISTINCT/
    # aggregation (too few) must still fail.
    predicted = [[1, 607.0], [2, 49.0], [3, 190.0]]
    gold = [[1, 607.0], [2, 49.0]]
    assert not _rows_match(predicted, gold)


def test_rows_match_rejects_wrong_values():
    predicted = [[1, 99.0]]
    gold = [[1, 607.0]]
    assert not _rows_match(predicted, gold)


def test_rows_match_requires_distinct_assignment():
    # two gold rows can't both be satisfied by the same predicted row even
    # if that row happens to be a superset of each individually.
    predicted = [[1, 2, 3]]
    gold = [[1], [2]]
    assert not _rows_match(predicted, gold)


def test_score_judgment_credits_caveat():
    correct, why = _score_judgment(
        "order_items is empty and its FK targets the deprecated orders table, "
        "not orders_v2 -- there's no reliable line-item data here.",
        None,
    )
    assert correct
    assert "surfaced" in why


def test_score_judgment_flags_uncaveated_join():
    correct, _ = _score_judgment(
        "Here is the query.",
        "SELECT * FROM order_items WHERE order_id = 5",
    )
    assert not correct


def test_row_valueset_is_a_frozenset():
    assert _row_valueset([1, "a", None]) == frozenset({1, "a", None})
