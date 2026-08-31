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

# The iteration-1 sha256 of each file, recorded so the check RUNS IN CI.
#
# The comparison below needs `~/.claude/.../iteration-1/scenario-inputs`, which
# exists on one machine. Everywhere else the test skipped -- so the guarantee it
# exists to enforce, that nobody edited a carried scenario, was never enforced
# anywhere it would be caught. All five of these were computed from the real
# iteration-1 files and verified equal to the working tree at the same moment.
#
# Two checks now, not one: against the original where it is present, and against
# these digests always. A digest may only be updated alongside a deliberate,
# explained decision to break comparability with iteration-1.
ITERATION_1_SHA256 = {
    "us-rn-nurse":
        "f8a619b5560ffa5c5d6e99bb736f2734bab5cd350eb5bbe02889348cb3effee8",
    "cjk-chinese-swe":
        "ab7914da4b3b0ae8c3a48cc601ca6bf5322a06801e8be8c09c103d3318c2a1f3",
    "career-switch-teacher-ux":
        "0db6c81194308227a7ee84039e89b97971568f337efd3e3982406b8b452422bd",
    "senior-exec-coo":
        "4112c68fa7a4a4f178b7758d5e92e511b4126cc1b1895faa583fd26f72564dce",
    "uk-nhs-structured":
        "8dc6ac219145327f1116c55ae3e2958a790c0deb9bcb860185d574135f3cdbc5",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("name", NAMES)
def test_the_carried_scenario_is_byte_identical(name):
    new = NEW / f"{name}.md"
    old = OLD / f"{name}.md"
    assert new.is_file(), f"{new} has not been carried forward"
    # Runs everywhere: the digest travels with the repo.
    assert sha(new) == ITERATION_1_SHA256[name], (
        f"{name}.md no longer matches its recorded iteration-1 sha256. "
        "Carrying a modified scenario forward makes the two iterations "
        "incomparable, and the previous-iteration diff becomes a comparison of "
        "two different questions.")
    if not old.is_file():
        return   # not a skip: the digest above already checked the bytes
    assert sha(new) == sha(old), (
        f"{name}.md differs from its iteration-1 original. Carrying a modified "
        "scenario forward makes the two iterations incomparable.")


def test_the_us_scenario_still_carries_the_market_string_that_leaked():
    text = (NEW / "us-rn-nurse.md").read_text(encoding="utf-8")
    assert "TARGET MARKET: United States (Los Angeles, CA)" in text
    assert "Date of birth" in text


def test_a_digest_is_recorded_for_every_carried_scenario():
    """A name added to NAMES with no digest would skip its own check silently."""
    assert set(ITERATION_1_SHA256) == set(NAMES)
    for name, digest in ITERATION_1_SHA256.items():
        assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), (
            f"{name}: {digest!r} is not a sha256")
