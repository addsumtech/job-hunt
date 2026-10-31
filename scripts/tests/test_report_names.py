import pathlib
import sys

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import deliver
import journal
from report_names import report_stem
from test_deliver import build, run, MANIFEST


def write(ws, name, data):
    (ws / name).write_text(yaml.safe_dump(data, allow_unicode=True), encoding='utf-8')


def test_three_cases_and_four_modes_have_identifiable_names(tmp_path):
    stems = []
    for company, role in [('Acme', 'Product Manager'), ('Beta', 'Data Analyst'), ('Gamma', 'Software Engineer')]:
        ws = tmp_path / (company + '-2026-10-31')
        ws.mkdir()
        write(ws, 'tailored-profile.yaml', {'meta': {'name': '沈序安'}})
        write(ws, 'posting.yaml', {'company': company, 'role_title': role})
        stem = report_stem(ws, 'apply')
        assert stem == f'沈序安－{company}－{role}－2026-10-31－投递建议报告'
        stems.append(stem)
    assert len(set(stems)) == 3
    assert len({report_stem(ws, mode) for mode in ['discover', 'assess', 'apply', 'interview']}) == 4


def test_discovery_uses_real_brief_fields_and_profile_precedence(tmp_path):
    write(tmp_path, 'candidate-profile.yaml', {'meta': {'name': '李明'}})
    write(tmp_path, 'profile.yaml', {'meta': {'name': 'Old'}})
    write(tmp_path, 'brief.yaml', {'locations': ['伦敦', '曼彻斯特'], 'target_titles': ['数据分析师']})
    assert report_stem(tmp_path, 'discover') == '李明－伦敦－曼彻斯特－数据分析师－岗位推荐报告'
    write(tmp_path, 'posting.yaml', {'company': 'Acme', 'title': 'Analyst'})
    assert report_stem(tmp_path, 'assess') == '李明－Acme－Analyst－岗位评估报告'


def test_bad_metadata_and_external_symlinks_are_skipped(tmp_path):
    ws = tmp_path / 'empty'
    ws.mkdir()
    (tmp_path / 'secret.yaml').write_text('meta: {name: OUTSIDE}')
    (ws / 'candidate-profile.yaml').symlink_to(tmp_path / 'secret.yaml')
    (ws / 'tailored-profile.yaml').write_bytes(b'\xff')
    write(ws, 'profile.yaml', ['not a mapping'])
    assert report_stem(ws, 'discover') == '求职建议报告'
    write(ws, 'posting.yaml', {'company': ['wrong type'], 'role_title': 123})
    assert report_stem(ws, 'apply') == '求职建议报告'


def test_filename_safety_long_names_and_determinism(tmp_path):
    write(tmp_path, 'candidate-profile.yaml', {'meta': {'name': '../李明\n\u202e/?:*'}})
    stems = []
    for last in ['甲', '乙']:
        write(tmp_path, 'posting.yaml', {'company': '公司' * 100, 'title': last})
        stem = report_stem(tmp_path, 'apply')
        assert len(stem.encode('utf-8')) <= 200 and stem.endswith('－投递建议报告')
        assert all(char not in stem for char in '/\\\n\u202e?:*')
        assert report_stem(tmp_path, 'apply') == stem
        stems.append(stem)
    assert stems[0] != stems[1]


@pytest.mark.parametrize('client_edited', [False, True])
def test_named_redelivery_migrates_only_owned_unedited_legacy_report(tmp_path, capsys, client_edited):
    ws = build(tmp_path)
    journal.append(ws, {'action': 'mode_entry', 'mode': 'apply'})
    dest = tmp_path / 'delivery'
    assert run(ws, dest, '--no-pdf') == 0
    old = dest / '报告/求职建议报告.md'
    if client_edited:
        old.write_text('Client edited this report.')
    write(ws, 'posting.yaml', {'company': 'Acme', 'role_title': 'Analyst'})
    assert run(ws, dest, '--no-pdf') == 0
    new = dest / '报告/Acme－Analyst－2026-09-06－投递建议报告.md'
    assert new.read_bytes() == (ws / 'report.md').read_bytes()
    assert old.exists() == client_edited
    if client_edited:
        assert old.read_text() == 'Client edited this report.'
        assert 'NOTICE_STALE_FILE_KEPT' in capsys.readouterr().err
    # The new namespace must remain readable on subsequent delivery.
    assert run(ws, dest, '--no-pdf') == 0
    assert (dest / MANIFEST).is_file()


def test_unrecorded_named_report_is_protected(tmp_path):
    ws = build(tmp_path)
    write(ws, 'posting.yaml', {'company': 'Acme', 'role_title': 'Analyst'})
    dest = tmp_path / 'delivery'
    foreign = dest / '报告/另一人－岗位推荐报告.md'
    foreign.parent.mkdir(parents=True)
    foreign.write_text('Keep this foreign report.')
    assert run(ws, dest, '--no-pdf') == 0
    assert foreign.read_text() == 'Keep this foreign report.'
    assert len(list(dest.rglob('*报告.md'))) == 2


@pytest.mark.parametrize('rel', ['报告/../../victim－投递建议报告.md', '报告/other.txt',
                                '简历/other－岗位推荐报告.pdf', '报告/other－岗位推荐报告.exe',
                                '报告/\ud800－投递建议报告.md', '报告/\u202e－投递建议报告.md'])
def test_dynamic_manifest_namespace_stays_inside_report_documents(rel):
    assert not deliver._manifest_rel_ok('', rel)
