"""One correction to the plan, measured: its write() helper called
mkdir(parents=True) without exist_ok, and test_the_cli_exits_1_on_findings_and_0
writes run-1 twice -- once dirty, once clean -- so it died with FileExistsError
before reaching either assertion.
"""
import json

import pytest

from evals import check_discrimination as cd

DOC = {"evals": [{
    "id": 14, "name": "apply-us-personal-data", "mode": "apply",
    "baseline_kind": "old_skill", "scenario": "s.md",
    "assertions": [
        {"id": "A14-1", "text": "no DOB in the US CV", "role": "discriminating",
         "expected_baseline": "fail", "falsifier": "z" * 30,
         "checker": "personal_data_stripped_for_cluster1"},
        {"id": "A14-2", "text": "the interlock is audible",
         "role": "discriminating", "expected_baseline": "fail",
         "falsifier": "z" * 30, "checker": "interlock_is_audible"},
        {"id": "A14-3", "text": "docx and pdf", "role": "regression",
         "expected_baseline": "pass", "falsifier": "z" * 30,
         "checker": "both_docx_and_pdf_produced"}]}]}


def write(root, arm, n, results):
    d = root / "eval-14" / arm / f"run-{n}"
    # exist_ok: the CLI test re-grades run-1 in place to flip the tree from
    # findings to clean, which is exactly what evals/grade.py does on a re-run.
    (d / "outputs").mkdir(parents=True, exist_ok=True)
    rows = [{"assertion_id": aid, "text": aid, "role": role, "passed": passed,
             "evidence": "recorded evidence line"}
            for aid, role, passed in results]
    decided = [r for r in rows if r["passed"] is not None]
    (d / "grading.json").write_text(json.dumps({
        "expectations": rows,
        "summary": {"passed": sum(1 for r in decided if r["passed"]),
                    "failed": sum(1 for r in decided if not r["passed"]),
                    "total": len(decided), "not_exercised": 0,
                    "pass_rate": 0.0}}), encoding="utf-8")


def test_the_pilot_is_quiet_when_the_baseline_fails_every_guard(tmp_path):
    write(tmp_path, "baseline", 1,
          [("A14-1", "discriminating", False),
           ("A14-2", "discriminating", False),
           ("A14-3", "regression", True)])
    assert cd.pilot(tmp_path, DOC) == []


def test_the_pilot_rejects_a_guard_the_baseline_passed(tmp_path):
    write(tmp_path, "baseline", 1,
          [("A14-1", "discriminating", True),
           ("A14-2", "discriminating", False),
           ("A14-3", "regression", True)])
    out = cd.pilot(tmp_path, DOC)
    assert len(out) == 1
    assert out[0].startswith("BASELINE_PASSED_A_GUARD: A14-1")
    assert "re-role" in out[0]


def test_the_pilot_reports_a_guard_that_was_never_exercised(tmp_path):
    write(tmp_path, "baseline", 1,
          [("A14-1", "discriminating", None),
           ("A14-2", "discriminating", False),
           ("A14-3", "regression", True)])
    out = cd.pilot(tmp_path, DOC)
    assert any(f.startswith("GUARD_NOT_EXERCISED: A14-1") for f in out)


def test_the_pilot_refuses_to_pass_on_a_with_skill_only_tree(tmp_path):
    write(tmp_path, "with_skill", 1, [("A14-1", "discriminating", True)])
    out = cd.pilot(tmp_path, DOC)
    assert any(f.startswith("NO_PILOT_RUN: eval-14") for f in out)


def test_posthoc_flags_only_guards_the_baseline_passed_in_every_run(tmp_path):
    write(tmp_path, "baseline", 1,
          [("A14-1", "discriminating", True), ("A14-2", "discriminating", True)])
    write(tmp_path, "baseline", 2,
          [("A14-1", "discriminating", True), ("A14-2", "discriminating", False)])
    write(tmp_path, "with_skill", 1,
          [("A14-1", "discriminating", True), ("A14-2", "discriminating", True)])
    out = cd.posthoc(tmp_path, DOC)
    assert any("A14-1" in f for f in out)
    assert not any("A14-2" in f for f in out), (
        "A14-2 failed in one baseline run, so it CAN tell the arms apart")


def test_the_cli_exits_1_on_findings_and_0_when_clean(tmp_path, capsys):
    write(tmp_path, "baseline", 1, [("A14-1", "discriminating", True),
                                    ("A14-2", "discriminating", True),
                                    ("A14-3", "regression", True)])
    assert cd.main(["--iteration", str(tmp_path), "--pilot",
                    "--assertions-inline", json.dumps(DOC)]) == 1
    write(tmp_path, "baseline", 1, [("A14-1", "discriminating", False),
                                    ("A14-2", "discriminating", False),
                                    ("A14-3", "regression", True)])
    assert cd.main(["--iteration", str(tmp_path), "--pilot",
                    "--assertions-inline", json.dumps(DOC)]) == 0


# ---- the baseline-arm filter, added after mutation testing --------------------
#
# Deleting `if arm != "baseline": continue` from _baseline_rows left all six
# planned tests green. The with_skill-only test passed for the WRONG REASON: with
# the filter gone the with_skill run supplies rows for A14-1, and the
# NO_PILOT_RUN the test looks for is emitted for A14-2 instead — a different
# guard, same string. These pin the arm the evidence came from.

def test_a_guard_the_baseline_passed_everywhere_is_flagged_even_if_with_skill_failed(tmp_path):
    """The case pooling the arms would hide.

    A14-1 passes in every BASELINE run, so it distinguishes nothing and must be
    flagged. If with_skill runs leak into the baseline pool, its one failure
    makes `all(results)` false and the finding disappears — the detector goes
    quiet on precisely the assertion it exists to catch.
    """
    write(tmp_path, "baseline", 1, [("A14-1", "discriminating", True)])
    write(tmp_path, "baseline", 2, [("A14-1", "discriminating", True)])
    write(tmp_path, "with_skill", 1, [("A14-1", "discriminating", False)])
    out = cd.posthoc(tmp_path, DOC)
    assert any("A14-1" in f for f in out), (
        "A14-1 passed in both baseline runs and is not evidence about the "
        "skill; a with_skill failure must not suppress that")
    assert any("all 2 baseline run(s)" in f for f in out), (
        "the count must be of baseline runs only — 3 here would mean the "
        "with_skill run was counted as baseline evidence")


def test_a_with_skill_only_tree_yields_no_baseline_evidence_for_any_guard(tmp_path):
    """Stronger than 'some NO_PILOT_RUN appeared': with no baseline run at all,
    EVERY guard must be unevidenced, and none may be judged from with_skill."""
    write(tmp_path, "with_skill", 1, [("A14-1", "discriminating", True),
                                      ("A14-2", "discriminating", True)])
    out = cd.pilot(tmp_path, DOC)
    assert len(out) == 2, f"expected one finding per guard, got: {out}"
    assert all(f.startswith("NO_PILOT_RUN") for f in out), out
    assert not any("BASELINE_PASSED_A_GUARD" in f for f in out), (
        "a with_skill result was read as a baseline verdict")
    assert cd.posthoc(tmp_path, DOC) == [], (
        "posthoc has no baseline evidence here and must say nothing")


# ---- three causes wearing one finding's name --------------------------------
#
# MEASURED IN THE ITERATION-2 PILOT. A0-3 uses `graded_by_reader`, which returns
# AWAITING_READER_GRADE because no program can settle whether a summary leads
# with the pivot. The pilot reported:
#
#   GUARD_NOT_EXERCISED: A0-3 ... The scenario does not reach the branch — fix
#   the scenario, not the assertion.
#
# Every clause of which is wrong. The scenario reached the branch fine; what is
# missing is a human. Following that remedy means rewriting a scenario that was
# never broken, and the row still will not be graded afterwards.

def write_reader_row(root, arm, n, aid="A14-1"):
    d = root / "eval-14" / arm / f"run-{n}"
    (d / "outputs").mkdir(parents=True, exist_ok=True)
    (d / "grading.json").write_text(json.dumps({"expectations": [
        {"assertion_id": aid, "text": aid, "role": "discriminating",
         "passed": None, "evidence": "AWAITING_READER_GRADE"}]}),
        encoding="utf-8")


def test_an_ungraded_reader_row_asks_for_a_reader_not_a_scenario_rewrite(tmp_path):
    write_reader_row(tmp_path, "baseline", 1)
    out = cd.pilot(tmp_path, DOC)
    assert any(f.startswith("NEEDS_READER_GRADE: A14-1") for f in out), out
    assert not any(f.startswith("GUARD_NOT_EXERCISED") for f in out), (
        "a row awaiting a human is not a scenario that failed to reach a branch")
    finding = [f for f in out if f.startswith("NEEDS_READER_GRADE")][0]
    assert "grading.json" in finding, (
        "the remedy must say where to write the verdict")
    assert "scenario" not in finding.lower(), (
        f"this remedy sends the reader to rewrite a working scenario: {finding}")


def test_a_genuinely_unexercised_guard_still_says_fix_the_scenario(tmp_path):
    """The other cause keeps its own diagnosis — the point is telling them
    apart, not replacing one wrong message with another."""
    d = tmp_path / "eval-14" / "baseline" / "run-1"
    (d / "outputs").mkdir(parents=True)
    (d / "grading.json").write_text(json.dumps({"expectations": [
        {"assertion_id": "A14-1", "text": "x", "role": "discriminating",
         "passed": None,
         "evidence": "not exercised: posting-source.txt is not a login wall"}]}),
        encoding="utf-8")
    out = cd.pilot(tmp_path, DOC)
    assert any(f.startswith("GUARD_NOT_EXERCISED: A14-1") for f in out), out
    assert not any(f.startswith("NEEDS_READER_GRADE") for f in out)
