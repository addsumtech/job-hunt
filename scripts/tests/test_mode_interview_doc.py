import datetime
import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_mock
import deliver
import mock_blocks as MB

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODE = ROOT / "modes" / "interview.md"
TODAY = datetime.date(2026, 8, 9)


def _example(anchor: str) -> str:
    text = MODE.read_text(encoding="utf-8")
    marker = f"<!-- example: {anchor} -->"
    assert marker in text, f"modes/interview.md has no {marker}"
    fence = re.search(r"```[a-z]*\n(.*?)```", text[text.index(marker):], re.S)
    assert fence, f"{marker} is not followed by a fenced block"
    return fence.group(1)


# --------------------------------------------- the schemas are executable, not prose

def test_the_question_log_example_passes_the_real_validator(tmp_path):
    path = tmp_path / "question-log.yaml"
    path.write_text(_example("question-log.yaml"), encoding="utf-8")
    assert check_mock.check_question_log(path, TODAY) == []


def test_the_answer_bank_example_passes_the_real_validator(tmp_path):
    path = tmp_path / "answer-bank.md"
    path.write_text(_example("answer-bank.md"), encoding="utf-8")
    assert check_mock.check_answer_bank(path) == []


def test_the_walkback_example_parses_into_a_complete_entry():
    entries = check_mock.walkback_entries(_example("walk-back list"))
    assert entries, "the walk-back example yields no entries"
    for entry in entries:
        assert entry["quote"] and entry["softened"] and entry["defect"]


def test_the_transcript_example_carries_parseable_question_headings():
    assert check_mock.transcript_refs(_example("transcript-<n>.md"))


def test_the_assessment_example_parses_as_both_blocks():
    text = _example("assessment-<n>.md")
    MB.parse_block(text, MB.ASSESSMENT)
    MB.parse_block(text, MB.PROVENANCE)


# --------------------------------------------- rules that must be stated in words

@pytest.mark.parametrize(
    "phrase",
    [
        "FLUSH THE TRANSCRIPT AFTER EVERY ANSWER",
        "One round per dispatch",
        "COUNTRY RULE",
        "never quoted as a specific technical question",
        "Never paste a scraped post's ANSWER",
        "Do not log in to work around it",
        "open-loops summary",
        "references/interview-shapes.md",
        "agents/mock-assessor-transcript.md",
        "agents/mock-assessor-provenance.md",
        "scripts/check_mock.py",
        "scripts/enter_mode.py",
    ],
)
def test_the_mode_file_states(phrase):
    """Asserted with the file's own capitalisation. Lowercasing both sides here would
    let 'ONE ROUND PER DISPATCH' or any other shouted variant pass, and the point of
    these is that a specific sentence, written a specific way, is present."""
    assert phrase in MODE.read_text(encoding="utf-8")


def test_mode_entry_is_the_first_instruction_in_the_file():
    """modes/interview.md is layer 1.5, and check_mock's NO_MODE_ENTRY is what reports
    a run that skipped it. If the command is buried below the interview steps, the
    model reaches the first question before it reaches the record."""
    text = MODE.read_text(encoding="utf-8")
    entry = text.index("scripts/enter_mode.py")
    assert entry < text.index("## 1."), "the mode-entry command is not in §0"
    assert "--mode interview" in text


def test_the_pack_split_names_what_pass_1_is_not_given():
    text = MODE.read_text(encoding="utf-8")
    table = text.split("## 4.")[1].split("## 5.")[0]
    assert "interview-brief.md" in table and "claims.yaml" in table
    assert "NOT" in table or "not given" in table


def _recovery_section():
    text = MODE.read_text(encoding="utf-8")
    marker = "### Recover an invalid assessor block"
    assert marker in text, "an invalid quote must have a bounded recovery path"
    return _flat(text.split(marker, 1)[1].split("<!-- example:", 1)[0])


def test_invalid_quote_recovery_selects_only_the_failed_pass():
    section = _recovery_section()
    for code in ("PARSE_FAIL", "MISSING_BLOCK", "QUOTE_NOT_IN_TRANSCRIPT"):
        assert code in section
    assert "block name in the diagnostic" in section
    assert "Re-dispatch only the failed pass" in section
    assert "Keep any valid pass's block byte-identical" in section
    assert "candidate's answer under that same heading" in section


def test_recovery_preserves_evidence_and_the_original_input_split():
    section = _recovery_section()
    assert "original failed assessment" in section
    assert "stdout/stderr" in section and "journal receipt" in section
    assert "fresh context" in section
    assert "same agent prompt and byte-identical source files" in section
    assert "only that pass's gate diagnostics" in section
    assert "Never supply the other pass's output" in section
    assert "Never hand-edit a block" in section
    assert "Never change the transcript or candidate facts" in section


def test_recovery_has_one_attempt_and_requires_an_honest_stop():
    section = _recovery_section()
    assert "at most one corrective reassessment per failed pass per round" in section
    assert "re-run the full gate" in section
    assert "If it still fails, stop" in section
    assert "both gate receipts" in section
    assert "Do not loop until green" in section


def test_documented_recovery_archive_is_excluded_from_delivery(tmp_path):
    section = _recovery_section()
    assert "mock/raw/recovery-<n>/" in section
    archived = tmp_path / "mock" / "raw" / "recovery-1" / "failed-assessment.md"
    assert not deliver.is_deliverable(archived, tmp_path)


def test_the_published_rubric_exception_is_bounded():
    text = MODE.read_text(encoding="utf-8")
    section = text.split("## Published employer rubric")[1]
    assert "attribut" in section.lower()
    assert "never as a prediction" in section.lower()


def test_the_twelve_month_rule_is_stated_with_its_reason():
    text = MODE.read_text(encoding="utf-8")
    assert "12 months" in text
    assert "shape" in text.lower()


def test_the_country_rule_names_the_measured_case():
    text = MODE.read_text(encoding="utf-8")
    assert "ASML" in text and "宣讲会" in text


def _flat(text):
    """Doc assertions normalise whitespace: a line wrap is not a content change."""
    return " ".join(text.split())


def test_the_mode_forbids_writing_the_answer_in_the_candidates_voice():
    """The clause the whole answer-guide step hangs on.

    Without it the step reads as "write good answers", which is what produces an
    invented instance on the rows the candidate has no evidence for.
    """
    doc = _flat(MODE.read_text(encoding="utf-8"))
    assert "Never write the candidate's answer in their voice" in doc
    where = doc.index("Never write the candidate's answer in their voice")
    assert "skeleton" in doc[where:where + 400]


def test_the_mode_states_the_three_lines_the_gate_reads():
    doc = _flat(MODE.read_text(encoding="utf-8"))
    for line in ("- row:", "- basis:", "- source:"):
        assert line in doc, line
    assert "evidenced" in doc and "honest_gap" in doc
    # Pinned to the TABLE CELL, not to the document. Asserting "no default" anywhere
    # let a mutant rewrite the cell to "defaults to `evidenced`" and stay green off
    # the prose sentence below it -- two copies disagreeing, which is the shape of
    # defect this repo keeps finding.
    cell = doc[doc.index("| `- basis:` |"):]
    cell = cell[:cell.index("|", cell.index("honest_gap"))]
    assert "no third value and no default" in cell, cell
    assert "default" not in cell.replace("no third value and no default", "")


def test_the_mode_says_a_gapped_row_may_not_be_written_up_as_evidenced():
    doc = _flat(MODE.read_text(encoding="utf-8"))
    assert "GUIDE_GAP_AS_EVIDENCED" in doc
    where = doc.index("GUIDE_GAP_AS_EVIDENCED")
    assert "gap" in doc[where:where + 200] and "no_evidence" in doc[where:where + 200]
