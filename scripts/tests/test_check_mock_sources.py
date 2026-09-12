import datetime
import pathlib
import sys
import types

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_mock
import mock_fixtures as F

TODAY = datetime.date(2026, 8, 9)


def run(workspace, **kw):
    kw.setdefault("vocab_scanner", F.no_vocab)
    kw.setdefault("today", TODAY)
    kw.setdefault("skill_root", F.skill_root(workspace))
    return check_mock.run(workspace, 2, **kw)


SCRAPED = """  - id: Q4
    text: 讲一下 variational network 的展开步数怎么定的
    source: scraped
    source_site: nowcoder
    source_id: "ce23c4da4205"
    source_url: https://www.nowcoder.com/discuss/ce23c4da4205
    source_time: "2026-08-03T11:12:22"
    entity_country: NL
    country_named_in_post: true
    use: question
    asked: false
"""


def with_scraped(**overrides):
    """The quiet question log plus one well-formed scraped row, then edits."""
    text = F.QUESTION_LOG.replace("rejected:", SCRAPED + "rejected:")
    for old, new in overrides.items():
        text = text.replace(old.replace("__", " "), new)
    return text


# ---------------------------------------------------------------- the quiet case

def test_a_well_formed_scraped_row_is_quiet(tmp_path):
    findings = run(F.build(tmp_path, question_log=with_scraped()))
    assert findings == []


def test_a_generated_question_needs_no_source_id(tmp_path):
    """Cry-wolf guard: the scraped rules must not fire on generated questions."""
    findings = run(F.build(tmp_path))
    assert not [f for f in findings if f.startswith(("NO_SOURCE_ID:", "NO_SOURCE_TIME:"))]


# ---------------------------------------------------------------- question-log.yaml

def test_a_missing_question_log_is_a_finding_not_an_exit_2(tmp_path):
    ws = F.build(tmp_path)
    (ws / "mock" / "question-log.yaml").unlink()
    findings = run(ws)
    assert any(f.startswith("NO_QUESTION_LOG:") for f in findings)


def test_a_scraped_question_without_a_source_id_fails(tmp_path):
    text = with_scraped().replace('    source_id: "ce23c4da4205"\n', "")
    findings = run(F.build(tmp_path, question_log=text))
    assert any(f.startswith("NO_SOURCE_ID:") and "Q4" in f for f in findings)


def test_a_scraped_question_without_a_time_fails(tmp_path):
    text = with_scraped().replace('    source_time: "2026-08-03T11:12:22"\n', "")
    findings = run(F.build(tmp_path, question_log=text))
    assert any(f.startswith("NO_SOURCE_TIME:") and "Q4" in f for f in findings)


def test_an_unparseable_time_fails(tmp_path):
    text = with_scraped().replace('"2026-08-03T11:12:22"', '"last spring"')
    findings = run(F.build(tmp_path, question_log=text))
    assert any(f.startswith("BAD_SOURCE_TIME:") for f in findings)


def test_a_year_old_post_may_not_be_quoted_as_a_specific_question(tmp_path):
    text = with_scraped().replace('"2026-08-03T11:12:22"', '"2025-01-04T09:30:27"')
    findings = run(F.build(tmp_path, question_log=text))
    assert any(f.startswith("STALE_SPECIFIC:") and "Q4" in f for f in findings)


def test_the_same_year_old_post_used_for_shape_is_quiet(tmp_path):
    text = with_scraped().replace('"2026-08-03T11:12:22"', '"2025-01-04T09:30:27"')
    text = text.replace("    use: question\n", "    use: shape\n")
    findings = run(F.build(tmp_path, question_log=text))
    assert not [f for f in findings if f.startswith("STALE_SPECIFIC:")]


def test_the_country_rule_fires_on_a_same_name_different_entity_post(tmp_path):
    """The ASML case: company matches, content is real, the process is the wrong one."""
    text = with_scraped().replace("    entity_country: NL\n", "    entity_country: CN\n")
    text = text.replace("    country_named_in_post: true\n",
                        "    country_named_in_post: false\n")
    findings = run(F.build(tmp_path, question_log=text))
    assert any(f.startswith("WRONG_COUNTRY:") and "Q4" in f for f in findings)


def test_a_post_that_names_the_posting_country_itself_is_quiet(tmp_path):
    text = with_scraped().replace("    entity_country: NL\n", "    entity_country: CN\n")
    findings = run(F.build(tmp_path, question_log=text))
    assert not [f for f in findings if f.startswith("WRONG_COUNTRY:")]


def test_a_missing_entity_country_fails(tmp_path):
    text = with_scraped().replace("    entity_country: NL\n", "")
    findings = run(F.build(tmp_path, question_log=text))
    assert any(f.startswith("NO_ENTITY_COUNTRY:") for f in findings)


def test_a_missing_posting_country_fails(tmp_path):
    text = F.QUESTION_LOG.replace("posting_country: NL\n", "")
    findings = run(F.build(tmp_path, question_log=text))
    assert any(f.startswith("NO_POSTING_COUNTRY:") for f in findings)


def test_a_scraped_question_with_no_use_field_fails(tmp_path):
    """`use:` decides whether the 12-month rule applies at all. Absent, the staleness
    check silently does not run, which is the shape of bug this gate exists to stop."""
    text = with_scraped().replace("    use: question\n", "")
    findings = run(F.build(tmp_path, question_log=text))
    assert any(f.startswith("UNKNOWN_USE:") and "Q4" in f for f in findings)


def test_an_invented_use_value_fails(tmp_path):
    text = with_scraped().replace("    use: question\n", "    use: maybe\n")
    findings = run(F.build(tmp_path, question_log=text))
    assert any(f.startswith("UNKNOWN_USE:") for f in findings)


def test_a_question_log_with_no_questions_fails(tmp_path):
    """A round with no logged questions has no record of where anything came from."""
    findings = run(F.build(tmp_path, question_log="round: 2\nposting_country: NL\n"
                                                  "questions: []\n"))
    assert any(f.startswith("QUESTION_LOG_EMPTY:") for f in findings)


def test_an_unknown_question_source_fails(tmp_path):
    text = F.QUESTION_LOG.replace("source: generated", "source: invented", 1)
    findings = run(F.build(tmp_path, question_log=text))
    assert any(f.startswith("UNKNOWN_QUESTION_SOURCE:") for f in findings)


def test_user_supplied_questions_need_no_fabricated_scraping_metadata(tmp_path):
    text = F.QUESTION_LOG.replace("source: generated", "source: user-provided")
    findings = run(F.build(tmp_path, question_log=text))
    assert not findings, findings


def test_an_unknown_rejection_reason_fails(tmp_path):
    text = F.QUESTION_LOG.replace("reason: wrong_country", "reason: seemed_off")
    findings = run(F.build(tmp_path, question_log=text))
    assert any(f.startswith("UNKNOWN_REJECT_REASON:") for f in findings)


def test_the_advertising_rejection_reason_is_accepted(tmp_path):
    """Two posts in the source probe were commercial pitches dressed as 面经."""
    text = F.QUESTION_LOG.replace("reason: wrong_country", "reason: advertising")
    findings = run(F.build(tmp_path, question_log=text))
    assert not [f for f in findings if f.startswith("UNKNOWN_REJECT_REASON:")]


def test_unreadable_yaml_is_reported_not_crashed(tmp_path):
    findings = run(F.build(tmp_path, question_log="questions: [unclosed\n"))
    assert any(f.startswith("QUESTION_LOG_UNPARSEABLE:") for f in findings)


# ---------------------------------------------------------------- answer-bank.md

def test_an_answer_bank_entry_without_a_source_line_fails(tmp_path):
    text = F.ANSWER_BANK.replace(
        '- source: profile.yaml:experience[0].bullets[2] — "rewrote the recon loop for GPU batching"\n',
        "",
    )
    findings = run(F.build(tmp_path, answer_bank=text))
    assert any(f.startswith("ANSWER_NO_SOURCE:") for f in findings)


def test_an_empty_source_line_fails(tmp_path):
    text = F.ANSWER_BANK.replace(
        '- source: profile.yaml:experience[0].bullets[2] — "rewrote the recon loop for GPU batching"',
        "- source:",
    )
    findings = run(F.build(tmp_path, answer_bank=text))
    assert any(f.startswith("ANSWER_NO_SOURCE:") for f in findings)


def test_a_session_answer_source_is_accepted(tmp_path):
    text = F.ANSWER_BANK.replace(
        '- source: profile.yaml:experience[0].bullets[2] — "rewrote the recon loop for GPU batching"',
        "- source: session-answer 2026-08-09 — mock/transcript-2.md#Q2",
    )
    findings = run(F.build(tmp_path, answer_bank=text))
    assert not [f for f in findings if f.startswith("ANSWER_NO_SOURCE:")]


def test_an_answer_bank_with_no_entries_fails(tmp_path):
    """A file that exists but banks nothing is the same defect as no file, and it is
    the likelier one: the model writes the heading and stops."""
    findings = run(F.build(tmp_path, answer_bank="# Answer bank\n\nnothing yet\n"))
    assert any(f.startswith("NO_ANSWER_BANK_ENTRIES:") for f in findings)


def test_a_missing_answer_bank_fails(tmp_path):
    ws = F.build(tmp_path)
    (ws.parents[1] / "answer-bank.md").unlink()
    findings = run(ws)
    assert any(f.startswith("NO_ANSWER_BANK:") for f in findings)


def test_the_answer_bank_default_comes_from_paths(tmp_path):
    """paths.py owns the layout. If this gate re-derived it, a change to the profile
    shape would leave the answer-bank check silently reading the wrong file."""
    import paths
    ws = F.build(tmp_path)
    assert check_mock._answer_bank_default(ws) == paths.answer_bank_of(ws)
    assert check_mock._answer_bank_default(ws).exists()


def test_an_explicit_answer_bank_path_is_honoured(tmp_path):
    ws = F.build(tmp_path)
    elsewhere = tmp_path / "elsewhere.md"
    elsewhere.write_text(F.ANSWER_BANK, encoding="utf-8")
    (ws.parents[1] / "answer-bank.md").unlink()
    assert run(ws, answer_bank=elsewhere) == []


# ---------------------------------------------------------------- banned vocabulary

def test_banned_vocabulary_findings_are_passed_through(tmp_path):
    def scanner(text, source):
        return [f"BANNED_VOCAB: {source}: 'strong candidate'"] if "assessment" in source else []

    findings = check_mock.run(F.build(tmp_path), 2, today=TODAY, vocab_scanner=scanner)
    assert any(f.startswith("BANNED_VOCAB:") for f in findings)


def test_the_vocabulary_scanner_sees_the_candidate_facing_files(tmp_path):
    seen = []

    def scanner(text, source):
        seen.append(pathlib.Path(source).name)
        return []

    ws = F.build(tmp_path)
    (ws / "mock" / "cheatsheet.md").write_text("# Cheatsheet\n", encoding="utf-8")
    run(ws, vocab_scanner=scanner)
    assert "assessment-2.md" in seen
    assert "cheatsheet.md" in seen


def _argv(ws):
    return ["--workspace", str(ws), "--round", "2", "--today", "2026-08-09",
            "--skill-root", str(F.skill_root(ws))]


def test_an_absent_lint_module_is_exit_2_never_a_silent_skip(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(check_mock, "_default_scanner", lambda: None)
    ws = F.build(tmp_path)
    code = check_mock.main(_argv(ws))
    assert code == 2
    assert "lint_no_prediction" in capsys.readouterr().err


def test_an_absent_lint_module_still_leaves_a_could_not_run_receipt(tmp_path, monkeypatch):
    import journal
    monkeypatch.setattr(check_mock, "_default_scanner", lambda: None)
    ws = F.build(tmp_path)
    check_mock.main(_argv(ws))
    receipts = journal.read_receipts(ws, "check_mock")
    assert len(receipts) == 1
    assert receipts[0]["verdict"] == "could_not_run"


def test_a_renamed_scan_function_is_exit_2_not_a_traceback(tmp_path, monkeypatch, capsys):
    """The adapter resolves scan_text with getattr. If Plan 2 renames it, attribute
    access would raise AttributeError inside main() — traceback, exit 1 from Python,
    no receipt, no stable code. That is exactly 'a check that did not run looking like
    a check that failed for some other reason'."""
    stub = types.ModuleType("lint_no_prediction")      # no scan_text attribute
    monkeypatch.setitem(sys.modules, "lint_no_prediction", stub)
    assert check_mock._default_scanner() is None
    ws = F.build(tmp_path)
    code = check_mock.main(_argv(ws))
    assert code == 2
    assert "lint_no_prediction" in capsys.readouterr().err


def test_run_resolves_the_scanner_itself_when_not_injected(tmp_path, monkeypatch):
    monkeypatch.setattr(check_mock, "_default_scanner", lambda: F.no_vocab)
    ws = F.build(tmp_path)
    assert check_mock.run(ws, 2, today=TODAY, skill_root=F.skill_root(ws)) == []
