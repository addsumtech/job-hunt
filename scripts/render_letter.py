#!/usr/bin/env python3
"""Render a motivation letter (letter.yaml) to Markdown / .docx / PDF.

Usage:
  python render_letter.py LETTER.yaml --format md|docx|pdf --out OUTPATH
"""
import argparse
import pathlib
import sys

import yaml

# Reuse LaTeX helpers from render_cv (same directory).
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import render_cv


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


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


def build_latex(d):
    e = render_cv.latex_escape
    s = d.get("sender", {}) or {}
    r = d.get("recipient", {}) or {}
    parts = [
        r"\documentclass[11pt,a4paper]{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage[T1]{fontenc}",
        r"\usepackage[margin=2.5cm]{geometry}",
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


def render_pdf(d, out_path):
    out_path = pathlib.Path(out_path)
    tex_path = out_path.with_suffix(".tex")
    tex = build_latex(d)
    tex_path.write_text(tex, encoding="utf-8")
    if render_cv._has_cjk(tex):
        print("WARNING: the letter contains CJK/Thai characters, which the "
              "Latin-script LaTeX template cannot compile. Use Markdown or .docx "
              f"(or a XeLaTeX template with a CJK font). Source at {tex_path}.",
              file=sys.stderr)
        return False
    engine = render_cv.find_latex_engine()
    if engine is None:
        print(f"WARNING: no LaTeX engine found. Wrote {tex_path}.", file=sys.stderr)
        return False
    import subprocess
    if engine == "tectonic":
        cmd = [engine, str(tex_path), "--outdir", str(out_path.parent)]
    else:
        cmd = [engine, "-interaction=nonstopmode", "-output-directory",
               str(out_path.parent), str(tex_path)]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print(f"WARNING: LaTeX compile failed. Source at {tex_path}.", file=sys.stderr)
        return False
    if not out_path.exists():
        produced = tex_path.with_suffix(".pdf")
        if produced.exists():
            produced.replace(out_path)
    return True


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("letter")
    ap.add_argument("--format", choices=["md", "docx", "pdf"], default="md")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    d = load(args.letter)
    out = pathlib.Path(args.out)
    if args.format == "md":
        out.write_text(render_markdown(d), encoding="utf-8")
    elif args.format == "docx":
        render_docx(d, out)
    else:
        ok = render_pdf(d, out)
        if ok:
            print(f"Wrote {out}")
        else:
            print(f"PDF not built; LaTeX source at {out.with_suffix('.tex')}",
                  file=sys.stderr)
        return
    print(f"Wrote {out}")


if __name__ == "__main__":
    sys.exit(main())
