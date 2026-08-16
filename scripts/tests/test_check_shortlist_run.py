"""Run-level tests for scripts/check_shortlist.py.

Risk register row 2: all-adapters-died and found-nothing have the identical
shape. Only the receipts tell them apart, so both branches get a QUIET twin
here — a gate that fires on an honest zero-result would teach the reader to
skip the line that matters.
"""
import copy

import check_shortlist as cs
import discover_fixtures as fx


def run(workspace, capsys):
    code = cs.main(["--workspace", str(workspace)])
    return code, capsys.readouterr()


def codes(out):
    return sorted({line.split(":", 1)[0] for line in out.strip().splitlines() if line})


OK_CALL = fx.JOURNAL[0]

DEAD_CALL = {
    "ts": "2026-08-09T14:02:11Z", "mode": "discover", "action": "adapter_call",
    "site": "51job", "command": "search", "exit_code": 1,
    "classification": "not_logged_in", "row_count": 0, "empty_result": False,
    "identity_field": "title", "empty_identity_rows": [],
    "needs_detail_recovery": False, "auth_state": "not_logged_in",
    "signal_id": None, "remedy": "hand the login command to the user",
    "error_message": "51job request failed: HTTP 403 Forbidden",
    "stdout_file": "raw/51job-1.json", "stderr_file": "raw/51job-1.err",
    "command_line": "opencli 51job search 算法工程师 --limit 25 -f json",
}

EMPTY_CALL = dict(OK_CALL, row_count=0, empty_result=True)

DISCLOSURE_OK = """# Shortlist — 2026-08-09 · 降级输出

## §0 来源与读取质量

本轮所有 adapter 均未返回岗位，见下方披露块。输出为方向级 shortlist。

## §0.1 触发原因

用户要求检索算法工程师岗位。

## §0.2 披露

本次会话已登录：        否
Adapter 返回：          51job request failed: HTTP 403 Forbidden
收到限制信号后重试：    否
绕过任何平台控制：      否
取得真实岗位：          否
降级输出类型：          方向级 shortlist

## §1 方向级 shortlist

1. 计算机视觉算法工程师（制造/半导体设备方向）— 检索词「视觉算法 半导体」…
"""


def make_empty(tmp_path, journal_records, md_text):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"] = []
    data["sources"] = []
    data["shortfall_reason"] = "本轮 adapter 未返回可用行，原因见 §0.2 披露块。"
    fx.save_shortlist(workspace, data)
    fx.write_journal(workspace, journal_records)
    fx.write_md(workspace, md_text)
    return workspace


def test_the_valid_workspace_is_still_completely_quiet(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    code, captured = run(workspace, capsys)
    assert code == 0
    assert captured.out == ""


def test_no_adapter_receipts_at_all_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    fx.write_journal(workspace, [{"action": "gate", "gate": "check_no_write",
                                  "verdict": "pass"}])
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "NO_ADAPTER_RECEIPTS" in codes(captured.out)


def test_no_results_wording_when_every_adapter_died_fires(tmp_path, capsys):
    workspace = make_empty(
        tmp_path, [DEAD_CALL],
        "## §0 来源\n\n## §0.1 触发原因\n\n用户要求检索。\n\n本轮没有匹配的岗位。\n")
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "EMPTY_RESULT_UNSUPPORTED" in codes(captured.out)
    assert "没有匹配" in captured.out
    assert "DEGRADED_WITHOUT_DISCLOSURE" in codes(captured.out)


def test_no_results_wording_with_a_genuine_empty_adapter_result_is_quiet(
        tmp_path, capsys):
    # THE quiet twin: exit 0, a parsed array, zero rows. That IS "no results".
    workspace = make_empty(
        tmp_path, [EMPTY_CALL],
        "## §0 来源\n\n## §0.1 触发原因\n\n用户要求检索。\n\n本轮没有匹配的岗位。\n")
    code, captured = run(workspace, capsys)
    assert code == 0
    assert captured.out == ""


def test_a_degraded_run_with_a_complete_disclosure_block_is_quiet(tmp_path, capsys):
    workspace = make_empty(tmp_path, [DEAD_CALL], DISCLOSURE_OK)
    code, captured = run(workspace, capsys)
    assert code == 0
    assert captured.out == ""


def test_a_blank_disclosure_answer_fires(tmp_path, capsys):
    label = "绕过任何平台控制："
    blanked = "\n".join(label if label in line else line
                        for line in DISCLOSURE_OK.splitlines())
    workspace = make_empty(tmp_path, [DEAD_CALL], blanked)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "DISCLOSURE_INCOMPLETE" in codes(captured.out)
    assert "active overwrite" in captured.out


def test_a_partially_missing_disclosure_block_names_the_missing_lines(
        tmp_path, capsys):
    # The middle branch: some labels present, some absent. All-absent gives
    # DEGRADED_WITHOUT_DISCLOSURE and a blank answer gives DISCLOSURE_INCOMPLETE;
    # this one was the only path with no test in either direction, which is how
    # a half-filled disclosure block would have shipped silently.
    dropped = ("收到限制信号后重试：", "绕过任何平台控制：")
    trimmed = "\n".join(line for line in DISCLOSURE_OK.splitlines()
                        if not any(label in line for label in dropped))
    workspace = make_empty(tmp_path, [DEAD_CALL], trimmed)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "DISCLOSURE_INCOMPLETE" in codes(captured.out)
    assert "DEGRADED_WITHOUT_DISCLOSURE" not in codes(captured.out)
    for label in dropped:
        assert label in captured.out


def test_the_markdown_must_carry_the_card_based_stamp(tmp_path, capsys):
    # spec §5.1 step 6: 不带这个戳就不许渲染. The YAML half is MISSING_PROVISIONAL;
    # this is the half the reader actually sees.
    workspace = fx.build_workspace(tmp_path)
    text = (workspace / "shortlist.md").read_text(encoding="utf-8")
    fx.write_md(workspace, text.replace("基于卡片信息的初判", "候选"))
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "MD_MISSING_PROVISIONAL_STAMP" in codes(captured.out)


def test_an_over_reported_rows_returned_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["sources"][0]["rows_returned"] = 25
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "SOURCE_REPORT_COUNT_MISMATCH" in codes(captured.out)
    assert "more rows than the adapter returned" in captured.out


def test_more_shortlist_rows_than_the_site_returned_fires(tmp_path, capsys):
    # The failure this bounds: one raw row becoming three shortlist rows.
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["sources"][0]["rows_returned"] = 1
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "SOURCE_REPORT_COUNT_MISMATCH" in codes(captured.out)
    assert "De-duplication removes rows" in captured.out


def test_a_hidden_second_invocation_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    fx.write_journal(workspace, list(fx.JOURNAL) + [dict(fx.JOURNAL[0])])
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "SOURCE_REPORT_COUNT_MISMATCH" in codes(captured.out)
    assert "invocations=1" in captured.out


def test_an_understated_empty_identity_count_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    records = [dict(fx.JOURNAL[0], empty_identity_rows=[0],
                    needs_detail_recovery=True), fx.JOURNAL[1]]
    fx.write_journal(workspace, records)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "SOURCE_REPORT_COUNT_MISMATCH" in codes(captured.out)
    assert "needs_detail_recovery" in captured.out


def test_a_brief_missing_the_yellow_caps_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    brief = fx.load_brief(workspace)
    del brief["max_pages_per_site"]
    fx.save_brief(workspace, brief)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "CAP_MISSING" in codes(captured.out)
    assert "references/source-policy.md" in captured.out


def test_a_cap_above_the_yellow_ceiling_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    brief = fx.load_brief(workspace)
    brief["max_pages_per_site"] = 12
    fx.save_brief(workspace, brief)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "CAP_ABOVE_CEILING" in codes(captured.out)
    assert "references/source-policy.md" in captured.out


def test_qualified_prose_about_no_matches_with_rows_present_is_quiet(
        tmp_path, capsys):
    # "no matching senior roles in Utrecht" alongside two real rows is a
    # qualified statement, not a claim that the run found nothing.
    workspace = fx.build_workspace(tmp_path)
    text = (workspace / "shortlist.md").read_text(encoding="utf-8")
    fx.write_md(workspace, text + "\n本轮没有匹配到 staff 级别的岗位。\n")
    code, captured = run(workspace, capsys)
    assert code == 0
    assert captured.out == ""


def test_a_shortfall_without_a_written_reason_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    brief = fx.load_brief(workspace)
    brief["target_count"] = 8
    fx.save_brief(workspace, brief)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "SHORTFALL_NO_REASON" in codes(captured.out)
    assert "never pad" in captured.out


def test_a_shortfall_with_a_written_reason_is_quiet(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    brief = fx.load_brief(workspace)
    brief["target_count"] = 8
    fx.save_brief(workspace, brief)
    data = fx.load_shortlist(workspace)
    data["shortfall_reason"] = (
        "51job 单轮上限 25 行，去重后只有 2 行同时满足 brief 的城市与薪资约束；"
        "下一轮放宽城市到长三角再检索。")
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 0
    assert captured.out == ""


def test_a_missing_trigger_reason_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    brief = fx.load_brief(workspace)
    brief["trigger_reason"] = ""
    fx.save_brief(workspace, brief)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "NO_TRIGGER_REASON" in codes(captured.out)


def test_a_missing_trigger_section_in_the_markdown_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    text = (workspace / "shortlist.md").read_text(encoding="utf-8")
    fx.write_md(workspace, text.replace("§0.1", "§9.9"))
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "NO_TRIGGER_SECTION" in codes(captured.out)


def test_a_missing_brief_exits_2_and_still_leaves_a_receipt(tmp_path, capsys):
    import json
    workspace = fx.build_workspace(tmp_path)
    (workspace / "brief.yaml").unlink()
    code, captured = run(workspace, capsys)
    assert code == 2
    assert "brief.yaml" in captured.err
    receipt = json.loads((workspace / "journal.jsonl").read_text(
        encoding="utf-8").strip().splitlines()[-1])
    assert receipt["gate"] == "check_shortlist"
    assert receipt["verdict"] == "could_not_run"


def test_a_used_site_with_no_source_report_entry_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["sources"] = []
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "SOURCE_REPORT_MISSING" in codes(captured.out)
    assert "references/discovery-sources.md" in captured.out


def test_a_source_report_that_contradicts_the_journal_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    fx.write_journal(workspace, [DEAD_CALL])      # journal says it failed
    code, captured = run(workspace, capsys)       # sources still claims ok
    assert code == 1
    assert "SOURCE_REPORT_CONTRADICTS_JOURNAL" in codes(captured.out)


def test_a_source_report_naming_a_missing_raw_file_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["sources"][0]["raw_files"] = ["raw/51job-9.json"]
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "SOURCE_REPORT_MISSING_RAW" in codes(captured.out)


def test_a_raw_file_named_without_the_raw_prefix_fires(tmp_path, capsys):
    # One convention, pinned: raw_files entries are workspace-relative and carry
    # the `raw/` prefix, exactly as modes/discover.md writes them. A bare
    # basename resolved to <ws>/51job-1.json, which is not where the capture is,
    # so the SAME correct file reported two ways gave two different verdicts.
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["sources"][0]["raw_files"] = ["51job-1.json",
                                       "51job-detail-173199597.json"]
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "SOURCE_REPORT_RAW_PATH" in codes(captured.out)
    assert "raw/51job-1.json" in captured.out      # names the spelling it wants


def test_a_raw_file_escaping_the_workspace_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["sources"][0]["raw_files"] = ["raw/../../elsewhere/51job-1.json"]
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "SOURCE_REPORT_RAW_PATH" in codes(captured.out)


def test_the_prefixed_raw_file_names_the_mode_doc_writes_are_quiet(tmp_path, capsys):
    # The quiet twin. This is also what discover_fixtures writes, so the whole
    # suite would go red if the pinned convention were the other one.
    workspace = fx.build_workspace(tmp_path)
    assert fx.load_shortlist(workspace)["sources"][0]["raw_files"] == [
        "raw/51job-1.json", "raw/51job-detail-173199597.json"]
    code, captured = run(workspace, capsys)
    assert code == 0
    assert captured.out == ""


# ---------------------------------------------------------------- market fit
#
# A WARNING in both directions, and the asymmetry is deliberate: the measured
# failure (an `indeed` search for London returning Columbus, Ohio) is caught by
# positive evidence of the WRONG country, never by failure to recognise the
# right one. `Remote in EU`, `Randstad` and `Noord-Holland` name no country a
# gazetteer of five markets can resolve, and a hard finding on those would teach
# the reader to pad brief.locations until the gate shut up.

def _uk_brief(workspace):
    brief = fx.load_brief(workspace)
    brief["markets"] = ["uk"]
    brief["locations"] = ["London", "Manchester", "Remote (UK)"]
    fx.save_brief(workspace, brief)


def test_a_row_in_another_market_warns_without_failing_the_gate(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    _uk_brief(workspace)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["location"] = "Hybrid work in Columbus, OH 43215"
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 0, "market fit is a warning, not a finding"
    assert "WARN_ROW_OUTSIDE_BRIEF_MARKET" in codes(captured.out)
    assert "Columbus, OH 43215" in captured.out
    assert "uk" in captured.out


def test_the_warning_is_recorded_in_the_receipt_and_still_verdict_pass(
        tmp_path, capsys):
    import json
    workspace = fx.build_workspace(tmp_path)
    _uk_brief(workspace)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["location"] = "Remote in United States"
    fx.save_shortlist(workspace, data)
    assert cs.main(["--workspace", str(workspace)]) == 0
    capsys.readouterr()
    receipt = json.loads((workspace / "journal.jsonl").read_text(
        encoding="utf-8").strip().splitlines()[-1])
    assert receipt["verdict"] == "pass"
    assert any(f.startswith("WARN_ROW_OUTSIDE_BRIEF_MARKET")
               for f in receipt["findings"])


def test_a_us_row_under_a_us_brief_is_quiet(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    brief = fx.load_brief(workspace)
    brief["markets"] = ["us"]
    brief["locations"] = ["Columbus, OH"]
    fx.save_brief(workspace, brief)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["location"] = "Hybrid work in Columbus, OH 43215"
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 0
    assert captured.out == ""


def test_the_locations_a_naive_match_would_cry_wolf_on_are_quiet(
        tmp_path, capsys):
    for location in ("Remote in EU", "Noord-Holland", "Randstad",
                     "Amsterdam-Zuidoost", "Hybrid · Eindhoven",
                     "Fully remote"):
        workspace = fx.build_workspace(tmp_path / location.replace("/", "-"))
        brief = fx.load_brief(workspace)
        brief["markets"] = ["nl"]
        brief["locations"] = ["Amsterdam"]
        fx.save_brief(workspace, brief)
        data = fx.load_shortlist(workspace)
        data["rows"][0]["location"] = location
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 0, f"{location!r} should not fail the gate"
        assert captured.out == "", f"{location!r} cried wolf: {captured.out}"


def test_a_london_ohio_row_still_warns_despite_matching_a_brief_location(
        tmp_path, capsys):
    # The trap the measured defect actually sets: `--location "London"` resolves
    # against the US gazetteer, so the returned rows CONTAIN the brief's own
    # location string. Positive evidence of the wrong country outranks it.
    workspace = fx.build_workspace(tmp_path)
    _uk_brief(workspace)
    data = fx.load_shortlist(workspace)
    data["rows"][0]["location"] = "London, OH 43140"
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 0
    assert "WARN_ROW_OUTSIDE_BRIEF_MARKET" in codes(captured.out)


def test_a_brief_with_no_markets_or_market_other_says_nothing(tmp_path, capsys):
    for index, markets in enumerate(([], ["other"], ["uk", "other"])):
        workspace = fx.build_workspace(tmp_path / f"markets-{index}")
        brief = fx.load_brief(workspace)
        brief["markets"] = markets
        fx.save_brief(workspace, brief)
        data = fx.load_shortlist(workspace)
        data["rows"][0]["location"] = "Columbus, OH 43215"
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 0
        assert captured.out == "", (
            f"markets={markets!r} has no market to compare against; a warning "
            "here is a guess")


def test_a_detail_fetch_on_a_screened_out_row_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][1]["verdict"] = "likely_screen_out"   # still quality: complete
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "DETAIL_FETCH_OUT_OF_BAND" in codes(captured.out)
    assert "detail_fetch_exceptions" in captured.out


def test_a_named_detail_fetch_exception_is_quiet(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"][1]["verdict"] = "likely_screen_out"
    data["detail_fetch_exceptions"] = [
        {"id": "51job-173199597", "reason": "用户点名要求补取这一条的详情"}]
    fx.save_shortlist(workspace, data)
    code, captured = run(workspace, capsys)
    assert code == 0
    assert captured.out == ""


def test_every_top_three_verdict_may_carry_a_detail_fetch(tmp_path, capsys):
    for verdict in cs.TOP_THREE:
        data = copy.deepcopy(fx.SHORTLIST)
        workspace = fx.build_workspace(tmp_path / verdict)
        data["rows"][1]["verdict"] = verdict
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 0, f"{verdict} should be allowed a detail fetch"
        assert captured.out == ""
