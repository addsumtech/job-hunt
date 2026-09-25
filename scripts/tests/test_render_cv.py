import copy
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import render_cv
# A real 1x1 PNG, not just the signature. The fixtures below used to write the
# 8-byte magic alone, which every renderer accepted because nothing had ever
# tried to DECODE it — until render_cv started reporting a photo it could not
# embed, at which point a stub image produced a genuine "could not embed" warning
# and this file's own warning-count test caught it. A fixture that is not the
# thing it stands in for hides exactly the defect the test is watching for.
PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?"
    b"\x00\x05\xfe\x02\xfe\r\xefF\xb8\x00\x00\x00\x00IEND\xaeB`\x82"
)

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


@pytest.mark.parametrize("main_font", [None, "Arial"])
def test_english_docx_names_and_headings_cannot_be_overridden_by_theme_fonts(
        sample_profile_path, tmp_path, main_font):
    from docx import Document
    from docx.oxml.ns import qn
    profile = render_cv.load_profile(sample_profile_path)
    profile["meta"]["language"] = "en"
    if main_font:
        profile["meta"]["main_font"] = main_font
    out = tmp_path / "cv.docx"
    render_cv.render_docx(profile, out)
    doc = Document(out)
    for name in ("Normal", "Title", "Heading 1", "List Bullet"):
        fonts = doc.styles[name].element.rPr.rFonts
        assert fonts.get(qn("w:ascii")) == (main_font or "Times New Roman")
        assert fonts.get(qn("w:hAnsi")) == (main_font or "Times New Roman")
        assert not any("theme" in key.lower() for key in fonts.attrib), name


def test_docx_education_includes_dates(full_profile, tmp_path):
    """Regression: docx must not drop Education dates (md/LaTeX include them)."""
    from docx import Document
    out = tmp_path / "cv.docx"
    render_cv.render_docx(full_profile, out)
    text = "\n".join(par.text for par in Document(str(out)).paragraphs)
    assert "2019" in text and "2021" in text   # education start/end from fixture


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
    monkeypatch.setattr(render_cv, "find_latex_engine", lambda cjk=False: None)
    p = render_cv.load_profile(sample_profile_path)
    out = tmp_path / "cv.pdf"
    result = render_cv.render_pdf(p, out)
    assert result is False                      # signalled it could not build PDF
    assert (tmp_path / "cv.tex").exists()       # but emitted the .tex alongside


def test_render_pdf_degrades_on_compile_error(sample_profile_path, tmp_path, monkeypatch):
    import subprocess as _subprocess
    # Simulate an engine that is found but fails to compile.
    monkeypatch.setattr(render_cv, "find_latex_engine", lambda cjk=False: "pdflatex")
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


def test_latex_preamble_matches_the_engine_that_will_compile_it(full_profile):
    """The encoding preamble is chosen by ENGINE, never by content.

    This test used to be called `test_latex_preamble_has_unicode_packages`, and its
    docstring said "must include inputenc and fontenc for UTF-8 safety". Both were
    wrong in the one way that mattered: `inputenc`/`fontenc` is the *pdfLaTeX*
    preamble, `find_latex_engine` prefers **tectonic**, and tectonic is XeTeX-based
    — it reads the file as Unicode and hands each codepoint to an 8-bit T1 font
    that has no Latin-Extended-A glyph, drops it with a `Missing character`
    warning, and exits 0. So the green test was pinning the defect: `Łukasz
    Wójcik` was delivered to recruiters as `ukasz Wójcik`. UTF-8 safety under a
    Unicode engine is fontspec, and only pdflatex may keep the T1 pair."""
    for engine in ("tectonic", "/opt/homebrew/bin/tectonic", "xelatex", "lualatex", None):
        tex = render_cv.build_latex(full_profile, engine=engine)
        assert r"\usepackage{fontspec}" in tex, engine
        assert "inputenc" not in tex and "fontenc" not in tex, engine

    tex = render_cv.build_latex(full_profile, engine="/usr/bin/pdflatex")
    assert r"\usepackage[utf8]{inputenc}" in tex
    assert r"\usepackage[T1]{fontenc}" in tex
    assert "fontspec" not in tex, "fontspec under pdflatex is a hard compile error"


def test_latex_no_raw_middot(full_profile):
    """BUG 2: LaTeX must not contain raw · (U+00B7); accented name survives as UTF-8."""
    tex = render_cv.build_latex(full_profile)
    assert "·" not in tex, "Raw middle dot found in LaTeX output"
    assert "José García" in tex, "Accented name must appear as raw UTF-8"


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


# ── Friendly link labels (no raw URLs as display text) ─────────────────────

def test_link_label_known_keys_and_hosts():
    # A scholar key, or a scholar.google.com host, both become "Google Scholar".
    assert render_cv.link_label("https://scholar.google.com/citations?user=AbC",
                                key="scholar") == "Google Scholar"
    assert render_cv.link_label("https://scholar.google.com/citations?user=AbC") \
        == "Google Scholar"
    assert render_cv.link_label("https://github.com/jane", key="github") == "GitHub"
    assert render_cv.link_label("https://www.linkedin.com/in/jane") == "LinkedIn"


def test_link_label_explicit_and_fallback():
    # An explicit label wins; an unknown host never leaks the full URL.
    assert render_cv.link_label("https://x.example.org/p",
                                explicit="My Site") == "My Site"
    assert render_cv.link_label("https://acme-personal.dev/cv") == "acme-personal.dev"


def test_no_raw_url_as_display_text_in_any_renderer(tmp_path):
    """A scholar link with a long query string must surface as 'Google Scholar',
    never as the raw citations?user=... string, in md / latex (the user's ask)."""
    from docx import Document
    profile = {
        "meta": {"name": "Q"},
        "contact": {"email": "q@x.com",
                    "links": {"scholar": "scholar.google.com/citations?user=YDMwxZwAAAAJ"}},
        "experience": [{"title": "Engineer", "org": "X", "bullets": ["Did a thing."]}],
    }
    md = render_cv.render_markdown(profile)
    tex = render_cv.build_latex(profile)
    assert "Google Scholar" in md and "[Google Scholar]" in md
    assert "Google Scholar" in tex and r"\href{" in tex
    # The visible label must not be the query string; the URL still rides underneath.
    assert "[citations?user" not in md
    assert "https://scholar.google.com/citations?user=YDMwxZwAAAAJ" in md  # recoverable
    out = tmp_path / "q.docx"
    render_cv.render_docx(profile, out)
    # The clickable label lives in a w:hyperlink (not paragraph.text); assert the
    # external relationship target is the real URL.
    rels = "\n".join(r.target_ref for r in Document(str(out)).part.rels.values()
                     if r.is_external)
    assert "scholar.google.com/citations?user=YDMwxZwAAAAJ" in rels


# ── Section ordering ───────────────────────────────────────────────────────

def _academic_profile():
    return {
        "meta": {"name": "Dr P"},
        "summary": "Researcher.",
        "experience": [{"title": "PhD Researcher", "org": "LUMC", "end": "present",
                        "bullets": ["Built recon pipelines."]}],
        "education": [{"degree": "PhD", "institution": "LUMC", "end": "2027 (est.)"}],
        "publications": ["Paper A.", "Paper B."],
    }


def test_academic_profile_leads_with_education():
    p = _academic_profile()
    assert render_cv.is_academic_profile(p) is True
    md = render_cv.render_markdown(p)
    assert md.index("## Education") < md.index("## Experience")


def test_industry_profile_leads_with_experience(full_profile):
    # José is a Lead Engineer (one paper, but current role is not academic).
    assert render_cv.is_academic_profile(full_profile) is False
    md = render_cv.render_markdown(full_profile)
    assert md.index("## Experience") < md.index("## Education")


def test_explicit_section_order_overrides(full_profile):
    import copy
    p = copy.deepcopy(full_profile)
    p["meta"]["section_order"] = ["education", "skills", "experience"]
    md = render_cv.render_markdown(p)
    assert md.index("## Education") < md.index("## Skills") < md.index("## Experience")
    # Sections omitted from the explicit order still render (order ≠ hiding).
    assert "## Projects" in md


def test_section_order_accepts_scalar_string(full_profile):
    import copy
    p = copy.deepcopy(full_profile)
    p["meta"]["section_order"] = "education"   # a scalar, not a list (easy YAML slip)
    md = render_cv.render_markdown(p)
    # The scalar is honoured: Education leads, the rest follow in default order.
    assert md.index("## Education") < md.index("## Experience")


# ── Edge cases surfaced by adversarial review ──────────────────────────────

def test_is_current_word_boundary():
    cur = render_cv._is_current
    assert cur({"end": ""}) is True
    assert cur({"end": "present"}) is True
    assert cur({"end": "2027 (est.)"}) is True
    assert cur({"end": "expected 2027"}) is True
    # Substrings inside ordinary words must NOT read as ongoing.
    assert cur({"end": "2024 (estimated)"}) is False
    assert cur({"end": "invested"}) is False
    assert cur({"end": "2021"}) is False


def test_links_tolerate_bad_types():
    # None / numbers must not crash link resolution (profiles are user-authored).
    assert render_cv.link_label(None) == ""
    assert render_cv.resolve_link(None) == (None, None)
    label, url = render_cv.resolve_link(12345)            # YAML number slipped in
    assert url == "https://12345"                          # coerced, not a crash
    # A scalar link in a profile renders without raising.
    profile = {"meta": {"name": "Q"}, "contact": {"email": "q@x.com",
               "links": {"site": 12345}},
               "experience": [{"title": "Eng", "org": "X", "bullets": ["Did it."]}]}
    render_cv.render_markdown(profile)
    render_cv.build_latex(profile)


def test_senior_eng_with_one_paper_is_not_academic(full_profile):
    # José has a publication but his current role is Lead Engineer — industry order.
    assert render_cv.is_academic_profile(full_profile) is False


def test_unknown_host_label_is_clean_not_a_url():
    # Fallback label is the bare host, never the path/query string.
    assert render_cv.link_label("https://acme-personal.dev/cv?ref=x") == "acme-personal.dev"
    assert render_cv.link_label("https://user@example.org:8080/p") == "example.org"


# ── i18n: cluster languages + headings override ────────────────────────────

def test_builtin_german_headings(full_profile):
    import copy
    p = copy.deepcopy(full_profile)
    p["meta"]["language"] = "de"
    md = render_cv.render_markdown(p)
    assert "## Berufserfahrung" in md and "## Ausbildung" in md
    assert "## Experience" not in md


def test_headings_override_for_non_builtin_language(full_profile):
    import copy
    p = copy.deepcopy(full_profile)
    p["meta"]["language"] = "ru"                      # no built-in table
    p["meta"]["headings"] = {"experience": "Опыт работы", "education": "Образование"}
    md = render_cv.render_markdown(p)
    assert "## Опыт работы" in md and "## Образование" in md
    # Un-overridden sections fall back to English labels (no crash, no blanks).
    assert "## Skills" in md


def test_builtin_cjk_headings_without_override():
    """zh/ja/ko have built-in heading tables now — a CJK CV gets localized
    section labels without the model having to supply meta.headings."""
    for lang, exp in (("zh", "工作经历"), ("ja", "職務経歴"), ("ko", "경력")):
        md = render_cv.render_markdown({
            "meta": {"name": "X", "language": lang},
            "experience": [{"title": "t", "org": "o", "bullets": ["b"]}],
        })
        assert f"## {exp}" in md, f"{lang} should render built-in heading {exp}"


def test_list_items_coerce_dicts_and_strings():
    """A list field written as dicts (or a bare string) renders readable text,
    never a Python repr or character-by-character."""
    md = render_cv.render_markdown({
        "meta": {"name": "X"},
        "certifications": [{"name": "ACLS", "issuer": "AHA", "status": "current"}, "RN #1"],
    })
    assert "ACLS — AHA — current" in md
    assert "RN #1" in md
    assert "{'name'" not in md                        # no dict repr leaked


def test_latex_escapes_headings_and_unicode_punctuation():
    """Section headings and Unicode punctuation must be LaTeX-safe — a '&' in a
    heading or an em-dash in a bullet previously broke the compile."""
    tex = render_cv.build_latex({
        "meta": {"name": "X", "headings": {"certifications": "Licenses & Certifications"}},
        "section_order": ["certifications"],
        "certifications": ["RN — active"],
    })
    assert r"Licenses \& Certifications" in tex      # heading & escaped
    assert "Licenses & Certifications" not in tex    # no raw &
    assert "---" in tex and "—" not in tex           # em-dash mapped


def test_cjk_folded_scalar_spaces_collapsed():
    """YAML folded-scalar spaces that land between CJK characters are stripped."""
    md = render_cv.render_markdown({
        "meta": {"name": "X", "language": "zh"},
        "summary": "后端 工程师 专注 高并发",
    })
    assert "后端工程师专注高并发" in md


def test_cjk_latex_uses_xecjk_preamble():
    """A CJK CV must build a XeLaTeX/xeCJK source, never the pdfLaTeX
    inputenc/fontenc one that cannot render CJK glyphs."""
    profile = {
        "meta": {"name": "김철수", "language": "ko",
                 "headings": {"experience": "경력"}},
        "experience": [{"title": "엔지니어", "org": "회사", "bullets": ["일을 했다."]}],
    }
    tex = render_cv.build_latex(profile)             # auto-detects CJK
    # `[CJKspace]` is part of the mechanism, not decoration: xeCJK
    # defaults to CJKspace=false and DISCARDS whitespace next to a CJK
    # glyph at typeset time, which silently ate every Korean word space
    # in the compiled PDF while the .tex looked correct.
    assert r"\usepackage[CJKspace]{xeCJK}" in tex
    assert r"\setCJKmainfont" in tex
    assert "inputenc" not in tex                     # pdfLaTeX-only, must be gone
    # xeCJK is the one part of the preamble that IS content-driven: it exists for
    # CJK line-breaking and needs a CJK font, so a Latin CV must not load it —
    # under either engine.
    for engine in ("tectonic", "/usr/bin/pdflatex", None):
        latin = render_cv.build_latex({"meta": {"name": "Jane Doe"}}, engine=engine)
        assert "xeCJK" not in latin, engine
        assert "setCJKmainfont" not in latin, engine
    # And the pdfLaTeX preamble is still what pdflatex gets.
    assert "inputenc" in render_cv.build_latex({"meta": {"name": "Jane Doe"}},
                                               engine="/usr/bin/pdflatex")


def test_cjk_engine_selection_requires_unicode_engine(monkeypatch):
    """CJK must pick a Unicode engine (xelatex/lualatex/tectonic); pdflatex is
    not acceptable. When none is available, render degrades and writes .tex."""
    monkeypatch.setattr(render_cv.shutil, "which",
                        lambda name: name if name == "pdflatex" else None)
    monkeypatch.setattr(render_cv, "_ENGINE_DIRS", [])     # hermetic: ignore real installs
    assert render_cv.find_latex_engine(cjk=False) == "pdflatex"
    assert render_cv.find_latex_engine(cjk=True) is None   # pdflatex rejected for CJK


def test_engine_found_via_absolute_path_fallback(monkeypatch, tmp_path):
    """A non-login shell may lack the engine on PATH; we still find it in a
    standard install dir, and the engine type is recognized by basename."""
    fake = tmp_path / "tectonic"
    fake.write_text("#!/bin/sh\n"); fake.chmod(0o755)
    monkeypatch.setattr(render_cv.shutil, "which", lambda name: None)  # not on PATH
    monkeypatch.setattr(render_cv, "_ENGINE_DIRS", [str(tmp_path)])
    found = render_cv.find_latex_engine(cjk=False)
    assert found == str(fake)
    import pathlib
    assert pathlib.Path(found).name == "tectonic"          # type still detectable


def test_native_achievements_and_board_sections():
    """Exec CVs get first-class Selected Achievements + Board sections, no relabel."""
    profile = {
        "meta": {"name": "X", "section_order": ["summary", "achievements", "experience", "board"]},
        "summary": "Operating executive.",
        "achievements": ["Grew ARR $42M to $148M"],
        "experience": [{"title": "COO", "org": "Co", "bullets": ["P&L owner"]}],
        "board": ["Advisory board, TechForward"],
    }
    md = render_cv.render_markdown(profile)
    assert "## Selected Achievements" in md and "## Board & Advisory" in md
    assert md.index("Selected Achievements") < md.index("Experience") < md.index("Board")
    tex = render_cv.build_latex(profile)
    assert r"Board \& Advisory" in tex                     # '&' heading escaped, compiles


def test_personal_data_and_photo_included_for_non_cluster1(tmp_path):
    img = tmp_path / "p.png"; img.write_bytes(PNG_1X1)  # path just needs to exist
    profile = {
        "meta": {"name": "Z", "target_market": "cn", "photo": str(img)},
        "contact": {"email": "z@x.com", "personal": {"date_of_birth": "1992", "hometown": "Shanghai"}},
    }
    md = render_cv.render_markdown(profile)
    assert "Date Of Birth: 1992" in md and "Hometown: Shanghai" in md
    assert f"![Photo]({img})" in md
    tex = render_cv.build_latex(profile)
    assert "includegraphics" in tex


# Realistic spellings, drawn from the eval scenario inputs and from what a
# returning user actually types. Every one must either suppress or warn — never
# render protected data silently.
CLUSTER1_SPELLINGS = [
    "us", "USA", "U.S.", "United States", "United States of America",
    "United States (Los Angeles, CA)", "US (Boston)", "Los Angeles, CA",
    "remote (US)", "uk", "U.K.", "United Kingdom", "London, United Kingdom",
    "Canada", "Toronto, Canada", "Ireland", "australia", "New Zealand",
]
# "Eindhoven, NL (hybrid)" was here and is deliberately not any more. `NL` is
# both the Netherlands and Newfoundland and Labrador, and `<place>, <CODE>` is
# also how "Wilmington, DE" is written — which resolved to cluster 2 and
# rendered a date of birth, an age, a marital status, a nationality and a photo
# onto a US CV, silently, with check_personal_data exiting 0 (reproduced
# 2026-09-06). The renderer cannot tell Eindhoven from Wilmington without a
# gazetteer, so it takes the side this module's own docstring names as cheaper:
# stripping a photo off a Dutch CV is cosmetic, warned, and fixed by writing
# "Netherlands"; leaving a DOB on a US CV is an automatic rejection and was
# silent. Bare codes are unaffected — "nl", "NL-based" and "NL-remote" all still
# resolve to 2, which is why they are still in this list.
# "Netherlands, NL" and "Germany, DE" have the `<place>, <CODE>` shape, but the
# place is the country the code names, so there is nothing ambiguous to withhold.
KNOWN_NON_CLUSTER1_SPELLINGS = [
    "nl", "Netherlands", "Amsterdam, Netherlands", "NL-based", "NL-remote",
    "Netherlands, NL", "Germany, DE",
    "Germany", "Munich, Germany", "Remote — EU", "Austria", "Switzerland",
    "cn", "China", "中国", "Japan", "Tokyo, Japan", "South Korea", "Singapore",
]
UNRECOGNIZED_SPELLINGS = ["Brazil", "Dubai, UAE", "Mars", "", "somewhere nice"]


@pytest.mark.parametrize("market", CLUSTER1_SPELLINGS)
def test_cluster1_spellings_suppress_personal_data(tmp_path, market):
    img = tmp_path / "p.png"; img.write_bytes(PNG_1X1)
    profile = {
        "meta": {"name": "Z", "target_market": market, "photo": str(img)},
        "contact": {"email": "z@x.com", "personal": {"date_of_birth": "1992"}},
    }
    assert render_cv.resolve_cluster(market) == 1
    md = render_cv.render_markdown(profile)
    assert "1992" not in md and "Photo" not in md, f"{market!r} leaked personal data"
    assert "includegraphics" not in render_cv.build_latex(profile)


@pytest.mark.parametrize("market", KNOWN_NON_CLUSTER1_SPELLINGS)
def test_known_non_cluster1_markets_render_quietly(tmp_path, capsys, market):
    """The quiet case, pinned as hard as the firing one: a photo on a Dutch or
    Chinese CV is a convention, not a defect. A warning here would be a warning
    everyone learns to ignore."""
    img = tmp_path / "p.png"; img.write_bytes(PNG_1X1)
    profile = {
        "meta": {"name": "Z", "target_market": market, "photo": str(img)},
        "contact": {"email": "z@x.com", "personal": {"date_of_birth": "1992"}},
    }
    assert render_cv.resolve_cluster(market) in (2, 3)
    md = render_cv.render_markdown(profile)
    assert "1992" in md
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("market", UNRECOGNIZED_SPELLINGS)
def test_unrecognized_market_with_personal_data_warns_and_names_the_fields(tmp_path, capsys, market):
    img = tmp_path / "p.png"; img.write_bytes(PNG_1X1)
    profile = {
        "meta": {"name": "Z", "target_market": market, "photo": str(img)},
        "contact": {"email": "z@x.com", "personal": {"date_of_birth": "1992"}},
    }
    assert render_cv.resolve_cluster(market) is None
    render_cv.render_markdown(profile)
    err = capsys.readouterr().err
    assert "WARNING" in err
    assert "contact.personal.date_of_birth" in err
    assert "meta.photo" in err
    assert repr(market) in err or f"{market!r}" in err


def test_unrecognized_market_without_personal_data_is_silent(tmp_path, capsys):
    """No protected data, nothing to warn about."""
    profile = {"meta": {"name": "Z", "target_market": "Brazil"},
               "contact": {"email": "z@x.com"}}
    render_cv.render_markdown(profile)
    assert capsys.readouterr().err == ""


def test_the_unknown_market_warning_prints_once_per_profile_not_once_per_format(
        tmp_path, capsys):
    """An md + docx + pdf run — three invocations, or three direct calls from
    one process — renders from the SAME profile. Three identical warnings is
    how a warning gets trained away, and it is why this does not live in
    personal_items (a generator consumed at three separate sites)."""
    img = tmp_path / "p.png"; img.write_bytes(PNG_1X1)
    profile = {"meta": {"name": "Z", "target_market": "Dubai, UAE", "photo": str(img)},
               "contact": {"email": "z@x.com",
                           "personal": {"date_of_birth": "1992"}}}
    render_cv.render_markdown(profile)
    render_cv.build_latex(profile)
    render_cv.render_docx(profile, tmp_path / "cv.docx")
    assert capsys.readouterr().err.count("WARNING") == 1


def test_resetting_lets_a_second_run_warn_again(tmp_path, capsys):
    """The guard is per-run, not per-process: main() clears it, so a second
    CLI invocation in the same process is not silently exempted."""
    profile = {"meta": {"name": "Z", "target_market": "Mars"},
               "contact": {"personal": {"nationality": "NL"}}}
    render_cv.render_markdown(profile)
    render_cv.reset_market_warnings()
    render_cv.render_markdown(profile)
    assert capsys.readouterr().err.count("WARNING") == 2


def test_protected_fields_names_exactly_what_is_present():
    profile = {"meta": {"name": "Z", "photo": "/tmp/p.png"},
               "contact": {"personal": {"date_of_birth": "1992", "nationality": "NL",
                                        "marital_status": None}}}
    assert render_cv.protected_fields(profile) == [
        "contact.personal.date_of_birth", "contact.personal.nationality", "meta.photo"]


def test_cjk_pdf_degrades_without_unicode_engine(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(render_cv, "find_latex_engine", lambda cjk=False: None)
    profile = {"meta": {"name": "김철수", "language": "ko"},
               "experience": [{"title": "엔지니어", "org": "회사", "bullets": ["일."]}]}
    out = tmp_path / "cv.pdf"
    result = render_cv.render_pdf(profile, out)
    assert result is False                            # no engine → no PDF
    tex = (tmp_path / "cv.tex").read_text(encoding="utf-8")
    # `[CJKspace]` is part of the mechanism, not decoration: xeCJK
    # defaults to CJKspace=false and DISCARDS whitespace next to a CJK
    # glyph at typeset time, which silently ate every Korean word space
    # in the compiled PDF while the .tex looked correct.
    assert r"\usepackage[CJKspace]{xeCJK}" in tex               # but a *correct* CJK .tex is written
    assert "CJK" in capsys.readouterr().err           # and the user is told why


def test_has_cjk_detects_scripts():
    assert render_cv._has_cjk("経歴") is True       # Japanese
    assert render_cv._has_cjk("경력") is True       # Korean
    assert render_cv._has_cjk("工作经历") is True    # Chinese
    assert render_cv._has_cjk("ประสบการณ์") is True  # Thai
    assert render_cv._has_cjk("Berufserfahrung") is False
    assert render_cv._has_cjk("Café résumé") is False


# ── the U+00FF threshold, and the warnings that used to be discarded ──────────

def test_needs_unicode_font_is_a_threshold_not_a_script_list():
    """`_has_cjk` was doing this job, and because it enumerates scripts it
    answered False for Latin Extended-A — so `Łukasz Wójcik` was routed to an
    8-bit font with no Ł in it and reached recruiters as `ukasz Wójcik`.

    The whole point of the replacement is that it names no script. Every
    assertion below that is NOT CJK is a character `_has_cjk` returns False for,
    and each is an ordinary letter in a market this skill targets."""
    for text in ("Łukasz Wójcik",     # Polish, Latin Extended-A
                 "Politechnika Śląska",
                 "Škoda", "Ștefan",   # Czech, Romanian
                 "Ģirts", "Ceyhun İpek",  # Latvian, Turkish
                 "Иван Петров", "Γεωργίου",  # Cyrillic, Greek
                 "李明", "김철수"):     # and CJK, which it must still catch
        assert render_cv._needs_unicode_font(text) is True, text
    for text in ("Berufserfahrung", "Café résumé naïve", "Ångström", "Zoë",
                 "100% & more_", ""):
        assert render_cv._needs_unicode_font(text) is False, text
    # …and it reaches into the whole profile, not just one field.
    assert render_cv.profile_needs_unicode_font(
        {"experience": [{"org": "Politechnika Śląska"}]}) is True
    assert render_cv.profile_needs_unicode_font(
        {"experience": [{"org": "Acme BV"}]}) is False


def test_is_unicode_engine_dispatches_on_the_basename():
    for engine in ("tectonic", "/opt/homebrew/bin/tectonic", "xelatex",
                   "/Library/TeX/texbin/lualatex", None):
        assert render_cv._is_unicode_engine(engine) is True, engine
    for engine in ("pdflatex", "/usr/bin/pdflatex", "latex"):
        assert render_cv._is_unicode_engine(engine) is False, engine


def test_missing_characters_reads_both_engine_dialects():
    """The engine reports the drop and exits 0; this scan is what turns that back
    into a failure. Both wordings are real output measured on this machine.

    Note the mojibake in the tectonic line: tectonic writes the character itself
    as U+FFFD before anyone here can read it, so the codepoint in the parentheses
    is the only trustworthy part and the character is rebuilt from it."""
    log = (
        'warning: cv.tex:12: Missing character: There is no �� ("141) '
        'in font ec-lmbx12!\n'
        'warning: cv.tex:19: Missing character: There is no �� ("15A) '
        'in font ec-lmr10!\n'
        'Missing character: There is no � (U+0418) in font '
        '[lmroman10-regular]:mapping=tex-text;!\n'
    )
    assert render_cv.missing_characters(log) == [
        "U+0141 'Ł' in font ec-lmbx12",
        "U+015A 'Ś' in font ec-lmr10",
        "U+0418 'И' in font [lmroman10-regular]:mapping=tex-text",
    ]


def test_missing_characters_deduplicates_and_is_quiet_on_a_clean_log():
    log = 'Missing character: There is no x ("141) in font f!\n' * 12
    assert render_cv.missing_characters(log) == ["U+0141 'Ł' in font f"]
    assert render_cv.missing_characters("") == []
    assert render_cv.missing_characters(None) == []
    assert render_cv.missing_characters("note: Writing `cv.pdf` (24 KiB)") == []


def test_a_compile_that_drops_glyphs_deletes_the_pdf_and_fails(tmp_path, monkeypatch):
    """A PDF with dropped glyphs is a WRONG artifact, not a degraded one — the
    recruiter cannot tell, and neither can the candidate, because cv.md is
    intact. So it must not be left on disk to be attached to an email."""
    tex = tmp_path / "cv.tex"
    tex.write_text("x", encoding="utf-8")
    out = tmp_path / "cv.pdf"

    def fake_run(cmd, **kw):
        out.write_bytes(b"%PDF-1.5\n")            # the engine "succeeds"
        class R:
            returncode = 0
            stdout = ""
            stderr = ('Missing character: There is no �� ("141) '
                      'in font ec-lmbx12!\n')
        return R()

    monkeypatch.setattr(render_cv.subprocess, "run", fake_run)
    reasons = []
    assert render_cv.compile_latex("tectonic", tex, out, reasons=reasons) is False
    assert reasons == [render_cv.MISSING_CHARACTERS]
    assert not out.exists()
    assert tex.exists()                            # the .tex is still delivered


def test_tectonic_sandbox_panic_is_actionable_and_cannot_leave_a_stale_pdf(
        tmp_path, monkeypatch, capsys):
    tex, out = tmp_path / "cv.tex", tmp_path / "cv.pdf"
    tex.write_text("x", encoding="utf-8")
    out.write_bytes(b"%PDF stale")

    class Failed:
        returncode = 101
        stdout = "thread 'reqwest-internal-sync-runtime' panicked\n"
        stderr = ("system-configuration-0.6.1/src/dynamic_store.rs:154: "
                  "Attempted to create a NULL object.")

    monkeypatch.setattr(render_cv.subprocess, "run", lambda *args, **kwargs: Failed())
    reasons = []
    assert render_cv.compile_latex("/opt/homebrew/bin/tectonic", tex, out,
                                   reasons=reasons) is False
    assert reasons == [render_cv.COMPILE_FAILED]
    assert not out.exists()
    err = capsys.readouterr().err
    assert "NOTICE_HOST_EXECUTION_REQUIRED" in err
    assert "Do not reinstall Tectonic" in err
    assert not render_cv.tectonic_needs_host_execution("xelatex", Failed.stderr)


def test_the_cli_exits_nonzero_when_a_compilable_machine_produced_no_pdf(
        tmp_path, monkeypatch, sample_profile_path):
    """`Wrote cv.pdf` + exit 0 is how the wrong artifact got delivered. A missing
    engine keeps exit 0 — modes/apply.md documents that degradation and expects
    the run to carry on with .md/.docx — but a machine that could have compiled
    and did not produce a correct PDF has failed."""
    out = tmp_path / "cv.pdf"
    monkeypatch.setattr(render_cv, "find_latex_engine", lambda cjk=False: None)
    assert render_cv.main([str(sample_profile_path), "--format", "pdf",
                           "--out", str(out)]) == 0

    monkeypatch.setattr(render_cv, "find_latex_engine", lambda cjk=False: "tectonic")
    monkeypatch.setattr(render_cv, "compile_latex",
                        lambda *a, **kw: render_cv._note(kw.get("reasons"),
                                                         render_cv.MISSING_CHARACTERS))
    assert render_cv.main([str(sample_profile_path), "--format", "pdf",
                           "--out", str(out)]) == 1


# ── engine argv: one helper, two renderers ────────────────────────────────

def test_engine_cmd_dispatches_on_the_basename_not_the_whole_path():
    """find_latex_engine returns an ABSOLUTE path (measured:
    '/opt/homebrew/bin/tectonic'). Comparing the whole string to 'tectonic'
    silently selects the pdflatex argv and the compile fails."""
    assert render_cv._engine_cmd("/opt/homebrew/bin/tectonic", "/w/cv.tex", "/w") == \
        ["/opt/homebrew/bin/tectonic", "/w/cv.tex", "--outdir", "/w"]


def test_engine_cmd_bare_tectonic_name_is_unchanged():
    assert render_cv._engine_cmd("tectonic", "/w/cv.tex", "/w") == \
        ["tectonic", "/w/cv.tex", "--outdir", "/w"]


def test_engine_cmd_non_tectonic_engines_get_the_latex_argv():
    for engine in ("/usr/bin/pdflatex", "pdflatex", "/Library/TeX/texbin/xelatex"):
        assert render_cv._engine_cmd(engine, "/w/cv.tex", "/w") == \
            [engine, "-interaction=nonstopmode", "-output-directory", "/w", "/w/cv.tex"]


def test_engine_cmd_accepts_path_objects():
    cmd = render_cv._engine_cmd(pathlib.Path("/opt/homebrew/bin/tectonic"),
                                pathlib.Path("/w/cv.tex"), pathlib.Path("/w"))
    assert all(isinstance(x, str) for x in cmd)
    assert cmd[2] == "--outdir"


def test_cv_pdf_invokes_tectonic_with_the_tectonic_argv(tmp_path, monkeypatch):
    engine = "/opt/homebrew/bin/tectonic"
    monkeypatch.setattr(render_cv, "find_latex_engine", lambda cjk=False: engine)
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        class R:
            returncode = 0
        return R()

    monkeypatch.setattr(render_cv.subprocess, "run", fake_run)
    out = tmp_path / "cv.pdf"
    render_cv.render_pdf({"meta": {"name": "Z"}}, out)
    assert seen["cmd"] == [engine, str(tmp_path / "cv.tex"), "--outdir", str(tmp_path)]


def test_unknown_headings_key_warns_and_names_the_valid_set(full_profile, capsys):
    """Measured silent failure: role-families.md's legal recipe relabels a
    section via meta.headings, and a key outside the built-in set is dropped
    with no warning — so the CV renders perfectly and loses its heading."""
    p = copy.deepcopy(full_profile)
    p["meta"]["headings"] = {"selected_matters": "Selected Matters",
                             "experience": "Clinical Experience"}
    md = render_cv.render_markdown(p)
    err = capsys.readouterr().err
    assert "WARNING" in err
    assert "'selected_matters'" in err
    assert "certifications" in err and "publications" in err   # the valid set is listed
    assert "## Clinical Experience" in md                      # the valid key still works


def test_unknown_section_order_entry_warns(full_profile, capsys):
    p = copy.deepcopy(full_profile)
    p["meta"]["section_order"] = ["summary", "selected_matters", "experience"]
    render_cv.render_markdown(p)
    err = capsys.readouterr().err
    assert "WARNING" in err and "'selected_matters'" in err


def test_valid_headings_and_section_order_are_silent(full_profile, capsys):
    """The quiet case: headings() runs on every render of every CV. A warning
    here would appear on every clean run and be trained away."""
    p = copy.deepcopy(full_profile)
    p["meta"]["headings"] = {"experience": "Clinical Experience"}
    p["meta"]["section_order"] = ["education", "skills", "experience"]
    render_cv.render_markdown(p)
    assert capsys.readouterr().err == ""


# assets/profile.example.yaml:2 declares meta.name and contact.email the only two
# required fields, and until 2026-08-16 nothing enforced that. A profile missing
# meta.name rendered `{\LARGE \textbf{}}` into the PDF and a bare `#` into the
# Markdown, printed "Wrote cv.pdf", and exited 0 — a nameless CV, in every format,
# with no warning. It was invisible downstream too: check_pages cannot require a name
# the profile never supplied, and the three judges read a cv.md wrong the same way.

def test_a_profile_missing_a_declared_required_field_is_refused(tmp_path):
    """Loud, and naming the field. The old behaviour was a rendered artifact the
    candidate would have had to notice by reading their own PDF."""
    p = tmp_path / "p.yaml"
    p.write_text('meta: {}\ncontact: {email: "x@example.com"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match=r"meta\.name"):
        render_cv.load_profile(p)

    p.write_text('meta: {name: "X"}\ncontact: {}\n', encoding="utf-8")
    with pytest.raises(ValueError, match=r"contact\.email"):
        render_cv.load_profile(p)


def test_a_field_present_but_blank_counts_as_missing(tmp_path):
    """`name: ""` and `name: "   "` render exactly the same empty block as no key at
    all, so the check keys on the rendered value, not on the key existing."""
    p = tmp_path / "p.yaml"
    for blank in ('""', '"   "'):
        p.write_text(f'meta: {{name: {blank}}}\ncontact: {{email: "x@example.com"}}\n',
                     encoding="utf-8")
        with pytest.raises(ValueError, match=r"meta\.name"):
            render_cv.load_profile(p)


def test_a_complete_profile_loads_silently(tmp_path):
    """The quiet case, pinned as hard as the firing one — a check that refuses a
    legitimate profile is worse than the hole it closes, because the user's only
    move is to stop using the renderer."""
    p = tmp_path / "p.yaml"
    p.write_text('meta: {name: "Łukasz Wójcik"}\ncontact: {email: "l@example.com"}\n',
                 encoding="utf-8")
    assert render_cv.load_profile(p)["meta"]["name"] == "Łukasz Wójcik"


def test_the_shipped_example_and_fixtures_satisfy_their_own_schema(tmp_path):
    """The example is what a user copies. If it ever stopped satisfying the rule the
    example's own line 2 states, the rule would be the thing that is wrong."""
    root = pathlib.Path(__file__).resolve().parent.parent.parent
    for rel in ("assets/profile.example.yaml",
                "scripts/tests/fixtures/full_profile.yaml",
                "scripts/tests/fixtures/sample_profile.yaml"):
        # Through load_profile, which is what a user's run actually calls: it parses
        # with journal.load_yaml and applies this same rule, so a fixture that fails
        # it raises here with the field names rather than yielding a bare [] mismatch.
        assert render_cv.missing_required_fields(
            render_cv.load_profile(root / rel)) == [], rel


# ---------------------------------------------------------------------------
# Paper size. `\documentclass[11pt,a4paper]` was hard-coded for every market, so
# every US and Canadian CV this skill ever produced came out on A4.
#
# Deliberately NOT keyed on the CV-convention cluster: Cluster 1 is
# US/CA/UK/IE/AU/NZ, and the UK, Ireland, Australia and New Zealand all print on
# A4. Letter is North American, not Anglophone — one enum reused for two
# different axes is how a rule ends up right for half its members.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("market", ["us", "ca", "United States", "Canada",
                                    "美国", "加拿大", "remote (US) / hybrid Berlin"])
def test_north_america_gets_letter(market):
    assert render_cv.paper_for({"target_market": market}) == "letterpaper"


@pytest.mark.parametrize("market", ["uk", "ie", "au", "nz", "nl", "de", "jp", "cn",
                                    "Boston, MA", "", None])
def test_everywhere_else_including_the_rest_of_cluster_1_gets_a4(market):
    """`Boston, MA` is here on purpose: a bare US state is not a market token,
    and guessing one would be the same substring failure check_shortlist has."""
    assert render_cv.paper_for({"target_market": market}) == "a4paper"


def test_meta_paper_overrides_the_market():
    """The escape hatch for Mexico, the Philippines and anywhere else that
    prints Letter, without this module asserting a country list it has not
    verified."""
    assert render_cv.paper_for({"target_market": "nl", "paper": "letter"}) == "letterpaper"
    assert render_cv.paper_for({"target_market": "us", "paper": "a4"}) == "a4paper"


def test_an_unknown_meta_paper_is_refused_rather_than_silently_a4():
    with pytest.raises(ValueError):
        render_cv.paper_for({"paper": "foolscap"})


def test_the_preamble_carries_the_chosen_paper():
    us = "\n".join(render_cv.latex_preamble(meta={"target_market": "us"}))
    nl = "\n".join(render_cv.latex_preamble(meta={"target_market": "nl"}))
    assert "letterpaper" in us and "a4paper" not in us
    assert "a4paper" in nl and "letterpaper" not in nl


# ---------------------------------------------------------------------------
# Right-to-left text. The preamble loads neither `bidi` nor `polyglossia`, so
# once a font covers Arabic the compile SUCCEEDS and produces a reversed,
# unshaped page: `أحمد الفارسي` read back out of pdftotext as isolated
# presentation forms, left to right, at exit 0. Worse, the documented remedy for
# the no-font refusal — "set meta.main_font" — led straight into it.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", ["أحمد الفارسي", "שקל אלביט", "ܐܪܡܝܐ", "ދިވެހި"])
def test_right_to_left_text_is_detected(text):
    assert render_cv.has_rtl(text)


@pytest.mark.parametrize("text", ["Ahmed Al-Farsi", "阿里巴巴", "김민준",
                                  "Łukasz Wójcik", "Ștefan", "ภาษาไทย"])
def test_left_to_right_text_is_not(text):
    """The cry-wolf half. Thai is here on purpose: it is complex-shaping but
    left-to-right, and the LaTeX path handles it."""
    assert not render_cv.has_rtl(text)


def test_an_rtl_profile_refuses_the_pdf_and_leaves_the_tex(tmp_path):
    profile = {"meta": {"name": "أحمد الفارسي", "main_font": "Arial"},
               "contact": {"email": "a@example.com"}, "experience": []}
    reasons = []
    out = tmp_path / "cv.pdf"
    assert render_cv.render_pdf(profile, out, reasons=reasons) is False
    assert reasons == [render_cv.UNSUPPORTED_SCRIPT]
    assert not out.exists(), "a reversed PDF is a wrong artifact, not a degraded one"
    assert not out.with_suffix(".tex").exists(), (
        "nor is the .tex: it is exactly the source that compiles to the reversed "
        "page, so shipping it hands over the same defect one step back")


def test_the_rtl_refusal_keeps_exit_zero_so_md_and_docx_still_ship():
    """UNSUPPORTED_SCRIPT is a TOLERATED failure: Markdown and .docx carry RTL
    text correctly, and failing the whole run would take those away too."""
    assert render_cv.pdf_failure_is_tolerated([render_cv.UNSUPPORTED_SCRIPT])


# ---------------------------------------------------------------------------
# "still there", in the languages this skill renders CVs in. English-only, the
# consequence ran two ways and neither was visible: is_academic_profile decides
# where Education sits, and render_rirekisho printed a 履歴書 row reading 退社
# — "left the company" — for a candidate whose end date said 現在.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("end", ["present", "至今", "现在", "現在", "在職中",
                                 "現在に至る", "heden", "heute", "재직중",
                                 "actualidad", "aujourd'hui", ""])
def test_an_ongoing_role_is_recognised_in_any_language(end):
    assert render_cv._is_current({"end": end}), end


@pytest.mark.parametrize("end", ["2024-06", "2019年3月", "May 2021",
                                 "left in 2020", "2020"])
def test_a_finished_role_is_not(end):
    assert not render_cv._is_current({"end": end}), end


# ---------------------------------------------------------------------------
# The market vocabulary, audited 2026-09-05.
#
# Endonyms all resolved to None — `Nederland`, `Österreich`, `España`, `Suomi`,
# `한국`, `Việt Nam` — so a profile written in its own market's language got no
# cluster, and the personal-data interlock could not fire on it. A candidate
# writing their own country's name for their own country is the ordinary case.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("market,cluster", [
    ("Nederland", 2), ("Österreich", 2), ("Schweiz", 2), ("España", 2),
    ("Suomi", 2), ("Sverige", 2), ("Deutschland", 2), ("ドイツ", 2),
    ("한국", 3), ("Việt Nam", 3), ("日本", 3), ("中國", 3),
    ("미국", 1), ("États-Unis", 1), ("Pays-Bas", 2), ("Nouvelle-Zélande", 1),
    ("us", 1), ("nl", 2), ("cn", 3),
])
def test_a_market_named_in_its_own_language_resolves(market, cluster):
    assert render_cv.resolve_cluster(market) == cluster, market


@pytest.mark.parametrize("market", ["Brazil", "Mexico", "South Africa", "", None])
def test_a_market_this_module_does_not_know_still_resolves_to_none(market):
    """The twin: the fix is more aliases, not a matcher that says yes to
    anything. What an unknown market MEANS is the next test."""
    assert render_cv.resolve_cluster(market) is None


# --- the conservative default ------------------------------------------------

def _with_personal(market):
    return {"meta": {"target_market": market},
            "contact": {"personal": {"date_of_birth": "1992-05-01",
                                     "nationality": "Brazilian"}}}


@pytest.mark.parametrize("market", ["Brazil", "Mexico", "South Africa", "Israel"])
def test_an_unrecognised_market_withholds_protected_data(market):
    """`resolve_cluster` returns None for these, and None was read as "not
    Cluster 1, so print it" — so the interlock could not fire on exactly the
    markets nobody had thought about. SKILL.md already stated the rule this
    implements: in genuine doubt, omit."""
    assert list(render_cv.personal_items(_with_personal(market))) == []


@pytest.mark.parametrize("market", ["us", "uk", "Canada"])
def test_cluster_one_still_withholds_it(market):
    assert list(render_cv.personal_items(_with_personal(market))) == []


@pytest.mark.parametrize("market", ["de", "Nederland", "cn", "日本"])
def test_a_market_that_expects_them_still_gets_them(market):
    """The cry-wolf half, and the one that matters most: widening suppression to
    unknown markets must not take the fields away from the markets that expect
    them."""
    assert list(render_cv.personal_items(_with_personal(market)))


# --- labels ------------------------------------------------------------------

@pytest.mark.parametrize("lang,expected", [
    ("zh", "出生日期"), ("ja", "生年月日"), ("ko", "생년월일"),
    ("de", "Geburtsdatum"), ("nl", "Geboortedatum"), ("fr", "Date de naissance"),
])
def test_a_personal_data_label_is_written_in_the_cvs_language(lang, expected):
    """`Date Of Birth` above a Chinese value is the mirror image of the Chinese
    furniture in an English page this skill already calls a bug."""
    assert render_cv.personal_label("date_of_birth", lang) == expected


def test_an_untranslated_key_falls_back_rather_than_raising():
    assert render_cv.personal_label("security_clearance", "zh") == "Security Clearance"
    assert render_cv.personal_label("date_of_birth", "pl") == "Date Of Birth"


def test_a_language_with_no_headings_table_says_so(capsys):
    """Documented and silent until now: a Polish or Vietnamese CV rendered with
    ENGLISH section headings above its own-language content, and the first
    person to notice was the recruiter."""
    render_cv.reset_market_warnings()
    render_cv.headings({"meta": {"language": "pl"}})
    assert "no built-in section headings" in capsys.readouterr().err


def test_a_language_that_has_one_stays_quiet(capsys):
    render_cv.reset_market_warnings()
    assert render_cv.headings({"meta": {"language": "nl"}})["experience"] == "Werkervaring"
    assert capsys.readouterr().err == ""


def test_supplying_meta_headings_silences_it(capsys):
    """The escape hatch the warning names must actually work, or the warning is
    telling people to do something that does not help."""
    render_cv.reset_market_warnings()
    render_cv.headings({"meta": {"language": "pl", "headings": {"experience": "Doświadczenie"}}})
    assert capsys.readouterr().err == ""


def test_the_header_actually_uses_the_localized_label():
    """Mutation-found: `personal_label` was tested directly and `personal_items`
    was not, so reverting the yield to the English YAML key left the suite
    green — the translation existed and nothing said it reached the page."""
    profile = {"meta": {"language": "zh", "target_market": "中国"},
               "contact": {"personal": {"date_of_birth": "1995-03",
                                        "marital_status": "未婚"}}}
    labels = [label for label, _ in render_cv.personal_items(profile)]
    assert labels == ["出生日期", "婚姻状况"], labels
    assert not any(c.isascii() and c.isalpha() for label in labels for c in label)


# ---------------------------------------------------------------------------
# An override the renderer cannot read must fail the SAME WAY for every format.
# Found re-reading my own change, 2026-09-05: `paper_for` runs only on the LaTeX
# path, so `meta.paper: foolscap` rendered .md and .docx happily and then failed
# --format pdf with a raw Python traceback. One profile, three behaviours, and
# the only report the user got was a stack trace.
#
# It stays FATAL rather than falling back to the market default: silently
# ignoring the override is how a US CV goes out on A4, which is the defect the
# override exists to prevent.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fmt", ["md", "docx", "pdf"])
def test_an_unreadable_paper_override_fails_cleanly_in_every_format(fmt, tmp_path, capsys):
    profile = tmp_path / "p.yaml"
    profile.write_text(
        "meta:\n  name: X\n  target_market: nl\n  paper: foolscap\n"
        "contact:\n  email: x@example.com\n", encoding="utf-8")
    code = render_cv.main([str(profile), "--format", fmt,
                           "--out", str(tmp_path / f"cv.{fmt}")])
    assert code == 2, fmt
    err = capsys.readouterr().err
    assert "cannot render" in err and "meta.paper" in err
    assert "Traceback" not in err


def test_a_valid_paper_override_is_not_refused(tmp_path, capsys):
    """The twin: the escape hatch has to still work, or the validation has just
    removed the feature."""
    profile = tmp_path / "p.yaml"
    profile.write_text(
        "meta:\n  name: X\n  target_market: nl\n  paper: letter\n"
        "contact:\n  email: x@example.com\n", encoding="utf-8")
    assert render_cv.main([str(profile), "--format", "md",
                           "--out", str(tmp_path / "cv.md")]) == 0


@pytest.mark.parametrize("market,cluster", [
    # The regression an independent pass caught: making a plain hyphen a
    # non-separator (so `États-Unis` would resolve) broke the OTHER thing a
    # hyphen does — join a code to a qualifier. `DE-based` resolved to nothing,
    # and an unresolved market WITHHOLDS personal data, so a German candidate
    # writing the natural short form of their own market silently lost the photo
    # and date of birth their market expects.
    ("DE-based", 2), ("NL-based", 2), ("US-based", 1), ("NL-remote", 2),
    # …and the case that motivated the hyphen change in the first place.
    ("États-Unis", 1), ("Pays-Bas", 2), ("Nouvelle-Zélande", 1),
    # Diacritics are folded rather than listed, so the REAL spellings resolve.
    ("Groot-Brittannië", 1), ("Éire", 1), ("Österreich", 2), ("España", 2),
])
def test_both_things_a_hyphen_does_are_handled(market, cluster):
    assert render_cv.resolve_cluster(market) == cluster, market


# ---- a malformed contact.personal must not vanish silently ----------------
#
# MEASURED 2026-09-06 on a Netherlands target, where the market EXPECTS these
# fields: `personal:` written as a list of one-key dicts — which reads perfectly
# fine in YAML and is a shape a model produces — made `protected_fields` return
# [] and `personal_items` yield nothing. The date of birth and nationality
# simply were not on the CV, and stderr was empty.
#
# Every other over-strip in this module is loud: the unrecognised-market path
# prints a WARNING naming each withheld field. Silence was the outlier, and it
# is the dangerous direction — a US target would have withheld them anyway, so
# the only case this shape changes is the one where the data was wanted.

EXAMPLE_PROFILE = (pathlib.Path(__file__).resolve().parents[2]
                   / "assets" / "profile.example.yaml")


def _nl_profile(personal):
    import yaml as _yaml
    base = _yaml.safe_load(EXAMPLE_PROFILE.read_text(encoding="utf-8"))
    doc = copy.deepcopy(base)
    doc["meta"]["target_market"] = "Netherlands"
    doc.setdefault("contact", {})["personal"] = personal
    return doc


@pytest.mark.parametrize("shape", [
    [{"date_of_birth": "1992-05-01"}, {"nationality": "Dutch"}],
    "date_of_birth: 1992-05-01",
    42,
    True,
])
def test_a_non_mapping_personal_block_warns_rather_than_disappearing(shape, capsys):
    doc = _nl_profile(shape)
    assert render_cv.protected_fields(doc) == []
    assert list(render_cv.personal_items(doc)) == []
    err = capsys.readouterr().err
    assert "contact.personal is a" in err
    assert "not a mapping" in err


@pytest.mark.parametrize("shape", [
    [{"date_of_birth": "1992-05-01"}], "dob: 1992", 42, True,
])
def test_protected_fields_warns_on_its_own(shape, capsys):
    """`check_personal_data` calls ONLY this one — it never renders. A version
    that guarded the shape inline here and left the warning to `personal_items`
    would be silent on the gate's own path, and the first draft of the test
    above could not tell the two apart because it called both.
    """
    assert render_cv.protected_fields(_nl_profile(shape)) == []
    assert "contact.personal is a" in capsys.readouterr().err


def test_a_valid_personal_block_still_renders_and_stays_quiet(capsys):
    doc = _nl_profile({"date_of_birth": "1992-05-01", "nationality": "Dutch"})
    assert render_cv.protected_fields(doc) == [
        "contact.personal.date_of_birth", "contact.personal.nationality"]
    assert [v for _, v in render_cv.personal_items(doc)] == ["1992-05-01", "Dutch"]
    assert "contact.personal" not in capsys.readouterr().err


@pytest.mark.parametrize("empty", [None, "", {}, []])
def test_an_absent_personal_block_is_not_worth_warning_about(empty, capsys):
    """A profile that simply has no personal data is the ordinary case for most
    candidates. A warning there would be the noise this one exists to avoid."""
    doc = _nl_profile(empty)
    assert render_cv.protected_fields(doc) == []
    assert "contact.personal" not in capsys.readouterr().err


def test_the_shape_warning_does_not_override_the_market_interlock(capsys):
    """Shape and market are separate questions. A US target withholds whatever
    the shape is, and `_suppress_personal_data` stays the thing that decides it."""
    doc = _nl_profile({"date_of_birth": "1992-05-01"})
    doc["meta"]["target_market"] = "United States"
    assert list(render_cv.personal_items(doc)) == []
    assert "contact.personal is a" not in capsys.readouterr().err


# ---- every field the interlock names must have a label in every table ------
#
# `age` was missing from all eight, so a Chinese CV printed
# "Age: 34 · 出生日期: 1992-05-01 · 婚姻状况: 已婚" — the English word above a
# Chinese value, which is the exact bug the comment over PERSONAL_LABELS records
# fixing for `date_of_birth`. One key short of complete, and the silent
# title-case fallback is why nobody saw it.
#
# `age` is not an arbitrary key either: SKILL.md's personal-data interlock is
# specified around five fields — photo, date of birth, AGE, marital status,
# nationality — and age is the single most common personal field on an East
# Asian résumé.

INTERLOCK_PERSONAL_FIELDS = ["date_of_birth", "age", "marital_status", "nationality"]


@pytest.mark.parametrize("language", sorted(render_cv.PERSONAL_LABELS))
@pytest.mark.parametrize("field", INTERLOCK_PERSONAL_FIELDS)
def test_every_interlock_field_has_a_label(language, field):
    """The property that would have caught it. Testing `age` alone pins one
    regression; walking the interlock's own field list finds the next one."""
    label = render_cv.personal_label(field, language)
    fallback = field.replace("_", " ").title()
    assert label != fallback, (
        f"{language} has no translation for {field}, so a {language} CV prints "
        f"the English '{fallback}' above a {language} value")


def test_the_interlock_field_list_matches_what_skill_md_names():
    """If SKILL.md ever adds a sixth protected field, this list must follow —
    otherwise the test above quietly stops covering it."""
    text = (pathlib.Path(__file__).resolve().parents[2] / "SKILL.md").read_text(
        encoding="utf-8")
    for phrase in ("date of birth", "age", "marital status", "nationality"):
        assert phrase in text.lower(), phrase


@pytest.mark.parametrize("language, expected", [
    ("zh", "年龄"), ("ja", "年齢"), ("ko", "나이"),
    ("de", "Alter"), ("nl", "Leeftijd"), ("fr", "Âge"),
    ("es", "Edad"), ("it", "Età"),
])
def test_the_age_label_is_the_market_s_own_word(language, expected):
    assert render_cv.personal_label("age", language) == expected


def test_an_unknown_key_still_falls_back_rather_than_raising():
    """The fallback is deliberate: adding a `contact.personal` field must not
    require nine tables updated at once. It is only wrong for the fields the
    interlock names, which is what the parametrized test above covers."""
    assert render_cv.personal_label("driving_licence", "zh") == "Driving Licence"
    assert render_cv.personal_label("age", "en") == "Age"


# ---------------------------------------------------------------------------
# Pinned by the first complete mutation run (2026-09-25). Each test below failed
# to exist while its line could be broken with the whole suite green. Several of
# these paths are exercised only by a real TeX compile, and CI has no engine, so
# they are tested here without one.
# ---------------------------------------------------------------------------

def test_the_ambiguous_code_warning_prints_once_per_market(monkeypatch, capsys):
    """md, docx and pdf resolve one profile three times; the same WARNING three
    times is how a warning gets trained away."""
    monkeypatch.setattr(render_cv, "_AMBIGUOUS_WARNED", [])
    for _ in range(3):
        assert render_cv.resolve_cluster("Wilmington, DE") == 1
    assert capsys.readouterr().err.count("WARNING") == 1


@pytest.mark.parametrize("market, paper", [
    ("Remote United States", "letterpaper"),
    ("Toronto Canada", "letterpaper"),
    ("Munich Germany", "a4paper"),
])
def test_a_letter_country_inside_a_longer_segment_gets_letter_paper(market, paper):
    """Without a comma the country is one phrase inside a longer segment, so only
    the phrase scan can see it."""
    assert render_cv.paper_for({"target_market": market}) == paper


@pytest.mark.parametrize("market, width_mm, height_mm", [
    ("United States", 215.9, 279.4),
    ("Germany", 210.0, 297.0),
])
def test_the_docx_page_is_the_market_s_paper(tmp_path, market, width_mm, height_mm):
    """The .docx sets its own page size; nothing else checked it, so a US CV
    could come out on A4 while the PDF of the same profile was on Letter."""
    from docx import Document
    out = tmp_path / "cv.docx"
    render_cv.render_docx({"meta": {"name": "Z", "target_market": market},
                           "contact": {"email": "z@x.com"}}, out)
    section = Document(str(out)).sections[0]
    assert section.page_width.mm == pytest.approx(width_mm, abs=0.1)
    assert section.page_height.mm == pytest.approx(height_mm, abs=0.1)


def test_an_entry_with_no_right_column_is_a_plain_full_width_heading():
    """With no dates or place there is nothing to measure. The title gets the
    whole line as an ordinary paragraph, not a parbox 1em short of it."""
    assert (render_cv._tex_entry_heading("Engineer", "")
            == r"\smallskip\noindent Engineer\par")
    assert r"\setbox0" in render_cv._tex_entry_heading("Engineer", "2020")


def test_a_list_section_the_profile_does_not_have_is_not_printed():
    """section_order() lists every section, present or not. An empty one has to
    print nothing: a heading over an empty itemize is a LaTeX error, which only
    a real compile would show."""
    p = {"meta": {"name": "Z"}, "contact": {"email": "z@x.com"}, "awards": []}
    tex = render_cv.build_latex(p)
    h = render_cv.headings(p)
    for key in ("publications", "awards", "certifications", "achievements",
                "board", "volunteer"):
        assert r"\section*{%s}" % h[key] not in tex, key
    assert "\\begin{itemize}\n\\end{itemize}" not in tex


def _engine_that_reports(out, log):
    """A stand-in for a TeX engine: it writes a PDF, exits 0 and prints `log`."""
    def fake_run(cmd, **kw):
        out.write_bytes(b"%PDF-1.5\n")
        class R:
            returncode = 0
            stdout = log
            stderr = ""
        return R()
    return fake_run


def test_a_line_past_the_margin_deletes_the_pdf(tmp_path, monkeypatch):
    """The real-compile version of this test needs an engine and is skipped
    without one, which left the off-page refusal untested in CI."""
    tex, out = tmp_path / "cv.tex", tmp_path / "cv.pdf"
    tex.write_text("x", encoding="utf-8")
    monkeypatch.setattr(render_cv.subprocess, "run", _engine_that_reports(
        out, "Overfull \\hbox (86.0pt too wide) in paragraph at lines 9--10\n"))
    reasons = []
    assert render_cv.compile_latex("tectonic", tex, out, reasons=reasons) is False
    assert reasons == [render_cv.TEXT_OFF_PAGE]
    assert not out.exists()


def test_a_line_into_the_margin_warns_and_keeps_the_pdf(tmp_path, monkeypatch, capsys):
    """The twin: inside the margin the text is still on the paper, so the PDF
    stays and the run says so on stderr."""
    tex, out = tmp_path / "cv.tex", tmp_path / "cv.pdf"
    tex.write_text("x", encoding="utf-8")
    monkeypatch.setattr(render_cv.subprocess, "run", _engine_that_reports(
        out, "Overfull \\hbox (12.5pt too wide) in paragraph at lines 4--5\n"))
    reasons = []
    assert render_cv.compile_latex("tectonic", tex, out, reasons=reasons) is True
    assert reasons == []
    assert out.exists()
    assert "WARNING" in capsys.readouterr().err
