"""Grading writes the viewer's field names, and the lint refuses empty evidence.

ONE CORRECTION TO THE PLAN, measured rather than argued. Its Step 1 asserted
`"closed set" in row["evidence"]` for a passing `no_receipt_for_a_gate_not_run`.
That string is the ASSERTION TEXT ("Receipt verdicts are in the closed set");
the checker's own evidence reads "1 receipt(s) in journal.jsonl, every verdict
in ('pass', ...)" and never contains it. Written as planned the test fails, and
"fix" it by loosening the string and it stops testing anything.

What that test was reaching for is that the checker's evidence arrives in the
row UNCHANGED -- the grader must not summarise, truncate or re-word what a
checker reported. So it is asserted as identity against the checker's own
return value, which is the property, and which cannot rot when a checker's
wording changes.
"""
import json

from evals import checkers as ck
from evals import grade, lint_grading, runlib

EVAL = {
    "id": 8, "name": "discover-clean-retrieval", "mode": "discover",
    "baseline_kind": "no_skill", "scenario": "scenarios/x.md",
    "assertions": [
        {"id": "A8-4", "text": "Receipt verdicts are in the closed set.",
         "role": "regression", "expected_baseline": "pass",
         "falsifier": "A receipt with verdict 'error'.",
         "checker": "no_receipt_for_a_gate_not_run"},
        {"id": "A8-9", "text": "The summary reads well.", "role": "regression",
         "expected_baseline": "pass",
         "falsifier": "A summary that buries the pivot.",
         "checker": "graded_by_reader"},
    ],
}


def make_run(tmp_path, verdict="pass"):
    out = tmp_path / "outputs"
    (out / "workspace").mkdir(parents=True)
    (out / "final-message.md").write_text("done\n", encoding="utf-8")
    (out / "workspace" / "journal.jsonl").write_text(
        json.dumps({"action": "gate", "gate": "check_shortlist",
                    "verdict": verdict}) + "\n", encoding="utf-8")
    return runlib.Run(tmp_path)


def test_grading_uses_the_exact_field_names_the_viewer_requires(tmp_path):
    doc = grade.grade_run(make_run(tmp_path), EVAL)
    assert set(doc) == {"expectations", "summary", "eval_id", "eval_name"}
    for row in doc["expectations"]:
        assert set(row) >= {"text", "passed", "evidence"}


def test_a_passing_checker_s_evidence_arrives_in_the_row_unchanged(tmp_path):
    run = make_run(tmp_path)
    expected_passed, expected_evidence = \
        ck.CHECKERS["no_receipt_for_a_gate_not_run"](run)
    row = grade.grade_run(run, EVAL)["expectations"][0]
    assert row["passed"] is expected_passed is True
    assert row["evidence"] == expected_evidence, (
        "the grader re-worded the checker's evidence; a grading file is read by "
        "someone checking the claim, and a summary of the evidence is not it")
    assert "journal.jsonl" in row["evidence"], (
        "evidence must name the artifact it was read from")


def test_a_failing_checker_records_why(tmp_path):
    doc = grade.grade_run(make_run(tmp_path, verdict="error"), EVAL)
    row = doc["expectations"][0]
    assert row["passed"] is False
    assert "error" in row["evidence"]


def test_not_exercised_rows_are_null_and_out_of_the_denominator(tmp_path):
    doc = grade.grade_run(make_run(tmp_path), EVAL)
    reader_row = doc["expectations"][1]
    assert reader_row["passed"] is None
    assert reader_row["evidence"] == "AWAITING_READER_GRADE"
    assert doc["summary"] == {"passed": 1, "failed": 0, "total": 1,
                              "not_exercised": 1, "pass_rate": 1.0}


def test_a_run_with_no_decidable_rows_reports_a_zero_denominator(tmp_path):
    only_reader = dict(EVAL, assertions=[EVAL["assertions"][1]])
    doc = grade.grade_run(make_run(tmp_path), only_reader)
    assert doc["summary"]["total"] == 0
    assert doc["summary"]["pass_rate"] is None, (
        "a pass rate over an empty denominator must be null, not 0.0 -- 0.0 "
        "reads as 'everything failed'")


def test_grade_does_not_overwrite_a_human_grade(tmp_path):
    run = make_run(tmp_path)
    existing = {"expectations": [
        {"text": "The summary reads well.", "passed": True,
         "evidence": "Summary line 1 names the pivot: 'From classroom to "
                     "learning design'."}], "summary": {}}
    (run.dir / "grading.json").write_text(json.dumps(existing),
                                          encoding="utf-8")
    doc = grade.grade_run(run, EVAL)
    row = [r for r in doc["expectations"]
           if r["text"] == "The summary reads well."][0]
    assert row["passed"] is True
    assert "classroom" in row["evidence"]


def test_a_checker_that_raises_fails_the_row_rather_than_the_run(tmp_path):
    """A crash is a failed assertion with the traceback as evidence, not an
    aborted grading pass: one broken checker must not cost the other rows."""
    boom = dict(EVAL, assertions=[
        dict(EVAL["assertions"][0], checker="explodes"),
        EVAL["assertions"][1]])
    ck.CHECKERS["explodes"] = lambda run: (_ for _ in ()).throw(
        RuntimeError("kaboom"))
    try:
        doc = grade.grade_run(make_run(tmp_path), boom)
    finally:
        del ck.CHECKERS["explodes"]
    assert doc["expectations"][0]["passed"] is False
    assert "kaboom" in doc["expectations"][0]["evidence"]
    assert len(doc["expectations"]) == 2


# ---- lint_grading -----------------------------------------------------------

def good_doc():
    return {"expectations": [
        {"text": "a", "passed": True,
         "evidence": "cv.md:3 'Registered Nurse, 7 years critical care'"},
        {"text": "b", "passed": False,
         "evidence": "no check_personal_data receipt in journal.jsonl"}],
        "summary": {"passed": 1, "failed": 1, "total": 2,
                    "not_exercised": 0, "pass_rate": 0.5}}


def test_a_well_formed_grading_file_is_quiet():
    assert lint_grading.check(good_doc(), "g.json") == []


def test_contentless_evidence_is_rejected():
    doc = good_doc()
    doc["expectations"][0]["evidence"] = "looks good"
    out = lint_grading.check(doc, "g.json")
    assert any(f.startswith("CONTENTLESS_EVIDENCE") for f in out)


def test_empty_evidence_is_rejected():
    doc = good_doc()
    doc["expectations"][1]["evidence"] = ""
    assert any(f.startswith("NO_EVIDENCE") for f in lint_grading.check(doc, "g"))


def test_an_ungraded_reader_row_blocks_aggregation():
    doc = good_doc()
    doc["expectations"].append({"text": "c", "passed": None,
                                "evidence": "AWAITING_READER_GRADE"})
    out = lint_grading.check(doc, "g.json")
    assert any(f.startswith("AWAITING_READER_GRADE") for f in out)


def test_a_deliberate_not_exercised_row_with_a_reason_is_allowed():
    doc = good_doc()
    doc["expectations"].append({
        "text": "c", "passed": None,
        "evidence": "not exercised: no escalating tag fired this round"})
    assert lint_grading.check(doc, "g.json") == []


def test_a_null_row_with_no_reason_at_all_is_rejected():
    doc = good_doc()
    doc["expectations"].append({"text": "c", "passed": None, "evidence": ""})
    out = lint_grading.check(doc, "g.json")
    assert any(f.startswith("UNEXPLAINED_NULL") for f in out)


def test_a_summary_that_disagrees_with_its_rows_is_rejected():
    doc = good_doc()
    doc["summary"]["passed"] = 2
    out = lint_grading.check(doc, "g.json")
    assert any(f.startswith("SUMMARY_MISMATCH") for f in out)
