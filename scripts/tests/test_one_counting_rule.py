"""One rule for what counts as evidenced, stated the same way everywhere.

MEASURED IN A REAL APPLY RUN. SKILL.md's gate table calls
`scripts/count_coverage.py` "the only count-producing path; a hand-written
second number cannot be reconciled". Apply mode has no `fit-assessment.yaml`
for it to read, so its FIT SNAPSHOT is hand-counted from a formula in SKILL.md
— a second path, with a second disclaimer, which is the situation that sentence
forbids.

Worse than duplication: the two definitions DISAGREE.

    count_coverage.py   `match: strong` + `recency: dated`  ->  counted PARTIAL
    gap-analysis.md:19  stale evidence IS partial, not strong
    SKILL.md:213        "must-haves where CV evidence is `strong`"  -- silent on recency

A model computing the snapshot from SKILL.md's formula alone counts a
stale-but-strong must-have as evidenced; count_coverage counts the same row as
partial. Same facts, two numbers, and which one the user sees depends on which
file was read.

These pin the rule to one shape in all three places.
"""
import pathlib
import re
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import count_coverage  # noqa: E402

SKILL = (REPO / "SKILL.md").read_text(encoding="utf-8")
CRAFT = (REPO / "references" / "gap-analysis.md").read_text(encoding="utf-8")


def _formula():
    for line in SKILL.splitlines():
        if line.startswith("**Computation & labels"):
            return line
    raise AssertionError("SKILL.md no longer states the apply counting formula")


def test_the_code_downgrades_stale_strong_evidence():
    """The behaviour the prose has to match. Asserted first so a change in
    count_coverage shows up here rather than as a silent divergence."""
    rows = [{"id": "M1", "kind": "must_have", "match": "strong", "recency": "dated"},
            {"id": "M2", "kind": "must_have", "match": "strong", "recency": "current"}]
    counts = count_coverage.coverage(rows)
    assert counts["must_strong"] == 1, counts
    assert counts["must_partial"] == 1, (
        "strong+dated must land on partial — it satisfies the keyword and reads "
        "as rusty to a human")


def test_the_apply_formula_states_the_recency_rule():
    """The formula is what a model computing the FIT SNAPSHOT actually reads. If
    it does not say what stale evidence counts AS, the snapshot disagrees with
    count_coverage on every dated must-have.

    Asserted as the `dated` -> `partial` PAIR in proximity, not as a keyword
    anywhere in the sentence: the first version of this test looked for "dated"
    or "stale" anywhere in the line, and deleting the load-bearing clause left
    enough surrounding prose to satisfy it. A substring cannot tell a rule from
    a mention of the words in it.
    """
    formula = _formula().lower()
    assert re.search(r"`?dated`?[^.]{0,80}`?partial`?", formula), (
        "the formula must say that dated evidence counts as PARTIAL, in those "
        "terms and close enough together to be one statement:\n  "
        + _formula()[:200])
    assert re.search(r"never\s+`?strong`?", formula), (
        "and that it is never counted strong — the half that makes it a rule "
        "rather than a caveat")


def test_the_gate_table_does_not_overclaim_a_single_path():
    """The claim as written is false in apply mode, and a false invariant is
    worse than an absent one — a reader trusts it and stops looking for the
    second number.

    Checked by what FOLLOWS the claim, not by a keyword in the row: the row is
    long, and almost any qualifier word appears somewhere in it regardless.
    """
    row = [l for l in SKILL.splitlines() if "count_coverage.py" in l and l.startswith("|")]
    assert row, "the gate table no longer lists count_coverage"
    text = row[0]
    m = re.search(r"only count-producing path", text)
    if not m:
        return                                  # rephrased away entirely is fine
    tail = text[m.end():m.end() + 90].lower()
    assert re.search(r"\bwherever\b|\bwhen\b|\bin assess\b|\bexcept\b", tail), (
        "the claim is stated unqualified; apply mode without an assessment "
        "hand-counts, so it is not the only path:\n  " + text[:200])


def test_gap_analysis_and_the_formula_agree_on_stale_evidence():
    assert "recency matters" in CRAFT.lower(), "gap-analysis.md lost the rule"
    assert "partial" in _formula().lower(), (
        "the formula must say what stale evidence counts as, not merely that "
        "recency exists")


@pytest.mark.parametrize("recency,expect_strong", [("current", 1), ("dated", 0)])
def test_the_rule_is_the_same_whichever_stage_applies_it(recency, expect_strong):
    """gap-analysis.md tells the analyst to classify stale evidence as partial;
    count_coverage downgrades it at counting time. Both orders must give the
    same answer, or the number moves with when the analyst happened to apply it.
    """
    downgraded_early = [{"id": "M1", "kind": "must_have",
                         "match": "partial" if recency == "dated" else "strong",
                         "recency": recency}]
    downgraded_late = [{"id": "M1", "kind": "must_have",
                        "match": "strong", "recency": recency}]
    assert (count_coverage.coverage(downgraded_early)["must_strong"]
            == count_coverage.coverage(downgraded_late)["must_strong"]
            == expect_strong)
