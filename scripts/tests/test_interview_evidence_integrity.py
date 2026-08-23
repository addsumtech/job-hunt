"""Interview mode's evidence checks, held to what they claim to check.

The mode's payback is the walk-back list, and modes/interview.md §6 copies it
into interview-brief.md where it drives a real CV edit. An audit on 2026-08-23
found the verification underneath it was substring matching with no anchors:

  1. a quote could be spliced out of a DIFFERENT answer, in reverse order, or be
     the interviewer's own question
  2. any ellipsis fragment under 8 characters was DISCARDED rather than checked,
     so `40%`, `MDR`, `at GE` and `带过五人团队` were never compared to anything
  3. a claims.yaml promotion row was never resolved: `source_ref` was read by no
     script in the skill, and the row's term was never looked for in the
     transcript it cited
  4. a row explicitly marked `retracted` still discharged an UNSOURCED-FACT
  5. question-log.yaml was reconciled against nothing, so every scraped-only rule
     — the country rule included — bound only the rows the model chose to write

The through-line: each of these ends with a term the candidate never said
reaching the tailored CV with every gate green.
"""
import datetime
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_mock
import mock_blocks as MB
import mock_fixtures as F

TODAY = datetime.date(2026, 8, 9)


def run(workspace, **kw):
    kw.setdefault("vocab_scanner", F.no_vocab)
    kw.setdefault("skill_root", F.skill_root(workspace))
    kw.setdefault("today", TODAY)
    return check_mock.run(workspace, 2, **kw)


def codes(findings):
    return sorted({f.split(":")[0] for f in findings})


def claims_row(term="PACS", ref="mock/transcript-2.md#Q1", retracted="null"):
    return (f"- term: {term}\n"
            f"  where: cv.md\n"
            f"  source_kind: session-answer\n"
            f"  source_ref: {ref}\n"
            f"  session_date: '2026-08-09'\n"
            f"  retracted: {retracted}\n")


# ── 1 + 2. the quote must come from the answer it cites ───────────────────────

def answer(ref):
    """The candidate's own words under one question heading.

    Computed per-call, not at import: these helpers are the thing under test, and
    a module-level call makes the whole file error at COLLECTION against a build
    that lacks them — which reports as one error instead of N specific failures,
    and would have hidden which behaviours actually discriminate.
    """
    return MB.candidate_only(MB.transcript_sections(F.TRANSCRIPT)[ref])


def test_a_verbatim_quote_from_the_cited_answer_still_matches():
    assert MB.quote_is_in(
        "At the university hospital I owned the offline recon pipeline", answer('Q1'))


def test_a_short_quote_is_still_accepted():
    """The floor removed in this change was on SEGMENTS, not on quotes. A terse
    answer is terse, not fabricated, and rejecting it would report honest
    assessors as liars — the cry-wolf failure, which is how a gate gets ignored."""
    assert MB.quote_is_in("we did", "and then we did, eventually")


@pytest.mark.parametrize("quote,what", [
    ("At the university hospital ... at NASA ... for a 3T scanner study",
     "a short fabricated employer between two real halves"),
    ("At the university hospital ... 带过五人团队 ... for a 3T scanner study",
     "the same attack in Chinese, where six characters is a whole claim"),
    ("At the university hospital ... 40% faster ... for a 3T scanner study",
     "a fabricated number, the thing a recruiter asks about"),
])
def test_a_short_fabricated_segment_is_no_longer_discarded(quote, what):
    assert not MB.quote_is_in(quote, answer("Q1")), what


def test_a_quote_assembled_backwards_is_refused():
    """`all(seg in hay)` accepted a sentence built out of two real clauses in the
    wrong order. An elision means "I left something out here", not "these phrases
    occur somewhere in this document"."""
    assert not MB.quote_is_in(
        "then wrote DICOMs back to the PACS ... At the university hospital", answer('Q1'))


def test_the_interviewers_own_question_cannot_evidence_a_finding():
    assert "Walk me through" in MB.transcript_sections(F.TRANSCRIPT)["Q1"]
    assert "Walk me through" not in answer("Q1")
    assert not MB.quote_is_in("Walk me through the reconstruction pipeline you owned", answer('Q1'))


def test_a_quote_cannot_be_taken_from_a_different_answer():
    real_q2 = "I replaced the per-slice loop with a batched GPU implementation"
    assert MB.quote_is_in(real_q2, answer('Q2')), "must still match against its own answer"
    assert not MB.quote_is_in(real_q2, answer('Q1')), "must not match against Q1"


def test_candidate_only_falls_back_when_the_transcript_has_no_speaker_markers():
    """Deliberate: the `**Candidate:**` convention is described in
    modes/interview.md and enforced nowhere, so a stricter reading would report
    every quote in an otherwise valid round as fabricated. Section scoping still
    applies, so the cross-answer splice stays closed either way."""
    section = "The candidate said something useful here.\n"
    assert MB.candidate_only(section) == section


def test_transcript_sections_splits_on_question_headings():
    sections = MB.transcript_sections(F.TRANSCRIPT)
    assert set(sections) == {"Q1", "Q2", "Q3"}
    assert "batched GPU" in sections["Q2"]
    assert "batched GPU" not in sections["Q1"]


def test_quote_segments_keeps_every_fragment():
    assert MB.quote_segments("aaaaaaaaaa ... bb ... cccccccccc") == [
        "aaaaaaaaaa", "bb", "cccccccccc"]


# ── 3 + 4. claims.yaml promotions ─────────────────────────────────────────────

def test_the_baseline_workspace_is_clean(tmp_path):
    assert run(F.build(tmp_path)) == []


def test_an_honest_promotion_is_clean(tmp_path):
    """PACS is in the Q1 answer and the ref resolves, so nothing should fire."""
    assert run(F.build(tmp_path, claims=claims_row())) == []


def test_a_retracted_row_cannot_source_anything(tmp_path):
    """The worst version: the workspace holds a written record that the candidate
    withdrew this claim, and the gate read that record as the claim's source.
    check_claims.py:415 already sorts rows this way."""
    out = run(F.build(tmp_path, claims=claims_row(retracted="true")))
    assert "PROMOTION_RETRACTED" in codes(out)


def test_a_source_ref_that_resolves_to_nothing_is_refused(tmp_path):
    out = run(F.build(tmp_path, claims=claims_row(ref="wrong/dir/transcript-2.md#Q1")))
    assert "PROMOTION_REF_MISSING" in codes(out)


def test_a_term_the_candidate_never_said_is_refused(tmp_path):
    """MDR is a regulatory credential. It is not in the transcript, its only
    provenance is this row, and it used to reach the rendered CV."""
    out = run(F.build(tmp_path, claims=claims_row(term="MDR")))
    assert "PROMOTION_NOT_IN_TRANSCRIPT" in codes(out)


def test_promotions_are_checked_on_a_round_where_nothing_fired(tmp_path):
    """The load-bearing one. check_walkback returned early when no tag had fired,
    so the documented clean round — both blocks emitting `FINDINGS: none`, which
    is the fixture — never opened claims.yaml at all. That is precisely the round
    where nothing else is looking."""
    ws = F.build(tmp_path, claims=claims_row(term="MDR"))
    assessment = (ws / "mock" / "assessment-2.md").read_text(encoding="utf-8")
    assert "UNSOURCED-FACT" not in assessment, "fixture must have no fired tags"
    assert "PROMOTION_NOT_IN_TRANSCRIPT" in codes(run(ws))


def test_promotion_matching_uses_whole_tokens(tmp_path):
    """An honest `term: Java` row must not discharge a finding about JavaScript.
    check_claims.phrase_in already draws this boundary, and handles the part that
    is easy to get wrong: CJK has no word boundaries, so a token test there would
    report every skill on a Chinese CV as unsourced."""
    assert check_mock._phrase_in("Java", "I wrote the Java service")
    assert not check_mock._phrase_in("Java", "I wrote the JavaScript dashboard")
    assert check_mock._phrase_in("重建", "我做了图像重建流水线"), "CJK must still match"


# ── 5. question-log reconciliation ────────────────────────────────────────────

def _log(rows):
    body = "".join(
        f"  - id: {qid}\n    text: {text}\n    source: generated\n    asked: true\n"
        for qid, text in rows)
    return f"round: 2\nposting_country: NL\nquestions:\n{body}"


ALL_THREE = [("Q1", "a"), ("Q2", "b"), ("Q3", "c")]


def test_a_question_that_was_asked_but_never_logged_is_reported(tmp_path):
    """Dropping the row switched off every scraped-only rule for that question,
    and the agent deciding whether to write the row is the same one that would
    make the mistake. modes/interview.md calls the wrong-country scraped question
    'the most dangerous failure available in this source'."""
    out = run(F.build(tmp_path, question_log=_log(ALL_THREE[:2])))
    assert "LOG_MISSING_QUESTION" in codes(out)
    assert any("Q3" in f for f in out)


def test_a_logged_question_that_was_never_asked_is_reported(tmp_path):
    out = run(F.build(tmp_path, question_log=_log(ALL_THREE + [("Q9", "phantom")])))
    assert "LOG_QUESTION_NOT_ASKED" in codes(out)
    assert any("Q9" in f for f in out)


def test_a_log_matching_the_transcript_is_clean(tmp_path):
    assert run(F.build(tmp_path, question_log=_log(ALL_THREE))) == []


def test_reconciliation_is_skipped_when_no_refs_are_supplied(tmp_path):
    """The parameter defaults to None so the function stays callable on its own,
    the way its existing tests call it."""
    log = tmp_path / "question-log.yaml"
    log.write_text(_log(ALL_THREE + [("Q9", "phantom")]), encoding="utf-8")
    assert check_mock.check_question_log(log, TODAY) == []
