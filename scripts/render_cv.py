#!/usr/bin/env python3
"""Render a canonical profile.yaml to Markdown / .docx / PDF (via LaTeX).

Usage:
  python render_cv.py PROFILE.yaml --format md|docx|pdf --out OUTPATH
"""
import argparse
import pathlib
import shutil
import subprocess
import sys

import yaml


def load_profile(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _contact_line(profile):
    c = profile.get("contact", {}) or {}
    parts = [c.get("email"), c.get("phone"), c.get("location")]
    links = (c.get("links") or {})
    parts += [v for v in links.values() if v]
    return " · ".join([p for p in parts if p])


def render_markdown(profile):
    meta = profile.get("meta", {}) or {}
    lines = [f"# {meta.get('name', '')}".rstrip()]
    if meta.get("headline"):
        lines.append(f"*{meta['headline']}*")
    contact = _contact_line(profile)
    if contact:
        lines.append(contact)
    if profile.get("summary"):
        lines += ["", "## Summary", profile["summary"].strip()]

    exp = profile.get("experience") or []
    if exp:
        lines += ["", "## Experience"]
        for e in exp:
            header = f"**{e.get('title','')}**, {e.get('org','')}"
            dates = f"{e.get('start','')} – {e.get('end','')}".strip(" –")
            loc = e.get("location", "")
            meta_bits = " · ".join([b for b in [loc, dates] if b])
            lines.append(f"{header}" + (f"  \n_{meta_bits}_" if meta_bits else ""))
            for b in (e.get("bullets") or []):
                lines.append(f"- {b}")

    edu = profile.get("education") or []
    if edu:
        lines += ["", "## Education"]
        for ed in edu:
            dates = f"{ed.get('start','')} – {ed.get('end','')}".strip(" –")
            line = f"**{ed.get('degree','')}**, {ed.get('institution','')}"
            if dates:
                line += f"  \n_{dates}_"
            lines.append(line)
            if ed.get("details"):
                lines.append(f"- {ed['details']}")

    skills = profile.get("skills") or {}
    if any(skills.values()):
        lines += ["", "## Skills"]
        for group, items in skills.items():
            if items:
                lines.append(f"- **{group.capitalize()}:** {', '.join(items)}")

    projects = profile.get("projects") or []
    if projects:
        lines += ["", "## Projects"]
        for pr in projects:
            lines.append(f"**{pr.get('name','')}** — {pr.get('description','')}")

    for key, title in [("publications", "Publications"),
                       ("awards", "Awards"),
                       ("certifications", "Certifications"),
                       ("volunteer", "Volunteer")]:
        items = profile.get(key) or []
        if items:
            lines += ["", f"## {title}"]
            lines += [f"- {it}" for it in items]

    return "\n".join(lines) + "\n"


def render_docx(profile, out_path):
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    meta = profile.get("meta", {}) or {}
    title = doc.add_heading(meta.get("name", ""), level=0)
    if meta.get("headline"):
        doc.add_paragraph(meta["headline"])
    contact = _contact_line(profile)
    if contact:
        doc.add_paragraph(contact)

    if profile.get("summary"):
        doc.add_heading("Summary", level=1)
        doc.add_paragraph(profile["summary"].strip())

    if profile.get("experience"):
        doc.add_heading("Experience", level=1)
        for e in profile["experience"]:
            h = doc.add_paragraph()
            h.add_run(f"{e.get('title','')}, {e.get('org','')}").bold = True
            dates = f"{e.get('start','')} – {e.get('end','')}".strip(" –")
            meta_bits = " · ".join([b for b in [e.get("location", ""), dates] if b])
            if meta_bits:
                doc.add_paragraph(meta_bits)
            for b in (e.get("bullets") or []):
                doc.add_paragraph(b, style="List Bullet")

    if profile.get("education"):
        doc.add_heading("Education", level=1)
        for ed in profile["education"]:
            p = doc.add_paragraph()
            p.add_run(f"{ed.get('degree','')}, {ed.get('institution','')}").bold = True
            if ed.get("details"):
                doc.add_paragraph(ed["details"])

    skills = profile.get("skills") or {}
    if any(skills.values()):
        doc.add_heading("Skills", level=1)
        for group, items in skills.items():
            if items:
                p = doc.add_paragraph()
                p.add_run(f"{group.capitalize()}: ").bold = True
                p.add_run(", ".join(items))

    if profile.get("projects"):
        doc.add_heading("Projects", level=1)
        for pr in profile["projects"]:
            p = doc.add_paragraph()
            p.add_run(f"{pr.get('name','')}: ").bold = True
            p.add_run(pr.get("description", ""))

    doc.save(str(out_path))


_LATEX_REPLACEMENTS = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
    "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def latex_escape(text):
    if text is None:
        return ""
    out = []
    for ch in str(text):
        out.append(_LATEX_REPLACEMENTS.get(ch, ch))
    return "".join(out)


def find_latex_engine():
    for engine in ("tectonic", "pdflatex"):
        if shutil.which(engine):
            return engine
    return None


def build_latex(profile):
    e = latex_escape
    meta = profile.get("meta", {}) or {}
    parts = [
        r"\documentclass[11pt,a4paper]{article}",
        r"\usepackage[margin=2cm]{geometry}",
        r"\usepackage{enumitem}",
        r"\usepackage[hidelinks]{hyperref}",
        r"\setlist{nosep,leftmargin=*}",
        r"\pagestyle{empty}",
        r"\begin{document}",
        r"\begin{center}",
        r"{\LARGE \textbf{%s}}\\[2pt]" % e(meta.get("name", "")),
    ]
    if meta.get("headline"):
        parts.append(r"{\large %s}\\[2pt]" % e(meta["headline"]))
    parts.append(e(_contact_line(profile)))
    parts.append(r"\end{center}")

    if profile.get("summary"):
        parts += [r"\section*{Summary}", e(profile["summary"].strip())]

    if profile.get("experience"):
        parts.append(r"\section*{Experience}")
        for ex in profile["experience"]:
            dates = f"{ex.get('start','')} -- {ex.get('end','')}".strip(" -")
            parts.append(r"\textbf{%s}, %s \hfill %s\\" % (
                e(ex.get("title", "")), e(ex.get("org", "")), e(dates)))
            bullets = ex.get("bullets") or []
            if bullets:
                parts.append(r"\begin{itemize}")
                parts += [r"\item %s" % e(b) for b in bullets]
                parts.append(r"\end{itemize}")

    if profile.get("education"):
        parts.append(r"\section*{Education}")
        for ed in profile["education"]:
            dates = f"{ed.get('start','')} -- {ed.get('end','')}".strip(" -")
            parts.append(r"\textbf{%s}, %s \hfill %s\\" % (
                e(ed.get("degree", "")), e(ed.get("institution", "")), e(dates)))
            if ed.get("details"):
                parts.append(e(ed["details"]) + r"\\")

    skills = profile.get("skills") or {}
    if any(skills.values()):
        parts.append(r"\section*{Skills}")
        for group, items in skills.items():
            if items:
                parts.append(r"\textbf{%s:} %s\\" % (
                    e(group.capitalize()), e(", ".join(items))))

    parts.append(r"\end{document}")
    return "\n".join(parts) + "\n"


def render_pdf(profile, out_path):
    """Build PDF via LaTeX. Returns True on success, False if no engine
    (still writes the .tex next to out_path so nothing is lost)."""
    out_path = pathlib.Path(out_path)
    tex_path = out_path.with_suffix(".tex")
    tex_path.write_text(build_latex(profile), encoding="utf-8")

    engine = find_latex_engine()
    if engine is None:
        print("WARNING: no LaTeX engine (tectonic/pdflatex) found. "
              f"Wrote {tex_path}; install tectonic to produce a PDF.",
              file=sys.stderr)
        return False

    if engine == "tectonic":
        cmd = [engine, str(tex_path), "--outdir", str(out_path.parent)]
    else:
        cmd = [engine, "-interaction=nonstopmode", "-output-directory",
               str(out_path.parent), str(tex_path)]
    subprocess.run(cmd, check=True, capture_output=True)
    produced = tex_path.with_suffix(".pdf")
    if produced != out_path and produced.exists():
        produced.replace(out_path)
    return True


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("profile")
    ap.add_argument("--format", choices=["md", "docx", "pdf"], default="md")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    profile = load_profile(args.profile)
    out = pathlib.Path(args.out)

    if args.format == "md":
        out.write_text(render_markdown(profile), encoding="utf-8")
    elif args.format == "docx":
        render_docx(profile, out)
    elif args.format == "pdf":
        ok = render_pdf(profile, out)
        if ok:
            print(f"Wrote {out}")
        else:
            tex = out.with_suffix(".tex")
            print(
                f"PDF could not be built (no LaTeX engine found). "
                f"LaTeX source written to: {tex}",
                file=sys.stderr,
            )
        return
    print(f"Wrote {out}")


if __name__ == "__main__":
    sys.exit(main())
