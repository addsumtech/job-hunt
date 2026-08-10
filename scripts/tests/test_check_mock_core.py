import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_mock
import journal
import mock_fixtures as F


def run(workspace, **kw):
    kw.setdefault("vocab_scanner", F.no_vocab)
    kw.setdefault("skill_root", F.skill_root(workspace))
    return check_mock.run(workspace, 2, **kw)


def argv(workspace):
    return ["--workspace", str(workspace), "--round", "2", "--today", "2026-08-09",
            "--skill-root", str(F.skill_root(workspace))]


# ---------------------------------------------------------------- the quiet case

def test_a_clean_workspace_produces_no_findings(tmp_path):
    assert run(F.build(tmp_path)) == []


def test_a_clean_workspace_exits_zero_and_prints_nothing(tmp_path, capsys, monkeypatch):
    ws = F.build(tmp_path)
    monkeypatch.setattr(check_mock, "_default_scanner", lambda: F.no_vocab)
    code = check_mock.main(argv(ws))
    assert code == 0
    assert capsys.readouterr().out == ""


def test_a_clean_run_writes_exactly_one_pass_receipt(tmp_path, monkeypatch):
    ws = F.build(tmp_path)
    monkeypatch.setattr(check_mock, "_default_scanner", lambda: F.no_vocab)
    check_mock.main(argv(ws))
    receipts = journal.read_receipts(ws, "check_mock")
    assert len(receipts) == 1
    record = receipts[0]
    assert record["verdict"] == "pass"
    assert "mock/assessment-2.md" in record["input_hashes"]
    assert "mock/transcript-2.md" in record["input_hashes"]


def test_the_receipt_is_stamped_with_the_mode_that_was_entered(tmp_path, monkeypatch):
    """journal.receipt reads the mode from the journal's last mode_entry. If that
    regresses, every interview receipt silently says 'apply' and the journal stops
    being able to answer 'which mode ran this?'."""
    ws = F.build(tmp_path)
    monkeypatch.setattr(check_mock, "_default_scanner", lambda: F.no_vocab)
    check_mock.main(argv(ws))
    assert journal.read_receipts(ws, "check_mock")[0]["mode"] == "interview"


# ---------------------------------------------------------------- the mode-entry backstop

def test_no_mode_entry_fails(tmp_path):
    """modes/interview.md is layer 1.5 — loaded on entering the mode, not 'if
    relevant'. The journal record is the only thing that reports it if it was not."""
    findings = run(F.build(tmp_path, enter=False))
    assert any(f.startswith("NO_MODE_ENTRY:") for f in findings)


def test_an_edited_mode_file_invalidates_the_entry(tmp_path):
    ws = F.build(tmp_path)
    (F.skill_root(ws) / "modes" / "interview.md").write_text(
        "# Mode: interview\n\nrewritten\n", encoding="utf-8")
    findings = run(ws)
    assert any(f.startswith("MODE_FILE_CHANGED:") for f in findings)


def test_an_unedited_entered_mode_is_quiet(tmp_path):
    findings = run(F.build(tmp_path))
    assert not [f for f in findings if f.startswith(("NO_MODE_ENTRY:",
                                                     "MODE_FILE_CHANGED:"))]


# ---------------------------------------------------------------- missing inputs

def test_a_missing_assessment_is_exit_2_not_a_failure(tmp_path, capsys, monkeypatch):
    ws = F.build(tmp_path)
    (ws / "mock" / "assessment-2.md").unlink()
    monkeypatch.setattr(check_mock, "_default_scanner", lambda: F.no_vocab)
    code = check_mock.main(argv(ws))
    assert code == 2
    assert "assessment-2.md" in capsys.readouterr().err


def test_a_missing_input_still_writes_exactly_one_could_not_run_receipt(
    tmp_path, monkeypatch
):
    ws = F.build(tmp_path)
    (ws / "mock" / "transcript-2.md").unlink()
    monkeypatch.setattr(check_mock, "_default_scanner", lambda: F.no_vocab)
    check_mock.main(argv(ws))
    receipts = journal.read_receipts(ws, "check_mock")
    assert len(receipts) == 1
    assert receipts[0]["verdict"] == "could_not_run"


def test_a_workspace_that_does_not_exist_is_exit_2_with_no_receipt(tmp_path, capsys):
    """The one documented exception to 'always leave a receipt': there is nowhere to
    append it to, and creating the directory to hold one would materialise a workspace
    on a typo."""
    missing = tmp_path / "nope"
    code = check_mock.main(["--workspace", str(missing), "--round", "2",
                            "--today", "2026-08-09"])
    assert code == 2
    assert str(missing) in capsys.readouterr().err
    assert not (missing / "journal.jsonl").exists()


def test_a_receipt_that_cannot_be_written_is_exit_2_not_exit_0(tmp_path, capsys,
                                                              monkeypatch):
    """A gate that exits 0 having written no receipt is indistinguishable from a gate
    nobody ran — which is the exact failure the receipt exists to prevent."""
    ws = F.build(tmp_path)
    monkeypatch.setattr(check_mock, "_default_scanner", lambda: F.no_vocab)

    def boom(*a, **kw):
        raise OSError("read-only file system")

    monkeypatch.setattr(check_mock.journal, "receipt", boom)
    code = check_mock.main(argv(ws))
    assert code == 2
    assert "RECEIPT_WRITE_FAILED" in capsys.readouterr().err


# ---------------------------------------------------------------- fail-closed parsing

def test_a_missing_provenance_block_is_reported_as_a_pass_that_never_ran(tmp_path):
    text = F.ASSESSMENT.split("MOCK-PROVENANCE-V1")[0]
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("MISSING_BLOCK: MOCK-PROVENANCE-V1") for f in findings)


def test_an_unreadable_block_is_a_parse_fail_not_a_silent_pass(tmp_path):
    text = F.ASSESSMENT.replace("ROUND-TYPE: technical", "ROUND-TYPE: technical | oops")
    text = text.replace("MARKET: nl\n", "")
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("PARSE_FAIL:") for f in findings)


# ---------------------------------------------------------------- the closed tag sets

def test_an_invented_tag_fails(tmp_path):
    text = F.ASSESSMENT.replace("tag=VAGUE-OUTCOME", "tag=WEAK-ANSWER")
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("UNKNOWN_TAG:") and "WEAK-ANSWER" in f for f in findings)


def test_a_provenance_tag_in_the_transcript_pass_fails(tmp_path):
    """Pass 1 does not hold interview-brief.md, so it cannot have decided this."""
    text = F.ASSESSMENT.replace("tag=VAGUE-OUTCOME", "tag=UNSOURCED-FACT")
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("WRONG_PASS:") and "UNSOURCED-FACT" in f for f in findings)


def test_a_shape_tag_in_the_provenance_pass_fails(tmp_path):
    text = F.ASSESSMENT.replace(
        "MOCK-PROVENANCE-V1\nROUND: 2\nFINDINGS: none",
        "MOCK-PROVENANCE-V1\nROUND: 2\n"
        "FINDING: tag=NO-OUTCOME | ref=Q2 | quote=It went really well after that.",
    )
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("WRONG_PASS:") and "NO-OUTCOME" in f for f in findings)


def test_all_four_contract_tags_are_accepted_in_their_own_pass(tmp_path):
    text = F.ASSESSMENT.replace(
        "FINDING: tag=VAGUE-OUTCOME | ref=Q2 | quote=It went really well after that.",
        "FINDING: tag=PROBE-COLLAPSE | ref=Q2 | quote=It went really well after that.",
    ).replace(
        "MOCK-PROVENANCE-V1\nROUND: 2\nFINDINGS: none",
        "MOCK-PROVENANCE-V1\nROUND: 2\n"
        "FINDING: tag=UNSOURCED-FACT | ref=Q1 | quote=then wrote DICOMs back to the PACS\n"
        "FINDING: tag=OVER-CLAIM | ref=Q1 | quote=I owned the offline recon pipeline\n"
        "FINDING: tag=CONTRADICTED | ref=Q3 | quote=I learned to profile before optimising.",
    )
    findings = run(F.build(tmp_path, assessment=text))
    assert not [f for f in findings if f.startswith(("UNKNOWN_TAG:", "WRONG_PASS:"))]


# ---------------------------------------------------------------- conditional tags

def test_a_dutch_only_tag_outside_the_dutch_market_fails(tmp_path):
    text = F.ASSESSMENT.replace("MARKET: nl", "MARKET: us").replace(
        "tag=VAGUE-OUTCOME", "tag=NO-REFLECTION")
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("TAG_NOT_APPLICABLE:") and "NO-REFLECTION" in f
               for f in findings)


def test_the_same_tag_in_the_dutch_market_is_quiet(tmp_path):
    text = F.ASSESSMENT.replace("tag=VAGUE-OUTCOME", "tag=NO-REFLECTION")
    findings = run(F.build(tmp_path, assessment=text))
    assert not [f for f in findings if f.startswith("TAG_NOT_APPLICABLE:")]


def test_a_sales_only_tag_outside_sales_fails(tmp_path):
    text = F.ASSESSMENT.replace("tag=VAGUE-OUTCOME", "tag=NO-NEXT-STEP")
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("TAG_NOT_APPLICABLE:") and "NO-NEXT-STEP" in f
               for f in findings)


# ---------------------------------------------------------------- no quote, no tag

def test_a_tag_without_a_quote_fails(tmp_path):
    text = F.ASSESSMENT.replace(
        "FINDING: tag=VAGUE-OUTCOME | ref=Q2 | quote=It went really well after that.",
        "FINDING: tag=VAGUE-OUTCOME | ref=Q2 | quote=",
    )
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("NO_QUOTE:") for f in findings)


def test_a_band_without_a_quote_fails(tmp_path):
    text = F.ASSESSMENT.replace(
        "BAND: dimension=outcome | value=asserted | ref=Q2 | "
        "quote=It went really well after that.",
        "BAND: dimension=outcome | value=asserted | ref=Q2 | quote=   ",
    )
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("NO_QUOTE:") for f in findings)


def test_an_invented_quote_fails(tmp_path):
    text = F.ASSESSMENT.replace(
        "quote=It went really well after that.",
        "quote=we cut the reconstruction time by 40%",
        1,
    )
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("QUOTE_NOT_IN_TRANSCRIPT:") for f in findings)


def test_a_rewrapped_quote_is_quiet(tmp_path):
    """The transcript wraps; the assessor's copy of the line must still count."""
    transcript = F.TRANSCRIPT.replace(
        "I replaced the per-slice loop with a batched GPU implementation. "
        "It went really well after that.",
        "I replaced the per-slice loop with a batched GPU implementation.\n"
        "It went really\n  well after that.",
    )
    findings = run(F.build(tmp_path, transcript=transcript))
    assert not [f for f in findings if f.startswith("QUOTE_NOT_IN_TRANSCRIPT:")]


def test_an_elided_quote_is_quiet(tmp_path):
    text = F.ASSESSMENT.replace(
        "quote=At the university hospital I owned the offline recon pipeline "
        "for a 3T scanner study",
        "quote=At the university hospital I owned ... for a 3T scanner study",
    )
    findings = run(F.build(tmp_path, assessment=text))
    assert not [f for f in findings if f.startswith("QUOTE_NOT_IN_TRANSCRIPT:")]


def test_a_reference_to_a_question_that_was_never_asked_fails(tmp_path):
    text = F.ASSESSMENT.replace("ref=Q2 | quote=It went", "ref=Q9 | quote=It went")
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("UNKNOWN_REF:") and "Q9" in f for f in findings)


def test_a_transcript_with_no_question_headings_says_so(tmp_path):
    """Without '## Q<n>' headings there is nothing to check ref= against, so the ref
    check would silently pass everything. The absence of the headings is the defect —
    modes/interview.md requires them — so it is named rather than tolerated."""
    transcript = F.TRANSCRIPT.replace("\n## Q", "\n### Q")
    findings = run(F.build(tmp_path, transcript=transcript))
    assert any(f.startswith("NO_QUESTION_HEADINGS:") for f in findings)


def test_an_ordinary_transcript_does_not_trigger_the_headings_finding(tmp_path):
    findings = run(F.build(tmp_path))
    assert not [f for f in findings if f.startswith("NO_QUESTION_HEADINGS:")]


# ---------------------------------------------------------------- bands

def test_the_flag_is_rejected_as_a_band_value(tmp_path):
    text = F.ASSESSMENT.replace("value=asserted", "value=contradicted")
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("NOT_A_BAND:") for f in findings)
    assert any("tag=CONTRADICTED" in f for f in findings)


def test_an_invented_band_fails(tmp_path):
    text = F.ASSESSMENT.replace("value=asserted", "value=excellent")
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("UNKNOWN_BAND:") for f in findings)


def test_a_numeric_band_fails(tmp_path):
    text = F.ASSESSMENT.replace("value=asserted", "value=3")
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("UNKNOWN_BAND:") for f in findings)


def test_an_invented_dimension_fails(tmp_path):
    text = F.ASSESSMENT.replace("dimension=outcome", "dimension=charisma")
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("UNKNOWN_DIMENSION:") for f in findings)


def test_a_provenance_dimension_fails_because_pass_1_cannot_decide_it(tmp_path):
    text = F.ASSESSMENT.replace("dimension=outcome", "dimension=provenance")
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("UNKNOWN_DIMENSION:") for f in findings)


# ---------------------------------------------------------------- headers

def test_a_round_mismatch_fails(tmp_path):
    text = F.ASSESSMENT.replace("ROUND: 2\nROUND-TYPE", "ROUND: 3\nROUND-TYPE")
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("ROUND_MISMATCH:") for f in findings)


def test_a_non_numeric_round_fails(tmp_path):
    """`ROUND: two` cannot be compared to --round, so it is its own finding: silently
    treating it as a mismatch would send the model looking for the wrong bug."""
    text = F.ASSESSMENT.replace("ROUND: 2\nROUND-TYPE", "ROUND: two\nROUND-TYPE")
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("BAD_ROUND:") for f in findings)
    assert not [f for f in findings if f.startswith("ROUND_MISMATCH:")]


def test_an_invented_round_type_fails(tmp_path):
    text = F.ASSESSMENT.replace("ROUND-TYPE: technical", "ROUND-TYPE: culture-fit")
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("UNKNOWN_ROUND_TYPE:") for f in findings)


def test_an_unknown_market_fails(tmp_path):
    text = F.ASSESSMENT.replace("MARKET: nl", "MARKET: benelux")
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("UNKNOWN_MARKET:") for f in findings)


def test_the_no_market_token_is_accepted(tmp_path):
    """mock_vocab.MOCK_MARKET_KEYS is vocab.MARKET_KEYS plus vocab.NO_MARKET. A real
    target often has no market-convention table, and the block must be able to say so
    rather than being forced to pick a country it does not mean."""
    text = F.ASSESSMENT.replace("MARKET: nl", "MARKET: other")
    findings = run(F.build(tmp_path, assessment=text))
    assert not [f for f in findings if f.startswith("UNKNOWN_MARKET:")]


def test_an_empty_family_fails(tmp_path):
    """FAMILY drives the family-conditional tags. Blank means every one of them is
    unverifiable, so the round cannot be assessed against them at all."""
    text = F.ASSESSMENT.replace("FAMILY: ml-engineering", "FAMILY:")
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("NO_FAMILY:") for f in findings)


def test_an_unknown_coverage_status_fails(tmp_path):
    text = F.ASSESSMENT.replace("status=evidenced", "status=covered")
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("UNKNOWN_STATUS:") and "COVERAGE" in f for f in findings)


def test_an_unknown_shape_status_fails(tmp_path):
    """SHAPE has its own status vocabulary — `cannot_simulate` is in it and
    `evidenced` is not. One shared check would accept either in either place."""
    text = F.ASSESSMENT.replace("SHAPE: status=rehearsed", "SHAPE: status=done")
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("UNKNOWN_STATUS:") and "SHAPE" in f for f in findings)


def test_cannot_simulate_is_an_accepted_shape_status(tmp_path):
    """Cry-wolf guard: saying 手撕代码 cannot be run here is the honest answer, and
    the gate must not punish it."""
    text = F.ASSESSMENT.replace("SHAPE: status=not_attempted",
                                "SHAPE: status=cannot_simulate")
    findings = run(F.build(tmp_path, assessment=text))
    assert not [f for f in findings if f.startswith("UNKNOWN_STATUS:")]


# ---------------------------------------------------------------- exit codes

def test_a_failing_workspace_exits_1_and_prints_one_finding_per_line(
    tmp_path, capsys, monkeypatch
):
    ws = F.build(tmp_path, assessment=F.ASSESSMENT.replace(
        "tag=VAGUE-OUTCOME", "tag=WEAK-ANSWER"))
    monkeypatch.setattr(check_mock, "_default_scanner", lambda: F.no_vocab)
    code = check_mock.main(argv(ws))
    out = capsys.readouterr().out.strip().splitlines()
    assert code == 1
    assert out and all(line.split(":")[0].isupper() for line in out)
