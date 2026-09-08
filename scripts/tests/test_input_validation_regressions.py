"""Malformed generated artifacts must fail visibly and leave a gate receipt."""
import json

import pytest
import yaml

import journal
import discover_fixtures as discover
import mock_fixtures as mock
import test_check_apply as apply_fixture
import test_check_assessment as assess_fixture
import check_apply
import check_assessment
import check_mock
import check_shortlist
import check_evidence_refs


def setup(mode, tmp_path):
    if mode == 'discover':
        ws = discover.build_workspace(tmp_path)
        return ws, check_shortlist.main, ['--workspace', str(ws)]
    if mode == 'assess':
        ws, market, root = assess_fixture.build(tmp_path)
        return ws, check_assessment.main, ['--workspace', str(ws), '--market-dir', str(market),
            '--skill-root', str(root), '--today', '2026-08-09']
    if mode == 'interview':
        ws = mock.build(tmp_path)
        return ws, check_mock.main, ['--workspace', str(ws), '--round', '2',
            '--skill-root', str(tmp_path / 'skill'), '--today', '2026-08-09']
    root = apply_fixture._skill_root(tmp_path)
    ws = apply_fixture._good_workspace(tmp_path, root)
    return ws, check_apply.main, apply_fixture._argv(ws, root)


COLLECTIONS = [
    ('discover', 'shortlist.yaml', 'rows'),
    ('discover', 'shortlist.yaml', 'sources'),
    ('discover', 'shortlist.yaml', 'detail_fetch_exceptions'),
    ('discover', 'brief.yaml', 'target_titles'),
    ('discover', 'brief.yaml', 'markets'),
    ('assess', 'fit-assessment.yaml', 'requirements'),
    ('assess', 'fit-assessment.yaml', 'stated_conditions'),
    ('assess', 'fit-assessment.yaml', 'actions'),
    ('assess', 'fit-assessment.yaml', 'conventions_rendered'),
    ('interview', 'mock/question-log.yaml', 'questions'),
    ('interview', 'mock/question-log.yaml', 'rejected'),
    ('interview', 'fit-assessment.yaml', 'requirements'),
    ('interview', 'posting.yaml', 'must_haves'),
]


def rejects_with_receipt(ws, fn, args):
    before = len(journal.read_receipts(ws))
    assert fn(args) in (1, 2)
    receipts = journal.read_receipts(ws)
    assert len(receipts) == before + 1
    assert receipts[-1]['verdict'] in ('fail', 'could_not_run')
    assert receipts[-1]['findings']
    assert journal.receipt_intact(receipts[-1])


@pytest.mark.parametrize('mode', ['discover', 'assess', 'interview', 'apply'])
def test_ordinary_workspaces_still_pass(mode, tmp_path):
    ws, fn, args = setup(mode, tmp_path)
    assert fn(args) == 0


@pytest.mark.parametrize('mode,file,key', COLLECTIONS)
@pytest.mark.parametrize('bad', ['broken', 17, {'wrong': 'shape'}])
def test_bad_collection_shape_is_not_iterated_or_silently_ignored(mode, file, key, bad, tmp_path):
    ws, fn, args = setup(mode, tmp_path)
    path = ws / file
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data[key] = bad
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    rejects_with_receipt(ws, fn, args)


@pytest.mark.parametrize('mode,file', [
    ('discover', 'shortlist.md'), ('assess', 'fit-assessment.md'),
    ('interview', 'mock/assessment-2.md'), ('apply', 'interview-brief.md')])
def test_unreadable_deliverable_never_leaves_a_clean_result(mode, file, tmp_path):
    ws, fn, args = setup(mode, tmp_path)
    (ws / file).write_bytes(b'\xff\xfe\x00')
    rejects_with_receipt(ws, fn, args)


@pytest.mark.parametrize('mode,gate', [('discover','check_no_write'), ('assess','evidence_blocks'),
    ('apply','lint_cv'), ('interview','lint_no_prediction')])
@pytest.mark.parametrize('field,bad', [('input_hashes', ['not-a-map']), ('findings', [42])])
def test_signed_receipt_with_invalid_shape_cannot_authorise_delivery(mode, gate, field, bad, tmp_path):
    ws, fn, args = setup(mode, tmp_path)
    record = {'action':'gate', 'gate':gate, 'verdict':'pass', 'input_hashes':{}, 'findings':[]}
    record[field] = bad
    journal.append(ws, journal.sign_receipt(record))
    rejects_with_receipt(ws, fn, args)


@pytest.mark.parametrize('bad', ['not json', '[]', '{"blocks":17}', '{"blocks":[{"id":[]}]}'])
@pytest.mark.parametrize('gate', ['assess', 'refs'])
def test_bad_evidence_json_is_reported_by_both_readers(bad, gate, tmp_path):
    ws, fn, args = setup('assess', tmp_path)
    (ws / 'evidence-blocks.json').write_text(bad, encoding="utf-8")
    if gate == 'refs':
        fn, args = check_evidence_refs.main, ['--workspace', str(ws), '--check-only']
    rejects_with_receipt(ws, fn, args)


@pytest.mark.parametrize('bad', ['not-a-list', 3, ['not-a-mapping']])
def test_nested_evidence_shape_is_not_a_traceback(bad, tmp_path):
    ws, fn, args = setup('assess', tmp_path)
    p = ws / 'fit-assessment.yaml'
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    data['requirements'][0]['evidence'] = bad
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    rejects_with_receipt(ws, fn, args)


def test_empty_interview_brief_is_not_a_finished_apply_package(tmp_path):
    ws, fn, args = setup('apply', tmp_path)
    (ws / 'interview-brief.md').write_text(' \n', encoding="utf-8")
    rejects_with_receipt(ws, fn, args)
