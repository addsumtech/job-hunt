"""Real PDF regressions from the five-language client-report forward test."""
import pathlib
import sys

import pymupdf
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import deliver


@pytest.mark.parametrize('body,footer,page_label,link_label', [
    ('建议先确认每周到岗天数，再决定是否申请。你的简历写明你负责过数据分析，'
     '但没有说明产品上线后的效果。请准备真实项目，写清你的责任和衡量方式。',
     '职业咨询报告', '第 1 页', '链接：'),
    ('Confirm the remote-work arrangement before applying. Your CV describes '
     'data analysis but does not describe results after a product release. '
     'Prepare one real project with your responsibilities and measurement method.',
     'Career consultation report', 'Page 1', 'Link: '),
    ('応募する前に出社日数を確認してください。履歴書にはデータ分析の経験がありますが、'
     '製品公開後の成果は書かれていません。実際のプロジェクトを一つ選び、'
     '担当した仕事と評価方法を説明してください。',
     'キャリア相談レポート', '1 ページ', 'リンク：'),
    ('지원하기 전에 출근 일수를 확인하세요. 이력서에는 데이터 분석 경험이 있지만 '
     '제품 출시 후의 성과는 설명되어 있지 않습니다. 실제 프로젝트 하나를 골라 '
     '담당한 업무와 평가 방법을 정리하세요.',
     '커리어 상담 보고서', '1쪽', '링크: '),
    ('Confirma los días de trabajo presencial antes de presentar tu candidatura. '
     'Tu currículum describe análisis de datos, pero no explica los resultados '
     'posteriores al lanzamiento. Prepara un proyecto real con tus responsabilidades.',
     'Informe de orientación profesional', 'Página 1', 'Enlace: '),
])
def test_foreign_employer_and_source_titles_do_not_change_report_language(
        tmp_path, body, footer, page_label, link_label):
    ws, dest = tmp_path / 'workspace', tmp_path / 'delivery'
    ws.mkdir()
    quote = '株式会社さくら — ソフトウェアエンジニア'
    url = 'https://careers.example.test/job?id=123&city=tokyo'
    (ws / 'report.md').write_text(
        f'{body}\n\n"{quote}"\n\n[Posting]({url})\n', encoding='utf-8')
    assert deliver.main(['--workspace', str(ws), '--to', str(dest)]) == 0
    with pymupdf.open(dest / '报告' / '求职建议报告.pdf') as doc:
        text = '\n'.join(page.get_text() for page in doc)
        assert text.splitlines()[0] == footer
        assert page_label in text and link_label + 'Posting' in text
        assert ''.join(body.split()) in ''.join(text.split())
        assert quote in text
        assert any(link.get('uri') == url for page in doc for link in page.get_links())


def test_accented_employer_name_does_not_make_an_english_report_spanish(tmp_path):
    md, pdf = tmp_path / 'report.md', tmp_path / 'report.pdf'
    md.write_text('Confirm the on-site requirements before applying to "José García". '
                  'Your CV documents the relevant analysis experience. '
                  'Ask the employer about the team and work location.', encoding='utf-8')
    assert deliver.render_pdf(md, pdf, None) == (True, '')
    with pymupdf.open(pdf) as doc:
        assert doc[0].get_text().splitlines()[0] == 'Career consultation report'


@pytest.mark.parametrize('actual', [
    'https://careers.example.test/job?id=456#requirements',
    'https://careers.example.test/job?id=123#different-role',
    None,
])
def test_render_pdf_rejects_lost_or_changed_posting_destination(tmp_path, monkeypatch, actual):
    md, pdf = tmp_path / 'report.md', tmp_path / 'report.pdf'
    expected = 'https://careers.example.test/job?id=123#requirements'
    md.write_text(f'Read [the posting]({expected}) before applying.', encoding='utf-8')

    def corrupted_renderer(md, pdf, style):
        with pymupdf.open() as doc:
            page = doc.new_page()
            page.insert_text((72, 72), 'Read the posting before applying.')
            if actual:
                page.insert_link({'kind': pymupdf.LINK_URI,
                                  'from': pymupdf.Rect(72, 60, 180, 75), 'uri': actual})
            doc.save(pdf)
        return True, ''

    monkeypatch.setattr(deliver, '_render_portable_report', corrupted_renderer)
    ok, reason = deliver.render_pdf(md, pdf, None)
    assert not ok and 'PDF_LINKS_MISSING' in reason
    assert not pdf.exists()


def test_two_posting_ids_at_one_path_both_remain_required(tmp_path):
    pdf = tmp_path / 'report.pdf'
    first = 'https://careers.example.test/job?id=123'
    second = 'https://careers.example.test/job?id=456'
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((72, 72), 'Two jobs')
        page.insert_link({'kind': pymupdf.LINK_URI,
                          'from': pymupdf.Rect(72, 60, 180, 75), 'uri': first})
        doc.save(pdf)
    ok, reason = deliver._verify_pdf(pdf, f'[One]({first}) [Two]({second})', False)
    assert not ok and second in reason
    assert not pdf.exists()


@pytest.mark.parametrize('fence', ['```', '~~~~'])
def test_fenced_counts_render_content_without_interpreting_code_as_markdown(tmp_path, fence):
    ws, dest = tmp_path / 'workspace', tmp_path / 'delivery'
    ws.mkdir()
    literal = ('要求总数：4\n已满足：2\n# literal heading\n'
               '[Literal link](https://example.test/code)\n  **keep exact**')
    (ws / 'report.md').write_text(
        '# 岗位建议\n\n先确认出差频率，再决定是否申请。\n\n'
        f'{fence}text\n{literal}\n{fence}\n\n'
        '[岗位链接](https://example.test/posting)\n', encoding='utf-8')
    assert deliver.main(['--workspace', str(ws), '--to', str(dest)]) == 0
    with pymupdf.open(dest / '报告' / '求职建议报告.pdf') as doc:
        text = '\n'.join(page.get_text() for page in doc)
        assert literal in text
        assert fence not in text
        assert text.splitlines()[0] == '职业咨询报告'
        urls = {link.get('uri') for page in doc for link in page.get_links()}
        assert urls == {'https://example.test/posting'}
        assert not doc.get_toc(), 'a code heading must not become a report section'


def test_chinese_prose_after_english_skills_fills_the_line(tmp_path):
    md, pdf = tmp_path / 'report.md', tmp_path / 'report.pdf'
    body = ('你使用 PyTorch 和 OpenCV 完成图像处理项目，岗位同样要求设计评估方法，'
            '请说明实际参与的项目、承担的责任以及结果的验证方式。')
    md.write_text('# 项目建议\n\n' + body, encoding='utf-8')
    assert deliver.render_pdf(md, pdf, None) == (True, '')
    with pymupdf.open(pdf) as doc:
        lines = [line for page in doc for block in page.get_text('dict')['blocks']
                 for line in block.get('lines', [])]
        first = next(line for line in lines if 'PyTorch' in
                     ''.join(span['text'] for span in line['spans']))
        assert first['bbox'][2] > 500, 'a distant ASCII space must not truncate a CJK line'
        assert '完成图像处理项目' in ''.join(span['text'] for span in first['spans'])


def test_chinese_wrap_change_preserves_korean_word_boundaries(tmp_path):
    md, pdf = tmp_path / 'report.md', tmp_path / 'report.pdf'
    body = ('지원하기 전에 출근 일수를 확인하세요. 이력서에는 데이터 분석 경험이 있지만 '
            '제품 출시 후의 성과는 설명되어 있지 않습니다. 이 직무는 사용 현황 분석을 '
            '요구하므로 실제 프로젝트 하나를 골라 담당한 업무와 평가 방법을 정리하세요.')
    md.write_text('# 커리어 상담 보고서\n\n' + body, encoding='utf-8')
    assert deliver.render_pdf(md, pdf, None) == (True, '')
    with pymupdf.open(pdf) as doc:
        text = '\n'.join(page.get_text() for page in doc)
        assert all(word in text for word in body.split())


@pytest.mark.parametrize('technical_text', ['',
    '岗位要求 Python、PyTorch、OpenCV、TensorFlow、Kubernetes、Docker、PostgreSQL、'
    'TypeScript、JavaScript、React、Node.js。请区分实际使用经验与待学习内容。',
])
def test_chinese_heading_and_visible_body_control_language_despite_long_urls(
        tmp_path, technical_text):
    md, pdf = tmp_path / 'report.md', tmp_path / 'report.pdf'
    url = 'https://example.test/job?token=' + 'a' * 180
    md.write_text('# 岗位建议\n\n建议先确认工作地点。\n\n'
                  + technical_text + f'\n\n[岗位]({url})', encoding='utf-8')
    assert deliver.render_pdf(md, pdf, None) == (True, '')
    with pymupdf.open(pdf) as doc:
        text = '\n'.join(page.get_text() for page in doc)
        assert text.splitlines()[0] == '职业咨询报告'
        assert '链接：岗位' in text and '第 1 页' in text
        assert doc[0].get_links()[0]['uri'] == url


@pytest.mark.parametrize('title,body,footer', [
    ('Alex Morgan 求职建议',
     '你可以先确认实际入职月份，再决定是否为这个岗位准备申请材料。'
     '你提供的简历已经说明后端开发经历，但没有具体的查询优化实例。'
     '请准备一个真实项目，写清自己承担的工作、测试方法和结果。',
     '职业咨询报告'),
    ('Career advice for 株式会社さくら',
     'Confirm the remote-work arrangement before applying. Your CV describes '
     'data analysis but does not describe results after a product release. '
     'Prepare one real project with your responsibilities and measurement method.',
     'Career consultation report'),
])
def test_names_in_mixed_titles_do_not_override_the_report_body_language(
        tmp_path, title, body, footer):
    ws, dest = tmp_path / 'workspace', tmp_path / 'delivery'
    ws.mkdir()
    source = f'# {title}\n\n{body}\n'
    (ws / 'report.md').write_text(source, encoding='utf-8')
    assert deliver.main(['--workspace', str(ws), '--to', str(dest)]) == 0
    assert (dest / '报告' / '求职建议报告.md').read_text(encoding='utf-8') == source
    with pymupdf.open(dest / '报告' / '求职建议报告.pdf') as doc:
        text = '\n'.join(page.get_text() for page in doc)
        assert text.splitlines()[0] == footer
        assert title in text
        assert ''.join(body.split()) in ''.join(text.split())
