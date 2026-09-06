#!/usr/bin/env python3
"""Every filesystem location job-hunt uses, in one module.

The <company>-<role>-<YYYY-MM-DD> workspace shape is load-bearing: the
"resume an in-progress application" lookup finds a prior run by that shape, so
a mode that invents its own layout orphans the previous workspace and
re-interviews the user from scratch with no error anywhere. Changing
`workspace()` changes that behaviour for every mode at once — which is the
point of it living here rather than in four mode files.

These are pure path builders: nothing here touches the disk. A helper that
created directories would materialise an empty workspace on a typo, and the
resume lookup would then find a shell and offer to continue from it.
"""
from __future__ import annotations

import pathlib
import re
import unicodedata

PROFILES_ROOT = pathlib.Path.home() / ".claude" / "job-profiles"
# The repo root IS the skill. Every script that needs it asks here rather than
# writing `.parent.parent` again: a hand-derived root is correct until someone
# moves one file, and then it is wrong in a way that only shows up at runtime.
SKILL_ROOT = pathlib.Path(__file__).resolve().parent.parent

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Latin letters that no amount of decomposition reduces to an ASCII base. NFKD
# turns é into e+◌́ but leaves ß, ø, ł, đ and æ whole, so they are spelled out.
_LATIN_SPECIALS = str.maketrans({
    "ß": "ss", "ẞ": "ss", "ø": "o", "Ø": "o", "æ": "ae", "Æ": "ae",
    "œ": "oe", "Œ": "oe", "ł": "l", "Ł": "l", "đ": "d", "Đ": "d",
    "þ": "th", "Þ": "th", "ð": "d", "Ð": "d", "ı": "i", "ŧ": "t", "ħ": "h",
})


def _fold_latin(ch: str) -> str:
    """Strip diacritics from LATIN letters only, leaving every other script alone.

    Folding by script matters in both directions. `Müller` and `Möller` were
    both becoming `m-ller` -- two different employers sharing one workspace, so
    the resume lookup offers the wrong prior application, which is precisely the
    failure this module's docstring says it exists to prevent. And folding
    indiscriminately would decompose Thai and Devanagari vowel signs, which are
    letters there, not accents.
    """
    if not unicodedata.name(ch, "").startswith("LATIN"):
        return ch
    return "".join(c for c in unicodedata.normalize("NFKD", ch)
                   if not unicodedata.combining(c))


def _keepable(ch: str) -> bool:
    """Letters and digits of ANY script, plus the combining marks that spell
    words in Thai, Devanagari, Arabic and Hebrew.

    The old rule was an allowlist of four scripts, so a Cyrillic, Greek, Arabic,
    Thai or Devanagari employer slugged to the EMPTY STRING -- and an empty slug
    makes `profile_dir` return PROFILES_ROOT itself, i.e. the shared parent of
    every candidate's private data. `unicodedata.category` is the general rule
    the allowlist was approximating.
    """
    return ch.isalnum() or unicodedata.category(ch).startswith("M")


def slugify(text: str) -> str:
    """A filesystem-safe, script-preserving slug.

    Latin is transliterated down to ASCII so that `Société Générale` and
    `Societe Generale` are one directory; every other script is kept as written,
    because there is no transliteration of `阿里巴巴` or `Яндекс` that a human
    would recognise in a path.
    """
    s = unicodedata.normalize("NFKC", str(text or "")).translate(_LATIN_SPECIALS)
    s = "".join(_fold_latin(ch) for ch in s).casefold()
    out, pending = [], False
    for ch in s:
        if _keepable(ch):
            out.append(ch)
            pending = False
        elif out and not pending:
            out.append("-")
            pending = True
    return "".join(out).strip("-")


def profile_dir(name: str) -> pathlib.Path:
    """<PROFILES_ROOT>/<slug>. Refuses a name that slugs to nothing.

    Without this, `profile_dir("")` returns PROFILES_ROOT itself — the shared
    parent of every candidate's private data — and the caller then writes a
    master profile, an answer bank and every application into the root. Loud is
    the only safe direction: an empty slug is always a caller bug, never a real
    candidate.
    """
    slug = slugify(name)
    if not slug:
        raise ValueError(
            f"name {name!r} contains no letters or digits, so it has no profile "
            f"directory; PROFILES_ROOT is not a profile")
    return PROFILES_ROOT / slug


# One candidate, several CVs — one per language. A returning user who has an
# English CV and then supplies a Chinese one has TWO masters, not a replacement:
# a Chinese CV is a different document with different conventions, not a
# translation of the English one, and overwriting is silent data loss the user
# only discovers when they next need the file that is gone.
#
# The language lives in the FILE (`meta.language`), and the filename only mirrors
# it. `master_profiles` reads the file rather than trusting the name, because a
# name is a claim and the content is the fact.
_LANGUAGE_ALIASES = {
    "english": "en", "en": "en", "en-us": "en", "en-gb": "en", "英文": "en",
    "chinese": "zh", "zh": "zh", "zh-cn": "zh", "zh-hans": "zh", "mandarin": "zh",
    "中文": "zh", "简体中文": "zh", "汉语": "zh",
    "zh-tw": "zh-tw", "zh-hant": "zh-tw", "繁體中文": "zh-tw",
    "dutch": "nl", "nl": "nl", "nederlands": "nl",
    "german": "de", "de": "de", "deutsch": "de",
    "french": "fr", "fr": "fr", "français": "fr", "francais": "fr",
    "spanish": "es", "es": "es", "español": "es", "espanol": "es",
    "italian": "it", "it": "it", "italiano": "it",
    "japanese": "ja", "ja": "ja", "jp": "ja", "日本語": "ja",
    "korean": "ko", "ko": "ko", "kr": "ko", "한국어": "ko",
}


def normalise_language(language) -> str:
    """A language tag reduced to one stable key, or "" when there is none.

    Case, region subtags and the endonym all collapse to the same slot, so
    "English", "en-US" and "英文" cannot become three masters for one CV. An
    unknown language is slugified rather than rejected: this skill writes CVs in
    languages this table has not been taught, and refusing them would be worse
    than filing them under their own name.
    """
    raw = str(language or "").strip().lower()
    if not raw:
        return ""
    if raw in _LANGUAGE_ALIASES:
        return _LANGUAGE_ALIASES[raw]
    base = raw.split("-")[0].split("_")[0]
    if base in _LANGUAGE_ALIASES:
        return _LANGUAGE_ALIASES[base]
    return slugify(raw)


def master_profile(name: str, language=None) -> pathlib.Path:
    """The master for one language. No language means the unsuffixed slot.

    `profile.yaml` stays exactly where it was — every profile saved before this
    existed lives there, and moving it would break `check_claims`' fingerprint,
    apply mode's resume lookup and every path a user has already written down.
    A language-tagged master is `profile.<lang>.yaml` beside it.
    """
    key = normalise_language(language)
    if not key:
        return profile_dir(name) / "profile.yaml"
    return profile_dir(name) / f"profile.{key}.yaml"


def master_profiles(name: str) -> dict:
    """{language key: path} for every master on disk, language read from content.

    The filename is a mirror, not the source: a file called `profile.en.yaml`
    whose `meta.language` says `zh` is filed under `zh`, because the renderer,
    the heading tables and the letter salutations all key off `meta.language`
    and the filename reaches none of them.

    A master with no readable `meta.language` is filed under `""` — the
    unsuffixed slot's ordinary state for profiles written before languages were
    tracked. Unreadable YAML is skipped rather than raising: one corrupt file
    must not hide the others.
    """
    # Imported here, not at module scope: paths.py is imported by scripts that
    # never touch YAML, and journal.py imports nothing from paths.
    import journal

    out = {}
    directory = profile_dir(name)
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("profile*.yaml")):
        if ".bak" in path.name:
            continue
        try:
            loaded = journal.load_yaml(path)
        except journal.YamlUnreadable:
            continue
        out.setdefault(
            normalise_language((loaded.get("meta") or {}).get("language")), path)
    return out


def search_prefs(name: str) -> pathlib.Path:
    return profile_dir(name) / "search-preferences.yaml"


ANSWER_BANK_NAME = "answer-bank.md"


def answer_bank(name: str) -> pathlib.Path:
    return profile_dir(name) / ANSWER_BANK_NAME


def search_dir(name: str, slug: str) -> pathlib.Path:
    return profile_dir(name) / "searches" / slugify(slug)


def workspace(name: str, company: str, role: str, date: str) -> pathlib.Path:
    """<profile_dir>/applications/<company>-<role>-<YYYY-MM-DD>.

    `date` is validated rather than slugified: it is the only part of the name
    another run parses back out, and an unparseable one is a workspace nobody
    finds again.
    """
    if not _ISO_DATE.match(str(date)):
        raise ValueError(f"date must be YYYY-MM-DD, got {date!r}")
    for label, value in (("company", company), ("role", role)):
        if not slugify(value):
            raise ValueError(
                f"{label} {value!r} contains no letters or digits, so the "
                f"workspace name would collapse; two such runs would share one "
                f"directory and the resume lookup would offer the wrong one")
    stem = f"{slugify(company)}-{slugify(role)}-{date}"
    return profile_dir(name) / "applications" / stem


def profile_dir_of(workspace) -> pathlib.Path:
    """The profile directory that owns `workspace` — the inverse of workspace().

    Relative to the path given, not to PROFILES_ROOT, so it works on a copied
    workspace or a test fixture. Refuses anything that is not the documented shape
    rather than guessing: a wrong guess here silently writes the answer bank — the one
    artifact that compounds across applications — into the wrong profile.
    """
    workspace = pathlib.Path(workspace)
    if workspace.parent.name != "applications" or len(workspace.parents) < 2:
        raise ValueError(
            f"{workspace} is not a workspace: expected "
            "<profile_dir>/applications/<company>-<role>-<YYYY-MM-DD>"
        )
    return workspace.parents[1]


def answer_bank_of(workspace) -> pathlib.Path:
    """The profile-level answer bank for the profile that owns `workspace`."""
    return profile_dir_of(workspace) / ANSWER_BANK_NAME


def mode_file(mode: str, root=None) -> pathlib.Path:
    """<skill root>/modes/<mode>.md — the layer-1.5 file for a mode."""
    return (pathlib.Path(root) if root else SKILL_ROOT) / "modes" / f"{mode}.md"


def lossless_allowlist(root=None) -> pathlib.Path:
    return (pathlib.Path(root) if root else SKILL_ROOT) / "scripts" / \
        "lossless-allowlist.json"
