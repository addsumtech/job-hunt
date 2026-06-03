import copy
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import render_cv

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def full_profile():
    return render_cv.load_profile(FIXTURES / "full_profile.yaml")


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


def test_build_latex_contains_content(sample_profile_path):
    p = render_cv.load_profile(sample_profile_path)
    tex = render_cv.build_latex(p)
    assert "Test User" in tex
    assert "Cut latency 40\\%" in tex          # % is escaped for LaTeX
    assert "\\documentclass" in tex


def test_latex_escape():
    assert render_cv.latex_escape("100% & more_") == "100\\% \\& more\\_"


def test_render_pdf_degrades_without_latex(sample_profile_path, tmp_path, monkeypatch):
    # Simulate no LaTeX engine present.
    monkeypatch.setattr(render_cv, "find_latex_engine", lambda: None)
    p = render_cv.load_profile(sample_profile_path)
    out = tmp_path / "cv.pdf"
    result = render_cv.render_pdf(p, out)
    assert result is False                      # signalled it could not build PDF
    assert (tmp_path / "cv.tex").exists()       # but emitted the .tex alongside


def test_render_pdf_degrades_on_compile_error(sample_profile_path, tmp_path, monkeypatch):
    import subprocess as _subprocess
    # Simulate an engine that is found but fails to compile.
    monkeypatch.setattr(render_cv, "find_latex_engine", lambda: "pdflatex")
    monkeypatch.setattr(
        render_cv.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            _subprocess.CalledProcessError(1, "pdflatex")
        ),
    )
    p = render_cv.load_profile(sample_profile_path)
    out = tmp_path / "cv.pdf"
    result = render_cv.render_pdf(p, out)
    assert result is False                  # degrades gracefully
    assert (tmp_path / "cv.tex").exists()   # .tex source is preserved


# ── New tests for Bug 1-4 fixes ────────────────────────────────────────────

def test_parity_all_sections_md_docx_latex(full_profile, tmp_path):
    """BUG 1: publications/awards/certifications/volunteer/project appear in all 3 renderers."""
    from docx import Document

    md = render_cv.render_markdown(full_profile)
    docx_out = tmp_path / "full.docx"
    render_cv.render_docx(full_profile, docx_out)
    docx_text = "\n".join(p.text for p in Document(str(docx_out)).paragraphs)
    tex = render_cv.build_latex(full_profile)

    pub = "García, J. (2021)"
    award = "Best Paper Award"
    cert = "Certified Kubernetes Administrator"
    vol = "CoderDojo Amsterdam"
    proj = "OpenMetrics"

    for label, text in [("md", md), ("docx", docx_text), ("latex", tex)]:
        assert pub in text,   f"{label} missing publication"
        assert award in text, f"{label} missing award"
        assert cert in text,  f"{label} missing certification"
        assert vol in text,   f"{label} missing volunteer"
        assert proj in text,  f"{label} missing project"


def test_latex_preamble_has_unicode_packages(full_profile):
    """BUG 2: LaTeX preamble must include inputenc and fontenc for UTF-8 safety."""
    tex = render_cv.build_latex(full_profile)
    assert r"\usepackage[utf8]{inputenc}" in tex
    assert r"\usepackage[T1]{fontenc}" in tex


def test_latex_no_raw_middot(full_profile):
    """BUG 2: LaTeX must not contain raw · (U+00B7); accented name passes as UTF-8."""
    tex = render_cv.build_latex(full_profile)
    assert "·" not in tex, "Raw middle dot found in LaTeX output"
    assert "José García" in tex, "Accented name must appear as raw UTF-8 (handled by inputenc)"


def test_latex_links_hyperlinked(full_profile):
    """BUG 3: Contact links must be wrapped in \\href{} in LaTeX output."""
    tex = render_cv.build_latex(full_profile)
    assert r"\href{" in tex


def test_markdown_links_and_project_fields(full_profile):
    """BUG 3: Markdown must render links as [display](url) and include project role."""
    md = render_cv.render_markdown(full_profile)
    assert "](https://" in md, "No markdown hyperlink found"
    assert "Lead Developer" in md, "Project role missing from markdown"


def test_i18n_dutch_headings(full_profile):
    """BUG 4: Dutch language profile renders Dutch section headings."""
    nl_profile = copy.deepcopy(full_profile)
    nl_profile["meta"]["language"] = "nl"

    md = render_cv.render_markdown(nl_profile)
    assert "Werkervaring" in md, "Dutch heading 'Werkervaring' missing from markdown"
    assert "## Experience" not in md, "English heading still present in Dutch markdown"

    tex = render_cv.build_latex(nl_profile)
    assert "Werkervaring" in tex, "Dutch heading 'Werkervaring' missing from LaTeX"
