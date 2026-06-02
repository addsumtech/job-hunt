import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import render_cv


def test_load_profile(sample_profile_path):
    p = render_cv.load_profile(sample_profile_path)
    assert p["meta"]["name"] == "Test User"


def test_render_markdown_contains_key_content(sample_profile_path):
    p = render_cv.load_profile(sample_profile_path)
    md = render_cv.render_markdown(p)
    assert "# Test User" in md
    assert "Software Engineer" in md          # headline
    assert "test@example.com" in md           # contact
    assert "## Experience" in md
    assert "Cut latency 40%" in md            # bullet
    assert "## Education" in md
    assert "MSc CS" in md
    assert "## Skills" in md
    assert "Python" in md


def test_render_markdown_omits_empty_sections(sample_profile_path):
    p = render_cv.load_profile(sample_profile_path)
    md = render_cv.render_markdown(p)
    assert "## Projects" not in md            # projects is empty in fixture


def test_render_docx_creates_readable_file(sample_profile_path, tmp_path):
    from docx import Document
    p = render_cv.load_profile(sample_profile_path)
    out = tmp_path / "cv.docx"
    render_cv.render_docx(p, out)
    assert out.exists()
    text = "\n".join(par.text for par in Document(str(out)).paragraphs)
    assert "Test User" in text
    assert "Cut latency 40%" in text
    assert "MSc CS" in text
