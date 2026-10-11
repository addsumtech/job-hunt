"""Native search evidence must survive capture and cannot stand in for a JD."""
import json
import subprocess
import sys

import pytest
import yaml

import check_candidate_match as candidate
import check_no_write
import check_search_coverage as coverage
import check_shortlist
import journal
import record_browser_capture as browser
import run_tool
import search_capture as search


def workspace(tmp_path):
    ws = tmp_path / 'round'; (ws / 'raw').mkdir(parents=True)
    (ws / 'brief.yaml').write_text('max_rows_per_round: 25\ntarget_count: 1\n')
    (ws / 'shortlist.yaml').write_text('rows: []\n')
    (ws / 'report.md').write_text('Search report\n')
    data = dict(plan=dict(sources=[dict(id='web', site='anysearch', label='Public search', method='search')],
                          directions=[dict(id='ib', label='IB', query='IB Analyst')]), checks=[], leads=[])
    (ws / coverage.FILE).write_text(yaml.safe_dump(data))
    coverage.record_plan(ws)
    return ws, data


def invoke(ws, monkeypatch, rows=None, status=0, stderr=b''):
    envelope = dict(code=0, data=dict(results=[] if rows is None else rows))
    def execute(cmd, **kwargs):
        assert cmd[-2:] == ['--format', 'json']
        return subprocess.CompletedProcess(cmd, status, json.dumps(envelope).encode(), stderr)
    monkeypatch.setattr(search.subprocess, 'run', execute)
    rc = search.run(ws, ['node', 'anysearch.js'], ['search', 'IB Analyst', '--max_results', '3'], {})
    return rc, browser.read_retrieval_calls(ws)[-1]


def test_recorded_http_search_closes_coverage_and_no_write(tmp_path, monkeypatch):
    ws, data = workspace(tmp_path)
    rc, call = invoke(ws, monkeypatch)
    assert rc == 0 and call['empty_result'] is True
    assert search.validate_record(call, ws) == []
    assert check_no_write.scan([call], ws / 'cache', False, ws) == []
    data['checks'] = [dict(source='web', direction='ib', status='done', reason='No results returned.',
        evidence=dict(file=call['stdout_file'], sha256=call['input_hashes'][call['stdout_file']], quote='"results": []'))]
    (ws / coverage.FILE).write_text(yaml.safe_dump(data))
    assert coverage.inspect(ws) == []
    assert not check_shortlist._declared_queries_never_run({'target_titles':['IB Analyst']}, {}, [call])
    assert candidate._detail_files([call], ws) == {}


@pytest.mark.parametrize('alter', ['raw', 'metadata', 'command', 'backend', 'path'])
def test_modified_native_search_cannot_pass_evidence_gates(tmp_path, monkeypatch, alter):
    ws, _ = workspace(tmp_path); _, call = invoke(ws, monkeypatch)
    if alter == 'raw': (ws / call['stdout_file']).write_text('{"data":{"results":[]}}')
    elif alter == 'metadata': call['row_count'] = 7
    elif alter == 'command': call['command'] = 'detail'
    elif alter == 'backend': call['backend'] = 'browser'
    else: call['stdout_file'] = '../outside.json'
    assert search.validate_record(call, ws)
    assert check_no_write.scan([call], ws / 'cache', False, ws)


def test_provider_refusal_is_preserved_and_stops_next_call(tmp_path, monkeypatch):
    ws, _ = workspace(tmp_path)
    rc, call = invoke(ws, monkeypatch, status=1, stderr=b'HTTP 429 Too many requests')
    assert rc == 1 and call['classification'] == 'platform_limit' and not call['empty_result']
    assert search.validate_record(call, ws) == []
    with pytest.raises(ValueError, match='READ_AFTER_STOP'):
        search.preflight(ws, 'anysearch')


@pytest.mark.parametrize('stdout', ['not json', '{}', '{"code":0,"data":{"results":{}}}',
    '{"code":0,"data":{"results":[{"title":"Job","url":"javascript:alert(1)"}]}}'])
def test_success_exit_does_not_turn_malformed_output_into_empty_search(stdout):
    assert search.classify(stdout, '', 0) == dict(classification='transport', row_count=0, empty_result=False)


@pytest.mark.parametrize('change, message', [('missing', 'missing'), ('source', 'UNPLANNED'),
                                          ('changed', 'registration'), ('pending', 'PENDING_CAPTURE')])
def test_preflight_rejects_missing_ownership_before_network(tmp_path, change, message):
    ws, data = workspace(tmp_path)
    if change == 'missing': (ws / coverage.FILE).unlink()
    elif change == 'changed':
        data['plan']['directions'][0]['query'] = 'Other'
        (ws / coverage.FILE).write_text(yaml.safe_dump(data))
    elif change == 'pending':
        (ws / 'raw/employer-detail.json').write_text(json.dumps(dict(url='https://example.com/job', text='JD',
            links=[], retrieved_at='2026-10-11T00:00:00Z')))
    with pytest.raises((ValueError, journal.YamlUnreadable), match=message):
        search.preflight(ws, 'other' if change == 'source' else 'anysearch')


def test_budget_and_http_leads_cannot_be_promoted_to_postings(tmp_path, monkeypatch):
    ws, _ = workspace(tmp_path)
    rows = [dict(title='IB Analyst', url=f'https://employer.example/jobs/{i}', snippet='A search snippet') for i in range(3)]
    _, call = invoke(ws, monkeypatch, rows)
    (ws / 'brief.yaml').write_text('max_rows_per_round: 3\n')
    with pytest.raises(ValueError, match='SEARCH_BUDGET'):
        search.run(ws, [], ['search', 'IB Analyst'], {})
    findings = check_shortlist.check_run(ws, {'rows':[{'source_site':'anysearch'}]}, {}, '', [call])
    assert any('SEARCH_LEAD_NOT_POSTING' in f for f in findings)


@pytest.mark.parametrize('flags', [['--api_key=private'], ['--api_key', 'private'],
    ['-m', '1', '--max_results', '10'], ['--max_results'], ['--unknown', '3']])
def test_invalid_or_secret_arguments_never_reach_network(tmp_path, monkeypatch, flags):
    ws, _ = workspace(tmp_path)
    monkeypatch.setattr(search.subprocess, 'run', lambda *a, **k: pytest.fail('network reached'))
    with pytest.raises(ValueError):
        search.run(ws, [], ['search', 'IB Analyst', *flags], {})
    assert not browser.read_retrieval_calls(ws)


def test_provider_overflow_cannot_be_valid_coverage(tmp_path, monkeypatch):
    ws, _ = workspace(tmp_path)
    rc, call = invoke(ws, monkeypatch, [dict(title='Job', url=f'https://example.com/{i}') for i in range(4)])
    assert rc == 1 and call['row_count'] == 4
    assert 'row budget' in search.validate_record(call, ws)[0]


def test_workspace_does_not_bypass_browser_navigation_budget(tmp_path, monkeypatch):
    ws, _ = workspace(tmp_path)
    runtime = tmp_path / 'runtime'; runtime.mkdir()
    (runtime / 'runtime.json').write_text(json.dumps(dict(python=sys.executable, node='node', browser='chrome',
        opencli='/private/node_modules/@jackwener/opencli/dist/src/main.js')))
    monkeypatch.setattr(run_tool.subprocess, 'run', lambda *a, **k: pytest.fail('browser reached'))
    with pytest.raises(ValueError, match='Navigation requires'):
        run_tool.main(['--root', str(runtime), '--workspace', str(ws), 'browser', '--steps-file', 'steps.json'])


def test_launcher_records_native_search_without_browser_endpoint(tmp_path, monkeypatch):
    ws, _ = workspace(tmp_path)
    runtime = tmp_path / 'runtime'; runtime.mkdir()
    (runtime / 'runtime.json').write_text(json.dumps(dict(python=sys.executable, node='node',
        opencli='/private/node_modules/@jackwener/opencli/dist/src/main.js')))
    calls = []
    def execute(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, b'{"code":0,"data":{"results":[]}}', b'')
    monkeypatch.setattr(run_tool.subprocess, 'run', execute)
    assert run_tool.main(['--root', str(runtime), '--workspace', str(ws), 'anysearch', 'search', 'IB Analyst']) == 0
    assert len(calls) == 1 and 'endpoint' not in calls[0]
    assert len(browser.read_retrieval_calls(ws)) == 1


def test_native_lead_requires_same_url_to_resolve_to_real_posting(tmp_path, monkeypatch):
    ws, data = workspace(tmp_path)
    url = 'https://employer.example/jobs/1234'
    _, call = invoke(ws, monkeypatch, [dict(title='IB Analyst', url=url, snippet='London')])
    data['checks'] = [dict(source='web', direction='ib', status='done', reason='Reviewed lead.',
        evidence=dict(file=call['stdout_file'], sha256=call['input_hashes'][call['stdout_file']], quote='IB Analyst'))]
    data['leads'] = [dict(site='anysearch', source_id='1234', status='retained', row_id='real-job')]
    (ws / coverage.FILE).write_text(yaml.safe_dump(data))
    row = dict(id='real-job', source_site='employer', source_id='1234', title='Analyst', url=url)
    (ws / 'shortlist.yaml').write_text(yaml.safe_dump(dict(rows=[row])))
    assert coverage.inspect(ws) == []
    row['url'] = 'https://employer.example/jobs/9999'
    (ws / 'shortlist.yaml').write_text(yaml.safe_dump(dict(rows=[row])))
    assert 'does not match' in coverage.inspect(ws)[0]


@pytest.mark.parametrize('access', ['read', 'write', None])
def test_opencli_wrapper_records_only_metadata_verified_reads(tmp_path, monkeypatch, capsys, access):
    ws, _ = workspace(tmp_path)
    runtime = tmp_path / 'runtime'; runtime.mkdir()
    (runtime / 'runtime.json').write_text(json.dumps(dict(python=sys.executable, node='node', browser='chrome',
        opencli='/private/node_modules/@jackwener/opencli/dist/src/main.js')))
    calls = []
    def execute(cmd, **kw):
        calls.append(cmd)
        if '--help' in cmd:
            return subprocess.CompletedProcess(cmd, 0, yaml.safe_dump(dict(commands=[dict(name='search',access=access)])).encode(), b'')
        if 'endpoint' in cmd:
            return subprocess.CompletedProcess(cmd, 0, 'ws://local/test', '')
        return subprocess.CompletedProcess(cmd, 0, b'[]', b'')
    monkeypatch.setattr(run_tool.subprocess, 'run', execute)
    args = ['--root', str(runtime), '--workspace', str(ws), 'opencli', 'anysearch', 'search', 'IB Analyst', '-f', 'json']
    if access == 'read':
        assert run_tool.main(args) == 0
        assert json.loads(capsys.readouterr().out) == []
        call = browser.read_retrieval_calls(ws)[-1]
        assert call['action'] == 'adapter_call'
        assert check_no_write.scan([call], ws / 'raw/opencli-help', False, ws) == []
    else:
        with pytest.raises(ValueError, match='access: read'):
            run_tool.main(args)
        assert len(calls) == 1
        assert not browser.read_retrieval_calls(ws)
