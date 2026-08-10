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

# Keep ASCII alphanumerics and CJK/kana/hangul; everything else becomes a
# separator. Dropping CJK would turn a Chinese employer name into an empty
# slug and collapse two different companies onto the same directory.
_KEEP = re.compile(
    r"[^0-9a-z"
    r"぀-ヿ"      # kana
    r"㐀-䶿"      # CJK ext A
    r"一-鿿"      # CJK unified
    r"가-힯"      # hangul
    r"]+"
)
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def slugify(text: str) -> str:
    s = unicodedata.normalize("NFKC", str(text or "")).lower()
    return _KEEP.sub("-", s).strip("-")


def profile_dir(name: str) -> pathlib.Path:
    return PROFILES_ROOT / slugify(name)


def master_profile(name: str) -> pathlib.Path:
    return profile_dir(name) / "profile.yaml"


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
