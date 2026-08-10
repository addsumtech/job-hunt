"""Per-row provenance tests for scripts/check_shortlist.py.

Risk register row 1: a fabricated shortlist is internally consistent, perfectly
formatted, and every field has the right shape. The one thing a fabricated row
cannot do is appear in raw/ — so that is what is checked, verbatim, per row.
"""
import check_shortlist as cs
import discover_fixtures as fx


def run(workspace, capsys):
    code = cs.main(["--workspace", str(workspace)])
    return code, capsys.readouterr()


def codes(out):
    return sorted({line.split(":", 1)[0] for line in out.strip().splitlines() if line})


def test_the_valid_workspace_is_completely_quiet(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    code, captured = run(workspace, capsys)
    assert code == 0
    assert captured.out == ""


def test_source_id_absent_from_raw_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["source_id"] = "999999999"
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "SOURCE_ID_NOT_IN_RAW" in codes(captured.out)
    assert "51job-1.json" in captured.out


def test_a_short_source_id_is_rejected_before_the_substring_search(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["source_id"] = "17"      # would match almost any capture
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "SUSPICIOUS_SOURCE_ID" in codes(captured.out)


def test_a_site_with_no_raw_capture_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    row = dict(data["rows"][0])
    row.update({"id": "linkedin-1", "source_site": "linkedin",
                "source_id": "3812345678",
                "url": "https://www.linkedin.com/jobs/view/3812345678/"})
    data["rows"].append(row)
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "NO_RAW_CAPTURE_FOR_SITE" in codes(captured.out)
    # Reported once, not twice: no SOURCE_ID_NOT_IN_RAW piled on top.
    assert "SOURCE_ID_NOT_IN_RAW" not in codes(captured.out)


def test_an_invented_url_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["url"] = "https://jobs.51job.com/shanghai/173198362.html"
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "URL_NOT_FROM_ADAPTER" in codes(captured.out)


def test_the_full_url_with_tracking_params_is_quiet(tmp_path, capsys):
    # Storing either the trimmed url or the adapter's full one must pass;
    # stripping tracking parameters is not evidence of fabrication.
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["url"] = (
        "https://jobs.51job.com/xian-gxjs/173198362.html?s=sou_sou_soulb&t=0_0")
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 0
    assert captured.out == ""


def test_empty_title_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["title"] = ""
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "EMPTY_TITLE" in codes(captured.out)


def test_missing_why_matched_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][1]["why_matched"] = "   "
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "NO_WHY_MATCHED" in codes(captured.out)


def test_missing_retrieved_at_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    del data["rows"][0]["retrieved_at"]
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "NO_RETRIEVED_AT" in codes(captured.out)
    assert "MISSING_FIELD" in codes(captured.out)


def test_missing_source_site_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["source_site"] = ""
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "NO_SOURCE_SITE" in codes(captured.out)


def test_a_verdict_outside_the_five_levels_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["verdict"] = "maybe"
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "BAD_VERDICT" in codes(captured.out)
    assert "strong_apply" in captured.out


def test_a_missing_provisional_stamp_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["provisional"] = False
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "MISSING_PROVISIONAL" in codes(captured.out)
    assert "may not be rendered" in captured.out


def test_a_bad_enum_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["extraction_method"] = "screenshot"
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "BAD_ENUM" in codes(captured.out)


def test_a_bad_effort_value_fires(tmp_path, capsys):
    # effort is what makes D3's "within a band, order by effort-to-close"
    # implementable instead of merely stated, so it is enum-checked like the
    # rest rather than left as free text nobody can sort on.
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["effort"] = "a weekend maybe"
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "BAD_ENUM" in codes(captured.out)
    assert "not_closable" in captured.out


def test_a_duplicated_source_id_fires(tmp_path, capsys):
    # Count conservation from the row side: one retrieved posting may not be
    # listed twice to pad the shortlist toward target_count.
    import copy
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    clone = copy.deepcopy(data["rows"][0])
    clone["id"] = "51job-173198362-b"
    data["rows"].append(clone)
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "DUPLICATE_SOURCE_ID" in codes(captured.out)


def test_the_row_vocabulary_is_the_one_in_scripts_vocab(tmp_path):
    # R1: no closed set is spelled out twice. If check_shortlist ever grows its
    # own copy of the verdicts, this fails rather than drifting quietly.
    import vocab
    assert cs.VERDICTS is vocab.VERDICTS
    assert cs.EFFORT is vocab.EFFORT
    assert cs.TOP_THREE == ("strong_apply", "worth_applying", "stretch")
    assert len(cs.REQUIRED_ROW_FIELDS) == 17
    assert "effort" in cs.REQUIRED_ROW_FIELDS


def test_a_missing_shortlist_exits_2_and_still_leaves_a_receipt(tmp_path, capsys):
    import json
    workspace = fx.build_workspace(tmp_path)
    before = len((workspace / "journal.jsonl").read_text(
        encoding="utf-8").strip().splitlines())
    (workspace / "shortlist.yaml").unlink()
    code, captured = run(workspace, capsys)
    assert code == 2
    assert "shortlist.yaml" in captured.err
    lines = (workspace / "journal.jsonl").read_text(
        encoding="utf-8").strip().splitlines()
    assert len(lines) == before + 1
    receipt = json.loads(lines[-1])
    assert receipt["gate"] == "check_shortlist"
    assert receipt["verdict"] == "could_not_run"


def test_a_missing_workspace_directory_exits_2_with_no_receipt(tmp_path, capsys):
    missing = tmp_path / "nope"
    assert cs.main(["--workspace", str(missing)]) == 2
    assert "workspace not found" in capsys.readouterr().err
    assert not missing.exists()


def test_a_receipt_is_written_on_pass_and_on_fail(tmp_path, capsys):
    import json
    workspace = fx.build_workspace(tmp_path)
    assert cs.main(["--workspace", str(workspace)]) == 0
    capsys.readouterr()
    receipt = json.loads((workspace / "journal.jsonl").read_text(
        encoding="utf-8").strip().splitlines()[-1])
    assert receipt["gate"] == "check_shortlist"
    assert receipt["verdict"] == "pass"
    assert "shortlist.yaml" in receipt["input_hashes"]

    data = fx.load_shortlist(workspace)
    data["rows"][0]["source_id"] = "999999999"
    fx.save_shortlist(workspace, data)
    assert cs.main(["--workspace", str(workspace)]) == 1
    capsys.readouterr()
    receipt = json.loads((workspace / "journal.jsonl").read_text(
        encoding="utf-8").strip().splitlines()[-1])
    assert receipt["verdict"] == "fail"
    assert any(f.startswith("SOURCE_ID_NOT_IN_RAW") for f in receipt["findings"])
