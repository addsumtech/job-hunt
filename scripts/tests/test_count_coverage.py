import json

import yaml

import count_coverage as cc


def row(**kwargs):
    base = {"id": "R", "kind": "must_have", "text": "x", "level": "required",
            "screening": "weighted", "match": "strong", "recency": "current",
            "effort": "quick", "evidence": [{"ref": "CV-001"}]}
    base.update(kwargs)
    return base


ASSESSMENT = {
    "verdict": "worth_applying", "effort": "evening", "level_direction": "lateral",
    "requirements": [
        row(match="strong", recency="current"),
        row(match="strong", recency="undated"),
        row(match="strong", recency="dated"),
        row(match="partial"),
        row(match="gap"),
        row(match="no_evidence", evidence=[]),
        row(kind="responsibility", match="strong", recency="recent"),
        row(kind="responsibility", match="strong", recency="dated"),
        row(kind="responsibility", match="partial"),
    ],
}


def test_only_strong_counts_as_strong():
    counts = cc.coverage(ASSESSMENT["requirements"])
    assert counts["must_total"] == 6
    assert counts["must_strong"] == 2          # current + undated
    assert counts["must_partial"] == 2         # partial + strong-but-dated
    assert counts["must_gap"] == 1
    assert counts["must_no_evidence"] == 1
    assert counts["invalid"] == []


def test_undated_evidence_is_not_downgraded():
    counts = cc.coverage([row(match="strong", recency="undated")])
    assert counts["must_strong"] == 1 and counts["must_partial"] == 0


def test_dated_evidence_is_downgraded_to_partial():
    counts = cc.coverage([row(match="strong", recency="dated")])
    assert counts["must_strong"] == 0 and counts["must_partial"] == 1


def test_responsibilities_use_the_same_vocabulary():
    counts = cc.coverage(ASSESSMENT["requirements"])
    assert counts["resp_total"] == 3
    assert counts["resp_demonstrated"] == 1    # recent yes, dated no, partial no


def test_the_parts_always_sum_to_the_whole():
    counts = cc.coverage(ASSESSMENT["requirements"])
    assert (counts["must_strong"] + counts["must_partial"] + counts["must_gap"]
            + counts["must_no_evidence"]) == counts["must_total"]


def test_an_out_of_enum_match_is_reported_never_substituted():
    counts = cc.coverage([row(match="partly")])
    assert counts["must_total"] == 1
    assert counts["must_strong"] == counts["must_partial"] == 0
    assert any(f.startswith("INVALID_MATCH:") for f in counts["invalid"])


def test_an_out_of_enum_recency_is_reported():
    counts = cc.coverage([row(match="strong", recency="ancient")])
    assert any(f.startswith("INVALID_RECENCY:") for f in counts["invalid"])


def test_an_out_of_enum_kind_is_reported():
    # The quietest of the three: a misspelled `kind` lands in neither total, so
    # every printed number stays self-consistent and the row simply vanishes.
    counts = cc.coverage([row(kind="must-have")])
    assert counts["must_total"] == 0 and counts["resp_total"] == 0
    assert any(f.startswith("INVALID_KIND:") for f in counts["invalid"])


def test_the_zh_labels_come_from_the_shared_vocabulary():
    import vocab
    assert cc.VERDICT_ZH is vocab.VERDICT_ZH


def test_the_rendered_block_is_stable_and_exact():
    counts = cc.coverage(ASSESSMENT["requirements"])
    block = cc.render_block(ASSESSMENT, counts, "zh")
    assert block == (
        "must-have 强证据：   2 of 6   （partial 2，gap 1，无证据 1）\n"
        "核心职责已证实：     1 of 3\n"
        "职级匹配：           平级\n"
        "可补缺口所需投入：   一晚\n"
        "投递建议：           值得投")
    assert cc.render_block(ASSESSMENT, counts, "zh") == block


def test_the_english_block_uses_the_same_numbers():
    counts = cc.coverage(ASSESSMENT["requirements"])
    block = cc.render_block(ASSESSMENT, counts, "en")
    assert block == (
        "must-haves strongly evidenced:   2 of 6   (partial 2, gap 1, no evidence 1)\n"
        "core responsibilities demonstrated: 1 of 3\n"
        "level match:                     lateral\n"
        "effort to close the gaps:        evening\n"
        "apply verdict:                   worth_applying")


def test_the_block_contains_no_percentage_and_no_slash_score():
    counts = cc.coverage(ASSESSMENT["requirements"])
    for lang in ("zh", "en"):
        block = cc.render_block(ASSESSMENT, counts, lang)
        assert "%" not in block
        assert "/" not in block


def test_main_writes_coverage_json_and_prints_the_block(tmp_path, capsys):
    (tmp_path / "fit-assessment.yaml").write_text(
        yaml.safe_dump(ASSESSMENT, allow_unicode=True), encoding="utf-8")
    assert cc.main(["--workspace", str(tmp_path)]) == 0
    data = json.loads((tmp_path / "coverage.json").read_text(encoding="utf-8"))
    assert data["must_strong"] == 2 and data["resp_total"] == 3
    assert "must-have 强证据：   2 of 6" in capsys.readouterr().out


def test_main_fails_on_an_out_of_enum_value(tmp_path, capsys):
    broken = {"verdict": "stretch", "effort": "quick", "level_direction": "unclear",
              "requirements": [row(match="partly")]}
    (tmp_path / "fit-assessment.yaml").write_text(
        yaml.safe_dump(broken, allow_unicode=True), encoding="utf-8")
    assert cc.main(["--workspace", str(tmp_path)]) == 1
    assert "INVALID_MATCH:" in capsys.readouterr().out


def test_a_clean_run_records_rather_than_judges(tmp_path):
    (tmp_path / "fit-assessment.yaml").write_text(
        yaml.safe_dump(ASSESSMENT, allow_unicode=True), encoding="utf-8")
    assert cc.main(["--workspace", str(tmp_path)]) == 0
    record = json.loads((tmp_path / "journal.jsonl").read_text(encoding="utf-8"))
    assert record["gate"] == "count_coverage" and record["verdict"] == "recorded"


def test_main_exits_two_and_still_leaves_exactly_one_receipt(tmp_path, capsys):
    assert cc.main(["--workspace", str(tmp_path)]) == 2
    assert "fit-assessment.yaml" in capsys.readouterr().err
    receipts = [json.loads(line) for line in
                (tmp_path / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(receipts) == 1
    assert receipts[0]["gate"] == "count_coverage"
    assert receipts[0]["verdict"] == "could_not_run"


def test_a_workspace_that_does_not_exist_writes_no_journal(tmp_path, capsys):
    missing = tmp_path / "nope"
    assert cc.main(["--workspace", str(missing)]) == 2
    assert not missing.exists()
    assert "does not exist" in capsys.readouterr().err
