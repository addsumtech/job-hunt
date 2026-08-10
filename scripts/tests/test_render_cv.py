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
    assert r"\usepackage{xeCJK}" in tex
    assert r"\setCJKmainfont" in tex
    assert "inputenc" not in tex                     # pdfLaTeX-only, must be gone
    # A Latin CV keeps the pdfLaTeX preamble.
    latin = render_cv.build_latex({"meta": {"name": "Jane Doe"}})
    assert "inputenc" in latin
    assert "xeCJK" not in latin


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
    img = tmp_path / "p.png"; img.write_bytes(b"\x89PNG\r\n\x1a\n")  # path just needs to exist
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
KNOWN_NON_CLUSTER1_SPELLINGS = [
    "nl", "Netherlands", "Amsterdam, Netherlands", "Eindhoven, NL (hybrid)",
    "Germany", "Munich, Germany", "Remote — EU", "Austria", "Switzerland",
    "cn", "China", "中国", "Japan", "Tokyo, Japan", "South Korea", "Singapore",
]
UNRECOGNIZED_SPELLINGS = ["Brazil", "Dubai, UAE", "Mars", "", "somewhere nice"]


@pytest.mark.parametrize("market", CLUSTER1_SPELLINGS)
def test_cluster1_spellings_suppress_personal_data(tmp_path, market):
    img = tmp_path / "p.png"; img.write_bytes(b"\x89PNG\r\n\x1a\n")
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
    img = tmp_path / "p.png"; img.write_bytes(b"\x89PNG\r\n\x1a\n")
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
    img = tmp_path / "p.png"; img.write_bytes(b"\x89PNG\r\n\x1a\n")
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
    img = tmp_path / "p.png"; img.write_bytes(b"\x89PNG\r\n\x1a\n")
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
    assert r"\usepackage{xeCJK}" in tex               # but a *correct* CJK .tex is written
    assert "CJK" in capsys.readouterr().err           # and the user is told why


def test_has_cjk_detects_scripts():
    assert render_cv._has_cjk("経歴") is True       # Japanese
    assert render_cv._has_cjk("경력") is True       # Korean
    assert render_cv._has_cjk("工作经历") is True    # Chinese
    assert render_cv._has_cjk("ประสบการณ์") is True  # Thai
    assert render_cv._has_cjk("Berufserfahrung") is False
    assert render_cv._has_cjk("Café résumé") is False


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
