#!/usr/bin/env python3
"""Whether a market-conventions table may ship.

These tables carry the one class of assertion in this skill with no source text behind
it, so they are written by a person, dated, provenance-kinded, and rendered verbatim.
Nothing here can check that an entry is TRUE. It checks the things a program can decide,
and every threshold below was calibrated against the forty source entries before it was
chosen -- a gate that cries wolf on the repo's own fixtures is a gate someone
eventually switches off.

references/market-conventions/README.md is this script's spec. If the two disagree, the
README is what a person reads before adding an entry, so fix the script.

EXPIRED_REVIEW_BY is a HARD finding here on purpose: this script is the CI lint, and CI
is where a passed review date is supposed to stop the build. It is NOT hard at runtime --
check_assessment.py re-prefixes it as WARN_ and requires a 「已过复核期」 banner instead,
because a date passing while the code did not change should not stop the skill working
(spec §10). The two behaviours are deliberate and live in two different scripts.

Exit 2 still writes a receipt, verdict "could_not_run", unless the workspace directory
itself is absent -- there is nothing to append to.
"""
from __future__ import annotations

import argparse
import datetime
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import journal  # noqa: E402
import paths  # noqa: E402
import vocab  # noqa: E402
import yaml  # noqa: E402

GATE = "check_conventions"

# Re-exported, not re-typed. Plan 4's mock vocabulary carries a superset with a
# sixth token; two modules in one flat scripts/ namespace exporting the same name
# with different contents is how a closed set silently stops being closed.
MARKET_KEYS = vocab.MARKET_KEYS

# The skill root comes from paths.py, which is the one module allowed to know it --
# no second .parents[n] walk. The conventions directory is built from it ONCE here,
# and check_assessment.py imports CONVENTIONS_DIR rather than rebuilding it: two
# copies of a path is two things to be wrong when the tree moves.
SKILL_ROOT = paths.SKILL_ROOT
CONVENTIONS_DIR = SKILL_ROOT / "references" / "market-conventions"

PROSE_FIELDS = ("text_en", "text_zh", "applies_when", "why")
SOURCE_PROSE_FIELDS = ("publisher", "note")
REQUIRED_FIELDS = ("id", "text_en", "text_zh", "applies_when", "added", "review_by",
                   "source", "why")

# Closed on purpose. These three names are the only handle a reader has on the rules
# they belong to; deleting the digits to satisfy the lint would leave sentences nobody
# can act on. A general "proper nouns are fine" rule would be a lint-dodge licence.
PROPER_NOUNS = ("Form I-983", "Form I-9", "H-1B", "I-983", "I-9")

PROTECTED_TRAITS = (
    r"\bage\b", r"\bnationality\b", r"\bnational origin\b", r"\bcitizens?(?:hip)?\b",
    r"\bgender\b", r"\bsex\b", r"\bethnicity\b", r"\brace\b", r"\breligion\b",
    r"\bdisabilit(?:y|ies)\b", r"\bmarital status\b", r"\bpregnan\w*",
    "年龄", "国籍", "性别", "民族", "种族", "宗教", "残疾", "婚姻状况", "怀孕",
)

# Measured across all forty source entries: len(zh)/len(en) runs 0.258-0.424, and the
# modal-marker delta runs -1..+3. These bounds sit outside the body of both. The
# comparison below is STRICT (> MODAL_DELTA, not >=): at >= 3 the warning fires on
# nl-weu-language-requirement-must-be-justified, an entry that ships, which is the
# cry-wolf failure this calibration exists to avoid.
RATIO_LOW, RATIO_HIGH = 0.20, 0.60
MODAL_DELTA = 3

_MODAL_EN = re.compile(
    r"\bmust\b|\bshall\b|\bmay not\b|\bcannot\b|\b(?:is|are) required to\b"
    r"|\b(?:is|are) obliged to\b|\b(?:is|are) barred\b|\b(?:is|are) prohibited\b"
    r"|\b(?:is|are) not (?:allowed|permitted)\b", re.IGNORECASE)
_MODAL_ZH = re.compile(r"必须|不得|应当|禁止|有义务|方可")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HTTPS = re.compile(r"^https://\S+$")
_ID = re.compile(r"^[a-z0-9-]+$")
_LATIN_TOKEN = re.compile(r"[A-Za-z]{6,}")
_CJK_TOKEN = re.compile(r"[一-鿿]{3,}")


def cannot_run(workspace: pathlib.Path, reason: str) -> int:
    """Exactly one receipt on the could-not-run path, then exit 2."""
    print(f"cannot run: {reason}", file=sys.stderr)
    if workspace.is_dir():
        journal.receipt(workspace, GATE, {}, "could_not_run", [f"NO_INPUT: {reason}"])
    return 2


def load_market_file(path: pathlib.Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def conventions_by_id(data: dict) -> dict[str, dict]:
    return {c.get("id"): c for c in (data.get("conventions") or []) if c.get("id")}


def _strip_exempt(text: str) -> str:
    for noun in PROPER_NOUNS:
        text = text.replace(noun, "")
    return text


def _tokens(text: str) -> set[str]:
    return ({m.group(0).lower() for m in _LATIN_TOKEN.finditer(text)}
            | {m.group(0) for m in _CJK_TOKEN.finditer(text)})


def _check_source(entry_id: str, source, findings: list[str]) -> None:
    if not isinstance(source, dict):
        findings.append(f"MISSING_FIELD: {entry_id}.source is absent or not a mapping")
        return
    kind = source.get("kind")
    if kind not in ("maintainer", "published"):
        findings.append(f"BAD_SOURCE_KIND: {entry_id}.source.kind is {kind!r}, "
                        f"not 'maintainer' or 'published'")
        return
    if kind == "maintainer" and not str(source.get("note") or "").strip():
        findings.append(f"MISSING_SOURCE_NOTE: {entry_id} is a maintainer entry with no "
                        f"note saying what the maintainer saw")
    citations = [source] if kind == "published" else []
    citations += list(source.get("also") or [])
    for index, citation in enumerate(citations):
        where = f"{entry_id}.source" if index == 0 else f"{entry_id}.source.also[{index-1}]"
        for field in ("publisher", "title"):
            if not str(citation.get(field) or "").strip():
                findings.append(f"MISSING_FIELD: {where}.{field} is empty")
        if not _HTTPS.match(str(citation.get("url") or "")):
            findings.append(f"BAD_SOURCE_URL: {where}.url is "
                            f"{citation.get('url')!r}, not an https URL")
        if not _ISO_DATE.match(str(citation.get("retrieved") or "")):
            findings.append(f"BAD_SOURCE_RETRIEVED: {where}.retrieved is "
                            f"{citation.get('retrieved')!r}, not YYYY-MM-DD")


def check_file(path: pathlib.Path, today: datetime.date) -> list[str]:
    data = load_market_file(path)
    findings: list[str] = []

    if data.get("market") not in MARKET_KEYS:
        findings.append(f"BAD_MARKET: {path.name} declares market "
                        f"{data.get('market')!r}, not one of {MARKET_KEYS}")

    seen: set[str] = set()
    for entry in data.get("conventions") or []:
        entry = entry or {}
        entry_id = str(entry.get("id") or "<no id>")
        if not _ID.match(entry_id):
            findings.append(f"BAD_ID: {entry_id!r} is not [a-z0-9-]+")
        if entry_id in seen:
            findings.append(f"DUPLICATE_ID: {entry_id} appears more than once")
        seen.add(entry_id)

        for field in REQUIRED_FIELDS:
            if field != "source" and not str(entry.get(field) or "").strip():
                findings.append(f"MISSING_FIELD: {entry_id}.{field} is empty")

        prose = {field: str(entry.get(field) or "") for field in PROSE_FIELDS}
        source = entry.get("source") if isinstance(entry.get("source"), dict) else {}
        for field in SOURCE_PROSE_FIELDS:
            if source.get(field):
                prose[f"source.{field}"] = str(source[field])
        for field, text in prose.items():
            scanned = _strip_exempt(text)
            if "%" in scanned:
                findings.append(f"PERCENT_IN_PROSE: {entry_id}.{field} states a "
                                f"percentage: {text.strip()[:80]!r}")
            digits = sorted(set(re.findall(r"[0-9]", scanned)))
            if digits:
                snippet = next((w for w in re.findall(r"\S*[0-9]\S*", scanned)), "")
                findings.append(f"DIGIT_IN_PROSE: {entry_id}.{field} states a number "
                                f"({snippet!r}) in: {text.strip()[:80]!r}")
            for pattern in PROTECTED_TRAITS:
                hit = re.search(pattern, text, re.IGNORECASE)
                if hit and not str(entry.get("protected_trait_note") or "").strip():
                    findings.append(
                        f"PROTECTED_TRAIT: {entry_id}.{field} names "
                        f"{hit.group(0)!r} with no protected_trait_note explaining why "
                        f"the fact cannot be stated without it")

        _check_source(entry_id, entry.get("source"), findings)

        for field in ("added", "review_by"):
            value = str(entry.get(field) or "")
            if not _ISO_DATE.match(value):
                findings.append(f"BAD_DATE: {entry_id}.{field} is {value!r}, "
                                f"not YYYY-MM-DD")
            elif field == "review_by" and datetime.date.fromisoformat(value) < today:
                findings.append(f"EXPIRED_REVIEW_BY: {entry_id} was due for review on "
                                f"{value}; re-check the source or re-date it")

        english, chinese = prose.get("text_en", ""), prose.get("text_zh", "")
        if english and chinese:
            ratio = len(chinese) / len(english)
            if ratio < RATIO_LOW or ratio > RATIO_HIGH:
                findings.append(
                    f"WARN_LENGTH_RATIO: {entry_id} zh/en length ratio is {ratio:.2f}, "
                    f"outside {RATIO_LOW}-{RATIO_HIGH}; one language may be saying "
                    f"more than the other")
            delta = len(_MODAL_ZH.findall(chinese)) - len(_MODAL_EN.findall(english))
            if abs(delta) > MODAL_DELTA:
                findings.append(
                    f"WARN_MODAL_ASYMMETRY: {entry_id} has {delta:+d} more obligation "
                    f"markers in zh than en; check that neither version strengthens a "
                    f"'usually' into a 'must'")

    known = conventions_by_id(data)
    for index, item in enumerate(data.get("unverified") or []):
        item = item or {}
        targets = item.get("disclaims") or []
        if not targets:
            findings.append(f"MISSING_UNVERIFIED_DISCLAIMS: unverified[{index}] does not "
                            f"name the entry or field it disclaims")
            continue
        note_tokens = _tokens(str(item.get("note") or ""))
        for target in targets:
            entry_id = str(target).split(".")[0]
            entry = known.get(entry_id)
            if entry is None:
                findings.append(f"UNVERIFIED_TARGET_UNKNOWN: unverified[{index}] names "
                                f"{target!r}, which is not an entry in {path.name}")
                continue
            shared = note_tokens & _tokens(
                f"{entry.get('text_en', '')} {entry.get('text_zh', '')}")
            if len(shared) >= 3:
                findings.append(
                    f"WARN_UNVERIFIED_OVERLAP: unverified[{index}] disclaims "
                    f"{target} yet shares {sorted(shared)} with its rendered text; an "
                    f"assertion the note disclaims must be REMOVED from the text, not "
                    f"footnoted — the reader never sees this note")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint the market-convention tables.")
    parser.add_argument("--workspace", required=True, type=pathlib.Path)
    parser.add_argument("--market-file", action="append", type=pathlib.Path, default=[])
    parser.add_argument("--all", action="store_true",
                        help="check every shipped table under references/market-conventions")
    parser.add_argument("--today", default=None, help="YYYY-MM-DD, for deterministic tests")
    args = parser.parse_args(argv)

    today = (datetime.date.fromisoformat(args.today) if args.today
             else datetime.date.today())
    if not args.workspace.is_dir():
        return cannot_run(args.workspace,
                          f"workspace {args.workspace} does not exist")
    files = list(args.market_file)
    if args.all:
        files += [CONVENTIONS_DIR / f"{key}.yaml" for key in MARKET_KEYS]
    if not files:
        return cannot_run(args.workspace, "pass --market-file or --all")
    for path in files:
        if not path.exists():
            return cannot_run(args.workspace, f"{path} not found")

    findings: list[str] = []
    hashes: dict[str, str] = {}
    for path in files:
        hashes[path.name] = journal.sha256_file(path)
        findings += check_file(path, today)

    for finding in findings:
        print(finding)
    hard = [f for f in findings if not f.startswith("WARN_")]
    journal.receipt(args.workspace, GATE, hashes,
                    "fail" if hard else "pass", findings)
    return 1 if hard else 0


if __name__ == "__main__":
    raise SystemExit(main())
