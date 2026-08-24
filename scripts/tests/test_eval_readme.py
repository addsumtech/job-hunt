"""The eval README's load-bearing sentences.

Each anchor is a rule whose omission nothing else would report. The quiet case
is pinned too: the test asserts the README does NOT contain outcome-prediction
vocabulary, because a harness that talks about interview odds has already lost
the argument the skill spends thirty pages winning.
"""
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
README = REPO / "evals" / "README.md"

ANCHORS = [
    "An assertion that cannot distinguish the arms is not evidence",
    "A property both arms have is a property of the model, not of the skill",
    "passed: null means not exercised, and never means pass",
    "counted from disk",
    "every guard checker is paired with the twin checker that pins its quiet case",
    "the results root is outside the repo",
    "replays a capture measured on 2026-08-09",
    "not an outcome",
]

BANNED = ["interview probability", "chance of an offer", "likely to be hired",
          "面试概率", "录用概率"]


@pytest.mark.parametrize("anchor", ANCHORS, ids=lambda a: a[:32])
def test_the_readme_carries_the_anchor(anchor):
    assert README.is_file(), f"{README} does not exist"
    assert anchor in README.read_text(encoding="utf-8"), (
        f"evals/README.md no longer contains {anchor!r}. If this was deliberate, "
        "say why in the commit message and remove the anchor in the same commit.")


@pytest.mark.parametrize("phrase", BANNED, ids=lambda p: p[:24])
def test_the_readme_predicts_nothing(phrase):
    assert phrase not in README.read_text(encoding="utf-8").lower()


def test_evals_package_is_importable():
    import evals  # noqa: F401
