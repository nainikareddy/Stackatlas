"""StackAtlas evaluation + RL-environment package.

Public surface:
    from evals import score, verify, CatalogEnv, GOLD
"""
from .labels import GOLD, GOLD_HEALTH
from .scorer import score, format_report
from .verify import verify, is_valid
from .env import CatalogEnv, build_skeleton
from .taxonomy import TAGS, tag_issues

__all__ = [
    "GOLD", "GOLD_HEALTH", "score", "format_report",
    "verify", "is_valid", "CatalogEnv", "build_skeleton",
    "TAGS", "tag_issues",
]
