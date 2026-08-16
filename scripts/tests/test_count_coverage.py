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


# ---------- a field nobody assessed is not a field assessed pessimistically ----------

NOT_ASSESSED = {"verdict": "strong_apply", "requirements": [
    row(match="strong"),
    row(match="gap", effort="evening", how_to_close="Deploy it to a k3s cluster."),
]}


def test_an_unassessed_level_direction_and_effort_print_as_not_assessed_in_english():
    """The shipped defect: with neither field present the card stated `unclear`
    and `not_closable` as assessed facts, and `not_closable` was the OPPOSITE of
    what the only gapped row said. Inventing the most pessimistic value and
    printing it in the same column as a real one is a lie, not a safe default."""
    counts = cc.coverage(NOT_ASSESSED["requirements"])
    block = cc.render_block(NOT_ASSESSED, counts, "en")
    assert "level match:                     not assessed" in block
    assert "effort to close the gaps:        not assessed" in block
    assert "unclear" not in block and "not_closable" not in block


def test_an_unassessed_level_direction_and_effort_print_as_not_assessed_in_chinese():
    """zh is the DEFAULT --lang. The zh labels carried a SECOND set of defaults
    inside the dict lookups, so dropping only the two `.get` fallbacks would have
    left the default card still printing 「不明」 and 「补不上」."""
    counts = cc.coverage(NOT_ASSESSED["requirements"])
    block = cc.render_block(NOT_ASSESSED, counts, "zh")
    assert "职级匹配：           未评估" in block
    assert "可补缺口所需投入：   未评估" in block
    assert "不明" not in block and "补不上" not in block


def test_an_out_of_enum_value_reads_as_not_assessed_in_both_languages():
    """A typo is not an assessment either, and the two languages must not
    disagree about what the same file says: printing the raw token in en while
    zh printed 未评估 would make one card claim a judgement the other denies."""
    broken = dict(NOT_ASSESSED, level_direction="sideways", effort="a_weekend")
    counts = cc.coverage(broken["requirements"])
    assert "level match:                     not assessed" in cc.render_block(
        broken, counts, "en")
    assert "职级匹配：           未评估" in cc.render_block(broken, counts, "zh")
    assert "sideways" not in cc.render_block(broken, counts, "en")


def test_the_not_assessed_token_can_never_be_read_back_as_a_value():
    import vocab
    assert cc.NOT_ASSESSED_EN not in vocab.LEVEL_DIRECTION + vocab.EFFORT
    assert cc.NOT_ASSESSED_ZH not in set(cc.LEVEL_DIRECTION_ZH.values()) | set(
        cc.EFFORT_ZH.values())


def test_every_enum_member_still_has_a_zh_label():
    """The not-assessed token must be reachable ONLY by absence. A member of the
    set with no label would silently render as 未评估 and read as unassessed."""
    import vocab
    assert set(cc.LEVEL_DIRECTION_ZH) == set(vocab.LEVEL_DIRECTION)
    assert set(cc.EFFORT_ZH) == set(vocab.EFFORT)


def test_an_assessed_value_still_prints_itself():
    """The quiet case. `unclear` and `not_closable` are legitimate assessed
    values and must keep printing as themselves — the fix distinguishes
    'nobody judged this' from 'judged, and the answer is unclear'."""
    counts = cc.coverage(NOT_ASSESSED["requirements"])
    assessed = dict(NOT_ASSESSED, level_direction="unclear", effort="not_closable")
    en = cc.render_block(assessed, counts, "en")
    zh = cc.render_block(assessed, counts, "zh")
    assert "level match:                     unclear" in en
    assert "effort to close the gaps:        not_closable" in en
    assert "职级匹配：           不明" in zh
    assert "可补缺口所需投入：   补不上" in zh
    assert "not assessed" not in en and "未评估" not in zh


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
