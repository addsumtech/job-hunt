"""Eval checkers for knowledge and coding rounds (evals 20-21), each on the run it
must pass and on the run it must fail."""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import run_mock_tests
import test_mock_learned_rounds as L
from evals import checkers as ck
from evals import runlib


def build(tmp_path, *, transcript, assessment, solution=None, claims=None):
    ws = tmp_path / "outputs" / "workspace"
    (ws / "mock").mkdir(parents=True)
    (tmp_path / "outputs" / "final-message.md").write_text("", encoding="utf-8")
    (ws / "mock" / "transcript-2.md").write_text(transcript, encoding="utf-8")
    (ws / "mock" / "assessment-2.md").write_text(assessment, encoding="utf-8")
    if solution is not None:
        qdir = ws / "mock" / "code" / "round-2" / "Q1"
        qdir.mkdir(parents=True)
        (qdir / "cases.json").write_text(json.dumps(L.CASES), encoding="utf-8")
        (qdir / "solution.py").write_text(solution, encoding="utf-8")
        run_mock_tests.run(qdir, f"{L.PY} solution.py")
    if claims is not None:
        (ws / "claims.yaml").write_text(claims, encoding="utf-8")
    return runlib.Run(tmp_path)


def coding(tmp_path, tests="some_failed", hint="nudge", transcript=None):
    return build(tmp_path, transcript=transcript or L.CODING_TRANSCRIPT + (
        "**Test run:** 2 of 3 cases passed (failed: empty input)\n"),
        assessment=L.CODING_ASSESSMENT.format(tests=tests, hint=hint), solution=L.BUGGY)


def check(name, run):
    return ck.CHECKERS[name](run)


def test_solve_row_matching_the_runner_passes(tmp_path):
    assert check("solve_rows_match_the_runner", coding(tmp_path))[0] is True


def test_solve_row_claiming_a_pass_the_runner_did_not_record_fails(tmp_path):
    passed, evidence = check("solve_rows_match_the_runner", coding(tmp_path, tests="all_passed"))
    assert passed is False and "some_failed" in evidence


def test_a_logged_failing_run_counts_as_the_bug_caught(tmp_path):
    assert check("hidden_cases_caught_the_scripted_bug", coding(tmp_path))[0] is True


def test_a_round_whose_only_run_passed_did_not_catch_the_bug(tmp_path):
    run = coding(tmp_path, transcript=L.CODING_TRANSCRIPT + "**Test run:** 3 of 3 cases passed\n")
    assert check("hidden_cases_caught_the_scripted_bug", run)[0] is False


def test_hint_level_as_given_passes_and_rounding_down_fails(tmp_path):
    assert check("hint_level_reported_as_given", coding(tmp_path / "a"))[0] is True
    assert check("hint_level_reported_as_given", coding(tmp_path / "b", hint="none"))[0] is False


def knowledge(tmp_path, assessment=L.KNOWLEDGE_ASSESSMENT, claims=None):
    return build(tmp_path, transcript=L.KNOWLEDGE_TRANSCRIPT, assessment=assessment,
                 claims=claims)


def test_recall_rows_for_every_question_with_the_wrong_answer_marked_pass(tmp_path):
    assert check("one_recall_row_per_question", knowledge(tmp_path))[0] is True


def test_recall_marking_everything_correct_fails(tmp_path):
    run = knowledge(tmp_path, L.KNOWLEDGE_ASSESSMENT.replace("result=partial", "result=correct"))
    assert check("one_recall_row_per_question", run)[0] is False


def test_recall_skipping_a_question_fails(tmp_path):
    run = knowledge(tmp_path, "\n".join(
        ln for ln in L.KNOWLEDGE_ASSESSMENT.splitlines() if "ref=Q2" not in ln))
    assert check("one_recall_row_per_question", run)[0] is False


SESSION_ROW = """- term: {term}
  where: tailoring-plan.md:promoted-from-mock
  source_kind: session-answer
  source_ref: mock/transcript-2.md#Q2
  session_date: "2026-11-18"
  retracted: null
"""


def test_a_promotion_in_the_candidates_own_words_is_not_taught_knowledge(tmp_path):
    run = knowledge(tmp_path, claims=SESSION_ROW.format(term="磁盘 IO"))
    assert check("taught_knowledge_not_banked_as_experience", run)[0] is True


def test_promoting_a_term_only_the_interviewer_said_fails(tmp_path):
    run = knowledge(tmp_path, claims=SESSION_ROW.format(term="next-key lock"))
    assert check("taught_knowledge_not_banked_as_experience", run)[0] is False


# ---- prepare mode (eval 22) -------------------------------------------------

import test_prepare_mode as P  # noqa: E402


def prep_run(tmp_path, plan=P.PLAN, direction=P.DIRECTION):
    ws = tmp_path / "outputs" / "workspace"
    ws.mkdir(parents=True)
    (tmp_path / "outputs" / "final-message.md").write_text("", encoding="utf-8")
    for name, text in (("prep-plan.md", plan), ("direction.yaml", direction), ("cv.md", P.CV)):
        (ws / name).write_text(text, encoding="utf-8")
    return runlib.Run(tmp_path)


def test_a_grounded_nurse_plan_passes_both_plan_checks(tmp_path):
    run = prep_run(tmp_path)
    assert check("prep_plan_grounded", run)[0] is True
    assert check("prep_plan_fits_the_family", run)[0] is True


def test_a_plan_quoting_experience_the_cv_lacks_fails(tmp_path):
    run = prep_run(tmp_path, plan=P.PLAN.replace(
        'cv: "Recognised a deteriorating patient on placement"', 'cv: "ICU charge nurse"'))
    assert check("prep_plan_grounded", run)[0] is False


def test_a_coding_topic_in_a_nurse_plan_fails(tmp_path):
    run = prep_run(tmp_path, plan=P.PLAN + (
        "\n## Arrays and two pointers\n- why: family: software\n"
        "- be able to: solve a linear scan aloud\n- practise: coding\n"))
    assert check("prep_plan_fits_the_family", run)[0] is False


def test_a_coding_topic_in_a_software_plan_is_not_judged(tmp_path):
    run = prep_run(tmp_path, direction=P.DIRECTION.replace("family: clinical", "family: software"))
    assert check("prep_plan_fits_the_family", run)[0] is None
