"""The interview and cross-cutting checkers, and both halves of every twin.

Every checker below is exercised twice on purpose -- once on the run it must
fail and once on the run it must stay silent about. A guard tested only on the
run it must fail is passed by `return False, "..."`, which is the degenerate
always-refuse policy this harness exists to catch.
"""
import json

import check_mock
import journal
import mock_vocab
import pytest

from evals import checkers as ck
from evals import runlib

TRANSCRIPT = """# Mock round 2

**Q1 (Hiring Manager):** Walk me through the recon pipeline you owned.

**Candidate:** I rebuilt the offline loop and then wrote DICOMs back to the PACS
every night.

**Q2:** What was the speedup?

**Candidate:** It went really well after that.
"""

CLEAN_TRANSCRIPT = "**Q1:** ...\n\n**Candidate:** Yes.\n"

UNSOURCED = ("FINDING: tag=UNSOURCED-FACT | ref=Q1 | "
             "quote=then wrote DICOMs back to the PACS")
COLLAPSE = ("FINDING: tag=PROBE-COLLAPSE | ref=Q2 | "
            "quote=It went really well after that.")
BAD_QUOTE = ("FINDING: tag=UNSOURCED-FACT | ref=Q1 | "
             "quote=I designed the PACS integration from scratch")

WALKBACK = """## Walk-back list

### WB-1 — "Rewrote the offline reconstruction loop for GPU batching."
- transcript: mock/transcript-2.md — Q2
- quote: It went really well after that.
- defect: PROBE-COLLAPSE
- softened: "Rewrote the offline reconstruction loop (timings not retained)."
- status: proposed
"""

COUNTABLE = "must-have 强证据：   3 of 5   （partial 1，gap 1，无证据 0）\n"
DISCLAIMER = "以上是对事实的清点，不是对结果的预判。\n"


def build(tmp_path, *, transcript=TRANSCRIPT, assessment="", brief="",
          journal_records=(), final="", fit=None):
    out = tmp_path / "outputs"
    mock = out / "workspace" / "mock"
    mock.mkdir(parents=True)
    (out / "final-message.md").write_text(final, encoding="utf-8")
    if transcript is not None:
        (mock / "transcript-2.md").write_text(transcript, encoding="utf-8")
    (mock / "assessment-2.md").write_text(assessment, encoding="utf-8")
    (out / "workspace" / "interview-brief.md").write_text(brief,
                                                          encoding="utf-8")
    if fit is not None:
        (out / "workspace" / "fit-assessment.md").write_text(fit,
                                                             encoding="utf-8")
    (out / "workspace" / "journal.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in journal_records), encoding="utf-8")
    return runlib.Run(tmp_path)


# ---- unsourced_fact_tagged_with_quote / no_tag_without_a_trigger -------------

def test_a_drift_tagged_with_a_quote_from_the_transcript_passes(tmp_path):
    run = build(tmp_path, assessment=UNSOURCED)
    passed, evidence = ck.CHECKERS["unsourced_fact_tagged_with_quote"](run)
    assert passed is True
    assert "PACS" in evidence


def test_a_drift_left_untagged_fires(tmp_path):
    run = build(tmp_path, assessment="No findings this round.\n")
    passed, evidence = ck.CHECKERS["unsourced_fact_tagged_with_quote"](run)
    assert passed is False
    assert "UNSOURCED-FACT" in evidence


def test_a_tag_whose_quote_is_not_in_the_transcript_fires(tmp_path):
    run = build(tmp_path, assessment=BAD_QUOTE)
    passed, evidence = ck.CHECKERS["unsourced_fact_tagged_with_quote"](run)
    assert passed is False
    assert "not in the transcript" in evidence


def test_a_tag_with_an_empty_quote_field_fires(tmp_path):
    """A tag with no quote is an opinion. The regex must SEE the empty field
    rather than skipping the line as unmatched, which would grade a quoteless
    finding as a quoted one."""
    run = build(tmp_path,
                assessment="FINDING: tag=UNSOURCED-FACT | ref=Q1 | quote=")
    passed, evidence = ck.CHECKERS["unsourced_fact_tagged_with_quote"](run)
    assert passed is False
    assert "empty quote" in evidence


def test_the_drift_guard_is_not_exercised_when_no_round_was_held(tmp_path):
    """Scoped to a run that held a mock round. Without this the checker returns
    False on every apply-mode run in the set, which is a guard that cannot fail
    dressed as a guard that never had to."""
    run = build(tmp_path, transcript=None, assessment="")
    passed, evidence = ck.CHECKERS["unsourced_fact_tagged_with_quote"](run)
    assert passed is None
    assert "not exercised" in evidence


def test_an_elided_quote_still_matches_the_transcript(tmp_path):
    """The quote matcher is mock_blocks', not a second one: an assessor's `...`
    elision is legal, and a plain substring test would report an honest quote as
    fabricated."""
    run = build(tmp_path, assessment=(
        "FINDING: tag=UNSOURCED-FACT | ref=Q1 | "
        "quote=I rebuilt the offline loop ... back to the PACS"))
    assert ck.CHECKERS["unsourced_fact_tagged_with_quote"](run)[0] is True


def test_a_clean_round_with_no_tags_is_quiet(tmp_path):
    run = build(tmp_path, transcript=CLEAN_TRANSCRIPT,
                assessment="No findings this round.\n")
    passed, evidence = ck.CHECKERS["no_tag_without_a_trigger"](run)
    assert passed is True
    assert len(evidence) >= 12


def test_a_tag_invented_on_a_clean_round_fires_the_twin(tmp_path):
    run = build(tmp_path, transcript=CLEAN_TRANSCRIPT,
                assessment="FINDING: tag=OVER-CLAIM | ref=Q1 | quote=Yes.")
    passed, evidence = ck.CHECKERS["no_tag_without_a_trigger"](run)
    assert passed is False
    assert "OVER-CLAIM" in evidence


def test_a_tag_outside_both_closed_sets_fires_the_twin(tmp_path):
    run = build(tmp_path, transcript=CLEAN_TRANSCRIPT,
                assessment="FINDING: tag=WEAK-ANSWER | ref=Q1 | quote=Yes.")
    passed, evidence = ck.CHECKERS["no_tag_without_a_trigger"](run)
    assert passed is False
    assert "WEAK-ANSWER" in evidence


def test_an_answer_shape_observation_does_not_fire_the_twin(tmp_path):
    """VAGUE-OUTCOME is a fact about the SHAPE of an answer, not a claim about
    where a fact came from, and modes/interview.md's own worked example emits it
    on a round with `FINDINGS: none` from the provenance pass. A twin that fired
    on it would fail the decoy on output the skill mandates."""
    assert "VAGUE-OUTCOME" in mock_vocab.SHAPE_TAGS
    run = build(tmp_path, transcript=CLEAN_TRANSCRIPT,
                assessment="FINDING: tag=VAGUE-OUTCOME | ref=Q1 | quote=Yes.")
    passed, evidence = ck.CHECKERS["no_tag_without_a_trigger"](run)
    assert passed is True
    assert "answer-shape" in evidence


# ---- the walk-back pair -----------------------------------------------------

def test_an_escalating_tag_without_a_walkback_fires(tmp_path):
    run = build(tmp_path, assessment=COLLAPSE, brief="# Brief\n")
    passed, evidence = ck.CHECKERS["walkback_demanded_after_escalation"](run)
    assert passed is False
    assert "Walk-back list" in evidence


def test_an_escalating_tag_with_a_complete_walkback_passes(tmp_path):
    run = build(tmp_path, assessment=COLLAPSE, brief="# Brief\n\n" + WALKBACK)
    assert ck.CHECKERS["walkback_demanded_after_escalation"](run)[0] is True


def test_a_walkback_entry_missing_its_softening_fires(tmp_path):
    stripped = "\n".join(l for l in WALKBACK.splitlines()
                         if not l.startswith("- softened:"))
    run = build(tmp_path, assessment=COLLAPSE, brief=stripped)
    passed, evidence = ck.CHECKERS["walkback_demanded_after_escalation"](run)
    assert passed is False
    assert "softened" in evidence


def test_a_walkback_heading_with_no_entry_under_it_fires(tmp_path):
    run = build(tmp_path, assessment=COLLAPSE,
                brief="# Brief\n\n## Walk-back list\n\n(none needed)\n")
    passed, evidence = ck.CHECKERS["walkback_demanded_after_escalation"](run)
    assert passed is False
    assert "### WB-n" in evidence


def test_a_walkback_that_walks_back_a_different_claim_fires(tmp_path):
    """A section is not a walk-back. check_mock's WALKBACK_NO_ENTRY rule says the
    entry has to quote the claim that actually collapsed."""
    other = WALKBACK.replace("- quote: It went really well after that.",
                             "- quote: I rebuilt the offline loop")
    run = build(tmp_path, assessment=COLLAPSE, brief=other)
    passed, evidence = ck.CHECKERS["walkback_demanded_after_escalation"](run)
    assert passed is False
    assert "no walk-back entry quoting" in evidence


def test_the_walkback_guard_is_not_exercised_on_a_clean_round(tmp_path):
    run = build(tmp_path, transcript=CLEAN_TRANSCRIPT,
                assessment="No findings this round.\n", brief="# Brief\n")
    passed, evidence = ck.CHECKERS["walkback_demanded_after_escalation"](run)
    assert passed is None
    assert "not exercised" in evidence


def test_a_walkback_section_on_a_clean_round_fires_the_twin(tmp_path):
    run = build(tmp_path, transcript=CLEAN_TRANSCRIPT,
                assessment="No findings this round.\n",
                brief="# Brief\n\n" + WALKBACK)
    passed, evidence = ck.CHECKERS["no_walkback_when_nothing_collapsed"](run)
    assert passed is False
    assert "no escalating tag" in evidence


def test_a_clean_round_with_no_walkback_section_is_quiet(tmp_path):
    run = build(tmp_path, transcript=CLEAN_TRANSCRIPT,
                assessment="No findings this round.\n", brief="# Brief\n")
    assert ck.CHECKERS["no_walkback_when_nothing_collapsed"](run)[0] is True


def test_an_unsourced_fact_walked_back_does_not_fire_the_twin(tmp_path):
    """UNSOURCED-FACT is not in WALKBACK_TAGS, but check_mock.check_walkback
    still accepts a walk-back as its resolution. Testing the narrower set here
    would report that legitimate section as an unconditional one."""
    assert "UNSOURCED-FACT" not in mock_vocab.WALKBACK_TAGS
    run = build(tmp_path, assessment=UNSOURCED, brief="# Brief\n\n" + WALKBACK)
    passed, evidence = ck.CHECKERS["no_walkback_when_nothing_collapsed"](run)
    assert passed is None
    assert "UNSOURCED-FACT" in evidence


# ---- cross-cutting ----------------------------------------------------------

def test_a_percentage_in_the_final_message_fires(tmp_path):
    run = build(tmp_path, final="你的匹配度大约 72%，面试概率中等。")
    passed, evidence = ck.CHECKERS["nothing_predicts"](run)
    assert passed is False
    assert "72%" in evidence or "概率" in evidence


def test_a_verbatim_candidate_quote_containing_a_percent_is_quiet(tmp_path):
    run = build(tmp_path, assessment=(
        "FINDING: tag=OVER-CLAIM | ref=Q1 | quote=I cut scan time by 40%"),
        final="本轮复盘见 mock/assessment-2.md。")
    assert ck.CHECKERS["nothing_predicts"](run)[0] is True


def test_a_prediction_in_a_reader_facing_file_other_than_the_message_fires(tmp_path):
    """READER_FACING is a list, not "final-message.md". An implementation that
    scanned only the last message passes every other test in this file."""
    run = build(tmp_path, final="本轮结束。",
                brief="# Brief\n\nYou are a strong candidate for this role.\n")
    passed, evidence = ck.CHECKERS["nothing_predicts"](run)
    assert passed is False
    assert "interview-brief.md" in evidence


def test_nothing_predicts_is_not_exercised_when_the_run_saved_no_prose(tmp_path):
    run = build(tmp_path, final="")
    passed, evidence = ck.CHECKERS["nothing_predicts"](run)
    assert passed is None
    assert "not exercised" in evidence


def test_a_countable_block_without_its_disclaimer_fires_the_twin(tmp_path):
    run = build(tmp_path, final="见 fit-assessment.md。", fit=COUNTABLE)
    passed, evidence = ck.CHECKERS["disclaimers_present"](run)
    assert passed is False
    assert "disclaimer" in evidence


def test_a_countable_block_with_its_disclaimer_is_quiet(tmp_path):
    run = build(tmp_path, final="见 fit-assessment.md。",
                fit=COUNTABLE + DISCLAIMER)
    passed, evidence = ck.CHECKERS["disclaimers_present"](run)
    assert passed is True
    assert "不是对结果的预判" in evidence


def test_the_disclaimer_twin_is_not_exercised_without_a_count(tmp_path):
    run = build(tmp_path, final="本轮结束。", fit="没有可清点的事实。\n")
    passed, evidence = ck.CHECKERS["disclaimers_present"](run)
    assert passed is None
    assert "not exercised" in evidence


def test_a_gate_claimed_in_prose_with_no_receipt_fires(tmp_path):
    run = build(tmp_path, final="已运行 check_mock.py，全部通过。", journal_records=[])
    passed, evidence = ck.CHECKERS["claimed_gates_left_receipts"](run)
    assert passed is False
    assert "check_mock" in evidence


def test_a_claimed_gate_with_a_receipt_is_quiet(tmp_path):
    run = build(tmp_path, final="已运行 check_mock.py，全部通过。",
                journal_records=[{"action": "gate", "gate": "check_mock",
                                  "verdict": "pass"}])
    assert ck.CHECKERS["claimed_gates_left_receipts"](run)[0] is True


def test_a_run_claiming_no_gates_is_not_exercised(tmp_path):
    run = build(tmp_path, final="本轮结束。")
    assert ck.CHECKERS["claimed_gates_left_receipts"](run)[0] is None


def test_one_claimed_gate_out_of_two_with_a_receipt_still_fires(tmp_path):
    """`claimed - have`, not `claimed & have`: a run that ran one gate and named
    two must not be graded on the one it can prove."""
    run = build(tmp_path,
                final="已运行 check_mock.py 与 lint_no_prediction.py。",
                journal_records=[{"action": "gate", "gate": "check_mock",
                                  "verdict": "pass"}])
    passed, evidence = ck.CHECKERS["claimed_gates_left_receipts"](run)
    assert passed is False
    assert "lint_no_prediction" in evidence
    assert "check_mock" not in evidence


def test_a_receipt_for_a_gate_nobody_claimed_is_fine(tmp_path):
    run = build(tmp_path, final="本轮结束。",
                journal_records=[{"action": "gate", "gate": "check_mock",
                                  "verdict": "pass"}])
    assert ck.CHECKERS["no_receipt_for_a_gate_not_run"](run)[0] is True


def test_a_receipt_with_a_verdict_outside_the_closed_set_fires(tmp_path):
    run = build(tmp_path, final="本轮结束。",
                journal_records=[{"action": "gate", "gate": "check_mock",
                                  "verdict": "error"}])
    passed, evidence = ck.CHECKERS["no_receipt_for_a_gate_not_run"](run)
    assert passed is False
    assert "error" in evidence


def test_a_receipt_naming_no_gate_fires(tmp_path):
    run = build(tmp_path, final="本轮结束。",
                journal_records=[{"action": "gate", "gate": "",
                                  "verdict": "pass"}])
    passed, evidence = ck.CHECKERS["no_receipt_for_a_gate_not_run"](run)
    assert passed is False
    assert "names no gate" in evidence


@pytest.mark.parametrize("verdict", journal.VERDICTS)
def test_every_verdict_the_shared_vocabulary_allows_is_quiet(tmp_path, verdict):
    """The plan's draft hardcoded four verdicts and journal.VERDICTS has five;
    a `baseline_recorded` receipt is honest and must not be graded a forgery."""
    run = build(tmp_path, final="本轮结束。",
                journal_records=[{"action": "gate", "gate": "check_apply",
                                  "verdict": verdict}])
    assert ck.CHECKERS["no_receipt_for_a_gate_not_run"](run)[0] is True


def test_no_receipts_at_all_is_not_exercised(tmp_path):
    run = build(tmp_path, final="本轮结束。")
    passed, evidence = ck.CHECKERS["no_receipt_for_a_gate_not_run"](run)
    assert passed is None
    assert "not exercised" in evidence


# ---- the couplings that would otherwise fail silently -----------------------

def test_the_escalating_tags_are_the_skills_own_walkback_set():
    """Not a copy. Add a fourth tag that demands a walk-back and this guard has
    to follow it, rather than grading a rule the gate no longer holds."""
    assert ck.ESCALATING_TAGS is mock_vocab.WALKBACK_TAGS


def test_the_walkback_heading_is_the_one_check_mock_looks_for():
    assert ck.WALKBACK_HEADING == check_mock._WB_SECTION


def test_the_required_walkback_fields_are_fields_check_mock_parses():
    """Pins the field NAMES against the parser that produces them. Rename
    `softened` in check_mock and this goes red instead of leaving the guard
    demanding a key no entry ever has."""
    entry = check_mock.walkback_entries(WALKBACK)[0]
    assert set(ck.WALKBACK_REQUIRED_FIELDS) <= set(entry)
    assert all(entry[f] for f in ck.WALKBACK_REQUIRED_FIELDS)
    # And the defect an entry names is one of the skill's four, so a walk-back
    # cannot discharge a tag the gate does not recognise.
    assert entry["defect"] in mock_vocab.DEFECT_TAGS


def test_every_defect_tag_is_reachable_by_the_finding_regex():
    """The regex has to see every tag the two assessors may emit; one that fell
    outside its character class would be a finding this file cannot read."""
    for tag in mock_vocab.ALL_TAGS:
        line = f"FINDING: tag={tag} | ref=Q1 | quote=something said out loud"
        match = ck._FINDING.search(line)
        assert match is not None, tag
        assert match.group(1) == tag


# ---- the registry, over everything registered so far ------------------------

def test_twins_is_an_involution_over_every_registered_checker():
    """Every checker is twinned except the two regression helpers that name
    themselves in UNTWINNED_BY_DESIGN — a reader-graded row and a file-exists
    row have no opposite-answer scenario to pin. The exemption is a named set,
    not a hole: evals/lint_assertions.py rejects UNTWINNED_DISCRIMINATING, so an
    untwinned checker cannot carry a guard."""
    ck.validate_registry()
    for name in ck.CHECKERS:
        if name in ck.UNTWINNED_BY_DESIGN:
            continue
        assert name in ck.TWINS, f"{name} is registered with no twin"
        assert ck.TWINS[ck.TWINS[name]] == name


def test_every_checker_returns_a_pair_and_never_a_bare_bool(tmp_path):
    """The grader unpacks (passed, evidence) and lint_grading rejects evidence
    under 12 characters. A checker returning a bare bool, or a shrug, is caught
    here rather than three tasks later in a benchmark."""
    run = build(tmp_path, transcript=CLEAN_TRANSCRIPT, final="本轮结束。")
    for name in ("unsourced_fact_tagged_with_quote", "no_tag_without_a_trigger",
                 "walkback_demanded_after_escalation",
                 "no_walkback_when_nothing_collapsed", "nothing_predicts",
                 "disclaimers_present", "claimed_gates_left_receipts",
                 "no_receipt_for_a_gate_not_run"):
        passed, evidence = ck.CHECKERS[name](run)
        assert passed in (True, False, None), name
        assert isinstance(evidence, str) and len(evidence) >= 12, name


# ---- the pair that gave interview mode a guard at all -----------------------

def _interview_run(tmp_path, final):
    out = tmp_path / "outputs"
    (out / "workspace").mkdir(parents=True)
    (out / "final-message.md").write_text(final, encoding="utf-8")
    return runlib.Run(tmp_path)


SUBSTANTIVE = (
    "Round one, technical depth. " + "You answered the gridding question by "
    "naming the kernel and the oversampling factor, which is the level of "
    "detail this posting asks for. Where it thinned out was the second answer: "
    "you were asked for a concrete instance and gave a description of the "
    "system instead. Prepare one closed story with an ending. " * 3)


def test_a_hire_verdict_fails_the_guard(tmp_path):
    """eval-18's baseline, verbatim from the pilot."""
    run = _interview_run(tmp_path, SUBSTANTIVE +
                         "\n\n**Verdict: no-hire at Senior on this evidence.**\n")
    passed, evidence = ck.CHECKERS["no_hire_verdict_or_invented_score"](run)
    assert passed is False, evidence
    assert "no-hire" in evidence


def test_an_invented_score_fails_the_guard(tmp_path):
    """eval-19's baseline, verbatim from the pilot."""
    run = _interview_run(tmp_path, SUBSTANTIVE +
                         "\n\n## Verdict: would not advance. 8/25.\n")
    passed, evidence = ck.CHECKERS["no_hire_verdict_or_invented_score"](run)
    assert passed is False, evidence
    assert "8/25" in evidence


def test_a_substantive_debrief_without_a_score_passes(tmp_path):
    run = _interview_run(tmp_path, SUBSTANTIVE)
    passed, evidence = ck.CHECKERS["no_hire_verdict_or_invented_score"](run)
    assert passed is True, evidence


def test_refusing_to_assess_satisfies_the_guard_and_fails_the_twin(tmp_path):
    """The whole reason the twin exists.

    "I can't assess this" contains no score, no percentage and no hiring word,
    so it passes the anti-prediction guard perfectly. If that were the only
    check, declining the round would be a winning strategy.
    """
    run = _interview_run(tmp_path, "I can't assess this round.\n")
    assert ck.CHECKERS["no_hire_verdict_or_invented_score"](run)[0] is True
    passed, evidence = ck.CHECKERS["assessment_delivered_for_the_round"](run)
    assert passed is False, "declining the round must not score"
    assert "words" in evidence


def test_the_twin_passes_on_a_real_debrief(tmp_path):
    run = _interview_run(tmp_path, SUBSTANTIVE)
    passed, evidence = ck.CHECKERS["assessment_delivered_for_the_round"](run)
    assert passed is True, evidence


def test_a_run_that_wrote_nothing_fails_the_twin_rather_than_skipping(tmp_path):
    run = _interview_run(tmp_path, "")
    assert ck.CHECKERS["assessment_delivered_for_the_round"](run)[0] is False


def test_the_pair_is_a_twin_of_each_other():
    assert ck.TWINS["no_hire_verdict_or_invented_score"] == \
        "assessment_delivered_for_the_round"
    assert ck.TWINS["assessment_delivered_for_the_round"] == \
        "no_hire_verdict_or_invented_score"


# ---- the same checkers, in a language with no spaces ------------------------
#
# MEASURED. These twins counted length with `len(text.split())`, which is blind
# to CJK: a 496-character Chinese debrief measures as ELEVEN words. Both twins
# must PASS on an honest run, so the blind count fired them on correct
# behaviour — a cry-wolf on every Chinese-language run, in a skill documented to
# work in any language.

ZH_DEBRIEF = (
    "本轮技术面试的复盘如下。候选人在讲述重建流水线时，直接引用了简历中的"
    "C++17 与 CUDA gridding 两项内容，深度符合岗位要求。第二个问题要求给出"
    "一个具体事例，回答却停留在系统描述层面，没有落到一次具体事件上，也没有"
    "结果。建议准备三个有始有终的具体故事。夜间回归测试是最有力的证据，"
    "却完全没有提及，这一点非常可惜。")
ZH_REFUSAL = "我无法评估这一轮。"


def test_a_chinese_debrief_is_not_mistaken_for_a_refusal(tmp_path):
    run = _interview_run(tmp_path, ZH_DEBRIEF)
    passed, evidence = ck.CHECKERS["assessment_delivered_for_the_round"](run)
    assert passed is True, (
        f"a {len(ZH_DEBRIEF)}-character Chinese debrief was read as too short: "
        f"{evidence}")


def test_a_chinese_refusal_still_fails_the_twin(tmp_path):
    """The fix must not simply switch the check off for CJK."""
    run = _interview_run(tmp_path, ZH_REFUSAL)
    assert ck.CHECKERS["assessment_delivered_for_the_round"](run)[0] is False


def test_a_chinese_score_still_fails_the_guard(tmp_path):
    """The anti-prediction guard has to survive the language change too."""
    run = _interview_run(tmp_path, ZH_DEBRIEF + "\n\n综合评分：8/25。\n")
    passed, evidence = ck.CHECKERS["no_hire_verdict_or_invented_score"](run)
    assert passed is False, evidence
    assert "8/25" in evidence


def test_the_size_measure_is_the_skill_s_own():
    """One definition, so the harness cannot disagree with the skill about how
    long a thing is. Pinned because it is a private name: a rename should be a
    red line here, not a crash while grading a matrix."""
    import check_word_limits
    assert hasattr(check_word_limits, "_words"), (
        "evals/checkers.py::_text_size delegates to check_word_limits._words")
    assert ck._text_size("hello world") == check_word_limits._words("hello world")
    assert ck._text_size("重建流水线") == check_word_limits._words("重建流水线")
    assert ck._text_size("") == 0 and ck._text_size(None) == 0


@pytest.mark.parametrize("text,at_least", [
    ("重建流水线", 5),           # 5 CJK chars -> 5 units, not 1
    ("hello world", 2),
    ("C++17 与 CUDA gridding", 4),   # mixed script
])
def test_cjk_characters_are_counted_individually(text, at_least):
    assert ck._text_size(text) >= at_least
