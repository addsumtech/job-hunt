import pathlib
from pathlib import Path
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


def test_a_prepare_session_is_named_from_its_direction(tmp_path):
    ws = tmp_path / '2026-11-18-band-5-nurse-uk'
    ws.mkdir()
    write(ws, 'direction.yaml', {'target_titles': ['Staff Nurse (Band 5)', 'Community nurse'],
                                 'family': 'clinical', 'market': 'uk'})
    assert report_stem(ws, 'prepare') == 'Staff Nurse (Band 5)－2026-11-18－面试准备计划'


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
    old = dest / deliver.client_path(Path('report.md'), ws)  # the generic name
    if client_edited:
        old.write_text('Client edited this report.')
    write(ws, 'posting.yaml', {'company': 'Acme', 'role_title': 'Analyst'})
    assert run(ws, dest, '--no-pdf') == 0
    new = dest / deliver.client_path(Path('report.md'), ws)
    assert new != old and new.name.startswith('Acme－Analyst－2026-09-06－')
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
    reports = [p for p in dest.rglob('*.md') if p.parent.name in deliver._REPORT_FOLDERS]
    assert len(reports) == 2, 'the foreign report and this round\'s (in its own subfolder)'


@pytest.mark.parametrize('rel', ['报告/../../victim－投递建议报告.md', '报告/other.txt',
                                '简历/other－岗位推荐报告.pdf', '报告/other－岗位推荐报告.exe',
                                '报告/\ud800－投递建议报告.md', '报告/\u202e－投递建议报告.md'])
def test_dynamic_manifest_namespace_stays_inside_report_documents(rel):
    assert not deliver._manifest_rel_ok('', rel)


def test_a_bilingual_query_list_does_not_become_the_filename(tmp_path):
    """Measured 2026-11-01: three run-order queries in two languages made the name."""
    write(tmp_path, 'candidate-profile.yaml', {'meta': {'name': 'Donghang Lyu'}})
    write(tmp_path, 'brief.yaml', {'locations': ['Netherlands'], 'target_titles': [
        'medical imaging AI', 'medische beeldvorming', 'LLM engineer', 'machine learning engineer']})
    assert report_stem(tmp_path, 'discover') == 'Donghang Lyu－Netherlands－medical imaging AI－岗位推荐报告'


@pytest.mark.parametrize('label,expected', [
    ('AI/ML 初级', 'Donghang Lyu－Netherlands－AIML 初级－岗位推荐报告'),
    ('  ', 'Donghang Lyu－Netherlands－medical imaging AI－岗位推荐报告'),
    (['not', 'a string'], 'Donghang Lyu－Netherlands－medical imaging AI－岗位推荐报告'),
])
def test_report_label_names_the_direction_in_the_readers_words(tmp_path, label, expected):
    write(tmp_path, 'candidate-profile.yaml', {'meta': {'name': 'Donghang Lyu'}})
    write(tmp_path, 'brief.yaml', {'locations': ['Netherlands'], 'report_label': label,
                                   'target_titles': ['medical imaging AI', 'LLM engineer']})
    assert report_stem(tmp_path, 'discover') == expected


@pytest.mark.parametrize("space", ["\u3000", "\u00a0", "\u2003"])
def test_a_name_pasted_with_a_non_ascii_space_can_be_delivered_twice(tmp_path, space):
    """The stem kept the space, the manifest check stripped it, and the second
    delivery to the folder stopped at DELIVER_MANIFEST_UNREADABLE."""
    ws = build(tmp_path)
    write(ws, 'profile.yaml', {'meta': {'name': f'{space}张三{space}'}})
    assert report_stem(ws, 'apply').startswith('张三－')
    dest = tmp_path / 'out'
    assert run(ws, dest, '--no-pdf') == 0
    assert run(ws, dest, '--no-pdf') == 0


def test_a_folder_already_stuck_on_a_spaced_name_heals_on_the_next_delivery(tmp_path):
    """A manifest written before 1.5.1 records the stem with its ideographic space.
    Refusing to read it left that folder refusing every delivery for good."""
    import json
    import deliver
    ws = build(tmp_path)
    write(ws, 'profile.yaml', {'meta': {'name': '张三'}})
    dest = tmp_path / 'out'
    assert run(ws, dest, '--no-pdf') == 0
    manifest = dest / deliver.MANIFEST_NAME
    data = json.loads(manifest.read_text(encoding='utf-8'))
    entry = data['deliveries'][0]
    old = next(rel for rel in entry['files'] if '张三－' in rel)
    spaced = old.replace('张三－', '　张三－')
    (dest / old).rename(dest / spaced)
    entry['files'][spaced] = entry['files'].pop(old)
    manifest.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')

    assert run(ws, dest, '--no-pdf') == 0
    assert (dest / old).is_file()
    assert not (dest / spaced).exists()
