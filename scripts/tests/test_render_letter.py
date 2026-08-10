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


def test_letter_latex_preamble_has_unicode_packages():
    """BUG 2: render_letter.build_latex must include inputenc for UTF-8 safety."""
    data = render_letter.load(FIXTURES / "sample_letter.yaml")
    tex = render_letter.build_latex(data)
    assert r"\usepackage[utf8]{inputenc}" in tex


def test_letter_pdf_degrades_without_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(render_letter.render_cv, "find_latex_engine", lambda: None)
    data = render_letter.load(FIXTURES / "sample_letter.yaml")
    out = tmp_path / "letter.pdf"
    assert render_letter.render_pdf(data, out) is False
    assert (tmp_path / "letter.tex").exists()


def test_letter_cjk_warns_and_degrades(tmp_path, capsys):
    """A CJK letter must warn and degrade, not silently emit a broken PDF."""
    data = {"sender": {"name": "山田"}, "recipient": {"company": "会社"},
            "salutation": "拝啓", "body": ["貴社を志望します。"], "closing": "敬具"}
    out = tmp_path / "letter.pdf"
    assert render_letter.render_pdf(data, out) is False
    assert (tmp_path / "letter.tex").exists()
    assert "CJK" in capsys.readouterr().err


def test_letter_pdf_uses_the_tectonic_argv_for_an_absolute_engine_path(tmp_path, monkeypatch):
    """The bug this file shipped with: render_letter compared the engine to the
    bare string 'tectonic' while find_latex_engine returns an absolute path, so
    every letter PDF was compiled with pdflatex flags and failed — in the same
    run where cv.pdf built fine, with all 51 tests green."""
    engine = "/opt/homebrew/bin/tectonic"
    monkeypatch.setattr(render_letter.render_cv, "find_latex_engine", lambda: engine)
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        class R:
            returncode = 0
        return R()

    monkeypatch.setattr(render_letter.subprocess, "run", fake_run)
    data = render_letter.load(FIXTURES / "sample_letter.yaml")
    out = tmp_path / "letter.pdf"
    assert render_letter.render_pdf(data, out) is True
    assert seen["cmd"] == [engine, str(tmp_path / "letter.tex"), "--outdir", str(tmp_path)]


def test_letter_and_cv_build_the_same_argv_for_the_same_engine():
    """The two renderers cannot drift again: there is one helper."""
    import render_cv
    assert render_letter.render_cv._engine_cmd is render_cv._engine_cmd
