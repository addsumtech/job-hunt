"""Regressions from multilingual document delivery, with real render checks."""
import pathlib
import shutil
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import check_pages
import deliver
import render_cv


def test_selected_report_font_is_not_replaced_by_bundled_font(tmp_path, monkeypatch):
    md, pdf = tmp_path / 'report.md', tmp_path / 'report.pdf'
    md.write_text('中文报告', encoding='utf-8')
    seen = []
    monkeypatch.setattr(deliver, '_pandoc',
                        lambda m, p, f: (seen.append(f), p.write_bytes(b'PDF'), True)[-1])
    monkeypatch.setattr(deliver, '_verify_pdf', lambda *args: (True, ''))
    monkeypatch.setattr(deliver, '_render_portable_report',
                        lambda *args: pytest.fail('selected font was replaced'))
    assert deliver.render_pdf(md, pdf, 'SimSun') == (True, '')
    assert seen == ['SimSun']


def test_selected_report_font_failure_does_not_silently_substitute(tmp_path, monkeypatch):
    md, pdf = tmp_path / 'report.md', tmp_path / 'report.pdf'
    md.write_text('中文报告', encoding='utf-8')
    monkeypatch.setattr(deliver, '_pandoc', lambda *args: False)
    monkeypatch.setattr(deliver, '_render_portable_report',
                        lambda *args: pytest.fail('selected font was replaced'))
    ok, reason = deliver.render_pdf(md, pdf, 'Missing Font')
    assert not ok and 'selected report font' in reason and not pdf.exists()


def test_delivery_carries_profile_font_to_report(tmp_path, monkeypatch):
    ws, dest = tmp_path / 'workspace', tmp_path / 'delivery'
    ws.mkdir()
    (ws / 'report.md').write_text('中文报告', encoding='utf-8')
    (ws / 'tailored-profile.yaml').write_text('meta:\n  cjk_font: SimSun\n', encoding='utf-8')
    seen = []
    def render(md, pdf, font):
        seen.append(font)
        pdf.write_bytes(b'PDF')
        return True, ''
    monkeypatch.setattr(deliver, 'render_pdf', render)
    written, notes = deliver.deliver(ws, dest, 'candidate')
    assert not notes and len(written) == 2
    assert seen == ['SimSun']


@pytest.mark.parametrize('language,label', render_cv._PRESENT.items())
def test_current_dates_are_localized_without_changing_expected_graduation(language, label):
    profile = {'meta': {'name': 'Test Person', 'language': language},
               'experience': [{'title': 'Engineer', 'org': 'Example',
                               'start': '2023', 'end': 'present'}]}
    assert f'2023 – {label}' in render_cv.render_markdown(profile)
    assert render_cv._dates({'end': '2027 (expected)'}, language) == '2027 (expected)'
    assert render_cv._dates({'end': None}, language) == ''
    assert render_cv._dates_tex({'end': 'current'}, language) == label


@pytest.mark.skipif(not shutil.which('pandoc'), reason='requires pandoc parser')
def test_hidden_link_targets_are_not_visible_but_code_and_labels_are(tmp_path):
    md = tmp_path / 'report.md'
    md.write_text('[履歴](<https://example.org/隐藏中文路径>)\n\n`代码中文`\n', encoding='utf-8')
    text = deliver.visible_markdown(md)
    assert '履歴' in text and '代码中文' in text
    assert '隐藏中文路径' not in text


def test_wrong_cjk_glyphs_cannot_satisfy_coverage(tmp_path, monkeypatch):
    md, pdf = tmp_path / 'a.md', tmp_path / 'a.pdf'
    md.write_text('中文内容', encoding='utf-8')
    monkeypatch.setattr(deliver, 'visible_markdown', lambda p: '中文内容')
    monkeypatch.setattr(deliver, '_pandoc', lambda md, pdf, font: (pdf.write_bytes(b'PDF'), True)[1])
    monkeypatch.setattr(deliver, 'pdf_text', lambda p: '错误错误错误错误')
    monkeypatch.setattr(deliver, 'glyph_findings', lambda p: [])  # isolate text coverage
    ok, reason = deliver.render_pdf(md, pdf, 'fake')
    assert not ok and 'lost CJK' in reason and not pdf.exists()


def test_korean_probe_rejects_a_font_that_only_renders_chinese(tmp_path, monkeypatch):
    monkeypatch.setattr(deliver, '_pandoc', lambda *a: True)
    monkeypatch.setattr(deliver, 'pdf_text', lambda *a: '测试中文渲染')
    assert deliver.pick_cjk_font('한국어 문서') is None


def test_word_check_reports_missing_office_instead_of_passing(tmp_path, monkeypatch):
    doc = tmp_path / 'cv.docx'
    doc.write_bytes(b'not used')
    monkeypatch.setattr(check_pages.shutil, 'which', lambda name: None)
    assert check_pages.docx_findings(doc, {}, 2026)[0].startswith('DOCX_NOT_MEASURED:')


@pytest.mark.skipif(not shutil.which('soffice'), reason='requires LibreOffice')
def test_word_page_limit_measures_the_actual_word_file(tmp_path):
    from docx import Document
    profile = {'meta': {'name': 'Test Person', 'max_pages': 1},
               'experience': []}
    doc = Document()
    doc.add_paragraph('Test Person')
    doc.add_page_break()
    doc.add_paragraph('Education orphan on a second page')
    path = tmp_path / 'cv.docx'
    doc.save(path)
    findings = check_pages.docx_findings(path, profile, 2026)
    assert any('CV_TOO_LONG' in f and 'Word file cv.docx' in f for f in findings), findings


@pytest.mark.skipif(not all(shutil.which(t) for t in ('pandoc', 'tectonic', 'pdftotext')),
                    reason='requires PDF toolchain')
@pytest.mark.parametrize('text', ['한국어 문서 경력 기술 경험', '日本語の履歴書と経験',
                                 '中文报告与工作经历', '中文报告 日本語の履歴書 한국어 문서'])
def test_native_and_mixed_reports_really_round_trip(tmp_path, text):
    md, pdf = tmp_path / 'report.md', tmp_path / 'report.pdf'
    md.write_text(text + '\n', encoding='utf-8')
    font = deliver.pick_cjk_font(text)
    if font is None:
        pytest.skip('no installed font covering the requested script')
    ok, reason = deliver.render_pdf(md, pdf, font)
    assert ok, reason
    assert set(deliver._CJK.findall(text)) <= set(deliver._CJK.findall(deliver.pdf_text(pdf)))


@pytest.mark.skipif(not all(shutil.which(t) for t in ('pandoc', 'tectonic', 'pdftotext')),
                    reason='requires PDF toolchain')
def test_warning_symbol_has_a_readable_pdf_fallback_without_editing_source(tmp_path):
    md, pdf = tmp_path / 'notice.md', tmp_path / 'notice.pdf'
    source = '> ⚠️ Evidence count, not an outcome prediction.\n'
    md.write_text(source, encoding='utf-8')
    ok, reason = deliver.render_pdf(md, pdf, None)
    assert ok, reason
    text = deliver.pdf_text(pdf)
    assert '[!]' in text and 'Evidence count' in text
    assert md.read_text(encoding='utf-8') == source


@pytest.mark.parametrize('engine', ['tectonic', 'xelatex'])
def test_report_uses_available_supported_engine(tmp_path, monkeypatch, engine):
    import subprocess
    md, pdf = tmp_path / 'report.md', tmp_path / 'report.pdf'
    md.write_text('Report')
    monkeypatch.setattr(deliver.shutil, 'which', lambda name: '/bin/' + name if name in {'pandoc', engine} else None)
    seen = []
    def run(cmd, **kwargs):
        seen.append(cmd)
        pdf.write_bytes(b'%PDF test')
        return subprocess.CompletedProcess(cmd, 0)
    monkeypatch.setattr(deliver.subprocess, 'run', run)
    assert deliver._pandoc(md, pdf, None)
    assert '--pdf-engine=' + engine in seen[0]


def test_failed_report_compile_cannot_pass_on_partial_output(tmp_path, monkeypatch):
    import subprocess
    md, pdf = tmp_path / 'report.md', tmp_path / 'report.pdf'
    md.write_text('Report')
    monkeypatch.setattr(deliver.shutil, 'which', lambda name: '/bin/' + name)
    def fail(cmd, **kwargs):
        pdf.write_bytes(b'%PDF partial')
        return subprocess.CompletedProcess(cmd, 1)
    monkeypatch.setattr(deliver.subprocess, 'run', fail)
    # Portable report rendering deliberately avoids Pandoc. This regression
    # exercises the remaining Pandoc fallback, where a nonzero result must not
    # leave a partial output accepted as a finished PDF.
    monkeypatch.setattr(deliver, '_portable_report_style', lambda _source: None)
    ok, _ = deliver.render_pdf(md, pdf, None)
    assert not ok and not pdf.exists()


def test_cjk_does_not_select_luatex_for_xecjk(monkeypatch):
    import render_cv
    monkeypatch.setattr(render_cv, '_ENGINE_DIRS', ())
    monkeypatch.setattr(render_cv.shutil, 'which', lambda name: '/bin/lualatex' if name == 'lualatex' else None)
    assert render_cv.find_latex_engine(cjk=True) is None
    assert render_cv.find_latex_engine(cjk=False) == '/bin/lualatex'
