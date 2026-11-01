import json
import pathlib
import re
import sys

import pymupdf
import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import check_layout
import journal
import layout_pages
import render_report
from test_check_layout import reviewed_report, reviewed_workspace


def render(ws, second='Second page.', metadata='initial', uri='https://example.com/role'):
    (ws / 'report.md').write_text('# Test Candidate\n\nFirst page.\n\n[Open role](' + uri + ')\n\n<!-- PAGE -->\n\n' + second + '\n')

    def renderer(source, target):
        with pymupdf.open() as doc:
            for section in source.read_text().split('<!-- PAGE -->'):
                page = doc.new_page()
                y = 72
                for raw in section.splitlines():
                    if not raw.strip():
                        continue
                    text = re.sub(r'^#+\s*', '', raw)
                    text = re.sub(r'\[([^]]+)\]\([^)]+\)', r'\1', text)
                    page.insert_text((72, y), text)
                    if '[Open role]' in raw:
                        page.insert_link({'kind': pymupdf.LINK_URI, 'from': pymupdf.Rect(72, y-12, 140, y+2), 'uri': uri})
                    y += 20
            doc.set_metadata({'producer': metadata})
            doc.save(target)
        return True, ''

    assert render_report.render_with(ws / 'report.md', ws / 'report.pdf', renderer) == (True, '')


def pass_draft(ws, plan):
    review = yaml.safe_load(pathlib.Path(plan['draft']).read_text())
    review.update(reviewer='Synthetic test reviewer', unresolved_differences=[])
    review['checks'] = {key: {'status': 'pass', 'detail': 'Fixture visually compared.'} for key in check_layout.CHECKS}
    for artifact in review['artifacts'].values():
        for preview in artifact['previews']:
            if preview['review_status'] == 'pending':
                preview['review_status'] = 'pass'
    (ws / 'report-layout-review.yaml').write_text(yaml.safe_dump(review))
    return review


def baseline(tmp_path):
    ws = reviewed_report(tmp_path)
    render(ws)
    plan = layout_pages.prepare(ws, report=True)
    assert plan['review_required'] == [1, 2]
    pass_draft(ws, plan)
    assert check_layout.main(['--workspace', str(ws), '--report']) == 0
    assert (ws / 'report-layout-cache.json').exists()
    return ws


def test_metadata_only_pdf_rebuild_reuses_actual_passed_pages(tmp_path):
    ws = baseline(tmp_path)
    previous = journal.sha256_file(ws / 'report.pdf')
    render(ws, metadata='new PDF bytes, unchanged pages')
    assert previous != journal.sha256_file(ws / 'report.pdf')
    plan = layout_pages.prepare(ws, report=True, adopt=True)
    assert plan['review_required'] == [] and plan['reused_pages'] == [1, 2] and plan['adopted']
    assert check_layout.main(['--workspace', str(ws), '--report']) == 0


def test_changed_page_remains_pending_until_reviewed(tmp_path):
    ws = baseline(tmp_path)
    render(ws, second='Revised second page.')
    plan = layout_pages.prepare(ws, report=True, adopt=True)
    assert plan['review_required'] == [2] and plan['reused_pages'] == [1] and not plan['adopted']
    review = yaml.safe_load(pathlib.Path(plan['draft']).read_text())
    review['checks'] = {key: {'status': 'pass', 'detail': 'Compared.'} for key in check_layout.CHECKS}
    review['unresolved_differences'] = []
    (ws / 'report-layout-review.yaml').write_text(yaml.safe_dump(review))
    assert any('UNREVIEWED_LAYOUT_PAGE' in item for item in check_layout.inspect(ws, report=True)[0])
    pass_draft(ws, plan)
    assert check_layout.main(['--workspace', str(ws), '--report']) == 0


def test_link_target_change_needs_review_even_when_pixels_match(tmp_path):
    ws = baseline(tmp_path)
    render(ws, uri='https://example.com/another-role')
    plan = layout_pages.prepare(ws, report=True)
    assert plan['review_required'] == [1] and plan['reused_pages'] == [2]


@pytest.mark.parametrize('damage', ['pdf', 'review', 'preview', 'proof', 'journal', 'requirements'])
def test_damaged_baseline_never_silently_reuses_pages(tmp_path, damage):
    ws = baseline(tmp_path)
    entry = json.loads((ws / 'report-layout-cache.json').read_text())
    proof = ws / entry['path']
    files = {'pdf': proof.parent / 'document.pdf', 'review': proof.parent / 'review.yaml',
             'preview': proof.parent / 'report.pdf-page-1.png', 'proof': proof,
             'requirements': ws / 'report-layout-requirements.yaml'}
    if damage == 'journal':
        # An otherwise intact proof without its actual passed journal gate is insufficient.
        journal_path = ws / 'journal.jsonl'
        journal_path.write_text('')
    elif damage == 'requirements':
        requirements = yaml.safe_load(files[damage].read_text())
        requirements['expectations']['fonts'] += ' New requirement.'
        files[damage].write_text(yaml.safe_dump(requirements))
    else:
        files[damage].write_bytes(files[damage].read_bytes() + b'\nchanged')
    plan = layout_pages.prepare(ws, report=True, adopt=True)
    assert plan['review_required'] == [1, 2] and not plan['adopted']


def test_forged_reuse_claim_is_rejected_by_the_gate(tmp_path):
    ws = baseline(tmp_path)
    render(ws, second='Changed page cannot borrow an old pass.')
    plan = layout_pages.prepare(ws, report=True)
    review = pass_draft(ws, plan)
    preview = review['artifacts']['report.pdf']['previews'][1]
    preview.update(review_status='reused', reused_from=review['artifacts']['report.pdf']['previews'][0]['reused_from'] | {'page': 2})
    (ws / 'report-layout-review.yaml').write_text(yaml.safe_dump(review))
    assert any('LAYOUT_REUSE_INVALID' in item for item in check_layout.inspect(ws, report=True)[0])


def test_cv_reuse_does_not_refresh_a_stale_word_export(tmp_path):
    ws, review = reviewed_workspace(tmp_path)
    # Replace old 72-dpi fixture previews with canonical previews before the first pass.
    with pymupdf.open(ws / 'cv.pdf') as doc:
        doc[0].get_pixmap(dpi=144, colorspace=pymupdf.csRGB, alpha=False).save(ws / 'preview.png')
    for artifact in review['artifacts'].values():
        artifact['previews'][0]['sha256'] = journal.sha256_file(ws / 'preview.png')
    (ws / 'layout-review.yaml').write_text(yaml.safe_dump(review))
    assert check_layout.main(['--workspace', str(ws)]) == 0
    (ws / 'cv.docx').write_bytes((ws / 'cv.docx').read_bytes() + b'changed')
    plan = layout_pages.prepare(ws, adopt=True)
    assert plan['review_required'] == [1] and not plan['adopted']
    draft = yaml.safe_load(pathlib.Path(plan['draft']).read_text())
    assert draft['word_export']['docx_sha256'] != journal.sha256_file(ws / 'cv.docx')


@pytest.mark.parametrize('change', ['rotation', 'font', 'page_count', 'annotation'])
def test_structural_changes_cannot_borrow_an_old_page_pass(tmp_path, change):
    ws = baseline(tmp_path)
    with pymupdf.open(ws / 'report.pdf') as doc:
        if change == 'rotation':
            doc[0].set_rotation(90)
        elif change == 'font':
            doc[0].insert_text((72, 200), 'Hidden new text', fontname='cour', render_mode=3)
        elif change == 'page_count':
            doc.new_page()
        else:
            doc[0].add_text_annot((200, 200), 'Needs annotation review')
        doc.saveIncr()
    plan = layout_pages.prepare(ws, report=True)
    assert plan['review_required'] == ([1, 2, 3] if change == 'page_count' else [1])


def test_changing_the_proof_and_its_index_does_not_change_past_review_evidence(tmp_path):
    ws = baseline(tmp_path)
    index = ws / 'report-layout-cache.json'
    entry = json.loads(index.read_text())
    path = ws / entry['path']
    proof = json.loads(path.read_text())
    proof['artifacts']['report.pdf'][0]['signature'] = '0' * 64
    path.write_text(json.dumps(proof))
    entry['sha256'] = journal.sha256_file(path)
    index.write_text(json.dumps(entry))
    assert layout_pages.prepare(ws, report=True)['review_required'] == [1, 2]


# Review 2026-11-01. A review that recorded cv.docx as 1 page beside a 2-page
# Word export passed check_layout (the DOCX page count was never compared with
# anything), wrote a pass receipt, and then remember() died on a bare next()
# with StopIteration — a traceback after a "pass".
def _two_page_word_review(tmp_path):
    ws, review = reviewed_workspace(tmp_path)
    with pymupdf.open() as doc:
        for text in ('Test Candidate', 'Page two'):
            doc.new_page().insert_text((72, 72), text)
        doc.save(ws / 'cv.pdf')
        previews = []
        for number, page in enumerate(doc, 1):
            page.get_pixmap(dpi=144, colorspace=pymupdf.csRGB, alpha=False).save(ws / f'p{number}.png')
            previews.append({'page': number, 'path': f'p{number}.png',
                             'sha256': journal.sha256_file(ws / f'p{number}.png')})
    (ws / 'word-export.pdf').write_bytes((ws / 'cv.pdf').read_bytes())
    review['word_export']['sha256'] = journal.sha256_file(ws / 'cv.pdf')
    review['artifacts']['cv.pdf'] = {'sha256': journal.sha256_file(ws / 'cv.pdf'), 'pages': 2,
                                     'previews': previews}
    review['artifacts']['cv.docx'].update(pages=2, previews=[dict(p) for p in previews])
    return ws, review


def test_docx_page_count_is_checked_against_its_word_export(tmp_path, capsys):
    ws, review = _two_page_word_review(tmp_path)
    review['artifacts']['cv.docx'].update(pages=1, previews=[review['artifacts']['cv.docx']['previews'][0]])
    (ws / 'layout-review.yaml').write_text(yaml.safe_dump(review))
    assert check_layout.main(['--workspace', str(ws)]) == 1
    out = capsys.readouterr().out
    assert 'LAYOUT_PAGE_COUNT: cv.docx (its Word export PDF) has 2 pages, review recorded 1' in out
    assert journal.read_receipts(ws, 'check_layout')[-1]['verdict'] == 'fail'


def test_a_matching_two_page_word_review_passes_and_is_archived(tmp_path, capsys):
    ws, review = _two_page_word_review(tmp_path)
    (ws / 'layout-review.yaml').write_text(yaml.safe_dump(review))
    assert check_layout.main(['--workspace', str(ws)]) == 0, capsys.readouterr().out
    assert (ws / 'layout-cache.json').is_file()
    plan = layout_pages.prepare(ws)
    assert plan['review_required'] == [] and plan['reused_pages'] == [1, 2]


# The gate now refuses the mismatch above, so remember() cannot be reached with
# it through check_layout; the lookup itself must still fail as a ValueError
# (which every caller catches), never as StopIteration (which none does).
@pytest.mark.parametrize('previews, count', [
    ([{'page': 1}], 0),                       # page 2 missing
    ([{'page': 1}, {'page': 1}], 0),          # page 1 doubled, page 2 missing
    ([{'page': 1}, 'not a mapping'], 0),
])
def test_a_missing_or_doubled_page_preview_is_a_value_error(previews, count):
    with pytest.raises(ValueError, match=f'records {count} previews for page 2'):
        layout_pages._preview(previews, 2, 'cv.docx')
    if previews.count({'page': 1}) == 2:
        with pytest.raises(ValueError, match='records 2 previews for page 1'):
            layout_pages._preview(previews, 1, 'cv.docx')


def test_an_unexpected_cache_error_never_turns_a_pass_into_a_traceback(tmp_path, capsys, monkeypatch):
    ws, review = _two_page_word_review(tmp_path)
    (ws / 'layout-review.yaml').write_text(yaml.safe_dump(review))

    def boom(*_args):
        raise StopIteration('simulated')
    monkeypatch.setattr(layout_pages, 'remember', boom)
    assert check_layout.main(['--workspace', str(ws)]) == 0
    assert 'NOTICE_LAYOUT_CACHE_UNAVAILABLE: StopIteration: simulated' in capsys.readouterr().out
