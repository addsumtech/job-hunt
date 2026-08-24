"""The five carried-forward scenarios must be byte-identical to iteration-1.

A scenario edited between iterations turns the previous-iteration diff into a
comparison of two different questions, and nothing in the viewer would say so.
"""
import hashlib
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
NEW = REPO / "evals" / "scenarios"
OLD = (pathlib.Path.home() / ".claude" / "skills" /
       "job-application-workspace" / "iteration-1" / "scenario-inputs")

NAMES = ["us-rn-nurse", "cjk-chinese-swe", "career-switch-teacher-ux",
         "senior-exec-coo", "uk-nhs-structured"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("name", NAMES)
def test_the_carried_scenario_is_byte_identical(name):
    new = NEW / f"{name}.md"
    old = OLD / f"{name}.md"
    assert new.is_file(), f"{new} has not been carried forward"
    if not old.is_file():
        pytest.skip(f"{old} is not on this machine; cannot verify the copy")
    assert sha(new) == sha(old), (
        f"{name}.md differs from its iteration-1 original. Carrying a modified "
        "scenario forward makes the two iterations incomparable.")


def test_the_us_scenario_still_carries_the_market_string_that_leaked():
    text = (NEW / "us-rn-nurse.md").read_text(encoding="utf-8")
    assert "TARGET MARKET: United States (Los Angeles, CA)" in text
    assert "Date of birth" in text
