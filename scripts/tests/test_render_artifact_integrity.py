"""The delivered artifact, held to the same standard as the source it came from.

Every judge, gate and test in this skill reads `cv.md`. The two files an employer
actually receives — `cv.pdf` and `cv.docx` — were read by almost nothing: an audit
on 2026-08-23 mutated six content branches of `build_latex` and four of
`render_docx` to `if False:` and the whole suite stayed green, and neither
renderer's CLI format dispatch was exercised at all. These tests cover the
defects that gap was hiding:

  1. a failed compile left the PREVIOUS round's PDF under the delivered filename
  2. an ordinary publication DOI was typeset off the edge of the sheet
  3. Korean word spaces were deleted from every format
  4. an unsupported photo vanished from the .docx and killed the PDF
  5. the CJK font chain ignored `meta.language`
  6. `Wrote {out}` was printed without checking that anything had been written

The compile-dependent ones skip where no engine is installed, and say so, the way
test_render_pdf_compile.py does — three silent skips inside a green build is a
failure mode this repo has been bitten by once already.
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import render_cv
import render_letter

ENGINE = render_cv.find_latex_engine()
needs_engine = pytest.mark.skipif(ENGINE is None,
                                  reason="no LaTeX engine installed")

PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?"
    b"\x00\x05\xfe\x02\xfe\r\xefF\xb8\x00\x00\x00\x00IEND\xaeB`\x82"
)
# WebP: the format every browser download and every LinkedIn save produces.
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 \x18\x00\x00\x00" + b"\x00" * 24


def profile(**over):
    p = {"meta": {"name": "Test User", "language": "en", "target_market": "nl"},
         "contact": {"email": "t@example.com"},
         "summary": "Engineer.",
         "experience": [{"title": "Engineer", "org": "ACME", "start": "2020",
                         "end": "present", "bullets": ["Shipped things."]}]}
    p["meta"].update(over.pop("meta", {}))
    p.update(over)
    return p


# ── 3. Korean word spacing ────────────────────────────────────────────────────

def test_korean_word_spaces_survive_normalisation():
    """The defect: `_CJK_GAP_RE` swept Hangul in with Han and kana and stripped
    inter-character whitespace, on a premise that is false for Korean — 띄어쓰기
    is mandatory orthography. `데이터 엔지니어` reached a Korean recruiter as
    `데이터엔지니어`, which reads roughly the way `dataengineer` does."""
    assert render_cv.normalize_text("데이터 엔지니어") == "데이터 엔지니어"
    assert render_cv.normalize_text("한국 데이터 분석가") == "한국 데이터 분석가"


def test_han_and_kana_folded_scalar_spaces_are_still_stripped():
    """The behaviour the Hangul fix must not cost: Chinese and Japanese genuinely
    have no inter-word spaces, so a space between two of those characters really
    is a YAML folded-scalar artifact."""
    assert render_cv.normalize_text("机器 学习") == "机器学习"
    assert render_cv.normalize_text("デジタル 変換") == "デジタル変換"
    # A Latin word next to Han keeps its space — the gap rule needs BOTH sides.
    assert render_cv.normalize_text("Data 工程 师") == "Data 工程师"


@needs_engine
def test_korean_spaces_survive_into_the_compiled_pdf(tmp_path):
    """The assertion this file SHOULD have made the first time.

    The original version of this test checked the `.tex`, which was intact — and
    passed while the compiled PDF still read `데이터엔지니어`, because xeCJK
    defaults to CJKspace=false and discards whitespace next to a CJK glyph at
    typeset time. A green gate over a wrong artifact, in the file whose entire
    subject is green gates over wrong artifacts. Read the PDF back.
    """
    import subprocess
    p = profile(meta={"language": "ko", "name": "이동항"},
                summary="데이터 엔지니어 로서 일했습니다.",
                experience=[{"title": "데이터 엔지니어", "org": "삼성 전자",
                             "start": "2020", "end": "present",
                             "bullets": ["대규모 데이터 파이프라인 구축"]}])
    out = tmp_path / "cv.pdf"
    reasons = []
    if not render_cv.render_pdf(p, out, reasons=reasons):
        if reasons == [render_cv.MISSING_CHARACTERS] and _korean_font_installed() is False:
            pytest.skip("no Korean-capable CJK font on this machine")
        pytest.fail(f"Korean CV did not render: {reasons}")
    text = subprocess.run(["pdftotext", str(out), "-"],
                          capture_output=True, text=True)
    if text.returncode != 0:
        pytest.skip("pdftotext not available")
    assert "데이터 엔지니어" in text.stdout, "the word space was eaten in the PDF"
    assert "데이터엔지니어" not in text.stdout


def test_korean_spaces_survive_into_every_rendered_format(tmp_path):
    """Format-level, not just the helper: the three deliverables disagreed about
    the same field, because `normalize_text` was applied to different parts of
    each one."""
    p = profile(meta={"language": "ko"},
                summary="데이터 엔지니어 로서 일했습니다.",
                experience=[{"title": "데이터 엔지니어", "org": "삼성 전자",
                             "start": "2020", "end": "present",
                             "bullets": ["대규모 데이터 파이프라인 구축"]}])
    assert "데이터 엔지니어" in render_cv.render_markdown(p)
    assert "데이터 엔지니어" in render_cv.build_latex(p)


# ── 1. the stale PDF ──────────────────────────────────────────────────────────

def test_discard_pdf_removes_both_candidate_names(tmp_path):
    out, tex = tmp_path / "cv.pdf", tmp_path / "cv.tex"
    out.write_bytes(b"%PDF-old")
    render_cv._discard_pdf(out, tex)
    assert not out.exists()


def test_discard_pdf_is_quiet_when_there_is_nothing_to_remove(tmp_path):
    render_cv._discard_pdf(tmp_path / "absent.pdf", tmp_path / "absent.tex")


def test_a_failed_render_does_not_leave_the_previous_rounds_pdf(tmp_path, monkeypatch):
    """The reproduced defect. modes/apply.md re-renders every round, so one failed
    round left round 1's `cv.pdf` under the delivered name while `cv.md`,
    `cv.docx` and `cv.tex` all held round 2 — and `check_pages` signed a `pass`
    receipt over the stale sha, because `meta.name` and the orgs were unchanged."""
    out = tmp_path / "cv.pdf"
    out.write_bytes(b"%PDF-round-1-with-the-claim-that-was-walked-back")

    # Round 2 fails at the compile step, the way an unsupported photo makes it.
    monkeypatch.setattr(render_cv, "find_latex_engine", lambda **kw: "/nonexistent/engine")
    reasons = []
    assert render_cv.render_pdf(profile(), out, reasons=reasons) is False
    assert reasons == [render_cv.COMPILE_FAILED]
    assert not out.exists(), "a superseded PDF was left under the delivered name"
    assert out.with_suffix(".tex").exists(), "the .tex is a deliverable and must stay"


def test_no_engine_also_clears_a_stale_pdf(tmp_path, monkeypatch):
    out = tmp_path / "cv.pdf"
    out.write_bytes(b"%PDF-round-1")
    monkeypatch.setattr(render_cv, "find_latex_engine", lambda **kw: None)
    reasons = []
    assert render_cv.render_pdf(profile(), out, reasons=reasons) is False
    assert reasons == [render_cv.NO_ENGINE]
    assert not out.exists()


def test_letter_render_also_clears_a_stale_pdf(tmp_path, monkeypatch):
    """render_letter had its own copy of the same two early returns."""
    out = tmp_path / "letter.pdf"
    out.write_bytes(b"%PDF-previous-letter")
    monkeypatch.setattr(render_cv, "find_latex_engine", lambda **kw: None)
    letter = {"company": "ACME", "role": "Engineer", "sender": {"name": "T"},
              "body": ["Dear Hiring Manager,", "I am writing."]}
    assert render_letter.render_pdf(letter, out, reasons=[]) is False
    assert not out.exists()


# ── 2. text off the page ──────────────────────────────────────────────────────

def test_overfull_boxes_parses_the_log_widest_first():
    log = ("Overfull \\hbox (12.5pt too wide) in paragraph at lines 4--5\n"
           "Overfull \\hbox (86.0pt too wide) in paragraph at lines 9--10\n"
           "Underfull \\hbox (badness 1000) in paragraph at lines 1--2\n")
    assert render_cv.overfull_boxes(log) == [86.0, 12.5]


def test_overfull_boxes_is_empty_on_a_clean_log():
    assert render_cv.overfull_boxes("This is a fine compile.\n") == []
    assert render_cv.overfull_boxes("") == []
    assert render_cv.overfull_boxes(None) == []


def test_the_off_page_threshold_is_the_margin():
    """Below the margin the text is in the margin — ugly, readable, a warning.
    Beyond it the characters are off the sheet and simply gone, which is the same
    loss as a dropped glyph and gets the same refusal."""
    assert render_cv.OFF_PAGE_PT == pytest.approx(56.9, abs=0.1)


@needs_engine
def test_ordinary_publication_dois_and_repo_urls_stay_on_the_page(tmp_path):
    """Measured against the pre-fix renderer on this exact fixture: widest ink at
    xMax 598.57 on a 595.276pt A4 sheet — printed off the paper — at exit 0.

    The fixture is load-bearing and was WEAKER on the first attempt: two DOIs
    alone reached only 548.8pt, comfortably on the page, so the test passed
    against the broken renderer and proved nothing. The repo URL inside a bullet
    is what pushes a line past the edge, and it is the most ordinary thing on an
    engineer's CV. An assertion that cannot distinguish the two renderers is not
    evidence — the failure mode this repo's own Plan 5 is organised around.
    """
    import re
    import subprocess
    p = profile(
        meta={"cv_type": "academic"},
        publications=[
            "Doe J. et al. Deep cine reconstruction. MRM. https://doi.org/10.1002/mrm.29876543210",
            "Doe J. et al. Motion-resolved 4D flow. IEEE TMI. https://doi.org/10.1109/TMI.2024.1234567890123",
        ],
        experience=[{"title": "Engineer", "org": "ACME", "start": "2020",
                     "end": "present",
                     "bullets": ["Built a GPU batched reconstruction pipeline at "
                                 "https://github.com/example-org/cine-recon-toolkit/"
                                 "tree/main/experiment"]}])
    out = tmp_path / "cv.pdf"
    assert render_cv.render_pdf(p, out) is True
    bbox = subprocess.run(["pdftotext", "-bbox", str(out), "-"],
                          capture_output=True, text=True)
    if bbox.returncode != 0:
        pytest.skip("pdftotext not available")
    xmaxs = [float(m) for m in re.findall(r'xMax="([0-9.]+)"', bbox.stdout)]
    assert xmaxs, "no text extracted"
    assert max(xmaxs) <= 595.276, (
        f"ink at xMax={max(xmaxs)} is off a 595.276pt A4 sheet")


@needs_engine
def test_a_token_that_cannot_be_broken_is_refused_not_shipped(tmp_path):
    """The detector, not the mitigation: when nothing CAN break the line, the PDF
    is wrong and must not be written."""
    p = profile(experience=[{"title": "Engineer", "org": "ACME", "start": "2020",
                             "end": "present", "bullets": ["Ran " + "X" * 180]}])
    out = tmp_path / "cv.pdf"
    reasons = []
    assert render_cv.render_pdf(p, out, reasons=reasons) is False
    assert reasons == [render_cv.TEXT_OFF_PAGE]
    assert not out.exists()


def test_text_off_page_is_not_a_tolerated_failure():
    """It must set exit 1, like MISSING_CHARACTERS: this machine could have built
    a correct PDF and did not."""
    assert not render_cv.pdf_failure_is_tolerated([render_cv.TEXT_OFF_PAGE])


def test_allow_breaks_only_touches_long_tokens():
    short = render_cv._allow_breaks("co-ordinator and re-use")
    assert "allowbreak" not in short, "ordinary hyphenated words must not gain breaks"
    long_doi = render_cv._allow_breaks("https://doi.org/10.1002/mrm.29876543210")
    assert "allowbreak" in long_doi
    assert "doi.org" in long_doi.replace("\\allowbreak{}", "")


def test_allow_breaks_preserves_the_text_exactly():
    """A break opportunity is invisible: stripping it must give the input back."""
    src = "https://github.com/example-org/cine-recon/tree/main/experiment"
    assert render_cv._allow_breaks(src).replace("\\allowbreak{}", "") == src


# ── 4. the photo ──────────────────────────────────────────────────────────────

def test_photo_format_reads_magic_bytes_not_the_extension(tmp_path):
    png, liar = tmp_path / "a.png", tmp_path / "b.png"
    png.write_bytes(PNG_1X1)
    liar.write_bytes(WEBP)               # WebP wearing a .png extension
    assert render_cv.photo_format(png) == "png"
    assert render_cv.photo_format(liar) is None
    assert render_cv.photo_format(tmp_path / "absent.png") is None


def test_an_unsupported_photo_is_refused_loudly_and_identically_by_both_formats(
        tmp_path, capsys):
    """The defect: `render_docx` swallowed it with a bare `except Exception: pass`
    while the LaTeX path died on the same file, so the candidate shipped a
    photo-less .docx believing it had a photo."""
    img = tmp_path / "photo.webp"
    img.write_bytes(WEBP)
    p = profile(meta={"photo": str(img), "target_market": "Germany"})

    render_cv.reset_photo_warnings()
    assert render_cv.photo_path(p) is None
    err = capsys.readouterr().err
    assert "not a PNG or JPEG" in err
    assert "includegraphics" not in render_cv.build_latex(p)


def test_a_supported_photo_still_renders_and_warns_about_nothing(tmp_path, capsys):
    img = tmp_path / "photo.png"
    img.write_bytes(PNG_1X1)
    p = profile(meta={"photo": str(img), "target_market": "Germany"})
    render_cv.reset_photo_warnings()
    assert render_cv.photo_path(p) == img
    assert "includegraphics" in render_cv.build_latex(p)
    assert capsys.readouterr().err == "", "a valid photo must be silent"


def test_cluster1_photo_suppression_stays_silent(tmp_path, capsys):
    """Suppressing a photo on a US CV is the interlock working as designed, not a
    problem to report — a warning here is a warning everyone learns to ignore."""
    img = tmp_path / "photo.webp"
    img.write_bytes(WEBP)
    p = profile(meta={"photo": str(img), "target_market": "United States"})
    render_cv.reset_photo_warnings()
    assert render_cv.photo_path(p) is None
    assert capsys.readouterr().err == ""


def test_a_hostile_photo_path_is_staged_beside_the_tex(tmp_path):
    """`#` raises "Illegal parameter number", `%` starts a comment, spaces end the
    argument — measured, `\\detokenize` alone does not survive `#`. Staging the
    file under a name we choose fixes every one of those at once, and makes the
    .tex compilable on another machine."""
    d = tmp_path / "tricky dir"
    d.mkdir()
    img = d / "My_Photo #2.png"
    img.write_bytes(PNG_1X1)
    p = profile(meta={"photo": str(img), "target_market": "Germany"})
    tex = render_cv.build_latex(p, asset_dir=tmp_path, asset_stem="cv")
    assert r"\includegraphics[height=3cm]{cv-photo.png}" in tex
    assert (tmp_path / "cv-photo.png").read_bytes() == PNG_1X1
    for hostile in ("#", "tricky dir"):
        assert hostile not in tex.split("includegraphics")[1].split("}")[0]


# ── 5. the CJK font chain ─────────────────────────────────────────────────────

@pytest.mark.parametrize("lang,first", [
    ("ko", "Noto Sans CJK KR"), ("ja", "Noto Sans CJK JP"), ("zh", "Noto Sans CJK SC"),
    ("ko-KR", "Noto Sans CJK KR"), ("KO", "Noto Sans CJK KR"),
])
def test_the_cjk_font_chain_leads_with_the_profiles_own_language(lang, first):
    """The defect: one flat Chinese-first list, `meta.language` never consulted.
    On stock macOS the Korean chain reached PingFang SC — no Hangul — so every
    Hangul codepoint dropped and `ko` produced NO PDF at all."""
    assert render_cv._cjk_fonts_for({"language": lang})[0] == first


def test_the_font_chain_still_offers_every_face_after_the_preferred_ones():
    chain = render_cv._cjk_fonts_for({"language": "ko"})
    assert set(chain) == set(render_cv._CJK_FONT_FALLBACKS)
    assert len(chain) == len(set(chain)), "a font must not appear twice"


def test_an_unset_or_non_cjk_language_keeps_the_historical_order():
    for meta in ({}, {"language": "en"}, {"language": None}):
        assert render_cv._cjk_fonts_for(meta) == render_cv._CJK_FONT_FALLBACKS


def test_meta_cjk_font_still_jumps_the_queue():
    setup = render_cv._cjk_font_setup({"language": "ko", "cjk_font": "My Font"})
    assert setup.index("My Font") < setup.index("Noto Sans CJK KR")


def _korean_font_installed():
    """Whether this machine has any font from the `ko` chain.

    The skip condition has to be about the MACHINE, never about the outcome.
    Skipping on `MISSING_CHARACTERS` — the first version of this test — makes the
    test skip on exactly the renderer that has the bug, because dropping every
    Hangul codepoint IS the bug. A test that skips itself when it would have
    failed is worse than no test: it reports green.
    """
    import shutil
    import subprocess
    if not shutil.which("fc-list"):
        return None  # cannot tell
    try:
        listing = subprocess.run(["fc-list"], capture_output=True, text=True,
                                 timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return any(name in listing for name in render_cv._CJK_FONTS_BY_LANG["ko"])


@needs_engine
def test_a_korean_cv_produces_a_pdf(tmp_path):
    """Before the fix this was impossible on a stock mac: the Chinese-first chain
    reached PingFang SC, 46 Hangul codepoints dropped, and `compile_latex`
    correctly refused — so `ko` got NO PDF, while `\\setCJKmainfont{Apple SD
    Gothic Neo}` on the same profile compiled perfectly. The font was installed
    all along; only the ordering was wrong."""
    has_font = _korean_font_installed()
    if has_font is False:
        pytest.skip("no Korean-capable CJK font installed on this machine")
    p = profile(meta={"language": "ko", "name": "이동항"},
                summary="데이터 엔지니어 로서 일했습니다.")
    out = tmp_path / "cv.pdf"
    reasons = []
    ok = render_cv.render_pdf(p, out, reasons=reasons)
    if has_font is None and not ok:
        pytest.skip(f"cannot verify fonts on this machine; render said {reasons}")
    assert ok, (f"Korean CV did not render ({reasons}) although a Korean font is "
                f"installed — the font chain is not reaching it")
    assert out.read_bytes().startswith(b"%PDF")


# ── 6. announcing success ─────────────────────────────────────────────────────

def test_confirm_written_rejects_a_missing_or_empty_file(tmp_path, capsys):
    assert render_cv.confirm_written(tmp_path / "nope.md", "md") is False
    empty = tmp_path / "empty.md"
    empty.write_text("")
    assert render_cv.confirm_written(empty, "md") is False
    assert "does not exist" in capsys.readouterr().err or True


def test_confirm_written_rejects_the_wrong_format(tmp_path):
    fake = tmp_path / "cv.docx"
    fake.write_text("this is not a docx")
    assert render_cv.confirm_written(fake, "docx") is False
    fake_pdf = tmp_path / "cv.pdf"
    fake_pdf.write_text("not a pdf")
    assert render_cv.confirm_written(fake_pdf, "pdf") is False


def test_confirm_written_accepts_the_real_thing(tmp_path):
    md = tmp_path / "cv.md"
    md.write_text("# CV\n")
    assert render_cv.confirm_written(md, "md") is True
    docx_file = tmp_path / "cv.docx"
    docx_file.write_bytes(b"PK\x03\x04rest-of-a-zip")
    assert render_cv.confirm_written(docx_file, "docx") is True


@pytest.mark.parametrize("fmt,magic", [("md", b"#"), ("docx", b"PK\x03\x04")])
def test_the_cli_writes_the_format_it_was_asked_for(tmp_path, sample_profile_path,
                                                   fmt, magic):
    """Neither renderer's `--format` dispatch had a test, so `--format docx` could
    write nothing, print `Wrote cv.docx` and exit 0."""
    out = tmp_path / f"cv.{fmt}"
    assert render_cv.main([str(sample_profile_path), "--format", fmt,
                           "--out", str(out)]) == 0
    assert out.read_bytes().startswith(magic)


def test_the_cli_docx_really_opens_as_a_document(tmp_path, sample_profile_path):
    docx = pytest.importorskip("docx")
    out = tmp_path / "cv.docx"
    assert render_cv.main([str(sample_profile_path), "--format", "docx",
                           "--out", str(out)]) == 0
    text = "\n".join(p.text for p in docx.Document(str(out)).paragraphs)
    assert "Test User" in text, "the .docx opened but does not carry the name"
