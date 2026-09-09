#!/usr/bin/env python3
"""Render a motivation letter (letter.yaml) to Markdown / .docx / PDF.

Usage:
  python render_letter.py LETTER.yaml --format md|docx|pdf --out OUTPATH
"""
import argparse
import pathlib
# The compile itself now runs inside render_cv.compile_latex, but this import
# stays: `render_letter.subprocess` is the same module object as
# `render_cv.subprocess`, and it is the handle the letter's engine-argv test
# patches to prove the two renderers build the same argv.
import subprocess  # noqa: F401
import sys


# Reuse LaTeX helpers from render_cv (same directory).
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import journal
import render_cv


def load(path):
    """Raises journal.YamlUnreadable; main() prints it and exits 2. Same reasoning as
    render_cv.load_profile — no workspace, so no receipt, and the exit code is the
    only channel left. 2 stays "could not read the input", 1 stays "the PDF failed"."""
    return journal.load_yaml(path)


def body_paragraphs(d):
    body = d.get("body") or []
    return [body] if isinstance(body, str) else body


def render_markdown(d):
    s = d.get("sender", {}) or {}
    r = d.get("recipient", {}) or {}
    lines = [s.get("name", ""), s.get("email", ""), s.get("location", ""), ""]
    if d.get("date"):
        lines += [d["date"], ""]
    lines += [r.get("name", ""), r.get("company", ""), r.get("location", ""), ""]
    if salutation_for(d):
        lines += [salutation_for(d), ""]
    for para in body_paragraphs(d):
        lines += [para, ""]
    lines += [x for x in (closing_for(d), s.get("name", "")) if x]
    return "\n".join([ln for ln in lines]) + "\n"


def render_docx(d, out_path):
    from docx import Document
    doc = Document()
    s = d.get("sender", {}) or {}
    r = d.get("recipient", {}) or {}
    for line in [s.get("name"), s.get("email"), s.get("location")]:
        if line:
            doc.add_paragraph(line)
    if d.get("date"):
        doc.add_paragraph(d["date"])
    for line in [r.get("name"), r.get("company"), r.get("location")]:
        if line:
            doc.add_paragraph(line)
    if salutation_for(d):
        doc.add_paragraph(salutation_for(d))
    for para in body_paragraphs(d):
        doc.add_paragraph(para)
    if closing_for(d):
        doc.add_paragraph(closing_for(d))
    doc.add_paragraph(s.get("name", ""))
    doc.save(str(out_path))


# Salutations for an UNNAMED recipient, quoted from references/motivation-letter.md
# :208, which is the file that sources them. Not invented here and not translated
# here: that line is the provenance, and a second spelling in this file would be a
# second thing for the two to disagree about.
#
# Every default was `"Dear Hiring Manager,"` / `"Sincerely,"` regardless of
# language, so a Dutch letter shipped with an English opener and an English
# sign-off — against motivation-letter.md:272, "Never mix languages in one
# letter", in the renderer that file drives.
_SALUTATION = {
    "en": "Dear Hiring Team,",
    "de": "Sehr geehrte Damen und Herren,",
    "fr": "Madame, Monsieur,",
    "es": "Estimados señores:",
    "it": "Gentile Responsabile delle Assunzioni,",
    "nl": "Geachte heer/mevrouw,",
}
# Quoted from references/motivation-letter.md, the same file and the same status
# as the salutations above. An independent pass caught the asymmetry: five
# languages had a sourced opener and no sourced sign-off, so an honest Dutch or
# German letter that left `closing` unset — exactly as leaving `salutation`
# unset correctly works — hard-failed NO_CLOSING with nothing to fill it in.
#
# Languages still absent here (zh, ja, ko and the rest) keep the honest
# behaviour: no sign-off is emitted and check_letter reports the gap, because
# inventing one is what this skill bans.
_CLOSING = {
    "en": "Sincerely,",
    "de": "Mit freundlichen Grüßen",
    "nl": "Met vriendelijke groet,",
    "fr": "Cordialement,",
    "es": "Atentamente,",
    "it": "Cordiali saluti,",
}


def _language(d) -> str:
    meta = d.get("meta") if isinstance(d.get("meta"), dict) else {}
    return str(meta.get("language") or "en").strip().lower()[:2]


def salutation_for(d) -> str:
    """The letter's own `salutation`, or the sourced default for its language.

    "" when there is no sourced default — Chinese, Japanese and Korean have
    none in motivation-letter.md, and defaulting them to `Dear Hiring Team,`
    is the exact defect this function was written to remove, just moved. The
    renderer omits the line and check_letter reports the gap.
    """
    written = str(d.get("salutation") or "").strip()
    if written:
        return written
    return _SALUTATION.get(_language(d), "")


def closing_for(d) -> str:
    """The letter's own `closing`, or the sourced default — "" when there is
    none for this language, because an English sign-off on a non-English letter
    is the defect, not the fallback."""
    written = str(d.get("closing") or "").strip()
    if written:
        return written
    return _CLOSING.get(_language(d), "")


def build_latex(d, engine=None, cjk=False):
    """Assemble the letter's LaTeX source.

    The preamble comes from `render_cv.latex_preamble`, not from a copy here.
    This file used to carry its own `inputenc`+`fontenc` pair, which meant it
    also carried its own copy of the bug that pair causes under the engine
    `find_latex_engine` actually prefers: a letter to `Ștefan Ionescu` at
    `Politechnika Śląska` compiled, exited 0, and reached him addressed to
    "tefan Ionescu" at "Politechnika lska". See `latex_preamble` for why the
    choice is made from the engine and not from the text.
    """
    e = render_cv.latex_escape
    s = d.get("sender", {}) or {}
    r = d.get("recipient", {}) or {}
    # `meta` is passed for the paper size. Without it the CV in an application
    # package printed on Letter for a US role while the letter beside it printed
    # on A4 — one package, two page sizes, and nothing said so.
    parts = render_cv.latex_preamble(engine=engine, cjk=cjk, margin="2.5cm",
                                     meta=d.get("meta")) + [
        r"\pagestyle{empty}",
        r"\begin{document}",
        r"\noindent %s\\ %s\\ %s\\[1em]" % (
            e(s.get("name", "")), e(s.get("email", "")), e(s.get("location", ""))),
    ]
    if d.get("date"):
        parts.append(r"%s\\[1em]" % e(d["date"]))
    parts.append(r"\noindent %s\\ %s\\ %s\\[1em]" % (
        e(r.get("name", "")), e(r.get("company", "")), e(r.get("location", ""))))
    if salutation_for(d):
        parts.append(e(salutation_for(d)) + r"\\[1em]")
    for para in body_paragraphs(d):
        parts.append(e(para) + r"\\[1em]")
    if closing_for(d):
        parts.append(e(closing_for(d)) + r"\\")
    parts.append(e(s.get("name", "")))
    parts.append(r"\end{document}")
    return "\n".join(parts) + "\n"


def render_pdf(d, out_path, reasons=None):
    out_path = pathlib.Path(out_path)
    tex_path = out_path.with_suffix(".tex")
    # Any PDF here is from an earlier run; this call either replaces it or must
    # leave none. Same reasoning, same helper, as render_cv.render_pdf — the two
    # early returns below (unsupported script, no engine) are exactly the paths
    # that used to leave a superseded letter sitting under the delivered name.
    render_cv._discard_pdf(out_path, tex_path)

    # Right-to-left first, and before any source is written. Same template, same
    # missing `bidi`, same consequence as render_cv: the compile succeeds and
    # produces a reversed, unshaped page at exit 0. The .tex is refused with it,
    # because it is the source that produces exactly that page.
    if render_cv.profile_has_rtl(d):
        print("WARNING: the letter contains right-to-left text (Arabic, Hebrew "
              "or similar). The LaTeX template has no bidi support, so a PDF "
              "built from it would come out reversed and unshaped. No PDF was "
              "written; Markdown and .docx carry the text correctly.",
              file=sys.stderr)
        return render_cv._note(reasons, render_cv.UNSUPPORTED_SCRIPT)

    # CJK is TYPESET, not refused. render_cv has had an xeCJK preamble and a
    # font chain for a long time; this file simply never passed `cjk=` through,
    # so a Chinese application shipped a Chinese CV as PDF and no letter PDF at
    # all — one package, one script, two different answers, exit 0 both times.
    cjk = render_cv._has_cjk(str(d))
    # Resolve the engine first: the preamble has to match whatever will compile it.
    engine = render_cv.find_latex_engine(cjk=cjk)
    tex = build_latex(d, engine=engine, cjk=cjk)
    tex_path.write_text(tex, encoding="utf-8")
    if cjk and engine is None:
        print("WARNING: no Unicode LaTeX engine found for this CJK letter. A CJK "
              "PDF needs XeLaTeX (xelatex) or tectonic plus an installed CJK "
              f"font; pdflatex cannot do it. Source at {tex_path}.",
              file=sys.stderr)
        return render_cv._note(reasons, render_cv.NO_ENGINE)
    if engine is None:
        print(f"WARNING: no LaTeX engine found. Wrote {tex_path}.", file=sys.stderr)
        return render_cv._note(reasons, render_cv.NO_ENGINE)
    # One compile helper, both renderers — including the `Missing character`
    # scan, so a letter can no longer ship with glyphs silently dropped either.
    return render_cv.compile_latex(engine, tex_path, out_path, reasons=reasons)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("letter")
    ap.add_argument("--format", choices=["md", "docx", "pdf"], default="md")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    try:
        d = load(args.letter)
    except journal.YamlUnreadable as exc:
        print(f"cannot render: {exc}", file=sys.stderr)
        return 2
    render_cv.reset_photo_warnings()
    out = pathlib.Path(args.out)

    # Same early validation as render_cv.main: the letter shares `paper_for`, so
    # an override it cannot read must fail the same way for every format rather
    # than only on the LaTeX path.
    try:
        render_cv.paper_for((d or {}).get("meta"))
    except ValueError as exc:
        print(f"cannot render: {exc}", file=sys.stderr)
        return 2
    if args.format == "md":
        out.write_text(render_markdown(d), encoding="utf-8")
    elif args.format == "docx":
        render_docx(d, out)
    else:
        reasons = []
        ok = render_pdf(d, out, reasons=reasons)
        if ok:
            if not render_cv.confirm_written(out, "pdf"):
                return 1
            print(f"Wrote {out}")
            return 0
        print(f"PDF not built; LaTeX source at {out.with_suffix('.tex')}",
              file=sys.stderr)
        # Same split as render_cv.main, from the same table: a missing engine or
        # a script this template cannot set are documented degradations; anything
        # else means this machine could have produced a correct PDF and did not.
        return 0 if render_cv.pdf_failure_is_tolerated(reasons) else 1
    if not render_cv.confirm_written(out, args.format):
        return 1
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    from cli_io import configure_output

    configure_output()
    sys.exit(main())
