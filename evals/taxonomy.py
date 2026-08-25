"""Issue taxonomy + a deterministic tagger.

The catalog's `issues` are free text written by an LLM. To score extraction
against a fixed answer key we map each free-text issue onto a small, closed
set of canonical *tags*. The tagger is pure keyword/regex logic — no model,
no network — so scoring is deterministic and reproducible in CI.

This is the piece that makes the task legible for RL: the reward function
compares *tags*, not prose, so paraphrases score the same and the signal is
stable enough to optimise against.
"""
from __future__ import annotations

import re

# Canonical issue taxonomy. Keep this closed and small: every gold label and
# every scored prediction is reduced to this vocabulary.
TAGS = [
    "missing_fk",          # a logical foreign key exists in intent but no constraint enforces it
    "broken_fk",           # an enforced FK points at the wrong / deprecated table
    "deprecated_table",    # legacy table kept alive after being superseded
    "orphan_table",        # no traffic; junk / abandoned
    "naming_drift",        # camelCase vs snake_case, uid vs user_id, updated vs updated_at
    "magic_values",        # undocumented magic codes (single-char status, etc.)
    "status_vocab_drift",  # multiple disagreeing status vocabularies across tables
    "money_as_float",      # currency stored as FLOAT
    "no_primary_key",      # table has no primary key
    "no_unique_index",     # missing uniqueness where identity requires it (e.g. email)
    "undocumented_jsonb",  # jsonb blob with no documented shape
    "unbounded_growth",    # append-only table with no retention policy
    "epoch_timestamp",     # integer epoch timestamps while the rest use timestamptz
    "zero_writes",         # no writes in the observation window
    "empty_but_hot",       # empty table still receiving heavy reads (silent workaround)
]
TAG_SET = set(TAGS)

# Ordered (tag, pattern) rules. A single issue string may match several tags.
_RULES: list[tuple[str, re.Pattern]] = [
    ("broken_fk",          re.compile(r"\b(broken fk|points? (at|to) (a )?deprecated|targets? (a )?deprecated|should be orders_v2|re-?point|wrong table)\b", re.I)),
    ("deprecated_table",   re.compile(r"\b(deprecated|legacy|superseded|replaced by)\b", re.I)),
    ("empty_but_hot",      re.compile(r"\b(empty (despite|but)|empty .*read|worked around|silent(ly)? (stuff|workaround))\b", re.I)),
    ("orphan_table",       re.compile(r"\b(orphan|junk|abandoned|zero reads|no reads|left behind)\b", re.I)),
    ("missing_fk",         re.compile(r"\b(missing fk|no fk|not enforced|unenforced|logical fk|fk (dropped|removed))\b", re.I)),
    ("no_primary_key",     re.compile(r"\bno primary key\b", re.I)),
    ("no_unique_index",    re.compile(r"\b(no unique index|not unique|duplicate account|duplicate .*possible)\b", re.I)),
    ("money_as_float",     re.compile(r"\b(float .*(money|currency|price)|money .*(float|real)|currency .*float|price .*float)\b", re.I)),
    ("status_vocab_drift", re.compile(r"\b(status vocab|another status|third status|different (status )?vocabular|inconsistent status)\b", re.I)),
    ("magic_values",       re.compile(r"\b(magic (status |value)|single[- ]char|undocumented .*status|status values? \()", re.I)),
    ("epoch_timestamp",    re.compile(r"\b(epoch|unix (epoch|seconds|time)|integer timestamp|timestamp .*integer)\b", re.I)),
    ("naming_drift",       re.compile(r"\b(camelcase|naming drift|uid vs|named (differently|inconsistently)|inconsistent(ly)? (named|naming)|snake_case)\b", re.I)),
    ("undocumented_jsonb", re.compile(r"\b(undocumented jsonb|jsonb shape|jsonb (blob|payload)|shape .*jsonb)\b", re.I)),
    ("unbounded_growth",   re.compile(r"\b(retention|unbounded|grow(ing|s) (unbounded|forever)|no ttl)\b", re.I)),
    ("zero_writes",        re.compile(r"\b(zero writes|no writes in|0 writes)\b", re.I)),
]


# A representative issue sentence for each tag: the tagger is guaranteed to map
# PHRASING[tag] back onto {tag} (enforced by a round-trip test). Handy as an
# oracle policy in the RL env and as documentation of what each tag "sounds like".
PHRASING = {
    "missing_fk":         "Missing FK: column is a logical foreign key, not enforced",
    "broken_fk":          "Enforced FK points at a deprecated table (wrong target)",
    "deprecated_table":   "Deprecated legacy table, superseded but never dropped",
    "orphan_table":       "Orphaned table: zero reads, junk left behind",
    "naming_drift":       "Naming drift: camelCase columns break the snake_case convention",
    "magic_values":       "Magic status values, undocumented single-char codes",
    "status_vocab_drift": "Third status vocabulary — different status vocabulary than other tables",
    "money_as_float":     "FLOAT used for currency",
    "no_primary_key":     "No primary key",
    "no_unique_index":    "No unique index — duplicate accounts possible",
    "undocumented_jsonb": "Undocumented jsonb shape",
    "unbounded_growth":   "No retention policy — unbounded growth",
    "epoch_timestamp":    "Epoch integer timestamps vs timestamptz",
    "zero_writes":        "Zero writes in the observation window",
    "empty_but_hot":      "Empty despite heavy reads — app silently worked around it",
}


def tag_issue(issue: str) -> set[str]:
    """Map one free-text issue string onto zero or more canonical tags."""
    tags = {tag for tag, pat in _RULES if pat.search(issue or "")}
    # A broken FK sentence usually also mentions the "deprecated" target; that
    # deprecation is the *cause* of the broken FK, not a second finding on this
    # table, so don't double-count it here.
    if "broken_fk" in tags:
        tags.discard("deprecated_table")
    return tags


def tag_issues(issues) -> set[str]:
    """Union of tags across a table's list of issue strings."""
    out: set[str] = set()
    for issue in issues or []:
        out |= tag_issue(issue)
    return out
