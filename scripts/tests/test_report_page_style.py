"""How a default report page looks, as far as a PDF can be asked.

The report used to be navy on a pale blue band, a link inside a sentence was
printed a second time on a line of its own, and every table row carried a rule
(user report, 2026-11-20: ugly, and the point of a page is hard to find). Two
redraws were rejected the same day: one with a rule under every heading and
bold labels everywhere, one with bold headings and a grey conclusion box that
"looked AI-made". These tests hold what was accepted: a plain document in
black ink and one weight, with few lines and no boxes.
"""
import pathlib
import sys

import pymupdf
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import deliver

INK = 0x1A1A1C


def render(tmp_path, markdown):
    md, pdf = tmp_path / 'report.md', tmp_path / 'report.pdf'
    md.write_text(markdown, encoding='utf-8')
    assert deliver.render_pdf(md, pdf, None) == (True, '')
    return pymupdf.open(pdf)


def spans(page):
    return [span for block in page.get_text('dict')['blocks']
            for line in block.get('lines', []) for span in line['spans'] if span['text'].strip()]


def rules(page):
    """Horizontal strokes in the body, the footer rule left out."""
    return [d for d in page.get_drawings() if d['type'] == 's' and d['rect'].height < 1
            and d['rect'].width > 100 and d['rect'].y0 < 780]


REPORT = ('# 求职建议\n\n林知远｜产品经理｜北京\n\n## 结论\n\n> **先投北京的评测岗位。**\n'
          '> 下一步：核实薪资。\n\n正文说明真实经历。\n\n## 岗位\n\n'
          '| 岗位 | 判断 |\n|---|---|\n| 评测产品 | 可以投 |\n| 平台产品 | 需补经历 |\n| 增长产品 | 暂缓 |\n')


def test_the_page_is_black_ink_with_no_blue(tmp_path):
    with render(tmp_path, REPORT) as doc:
        page = doc[0]
        colors = {span['color'] for span in spans(page)}
        assert INK in colors
        for color in colors:
            red, green, blue = color >> 16, color >> 8 & 255, color & 255
            assert max(red, green, blue) - min(red, green, blue) <= 6, hex(color)
        for drawing in page.get_drawings():
            for tone in (drawing.get('fill'), drawing.get('color')):
                if tone:
                    assert max(tone) - min(tone) < 0.03, tone


def test_the_whole_page_is_one_weight_and_headings_differ_by_size(tmp_path):
    with render(tmp_path, REPORT) as doc:
        page = doc[0]
        # No stroked (faux bold) text and a single face.
        assert b'\n2 Tr' not in page.read_contents()
        assert len({span['font'] for span in spans(page)}) == 1
        size = {span['text']: span['size'] for span in spans(page)}
        assert size['求职建议'] > size['结论'] > size['正文说明真实经历。']
        # Emphasis marks are dropped, never printed.
        assert '**' not in page.get_text() and '先投北京的评测岗位。' in page.get_text()


def test_a_quoted_block_is_plain_indented_text_with_no_box(tmp_path):
    with render(tmp_path, REPORT) as doc:
        page = doc[0]
        assert not [d for d in page.get_drawings() if d.get('fill')]
        quoted = next(span for span in spans(page) if span['text'] == '先投北京的评测岗位。')
        plain = next(span for span in spans(page) if span['text'] == '正文说明真实经历。')
        assert quoted['bbox'][0] > plain['bbox'][0]
        assert (quoted['size'], quoted['color']) == (plain['size'], plain['color'])
        assert '>' not in page.get_text()


def test_a_table_has_one_light_rule_and_headings_have_none(tmp_path):
    with render(tmp_path, REPORT) as doc:
        page = doc[0]
        lines = rules(page)
        assert len(lines) == 1
        header = next(span for span in spans(page) if span['text'] == '岗位' and span['size'] == pytest.approx(11.5))
        first_row = next(span for span in spans(page) if span['text'] == '评测产品')
        assert header['bbox'][3] < lines[0]['rect'].y0 < first_row['bbox'][1]
        # Column labels recede: grey, not ink.
        assert header['color'] != INK and first_row['color'] == INK


def test_one_link_in_a_sentence_is_clickable_in_place_and_printed_once(tmp_path):
    url = 'https://example.com/jobs/1'
    with render(tmp_path, f'# 报告\n\n投递前先读[职位原文]({url})，再决定。\n') as doc:
        page = doc[0]
        assert '投递前先读职位原文，再决定。' in page.get_text().splitlines()
        assert page.get_text().count('职位原文') == 1
        links = [link for link in page.get_links() if link['kind'] == pymupdf.LINK_URI]
        assert [link['uri'] for link in links] == [url]
        label = page.search_for('职位原文')[0]
        assert links[0]['from'].intersects(label) and links[0]['from'].width < label.width + 4


def test_a_link_whose_label_wraps_keeps_a_line_of_its_own(tmp_path):
    url = 'https://example.com/jobs/2'
    label = '这是一个很长很长的职位标题用来跨过行尾' * 3
    with render(tmp_path, f'# 报告\n\n请读[{label}]({url})。\n') as doc:
        links = [link for link in doc[0].get_links() if link['kind'] == pymupdf.LINK_URI]
        assert [link['uri'] for link in links] == [url]
        assert any(line.startswith('链接：') for line in doc[0].get_text().splitlines())


def test_a_dateline_under_the_title_is_grey_and_a_sentence_is_not(tmp_path):
    with render(tmp_path, REPORT) as doc:
        meta = next(span for span in spans(doc[0]) if '林知远' in span['text'])
        assert meta['color'] != INK and meta['size'] < 12
    (tmp_path / 'b').mkdir()
    with render(tmp_path / 'b', '# 报告\n\n已完整阅读这个岗位｜结论是可以投。\n') as doc:
        sentence = next(span for span in spans(doc[0]) if '已完整阅读' in span['text'])
        assert sentence['color'] == INK and sentence['size'] == pytest.approx(12)


def test_a_list_item_hangs_from_its_mark(tmp_path):
    item = '准备一个做过的工作流项目，' * 8
    with render(tmp_path, f'# 报告\n\n- {item}\n') as doc:
        lines = [span for span in spans(doc[0]) if '准备一个' in span['text'] or '工作流项目' in span['text']]
        assert len({round(span['bbox'][0]) for span in lines}) == 1
        mark = next(span for span in spans(doc[0]) if span['text'].strip() == '•')
        assert mark['bbox'][0] < lines[0]['bbox'][0]
