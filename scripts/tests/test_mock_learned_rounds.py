"""Knowledge and coding rounds: the runner, the gate's RECALL/SOLVE checks, the prep plan.

Same discipline as the rest of the mock suite: build a quiet, passing round, then
break exactly one thing per test.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_mock
import check_prep_plan
import mock_fixtures as F
import run_mock_tests

PY = f'"{sys.executable}"'

# ------------------------------------------------------------------ coding fixture

CODING_TRANSCRIPT = """# Mock transcript — round 2
Round type: coding
Market: nl
Family: swe
Persona: Pieter Bakker, backend lead — wants the approach before the code

## Q1 — Given a list of integers, print the length of the longest strictly increasing run.
**Interviewer:** Given a list of integers, print the length of the longest strictly increasing run. Input: n, then the n numbers.
**Candidate:** I'd walk the list once, keep the current run length and the best so far, so it's O(n) time and O(1) space.
**Candidate:** Can I get a small hint about the reset?
**Hint (nudge):** What should the current run be right after a number that is not larger than the previous one?
**Candidate:** It goes back to one. I've saved it as solution.py.
"""

CODING_ASSESSMENT = """# Mock assessment — round 2

MOCK-ASSESSMENT-V1
ROUND: 2
ROUND-TYPE: coding
MARKET: nl
FAMILY: swe
FINDINGS: none
SOLVE: tests={tests} | complexity=stated_correct | hint={hint} | ref=Q1 | quote=so it's O(n) time and O(1) space
COVERAGE: status=not_asked | must_have=MRI reconstruction pipelines in a clinical setting
COVERAGE: status=not_asked | must_have=Regulatory documentation (MDR)
SHAPE: status=rehearsed | round_name=technical interview — live coding
END-MOCK-ASSESSMENT-V1

MOCK-PROVENANCE-V1
ROUND: 2
FINDINGS: none
END-MOCK-PROVENANCE-V1
"""

CODING_LOG = """round: 2
posting_country: NL
questions:
  - id: Q1
    text: Longest strictly increasing run.
    source: generated
    asked: true
"""

CASES = [
    {"name": "example", "stdin": "5\n1 2 3 1 2\n", "expected": "3"},
    {"name": "empty input", "stdin": "0\n\n", "expected": "0"},
    {"name": "all equal", "stdin": "3\n7 7 7\n", "expected": "1"},
]

# Correct except on empty input, where it prints 1 — the bug the hidden cases exist for.
BUGGY = """import sys
data = sys.stdin.read().split()
n, a = int(data[0]), list(map(int, data[1:]))
best = cur = 1
for i in range(1, n):
    cur = cur + 1 if a[i] > a[i - 1] else 1
    best = max(best, cur)
print(best)
"""
FIXED = BUGGY.replace("best = cur = 1", "best = cur = 1 if n else 0")

STUDY_NOTES = """# Study notes — round 2

## Q1 — longest strictly increasing run
- correct approach: one pass, current run and best run, O(n) time, O(1) space.
- what your answer missed: the empty list. `best = cur = 1` prints 1 for no numbers.
"""


def coding_ws(tmp_path, *, tests="some_failed", hint="nudge", solution=BUGGY, run=True,
              notes=STUDY_NOTES, transcript=CODING_TRANSCRIPT):
    ws = F.build(tmp_path, transcript=transcript,
                 assessment=CODING_ASSESSMENT.format(tests=tests, hint=hint),
                 question_log=CODING_LOG)
    (ws / "mock" / "answer-guide.md").unlink()
    qdir = check_mock.code_dir(ws, 2, "Q1")
    qdir.mkdir(parents=True)
    (qdir / "cases.json").write_text(json.dumps(CASES), encoding="utf-8")
    (qdir / "solution.py").write_text(solution, encoding="utf-8")
    if run:
        run_mock_tests.run(qdir, f"{PY} solution.py")
    if notes is not None:
        (ws / "mock" / "study-notes-2.md").write_text(notes, encoding="utf-8")
    return ws


def gate(ws, **kw):
    kw.setdefault("vocab_scanner", F.no_vocab)
    kw.setdefault("skill_root", F.skill_root(ws))
    return check_mock.run(ws, 2, **kw)


def codes(findings):
    return sorted({f.split(":", 1)[0] for f in findings})


# ------------------------------------------------------------------ the runner

def test_runner_catches_the_empty_input_bug(tmp_path):
    qdir = tmp_path / "Q1"
    qdir.mkdir()
    (qdir / "cases.json").write_text(json.dumps(CASES), encoding="utf-8")
    (qdir / "solution.py").write_text(BUGGY, encoding="utf-8")
    result = run_mock_tests.run(qdir, f"{PY} solution.py")
    assert (result["passed"], result["total"], result["status"]) == (2, 3, "some_failed")
    failed = [c["name"] for c in result["cases"] if not c["passed"]]
    assert failed == ["empty input"]
    assert json.loads((qdir / "result.json").read_text())["status"] == "some_failed"


def test_runner_passes_a_correct_solution(tmp_path):
    qdir = tmp_path / "Q1"
    qdir.mkdir()
    (qdir / "cases.json").write_text(json.dumps(CASES), encoding="utf-8")
    (qdir / "solution.py").write_text(FIXED, encoding="utf-8")
    assert run_mock_tests.run(qdir, f"{PY} solution.py")["status"] == "all_passed"


def test_runner_records_a_timeout_as_a_failed_case(tmp_path):
    qdir = tmp_path / "Q1"
    qdir.mkdir()
    (qdir / "cases.json").write_text(json.dumps(CASES[:1]), encoding="utf-8")
    (qdir / "solution.py").write_text("while True:\n    pass\n", encoding="utf-8")
    result = run_mock_tests.run(qdir, f"{PY} solution.py", timeout=0.5)
    assert result["cases"][0]["timed_out"] and result["status"] == "none_passed"


def test_a_failed_build_is_a_result_not_a_crash(tmp_path):
    qdir = tmp_path / "Q1"
    qdir.mkdir()
    (qdir / "cases.json").write_text(json.dumps(CASES), encoding="utf-8")
    (qdir / "solution.py").write_text(FIXED, encoding="utf-8")
    result = run_mock_tests.run(qdir, f"{PY} solution.py", build="exit 3")
    assert not result["build_ok"] and result["status"] == "none_passed"


def test_a_rebuilt_binary_is_part_of_the_fresh_identity(tmp_path):
    """A resubmission rewrites the build output; the result must describe that one."""
    qdir = tmp_path / "Q1"
    qdir.mkdir()
    (qdir / "cases.json").write_text(json.dumps(CASES), encoding="utf-8")
    (qdir / "solution.py").write_text(BUGGY, encoding="utf-8")
    build = f"{PY} -c \"import shutil; shutil.copy('solution.py', 'built.py')\""
    run_mock_tests.run(qdir, f"{PY} built.py", build=build)
    (qdir / "solution.py").write_text(FIXED, encoding="utf-8")
    result = run_mock_tests.run(qdir, f"{PY} built.py", build=build)
    assert result["status"] == "all_passed"
    import journal
    for name, digest in result["solution_sha256"].items():
        assert journal.sha256_file(qdir / name) == digest, f"{name} recorded stale"


def test_runner_without_cases_cannot_run(tmp_path, capsys):
    qdir = tmp_path / "Q1"
    qdir.mkdir()
    (qdir / "solution.py").write_text(FIXED, encoding="utf-8")
    assert run_mock_tests.main(["--dir", str(qdir), "--cmd", "true"]) == 2
    assert "cases.json" in capsys.readouterr().err


def test_output_comparison_ignores_trailing_whitespace_only():
    assert run_mock_tests.normalize_output("3  \n\n") == run_mock_tests.normalize_output("3")
    assert run_mock_tests.normalize_output("3 4") != run_mock_tests.normalize_output("34")


# ------------------------------------------------------------------ coding round gate

def test_an_honest_coding_round_is_quiet(tmp_path):
    assert gate(coding_ws(tmp_path)) == []


def test_a_coding_round_needs_no_bands_and_no_answer_guide(tmp_path):
    findings = gate(coding_ws(tmp_path))
    assert "NO_BANDS" not in codes(findings)
    assert "NO_ANSWER_GUIDE" not in codes(findings)


def test_claiming_a_pass_the_runner_did_not_record_fails(tmp_path):
    assert "TESTS_MISREPORTED" in codes(gate(coding_ws(tmp_path, tests="all_passed")))


def test_claiming_a_pass_with_no_run_at_all_fails(tmp_path):
    assert "NO_TEST_RESULT" in codes(gate(coding_ws(tmp_path, tests="all_passed", run=False)))


def test_not_run_with_no_result_is_honest(tmp_path):
    assert gate(coding_ws(tmp_path, tests="not_run", run=False)) == []


def test_editing_the_solution_after_the_run_makes_the_result_stale(tmp_path):
    ws = coding_ws(tmp_path)
    (check_mock.code_dir(ws, 2, "Q1") / "solution.py").write_text(FIXED, encoding="utf-8")
    assert "STALE_TEST_RESULT" in codes(gate(ws))


def test_rewriting_the_cases_after_the_run_makes_the_result_stale(tmp_path):
    ws = coding_ws(tmp_path)
    (check_mock.code_dir(ws, 2, "Q1") / "cases.json").write_text(
        json.dumps(CASES[:1]), encoding="utf-8")
    assert "STALE_TEST_RESULT" in codes(gate(ws))


def test_a_hand_edited_status_field_is_not_believed(tmp_path):
    ws = coding_ws(tmp_path, tests="all_passed")
    path = check_mock.code_dir(ws, 2, "Q1") / "result.json"
    data = json.loads(path.read_text())
    data["status"] = "all_passed"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert "TESTS_MISREPORTED" in codes(gate(ws))


def test_under_reporting_the_hint_fails(tmp_path):
    assert "HINT_MISMATCH" in codes(gate(coding_ws(tmp_path, hint="none")))


def test_a_misspelt_hint_level_is_reported(tmp_path):
    ws = coding_ws(tmp_path, transcript=CODING_TRANSCRIPT.replace("Hint (nudge)",
                                                                  "Hint (small)"),
                   hint="none")
    assert "UNKNOWN_HINT_LEVEL" in codes(gate(ws))


def test_a_question_with_no_solve_row_fails(tmp_path):
    transcript = CODING_TRANSCRIPT + (
        "\n## Q2 — What if the list does not fit in memory?\n"
        "**Interviewer:** What if the list does not fit in memory?\n"
        "**Candidate:** It streams, so nothing changes.\n")
    ws = coding_ws(tmp_path, transcript=transcript,
                   notes=STUDY_NOTES + "\n## Q2 — streaming\n- it streams.\n")
    assert "NO_SOLVE_ROW" in codes(gate(ws))


def test_missing_study_notes_fail(tmp_path):
    assert "NO_STUDY_NOTES" in codes(gate(coding_ws(tmp_path, notes=None)))


def test_study_notes_must_cover_every_question(tmp_path):
    ws = coding_ws(tmp_path, notes="# Study notes\n\n## Q9 — something else\n- x\n")
    assert "STUDY_NOTE_MISSING" in codes(gate(ws))


def test_a_solve_row_in_a_knowledge_round_fails(tmp_path):
    ws = coding_ws(tmp_path)
    path = ws / "mock" / "assessment-2.md"
    path.write_text(path.read_text().replace("ROUND-TYPE: coding", "ROUND-TYPE: knowledge"))
    assert "RECORD_WRONG_ROUND" in codes(gate(ws))


def test_code_in_study_notes_is_not_scanned_as_prose(tmp_path):
    import lint_no_prediction
    ws = coding_ws(tmp_path, notes=STUDY_NOTES + "\n```python\nmid = (lo + hi) % 2 + 1/2\n```\n")
    corpus = lint_no_prediction.capture_corpus(ws)
    scanner = lambda text, source: lint_no_prediction.scan_text(text, source, corpus)  # noqa: E731
    assert gate(ws, vocab_scanner=scanner) == []


def test_prose_in_study_notes_is_still_scanned(tmp_path):
    import lint_no_prediction
    ws = coding_ws(tmp_path, notes=STUDY_NOTES + "\nYou have a 70% chance of passing.\n")
    corpus = lint_no_prediction.capture_corpus(ws)
    scanner = lambda text, source: lint_no_prediction.scan_text(text, source, corpus)  # noqa: E731
    assert gate(ws, vocab_scanner=scanner) != []


def test_a_story_round_still_requires_bands(tmp_path):
    ws = F.build(tmp_path, assessment="\n".join(
        line for line in F.ASSESSMENT.splitlines() if not line.startswith("BAND:")))
    assert "NO_BANDS" in codes(gate(ws))


# ------------------------------------------------------------------ knowledge round

KNOWLEDGE_TRANSCRIPT = """# Mock transcript — round 2
Round type: knowledge
Market: cn
Family: swe

## Q1 — 事务的隔离级别有哪些？可重复读能防止幻读吗？
**Interviewer:** 事务的隔离级别有哪些？可重复读能防止幻读吗？
**Candidate:** 读未提交、读已提交、可重复读、串行化。可重复读能完全防止幻读。

## Q2 — 为什么 B+ 树适合做数据库索引？
**Interviewer:** 为什么 B+ 树适合做数据库索引？
**Candidate:** 能给个提示吗？
**Hint (approach):** 想一想磁盘页和范围查询。
**Candidate:** 节点大、树矮，磁盘 IO 少；叶子节点连成链表，范围查询快。
"""

KNOWLEDGE_ASSESSMENT = """MOCK-ASSESSMENT-V1
ROUND: 2
ROUND-TYPE: knowledge
MARKET: cn
FAMILY: swe
FINDINGS: none
RECALL: result=partial | hint=none | ref=Q1 | quote=可重复读能完全防止幻读。
RECALL: result=correct | hint=approach | ref=Q2 | quote=叶子节点连成链表，范围查询快。
COVERAGE: status=not_asked | must_have=MRI reconstruction pipelines in a clinical setting
COVERAGE: status=not_asked | must_have=Regulatory documentation (MDR)
SHAPE: status=rehearsed | round_name=技术一面 — 基础知识
END-MOCK-ASSESSMENT-V1

MOCK-PROVENANCE-V1
ROUND: 2
FINDINGS: none
END-MOCK-PROVENANCE-V1
"""

KNOWLEDGE_NOTES = """# 学习笔记 — 第 2 轮

## Q1 — 隔离级别与幻读
- 正确答案：四个级别没错；但标准的可重复读并不保证防止幻读，InnoDB 靠 next-key lock 在多数情况下避免。

## Q2 — B+ 树
- 正确答案：你的回答覆盖了要点。
"""


def knowledge_ws(tmp_path, assessment=KNOWLEDGE_ASSESSMENT):
    ws = F.build(tmp_path, transcript=KNOWLEDGE_TRANSCRIPT, assessment=assessment,
                 question_log=CODING_LOG.replace("Longest strictly increasing run.", "隔离级别")
                 + "  - id: Q2\n    text: B+ 树\n    source: generated\n    asked: true\n")
    (ws / "mock" / "study-notes-2.md").write_text(KNOWLEDGE_NOTES, encoding="utf-8")
    return ws


def test_an_honest_knowledge_round_is_quiet(tmp_path):
    assert gate(knowledge_ws(tmp_path)) == []


def test_a_knowledge_round_may_be_the_first_with_no_answer_bank(tmp_path):
    ws = knowledge_ws(tmp_path)
    bank = ws.parents[1] / "answer-bank.md"
    bank.unlink()
    assert gate(ws, answer_bank=bank) == []


def test_a_recall_quote_from_the_interviewer_fails(tmp_path):
    ws = knowledge_ws(tmp_path, KNOWLEDGE_ASSESSMENT.replace(
        "quote=可重复读能完全防止幻读。", "quote=可重复读能防止幻读吗？"))
    assert "QUOTE_NOT_IN_TRANSCRIPT" in codes(gate(ws))


def test_an_unknown_recall_result_fails(tmp_path):
    ws = knowledge_ws(tmp_path, KNOWLEDGE_ASSESSMENT.replace("result=partial", "result=7"))
    assert "UNKNOWN_VALUE" in codes(gate(ws))


def test_a_missing_recall_row_fails(tmp_path):
    ws = knowledge_ws(tmp_path, "\n".join(
        line for line in KNOWLEDGE_ASSESSMENT.splitlines() if "ref=Q2" not in line))
    assert "NO_RECALL_ROW" in codes(gate(ws))


# ------------------------------------------------------------------ prep plan

PLAN = """# Preparation plan — ASML, MR Reconstruction Engineer

## MRI reconstruction fundamentals
- why: posting: "MRI reconstruction pipelines in a clinical setting"
- be able to: explain k-space sampling, why undersampling aliases, and how coil sensitivities enter SENSE
- practise: knowledge

## Arrays and two pointers
- why: family: swe — coding round
- be able to: solve a linear-scan problem aloud, state its complexity, and name the empty-input case
- practise: coding
"""


def plan_ws(tmp_path, plan=PLAN):
    ws = F.build(tmp_path)
    (ws / "mock" / "prep-plan.md").write_text(plan, encoding="utf-8")
    return ws


def plan_gate(ws):
    return check_prep_plan.run(ws, skill_root=F.skill_root(ws), vocab_scanner=F.no_vocab)


def test_a_grounded_prep_plan_is_quiet(tmp_path):
    assert plan_gate(plan_ws(tmp_path)) == []


def test_a_posting_reason_the_posting_does_not_contain_fails(tmp_path):
    ws = plan_ws(tmp_path, PLAN.replace("MRI reconstruction pipelines in a clinical setting",
                                        "Kubernetes in production"))
    assert "PREP_WHY_NOT_IN_SOURCE" in codes(plan_gate(ws))


def test_a_topic_with_no_reason_fails(tmp_path):
    ws = plan_ws(tmp_path, PLAN.replace("- why: family: swe — coding round\n", ""))
    assert "PREP_NO_WHY" in codes(plan_gate(ws))


def test_a_topic_with_no_ability_fails(tmp_path):
    ws = plan_ws(tmp_path, PLAN.replace(
        "- be able to: solve a linear-scan problem aloud, state its complexity, and name "
        "the empty-input case\n", ""))
    assert "PREP_NO_ABILITY" in codes(plan_gate(ws))


def test_a_cv_reason_needs_the_cv(tmp_path):
    ws = plan_ws(tmp_path, PLAN.replace("family: swe — coding round", 'cv: "Kotlin"'))
    assert "PREP_WHY_NO_SOURCE" in codes(plan_gate(ws))


def test_missing_plan_cannot_run(tmp_path, capsys):
    ws = F.build(tmp_path)
    assert check_prep_plan.main(["--workspace", str(ws),
                                 "--skill-root", str(F.skill_root(ws))]) == 2
    assert "NO_PREP_PLAN" in capsys.readouterr().err


def test_prep_gate_writes_a_receipt(tmp_path, monkeypatch):
    import journal
    ws = plan_ws(tmp_path)
    monkeypatch.setattr(check_mock, "_default_scanner", lambda workspace: F.no_vocab)
    assert check_prep_plan.main(["--workspace", str(ws),
                                 "--skill-root", str(F.skill_root(ws))]) == 0
    assert journal.read_receipts(ws, "check_prep_plan")[-1]["verdict"] == "pass"
