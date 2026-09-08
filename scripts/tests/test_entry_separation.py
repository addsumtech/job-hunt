"""Entries must be separated — in the Markdown a parser reads, and on the page.

TWO DEFECTS, ONE ROOT: consecutive experience/education entries were emitted with
no separation, only a line break.

MARKDOWN — the serious one. A bold entry header written directly after a bullet
is LAZY CONTINUATION in CommonMark: the header is absorbed into the preceding
list item. Measured with pandoc on a real generated CV, the whole Experience
section collapsed into ONE list item, so a parser saw one job where the candidate
had four. `cv.md` is what the ATS judge reads and what a candidate pastes into a
portal.

This was reported once before and not fixed: in the iteration-2 eval pilot, the
baseline run on eval-17 wrote it up against the OLD skill — "no blank line
between roles in the Markdown so an ATS could merge two jobs into one, and roles
butting together in the PDF". The new skill inherited both halves.

PDF — the visual half, plus an overflow. `\\textbf{degree}, institution \\hfill meta`
puts the metadata right-aligned with `\\hfill`, which only reaches the margin while
the line fits. On an over-long heading the line wraps, `\\hfill` collapses at the
break, the institution and location collide, and the dates orphan onto their own
line. Measured on a real CV: "MSc Computer Science (Data Science track) — Cum
Laude, Leiden University  Leiden, NL" with "2021-09 – 2023-02" alone underneath.
"""
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import render_cv  # noqa: E402

ENGINE = render_cv.find_latex_engine()
needs_engine = pytest.mark.skipif(ENGINE is None,
                                  reason="no LaTeX engine installed")
# A LaTeX engine and `pdftotext` are separate installs, and these tests need
# both. `needs_engine` guards only the first, so on a machine with tectonic and
# no poppler these crashed with FileNotFoundError instead of skipping — and the
# in-body `if returncode != 0: skip` could never catch that, because a missing
# binary raises before there is a return code to read. Found by running the suite
# with a stripped PATH, which is closer to CI than this machine is.
needs_pdftotext = pytest.mark.skipif(shutil.which("pdftotext") is None,
                                     reason="pdftotext (poppler) is not installed")

PROFILE = {
    "meta": {"name": "Test Person", "target_market": "nl", "language": "en"},
    "contact": {"email": "t@example.com"},
    "experience": [
        {"title": "Senior Engineer", "org": "First Company", "location": "Delft, NL",
         "start": "2022-01", "end": "2023-07",
         "bullets": ["Did the first thing.", "Did the second thing."]},
        {"title": "Engineer", "org": "Second Company", "location": "Leiden, NL",
         "start": "2020-01", "end": "2021-12",
         "bullets": ["Did another thing."]},
    ],
    "education": [
        {"degree": "MSc Computer Science (Data Science track) — Cum Laude",
         "institution": "Leiden University", "location": "Leiden, NL",
         "start": "2021-09", "end": "2023-02", "details": "GPA 8.35/10."},
        {"degree": "BSc Communication Engineering",
         "institution": "Harbin Institute of Technology", "location": "China",
         "start": "2016-08", "end": "2020-06", "details": "GPA 90.4/100."},
    ],
}

_ENTRY_HEADER = re.compile(r"^\*\*.+?\*\*,")


def test_no_entry_header_directly_follows_a_bullet():
    """The CommonMark lazy-continuation rule, asserted as the invariant that
    causes it — no parser needed, and it names the real hazard."""
    lines = render_cv.render_markdown(PROFILE).split("\n")
    offenders = []
    for i, line in enumerate(lines):
        if _ENTRY_HEADER.match(line) and i and lines[i - 1].startswith("- "):
            offenders.append(f"line {i + 1}: {line[:48]!r} follows "
                             f"{lines[i - 1][:40]!r}")
    assert not offenders, (
        "an entry header immediately after a list item is lazy continuation — a "
        "CommonMark parser folds the header into the previous bullet, so an ATS "
        "reads fewer jobs than the candidate has:\n  " + "\n  ".join(offenders))


def test_every_entry_header_is_preceded_by_a_blank_line():
    """Stronger and simpler: separation, whatever precedes it."""
    lines = render_cv.render_markdown(PROFILE).split("\n")
    for i, line in enumerate(lines):
        if _ENTRY_HEADER.match(line) and i:
            assert lines[i - 1].strip() == "", (
                f"line {i + 1} {line[:48]!r} is not separated from "
                f"{lines[i - 1][:44]!r}")


def test_bullets_actually_form_a_list():
    """A `- item` directly after a paragraph line is lazy continuation too, and
    this half survived the first fix.

    Measured with pandoc after separating the ENTRIES: the four jobs parsed as
    four separate blocks, and every job's bullets were still absorbed into its
    own metadata line — rendering as "- Design ... - First-author ..." inside a
    <p>, with no <ul> anywhere in the document. An ATS reading that sees each
    job's achievements as one run-on sentence.
    """
    lines = render_cv.render_markdown(PROFILE).split("\n")
    offenders = []
    for i, line in enumerate(lines):
        if line.startswith("- ") and i:
            prev = lines[i - 1]
            if prev.strip() and not prev.startswith("- "):
                offenders.append(f"line {i + 1}: {line[:40]!r} follows {prev[:40]!r}")
    assert not offenders, (
        "a list item must be preceded by a blank line or another item, or the "
        "parser folds it into the preceding paragraph:\n  " + "\n  ".join(offenders))


def test_the_bullets_still_attach_to_their_own_entry():
    """The fix must not detach the bullets it was separating."""
    md = render_cv.render_markdown(PROFILE)
    first = md.index("**Senior Engineer**")
    second = md.index("**Engineer**, Second Company")
    assert first < md.index("Did the first thing.") < second
    assert second < md.index("Did another thing.")


def test_latex_entry_headings_do_not_rely_on_a_bare_hfill():
    r"""`\hfill` reaches the margin only while the line fits. On a heading long
    enough to wrap it collapses at the break, so the right-hand metadata lands
    beside the institution and the dates orphan."""
    tex = render_cv.build_latex(PROFILE)
    bad = [l for l in tex.split("\n")
           if l.startswith(r"\textbf{") and r"\hfill" in l]
    assert not bad, (
        "entry headings still use a bare \\hfill on a wrappable line:\n  "
        + "\n  ".join(x[:90] for x in bad))


@needs_engine
@needs_pdftotext
def test_a_long_heading_keeps_its_dates_with_the_heading(tmp_path):
    """The real artifact. Compile it and read the text back.

    The MSc line here is the one measured breaking on a real CV. The property is
    that the metadata rides the heading's FIRST line — not that it shares a line
    with the institution, which it cannot once the title is long enough to wrap
    (the first draft of this test asserted that and failed on a correct fix).
    What the defect looked like was the dates alone on a line of their own.
    """
    out = tmp_path / "cv.pdf"
    render_cv.render_pdf(PROFILE, out)
    assert out.is_file(), "no PDF produced"
    lines = [l.rstrip() for l in subprocess.run(
        ["pdftotext", "-layout", str(out), "-"],
        capture_output=True, text=True, encoding="utf-8").stdout.split("\n")]

    dated = [l for l in lines if "2021-09" in l]
    assert dated, "the MSc dates are not in the PDF text at all"
    line = dated[0]
    assert "MSc Computer Science" in line, (
        f"the dates left the heading's first line:\n  {line!r}")
    assert line.strip() != "Leiden, NL \u2022 2021-09 \u2013 2023-02", (
        "the dates are alone on their own line — \\hfill collapsed at the wrap")


@needs_engine
@needs_pdftotext
def test_every_entry_keeps_its_metadata_with_its_own_heading(tmp_path):
    """Generalises the above over every entry, so a regression in one section is
    not hidden by another passing.

    Asserted as "the date line also carries this entry's own title" rather than
    by pattern-matching what an orphaned line looks like: the first draft used a
    regex for a metadata-only line and `[\\w,.\\s]*` happily swallowed the heading
    too, so a correct line matched. A test that fires on correct output is worse
    than no test.
    """
    out = tmp_path / "cv.pdf"
    render_cv.render_pdf(PROFILE, out)
    lines = [l.rstrip() for l in subprocess.run(
        ["pdftotext", "-layout", str(out), "-"],
        capture_output=True, text=True, encoding="utf-8").stdout.split("\n")]
    for date, owner in (("2022-01", "Senior Engineer"),
                        ("2020-01", "Engineer, Second Company"),
                        ("2021-09", "MSc Computer Science"),
                        ("2016-08", "BSc Communication Engineering")):
        hit = [l for l in lines if date in l]
        assert hit, f"{date} missing from the PDF"
        assert owner.split(",")[0] in hit[0], (
            f"{date} is not on a line with its own entry ({owner!r}) — the "
            f"metadata came adrift:\n  {hit[0]!r}")
