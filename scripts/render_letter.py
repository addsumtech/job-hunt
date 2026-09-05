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


def render_markdown(d):
    s = d.get("sender", {}) or {}
    r = d.get("recipient", {}) or {}
    lines = [s.get("name", ""), s.get("email", ""), s.get("location", ""), ""]
    if d.get("date"):
        lines += [d["date"], ""]
    lines += [r.get("name", ""), r.get("company", ""), r.get("location", ""), ""]
    lines += [d.get("salutation", "Dear Hiring Manager,"), ""]
    for para in (d.get("body") or []):
        lines += [para, ""]
    lines += [d.get("closing", "Sincerely,"), s.get("name", "")]
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
    doc.add_paragraph(d.get("salutation", "Dear Hiring Manager,"))
    for para in (d.get("body") or []):
        doc.add_paragraph(para)
    doc.add_paragraph(d.get("closing", "Sincerely,"))
    doc.add_paragraph(s.get("name", ""))
    doc.save(str(out_path))


def build_latex(d, engine=None):
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
    parts = render_cv.latex_preamble(engine=engine, margin="2.5cm",
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
    parts.append(e(d.get("salutation", "Dear Hiring Manager,")) + r"\\[1em]")
    for para in (d.get("body") or []):
        parts.append(e(para) + r"\\[1em]")
    parts.append(e(d.get("closing", "Sincerely,")) + r"\\")
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
    # Resolve the engine first: the preamble has to match whatever will compile it.
    engine = render_cv.find_latex_engine()
    tex = build_latex(d, engine=engine)
    tex_path.write_text(tex, encoding="utf-8")
    if render_cv._has_cjk(tex):
        # Still refused, and still only for CJK/Thai: this template has no xeCJK
        # and no CJK font chain, so those scripts genuinely cannot be typeset
        # here. Everything else above U+00FF — Ł, ą, Š, Ș — now compiles, which
        # is the whole point; the old guard was the only thing standing between
        # a Polish letter and a silently mangled one, and it was not standing there.
        print("WARNING: the letter contains CJK/Thai characters, which the "
              "Latin-script LaTeX template cannot compile. Use Markdown or .docx "
              f"(or a XeLaTeX template with a CJK font). Source at {tex_path}.",
              file=sys.stderr)
        return render_cv._note(reasons, render_cv.UNSUPPORTED_SCRIPT)
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
    sys.exit(main())
