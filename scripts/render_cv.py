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
import unicodedata

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
        unknown = sorted(k for k in override if k not in base)
        if unknown:
            print(f"WARNING: meta.headings key(s) "
                  f"{', '.join(repr(k) for k in unknown)} are not section keys and "
                  f"were ignored — the section keeps its default label. Valid keys: "
                  f"{', '.join(sorted(base))}.", file=sys.stderr)
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
    unknown = [s for s in explicit if s not in _ALL_SECTIONS]
    if unknown:
        print(f"WARNING: meta.section_order entr(ies) "
              f"{', '.join(repr(s) for s in unknown)} are not section keys and were "
              f"ignored. Valid keys: {', '.join(_ALL_SECTIONS)}.", file=sys.stderr)
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


# Which regional CV convention a `meta.target_market` string belongs to.
#   1 = US/CA/UK/IE/AU/NZ — a photo/DOB/nationality is a liability there; many
#       employers route such CVs straight to rejection because considering that
#       data exposes them to discrimination-law claims.
#   2 = EU/EEA, 3 = East & SE Asia — the same fields are a normal convention.
#   None = not recognised, which is NOT the same as "safe".
#
# Full names are matched as whole-word phrases anywhere in a segment, so
# "United States of America" and "London, United Kingdom" both resolve. Two-letter
# codes are matched only when they are the WHOLE segment: otherwise "Remote in
# Berlin" would resolve to India via "in", and a false resolution is worse than
# none — it silences the warning.
_CLUSTER_NAMES = {
    1: ["united states of america", "united states", "u s a", "america", "canada",
        "united kingdom", "great britain", "britain", "england", "scotland", "wales",
        "northern ireland", "republic of ireland", "ireland", "australia",
        "new zealand", "u k", "u s"],
    2: ["the netherlands", "netherlands", "holland", "germany", "deutschland",
        "france", "belgium", "spain", "italy", "portugal", "austria", "switzerland",
        "sweden", "norway", "denmark", "finland", "poland", "czechia",
        "czech republic", "luxembourg", "greece", "romania", "hungary", "ireland eu",
        "european union", "eea"],
    3: ["mainland china", "china", "hong kong", "taiwan", "japan", "south korea",
        "republic of korea", "korea", "singapore", "malaysia", "thailand", "vietnam",
        "indonesia", "philippines", "india"],
}
_CLUSTER_CODES = {
    1: ["us", "usa", "ca", "can", "uk", "gb", "ie", "irl", "au", "aus", "nz"],
    2: ["nl", "de", "fr", "be", "es", "it", "pt", "at", "ch", "se", "no", "dk",
        "fi", "pl", "cz", "lu", "gr", "ro", "hu", "eu"],
    3: ["cn", "prc", "hk", "tw", "jp", "kr", "sg", "my", "th", "vn", "id", "ph", "in"],
}
# CJK market names have no word boundaries to split on, so they are matched by
# substring. Without these a Chinese-language profile resolves to None and the
# unknown-market warning fires on a perfectly ordinary Chinese CV.
_CLUSTER_CJK = {
    1: ["美国", "英国", "加拿大", "澳大利亚", "新西兰", "爱尔兰"],
    2: ["荷兰", "德国", "法国", "比利时", "西班牙", "意大利", "瑞士", "瑞典", "欧盟"],
    3: ["中国", "中国大陆", "香港", "台湾", "日本", "韩国", "新加坡", "马来西亚", "泰国", "印度"],
}

_NAME_CLUSTER, _CODE_CLUSTER, _CJK_CLUSTER = {}, {}, {}
for _c, _names in _CLUSTER_NAMES.items():
    for _n in _names:
        _NAME_CLUSTER.setdefault(_n, _c)
for _c, _codes in _CLUSTER_CODES.items():
    for _n in _codes:
        _CODE_CLUSTER.setdefault(_n, _c)
for _c, _names in _CLUSTER_CJK.items():
    for _n in _names:
        _CJK_CLUSTER.setdefault(_n, _c)
_MAX_NAME_WORDS = max(len(_n.split()) for _n in _NAME_CLUSTER)

_MARKET_SEP = re.compile(r"[,()\[\]/|;·–—-]+")
_MARKET_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)

# The protected fields, in the order they are reported. `contact.personal` is a
# free-form dict, so any key in it is treated as protected — the risk is the
# category, not a fixed list of key names.
_PHOTO_FIELD = "meta.photo"


def _market_segments(market):
    text = unicodedata.normalize("NFKC", str(market or "")).lower()
    for seg in _MARKET_SEP.split(text):
        seg = " ".join(_MARKET_PUNCT.sub(" ", seg).split())
        if seg:
            yield seg


def resolve_cluster(market):
    """1, 2, 3 — or None when the string names no market we know.

    When several clusters match (e.g. 'remote (US) / hybrid Berlin') the lowest
    wins: suppression is the safe direction, because the cost of stripping a
    photo from an EU CV is cosmetic and the cost of leaving a DOB on a US CV is
    an automatic rejection at best.
    """
    text = unicodedata.normalize("NFKC", str(market or "")).lower()
    found = {c for alias, c in _CJK_CLUSTER.items() if alias in text}
    for seg in _market_segments(market):
        if seg in _CODE_CLUSTER:
            found.add(_CODE_CLUSTER[seg])
        words = seg.split()
        for n in range(_MAX_NAME_WORDS, 0, -1):
            for i in range(len(words) - n + 1):
                phrase = " ".join(words[i:i + n])
                if phrase in _NAME_CLUSTER:
                    found.add(_NAME_CLUSTER[phrase])
    return min(found) if found else None


def protected_fields(profile):
    """Names of the protected personal-data fields actually present."""
    out = []
    personal = (profile.get("contact") or {}).get("personal") or {}
    if isinstance(personal, dict):
        out += [f"contact.personal.{k}" for k, v in personal.items()
                if v not in (None, "")]
    if (profile.get("meta") or {}).get("photo"):
        out.append(_PHOTO_FIELD)
    return out


# One warning per (profile object, market), not per render call. An md + docx
# + pdf run — three invocations, or three direct calls from one process —
# renders from the SAME profile dict, and printing the identical warning three
# times is how a warning gets trained away. (main() takes one --format per
# invocation: md, docx or pdf. There is no `all`.) The profile OBJECT is held
# rather than its id(): an id can be
# reused after garbage collection, and a silently-suppressed leak warning is
# exactly the failure this interlock exists to prevent.
_MARKET_WARNED = []


def reset_market_warnings():
    """Forget which profiles have already warned. main() calls this at the top
    of every CLI run so the guard is per-run, not per-process."""
    _MARKET_WARNED.clear()


def _warn_unknown_market(profile):
    """Loud when the market is unrecognised AND protected data is present.

    cv-craft.md claims a mis-tailored profile 'physically cannot leak protected
    data onto a US/UK CV'. It could, for five measured spellings. The matcher
    above closes those; this closes the class — an unrecognised market is not
    evidence that rendering a DOB is safe, and silence there is what made the
    original claim false.
    """
    market = (profile.get("meta") or {}).get("target_market")
    if resolve_cluster(market) is not None:
        return
    fields = protected_fields(profile)
    if not fields:
        return
    if any(p is profile and m == market for p, m in _MARKET_WARNED):
        return
    _MARKET_WARNED.append((profile, market))
    print(f"WARNING: meta.target_market {market!r} matches no known CV-convention "
          f"cluster, so the Cluster-1 personal-data interlock cannot fire. These "
          f"fields will render as-is: {', '.join(fields)}. If this is a "
          f"US/Canada/UK/Ireland/Australia/NZ target, set meta.target_market to a "
          f"recognised country name and re-render — protected personal data on "
          f"such a CV is a discrimination-law liability and a common auto-reject.",
          file=sys.stderr)


def _is_cluster1(profile):
    return resolve_cluster((profile.get("meta") or {}).get("target_market")) == 1


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
    _warn_unknown_market(profile)
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
    _warn_unknown_market(profile)
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


def _engine_cmd(engine, tex_path, out_dir):
    """argv to compile `tex_path` into `out_dir` with `engine`.

    Dispatch on the BASENAME, never on the whole string: find_latex_engine
    returns an absolute path when the engine is not on PATH (measured on this
    machine: '/opt/homebrew/bin/tectonic'), and `engine == "tectonic"` is False
    for it. That comparison shipped in render_letter.py and produced a
    pdflatex-shaped argv handed to tectonic — every letter PDF failed while
    cv.pdf built in the same run, with the whole test suite green.

    One helper, both renderers. Two call sites cannot drift if there is one.
    """
    engine, tex_path, out_dir = str(engine), str(tex_path), str(out_dir)
    if pathlib.Path(engine).stem == "tectonic":
        return [engine, tex_path, "--outdir", out_dir]
    return [engine, "-interaction=nonstopmode", "-output-directory", out_dir, tex_path]


_UNICODE_ENGINES = ("tectonic", "xelatex", "lualatex")


def _is_unicode_engine(engine):
    """True when `engine` reads its input as Unicode and wants `fontspec`.

    tectonic is XeTeX-based, so it belongs here with xelatex and lualatex; only
    pdflatex wants the 8-bit `inputenc`/`fontenc` preamble. `None` — no engine
    installed — resolves to True, because the `.tex` we leave behind in that case
    is the one `modes/apply.md` tells the user to compile after installing
    **tectonic**; handing them a pdfLaTeX preamble to compile with the engine we
    just recommended is how this went wrong in the first place.

    Dispatch on the BASENAME, for the same reason `_engine_cmd` does:
    find_latex_engine returns an absolute path when the engine is not on PATH.
    """
    if engine is None:
        return True
    return pathlib.Path(str(engine)).stem in _UNICODE_ENGINES


def _has_cjk(text):
    """True if text contains CJK / Hangul / Thai characters.

    Narrow on purpose, and NOT the test for "needs a Unicode font" — that is
    `_needs_unicode_font`. What this answers is the narrower question "does this
    document need the ``xeCJK`` package and an installed CJK font on top of a
    Unicode engine", which really is script-specific: xeCJK exists to fix CJK
    line-breaking and inter-script spacing, and pdflatex cannot typeset these
    scripts at any font. Do not reach for this function to decide anything about
    encodings or Latin fonts — see the comment on `_needs_unicode_font`.
    """
    return any("　" <= ch <= "鿿" or "가" <= ch <= "힣"
               or "฀" <= ch <= "๿" for ch in text)


def _needs_unicode_font(text):
    """True if text contains any character above U+00FF.

    A THRESHOLD, not a script list, and that distinction is the whole bug this
    function was added to close. `_has_cjk` used to be asked "does this need the
    Unicode/fontspec path?", and because it enumerates scripts — CJK, Hangul,
    Thai — everything in Latin Extended-A and beyond fell through to the 8-bit
    T1 path: `Łukasz Wójcik` compiled, exit 0, and reached the recruiter as
    `ukasz Wójcik`. That is Polish, Czech, Slovak, Croatian, Hungarian, Turkish,
    Romanian and Latvian names and employers, in exactly the nl/de/uk markets
    this skill is built for. Enumerating scripts is what produced it; the next
    script would produce it again, so the test is a boundary instead: U+00FF is
    where an 8-bit font's coverage stops being something you can assume.
    """
    return any(ord(ch) > 0xFF for ch in text)


def profile_has_cjk(profile):
    """Whether any rendered text in the profile is CJK/Hangul/Thai. Drives the
    xeCJK/CJK-font half of the preamble and the engine requirement. A flat string
    dump is enough — we only need to know whether such characters appear."""
    return _has_cjk(str(profile))


def profile_needs_unicode_font(profile):
    """Whether any rendered text in the profile sits above U+00FF."""
    return _needs_unicode_font(str(profile))


# The engine prints one of these per dropped glyph and still exits 0 — so this
# is a *warning* that destroys the artifact. Two dialects, both covered:
#   XeTeX/tectonic:  `Missing character: There is no Ł (U+0141) in font [lmroman10-regular]…`
#   pdfTeX/8-bit:    `Missing character: There is no Ł ("141) in font ec-lmr10!`
_MISSING_CHAR_RE = re.compile(
    r"Missing character: There is no (.+?) in font ([^\n!]*)")
# Measured: tectonic 0.16.9 writes the character itself as U+FFFD U+FFFD in its
# own log — `There is no �� ("141)` — so the character is already lost
# before this code sees it and only the codepoint is trustworthy. Read that, and
# rebuild the character from it, or the message names the dropped glyph as "??".
_CODEPOINT_RE = re.compile(r'\((?:U\+|")([0-9A-Fa-f]{2,6})\)')


def missing_characters(log):
    """Every distinct `Missing character` the engine reported, in order.

    The information was always there — `render_pdf` captured the engine output
    and threw it away, which is why a CV whose name had lost a letter reported
    success and printed "Wrote cv.pdf". Returns a list of
    "U+0141 'Ł' in font ec-lmbx12" strings.
    """
    seen, out = set(), []
    for described, font in _MISSING_CHAR_RE.findall(log or ""):
        m = _CODEPOINT_RE.search(described)
        if m:
            code = int(m.group(1), 16)
            try:
                what = f"U+{code:04X} {chr(code)!r}"
            except ValueError:
                what = f"U+{code:04X}"
        else:
            what = described.strip()
        item = f"{what} in font {font.strip().rstrip(':;')}"
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


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


def _font_chain(fonts, setter):
    """A nested `\\IfFontExistsTF` chain: the first font actually installed wins,
    and the innermost branch is empty, leaving the engine's own default.

    `\\IfFontExistsTF` is used rather than a bare `\\setmainfont`/`\\setCJKmainfont`
    because naming a font that is not installed is a FATAL fontspec error, not a
    fallback — measured under tectonic 0.16.9, `\\setmainfont{Latin Modern Roman}`
    halts with "The font ... cannot be found" even though Latin Modern is the very
    font the engine is about to use by default. A `.tex` is a deliverable that gets
    recompiled on other machines, so it must not name a font it cannot check for.

    One chain builder, two callers (main font and CJK font), for the reason
    `_engine_cmd` gives: two copies is two things to be wrong.
    """
    setup = "{}"
    for f in reversed(list(fonts)):
        setup = r"\IfFontExistsTF{%s}{\%s{%s}}{%s}" % (f, setter, f, setup)
    return setup


def _cjk_font_setup(meta):
    fonts = [str(meta["cjk_font"])] if meta.get("cjk_font") else []
    return _font_chain(fonts + _CJK_FONT_FALLBACKS, "setCJKmainfont")


def _main_font_setup(meta):
    """The Latin main-font chain for the fontspec path.

    Deliberately empty by default: fontspec's own default under a Unicode engine
    is Latin Modern Roman, which is the OpenType cut of the same typeface the
    pdfLaTeX path uses (ec-lmr10), so the PDF looks unchanged — and, measured,
    it covers Latin-1 and Latin Extended-A (Ł ą Š Ș all render). What it does not
    cover — Cyrillic, Greek — is now caught loudly by the `Missing character`
    scan in `render_pdf` rather than dropped, and `meta.main_font` is the answer
    the scan's message points at.
    """
    fonts = [str(meta["main_font"])] if meta.get("main_font") else []
    return _font_chain(fonts, "setmainfont")


def latex_preamble(engine=None, cjk=False, meta=None, margin="2cm"):
    """The documentclass + encoding/font lines, chosen by ENGINE, not by content.

    This is the fix for the defect that shipped a recruiter a CV missing letters
    out of the candidate's own name. The preamble has to match the engine that
    will compile it, because that is what decides how the bytes are read:

      * tectonic / xelatex / lualatex read the file as Unicode and hand each
        codepoint straight to the font, so they need **fontspec**. Given
        `inputenc`+`fontenc` instead they load an 8-bit T1 font, silently drop
        every glyph it lacks, print `Missing character`, and exit 0.
      * pdflatex needs **inputenc + fontenc**, and with them genuinely does
        handle Latin Extended-A (inputenc composes `Ś` as `\\'S`). Emitting
        fontspec for pdflatex would trade a silent glyph drop for a hard compile
        failure, which is why this is not decided by looking at the text.

    `find_latex_engine` prefers tectonic and `modes/apply.md` tells the user to
    install it, so the Unicode branch is the one taken on a normal machine — and
    it is also what an unknown engine (`None`) gets, since the `.tex` left behind
    when nothing is installed is meant to be compiled with tectonic later.

    One preamble builder, both renderers: render_letter.py had its own copy of
    the pdfLaTeX lines and therefore its own copy of this bug.
    """
    meta = meta or {}
    lines = [r"\documentclass[11pt,a4paper]{article}"]
    if _is_unicode_engine(engine):
        lines.append(r"\usepackage{fontspec}")
        main = _main_font_setup(meta)
        if main != "{}":
            lines.append(main)
        if cjk:
            lines += [r"\usepackage{xeCJK}", _cjk_font_setup(meta)]
    else:
        lines += [r"\usepackage[utf8]{inputenc}", r"\usepackage[T1]{fontenc}"]
    lines.append(r"\usepackage[margin=%s]{geometry}" % margin)
    return lines


# ── LaTeX renderer ────────────────────────────────────────────────────────────

def build_latex(profile, cjk=None, engine=None):
    """Assemble the LaTeX source.

    `engine` is the engine that will compile this file, and it selects the
    encoding/font half of the preamble — see `latex_preamble` for why that has to
    be an engine decision and not a content one. `None` means "unknown", which
    resolves to the Unicode/fontspec preamble because tectonic is what
    `find_latex_engine` prefers and what `modes/apply.md` tells the user to
    install. `render_pdf` always passes the engine it actually resolved.

    `cjk` adds xeCJK and a system CJK font on top: that part IS content-driven,
    because xeCJK exists for CJK line-breaking and needs a CJK font installed.
    When `cjk` is None we auto-detect from the profile content.
    """
    _warn_unknown_market(profile)
    e = latex_escape
    # Escape headings for LaTeX up front: section labels can legitimately contain
    # LaTeX-special characters — the regulated-profession recipes use headers like
    # "Licenses & Certifications" and "Board & Advisory", and a raw "&" is a fatal
    # alignment-tab error. (Markdown/docx use the unescaped headings.)
    h = {k: e(v) for k, v in headings(profile).items()}
    meta = profile.get("meta", {}) or {}
    if cjk is None:
        cjk = profile_has_cjk(profile)
    preamble = latex_preamble(engine=engine, cjk=cjk, meta=meta, margin="2cm")
    parts = preamble + [
        r"\usepackage{enumitem}",
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

# Why a PDF was not produced.
NO_ENGINE, UNSUPPORTED_SCRIPT, COMPILE_FAILED, MISSING_CHARACTERS = (
    "NO_ENGINE", "UNSUPPORTED_SCRIPT", "COMPILE_FAILED", "MISSING_CHARACTERS")

# The first two are limitations of the machine or the template that modes/apply.md
# documents and expects the run to continue past on .md/.docx, so they keep exit 0.
# The other two mean a machine that CAN build PDFs did not build a correct one —
# exiting 0 on that is how the CV with the missing letters got delivered.
TOLERATED_PDF_FAILURES = (NO_ENGINE, UNSUPPORTED_SCRIPT)


def pdf_failure_is_tolerated(reasons):
    return bool(reasons) and all(r in TOLERATED_PDF_FAILURES for r in reasons)


def _note(reasons, reason):
    if reasons is not None:
        reasons.append(reason)
    return False


def compile_latex(engine, tex_path, out_path, reasons=None):
    """Run `engine` on `tex_path` and land the result at `out_path`.

    Returns True only if a PDF was produced AND every glyph in it survived. One
    compile helper, both renderers — the same reason `_engine_cmd` is shared.
    `reasons`, if given, collects the failure token (see above) for a caller that
    needs to pick an exit code.

    The `Missing character` scan is the point of this function. The engine prints
    one such warning per dropped glyph and still exits 0, and the old code ran
    `subprocess.run(..., capture_output=True)` and discarded the output — so a CV
    whose name had lost a letter printed "Wrote cv.pdf" and passed every gate.
    A PDF with dropped glyphs is a WRONG artifact, not a degraded one: the
    recruiter cannot tell it is wrong, and the candidate cannot tell either
    because cv.md is intact. So the file is deleted rather than left to be sent,
    and the `.tex` (always a deliverable here) stays behind.
    """
    tex_path, out_path = pathlib.Path(tex_path), pathlib.Path(out_path)
    cmd = _engine_cmd(engine, tex_path, out_path.parent)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    except (OSError, subprocess.CalledProcessError):
        # OSError is the real one: find_latex_engine can return a path from
        # _ENGINE_DIRS that turns out not to be executable. CalledProcessError
        # cannot come from this call (there is no check=True — the output is
        # needed on the failure path too, and check=True would throw it away),
        # but it is caught so a caller that stubs subprocess.run the old way
        # still degrades instead of crashing.
        proc = None
    if proc is None or getattr(proc, "returncode", 1) != 0:
        log = "" if proc is None else _engine_log(proc)
        print(f"WARNING: LaTeX compile failed. PDF could not be produced. "
              f"LaTeX source is at: {tex_path}", file=sys.stderr)
        for line in log.strip().splitlines()[-15:]:
            print(f"  | {line}", file=sys.stderr)
        return _note(reasons, COMPILE_FAILED)

    # If the engine wrote the PDF next to the .tex but the caller requested a
    # different name, move it into place.
    produced = tex_path.with_suffix(".pdf")
    if not out_path.exists() and produced.exists():
        produced.replace(out_path)

    dropped = missing_characters(_engine_log(proc))
    if dropped:
        for p in (out_path, produced):
            if p.exists():
                p.unlink()
        print(f"ERROR: {len(dropped)} character(s) could not be typeset and were "
              f"DROPPED from the PDF — the engine reported this and exited 0, so "
              f"the file would have looked fine while a recruiter read a name with "
              f"letters missing. No PDF was written. The LaTeX source is at "
              f"{tex_path}.", file=sys.stderr)
        for item in dropped[:20]:
            print(f"  missing: {item}", file=sys.stderr)
        if len(dropped) > 20:
            print(f"  … and {len(dropped) - 20} more", file=sys.stderr)
        print("Fix it by pointing the renderer at a font that covers these "
              "characters: set `meta.main_font` (Latin) or `meta.cjk_font` (CJK) "
              "in the profile to a font installed on this machine. Markdown and "
              ".docx are unaffected.", file=sys.stderr)
        return _note(reasons, MISSING_CHARACTERS)
    return True


def _engine_log(proc):
    """stdout + stderr of a finished engine run, as one string."""
    return "".join(str(getattr(proc, s, "") or "") for s in ("stdout", "stderr"))


def render_pdf(profile, out_path, reasons=None):
    """Build PDF via LaTeX. Always writes the `.tex` next to out_path (it is a
    deliverable in its own right, not just a failure breadcrumb). Returns True
    on success, False if no engine / compile failed / glyphs were dropped;
    `reasons`, if given, collects which of the three it was."""
    out_path = pathlib.Path(out_path)
    tex_path = out_path.with_suffix(".tex")
    cjk = profile_has_cjk(profile)

    # Resolve the engine BEFORE building the source: the preamble has to match
    # the engine that will compile it, and getting that pairing wrong is what
    # dropped Latin Extended-A out of every PDF this renderer produced.
    engine = find_latex_engine(cjk=cjk)
    tex = build_latex(profile, cjk=cjk, engine=engine)
    tex_path.write_text(tex, encoding="utf-8")

    if engine is None:
        if cjk:
            print("WARNING: no Unicode LaTeX engine found for this CJK CV. "
                  "A CJK PDF needs XeLaTeX (xelatex) or tectonic plus an "
                  "installed CJK font; pdflatex cannot do it. Markdown and "
                  f".docx still render correctly. Wrote the XeLaTeX source to "
                  f"{tex_path} — compile it with `xelatex` once an engine and a "
                  "CJK font are available.", file=sys.stderr)
        elif profile_needs_unicode_font(profile):
            print("WARNING: no LaTeX engine (tectonic/pdflatex) found, and this "
                  "CV contains characters above U+00FF (accented or non-Latin "
                  f"letters). Wrote the XeLaTeX source to {tex_path}: compile it "
                  "with `tectonic` (or xelatex/lualatex), NOT pdflatex — the "
                  "source uses fontspec so those characters survive.",
                  file=sys.stderr)
        else:
            print("WARNING: no LaTeX engine (tectonic/pdflatex) found. "
                  f"Wrote {tex_path}; install tectonic to produce a PDF.",
                  file=sys.stderr)
        return _note(reasons, NO_ENGINE)

    return compile_latex(engine, tex_path, out_path, reasons=reasons)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv=None):
    reset_market_warnings()
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
        reasons = []
        ok = render_pdf(profile, out, reasons=reasons)
        tex = out.with_suffix(".tex")
        if ok:
            # The .tex is delivered alongside every PDF, by design.
            print(f"Wrote {out} (LaTeX source alongside it: {tex})")
            return 0
        # Deliberately does NOT name a cause: render_pdf already printed the
        # specific one (no engine / compile failed / glyphs dropped) and this
        # line used to assert "no LaTeX engine found" for all three, which told
        # a user whose glyphs had just been dropped to install an engine they
        # already had.
        print(f"PDF could not be built — see the warning above. "
              f"LaTeX source written to: {tex}", file=sys.stderr)
        return 0 if pdf_failure_is_tolerated(reasons) else 1
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
