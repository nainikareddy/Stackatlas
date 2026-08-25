"""CatalogEnv — StackAtlas cataloguing as a reinforcement-learning environment.

The task: given the *skeleton* of a messy database (tables, columns, traffic,
enforced FKs — everything introspection can see, but no semantics), produce a
correct catalog (docs, issue tags, health status). Reward comes from
`scorer.score`, checked against the gold labels for the fixture DB.

Two interaction modes:

  whole-database (bandit-style, one step):
      env = CatalogEnv()
      obs = env.reset()                 # the schema skeleton
      result = env.step(candidate_catalog)
      reward = result["reward"]

  per-table (multi-step episode, finer credit assignment):
      env = CatalogEnv(mode="per_table")
      obs = env.reset()                 # first table's skeleton + neighbours
      while not done:
          action = policy(obs)          # {doc, issues, status, columns}
          obs, reward, done, info = env.step_table(action)

The observation deliberately withholds `doc`, `issues`, `status`, and column
`flag`/`doc` — those are exactly what the policy must produce, so leaking them
would let a policy trivially copy the answer.
"""
from __future__ import annotations

import copy

from .labels import GOLD, GOLD_HEALTH
from .scorer import score, _prf
from .taxonomy import tag_issues

_SEMANTIC_TABLE_KEYS = {"doc", "issues", "status"}
_SEMANTIC_COL_KEYS = {"doc", "flag"}


def build_skeleton(catalog: dict) -> dict:
    """Strip a full catalog down to what introspection alone can observe."""
    skel = {
        "database": catalog.get("database"),
        "tables": [],
        "edges": copy.deepcopy(catalog.get("edges", [])),
    }
    for t in catalog.get("tables", []):
        skel["tables"].append({
            "name": t["name"],
            "rows": t.get("rows", 0),
            "readsPerDay": t.get("readsPerDay", 0),
            "writesPerDay": t.get("writesPerDay", 0),
            "pos": t.get("pos"),
            "columns": [{"name": c["name"], "type": c.get("type", "")}
                        for c in t.get("columns", [])],
        })
    return skel


class CatalogEnv:
    """A minimal, dependency-free gym-style environment.

    Parameters
    ----------
    full_catalog : dict
        A complete reference catalog for the fixture DB. Its skeleton becomes
        the observation; its labels (via `evals.labels.GOLD`) define reward.
    mode : "whole" | "per_table"
    """

    def __init__(self, full_catalog: dict, mode: str = "whole",
                 gold: dict = GOLD, gold_health: int = GOLD_HEALTH):
        self.full = full_catalog
        self.skeleton = build_skeleton(full_catalog)
        self.mode = mode
        self.gold = gold
        self.gold_health = gold_health
        self._cursor = 0
        self._table_order = [t["name"] for t in self.skeleton["tables"]]

    # ---- whole-database mode -------------------------------------------------
    def reset(self):
        self._cursor = 0
        if self.mode == "whole":
            return copy.deepcopy(self.skeleton)
        return self._table_obs(self._table_order[0])

    def step(self, candidate_catalog: dict) -> dict:
        """Score a complete candidate catalog. Returns the full reward breakdown."""
        return score(candidate_catalog, gold=self.gold, gold_health=self.gold_health)

    # ---- per-table mode ------------------------------------------------------
    def _table_obs(self, name: str) -> dict:
        t = next(t for t in self.skeleton["tables"] if t["name"] == name)
        neighbours = [e for e in self.skeleton["edges"]
                      if name in (e.get("from"), e.get("to"))]
        return {"table": copy.deepcopy(t), "edges": neighbours,
                "index": self._cursor, "total": len(self._table_order)}

    def step_table(self, action: dict):
        """action = {status, issues:[...], doc?, columns?} for the current table.

        Returns (next_obs, reward, done, info). Per-table reward blends issue-tag
        F1 (0.6) with a correct status call (0.4).
        """
        name = self._table_order[self._cursor]
        spec = self.gold[name]
        pred_tags = tag_issues(action.get("issues", []))
        _, _, f1 = _prf(pred_tags, spec["tags"])
        status_ok = action.get("status") == spec["status"]
        reward = round(0.6 * f1 + 0.4 * status_ok, 4)
        info = {"table": name, "f1": round(f1, 4), "status_ok": status_ok,
                "gold_tags": sorted(spec["tags"]), "pred_tags": sorted(pred_tags)}

        self._cursor += 1
        done = self._cursor >= len(self._table_order)
        next_obs = None if done else self._table_obs(self._table_order[self._cursor])
        return next_obs, reward, done, info
