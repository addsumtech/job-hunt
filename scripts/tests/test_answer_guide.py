"""answer-guide.md: the step where being useful collides with the load-bearing rule.

Interview mode produced a question list and nothing about what a good answer
contains, which is half a deliverable — the user who asked for the other half was
right. The reason it was missing is real though, and it is written into
modes/interview.md as "never write an answer for the candidate": the questions that
most need a model answer are exactly the ones the candidate has no evidence for, and
a satisfying answer to those can only be written by inventing the experience.

So the guidance ships, and the honesty distinction is mechanical rather than a
matter of tone. Each entry names the requirement it serves and declares whether it
rests on evidence; the gate reads fit-assessment.yaml and fails an entry that writes
a scored gap up as experience.

The pairs below are what make that checkable: every firing case has a quiet twin on
almost the same input, because a gate that fires on correct output is one people
switch off.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_mock
from findings import assert_finding, assert_no_finding, codes

ASSESSMENT = """requirements:
  - id: R1
    match: strong
  - id: R2
    match: no_evidence
  - id: R3
    match: gap
"""

EVIDENCED = """# Answer guide

## Q1 — Walk me through the pipeline you owned.
- row: R1
- basis: evidenced
- source: profile.yaml:experience[0].bullets[2]
- S: offline recon for a 3T scanner study
"""


def build(tmp_path, guide, assessment=ASSESSMENT):
    ws = tmp_path / "ws"
    (ws / "mock").mkdir(parents=True, exist_ok=True)
    if assessment is not None:
        (ws / "fit-assessment.yaml").write_text(assessment, encoding="utf-8")
    path = ws / "mock" / "answer-guide.md"
    path.write_text(guide, encoding="utf-8")
    return path, ws


def run(tmp_path, guide, assessment=ASSESSMENT):
    path, ws = build(tmp_path, guide, assessment)
    found, notices = check_mock.check_answer_guide(path, ws)
    return "\n".join(found), notices


def test_an_evidenced_entry_on_an_evidenced_row_is_quiet(tmp_path):
    out, notices = run(tmp_path, EVIDENCED)
    assert codes(out) == set(), out
    assert notices == []


# ---------------------------------------------------------------- the real check

def test_a_scored_gap_written_up_as_evidenced_fails(tmp_path):
    """The finding this artifact exists to make impossible.

    R2 is `no_evidence` in the assessment. An entry that tells the candidate how to
    answer it from experience is telling them to invent one.
    """
    out, _ = run(tmp_path, EVIDENCED.replace("row: R1", "row: R2"))
    assert_finding(out, "GUIDE_GAP_AS_EVIDENCED", about="R2")


def test_match_gap_fires_the_same_way_as_no_evidence(tmp_path):
    """Both values mean the candidate has not done it. Checking only one would leave
    half the rows able to carry an invented answer."""
    out, _ = run(tmp_path, EVIDENCED.replace("row: R1", "row: R3"))
    assert_finding(out, "GUIDE_GAP_AS_EVIDENCED", about="R3")


def test_the_same_gap_row_as_an_honest_gap_is_quiet(tmp_path):
    """The twin. Without it the gate could be failing every entry on a gapped row —
    which would delete the honest-gap framing, the one thing the candidate actually
    needs for those questions."""
    guide = EVIDENCED.replace("row: R1", "row: R2").replace("basis: evidenced",
                                                            "basis: honest_gap")
    out, _ = run(tmp_path, guide)
    assert_no_finding(out, "GUIDE_GAP_AS_EVIDENCED")


def test_a_gap_row_named_alongside_an_evidenced_one_still_fires(tmp_path):
    """An entry serving R1 and R2 must not launder R2 through R1's evidence."""
    out, _ = run(tmp_path, EVIDENCED.replace("row: R1", "row: R1, R2"))
    assert_finding(out, "GUIDE_GAP_AS_EVIDENCED", about="R2")


# ---------------------------------------------------------------- shape checks

def test_an_entry_with_no_source_line_fails(tmp_path):
    out, _ = run(tmp_path, EVIDENCED.replace(
        "- source: profile.yaml:experience[0].bullets[2]\n", ""))
    assert_finding(out, "GUIDE_NO_SOURCE")


def test_an_empty_source_line_does_not_pass_by_borrowing_the_next_hyphen(tmp_path):
    """The measured defect from the answer-bank check, re-pinned here.

    `\\s` matches a newline, so `^\\s*-\\s*source:\\s*\\S+` matches an EMPTY
    "- source:" line by taking the "-" of the bullet below it. This guide uses
    `[ \\t]`; the test is what stops someone 'simplifying' it back.
    """
    out, _ = run(tmp_path, EVIDENCED.replace(
        "- source: profile.yaml:experience[0].bullets[2]", "- source:"))
    assert_finding(out, "GUIDE_NO_SOURCE")


def test_an_entry_with_no_row_line_fails(tmp_path):
    out, _ = run(tmp_path, EVIDENCED.replace("- row: R1\n", ""))
    assert_finding(out, "GUIDE_NO_ROW")


def test_a_basis_outside_the_two_tokens_fails(tmp_path):
    out, _ = run(tmp_path, EVIDENCED.replace("basis: evidenced", "basis: mostly"))
    assert_finding(out, "GUIDE_BAD_BASIS")


def test_a_missing_basis_fails_rather_than_defaulting(tmp_path):
    """Defaulting would pick a side of the honesty distinction on the author's
    behalf, and the safe-looking default (`evidenced`) is the unsafe one."""
    out, _ = run(tmp_path, EVIDENCED.replace("- basis: evidenced\n", ""))
    assert_finding(out, "GUIDE_BAD_BASIS")


def test_a_guide_with_no_entries_fails(tmp_path):
    out, _ = run(tmp_path, "# Answer guide\n\nnothing here\n")
    assert_finding(out, "NO_ANSWER_GUIDE_ENTRIES")


# ---------------------------------------------------------------- could-not-run

def test_a_missing_assessment_reports_rather_than_passes_silently(tmp_path):
    """Interview mode can be entered on a posting plus a CV with no assessment. The
    cross-check then cannot run, and a check that did not run must not look like one
    that passed — so it says so, and the shape checks still run."""
    out, notices = run(tmp_path, EVIDENCED.replace("row: R1", "row: R2"),
                       assessment=None)
    assert_no_finding(out, "GUIDE_GAP_AS_EVIDENCED")
    assert any(n.startswith("NO_ASSESSMENT_TO_CHECK_AGAINST") for n in notices), notices


def test_the_shape_checks_still_run_without_an_assessment(tmp_path):
    out, _ = run(tmp_path, EVIDENCED.replace("- basis: evidenced\n", ""),
                 assessment=None)
    assert_finding(out, "GUIDE_BAD_BASIS")


def test_an_absent_guide_is_left_to_the_session_artifact_check(tmp_path):
    """Two codes for one absence would make the finding list read as two defects."""
    ws = tmp_path / "ws"
    (ws / "mock").mkdir(parents=True)
    found, _ = check_mock.check_answer_guide(ws / "mock" / "answer-guide.md", ws)
    assert found == []
    codes_out = codes("\n".join(check_mock.check_session_artifacts(ws / "mock")))
    assert "NO_ANSWER_GUIDE" in codes_out
