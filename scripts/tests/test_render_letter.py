import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import pytest

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
    monkeypatch.setattr(render_letter.render_cv, "find_latex_engine", lambda cjk=False: None)
    data = render_letter.load(FIXTURES / "sample_letter.yaml")
    out = tmp_path / "letter.pdf"
    assert render_letter.render_pdf(data, out) is False
    assert (tmp_path / "letter.tex").exists()


def test_a_cjk_letter_is_typeset_rather_than_refused(tmp_path):
    """UPDATED 2026-09-05. This test asserted the opposite — that a CJK letter
    must be refused — and the assertion was the defect, not the guard.

    render_cv has had an xeCJK preamble and a CJK font chain for a long time.
    This file simply never passed `cjk=` through to the shared
    `latex_preamble`, so a Chinese application shipped a Chinese CV as PDF and
    no letter PDF at all: one package, one script, two different answers, exit
    0 both times. Verified end to end on a real 306-character Chinese letter —
    19 KB PDF, `pdftotext` reads the sender's name back.
    """
    data = {"meta": {"language": "zh"}, "sender": {"name": "山田"},
            "recipient": {"company": "会社"}, "salutation": "拝啓",
            "body": ["貴社を志望します。"], "closing": "敬具"}
    out = tmp_path / "letter.pdf"
    reasons = []
    built = render_letter.render_pdf(data, out, reasons=reasons)
    if not built:
        # No Unicode engine or no CJK font on this machine is a legitimate
        # environment answer, and it must be the one reported.
        assert reasons == [render_letter.render_cv.NO_ENGINE], reasons
        return
    assert reasons == []
    assert out.exists()


def test_a_right_to_left_letter_is_refused_and_leaves_no_source(tmp_path, capsys):
    """The refusal that IS correct here: the template has no `bidi`, so the
    compile succeeds and produces a reversed, unshaped page. Same rule as
    render_cv, and the .tex goes with it — it is the source that produces
    exactly that page."""
    data = {"sender": {"name": "أحمد"}, "recipient": {"company": "شركة"},
            "salutation": "تحية طيبة", "body": ["أرغب في الانضمام."],
            "closing": "مع التحية"}
    out = tmp_path / "letter.pdf"
    reasons = []
    assert render_letter.render_pdf(data, out, reasons=reasons) is False
    assert reasons == [render_letter.render_cv.UNSUPPORTED_SCRIPT]
    assert not out.exists()
    assert not (tmp_path / "letter.tex").exists()
    assert "right-to-left" in capsys.readouterr().err



def test_letter_diacritics_are_not_refused(tmp_path, monkeypatch):
    """The other half of the same guard: a Polish sender is not CJK and must not
    be turned away — before the fix it was not turned away either, it was
    silently mangled."""
    monkeypatch.setattr(render_letter.render_cv, "find_latex_engine", lambda cjk=False: None)
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
    monkeypatch.setattr(render_letter.render_cv, "find_latex_engine", lambda cjk=False: engine)
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


# ---------------------------------------------------------------------------
# The letter shipped English furniture on non-English letters, and refused to
# typeset CJK its sibling renderer has typeset for a long time.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang,expected", [
    ("en", "Dear Hiring Team,"),
    ("de", "Sehr geehrte Damen und Herren,"),
    ("nl", "Geachte heer/mevrouw,"),
    ("fr", "Madame, Monsieur,"),
])
def test_the_default_salutation_follows_the_letters_language(lang, expected):
    """Quoted from references/motivation-letter.md:208, which is the file that
    sources them — not translated here."""
    assert render_letter.salutation_for({"meta": {"language": lang}}) == expected


@pytest.mark.parametrize("lang", ["zh", "ja", "ko", "pl"])
def test_a_language_with_no_sourced_salutation_gets_none_rather_than_english(lang):
    """`Dear Hiring Manager,` on a Chinese letter is the defect, and defaulting
    to it is not a fallback — motivation-letter.md:272 says never mix languages
    in one letter. The renderer omits the line; check_letter reports the gap."""
    assert render_letter.salutation_for({"meta": {"language": lang}}) == ""
    assert render_letter.closing_for({"meta": {"language": lang}}) == ""


def test_an_explicit_salutation_always_wins():
    assert render_letter.salutation_for(
        {"meta": {"language": "de"}, "salutation": "尊敬的招聘团队："}) == "尊敬的招聘团队："


def test_a_chinese_letter_renders_to_markdown_without_english_furniture():
    letter = {"meta": {"language": "zh"}, "sender": {"name": "吕东航"},
              "recipient": {"company": "阿里巴巴"}, "body": ["我对该岗位很感兴趣。"]}
    md = render_letter.render_markdown(letter)
    assert "Dear Hiring Manager" not in md
    assert "Sincerely" not in md
    assert "吕东航" in md
