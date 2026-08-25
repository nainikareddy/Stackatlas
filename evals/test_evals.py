"""Self-verification in CI.

These tests are the project's own quality gate: they prove the shipped catalogs
are structurally valid, that the reward function actually separates a good
catalog from a degraded one (a reward that can't tell them apart is useless for
RL), and that the tagger maps prose onto the right tags.

    pytest evals/ -q
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from evals.scorer import score
from evals.verify import verify, is_valid
from evals.taxonomy import tag_issue, TAG_SET, TAGS, PHRASING
from evals.env import CatalogEnv, build_skeleton
from evals.labels import GOLD

_ROOT = Path(__file__).resolve().parent.parent
_CATALOGS = [_ROOT / "mcp_server" / "catalog.json"]


@pytest.fixture(scope="module")
def demo_catalog():
    return json.loads((_ROOT / "mcp_server" / "catalog.json").read_text())


# ---- shipped catalogs are valid --------------------------------------------
@pytest.mark.parametrize("path", _CATALOGS, ids=lambda p: p.name)
def test_shipped_catalog_passes_self_verification(path):
    catalog = json.loads(path.read_text())
    problems = verify(catalog)
    assert problems == [], f"{path.name} has violations:\n" + "\n".join(problems)


# ---- the demo catalog scores well ------------------------------------------
def test_demo_catalog_scores_high(demo_catalog):
    result = score(demo_catalog)
    assert result["valid"]
    assert result["reward"] >= 0.80, result["reward"]
    assert result["components"]["issue_f1"] >= 0.75


# ---- reward separates good from degraded (the RL sanity check) --------------
def test_reward_separates_signal(demo_catalog):
    good = score(demo_catalog)["reward"]

    empty = copy.deepcopy(demo_catalog)
    for t in empty["tables"]:
        t["issues"], t["status"] = [], "healthy"
    empty["healthScore"] = 100
    empty_reward = score(empty)["reward"]

    assert good > empty_reward + 0.25, (good, empty_reward)


def test_dropping_one_issue_lowers_recall(demo_catalog):
    base = score(demo_catalog)["components"]["issue_f1"]
    hurt = copy.deepcopy(demo_catalog)
    # remove the flagship broken-FK finding
    for t in hurt["tables"]:
        if t["name"] == "order_items":
            t["issues"] = []
            t["status"] = "healthy"
    assert score(hurt)["components"]["issue_f1"] < base


# ---- invalid catalogs are gated to zero ------------------------------------
def test_invalid_catalog_gated_to_zero(demo_catalog):
    broken = copy.deepcopy(demo_catalog)
    # a warning table with no issues listed is a structural contradiction
    for t in broken["tables"]:
        if t["status"] == "warning":
            t["issues"] = []
            break
    result = score(broken)
    assert not result["valid"]
    assert result["reward"] == 0.0


# ---- tagger unit tests ------------------------------------------------------
@pytest.mark.parametrize("text,expected", [
    ("Missing FK: user_id -> users.id", "missing_fk"),
    ("FK points at deprecated table (orders, should be orders_v2)", "broken_fk"),
    ("FLOAT used for currency", "money_as_float"),
    ("Naming drift: camelCase columns", "naming_drift"),
    ("Epoch integer timestamps vs timestamptz", "epoch_timestamp"),
    ("No primary key", "no_primary_key"),
    ("No retention policy — unbounded growth", "unbounded_growth"),
])
def test_tagger_maps_known_issues(text, expected):
    assert expected in tag_issue(text)


def test_tagger_stays_in_taxonomy():
    assert tag_issue("some totally unrelated sentence") <= TAG_SET


@pytest.mark.parametrize("tag", TAGS)
def test_canonical_phrasing_round_trips(tag):
    assert tag in tag_issue(PHRASING[tag]), f"PHRASING[{tag}] does not tag back to {tag}"


# ---- the RL environment plumbs through -------------------------------------
def test_env_whole_mode_roundtrip(demo_catalog):
    env = CatalogEnv(demo_catalog, mode="whole")
    obs = env.reset()
    assert "doc" not in obs["tables"][0]  # observation withholds the answer
    result = env.step(demo_catalog)
    assert result["reward"] >= 0.80


def test_env_per_table_episode(demo_catalog):
    env = CatalogEnv(demo_catalog, mode="per_table")
    env.reset()
    done = False
    total, steps = 0.0, 0
    while not done:
        name = env._table_order[env._cursor]
        gold = GOLD[name]
        # oracle policy: emit the canonical phrasing for each true tag
        from evals.taxonomy import PHRASING
        action = {"status": gold["status"],
                  "issues": [PHRASING[t] for t in gold["tags"]]}
        _, reward, done, _ = env.step_table(action)
        total += reward
        steps += 1
    assert steps == len(GOLD)
    assert total / steps >= 0.55  # oracle tags score well; prose paraphrase not required


def test_build_skeleton_strips_semantics(demo_catalog):
    skel = build_skeleton(demo_catalog)
    for t in skel["tables"]:
        assert "issues" not in t and "status" not in t
        for c in t["columns"]:
            assert "flag" not in c and "doc" not in c
