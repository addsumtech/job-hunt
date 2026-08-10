#!/usr/bin/env python3
"""Render a canonical profile.yaml to Markdown / .docx / PDF (via LaTeX).

Usage:
  python render_cv.py PROFILE.yaml --format md|docx|pdf --out OUTPATH

Three things this renderer is opinionated about, because they materially affect
how a CV reads:

1. Links show a friendly label ("Google Scholar", "GitHub"), never a raw URL.
   A naked `scholar.google.com/citations?user=AbC123` is noise to a human eye;
   the label carries the meaning and the URL rides underneath as the hyperlink
   target (and stays recoverable in the Markdown source / docx relationship for
   any ATS that strips links). See `link_label`.

2. Section order adapts to the candidate. A PhD/researcher or current student
   leads with Education (their primary credential); everyone else leads with
   Experience. `meta.section_order` overrides the heuristic entirely. See
   `section_order`.

3. A PDF always leaves its `.tex` source next to it, so the candidate can hand-
   tune typography or recompile later without rerunning this tool.
"""
import argparse
import pathlib
import re
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
        "achievements":   "Selected Achievements",
        "board":          "Board & Advisory",
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
    "de": {
        "summary": "Profil", "experience": "Berufserfahrung", "education": "Ausbildung",
        "skills": "Kenntnisse", "projects": "Projekte", "publications": "Publikationen",
        "awards": "Auszeichnungen", "certifications": "Zertifizierungen", "volunteer": "Ehrenamt",
    },
    "fr": {
        "summary": "Profil", "experience": "Expérience professionnelle", "education": "Formation",
        "skills": "Compétences", "projects": "Projets", "publications": "Publications",
        "awards": "Distinctions", "certifications": "Certifications", "volunteer": "Bénévolat",
    },
    "es": {
        "summary": "Perfil", "experience": "Experiencia profesional", "education": "Formación",
        "skills": "Competencias", "projects": "Proyectos", "publications": "Publicaciones",
        "awards": "Premios", "certifications": "Certificaciones", "volunteer": "Voluntariado",
    },
    "it": {
        "summary": "Profilo", "experience": "Esperienza professionale", "education": "Formazione",
        "skills": "Competenze", "projects": "Progetti", "publications": "Pubblicazioni",
        "awards": "Riconoscimenti", "certifications": "Certificazioni", "volunteer": "Volontariato",
    },
    "zh": {
        "summary": "个人简介", "experience": "工作经历", "education": "教育背景",
        "skills": "专业技能", "projects": "项目经历", "publications": "论文发表",
        "awards": "获奖经历", "certifications": "证书", "volunteer": "志愿服务",
        "achievements": "主要成就", "board": "董事会与顾问",
    },
    "ja": {
        "summary": "概要", "experience": "職務経歴", "education": "学歴",
        "skills": "スキル", "projects": "プロジェクト", "publications": "論文",
        "awards": "受賞歴", "certifications": "資格", "volunteer": "ボランティア",
        "achievements": "主な実績", "board": "役員・顧問",
    },
    "ko": {
        "summary": "소개", "experience": "경력", "education": "학력",
        "skills": "기술", "projects": "프로젝트", "publications": "출판물",
        "awards": "수상 경력", "certifications": "자격증", "volunteer": "봉사활동",
        "achievements": "주요 성과", "board": "이사회 및 자문",
    },
}


def headings(profile):
    """Section labels for the profile's language (default 'en').

    Built-ins cover the common cluster languages (en, nl, de, fr, es, it). For
    any other language — including CJK — set `meta.headings` to a dict of
    {section_key: localized_label}; it overrides/extends the built-in set, so a
    Korean or Japanese CV can localize its headings without a code change. The
    model populates `meta.headings` when rendering in a language with no built-in.
    """
    meta = profile.get("meta") or {}
    # English is the floor: start from it, then overlay the target language's
    # table. Any key a language table doesn't translate falls back to the English
    # label instead of raising — so adding a new section never needs all nine
    # tables updated at once, and a partially-localized language degrades cleanly.
    base = dict(HEADINGS["en"])
    base.update(HEADINGS.get(meta.get("language", "en"), {}))
    override = meta.get("headings") or {}
    if isinstance(override, dict):
        base.update({k: v for k, v in override.items() if k in base and v})
    return base


# ── URL helpers ───────────────────────────────────────────────────────────────

def normalize_url(u):
    """Ensure URL has a scheme; strip trailing whitespace. Coerces non-string
    inputs (a YAML link that parsed as a number/date) so a malformed profile
    never crashes the render."""
    u = str(u or "").strip()
    if u and "://" not in u:
        return "https://" + u
    return u


def display_url(u):
    """Return a human-readable URL (no scheme prefix). Kept for callers that
    want the bare URL; the CV itself prefers `link_label` instead."""
    for prefix in ("https://", "http://"):
        if u.startswith(prefix):
            return u[len(prefix):]
    return u


# Friendly labels keyed by the contact.links key (normalised: lowercase, no
# separators) or by the URL's host. The point is that a reader scanning the
# header sees "Google Scholar", not a query-string-laden URL.
_LABELS_BY_KEY = {
    "scholar": "Google Scholar",
    "googlescholar": "Google Scholar",
    "github": "GitHub",
    "gitlab": "GitLab",
    "bitbucket": "Bitbucket",
    "linkedin": "LinkedIn",
    "orcid": "ORCID",
    "website": "Website",
    "homepage": "Website",
    "site": "Website",
    "portfolio": "Portfolio",
    "blog": "Blog",
    "twitter": "Twitter",
    "x": "X",
    "mastodon": "Mastodon",
    "researchgate": "ResearchGate",
    "semanticscholar": "Semantic Scholar",
    "youtube": "YouTube",
    "medium": "Medium",
    "substack": "Substack",
    "kaggle": "Kaggle",
    "huggingface": "Hugging Face",
    "stackoverflow": "Stack Overflow",
    "devpost": "Devpost",
    "dribbble": "Dribbble",
    "behance": "Behance",
}

_LABELS_BY_HOST = {
    "scholar.google.com": "Google Scholar",
    "github.com": "GitHub",
    "gitlab.com": "GitLab",
    "bitbucket.org": "Bitbucket",
    "linkedin.com": "LinkedIn",
    "orcid.org": "ORCID",
    "twitter.com": "Twitter",
    "x.com": "X",
    "researchgate.net": "ResearchGate",
    "semanticscholar.org": "Semantic Scholar",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "medium.com": "Medium",
    "substack.com": "Substack",
    "kaggle.com": "Kaggle",
    "huggingface.co": "Hugging Face",
    "stackoverflow.com": "Stack Overflow",
    "devpost.com": "Devpost",
    "dribbble.com": "Dribbble",
    "behance.net": "Behance",
}


def _host(url):
    """Bare host of a URL, lowercased, without leading www / userinfo / port."""
    s = str(url or "")
    host = s.split("://", 1)[-1].split("/", 1)[0].split("?", 1)[0]
    host = host.split("@", 1)[-1].split(":", 1)[0]   # drop user@ and :port
    if host.startswith("www."):
        host = host[4:]
    return host.lower()


def link_label(url, key=None, explicit=None):
    """Human-readable label for a link.

    Priority: an explicit label the profile supplied → a known key (e.g. the
    `scholar:` field) → a known host → a title-cased key → the bare host. We
    never fall back to the full URL: the whole point is to keep it off the page.
    """
    if explicit:
        return explicit
    url = str(url or "")
    if key:
        norm = "".join(ch for ch in key.lower() if ch.isalnum())
        if norm in _LABELS_BY_KEY:
            return _LABELS_BY_KEY[norm]
    host = _host(url)
    if host in _LABELS_BY_HOST:
        return _LABELS_BY_HOST[host]
    for known_host, label in _LABELS_BY_HOST.items():
        if host == known_host or host.endswith("." + known_host):
            return label
    if key:
        return key.replace("_", " ").replace("-", " ").title()
    return host or url


def resolve_link(item, key=None):
    """Turn a link entry into ``(label, url)``.

    An entry may be a bare URL string or a ``{label, url}`` mapping — the latter
    lets a profile override the auto-label (e.g. label a personal domain
    "Portfolio"). Returns ``(None, None)`` for an empty entry so callers can skip.
    """
    explicit = None
    if isinstance(item, dict):
        explicit = item.get("label") or item.get("text")
        raw = item.get("url") or item.get("href") or ""
    else:
        raw = item or ""
    if not raw:
        return None, None
    url = normalize_url(raw)
    return link_label(url, key=key, explicit=explicit), url


# ── Section ordering ──────────────────────────────────────────────────────────

# Two sensible defaults. Industry leads with Experience (recruiters spend
# seconds on the first pass and want impact up top); academic leads with
# Education and surfaces Publications early (the primary credentials of a
# researcher). Empty sections are skipped regardless, so an order may safely
# list sections a given profile doesn't have.
# `achievements` (a "Selected Achievements" band) and `board` (board/advisory
# roles) exist mainly for senior/executive CVs; they sit near the end of the
# default orders (empty → skipped for everyone else), and an exec promotes them
# via meta.section_order. They must appear here so section_order accepts them.
_INDUSTRY_ORDER = ["summary", "achievements", "experience", "education", "skills",
                   "projects", "publications", "awards", "certifications", "board",
                   "volunteer"]
_ACADEMIC_ORDER = ["summary", "achievements", "education", "experience", "publications",
                   "skills", "projects", "awards", "certifications", "board", "volunteer"]
_ALL_SECTIONS = _INDUSTRY_ORDER  # canonical set of known section keys

_ACADEMIC_TITLE_SIGNALS = (
    "phd", "ph.d", "ph. d", "doctoral", "postdoc", "post-doc", "postdoctoral",
    "research fellow", "research scientist", "research associate",
    "research assistant", "researcher", "lecturer", "professor",
)


# Word-boundary match so an end date that is genuinely ongoing ("present",
# "2027 (est.)", "expected 2027") reads as current, while substrings inside
# ordinary words ("greatest", "invested", "West") do not.
_ONGOING_RE = re.compile(r"\b(present|current|ongoing|now|expected|anticipated|est)\b")


def _is_current(entry):
    """True if an experience/education entry is ongoing (no real end date)."""
    end = (entry.get("end") or "").strip().lower()
    return end == "" or bool(_ONGOING_RE.search(end))


def is_academic_profile(profile):
    """Heuristic: should this CV lead with Education?

    Conservative on purpose — a senior engineer who happens to have a paper is
    not 'academic'. We flip only when the candidate's *current* situation is
    academic: a current research/PhD role, or a current student with no
    professional experience yet. Anything finer, the profile sets
    `meta.section_order` explicitly.
    """
    for ex in (profile.get("experience") or []):
        title = (ex.get("title") or "").lower()
        if _is_current(ex) and any(sig in title for sig in _ACADEMIC_TITLE_SIGNALS):
            return True
    currently_studying = any(_is_current(ed) for ed in (profile.get("education") or []))
    has_pro_experience = any((ex.get("bullets") or []) for ex in (profile.get("experience") or []))
    return currently_studying and not has_pro_experience


def section_order(profile):
    """Resolve the order of body sections for this profile.

    `meta.section_order` wins if present (unknown keys ignored; any known
    section the profile omitted is appended in default order so a section with
    real content is never silently dropped — order is for sequencing, not
    hiding). Otherwise pick the academic or industry default.
    """
    default = _ACADEMIC_ORDER if is_academic_profile(profile) else _INDUSTRY_ORDER
    explicit = (profile.get("meta") or {}).get("section_order")
    if not explicit:
        return default
    if isinstance(explicit, str):       # tolerate a single key written as a scalar
        explicit = [explicit]
    order = []
    for s in list(explicit) + default:           # explicit first, then any omitted
        if s in _ALL_SECTIONS and s not in order:  # known-only, de-duplicated
            order.append(s)
    return order


# ── Shared helpers ────────────────────────────────────────────────────────────

def load_profile(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _contact_links(profile):
    """Yield (label, url) for each non-empty contact link, in profile order."""
    for key, item in ((profile.get("contact") or {}).get("links") or {}).items():
        label, url = resolve_link(item, key=key)
        if url:
            yield label, url


# Markets where a photo / DOB / nationality on a CV is a liability rather than a
# convention (US/Canada/UK/Ireland/Australia/NZ). The skill's tailoring step is
# meant to strip these for such targets; the renderer enforces the same rule as
# defense-in-depth so a mis-tailored profile can't leak protected data onto a
# Cluster-1 CV. Matched loosely against meta.target_market.
_CLUSTER1_MARKETS = {
    "us", "usa", "united states", "ca", "can", "canada", "uk", "gb",
    "united kingdom", "britain", "england", "scotland", "wales", "ie", "irl",
    "ireland", "au", "aus", "australia", "nz", "new zealand",
}


def _is_cluster1(profile):
    tm = str((profile.get("meta") or {}).get("target_market", "")).strip().lower()
    return tm in _CLUSTER1_MARKETS


def personal_items(profile):
    """(label, value) personal-data pairs for the header, in profile order.

    Drawn from ``contact.personal`` (a dict like {date_of_birth, nationality,
    hometown, marital_status}). These are normal on CVs in much of the EU and
    East Asia and absent in the Anglophone world — so they are suppressed
    entirely for a Cluster-1 target even if present (see `_is_cluster1`)."""
    if _is_cluster1(profile):
        return
    personal = (profile.get("contact") or {}).get("personal") or {}
    if not isinstance(personal, dict):
        return
    for key, value in personal.items():
        if value in (None, ""):
            continue
        label = str(key).replace("_", " ").strip().title()
        yield label, normalize_text(value)


def photo_path(profile):
    """Resolved filesystem path of the CV photo, or None.

    Suppressed for Cluster-1 targets (a US/UK photo CV invites discrimination-law
    exposure and auto-rejection). Returns None if unset or the file is missing,
    so a stale path degrades to a photo-less CV rather than a crash."""
    if _is_cluster1(profile):
        return None
    p = (profile.get("meta") or {}).get("photo")
    if not p:
        return None
    path = pathlib.Path(str(p)).expanduser()
    return path if path.is_file() else None


def as_list(v):
    """Coerce a value into a list of items for rendering.

    Profiles are model-authored YAML, so a field that should be a list
    (``bullets``, a skills group, ``publications``) is sometimes written as a
    bare string — e.g. ``languages: "Python, C++"`` instead of a list. Iterating
    that string character-by-character silently renders 'P, y, t, h, …', which
    *looks* like a successful render but is garbage. Coercing a scalar to a
    single-item list turns that mistake into one readable item instead, and
    keeps a genuinely empty field empty.
    """
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return list(v)
    return [v]


def item_str(it):
    """Render one list item (a skill, certification, award, publication) as text.

    These are meant to be plain strings, but a model sometimes writes a list of
    dicts (e.g. ``{name: "RN", id: "12345", status: "active"}``). Plain
    ``str(dict)`` would emit Python's ``{'name': ...}`` repr onto the CV. Instead
    we join the dict's own values into a readable phrase, leading with a name-like
    field when present — strictly better than a repr, and a no-op for strings.
    """
    if isinstance(it, dict):
        lead = next((str(it[k]) for k in ("name", "title", "label", "text") if it.get(k)), None)
        rest = [str(v) for k, v in it.items()
                if k not in ("name", "title", "label", "text") and v not in (None, "")]
        parts = ([lead] if lead else []) + rest
        return " — ".join(parts)
    return str(it)


def group_label(group):
    """Display label for a skills group, preserving the author's intended case.

    The earlier ``str.capitalize()`` lower-cased everything after the first
    letter, which destroys acronyms and intentional casing — "ML/AI" became
    "Ml/ai" and "Programming Languages" became "Programming languages". We only
    upper-case the first character (so a lazily-lowercased "languages" still
    reads as "Languages") and leave the rest exactly as written.
    """
    g = str(group)
    return g[:1].upper() + g[1:] if g else g


# ── Markdown renderer ─────────────────────────────────────────────────────────

def render_markdown(profile):
    h = headings(profile)
    meta = profile.get("meta", {}) or {}
    lines = [f"# {meta.get('name', '')}".rstrip()]
    if meta.get("headline"):
        lines.append(f"*{meta['headline']}*")

    # Contact line — links render as [Label](url)
    c = profile.get("contact", {}) or {}
    contact_parts = [c.get("email"), c.get("phone"), c.get("location")]
    contact_parts += [f"[{label}]({url})" for label, url in _contact_links(profile)]
    contact_str = " · ".join([p for p in contact_parts if p])
    if contact_str:
        lines.append(contact_str)
    personal = [f"{label}: {value}" for label, value in personal_items(profile)]
    if personal:
        lines.append(" · ".join(personal))
    ph = photo_path(profile)
    if ph:
        lines.append(f"![Photo]({ph})")

    def summary():
        if profile.get("summary"):
            return ["", f"## {h['summary']}", normalize_text(profile["summary"]).strip()]
        return []

    def experience():
        out = []
        for e in (profile.get("experience") or []):
            if not out:
                out += ["", f"## {h['experience']}"]
            header = f"**{e.get('title','')}**, {e.get('org','')}"
            dates = f"{e.get('start','')} – {e.get('end','')}".strip(" –")
            meta_bits = " · ".join([b for b in [e.get("location", ""), dates] if b])
            out.append(header + (f"  \n_{meta_bits}_" if meta_bits else ""))
            out += [f"- {normalize_text(b)}" for b in as_list(e.get("bullets"))]
        return out

    def education():
        out = []
        for ed in (profile.get("education") or []):
            if not out:
                out += ["", f"## {h['education']}"]
            dates = f"{ed.get('start','')} – {ed.get('end','')}".strip(" –")
            line = f"**{ed.get('degree','')}**, {ed.get('institution','')}"
            if dates:
                line += f"  \n_{dates}_"
            out.append(line)
            if ed.get("details"):
                out.append(f"- {ed['details']}")
        return out

    def skills():
        sk = profile.get("skills") or {}
        if not any(sk.values()):
            return []
        out = ["", f"## {h['skills']}"]
        for group, items in sk.items():
            items = as_list(items)
            if items:
                out.append(f"- **{group_label(group)}:** {', '.join(normalize_text(item_str(i)) for i in items)}")
        return out

    def projects():
        prs = profile.get("projects") or []
        if not prs:
            return []
        out = ["", f"## {h['projects']}"]
        for pr in prs:
            header_parts = [f"**{pr.get('name', '')}**"]
            if pr.get("role"):
                header_parts.append(pr["role"])
            if pr.get("description"):
                header_parts.append(pr["description"])
            proj_line = " — ".join(header_parts)
            link_strs = [f"[{label}]({url})"
                         for label, url in (resolve_link(x) for x in (pr.get("links") or []))
                         if url]
            if link_strs:
                proj_line += " — " + ", ".join(link_strs)
            out.append(proj_line)
        return out

    def simple_list(key):
        items = as_list(profile.get(key))
        if not items:
            return []
        return ["", f"## {h[key]}"] + [f"- {normalize_text(item_str(it))}" for it in items]

    builders = {
        "summary": summary, "experience": experience, "education": education,
        "skills": skills, "projects": projects,
        "publications": lambda: simple_list("publications"),
        "awards": lambda: simple_list("awards"),
        "certifications": lambda: simple_list("certifications"),
        "achievements": lambda: simple_list("achievements"),
        "board": lambda: simple_list("board"),
        "volunteer": lambda: simple_list("volunteer"),
    }
    for key in section_order(profile):
        lines += builders.get(key, list)()

    return "\n".join(lines) + "\n"


# ── docx renderer ─────────────────────────────────────────────────────────────

def _add_hyperlink(paragraph, text, url):
    """Append a real, clickable hyperlink run (blue + underlined) showing `text`."""
    from docx.oxml.ns import qn
    from docx.oxml.shared import OxmlElement

    r_id = paragraph.part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    color = OxmlElement("w:color"); color.set(qn("w:val"), "0563C1"); rpr.append(color)
    underline = OxmlElement("w:u"); underline.set(qn("w:val"), "single"); rpr.append(underline)
    run.append(rpr)
    t = OxmlElement("w:t"); t.text = text; run.append(t)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)
    return hyperlink


def render_docx(profile, out_path):
    from docx import Document

    h = headings(profile)
    doc = Document()
    meta = profile.get("meta", {}) or {}
    doc.add_heading(meta.get("name", ""), level=0)
    if meta.get("headline"):
        doc.add_paragraph(meta["headline"])

    # Contact line — plain runs for email/phone/location, real hyperlinks (with
    # the friendly label as visible text) for the rest.
    c = profile.get("contact", {}) or {}
    plain_bits = [b for b in (c.get("email"), c.get("phone"), c.get("location")) if b]
    links = list(_contact_links(profile))
    if plain_bits or links:
        p = doc.add_paragraph()
        first = True
        for b in plain_bits:
            if not first:
                p.add_run(" · ")
            p.add_run(b)
            first = False
        for label, url in links:
            if not first:
                p.add_run(" · ")
            _add_hyperlink(p, label, url)
            first = False

    personal = [f"{label}: {value}" for label, value in personal_items(profile)]
    if personal:
        doc.add_paragraph(" · ".join(personal))
    ph = photo_path(profile)
    if ph:
        try:
            from docx.shared import Inches
            doc.add_picture(str(ph), width=Inches(1.3))
        except Exception:
            pass  # an unreadable/unsupported image must not sink the whole render

    def summary():
        if profile.get("summary"):
            doc.add_heading(h["summary"], level=1)
            doc.add_paragraph(normalize_text(profile["summary"]).strip())

    def experience():
        exp = profile.get("experience") or []
        if not exp:
            return
        doc.add_heading(h["experience"], level=1)
        for e in exp:
            doc.add_paragraph().add_run(
                f"{e.get('title','')}, {e.get('org','')}").bold = True
            dates = f"{e.get('start','')} – {e.get('end','')}".strip(" –")
            meta_bits = " · ".join([b for b in [e.get("location", ""), dates] if b])
            if meta_bits:
                doc.add_paragraph(meta_bits)
            for b in as_list(e.get("bullets")):
                doc.add_paragraph(normalize_text(b), style="List Bullet")

    def education():
        edu = profile.get("education") or []
        if not edu:
            return
        doc.add_heading(h["education"], level=1)
        for ed in edu:
            doc.add_paragraph().add_run(
                f"{ed.get('degree','')}, {ed.get('institution','')}").bold = True
            dates = f"{ed.get('start','')} – {ed.get('end','')}".strip(" –")
            if dates:
                doc.add_paragraph(dates)
            if ed.get("details"):
                doc.add_paragraph(ed["details"])

    def skills():
        sk = profile.get("skills") or {}
        if not any(sk.values()):
            return
        doc.add_heading(h["skills"], level=1)
        for group, items in sk.items():
            items = as_list(items)
            if items:
                p = doc.add_paragraph()
                p.add_run(f"{group_label(group)}: ").bold = True
                p.add_run(", ".join(normalize_text(item_str(i)) for i in items))

    def projects():
        prs = profile.get("projects") or []
        if not prs:
            return
        doc.add_heading(h["projects"], level=1)
        for pr in prs:
            p = doc.add_paragraph()
            p.add_run(pr.get("name", "")).bold = True
            text_parts = [x for x in [pr.get("role", ""), pr.get("description", "")] if x]
            if text_parts:
                p.add_run(": " + " — ".join(text_parts))
            resolved = [(label, url) for label, url in
                        (resolve_link(x) for x in (pr.get("links") or [])) if url]
            for i, (label, url) in enumerate(resolved):
                p.add_run(" — " if i == 0 else ", ")
                _add_hyperlink(p, label, url)

    def simple_list(key):
        items = as_list(profile.get(key))
        if not items:
            return
        doc.add_heading(h[key], level=1)
        for it in items:
            doc.add_paragraph(normalize_text(item_str(it)), style="List Bullet")

    builders = {
        "summary": summary, "experience": experience, "education": education,
        "skills": skills, "projects": projects,
        "publications": lambda: simple_list("publications"),
        "awards": lambda: simple_list("awards"),
        "certifications": lambda: simple_list("certifications"),
        "achievements": lambda: simple_list("achievements"),
        "board": lambda: simple_list("board"),
        "volunteer": lambda: simple_list("volunteer"),
    }
    for key in section_order(profile):
        builders.get(key, lambda: None)()

    doc.save(str(out_path))


# ── LaTeX helpers ─────────────────────────────────────────────────────────────

_LATEX_REPLACEMENTS = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
    "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    # Common Unicode punctuation that pdfLaTeX (Latin path) cannot typeset as-is —
    # map to LaTeX equivalents so an em-dash or a curly quote pasted from a CV
    # doesn't fail the compile. (XeLaTeX would accept the literals, but the mapped
    # forms render correctly there too.)
    "—": "---", "–": "--", "…": r"\ldots{}", " ": "~",
    "‘": "`", "’": "'", "“": "``", "”": "''",
}

# Whitespace sitting *between* two CJK characters is almost always an artifact of
# a YAML folded scalar (`>`), which joins wrapped lines with a space — but CJK has
# no inter-character spaces, so it shows up as a gap mid-word. Strip it.
_CJK = r"　-鿿豈-﫿가-힣぀-ヿ"
_CJK_GAP_RE = re.compile(r"(?<=[%s])[ \t]+(?=[%s])" % (_CJK, _CJK))


def normalize_text(text):
    """Clean a user-text string before rendering: drop folded-scalar spaces that
    landed between CJK characters. Format-agnostic, so all renderers can use it."""
    if text is None:
        return ""
    return _CJK_GAP_RE.sub("", str(text))


def latex_escape(text):
    if text is None:
        return ""
    out = []
    for ch in normalize_text(text):
        out.append(_LATEX_REPLACEMENTS.get(ch, ch))
    return "".join(out)


# Standard install locations searched when an engine isn't on PATH. A
# non-login shell (which is what the renderer often runs inside) frequently
# lacks Homebrew's /opt/homebrew/bin or the MacTeX bin on PATH, so a plain
# shutil.which misses a perfectly good tectonic/xelatex. We fall back to these.
_ENGINE_DIRS = ["/opt/homebrew/bin", "/usr/local/bin", "/Library/TeX/texbin",
                "~/.cargo/bin", "/usr/bin", "/bin"]


def find_latex_engine(cjk=False):
    """Locate a usable LaTeX engine, returning its path (or bare name).

    A CJK CV must be typeset by a Unicode/OpenType engine (XeTeX or LuaTeX) so
    that ``xeCJK`` and system CJK fonts work — ``pdflatex`` cannot do it. So for
    CJK we look only for ``xelatex``/``lualatex``/``tectonic`` (tectonic is
    XeTeX-based and handles ``xeCJK``). For Latin scripts, ``pdflatex`` is fine
    and ``tectonic`` is preferred for its self-contained package handling.
    Callers detect the engine *type* from the basename, so a returned absolute
    path works the same as a bare name.
    """
    candidates = ("xelatex", "lualatex", "tectonic") if cjk else ("tectonic", "pdflatex")
    for engine in candidates:
        found = shutil.which(engine)
        if found:
            return found
        for d in _ENGINE_DIRS:
            cand = pathlib.Path(d).expanduser() / engine
            if cand.is_file():
                return str(cand)
    return None


def _has_cjk(text):
    """True if text contains CJK / Hangul / Thai characters, which need a
    Unicode LaTeX engine (XeTeX/LuaTeX) and a CJK font rather than the default
    Latin-script setup."""
    return any("　" <= ch <= "鿿" or "가" <= ch <= "힣"
               or "฀" <= ch <= "๿" for ch in text)


def profile_has_cjk(profile):
    """Whether any rendered text in the profile is CJK/Hangul/Thai. Drives the
    XeLaTeX-vs-pdfLaTeX preamble choice. A flat string dump is enough — we only
    need to know whether such characters appear anywhere."""
    return _has_cjk(str(profile))


# Cross-platform CJK font fallback. xeCJK needs a real installed CJK font, and
# the right name differs per OS (macOS PingFang, Windows YaHei/Malgun, Linux
# Noto). We emit a nested \IfFontExistsTF chain that picks the first font that
# is actually installed, so the same .tex compiles on a typical mac, Windows or
# Linux box without hand-editing. `meta.cjk_font` jumps the queue. If none is
# found, xeCJK falls back to its own default (and may error — the .tex is still
# delivered for the user to point at a font they have).
_CJK_FONT_FALLBACKS = [
    "Noto Sans CJK SC", "Source Han Sans SC", "PingFang SC", "Hiragino Sans GB",
    "Microsoft YaHei", "SimSun",                       # Chinese
    "Noto Sans CJK JP", "Hiragino Sans", "Yu Gothic",  # Japanese
    "Noto Sans CJK KR", "Apple SD Gothic Neo", "Malgun Gothic",  # Korean
]


def _cjk_font_setup(meta):
    fonts = [str(meta["cjk_font"])] if meta.get("cjk_font") else []
    fonts += _CJK_FONT_FALLBACKS
    setup = "{}"  # innermost: leave xeCJK's own default
    for f in reversed(fonts):
        setup = r"\IfFontExistsTF{%s}{\setCJKmainfont{%s}}{%s}" % (f, f, setup)
    return setup


# ── LaTeX renderer ────────────────────────────────────────────────────────────

def build_latex(profile, cjk=None):
    """Assemble the LaTeX source.

    `cjk` selects the engine-specific preamble: a CJK CV needs a XeLaTeX setup
    (fontspec + xeCJK + a system CJK font) instead of the pdfLaTeX
    inputenc/fontenc setup, which cannot render CJK glyphs at all. When `cjk`
    is None we auto-detect from the profile content.
    """
    e = latex_escape
    # Escape headings for LaTeX up front: section labels can legitimately contain
    # LaTeX-special characters — the regulated-profession recipes use headers like
    # "Licenses & Certifications" and "Board & Advisory", and a raw "&" is a fatal
    # alignment-tab error. (Markdown/docx use the unescaped headings.)
    h = {k: e(v) for k, v in headings(profile).items()}
    meta = profile.get("meta", {}) or {}
    if cjk is None:
        cjk = profile_has_cjk(profile)
    if cjk:
        preamble = [
            r"\documentclass[11pt,a4paper]{article}",
            r"\usepackage[margin=2cm]{geometry}",
            r"\usepackage{enumitem}",
            r"\usepackage{fontspec}",
            r"\usepackage{xeCJK}",
            _cjk_font_setup(meta),
        ]
    else:
        preamble = [
            r"\documentclass[11pt,a4paper]{article}",
            r"\usepackage[utf8]{inputenc}",
            r"\usepackage[T1]{fontenc}",
            r"\usepackage[margin=2cm]{geometry}",
            r"\usepackage{enumitem}",
        ]
    parts = preamble + [
        r"\usepackage[hidelinks]{hyperref}",
        r"\usepackage{graphicx}",
        r"\setlist{nosep,leftmargin=*}",
        r"\pagestyle{empty}",
        r"\begin{document}",
        r"\begin{center}",
    ]
    # A passport-style photo above the name is the common layout for the EU/Asia
    # photo-CV; suppressed entirely for Cluster-1 targets by photo_path().
    ph = photo_path(profile)
    if ph:
        parts.append(r"\includegraphics[height=3cm]{%s}\\[6pt]" % str(ph))
    parts.append(r"{\LARGE \textbf{%s}}\\[2pt]" % e(meta.get("name", "")))
    if meta.get("headline"):
        parts.append(r"{\large %s}\\[2pt]" % e(meta["headline"]))

    # Contact line — \textbullet{} separators; links via \href{url}{Label}.
    c = profile.get("contact", {}) or {}
    contact_parts = [e(c.get(f)) for f in ("email", "phone", "location") if c.get(f)]
    contact_parts += [r"\href{%s}{%s}" % (url, e(label))
                      for label, url in _contact_links(profile)]
    if contact_parts:
        parts.append(r" \textbullet{} ".join(contact_parts))
    personal_parts = [e(f"{label}: {value}") for label, value in personal_items(profile)]
    if personal_parts:
        parts.append(r"\\[2pt]" + r" \textbullet{} ".join(personal_parts))
    parts.append(r"\end{center}")

    def summary():
        if profile.get("summary"):
            parts.extend([r"\section*{%s}" % h["summary"], e(profile["summary"].strip())])

    def experience():
        exp = profile.get("experience") or []
        if not exp:
            return
        parts.append(r"\section*{%s}" % h["experience"])
        for ex in exp:
            dates = f"{ex.get('start','')} -- {ex.get('end','')}".strip(" -")
            parts.append(r"\textbf{%s}, %s \hfill %s\\" % (
                e(ex.get("title", "")), e(ex.get("org", "")), e(dates)))
            bullets = as_list(ex.get("bullets"))
            if bullets:
                parts.append(r"\begin{itemize}")
                parts.extend(r"\item %s" % e(b) for b in bullets)
                parts.append(r"\end{itemize}")

    def education():
        edu = profile.get("education") or []
        if not edu:
            return
        parts.append(r"\section*{%s}" % h["education"])
        for ed in edu:
            dates = f"{ed.get('start','')} -- {ed.get('end','')}".strip(" -")
            parts.append(r"\textbf{%s}, %s \hfill %s\\" % (
                e(ed.get("degree", "")), e(ed.get("institution", "")), e(dates)))
            if ed.get("details"):
                parts.append(e(ed["details"]) + r"\\")

    def skills():
        sk = profile.get("skills") or {}
        if not any(sk.values()):
            return
        parts.append(r"\section*{%s}" % h["skills"])
        for group, items in sk.items():
            items = as_list(items)
            if items:
                parts.append(r"\textbf{%s:} %s\\" % (
                    e(group_label(group)), e(", ".join(item_str(i) for i in items))))

    def projects():
        prs = profile.get("projects") or []
        if not prs:
            return
        parts.append(r"\section*{%s}" % h["projects"])
        for pr in prs:
            line_parts = [r"\textbf{%s}" % e(pr.get("name", ""))]
            if pr.get("role"):
                line_parts.append(e(pr["role"]))
            if pr.get("description"):
                line_parts.append(e(pr["description"]))
            proj_line = ", ".join(line_parts)
            link_strs = [r"\href{%s}{%s}" % (url, e(label))
                         for label, url in (resolve_link(x) for x in (pr.get("links") or []))
                         if url]
            if link_strs:
                proj_line += " --- " + ", ".join(link_strs)
            parts.append(proj_line + r"\\")

    def simple_list(key):
        items = as_list(profile.get(key))
        if not items:
            return
        parts.append(r"\section*{%s}" % h[key])
        parts.append(r"\begin{itemize}")
        parts.extend(r"\item %s" % e(item_str(it)) for it in items)
        parts.append(r"\end{itemize}")

    builders = {
        "summary": summary, "experience": experience, "education": education,
        "skills": skills, "projects": projects,
        "publications": lambda: simple_list("publications"),
        "awards": lambda: simple_list("awards"),
        "certifications": lambda: simple_list("certifications"),
        "achievements": lambda: simple_list("achievements"),
        "board": lambda: simple_list("board"),
        "volunteer": lambda: simple_list("volunteer"),
    }
    for key in section_order(profile):
        builders.get(key, lambda: None)()

    parts.append(r"\end{document}")
    return "\n".join(parts) + "\n"


# ── PDF renderer ──────────────────────────────────────────────────────────────

def render_pdf(profile, out_path):
    """Build PDF via LaTeX. Always writes the `.tex` next to out_path (it is a
    deliverable in its own right, not just a failure breadcrumb). Returns True
    on success, False if no engine / compile failed."""
    out_path = pathlib.Path(out_path)
    tex_path = out_path.with_suffix(".tex")
    cjk = profile_has_cjk(profile)
    tex = build_latex(profile, cjk=cjk)
    tex_path.write_text(tex, encoding="utf-8")

    engine = find_latex_engine(cjk=cjk)
    if engine is None:
        if cjk:
            print("WARNING: no Unicode LaTeX engine found for this CJK CV. "
                  "A CJK PDF needs XeLaTeX (xelatex) or tectonic plus an "
                  "installed CJK font; pdflatex cannot do it. Markdown and "
                  f".docx still render correctly. Wrote the XeLaTeX source to "
                  f"{tex_path} — compile it with `xelatex` once an engine and a "
                  "CJK font are available.", file=sys.stderr)
        else:
            print("WARNING: no LaTeX engine (tectonic/pdflatex) found. "
                  f"Wrote {tex_path}; install tectonic to produce a PDF.",
                  file=sys.stderr)
        return False

    if pathlib.Path(engine).name == "tectonic":
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
        tex = out.with_suffix(".tex")
        if ok:
            # The .tex is delivered alongside every PDF, by design.
            print(f"Wrote {out} (LaTeX source alongside it: {tex})")
        else:
            print(
                f"PDF could not be built (no LaTeX engine found). "
                f"LaTeX source written to: {tex} — install tectonic to compile it.",
                file=sys.stderr,
            )
        return
    print(f"Wrote {out}")


if __name__ == "__main__":
    sys.exit(main())
