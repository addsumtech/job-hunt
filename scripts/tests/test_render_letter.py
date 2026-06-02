import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import render_letter

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def test_render_markdown_letter():
    data = render_letter.load(FIXTURES / "sample_letter.yaml")
    md = render_letter.render_markdown(data)
    assert "Dear Hiring Team," in md
    assert "cutting latency by 40%" in md
    assert "Sincerely," in md
    assert "Test User" in md


def test_render_docx_letter(tmp_path):
    from docx import Document
    data = render_letter.load(FIXTURES / "sample_letter.yaml")
    out = tmp_path / "letter.docx"
    render_letter.render_docx(data, out)
    assert out.exists()
    text = "\n".join(p.text for p in Document(str(out)).paragraphs)
    assert "Dear Hiring Team," in text
    assert "Acme" in text
