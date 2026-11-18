"""Prepare mode: the profile-level workspace, the general plan, and drills with no posting.

The fixtures are deliberately not software: a UK nurse's plan and a clinical
knowledge drill. job-hunt serves every profession, and a gate tuned on LeetCode
examples would pass its own tests and fail the first nurse.
"""
import contextlib
import io
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_drill
import check_mock
import check_prep_plan
import enter_mode
import journal
import mock_fixtures as F
import paths
import run_mock_tests
import test_mock_learned_rounds as L

DIRECTION = """target_titles: ["Staff Nurse (Band 5)"]
family: clinical
market: uk
level: newly qualified
timeline: interviews expected within two months
"""

CV = """# Amara Okafor
BSc Adult Nursing, 2026. Placements: acute medical ward, community nursing team.
Recognised a deteriorating patient on placement and escalated to the nurse in charge.
"""

PLAN = """# Preparation plan — Staff Nurse (Band 5), UK

## Values-based questions
- why: shape: United Kingdom and EU public / academic sector — NHS values framework
- be able to: give a real example for compassion, dignity and speaking up, each from a placement
- practise: behavioural

## Recognising and escalating deterioration
- why: cv: "Recognised a deteriorating patient on placement"
- be able to: explain the early warning signs of sepsis, how an early-warning score triggers escalation, and the SBAR handover structure
- practise: knowledge

## Newly qualified expectations
- why: direction: "newly qualified"
- be able to: explain what preceptorship is and what support you would ask for in the first months
- practise: self-study
"""

TRANSCRIPT = """# Drill transcript — round 1
Round type: knowledge
Market: uk
Family: clinical

## Q1 — What does SBAR stand for, and when would you use it?
**Interviewer:** What does SBAR stand for, and when would you use it?
**Candidate:** Situation, Background, Assessment, Recommendation. I'd use it when I phone the doctor about a patient who is deteriorating.

## Q2 — Name three early signs of sepsis in an adult.
**Interviewer:** Name three early signs of sepsis in an adult.
**Candidate:** A high temperature and a fast heart rate. I'm not sure of the third.
"""

ASSESSMENT = """MOCK-ASSESSMENT-V1
ROUND: 1
ROUND-TYPE: knowledge
MARKET: uk
FAMILY: clinical
FINDINGS: none
RECALL: result=correct | hint=none | ref=Q1 | quote=Situation, Background, Assessment, Recommendation.
RECALL: result=partial | hint=none | ref=Q2 | quote=I'm not sure of the third.
END-MOCK-ASSESSMENT-V1
"""

NOTES = """# Study notes — round 1

## Q1 — SBAR
- Correct, and the use you gave is the standard one.

## Q2 — early signs of sepsis
- You named fever and a raised heart rate. Also: raised breathing rate, new confusion, low blood pressure, mottled or cold skin, reduced urine output. Note that temperature can also be low.
"""


def prep_ws(tmp_path, *, plan=PLAN, direction=DIRECTION, cv=CV, enter=True):
    root = pathlib.Path(tmp_path) / "skill"
    (root / "modes").mkdir(parents=True, exist_ok=True)
    (root / "modes" / "prepare.md").write_text("# Mode: prepare (stub)\n", encoding="utf-8")
    ws = pathlib.Path(tmp_path) / "job-profiles" / "amara" / "prep" / "2026-11-18-band-5-nurse-uk"
    (ws / "mock").mkdir(parents=True)
    for name, text in (("direction.yaml", direction), ("cv.md", cv),
                       ("prep-plan.md", plan)):
        if text is not None:
            (ws / name).write_text(text, encoding="utf-8")
    if enter:
        with contextlib.redirect_stdout(io.StringIO()):
            enter_mode.main(["--workspace", str(ws), "--mode", "prepare",
                             "--skill-root", str(root)])
    return ws, root


def codes(findings):
    return sorted({f.split(":", 1)[0] for f in findings})


def plan_gate(ws, root):
    return check_prep_plan.run(ws, skill_root=root, vocab_scanner=F.no_vocab)


# ------------------------------------------------------------------ paths

def test_prep_workspace_lives_under_the_profile_not_applications(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path)
    ws = paths.prep_workspace("Amara Okafor", "Band 5 nurse UK", "2026-11-18")
    assert ws.parent.name == "prep" and ws.name == "2026-11-18-band-5-nurse-uk"


def test_latest_prep_plan_is_the_newest_session(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path)
    for date in ("2026-10-01", "2026-11-18"):
        ws = paths.prep_workspace("amara", "nurse", date)
        ws.mkdir(parents=True)
        (ws / paths.PREP_PLAN_NAME).write_text("# plan\n", encoding="utf-8")
    assert paths.latest_prep_plan("amara").parent.name == "2026-11-18-nurse"


def test_no_prep_session_means_no_plan(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path)
    assert paths.latest_prep_plan("nobody") is None


def test_paths_cli_refuses_a_mix_of_prep_and_posting(capsys):
    assert paths.main(["--name", "x", "--prep", "nurse", "--company", "NHS"]) == 2


# ------------------------------------------------------------------ the general plan

def test_a_grounded_general_plan_is_quiet(tmp_path):
    assert plan_gate(*prep_ws(tmp_path)) == []


def test_a_direction_reason_not_in_direction_yaml_fails(tmp_path):
    ws, root = prep_ws(tmp_path, plan=PLAN.replace('direction: "newly qualified"',
                                                   'direction: "ward manager"'))
    assert "PREP_WHY_NOT_IN_SOURCE" in codes(plan_gate(ws, root))


def test_a_posting_reason_in_a_session_with_no_posting_fails(tmp_path):
    ws, root = prep_ws(tmp_path, plan=PLAN.replace('direction: "newly qualified"',
                                                   'posting: "Band 5"'))
    assert "PREP_WHY_NO_SOURCE" in codes(plan_gate(ws, root))


def test_the_general_plan_is_read_from_the_workspace_root(tmp_path):
    ws, root = prep_ws(tmp_path)
    assert check_prep_plan.plan_path(ws) == ws / "prep-plan.md"


def test_a_role_play_or_case_topic_is_a_valid_practise_kind(tmp_path):
    ws, root = prep_ws(tmp_path, plan=PLAN.replace("- practise: self-study", "- practise: role-play"))
    assert plan_gate(ws, root) == []


def test_without_the_prepare_entry_the_mode_entry_finding_fires(tmp_path):
    ws, root = prep_ws(tmp_path, enter=False)
    assert "NO_MODE_ENTRY" in codes(plan_gate(ws, root))


# ------------------------------------------------------------------ drills

def drill_ws(tmp_path, *, transcript=TRANSCRIPT, assessment=ASSESSMENT, notes=NOTES):
    ws, root = prep_ws(tmp_path)
    (ws / "mock" / "transcript-1.md").write_text(transcript, encoding="utf-8")
    (ws / "mock" / "assessment-1.md").write_text(assessment, encoding="utf-8")
    if notes is not None:
        (ws / "mock" / "study-notes-1.md").write_text(notes, encoding="utf-8")
    return ws, root


def drill_gate(ws, root, n=1):
    return check_drill.run(ws, n, skill_root=root, vocab_scanner=F.no_vocab)


def test_an_honest_clinical_knowledge_drill_is_quiet(tmp_path):
    assert drill_gate(*drill_ws(tmp_path)) == []


def test_a_drill_needs_no_posting_coverage_or_provenance_block(tmp_path):
    ws, root = drill_ws(tmp_path)
    assert not (ws / "posting.yaml").exists()
    assert "MISSING_BLOCK" not in codes(drill_gate(ws, root))


def test_a_story_round_is_not_a_drill(tmp_path):
    ws, root = drill_ws(tmp_path, assessment=ASSESSMENT.replace(
        "ROUND-TYPE: knowledge", "ROUND-TYPE: behavioural"))
    assert "DRILL_ROUND_TYPE" in codes(drill_gate(ws, root))


def test_marking_the_partial_answer_from_the_interviewer_s_words_fails(tmp_path):
    ws, root = drill_ws(tmp_path, assessment=ASSESSMENT.replace(
        "quote=I'm not sure of the third.", "quote=Name three early signs of sepsis"))
    assert "QUOTE_NOT_IN_TRANSCRIPT" in codes(drill_gate(ws, root))


def test_a_drill_with_no_study_notes_fails(tmp_path):
    assert "NO_STUDY_NOTES" in codes(drill_gate(*drill_ws(tmp_path, notes=None)))


def test_a_missing_recall_row_fails(tmp_path):
    ws, root = drill_ws(tmp_path, assessment="\n".join(
        ln for ln in ASSESSMENT.splitlines() if "ref=Q2" not in ln))
    assert "NO_RECALL_ROW" in codes(drill_gate(ws, root))


def test_a_coding_drill_runs_through_the_same_runner_checks(tmp_path):
    ws, root = prep_ws(tmp_path)
    transcript = L.CODING_TRANSCRIPT.replace("round 2", "round 1")
    (ws / "mock" / "transcript-1.md").write_text(transcript, encoding="utf-8")
    assessment = L.CODING_ASSESSMENT.format(tests="all_passed", hint="nudge")
    assessment = assessment.replace("ROUND: 2", "ROUND: 1")
    (ws / "mock" / "assessment-1.md").write_text(assessment, encoding="utf-8")
    (ws / "mock" / "study-notes-1.md").write_text(L.STUDY_NOTES, encoding="utf-8")
    qdir = check_mock.code_dir(ws, 1, "Q1")
    qdir.mkdir(parents=True)
    (qdir / "cases.json").write_text(json.dumps(L.CASES), encoding="utf-8")
    (qdir / "solution.py").write_text(L.BUGGY, encoding="utf-8")
    run_mock_tests.run(qdir, f"{L.PY} solution.py")
    assert "TESTS_MISREPORTED" in codes(drill_gate(ws, root))


def test_drill_gate_receipt_and_missing_transcript_contract(tmp_path, capsys, monkeypatch):
    ws, root = drill_ws(tmp_path)
    monkeypatch.setattr(check_mock, "_default_scanner", lambda workspace: F.no_vocab)
    assert check_drill.main(["--workspace", str(ws), "--round", "1",
                             "--skill-root", str(root)]) == 0
    assert journal.read_receipts(ws, "check_drill")[-1]["verdict"] == "pass"
    assert check_drill.main(["--workspace", str(ws), "--round", "2",
                             "--skill-root", str(root)]) == 2
    assert journal.read_receipts(ws, "check_drill")[-1]["verdict"] == "could_not_run"
