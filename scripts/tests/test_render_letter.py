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


def test_letter_latex_preamble_matches_the_engine():
    """Same fix, same reason as test_render_cv's engine-aware preamble test.

    This file shipped its own copy of the `inputenc`+`fontenc` preamble and
    therefore its own copy of the defect: a letter to `Ștefan Ionescu` at
    `Politechnika Śląska` compiled under tectonic, exited 0, and printed
    "tefan Ionescu" at "Politechnika lska". It now shares
    `render_cv.latex_preamble`, so there is one place to be right."""
    data = render_letter.load(FIXTURES / "sample_letter.yaml")
    for engine in ("tectonic", "xelatex", None):
        tex = render_letter.build_latex(data, engine=engine)
        assert r"\usepackage{fontspec}" in tex, engine
        assert "inputenc" not in tex, engine
    pdf_tex = render_letter.build_latex(data, engine="/usr/bin/pdflatex")
    assert r"\usepackage[utf8]{inputenc}" in pdf_tex
    assert r"\usepackage[T1]{fontenc}" in pdf_tex


def test_letter_and_cv_share_one_preamble_builder():
    """Two call sites cannot drift if there is one — the lesson `_engine_cmd`
    already learned in this repo, applied to the preamble that broke next."""
    import render_cv
    assert render_letter.render_cv.latex_preamble is render_cv.latex_preamble


def test_letter_pdf_degrades_without_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(render_letter.render_cv, "find_latex_engine", lambda: None)
    data = render_letter.load(FIXTURES / "sample_letter.yaml")
    out = tmp_path / "letter.pdf"
    assert render_letter.render_pdf(data, out) is False
    assert (tmp_path / "letter.tex").exists()


def test_letter_cjk_warns_and_degrades(tmp_path, capsys):
    """A CJK letter must warn and degrade, not silently emit a broken PDF.

    Still keyed on CJK/Thai specifically, and deliberately not widened to the
    U+00FF threshold: this template has no xeCJK and no CJK font chain, so those
    scripts genuinely cannot be set here — but Ł, ą, Š and Ș now compile, and
    refusing them would have been a second wrong answer to the same question."""
    data = {"sender": {"name": "山田"}, "recipient": {"company": "会社"},
            "salutation": "拝啓", "body": ["貴社を志望します。"], "closing": "敬具"}
    out = tmp_path / "letter.pdf"
    reasons = []
    assert render_letter.render_pdf(data, out, reasons=reasons) is False
    assert reasons == [render_letter.render_cv.UNSUPPORTED_SCRIPT]
    assert (tmp_path / "letter.tex").exists()
    assert "CJK" in capsys.readouterr().err
    # …and it is a tolerated degradation, like a missing engine: the run carries
    # on with .md/.docx rather than being reported as a broken renderer.
    assert render_letter.render_cv.pdf_failure_is_tolerated(reasons) is True


def test_letter_diacritics_are_not_refused(tmp_path, monkeypatch):
    """The other half of the same guard: a Polish sender is not CJK and must not
    be turned away — before the fix it was not turned away either, it was
    silently mangled."""
    monkeypatch.setattr(render_letter.render_cv, "find_latex_engine", lambda: None)
    data = {"sender": {"name": "Łukasz Wójcik"},
            "recipient": {"company": "Politechnika Śląska"},
            "salutation": "Dear Ștefan,", "body": ["Škoda."], "closing": "Sincerely,"}
    reasons = []
    assert render_letter.render_pdf(data, tmp_path / "letter.pdf",
                                    reasons=reasons) is False
    assert reasons == [render_letter.render_cv.NO_ENGINE]   # not UNSUPPORTED_SCRIPT
    tex = (tmp_path / "letter.tex").read_text(encoding="utf-8")
    assert r"\usepackage{fontspec}" in tex and "Łukasz Wójcik" in tex


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
