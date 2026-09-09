"""Synthetic browser captures: do not mistake these for live site evidence."""
import copy
import json
from pathlib import Path

import pytest
import yaml

import journal
import record_browser_capture as browser
import check_no_write as nw
import check_shortlist as cs
import discover_fixtures as fx


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def setup_capture(tmp_path, page=1, text=None, status=None):
    ws = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(ws)
    rows = [{k: r[k] for k in ("source_id", "url", "title", "raw_text")}
            for r in data["rows"]]
    snap = {"url": "https://we.51job.com/pc/search?keyword=Python",
            "retrieved_at": "2026-09-08T05:00:00Z",
            "text": text if text is not None else "\n\n".join(r["raw_text"] for r in rows),
            "links": [r["url"] for r in rows], "http_status": status}
    if text is not None:
        rows = []
    a = ws / "raw/51job-browser-1.json"
    b = ws / "raw/51job-browser-1-rows.json"
    dump(a, snap); dump(b, rows)
    fx.write_journal(ws, [fx.mode_entry_record()])
    args = ["--workspace", str(ws), "--site", "51job", "--snapshot-file", str(a),
            "--rows-file", str(b), "--fallback-reason", "bridge_disconnected",
            "--query", "算法工程师", "--page", str(page)]
    return ws, data, snap, rows, args


def record(ws, args):
    assert browser.main(args) == 0
    call = browser.read_retrieval_calls(ws)[-1]
    for field, flag in (("snapshot_file", "--snapshot-file"), ("rows_file", "--rows-file")):
        expected = Path(args[args.index(flag) + 1]).relative_to(ws).as_posix()
        assert call[field] == expected
        assert "\\" not in call[field]
    assert set(call["input_hashes"]) == {call["snapshot_file"], call["rows_file"]}
    return call


def test_browser_only_full_shortlist_passes(tmp_path, capsys):
    ws, data, snap, _, args = setup_capture(tmp_path)
    call = record(ws, args)
    for row in data["rows"]:
        row.update(extraction_method="browser_page", retrieved_at=snap["retrieved_at"])
    source = data["sources"][0]
    source.update(command="search", invocations=1, rows_returned=len(data["rows"]),
                  raw_files=[call["snapshot_file"], call["rows_file"]])
    fx.save_shortlist(ws, data)
    assert nw.main(["--workspace", str(ws), "--no-fetch"]) == 0
    journal.append(ws, fx.upstream_receipt("lint_no_prediction"))
    assert cs.main(["--workspace", str(ws)]) == 0, capsys.readouterr().out
    assert not any(c["action"] == "adapter_call" for c in browser.read_retrieval_calls(ws))


@pytest.mark.parametrize("field,value", [("url", "https://fake.example/job"),
    ("raw_text", "invented salary"), ("source_id", "fake-1234"), ("title", "Invented role")])
def test_invented_row_rejected(tmp_path, field, value):
    ws, _, _, rows, args = setup_capture(tmp_path)
    rows[0][field] = value
    dump(ws / "raw/51job-browser-1-rows.json", rows)
    assert browser.main(args) == 2
    assert browser.read_retrieval_calls(ws) == []


@pytest.mark.parametrize("change", ["file", "metadata", "missing", "operation", "unsigned"])
def test_capture_tampering_fails_no_write(tmp_path, change):
    ws, _, _, _, args = setup_capture(tmp_path)
    call = record(ws, args)
    if change == "file":
        (ws / call["snapshot_file"]).write_text('{}')
    elif change == "missing":
        (ws / call["rows_file"]).unlink()
    elif change == "metadata":
        call["row_count"] = 25
    elif change == "operation":
        call["operation"] = "eval"
        call = journal.sign_receipt(call)
    else:
        call.pop("receipt_hash")
    assert nw.scan([call], ws / "raw/opencli-help", False, ws)
    assert cs.check_run(ws, {"rows": []}, {}, "", [call])


@pytest.mark.parametrize("status,text", [(403, "Forbidden"), (401, "Unauthorized"),
    (429, "Try later"), (200, "请输入验证码"), (200, "Please sign in to continue"),
    (200, "Verify you are human")])
def test_wall_recorded_as_stop_not_empty_success(tmp_path, status, text):
    ws, _, _, _, args = setup_capture(tmp_path, text=text, status=status)
    call = record(ws, args)
    assert call["classification"] == "platform_limit"
    assert call["empty_result"] is False
    assert browser.main(args) == 2
    follow = dict(fx.JOURNAL[0], site="51job")
    assert browser.check_stop_order([call, follow])
    assert nw.scan([call, follow], ws / "raw/opencli-help", False, ws)


def test_adapter_refusal_prevents_browser_import(tmp_path):
    ws, _, _, _, args = setup_capture(tmp_path)
    journal.append(ws, dict(fx.JOURNAL[0], classification="platform_limit", exit_code=1))
    assert browser.main(args) == 2
    assert len(browser.read_retrieval_calls(ws)) == 1


def test_transport_failure_is_not_a_site_refusal(tmp_path):
    ws, _, _, _, args = setup_capture(tmp_path)
    journal.append(ws, dict(fx.JOURNAL[0], classification="transport", exit_code=1))
    call = record(ws, args)
    assert call["fallback_reason"] == "bridge_disconnected"
    assert not browser.check_stop_order(browser.read_retrieval_calls(ws))


def test_browser_pages_count_with_adapter_pages(tmp_path):
    ws, _, _, _, args = setup_capture(tmp_path, page=3)
    call = record(ws, args)
    calls = [dict(fx.JOURNAL[0], command_line="opencli 51job search x --page 1"),
             dict(fx.JOURNAL[0], command_line="opencli 51job search x --page 2"), call]
    assert cs._check_caps_against_the_run(fx.BRIEF, {}, [], calls)[0].startswith("PAGES_ABOVE_CAP")


def test_query_coverage_and_changed_shortlist_row(tmp_path):
    ws, data, snap, _, args = setup_capture(tmp_path)
    call = record(ws, args)
    assert not cs._declared_queries_never_run(fx.BRIEF, data, [call])
    assert cs._declared_queries_never_run(dict(fx.BRIEF, target_titles=["unrun"]), data, [call])
    data["rows"][0].update(extraction_method="browser_page", retrieved_at=snap["retrieved_at"],
                            url="https://fake.example/job")
    assert cs._check_browser_rows(ws, data["rows"], [call], fx.BRIEF)
    assert cs._check_browser_rows(ws, [], [call], {"max_rows_per_round": 1})


@pytest.mark.parametrize("field,value", [("url", "javascript:alert(1)"),
    ("url", "file:///etc/passwd"), ("retrieved_at", "2026-09-08"),
    ("links", "not an array"), ("http_status", "403"), ("blocked", "false")])
def test_bad_snapshot_shape(tmp_path, field, value):
    ws, _, snap, _, args = setup_capture(tmp_path)
    snap[field] = value
    dump(ws / "raw/51job-browser-1.json", snap)
    assert browser.main(args) == 2


def test_genuine_empty_page_and_navbar_login_are_ok(tmp_path):
    ws, _, _, _, args = setup_capture(tmp_path, text="Jobs | Login | No matching jobs", status=200)
    call = record(ws, args)
    assert call["classification"] == "ok" and call["empty_result"]


def test_partial_browser_detail_still_obeys_detail_cap(tmp_path):
    ws, data, snap, _, args = setup_capture(tmp_path)
    args += ["--command", "detail"]
    call = record(ws, args)
    row = data["rows"][0]
    row.update(extraction_method="browser_page", retrieved_at=snap["retrieved_at"],
               quality="partial", verdict="blocked")
    findings = cs._check_browser_rows(ws, [row], [call], fx.BRIEF)
    assert any(f.startswith("DETAIL_FETCH_OUT_OF_BAND") for f in findings)
    assert not cs._check_browser_rows(ws, [row], [call], fx.BRIEF,
                                      [{"id": row["id"], "reason": "user requested"}])


def test_browser_only_cannot_mislabel_itself_as_adapter(tmp_path):
    ws, data, _, _, args = setup_capture(tmp_path)
    call = record(ws, args)
    assert any(f.startswith("BROWSER_METHOD_MISMATCH") for f in
               cs._check_browser_rows(ws, data["rows"], [call], fx.BRIEF))


def test_capture_path_cannot_escape_workspace(tmp_path):
    ws, _, _, _, args = setup_capture(tmp_path)
    raw = ws / "raw/51job-browser-1.json"
    outside = tmp_path / "outside.json"
    outside.write_bytes(raw.read_bytes())
    raw.unlink()
    raw.symlink_to(outside)
    assert browser.main(args) == 2


def test_prediction_lint_uses_only_intact_browser_snapshot(tmp_path):
    from lint_no_prediction import journaled_captures
    ws, _, _, _, args = setup_capture(tmp_path)
    call = record(ws, args)
    snapshot = (ws / call["snapshot_file"]).resolve()
    assert journaled_captures(ws) == [snapshot]
    snapshot.write_text('{"text":"invented fit 100%"}')
    assert journaled_captures(ws) == []


def test_captcha_in_a_legitimate_job_is_not_a_wall(tmp_path):
    ws, _, snap, rows, args = setup_capture(tmp_path)
    rows[0]['title'] = 'CAPTCHA security engineer'
    rows[0]['raw_text'] = 'CAPTCHA security engineer\nBuild CAPTCHA detection and abuse prevention.'
    snap['text'] = '\n\n'.join(r['raw_text'] for r in rows)
    dump(ws / 'raw/51job-browser-1.json', snap)
    dump(ws / 'raw/51job-browser-1-rows.json', rows)
    assert record(ws, args)['classification'] == 'ok'


@pytest.mark.parametrize('site,offset,page', [('indeed',0,1), ('indeed',10,2),
                                            ('linkedin',0,1), ('linkedin',25,2)])
def test_same_page_across_backends_counts_once(site, offset, page):
    calls = [{'site':site, 'command':'search', 'exit_code':0,
              'command_line':f'opencli {site} search Python --start {offset}'},
             {'site':site, 'action':'browser_call', 'command':'search', 'exit_code':0, 'page':page}]
    assert cs._pages_per_site(calls) == {site:{page}}


def test_non_aligned_offsets_cannot_hide_extra_reads():
    calls = [{'site':'indeed', 'command':'search', 'exit_code':0,
              'command_line':f'opencli indeed search Python --start {n}'} for n in [0,1,2]]
    assert len(cs._pages_per_site(calls)['indeed']) == 3
    assert cs._check_caps_against_the_run(fx.BRIEF, {}, [], calls)


def test_capping_final_shortlist_does_not_hide_over_retrieval():
    calls = [{'site':'51job', 'command':'search', 'exit_code':0, 'row_count':20},
             {'site':'51job', 'action':'browser_call', 'command':'search', 'exit_code':0,
              'row_count':20, 'page':1}]
    assert any(f.startswith('ROWS_ABOVE_CAP') for f in
               cs._check_caps_against_the_run(fx.BRIEF, {}, [], calls))


def test_row_budget_is_per_site_not_global():
    rows = [{'source_site':site} for site in ['51job','indeed'] for _ in range(20)]
    calls = [{'site':site, 'command':'search', 'exit_code':0, 'row_count':20}
             for site in ['51job','indeed']]
    assert not cs._check_caps_against_the_run(fx.BRIEF, {}, rows, calls)


def test_detail_read_does_not_spend_search_row_budget_again():
    calls = [{'site':'51job', 'command':'search', 'exit_code':0, 'row_count':25},
             {'site':'51job', 'command':'detail', 'exit_code':0, 'row_count':1}]
    assert not cs._check_caps_against_the_run(fx.BRIEF, {}, [], calls)
