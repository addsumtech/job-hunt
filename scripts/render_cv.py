#!/usr/bin/env python3
"""Render a canonical profile.yaml to Markdown / .docx / PDF (via LaTeX).

Usage:
  python render_cv.py PROFILE.yaml --format md|docx|pdf --out OUTPATH
"""
import argparse
import pathlib
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
        render_pdf(profile, out)
    print(f"Wrote {out}")


if __name__ == "__main__":
    sys.exit(main())
