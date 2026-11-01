"""Report renderer regressions from the 2026-11-01 end-to-end discover run.

Three defects in one real report: every contents entry printed twice (`- 结论`
and a clickable `结论` beneath it), a section link inside a paragraph added a
stray line, and `€4,000` / `€4000` were split across lines at the comma or
after the currency sign.
"""
import pathlib
import re
import sys

import pymupdf
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import deliver
import layout_requirements


def width(value, size):
    return float(len(value))


@pytest.mark.parametrize('token', ['€4,000', '€4000', '$1,234.56', '¥30,000', '1.234,56',
                                   '£12', '₩1,000,000', '4.5'])
def test_a_number_is_never_split_at_its_sign_or_separator(token):
    for prefix_len in range(0, 12):
        for line_width in range(len(token) + 1, 16):
            text = '达' * prefix_len + token + '下限'
            lines = deliver._wrap_report_text(text, 10, line_width, width)
            assert ''.join(lines) == text
            assert any(token in line for line in lines), (prefix_len, line_width, lines)


def test_a_number_wider_than_the_line_still_flows():
    token = '€' + '1,000' * 6
    lines = deliver._wrap_report_text(token, 10, 8, width)
    assert ''.join(lines) == token and all(len(line) <= 8 for line in lines)


@pytest.mark.parametrize('text', ['Python,SQL 和 Docker,Kubernetes 都写在简历里。',
                                  '先看第一页,再看第二页。', 'a, b, c, d, e, f, g, h'])
def test_commas_outside_numbers_wrap_as_before(text):
    """The number rule only joins digits; everything else keeps the old breaks."""
    for line_width in range(4, 20):
        lines = deliver._wrap_report_text(text, 10, line_width, width)
        assert ''.join(lines).replace(' ', '') == text.replace(' ', '')
        assert all(len(line) <= line_width for line in lines)


def render(tmp_path, markdown):
    md, pdf = tmp_path / 'report.md', tmp_path / 'report.pdf'
    md.write_text(markdown, encoding='utf-8')
    assert deliver.render_pdf(md, pdf, None) == (True, '')
    with pymupdf.open(pdf) as doc:
        pages = [page.get_text() for page in doc]
        lines = [line.strip() for text in pages for line in text.splitlines() if line.strip()]
        links = [link for page in doc for link in page.get_links()]
    assert layout_requirements.report_text_problems(markdown, pages) == []
    return lines, links


SECTIONS = ['结论', '先看的两个岗位', '这一轮没有覆盖的地方']


def test_contents_entries_print_once_and_jump(tmp_path):
    toc = '\n'.join(f'- [{name}](#{name})' for name in SECTIONS)
    body = '\n\n'.join(f'## {name}\n\n这一节的正文。' for name in SECTIONS)
    lines, links = render(tmp_path, f'# 报告\n\n{toc}\n\n{body}\n')
    for name in SECTIONS:
        assert lines.count(name) == 2, (name, lines)   # one contents entry, one heading
        assert f'- {name}' not in lines
    assert sum(link['kind'] == pymupdf.LINK_GOTO for link in links) == len(SECTIONS)


def test_a_section_link_in_prose_is_clickable_in_place(tmp_path):
    markdown = ('# 报告\n\n## 结论\n\n没有找到医学影像岗位，见[这一轮没有覆盖的地方]'
                '(#这一轮没有覆盖的地方)一节。\n\n## 这一轮没有覆盖的地方\n\n只搜了 LinkedIn。\n')
    lines, links = render(tmp_path, markdown)
    assert lines.count('这一轮没有覆盖的地方') == 1   # the heading only, no stray link line
    goto = [link for link in links if link['kind'] == pymupdf.LINK_GOTO]
    assert len(goto) == 1


def test_no_section_link_is_lost_wherever_its_label_wraps(tmp_path):
    """A label split across lines falls back to its own line; it is never dropped."""
    label = '这一轮没有覆盖的地方'
    paragraphs = [('说' * offset) + f'[{label}](#{label})' + '结束。' for offset in range(0, 48, 3)]
    markdown = '# 报告\n\n' + '\n\n'.join(paragraphs) + f'\n\n## {label}\n\n正文。\n'
    lines, links = render(tmp_path, markdown)
    goto = [link for link in links if link['kind'] == pymupdf.LINK_GOTO]
    assert len(goto) == len(paragraphs)


def test_external_links_keep_their_labelled_line(tmp_path):
    url = 'https://www.linkedin.com/jobs/view/4483567304'
    lines, links = render(tmp_path, f'# 报告\n\n投递前先读[职位原文]({url})。\n')
    assert '链接：职位原文' in lines
    assert [link['uri'] for link in links if link['kind'] == pymupdf.LINK_URI] == [url]
