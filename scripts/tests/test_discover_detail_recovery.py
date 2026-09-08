"""A synthetic successful detail response complements the real blank capture."""
import copy
import json
import pathlib
import subprocess
import sys

import discover_fixtures as fx
import check_shortlist

ROOT = pathlib.Path(__file__).resolve().parents[2]


def classify(workspace, command, path):
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/check_opencli_result.py'),
                             '--workspace', str(workspace), '--site', 'indeed',
                             '--command', command, '--exit-code', '0', '--stdout-file', str(path),
                             '--command-line', f'opencli indeed {command} synthetic-recovery-001 -f json'],
                            text=True, encoding="utf-8", capture_output=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_blank_title_is_recovered_only_after_a_successful_detail_capture(tmp_path):
    workspace = fx.build_english_workspace(tmp_path)
    record = json.loads((ROOT / 'evals/fixtures/opencli/indeed-detail-recovery-synthetic.json').read_text())
    detail = record['stdout'][0]
    blank = dict(detail, title='', description='')
    search_path = workspace / 'raw/indeed-search.json'
    search_path.write_text(json.dumps([blank]))
    before = search_path.read_bytes()
    classified = classify(workspace, 'search', search_path)
    assert classified['needs_detail_recovery'] is True
    assert classified['empty_result'] is False
    row = copy.deepcopy(fx.load_shortlist(workspace)['rows'][0])
    row.update(id='indeed-' + blank['id'], source_site='indeed', source_id=blank['id'], title='', company=blank['company'],
               location=blank['location'], salary='', url=blank['url'], raw_text=json.dumps(blank))
    initial = check_shortlist.check_rows({'rows': [row]}, {'indeed': {'indeed-search.json': search_path.read_text()}})
    assert any(f.startswith('EMPTY_TITLE:') for f in initial)
    detail_path = workspace / 'raw/indeed-detail.json'
    detail_path.write_text(json.dumps([detail]))
    recovered = classify(workspace, 'detail', detail_path)
    assert recovered['classification'] == 'ok' and not recovered['needs_detail_recovery']
    row.update(title=detail['title'], raw_text=json.dumps(detail))
    findings = check_shortlist.check_rows({'rows': [row]},
                                        {'indeed': {'indeed-search.json': search_path.read_text(),
                                         'indeed-detail.json': detail_path.read_text()}})
    assert findings == [], findings
    assert search_path.read_bytes() == before
