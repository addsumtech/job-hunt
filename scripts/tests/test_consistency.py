import json

import yaml

import consistency as cons


def row(**kwargs):
    base = {"id": "R1", "kind": "must_have", "text": "x", "level": "required",
            "screening": "weighted", "match": "strong", "recency": "current",
            "effort": "quick", "how_to_close": "", "evidence": [{"ref": "CV-001"}]}
    base.update(kwargs)
    return base


# ---------- check 1: verdict vs effort ----------

def test_strong_apply_priced_at_days_is_a_conflict():
    assert cons.verdict_effort_conflict({"verdict": "strong_apply",
                                         "effort": "multi_day"}) is True
    assert cons.verdict_effort_conflict({"verdict": "strong_apply",
                                         "effort": "not_closable"}) is True


def test_strong_apply_priced_at_an_evening_is_NOT_a_conflict():
    # Deliberate divergence from marketfit: effort here prices closing the gaps, and a
    # strong apply with an evening of work left is an ordinary honest assessment.
    assert cons.verdict_effort_conflict({"verdict": "strong_apply",
                                         "effort": "evening"}) is False


def test_other_verdicts_and_missing_effort_are_never_conflicts():
    for verdict in ("worth_applying", "stretch", "likely_screen_out", "blocked",
                    "insufficient_evidence"):
        assert cons.verdict_effort_conflict({"verdict": verdict,
                                             "effort": "not_closable"}) is False
    assert cons.verdict_effort_conflict({"verdict": "strong_apply"}) is False
    assert cons.verdict_effort_conflict({"verdict": "strong_apply",
                                         "effort": "wobbly"}) is False
    assert cons.verdict_effort_conflict({}) is False


# ---------- check 2: loose knockouts ----------

def test_two_knockouts_are_credible_and_report_zero():
    rows = [row(screening="knockout"), row(screening="knockout"),
            row(screening="weighted"), row(screening="nice_to_have")]
    assert cons.loose_knockouts(rows) == 0


def test_three_knockouts_report_the_count():
    assert cons.loose_knockouts([row(screening="knockout")] * 3) == 3


def test_no_rows_report_zero():
    assert cons.loose_knockouts([]) == 0
    assert cons.loose_knockouts(None) == 0


# ---------- check 3: closable gaps vs actions ----------

def test_a_plan_at_least_as_long_as_its_closable_gaps_reports_nothing():
    rows = [row(match="gap", effort="evening", how_to_close="do the thing"),
            row(match="partial", effort="quick", how_to_close="do the other thing")]
    actions = [{"action": "a", "acceptance": "x", "when": "before_apply"},
               {"action": "b", "acceptance": "y", "when": "before_apply"}]
    assert cons.uncovered_gap_actions(rows, actions) is None


def test_a_not_closable_gap_does_not_count_against_the_plan():
    rows = [row(match="gap", effort="not_closable", how_to_close="cannot")]
    assert cons.uncovered_gap_actions(rows, []) is None


def test_a_gap_with_no_how_to_close_does_not_count_against_the_plan():
    rows = [row(match="gap", effort="evening", how_to_close="")]
    assert cons.uncovered_gap_actions(rows, []) is None


def test_more_closable_gaps_than_actions_reports_both_numbers():
    rows = [row(match="gap", effort="evening", how_to_close="one"),
            row(match="gap", effort="quick", how_to_close="two")]
    assert cons.uncovered_gap_actions(rows, [{"action": "a"}]) == {"gaps": 2, "actions": 1}


# ---------- check 4: work authorization ----------

def test_requires_existing_against_needs_sponsorship_is_a_conflict():
    assert cons.work_authorization_alignment(
        {"type": "sponsorship", "stance": "requires_existing"},
        "needs_sponsorship") == "conflict"


def test_offers_support_against_needs_sponsorship_is_supported():
    assert cons.work_authorization_alignment(
        {"type": "sponsorship", "stance": "offers_support"},
        "needs_sponsorship") == "supported"


def test_a_student_or_temporary_route_asks_rather_than_kills():
    for status in ("student_or_graduate", "temporary_route"):
        assert cons.work_authorization_alignment(
            {"type": "work_authorization", "stance": "requires_existing"},
            status) == "verify"


def test_unknown_status_and_unrelated_condition_types_never_fire():
    assert cons.work_authorization_alignment(
        {"type": "sponsorship", "stance": "requires_existing"}, "unknown") is None
    assert cons.work_authorization_alignment(
        {"type": "onsite_location", "stance": "requires_existing"},
        "needs_sponsorship") is None
    assert cons.work_authorization_alignment(
        {"type": "sponsorship", "stance": "unclear"}, "needs_sponsorship") is None
    assert cons.work_authorization_alignment(
        {"type": "sponsorship", "stance": "requires_existing"}, "authorized") is None


def test_one_conflict_outranks_everything():
    conditions = [{"type": "sponsorship", "stance": "offers_support"},
                  {"type": "citizenship", "stance": "requires_existing"}]
    assert cons.overall_authorization_alignment(
        conditions, "needs_sponsorship") == "conflict"


# ---------- notices ----------

def test_an_ordinary_assessment_produces_no_notices():
    assessment = {"verdict": "worth_applying", "effort": "evening",
                  "declared_work_status": "authorized",
                  "stated_conditions": [{"type": "sponsorship", "stance": "offers_support"}],
                  "requirements": [row(screening="knockout"), row()],
                  "actions": [{"action": "a"}]}
    assert cons.notices(assessment) == []


def test_the_verdict_effort_notice_is_suppressed_by_a_work_auth_conflict():
    assessment = {"verdict": "strong_apply", "effort": "not_closable",
                  "declared_work_status": "needs_sponsorship",
                  "stated_conditions": [{"type": "sponsorship",
                                         "stance": "requires_existing"}],
                  "requirements": [], "actions": []}
    codes = [n["code"] for n in cons.notices(assessment)]
    assert codes == ["NOTICE_WORK_AUTH_CONFLICT"]


def test_every_notice_carries_both_languages_and_an_anchor():
    assessment = {"verdict": "strong_apply", "effort": "multi_day",
                  "declared_work_status": "unknown",
                  "requirements": [row(screening="knockout")] * 3, "actions": []}
    produced = cons.notices(assessment)
    assert [n["code"] for n in produced] == ["NOTICE_VERDICT_EFFORT",
                                             "NOTICE_LOOSE_KNOCKOUTS"]
    for notice in produced:
        assert notice["anchor_zh"] and notice["anchor_zh"] in notice["text_zh"]
        assert notice["anchor_en"] and notice["anchor_en"] in notice["text_en"]
        assert notice["code"] in cons.NOTICE_CODES


# ---------- the CLI ----------

def test_the_cli_reports_without_failing(tmp_path, capsys):
    assessment = {"verdict": "strong_apply", "effort": "multi_day",
                  "declared_work_status": "unknown", "requirements": [], "actions": []}
    (tmp_path / "fit-assessment.yaml").write_text(
        yaml.safe_dump(assessment, allow_unicode=True), encoding="utf-8")
    # A fired notice is a finding ABOUT the assessment, not a failure OF this script.
    assert cons.main(["--workspace", str(tmp_path)]) == 0
    assert "NOTICE_VERDICT_EFFORT" in capsys.readouterr().out
    record = json.loads((tmp_path / "journal.jsonl").read_text(encoding="utf-8"))
    assert record["gate"] == "consistency" and record["verdict"] == "recorded"


def test_the_cli_exits_two_and_still_leaves_exactly_one_receipt(tmp_path, capsys):
    assert cons.main(["--workspace", str(tmp_path)]) == 2
    assert "fit-assessment.yaml" in capsys.readouterr().err
    receipts = [json.loads(line) for line in
                (tmp_path / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(receipts) == 1
    assert receipts[0]["gate"] == "consistency"
    assert receipts[0]["verdict"] == "could_not_run"


def test_a_workspace_that_does_not_exist_writes_no_journal(tmp_path, capsys):
    missing = tmp_path / "nope"
    assert cons.main(["--workspace", str(missing)]) == 2
    assert not missing.exists()
    assert "does not exist" in capsys.readouterr().err


def test_the_conflict_efforts_are_members_of_the_shared_enum(tmp_path):
    # CONFLICT_EFFORTS is a threshold, not a second copy of the effort vocabulary.
    # If it ever stops being a subset, one of the two has drifted.
    import vocab
    assert set(cons.CONFLICT_EFFORTS) <= set(vocab.EFFORT)
