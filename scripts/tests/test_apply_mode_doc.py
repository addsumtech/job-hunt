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


def test_market_confirmation_agrees_across_mode_handoffs():
    """A posting location is not consent, and a current answer need not be repeated."""
    assert "Assess and interview also confirm the market" in text()
    assert "does not need to be asked again" in text()
    assert "Assess and interview do not need it" not in text()


def test_the_claim_about_the_interlock_matches_the_renderer():
    """The mode file asserts what `_suppress_personal_data` does. If the
    renderer's behaviour ever flips, this doc becomes confidently wrong — so the
    claim is checked against the code rather than trusted."""
    import render_cv
    assert render_cv._suppress_personal_data({"meta": {"target_market": "us"}}) is True
    assert render_cv._suppress_personal_data({"meta": {"target_market": "nl"}}) is False
    # and the conservative default the mode file relies on
    assert render_cv._suppress_personal_data({"meta": {}}) is True


# ---- judges get file paths, not pasted file contents --------------------------
#
# Pasting the three persona files (about 11K tokens) and the package into every
# judge prompt sent them through the orchestrator's context again in every round.
# The judges now open the files themselves. What must not change with that is the
# isolation and the fail-closed parse, so those are what is pinned here.

def _dispatch_block():
    t = text()
    start = t.index("**Dispatch all three in parallel**")
    block = t[start:t.index("**Japan rirekisho fork:**", start)]
    assert len(block) > 1000, "the dispatch block markers moved; this slice is empty"
    return block


def test_judges_are_dispatched_by_absolute_path_with_a_fallback():
    block = _dispatch_block()
    assert "absolute file paths the judge opens itself" in block
    for persona in ("agents/ats-screener.md", "agents/recruiter-screener.md",
                    "agents/hiring-manager.md"):
        assert persona in block, f"the dispatch block no longer names {persona}"
    assert "<workspace>/posting.yaml" in block and "<workspace>/cv.md" in block
    assert "**Fallback — a judge that cannot read files**" in block
    assert "paste the full text of every file above" in block


def test_a_judge_that_can_open_files_is_told_to_open_only_these():
    """With a file tool the judge could read profile.yaml — the source profile the
    whole review design keeps from it — unless the prompt forbids it."""
    block = _dispatch_block()
    assert "Read exactly these files, in full, and nothing else" in block
    assert "Name files, never the workspace directory" in block
    assert "`profile.yaml`" in block


def test_an_unreadable_file_fails_closed_through_the_real_parser():
    """The sentinel the doc prescribes must be one parse_verdicts treats as
    AMBIGUOUS (re-dispatch), never as a verdict."""
    import parse_verdicts
    block = _dispatch_block()
    assert "VERDICT: UNREADABLE <path>" in block
    parsed = parse_verdicts.parse_judge("VERDICT: UNREADABLE /skill/agents/ats-screener.md")
    assert parsed["verdict"] == "AMBIGUOUS"


def test_replies_are_still_saved_verbatim_and_persona_files_stay_out_of_record():
    block = _dispatch_block()
    assert "reply **verbatim**" in block
    for name in ("judge-<n>-ats.txt", "judge-<n>-recruiter.txt",
                 "judge-<n>-hiring-manager.txt"):
        assert name in block
    # check_apply rejects a receipt bound to a file outside the workspace, so a run
    # that "helpfully" hashed the persona files would fail at the very end.
    import check_apply
    assert "RECEIPT_INPUT_OUTSIDE_WORKSPACE" in block
    assert "RECEIPT_INPUT_OUTSIDE_WORKSPACE" in pathlib.Path(check_apply.__file__).read_text(
        encoding="utf-8")
