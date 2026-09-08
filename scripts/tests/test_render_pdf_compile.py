"""Tests that actually run the LaTeX engine and read the PDF back.

Every other test of `render_pdf` in this repo monkeypatches `find_latex_engine`
away, and that is precisely how the defect these tests exist for shipped: the
renderer emitted a pdfLaTeX `inputenc`/`fontenc` preamble, `find_latex_engine`
handed it to tectonic (XeTeX), and every character above Latin-1 was dropped with
an exit-0 `Missing character` warning that `subprocess.run(..., capture_output=
True)` threw away. `Łukasz Wójcik` was written to cv.pdf as `ukasz Wójcik`,
`Politechnika Śląska` as `Politechnika lska`. `cv.md` was intact, so the three
judges read the right name; `check_pages` counted pages, not glyphs; and
`test_render_cv.py` had a green test *pinning* the broken preamble under the
docstring "for UTF-8 safety".

A monkeypatched engine cannot catch any of that. These tests compile.

They SKIP where no engine is installed — CI has none — and the last test in the
file prints which of those states the run was in, the way test_install.py does,
because three silent skips inside a green build is a failure mode this repo has
already been bitten by once.
"""
import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import check_pages
import render_cv

# Polish, Czech, Romanian: Latin Extended-A and Extended-B, all above U+00FF, all
# ordinary in the nl/de/uk markets this skill is built for.
LATIN_EXT_PROFILE = {
    "meta": {"name": "Łukasz Wójcik", "target_market": "nl", "language": "en",
             "headline": "Software Engineer"},
    "contact": {"email": "lukasz@example.com", "location": "Gliwice, PL"},
    "summary": "Engineer who ships.",
    "experience": [{"title": "Engineer", "org": "Politechnika Śląska",
                    "start": "2023-01", "end": "present",
                    "bullets": ["Led the Škoda telemetry rewrite with Ștefan Ionescu."]}],
    "education": [{"degree": "MSc CS", "institution": "Politechnika Śląska",
                   "start": "2021", "end": "2023"}],
}

ASCII_PROFILE = {
    "meta": {"name": "Jane Doe", "target_market": "nl", "language": "en"},
    "contact": {"email": "jane@example.com", "location": "Leiden, NL"},
    "experience": [{"title": "Engineer", "org": "Acme BV", "start": "2023-01",
                    "end": "present", "bullets": ["Cut latency 40%."]}],
}

CJK_PROFILE = {
    "meta": {"name": "李明", "language": "zh", "target_market": "cn"},
    "contact": {"email": "li@example.com", "location": "上海"},
    "experience": [{"title": "工程师", "org": "华为技术有限公司",
                    "start": "2021-01", "end": "present",
                    "bullets": ["把延迟降低了百分之四十。"]}],
}


def _engine(cjk=False):
    return render_cv.find_latex_engine(cjk=cjk)


def _require_engine(cjk=False):
    engine = _engine(cjk)
    if engine is None:
        pytest.skip("no LaTeX engine installed on this machine — nothing compiled")
    return engine


def _pdf_says(pdf_path, *needles):
    """Every needle appears in the text of the PDF as delivered.

    Reads it with `check_pages.extract_text`, the same reader the gate uses, so a
    reader that quietly stops working takes this test down with it rather than
    leaving a green test in front of a blind gate."""
    readings = check_pages.extract_text(pdf_path)
    assert readings, f"no text could be extracted from {pdf_path}"
    missing = [n for n in needles if not check_pages.pdf_contains(readings, n)]
    assert not missing, f"{pdf_path.name} does not contain {missing}"


def test_latin_extended_a_survives_a_real_compile(tmp_path):
    """THE regression. Verbatim the profile from the audit's reproduction."""
    _require_engine()
    out = tmp_path / "cv.pdf"
    assert render_cv.render_pdf(LATIN_EXT_PROFILE, out) is True
    assert out.exists()
    _pdf_says(out, "Łukasz Wójcik", "Politechnika Śląska", "Škoda", "Ștefan Ionescu")


def test_plain_ascii_still_compiles_and_reads_back(tmp_path):
    """The path that always worked has to keep working — the fix swaps the whole
    font machinery on the engine this repo prefers, so 'it renders' is not a
    thing to assume."""
    _require_engine()
    out = tmp_path / "cv.pdf"
    assert render_cv.render_pdf(ASCII_PROFILE, out) is True
    _pdf_says(out, "Jane Doe", "Acme BV", "Cut latency 40%")


def test_the_pre_fix_preamble_is_now_caught_instead_of_shipped(tmp_path):
    """Compile the OLD preamble on purpose and prove the drop is now fatal.

    `build_latex(..., engine="pdflatex")` is exactly what the renderer used to
    emit unconditionally. Handed to tectonic it still drops the glyphs — that is
    a property of the engine, not something this repo can fix — so what has to be
    true is that the renderer notices, refuses, and leaves no PDF for anyone to
    send. Without this test the `Missing character` scan could be deleted and
    every other test here would stay green."""
    engine = _require_engine()
    if not render_cv._is_unicode_engine(engine):
        pytest.skip(f"{engine} is not XeTeX-based; the T1 preamble is correct for it")
    tex_path = tmp_path / "cv.tex"
    tex_path.write_text(render_cv.build_latex(LATIN_EXT_PROFILE, engine="pdflatex"),
                        encoding="utf-8")
    out = tmp_path / "cv.pdf"
    reasons = []
    assert render_cv.compile_latex(engine, tex_path, out, reasons=reasons) is False
    assert reasons == [render_cv.MISSING_CHARACTERS]
    assert not out.exists(), "a PDF with dropped glyphs must not be left to be sent"
    assert tex_path.exists(), "the .tex is a deliverable and stays"


def test_the_engine_log_scan_reads_this_engines_dialect(tmp_path):
    """`missing_characters` parses engine output, and engines word it differently
    (XeTeX `(U+0141)`, pdfTeX `("141)`). Pinned against the real thing rather than
    against a string someone typed into a test."""
    engine = _require_engine()
    if not render_cv._is_unicode_engine(engine):
        pytest.skip(f"{engine} is not XeTeX-based; the T1 preamble is correct for it")
    tex_path = tmp_path / "cv.tex"
    tex_path.write_text(render_cv.build_latex(LATIN_EXT_PROFILE, engine="pdflatex"),
                        encoding="utf-8")
    proc = render_cv.subprocess.run(
        render_cv._engine_cmd(engine, tex_path, tmp_path),
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    dropped = render_cv.missing_characters(render_cv._engine_log(proc))
    assert dropped, "the engine reported dropped glyphs and the scan saw none"
    assert any("Ł" in d for d in dropped), dropped[:5]


def test_a_letter_with_diacritics_survives_a_real_compile(tmp_path):
    """render_letter carried its own copy of the preamble and its own copy of the
    bug: measured before the fix, a letter to Ștefan Ionescu at Politechnika
    Śląska compiled, exited 0, and read 'tefan Ionescu' at 'Politechnika lska'."""
    _require_engine()
    import render_letter
    data = {
        "sender": {"name": "Łukasz Wójcik", "email": "lukasz@example.com",
                   "location": "Gliwice, PL"},
        "recipient": {"name": "Ștefan Ionescu", "company": "Politechnika Śląska",
                      "location": "Gliwice"},
        "date": "2026-08-16",
        "salutation": "Dear Ștefan Ionescu,",
        "body": ["I led the Škoda telemetry rewrite at Politechnika Śląska."],
        "closing": "Sincerely,",
    }
    out = tmp_path / "letter.pdf"
    assert render_letter.render_pdf(data, out) is True
    _pdf_says(out, "Łukasz Wójcik", "Ștefan Ionescu", "Politechnika Śląska", "Škoda")


@pytest.mark.skipif(os.environ.get("JOBHUNT_COMPILE_CJK") != "1",
                    reason="opt-in: subsetting a CJK font costs ~18s per compile "
                           "(measured), which is four times the whole suite. Run it "
                           "with JOBHUNT_COMPILE_CJK=1 when touching the font or "
                           "preamble code. The source-level CJK tests in "
                           "test_render_cv.py run every time.")
def test_cjk_still_compiles_and_reads_back(tmp_path):
    _require_engine(cjk=True)
    out = tmp_path / "cv.pdf"
    reasons = []
    ok = render_cv.render_pdf(CJK_PROFILE, out, reasons=reasons)
    if not ok and reasons == [render_cv.MISSING_CHARACTERS]:
        pytest.skip("no CJK font installed on this machine — the CJK path was NOT "
                    "checked here (install Noto Sans CJK / PingFang and re-run)")
    assert ok is True
    _pdf_says(out, "李明", "华为技术有限公司")


def test_this_module_says_out_loud_what_it_actually_compiled(record_property, capsys):
    """Every compiling test above skips where there is no engine, which on CI is
    all of them — and a build that is green because it checked nothing looks
    exactly like a build that is green because everything passed. So the state
    goes into the run's own output instead of being inferred from a dot count."""
    latin = _engine()
    cjk = _engine(cjk=True)
    state = "compiled" if latin else "no-engine-here"
    cjk_state = ("compiled" if os.environ.get("JOBHUNT_COMPILE_CJK") == "1" and cjk
                 else "opt-in-not-run" if cjk else "no-unicode-engine-here")
    record_property("pdf_compile_checks", state)
    record_property("pdf_compile_checks_cjk", cjk_state)
    print(f"\nPDF COMPILE CHECKS: {state} ({latin})"
          f"\nPDF COMPILE CHECKS (CJK): {cjk_state} ({cjk})")
    assert state in ("compiled", "no-engine-here")
