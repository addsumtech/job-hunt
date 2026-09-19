"""Stage accounting must protect real retrieval, not just the final shortlist."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import browser_budget as budget
import check_shortlist as shortlist
import check_search_coverage as coverage
import journal
import record_browser_capture as browser
import run_tool
from test_browser_fallback import setup_capture, dump
from test_search_coverage import build, close, save


def journey(ws, counts=(10, 10, 5), site='51job'):
    views, stages = [], []
    for index, count in enumerate(counts):
        rows = [dict(source_id=f'job-{index}-{n}', title=f'Job {index}-{n}',
                     raw_text=f'job-{index}-{n} Job {index}-{n} Sales', url='https://example.com/')
                for n in range(count)]
        views.append(dict(url='https://example.com/', text='\n'.join(r['raw_text'] for r in rows) or 'No matching jobs',
                          links=[], retrieved_at='2099-01-01T00:00:00Z', catalog_rows=rows))
        stages.append(dict(page=min(index + 1, 2), max_rows=count, row_count=count, row_selector='.job'))
    snap = copy.deepcopy(views[-1])
    if len(views) > 1:
        snap['navigation_steps'] = [dict(source_snapshot=before, result=after) for before, after in zip(views, views[1:])]
    snap['navigation_budget'] = dict(version=1, workspace=str(ws.resolve()), site=site, max_rows=25,
                                    max_pages=2, used_rows=0, used_pages=[], stages=stages,
                                    observed_rows=sum(counts), observed_pages=sorted({s['page'] for s in stages if s['row_count']}))
    return snap


def imported(ws, snap, site='51job', suffix='stages'):
    raw, rows = ws / f'raw/{site}-{suffix}.json', ws / f'raw/{site}-{suffix}-rows.json'
    dump(raw, snap)
    dump(rows, snap['catalog_rows'])
    assert browser.main(['--workspace', str(ws), '--site', site, '--snapshot-file', str(raw),
                         '--rows-file', str(rows), '--fallback-reason', 'unsupported_extraction',
                         '--query', 'IB Analyst']) == 0
    return browser.read_retrieval_calls(ws)[-1]


def test_all_stages_count_once_and_page_numbers_are_distinct(tmp_path):
    ws, *_ = setup_capture(tmp_path)
    snap = journey(ws)
    call = imported(ws, snap)
    assert call['row_count'] == 5
    assert call['search_row_count'] == 25
    assert call['search_pages'] == [1, 2]
    assert browser.validate_record(call, ws) == []
    assert budget.used([call], '51job') == (25, [1, 2])
    assert not shortlist._check_caps_against_the_run({'max_rows_per_round':25, 'max_pages_per_site':2}, {}, [], [call])
    assert 'ROWS_ABOVE_CAP' in shortlist._check_caps_against_the_run({'max_rows_per_round':20}, {}, [], [call])[0]


@pytest.mark.parametrize('change,match', [
    ('legacy', 'MISSING'), ('count', 'DOM count'), ('aggregate', 'aggregate'),
    ('chain', 'chain'), ('final', 'final snapshot'), ('row', 'copied verbatim'),
    ('overflow', 'overflow'), ('cumulative', 'allowance'), ('pages', 'allowance'),
    ('workspace', 'another round'), ('prior', 'prior round'), ('limits', 'limits differ'),
    ('error', 'INCOMPLETE')])
def test_invalid_journeys_are_preserved_but_cannot_pass(tmp_path, change, match):
    ws, *_ = setup_capture(tmp_path)
    snap = journey(ws)
    b = snap['navigation_budget']
    if change == 'legacy': del snap['navigation_budget']
    elif change == 'count': b['stages'][0]['row_count'] = 9
    elif change == 'aggregate': b['observed_rows'] = 5
    elif change == 'chain': snap['navigation_steps'][1]['source_snapshot'] = dict(snap['navigation_steps'][1]['source_snapshot'], text='Changed')
    elif change == 'final': snap['text'] += '\nChanged'
    elif change == 'row': snap['navigation_steps'][0]['source_snapshot']['catalog_rows'][0]['raw_text'] = 'Invented'
    elif change == 'overflow': b['stages'][0]['max_rows'] = 9
    elif change == 'cumulative': b['used_rows'] = 1
    elif change == 'pages': b['used_pages'] = [3]
    elif change == 'workspace': b['workspace'] = str(ws.parent)
    elif change == 'prior': b['used_pages'] = [1]
    elif change == 'limits': b['max_pages'] = 1; b['stages'][1]['page'] = b['stages'][2]['page'] = 1; b['observed_pages'] = [1]
    elif change == 'error': snap['navigation_error'] = {'message':'Click failed'}
    call = imported(ws, snap)
    assert match in ' '.join(browser.validate_record(call, ws))
    assert (ws / call['snapshot_file']).exists()


def test_unexpected_overflow_is_counted_and_stops_next_read(tmp_path):
    ws, *_ = setup_capture(tmp_path)
    snap = journey(ws, (26,))
    snap['navigation_budget']['stages'][0]['max_rows'] = 20
    snap['budget_exceeded'] = True
    call = imported(ws, snap)
    assert call['search_row_count'] == 26
    assert call['classification'] == 'transport'
    assert call['empty_result'] is False
    assert 'EXCEEDED' in browser.validate_record(call, ws)[0]
    with pytest.raises(ValueError, match='EXCEEDED'):
        budget.prepare(ws, '51job', {'stages':[]}, [call], browser.validate_record)


def test_prepare_uses_previous_calls_and_requires_import(tmp_path):
    ws, *_ = setup_capture(tmp_path)
    snap = journey(ws, (10,))
    pending = ws / 'raw/51job-pending.json'
    dump(pending, snap)
    with pytest.raises(ValueError, match='pending capture'):
        budget.prepare(ws, '51job', {'stages':[]}, [], browser.validate_record)
    pending.unlink()
    call = imported(ws, snap)
    plan = {'stages':[{'max_rows':10, 'page':2, 'row_selector':'.job'}]}
    actual = budget.prepare(ws, '51job', plan, [call], browser.validate_record)
    assert (actual['used_rows'], actual['used_pages']) == (10, [1])
    with (ws / 'journal.jsonl').open('a') as f: f.write('{broken\n')
    with pytest.raises(ValueError, match='unparsable'):
        budget.prepare(ws, '51job', plan, [call], browser.validate_record)


def test_adapter_offsets_and_browser_counts_share_the_same_pages():
    calls = [dict(action='adapter_call', site='indeed', command='search', exit_code=0, row_count=10,
                  command_line='opencli indeed search IB --start 20'),
             dict(action='browser_call', site='indeed', command='detail', exit_code=1,
                  search_row_count=5, search_pages=[1])]
    assert budget.used(calls, 'indeed') == (15, [1, 3])


@pytest.mark.parametrize('wall', [False, True])
def test_intermediate_leads_cannot_disappear_behind_empty_or_refused_final_page(tmp_path, wall):
    ws, data = build(tmp_path)
    (ws / 'brief.yaml').write_text('max_rows_per_round: 25\nmax_pages_per_site: 2\n')
    snap = journey(ws, (2, 0), site='employer')
    if wall:
        snap['text'] = snap['navigation_steps'][-1]['result']['text'] = 'Please sign in to continue'
    call = imported(ws, snap, site='employer')
    assert call['empty_result'] is False
    ref = dict(file=call['snapshot_file'], sha256=journal.sha256_file(ws / call['snapshot_file']), quote=snap['text'])
    close(ws, data, ref, status='blocked' if wall else 'done')
    if wall:
        (ws / 'report.md').write_text(data['checks'][0]['reason'])
    assert 'unprocessed' in ' '.join(coverage.inspect(ws)).lower()
    data['leads'] = [dict(site='employer', source_id=f'job-0-{n}', status='excluded', reason_code='wrong_role',
                          reason='Sales role outside IB', evidence={**ref, 'quote':f'Job 0-{n} Sales'}) for n in range(2)]
    save(ws, data)
    assert coverage.inspect(ws) == []


def runtime(tmp_path):
    root = tmp_path / 'runtime'; root.mkdir()
    (root / 'runtime.json').write_text(json.dumps(dict(python=sys.executable, node='node',
        opencli='/private/node_modules/@jackwener/opencli/dist/src/main.js', browser='chrome')))
    return root


def test_launcher_uses_prepared_python_for_budget_dependencies(tmp_path, monkeypatch):
    root = runtime(tmp_path)
    data = json.loads((root / 'runtime.json').read_text()); data['python'] = '/prepared/python'
    (root / 'runtime.json').write_text(json.dumps(data))
    calls = []
    monkeypatch.setattr(run_tool.subprocess, 'run', lambda cmd, **kw: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0))
    args = ['--root', str(root), 'browser', '--budget-plan', 'a plan.json']
    assert run_tool.main(args) == 0
    assert calls == [['/prepared/python', str(Path(run_tool.__file__).resolve()), *args]]


@pytest.mark.parametrize('failure', ['endpoint', 'capture'])
def test_launcher_cleans_private_budget_and_preserves_arguments(tmp_path, monkeypatch, failure):
    ws, *_ = setup_capture(tmp_path)
    root = runtime(tmp_path)
    plan = ws / 'plan.json'; dump(plan, {'stages':[dict(page=1,max_rows=10,row_selector='.job')]})
    files = []
    def run(cmd, **kw):
        if 'endpoint' in cmd:
            return subprocess.CompletedProcess(cmd, 1 if failure == 'endpoint' else 0, stdout='ws://127.0.0.1/devtools/browser/test', stderr='No connection')
        file = Path(cmd[cmd.index('--budget-file') + 1]); files.append(file)
        assert json.loads(file.read_text())['used_rows'] == 0
        assert '--budget-plan' not in cmd and '--workspace' not in cmd
        raise OSError('Capture failed')
    monkeypatch.setattr(run_tool.subprocess, 'run', run)
    with pytest.raises((OSError, ValueError)):
        run_tool.main(['--root', str(root), 'browser', '--workspace', str(ws), '--site', '51job',
                      '--budget-plan', str(plan), '--url', 'https://example.com/', '--output', str(ws / 'raw/51job-new.json')])
    assert all(not f.exists() for f in files)
    assert len(files) == (failure == 'capture')


def test_wrong_dom_contract_never_looks_like_successful_empty_search(tmp_path):
    ws, *_ = setup_capture(tmp_path)
    snap = journey(ws, (2,))
    snap['catalog_rows'][0].update(source_id='', title='', raw_text='')
    raw, rows = ws / 'raw/51job-bad-selector.json', ws / 'raw/51job-bad-selector-rows.json'
    dump(raw, snap); dump(rows, [])
    assert browser.main(['--workspace', str(ws), '--site', '51job', '--snapshot-file', str(raw),
                         '--rows-file', str(rows), '--fallback-reason', 'unsupported_extraction', '--query', 'IB']) == 0
    call = browser.read_retrieval_calls(ws)[-1]
    assert call['classification'] == 'transport'
    assert call['exit_code'] == 1 and call['empty_result'] is False
    assert call['budget_error'] and browser.validate_record(call, ws)


def test_pending_inspection_is_preserved_and_blocks_same_round_continuation(tmp_path):
    ws, *_ = setup_capture(tmp_path)
    snap = journey(ws, (0, 0))
    snap['catalog_accounting_pending'] = True
    snap['navigation_steps'][0]['result']['catalog_accounting_pending'] = True
    for index, stage in enumerate(snap['navigation_budget']['stages']):
        stage.update(row_selector=None, max_rows=25 if index else 0, row_count=None if index else 0)
    snap['navigation_budget']['observed_rows'] = None
    call = imported(ws, snap)
    assert call['classification'] == 'transport' and call['empty_result'] is False
    assert 'PENDING' in browser.validate_record(call, ws)[0]
    with pytest.raises(ValueError, match='PENDING'):
        budget.prepare(ws, '51job', {'stages':[]}, [call], browser.validate_record)


def test_observed_homepage_without_catalog_does_not_consume_job_rows(tmp_path):
    ws, *_ = setup_capture(tmp_path)
    snap = journey(ws, (0, 10))
    snap['navigation_budget']['stages'][0]['row_selector'] = None
    call = imported(ws, snap)
    assert call['search_row_count'] == 10 and not browser.validate_record(call, ws)


def test_unknown_catalog_refusal_keeps_manual_recovery_instead_of_retrying(tmp_path):
    ws, *_ = setup_capture(tmp_path)
    snap = journey(ws, (0, 0))
    snap['text'] = snap['navigation_steps'][0]['result']['text'] = '请输入验证码'
    for index, stage in enumerate(snap['navigation_budget']['stages']):
        stage.update(row_selector=None, max_rows=25 if index else 0)
    call = imported(ws, snap)
    assert call['classification'] == 'platform_limit'
    assert 'Ask the user' in call['remedy']
    assert not browser.validate_record(call, ws)
    assert browser.check_stop_order([call,dict(action='browser_call',site='51job',url=snap['url'])])
