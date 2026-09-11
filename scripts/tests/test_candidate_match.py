"""Evidence-backed default recommendations in discover mode."""
import copy

import pytest
import yaml

import candidate_match as matching
import check_candidate_match as gate
import discover_fixtures as fx
import lint_no_prediction as prediction
import snapshot_profile as snapshot


def load_match(workspace):
    return yaml.safe_load((workspace / gate.MATCH_FILE).read_text(encoding="utf-8"))


def save_match(workspace, document):
    (workspace / gate.MATCH_FILE).write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")


def run(workspace, capsys, *extra):
    code = gate.main(["--workspace", str(workspace), *extra])
    return code, capsys.readouterr()


def test_valid_detail_recommendation_and_card_lead_are_quiet(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path / "job-quote")
    code, captured = run(workspace, capsys)
    assert code == 0
    assert captured.out == ""

    code, captured = run(workspace, capsys, "--render", "--lang", "zh")
    assert code == 0
    assert fx.ZH_DETAIL_MATCH_SUMMARY in captured.out
    assert fx.ZH_CARD_MATCH_SUMMARY in captured.out


@pytest.mark.parametrize("lang", ("en", "ja", "ko", "es"))
def test_native_match_summaries_are_localized_and_lint_clean(tmp_path, capsys, lang):
    workspace = fx.build_english_workspace(tmp_path)
    code, captured = run(workspace, capsys, "--render", "--lang", lang)
    assert code == 0
    lines = captured.out.strip()
    assert lines
    assert prediction.scan_text(lines, "shortlist.md") == []


def test_a_summary_in_the_wrong_report_language_is_refused(tmp_path, capsys):
    workspace = fx.build_english_workspace(tmp_path)
    document = load_match(workspace)
    english = matching.render_summary(document["rows"][0], "en")
    chinese = matching.render_summary(document["rows"][0], "zh")
    markdown = (workspace / "shortlist.md").read_text(encoding="utf-8")
    (workspace / "shortlist.md").write_text(markdown.replace(english, chinese), encoding="utf-8")
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "MD_MATCH_SUMMARY_WRONG_LANGUAGE" in captured.out


def test_card_cannot_be_promoted_to_a_default_recommendation(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path / "cv-pointer")
    document = load_match(workspace)
    document["rows"][1]["recommendation"] = "recommend"
    save_match(workspace, document)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "CARD_CANNOT_RECOMMEND" in captured.out
    assert "RECOMMENDATION_NOT_READY" in captured.out


def test_core_gap_blocks_a_default_but_optional_gap_does_not(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path / "missing-summary")
    document = load_match(workspace)
    detail = document["rows"][0]
    optional = {
        "id": "N1", "text": "有半导体设备经验优先", "kind": "must_have",
        "screening": "nice_to_have", "match": "no_evidence", "recency": "undated",
        "effort": "multi_day",
        "job_evidence": [{"file": "raw/51job-detail-173199597.json",
                          "quote": "有半导体设备经验优先"}],
        "cv_evidence": [],
    }
    detail["requirements"].append(optional)
    save_match(workspace, document)
    code, captured = run(workspace, capsys)
    assert code == 0, captured.out

    detail["requirements"][0]["match"] = "no_evidence"
    detail["requirements"][0]["cv_evidence"] = []
    save_match(workspace, document)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "core_gap" in captured.out


def test_dated_strong_evidence_is_not_used_as_current_core_strength(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path / "over-cap")
    document = load_match(workspace)
    document["rows"][0]["requirements"][0]["recency"] = "dated"
    save_match(workspace, document)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "strong_requires_core_strength" in captured.out


def test_job_and_cv_evidence_must_be_real_and_addressable(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path / "job-quote")
    document = load_match(workspace)
    requirement = document["rows"][0]["requirements"][0]
    requirement["job_evidence"][0]["quote"] = "this phrase is not in the detail"
    save_match(workspace, document)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "JOB_EVIDENCE_QUOTE_MISSING" in captured.out

    workspace = fx.build_workspace(tmp_path / "cv-pointer")
    document = load_match(workspace)
    document["rows"][0]["requirements"][0]["cv_evidence"][0]["path"] = "/skills/不存在/0"
    save_match(workspace, document)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "CV_EVIDENCE_PATH_INVALID" in captured.out


def test_job_evidence_must_come_from_a_successful_detail_capture(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    document = load_match(workspace)
    requirement = document["rows"][0]["requirements"][0]
    requirement.update(
        text="173199597",
        job_evidence=[{"file": "raw/51job-1.json", "quote": "173199597"}],
    )
    save_match(workspace, document)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "JOB_EVIDENCE_NOT_DETAIL" in captured.out


def test_indeed_job_command_is_accepted_as_detail_evidence():
    capture = "raw/indeed-detail-job1234.json"
    call = {"action": "adapter_call", "site": "indeed", "command": "job",
            "classification": "ok", "exit_code": 0, "stdout_file": capture}
    assert gate._detail_files([call]) == {capture: [call]}
    # Search cards and unrelated commands must not acquire detail status.
    assert gate._detail_files([{**call, "command": "search"}]) == {}
    assert gate._detail_files([{**call, "site": "unrelated"}]) == {}
    assert gate._detail_files([{**call, "classification": "platform_limit",
                               "exit_code": 1}]) == {}


def test_rendered_summary_order_and_review_cap_are_checked(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path / "missing-summary")
    markdown = (workspace / "shortlist.md").read_text(encoding="utf-8")
    (workspace / "shortlist.md").write_text(
        markdown.replace(fx.ZH_DETAIL_MATCH_SUMMARY, "summary removed"), encoding="utf-8")
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "MD_MATCH_SUMMARY_MISSING" in captured.out

    workspace = fx.build_workspace(tmp_path / "over-cap")
    document = load_match(workspace)
    document["rows"][1]["basis"] = "detail"
    save_match(workspace, document)
    brief = fx.load_brief(workspace)
    brief["max_match_reviews"] = 1
    fx.save_brief(workspace, brief)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "MATCH_REVIEWS_ABOVE_CAP" in captured.out


def test_ordering_prefers_verified_recommendations_before_card_leads(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    shortlist = fx.load_shortlist(workspace)
    shortlist["rows"] = list(reversed(shortlist["rows"]))
    fx.save_shortlist(workspace, shortlist)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "MATCH_ORDER" in captured.out


def test_snapshot_is_frozen_without_touching_the_master(tmp_path, capsys):
    workspace = tmp_path / "round"
    workspace.mkdir()
    master = tmp_path / "master.yaml"
    master.write_text("meta:\n  name: Candidate\n", encoding="utf-8")

    assert snapshot.main(["--workspace", str(workspace), "--profile", str(master)]) == 0
    capsys.readouterr()
    frozen = (workspace / snapshot.DESTINATION).read_bytes()
    assert frozen == master.read_bytes()

    master.write_text("meta:\n  name: Changed candidate\n", encoding="utf-8")
    assert snapshot.main(["--workspace", str(workspace), "--profile", str(master)]) == 2
    captured = capsys.readouterr()
    assert "PROFILE_SNAPSHOT_EXISTS" in captured.err
    assert (workspace / snapshot.DESTINATION).read_bytes() == frozen


def test_snapshot_refuses_a_workspace_symlink(tmp_path, capsys):
    workspace = tmp_path / "round"
    workspace.mkdir()
    master = tmp_path / "master.yaml"
    outside = tmp_path / "outside.yaml"
    master.write_text("meta:\n  name: Candidate\n", encoding="utf-8")
    (workspace / snapshot.DESTINATION).symlink_to(outside)

    assert snapshot.main(["--workspace", str(workspace), "--profile", str(master)]) == 2
    captured = capsys.readouterr()
    assert "PROFILE_SNAPSHOT_PATH_UNSAFE" in captured.err
    assert not outside.exists()


def test_recommendation_failure_uses_the_same_recency_interpretation_as_counts():
    row = {"verdict": "strong_apply"}
    match = copy.deepcopy(fx.CANDIDATE_MATCH["rows"][0])
    match["requirements"][0]["recency"] = "dated"
    assert "strong_requires_core_strength" in matching.recommendation_failures(row, match)


def test_default_recommendation_needs_direct_evidence_for_half_of_core_requirements():
    row = {"verdict": "worth_applying"}
    match = {
        "basis": "detail",
        "alignment": {"domain_fit": "same_domain", "level_direction": "lateral"},
        "requirements": [
            {"kind": "must_have", "screening": "weighted", "match": "strong",
             "recency": "current", "effort": "quick"},
            {"kind": "responsibility", "screening": "weighted", "match": "strong",
             "recency": "recent", "effort": "quick"},
            {"kind": "must_have", "screening": "weighted", "match": "partial",
             "recency": "current", "effort": "quick"},
            {"kind": "responsibility", "screening": "weighted", "match": "partial",
             "recency": "current", "effort": "evening"},
        ],
    }
    # Two strong rows and two small, closable partial rows are deliberately
    # sufficient. The default is strict about core evidence, not an all-or-
    # nothing demand that rejects every candidate who lacks a minor detail.
    assert matching.recommendation_failures(row, match) == []
    match["requirements"].append(
        {"kind": "must_have", "screening": "weighted", "match": "partial",
         "recency": "current", "effort": "quick"})
    assert "insufficient_strong_core_evidence" in matching.recommendation_failures(row, match)


def test_partial_knockout_cannot_be_treated_as_a_small_core_gap():
    row = {"verdict": "worth_applying"}
    match = copy.deepcopy(fx.CANDIDATE_MATCH["rows"][0])
    match["requirements"][0].update(
        screening="knockout", match="partial", recency="current", effort="quick")
    assert "knockout_not_strong" in matching.recommendation_failures(row, match)
