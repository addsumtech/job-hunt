"""Every profile field the CV declares must survive into ALL THREE deliverables.

The defect this exists for: an audit neutralised six content branches of
`build_latex` and four of `render_docx` and the whole suite stayed green,
because every judge, gate and test in the skill reads `cv.md` — and `cv.md`
still rendered. `cv.docx` and `cv.pdf` are what an employer actually opens.

This test is DERIVED, not a list of five strings. It walks the fixture profile,
turns every leaf into a path pattern, and requires an entry in SURFACES for each
pattern — so a field added to `assets/profile.example.yaml` with no entry here
fails this test by name instead of quietly skipping parity.
"""
import pathlib
import sys
import zipfile

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import check_pages
import render_cv

ENGINE = render_cv.find_latex_engine()
needs_engine = pytest.mark.skipif(ENGINE is None, reason="no LaTeX engine installed")

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
MD, DOCX, TEX, PDF = "md", "docx", "latex", "pdf"
ALL = frozenset((MD, DOCX, TEX))


# ── walking the profile into path patterns ───────────────────────────────────
# Dicts whose KEYS are themselves rendered text (a skills-group label, a
# personal-data label) rather than schema names.
KEYED_AS_CONTENT = {"skills", "contact.personal"}
# Dicts whose keys SELECT a rendering rather than being rendered (the link key
# picks the friendly label via `link_label`).
KEYED_AS_SELECTOR = {"contact.links"}


def walk(node, path=""):
    """Yield (pattern, value) for every leaf, list indices collapsed to `[]`."""
    if isinstance(node, dict):
        for k, v in node.items():
            if path in KEYED_AS_CONTENT:
                yield f"{path}.<key>#label", k
                yield from walk(v, f"{path}.<key>")
            elif path in KEYED_AS_SELECTOR:
                yield from walk(v, f"{path}.<key>")
            else:
                yield from walk(v, f"{path}.{k}" if path else str(k))
    elif isinstance(node, list):
        for item in node:
            yield from walk(item, path + "[]")
    else:
        yield path, node


# ── how a value is expected to SHOW UP, per format ───────────────────────────
# A field is never "exempt from checking". It is either
#   * ALL          — the same literal string in all three, or
#   * a surface fn — the string it turns into (computed with the renderers' OWN
#                    shared helper, so this file never re-implements the rule), or
#   * PREDICATES   — per-format evidence, for a value that cannot be a literal
#                    (a photo is bytes in .docx and a staged filename in .tex), or
#   * NOT_RENDERED — configuration that steers rendering and is not text on the
#                    page. It still needs an entry, with the reason.
#   * KNOWN_GAP    — currently missing somewhere. Asserted in BOTH directions so
#                    the gap can neither widen nor heal unnoticed.

def _link_url(value, profile):
    return render_cv.normalize_url(value)


def _personal_label(value, profile):
    """The label `personal_items` derives from a `contact.personal` key."""
    keys = list(((profile.get("contact") or {}).get("personal") or {}))
    labels = [lab for lab, _ in render_cv.personal_items(profile)]
    return dict(zip(keys, labels)).get(value, value)


def _group_label(value, profile):
    return render_cv.group_label(value)


def _photo_predicates(value, profile, art):
    path = pathlib.Path(value)
    return {
        MD: f"![Photo]({path})" in art.md,
        DOCX: bool(art.docx_media),
        TEX: r"\includegraphics" in art.tex and art.staged_photo.exists(),
    }


# `\href{url}{Label}` puts the URL in a PDF *link annotation*, which is not
# extractable text — only the Label is. So a URL is asserted in .md/.docx/.tex,
# and the LABEL is what must survive into the compiled PDF (below).
LINK_PATTERNS = frozenset((
    "contact.links.<key>", "contact.links.<key>.url", "projects[].links[]"))

NOT_RENDERED = "not-rendered"
KNOWN_GAP = "known-gap"

SURFACES = {
    # pattern                       expectation                     reason
    "meta.name":                   (ALL, None),
    "meta.headline":               (ALL, None),
    "meta.target_market":          (NOT_RENDERED, "selects the cluster; steers photo/personal suppression"),
    "meta.language":               (NOT_RENDERED, "selects the heading table"),
    "meta.headings.<any>":         (ALL, None),
    "meta.photo":                  (_photo_predicates, "bytes in .docx, staged filename in .tex, path in .md"),
    "contact.email":               (ALL, None),
    "contact.phone":               (ALL, None),
    "contact.location":            (ALL, None),
    "contact.personal.<key>#label": (_personal_label, "the key is title-cased into the on-CV label"),
    "contact.personal.<key>":      (ALL, None),
    "contact.links.<key>":         (_link_url, "rendered as the scheme-normalised URL"),
    "contact.links.<key>.url":     (_link_url, "rendered as the scheme-normalised URL"),
    "contact.links.<key>.label":   (ALL, None),
    "summary":                     (ALL, None),
    "experience[].title":          (ALL, None),
    "experience[].org":            (ALL, None),
    "experience[].location":       (ALL, None),
    "experience[].start":          (ALL, None),
    "experience[].end":            (ALL, None),
    "experience[].bullets[]":      (ALL, None),
    "education[].degree":          (ALL, None),
    "education[].institution":     (ALL, None),
    "education[].location":        (ALL, None),
    "education[].start":           (ALL, None),
    "education[].end":             (ALL, None),
    "education[].details":         (ALL, None),
    "skills.<key>#label":          (_group_label, "the group key is the on-CV label, first letter upper-cased"),
    "skills.<key>[]":              (ALL, None),
    "projects[].name":             (ALL, None),
    "projects[].role":             (ALL, None),
    "projects[].description":      (ALL, None),
    "projects[].links[]":          (_link_url, "rendered as the scheme-normalised URL"),
    "publications[]":              (ALL, None),
    "awards[]":                    (ALL, None),
    "certifications[]":            (ALL, None),
    "achievements[]":              (ALL, None),
    "board[]":                     (ALL, None),
    "volunteer[]":                 (ALL, None),
    "extras.photo":                (NOT_RENDERED, "legacy flag; meta.photo is what the renderers read"),
}


def _pattern_key(pattern):
    """meta.headings.<anything> collapses to one entry — the keys are section names."""
    return "meta.headings.<any>" if pattern.startswith("meta.headings.") else pattern


# ── the three artifacts, read back off disk ──────────────────────────────────

class Artifacts:
    def __init__(self, profile, tmp_path):
        from docx import Document
        self.profile = profile
        self.md = render_cv.render_markdown(profile)
        docx_out = tmp_path / "cv.docx"
        render_cv.render_docx(profile, docx_out)
        doc = Document(str(docx_out))
        text = [p.text for p in doc.paragraphs]
        # Hyperlink URLs live in the relationship part, never in paragraph text.
        text += [r.target_ref for r in doc.part.rels.values() if r.is_external]
        self.docx = "\n".join(text)
        self.docx_media = [n for n in zipfile.ZipFile(docx_out).namelist()
                           if n.startswith("word/media/")]
        self.tex = render_cv.build_latex(profile, asset_dir=str(tmp_path),
                                         asset_stem="cv")
        self.staged_photo = tmp_path / "cv-photo.png"
        # The .tex is a proxy. `cv.pdf` is the file the employer opens, so when a
        # LaTeX engine exists we assert against the COMPILED text, not the source.
        self.pdf_readings = None
        if ENGINE is not None:
            pdf_out = tmp_path / "cv.pdf"
            if render_cv.render_pdf(profile, pdf_out):
                self.pdf_readings = check_pages.extract_text(pdf_out)

    def contains(self, fmt, surface):
        if fmt == MD:
            return surface in self.md
        if fmt == DOCX:
            return surface in self.docx
        if fmt == TEX:
            return (render_cv.latex_escape(surface) in self.tex
                    or surface in self.tex)
        return check_pages.pdf_contains(self.pdf_readings, surface)


@pytest.fixture
def artifacts(tmp_path):
    profile = render_cv.load_profile(FIXTURES / "parity_profile.yaml")
    return Artifacts(profile, tmp_path)


# ── the tests ────────────────────────────────────────────────────────────────

def test_every_profile_field_has_a_declared_cross_format_expectation():
    """A new field in the schema cannot skip parity by being forgotten here."""
    raw = yaml.safe_load((FIXTURES / "parity_profile.yaml").read_text())
    seen = {_pattern_key(p) for p, _ in walk(raw)}
    undeclared = sorted(seen - set(SURFACES))
    assert not undeclared, (
        "profile field(s) with no cross-format expectation declared in "
        f"SURFACES: {undeclared}")
    unused = sorted(set(SURFACES) - seen)
    assert not unused, f"SURFACES declares patterns the fixture never produces: {unused}"


def test_the_parity_fixture_exercises_every_field_the_example_profile_declares():
    """The shipped example has six EMPTY list sections and no `summary`, so it
    cannot drive this test — it never reaches the `simple_list` branch at all."""
    example = yaml.safe_load(
        (pathlib.Path(__file__).resolve().parents[2] / "assets/profile.example.yaml").read_text())
    example_keys = {_pattern_key(p) for p, _ in walk(example)}
    fixture_keys = set(SURFACES)
    missing = sorted(example_keys - fixture_keys)
    assert not missing, f"example profile declares fields the parity fixture omits: {missing}"


def test_every_field_reaches_every_format(artifacts):
    raw = yaml.safe_load((FIXTURES / "parity_profile.yaml").read_text())
    failures = []
    for pattern, value in walk(raw):
        key = _pattern_key(pattern)
        expectation, extra = SURFACES[key]
        if expectation is NOT_RENDERED:
            continue
        if callable(expectation) and expectation is _photo_predicates:
            for fmt, ok in expectation(value, artifacts.profile, artifacts).items():
                if not ok:
                    failures.append(f"{pattern}={value!r} missing from {fmt}")
            continue
        if expectation is KNOWN_GAP:
            expected_in = extra
        elif callable(expectation):
            value, expected_in = expectation(value, artifacts.profile), ALL
        else:
            expected_in = expectation
        for fmt in ALL:
            present = artifacts.contains(fmt, str(value))
            if fmt in expected_in and not present:
                failures.append(f"{pattern}={value!r} missing from {fmt}")
            if fmt not in expected_in and present:
                failures.append(
                    f"{pattern}={value!r} now reaches {fmt} — the KNOWN_GAP entry "
                    f"in SURFACES is stale, delete it")
    assert not failures, "cross-format parity broken:\n  " + "\n  ".join(failures)


def test_every_rendered_section_heading_reaches_every_format(artifacts):
    """Headings are derived from `headings(profile)`, so a new section is covered
    the day it is added — and a neutralised builder loses its heading even when
    its items happen to appear elsewhere on the page."""
    labels = render_cv.headings(artifacts.profile)
    failures = []
    for key in render_cv.section_order(artifacts.profile):
        if not artifacts.profile.get(key):
            continue
        for fmt in ALL:
            if not artifacts.contains(fmt, labels[key]):
                failures.append(f"heading {key!r} ({labels[key]!r}) missing from {fmt}")
    assert not failures, "section headings missing:\n  " + "\n  ".join(failures)


@needs_engine
def test_every_field_that_reaches_the_tex_also_reaches_the_compiled_pdf(artifacts):
    """`cv.tex` is a proxy; `cv.pdf` is the artifact. A compile that drops a
    section, or a font that drops glyphs, is invisible to every .tex assertion."""
    if artifacts.pdf_readings is None:
        pytest.skip("the engine is present but produced no PDF")
    assert artifacts.pdf_readings, "no text could be extracted from cv.pdf"
    raw = yaml.safe_load((FIXTURES / "parity_profile.yaml").read_text())
    failures = []
    for pattern, value in walk(raw):
        key = _pattern_key(pattern)
        expectation, extra = SURFACES[key]
        if (expectation is NOT_RENDERED or expectation is _photo_predicates
                or key in LINK_PATTERNS):
            continue
        if expectation is KNOWN_GAP:
            if TEX not in extra:
                continue
        elif callable(expectation):
            value = expectation(value, artifacts.profile)
        if not artifacts.contains(PDF, str(value)):
            failures.append(f"{pattern}={value!r} is in cv.tex but not in cv.pdf")
    assert not failures, "text lost between .tex and .pdf:\n  " + "\n  ".join(failures)


def _all_link_labels(profile):
    """Every visible link label the renderers derive, contact + project."""
    labels = [label for label, _ in render_cv._contact_links(profile)]
    for pr in (profile.get("projects") or []):
        for item in (pr.get("links") or []):
            label, url = render_cv.resolve_link(item)
            if url:
                labels.append(label)
    return labels


def test_every_link_label_reaches_every_format(artifacts):
    """A URL is never visible text; its label is. Derived from the profile's own
    links, so a link added to the schema is covered without editing this test."""
    failures = []
    for label in _all_link_labels(artifacts.profile):
        for fmt in ALL:
            if not artifacts.contains(fmt, label):
                failures.append(f"link label {label!r} missing from {fmt}")
    assert not failures, "link labels missing:\n  " + "\n  ".join(failures)


@needs_engine
def test_every_link_label_survives_into_the_compiled_pdf(artifacts):
    if artifacts.pdf_readings is None:
        pytest.skip("the engine is present but produced no PDF")
    missing = [l for l in _all_link_labels(artifacts.profile)
               if not artifacts.contains(PDF, l)]
    assert not missing, f"link labels missing from cv.pdf: {missing}"
