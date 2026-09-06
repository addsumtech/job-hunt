"""The apply mode file is layer 1.5: loaded unconditionally on entering apply.

These assertions are its backstop for the one field that arms the personal-data
interlock. A mode file that drifts from that mechanism fails silently — the run
renders a CV that passes every gate and carries a date of birth into a market
that treats it as a liability.
"""
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

MODE = REPO / "modes" / "apply.md"


def text():
    return MODE.read_text(encoding="utf-8")


def test_the_region_is_one_of_the_step_0_questions():
    t = text()
    assert "**Target region**" in t
    assert t.index("**Target region**") < t.index("## Step 1")


def test_the_options_are_the_three_clusters_not_individual_countries():
    """Promoting a country to a top-level option is how a saved default becomes
    the shape of the question itself."""
    t = text()
    for cluster in ("Anglophone developed", "EU / EEA", "East & SE Asia"):
        assert cluster in t, cluster
    assert "never as a separate region" in t


# ---- the region is asked, never inherited from a saved profile -------------
#
# `meta.target_market` is the field that arms the personal-data interlock:
# `render_cv._suppress_personal_data` returns True for Cluster 1 and False for
# Cluster 2, so getting it wrong either leaks a photo and a date of birth onto a
# US CV or strips the Bewerbungsfoto off a German one.
#
# A master profile records where the LAST application went. A CV is a record of
# what someone has done and says nothing about where they now want to work --
# reading a region off it is the same class of error as reading a salary floor
# off a payslip. Raised by the user 2026-09-06, after a discover round had made
# exactly this mistake with a stored `target_market: nl`.

def test_a_saved_profile_is_not_an_answer_to_the_region_question():
    t = text()
    assert "A saved profile is never an answer to this question" in t
    assert "answered *by the user, in this" in t


def test_the_reason_names_the_interlock_it_arms():
    """The rule has to carry its own cost or the next editor trims it as
    boilerplate, so both directions of the failure are named."""
    t = text()
    assert "interlock" in t
    assert "Bewerbungsfoto" in t or "German" in t


def test_reusing_a_master_carries_experience_not_a_target():
    """The reuse step is where the temptation lives, so the fence is restated
    there and not only at the question."""
    t = text()
    assert "carries their experience forward, never their target" in t
    i, j = t.index("Check for existing profiles"), t.index("## Step 2")
    assert i < t.index("carries their experience forward") < j, \
        "the rule has to sit inside the reuse paragraph, where the temptation is"


def test_it_says_why_assess_and_interview_do_not_need_the_question():
    """Both are handed a posting and the posting states its own location.
    Without this line the rule reads as an omission in the other two modes."""
    assert "Assess and interview do not need it" in text()


def test_the_claim_about_the_interlock_matches_the_renderer():
    """The mode file asserts what `_suppress_personal_data` does. If the
    renderer's behaviour ever flips, this doc becomes confidently wrong — so the
    claim is checked against the code rather than trusted."""
    import render_cv
    assert render_cv._suppress_personal_data({"meta": {"target_market": "us"}}) is True
    assert render_cv._suppress_personal_data({"meta": {"target_market": "nl"}}) is False
    # and the conservative default the mode file relies on
    assert render_cv._suppress_personal_data({"meta": {}}) is True
