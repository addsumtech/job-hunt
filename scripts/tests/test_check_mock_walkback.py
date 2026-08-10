import datetime
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_mock
import mock_fixtures as F

TODAY = datetime.date(2026, 8, 9)

COLLAPSE = (
    "FINDING: tag=PROBE-COLLAPSE | ref=Q2 | quote=It went really well after that."
)
OVERCLAIM = (
    "FINDING: tag=OVER-CLAIM | ref=Q1 | quote=I owned the offline recon pipeline"
)
UNSOURCED = (
    "FINDING: tag=UNSOURCED-FACT | ref=Q1 | quote=then wrote DICOMs back to the PACS"
)

WALKBACK = """
## Walk-back list

### WB-1 — "Rewrote the offline reconstruction loop for GPU batching."
- transcript: mock/transcript-2.md — Q2
- quote: It went really well after that.
- defect: PROBE-COLLAPSE
- softened: "Rewrote the offline reconstruction loop for GPU batching (timings not retained)."
- status: proposed
"""

# `term:` must be a substring of the quote it resolves — that is the whole matching
# rule in check_walkback. UNSOURCED quotes "then wrote DICOMs back to the PACS", so the
# promoted term is "PACS". A prettier term like "PACS export" appears nowhere in the
# quote and would not resolve anything; test_a_promotion_row_whose_term_is_not_in_the_
# quote_does_not_resolve_it pins that direction so the rule stays tested both ways.
PROMOTED = """- term: PACS
  where: tailoring-plan.md:promoted-from-mock
  source_kind: session-answer
  source_ref: mock/transcript-2.md#Q1
  session_date: "2026-08-09"
  retracted: null
"""


def run(workspace, **kw):
    kw.setdefault("vocab_scanner", F.no_vocab)
    kw.setdefault("today", TODAY)
    kw.setdefault("skill_root", F.skill_root(workspace))
    return check_mock.run(workspace, 2, **kw)


def assessment_with(*findings):
    return F.ASSESSMENT.replace(
        "MOCK-PROVENANCE-V1\nROUND: 2\nFINDINGS: none",
        "MOCK-PROVENANCE-V1\nROUND: 2\n" + "\n".join(findings),
    )


# ---------------------------------------------------------------- the quiet case

def test_no_walkback_is_demanded_when_no_walkback_tag_fired(tmp_path):
    """Cry-wolf guard: an ordinary round with shape findings needs no walk-back."""
    findings = run(F.build(tmp_path))
    assert not [f for f in findings if f.startswith("WALKBACK")]


def test_a_walkback_section_present_without_any_tag_is_not_penalised(tmp_path):
    findings = run(F.build(tmp_path, brief=F.BRIEF + WALKBACK))
    assert not [f for f in findings if f.startswith("WALKBACK")]


# ---------------------------------------------------------------- the demand

def test_a_probe_collapse_demands_the_walkback_section(tmp_path):
    text = F.ASSESSMENT.replace(
        "FINDING: tag=VAGUE-OUTCOME | ref=Q2 | quote=It went really well after that.",
        COLLAPSE,
    )
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("WALKBACK_MISSING:") for f in findings)


def test_an_over_claim_demands_the_walkback_section(tmp_path):
    findings = run(F.build(tmp_path, assessment=assessment_with(OVERCLAIM)))
    assert any(f.startswith("WALKBACK_MISSING:") for f in findings)


def test_a_contradiction_demands_the_walkback_section(tmp_path):
    text = assessment_with(
        "FINDING: tag=CONTRADICTED | ref=Q2 | quote=It went really well after that."
    )
    findings = run(F.build(tmp_path, assessment=text))
    assert any(f.startswith("WALKBACK_MISSING:") for f in findings)


def test_an_unsourced_fact_alone_does_not_demand_a_walkback(tmp_path):
    """Its honest route is usually claims.yaml — 'true, just not on my CV'."""
    findings = run(F.build(tmp_path, assessment=assessment_with(UNSOURCED)))
    assert not [f for f in findings if f.startswith("WALKBACK_MISSING:")]


# ---------------------------------------------------------------- per-finding matching

def test_a_walkback_section_that_misses_this_finding_fails(tmp_path):
    findings = run(
        F.build(tmp_path, assessment=assessment_with(OVERCLAIM), brief=F.BRIEF + WALKBACK)
    )
    assert any(f.startswith("WALKBACK_NO_ENTRY:") and "OVER-CLAIM" in f for f in findings)


def test_the_matching_entry_satisfies_it(tmp_path):
    text = F.ASSESSMENT.replace(
        "FINDING: tag=VAGUE-OUTCOME | ref=Q2 | quote=It went really well after that.",
        COLLAPSE,
    )
    findings = run(F.build(tmp_path, assessment=text, brief=F.BRIEF + WALKBACK))
    assert not [f for f in findings if f.startswith("WALKBACK")]


def test_an_entry_without_softened_wording_fails(tmp_path):
    brief = F.BRIEF + WALKBACK.replace('- softened: "Rewrote the offline '
                                       'reconstruction loop for GPU batching '
                                       '(timings not retained)."\n', "")
    text = F.ASSESSMENT.replace(
        "FINDING: tag=VAGUE-OUTCOME | ref=Q2 | quote=It went really well after that.",
        COLLAPSE,
    )
    findings = run(F.build(tmp_path, assessment=text, brief=brief))
    assert any(f.startswith("WALKBACK_INCOMPLETE:") and "softened" in f for f in findings)


def test_an_entry_with_a_tag_outside_the_walkback_set_fails(tmp_path):
    brief = F.BRIEF + WALKBACK.replace("- defect: PROBE-COLLAPSE", "- defect: NO-OUTCOME")
    text = F.ASSESSMENT.replace(
        "FINDING: tag=VAGUE-OUTCOME | ref=Q2 | quote=It went really well after that.",
        COLLAPSE,
    )
    findings = run(F.build(tmp_path, assessment=text, brief=brief))
    assert any(f.startswith("WALKBACK_BAD_DEFECT:") for f in findings)


# ---------------------------------------------------------------- claims promotion

def test_an_unsourced_fact_must_be_resolved_somewhere(tmp_path):
    findings = run(F.build(tmp_path, assessment=assessment_with(UNSOURCED)))
    assert any(f.startswith("UNRESOLVED_FACT:") for f in findings)


def test_promotion_to_claims_resolves_it(tmp_path):
    findings = run(
        F.build(tmp_path, assessment=assessment_with(UNSOURCED), claims=F.CLAIMS + PROMOTED)
    )
    assert not [f for f in findings if f.startswith("UNRESOLVED_FACT:")]


def test_a_promotion_row_whose_term_is_not_in_the_quote_does_not_resolve_it(tmp_path):
    """The matching rule is 'term appears in the quote', and it has to be tested in
    both directions: a rule that never says no resolves everything, including the
    unsourced fact nobody actually asked the candidate about."""
    claims = F.CLAIMS + PROMOTED.replace("- term: PACS", "- term: coil compression")
    findings = run(F.build(tmp_path, assessment=assessment_with(UNSOURCED), claims=claims))
    assert any(f.startswith("UNRESOLVED_FACT:") for f in findings)


def test_a_promotion_row_pointing_at_another_round_does_not_resolve_it(tmp_path):
    claims = F.CLAIMS + PROMOTED.replace("transcript-2.md", "transcript-1.md")
    findings = run(F.build(tmp_path, assessment=assessment_with(UNSOURCED), claims=claims))
    assert any(f.startswith("UNRESOLVED_FACT:") for f in findings)


def test_a_promotion_row_missing_a_contract_field_fails(tmp_path):
    claims = F.CLAIMS + PROMOTED.replace('  session_date: "2026-08-09"\n', "")
    findings = run(F.build(tmp_path, assessment=assessment_with(UNSOURCED), claims=claims))
    assert any(f.startswith("CLAIM_ROW_INCOMPLETE:") and "session_date" in f
               for f in findings)


def test_an_unparseable_claims_file_is_reported_not_crashed(tmp_path):
    """claims.yaml is hand-appended by the mode. A YAML error there must name itself,
    not surface as 'the unsourced fact was never resolved'."""
    findings = run(F.build(tmp_path, assessment=assessment_with(UNSOURCED),
                           claims="- term: [unclosed\n"))
    assert any(f.startswith("CLAIMS_UNPARSEABLE:") for f in findings)


def test_walking_the_fact_back_also_resolves_it(tmp_path):
    """Drift under pressure is not promoted to the CV — it is walked back."""
    walkback = WALKBACK.replace(
        "- quote: It went really well after that.",
        "- quote: then wrote DICOMs back to the PACS",
    ).replace("- defect: PROBE-COLLAPSE", "- defect: CONTRADICTED")
    findings = run(
        F.build(tmp_path, assessment=assessment_with(UNSOURCED), brief=F.BRIEF + walkback)
    )
    assert not [f for f in findings if f.startswith("UNRESOLVED_FACT:")]


def test_the_ordinary_claims_file_is_not_flagged(tmp_path):
    """Cry-wolf guard: profile-line rows are not promotion rows and are not checked."""
    findings = run(F.build(tmp_path))
    assert not [f for f in findings if f.startswith("CLAIM_ROW_INCOMPLETE:")]
