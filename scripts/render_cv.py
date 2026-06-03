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


# ── i18n headings ────────────────────────────────────────────────────────────

HEADINGS = {
    "en": {
        "summary":        "Summary",
        "experience":     "Experience",
        "education":      "Education",
        "skills":         "Skills",
        "projects":       "Projects",
        "publications":   "Publications",
        "awards":         "Awards",
        "certifications": "Certifications",
        "volunteer":      "Volunteer",
    },
    "nl": {
        "summary":        "Samenvatting",
        "experience":     "Werkervaring",
        "education":      "Opleiding",
        "skills":         "Vaardigheden",
        "projects":       "Projecten",
        "publications":   "Publicaties",
        "awards":         "Prijzen",
        "certifications": "Certificeringen",
        "volunteer":      "Vrijwilligerswerk",
    },
}


def headings(profile):
    """Return the headings dict for the profile's language (default 'en')."""
    lang = (profile.get("meta") or {}).get("language", "en")
    return HEADINGS.get(lang, HEADINGS["en"])


# ── URL helpers ───────────────────────────────────────────────────────────────

def normalize_url(u):
    """Ensure URL has a scheme; strip trailing whitespace."""
    u = (u or "").strip()
    if u and "://" not in u:
        return "https://" + u
    return u


def display_url(u):
    """Return a human-readable URL (no scheme prefix)."""
    for prefix in ("https://", "http://"):
        if u.startswith(prefix):
            return u[len(prefix):]
    return u


# ── Shared helpers ────────────────────────────────────────────────────────────

def load_profile(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _contact_line(profile):
    """Plain-text contact line used by Markdown/docx (raw URLs, · separator)."""
    c = profile.get("contact", {}) or {}
    parts = [c.get("email"), c.get("phone"), c.get("location")]
    links = (c.get("links") or {})
    parts += [v for v in links.values() if v]
    return " · ".join([p for p in parts if p])


# ── Markdown renderer ─────────────────────────────────────────────────────────

def render_markdown(profile):
    h = headings(profile)
    meta = profile.get("meta", {}) or {}
    lines = [f"# {meta.get('name', '')}".rstrip()]
    if meta.get("headline"):
        lines.append(f"*{meta['headline']}*")

    # Contact line — render links as [display](url)
    c = profile.get("contact", {}) or {}
    contact_parts = [c.get("email"), c.get("phone"), c.get("location")]
    for raw_url in (c.get("links") or {}).values():
        if raw_url:
            url = normalize_url(raw_url)
            disp = display_url(url)
            contact_parts.append(f"[{disp}]({url})")
    contact_str = " · ".join([p for p in contact_parts if p])
    if contact_str:
        lines.append(contact_str)

    if profile.get("summary"):
        lines += ["", f"## {h['summary']}", profile["summary"].strip()]

    exp = profile.get("experience") or []
    if exp:
        lines += ["", f"## {h['experience']}"]
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
        lines += ["", f"## {h['education']}"]
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
        lines += ["", f"## {h['skills']}"]
        for group, items in skills.items():
            if items:
                lines.append(f"- **{group.capitalize()}:** {', '.join(items)}")

    projects = profile.get("projects") or []
    if projects:
        lines += ["", f"## {h['projects']}"]
        for pr in projects:
            name = pr.get("name", "")
            role = pr.get("role", "")
            desc = pr.get("description", "")
            # Build header: name — role — description (omit role if absent)
            header_parts = [f"**{name}**"]
            if role:
                header_parts.append(role)
            header_parts.append(desc)
            proj_line = " — ".join(header_parts)
            # Append project links
            proj_links = pr.get("links") or []
            if proj_links:
                link_strs = []
                for raw in proj_links:
                    url = normalize_url(raw)
                    disp = display_url(url)
                    link_strs.append(f"[{disp}]({url})")
                proj_line += " — " + ", ".join(link_strs)
            lines.append(proj_line)

    for key in ("publications", "awards", "certifications", "volunteer"):
        items = profile.get(key) or []
        if items:
            lines += ["", f"## {h[key]}"]
            lines += [f"- {it}" for it in items]

    return "\n".join(lines) + "\n"


# ── docx renderer ─────────────────────────────────────────────────────────────

def render_docx(profile, out_path):
    from docx import Document
    from docx.shared import Pt

    h = headings(profile)
    doc = Document()
    meta = profile.get("meta", {}) or {}
    doc.add_heading(meta.get("name", ""), level=0)
    if meta.get("headline"):
        doc.add_paragraph(meta["headline"])

    # Contact line — render links with display text (URL in parens)
    c = profile.get("contact", {}) or {}
    contact_parts = [c.get("email"), c.get("phone"), c.get("location")]
    for raw_url in (c.get("links") or {}).values():
        if raw_url:
            url = normalize_url(raw_url)
            disp = display_url(url)
            contact_parts.append(f"{disp} ({url})")
    contact_str = " · ".join([p for p in contact_parts if p])
    if contact_str:
        doc.add_paragraph(contact_str)

    if profile.get("summary"):
        doc.add_heading(h["summary"], level=1)
        doc.add_paragraph(profile["summary"].strip())

    if profile.get("experience"):
        doc.add_heading(h["experience"], level=1)
        for e in profile["experience"]:
            hp = doc.add_paragraph()
            hp.add_run(f"{e.get('title','')}, {e.get('org','')}").bold = True
            dates = f"{e.get('start','')} – {e.get('end','')}".strip(" –")
            meta_bits = " · ".join([b for b in [e.get("location", ""), dates] if b])
            if meta_bits:
                doc.add_paragraph(meta_bits)
            for b in (e.get("bullets") or []):
                doc.add_paragraph(b, style="List Bullet")

    if profile.get("education"):
        doc.add_heading(h["education"], level=1)
        for ed in profile["education"]:
            p = doc.add_paragraph()
            p.add_run(f"{ed.get('degree','')}, {ed.get('institution','')}").bold = True
            if ed.get("details"):
                doc.add_paragraph(ed["details"])

    skills = profile.get("skills") or {}
    if any(skills.values()):
        doc.add_heading(h["skills"], level=1)
        for group, items in skills.items():
            if items:
                p = doc.add_paragraph()
                p.add_run(f"{group.capitalize()}: ").bold = True
                p.add_run(", ".join(items))

    if profile.get("projects"):
        doc.add_heading(h["projects"], level=1)
        for pr in profile["projects"]:
            p = doc.add_paragraph()
            p.add_run(f"{pr.get('name','')}: ").bold = True
            role = pr.get("role", "")
            desc = pr.get("description", "")
            text_parts = [x for x in [role, desc] if x]
            p.add_run(" — ".join(text_parts) if text_parts else "")
            # Render project links
            proj_links = pr.get("links") or []
            for raw in proj_links:
                url = normalize_url(raw)
                disp = display_url(url)
                doc.add_paragraph(f"{disp} ({url})")

    for key in ("publications", "awards", "certifications", "volunteer"):
        items = profile.get(key) or []
        if items:
            doc.add_heading(h[key], level=1)
            for it in items:
                doc.add_paragraph(it, style="List Bullet")

    doc.save(str(out_path))


# ── LaTeX helpers ─────────────────────────────────────────────────────────────

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


# ── LaTeX renderer ────────────────────────────────────────────────────────────

def build_latex(profile):
    e = latex_escape
    h = headings(profile)
    meta = profile.get("meta", {}) or {}
    parts = [
        r"\documentclass[11pt,a4paper]{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage[T1]{fontenc}",
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

    # Build contact line using \textbullet{} separator and \href for links
    c = profile.get("contact", {}) or {}
    contact_parts = []
    for field in ("email", "phone", "location"):
        val = c.get(field)
        if val:
            contact_parts.append(e(val))
    for raw_url in (c.get("links") or {}).values():
        if raw_url:
            url = normalize_url(raw_url)
            disp = display_url(url)
            contact_parts.append(r"\href{%s}{%s}" % (url, e(disp)))
    if contact_parts:
        parts.append(r" \textbullet{} ".join(contact_parts))

    parts.append(r"\end{center}")

    if profile.get("summary"):
        parts += [r"\section*{%s}" % h["summary"], e(profile["summary"].strip())]

    if profile.get("experience"):
        parts.append(r"\section*{%s}" % h["experience"])
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
        parts.append(r"\section*{%s}" % h["education"])
        for ed in profile["education"]:
            dates = f"{ed.get('start','')} -- {ed.get('end','')}".strip(" -")
            parts.append(r"\textbf{%s}, %s \hfill %s\\" % (
                e(ed.get("degree", "")), e(ed.get("institution", "")), e(dates)))
            if ed.get("details"):
                parts.append(e(ed["details"]) + r"\\")

    skills = profile.get("skills") or {}
    if any(skills.values()):
        parts.append(r"\section*{%s}" % h["skills"])
        for group, items in skills.items():
            if items:
                parts.append(r"\textbf{%s:} %s\\" % (
                    e(group.capitalize()), e(", ".join(items))))

    if profile.get("projects"):
        parts.append(r"\section*{%s}" % h["projects"])
        for pr in profile["projects"]:
            name = pr.get("name", "")
            role = pr.get("role", "")
            desc = pr.get("description", "")
            line_parts = [r"\textbf{%s}" % e(name)]
            if role:
                line_parts.append(e(role))
            line_parts.append(e(desc))
            proj_line = ", ".join(line_parts)
            # Project links via \href
            proj_links = pr.get("links") or []
            link_strs = []
            for raw in proj_links:
                url = normalize_url(raw)
                disp = display_url(url)
                link_strs.append(r"\href{%s}{%s}" % (url, e(disp)))
            if link_strs:
                proj_line += " --- " + ", ".join(link_strs)
            parts.append(proj_line + r"\\")

    for key in ("publications", "awards", "certifications", "volunteer"):
        items = profile.get(key) or []
        if items:
            parts.append(r"\section*{%s}" % h[key])
            parts.append(r"\begin{itemize}")
            parts += [r"\item %s" % e(it) for it in items]
            parts.append(r"\end{itemize}")

    parts.append(r"\end{document}")
    return "\n".join(parts) + "\n"


# ── PDF renderer ──────────────────────────────────────────────────────────────

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
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print(
            f"WARNING: LaTeX compile failed. PDF could not be produced. "
            f"LaTeX source is at: {tex_path}",
            file=sys.stderr,
        )
        return False

    # If the engine wrote the PDF next to the .tex but the caller requested a
    # different name, move it into place.
    if not out_path.exists():
        produced = tex_path.with_suffix(".pdf")
        if produced.exists():
            produced.replace(out_path)
    return True


# ── CLI ───────────────────────────────────────────────────────────────────────

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
