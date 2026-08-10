#!/usr/bin/env python3
"""Gate: the mechanically decidable half of the CV quality pass.

Nothing downstream scores voice — the ATS judge is a literal text matcher, the
recruiter judge scores readability not phrasing — so a grammatical,
keyword-complete, utterly templated CV passes all three judges and loses at the
real human recruiter, outside every loop this skill can observe. What a program
can decide goes here; dimensions 3 and 4 of the AI-uniformity check (voice,
specificity) cannot be decided by a program and stay inline in SKILL.md.

Exit 0 = clean. Exit 1 = findings. Exit 2 = no cv.md.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import journal

GATE = "lint_cv"

# Multi-word clichés are unambiguous. "leveraged" is not: a finance CV
# legitimately says "leveraged buyout", so that one collocation is carved out
# rather than teaching the reader to ignore the whole CLICHE class.
CLICHES = [
    ("results-driven", re.compile(r"\bresults[- ]driven\b", re.I)),
    ("proven track record", re.compile(r"\bproven track record\b", re.I)),
    ("synergy", re.compile(r"\bsynerg(y|ies|istic)\b", re.I)),
    ("leveraged", re.compile(r"\bleverag(e|ed|es|ing)\b(?!\s+buyout)", re.I)),
    ("excellent communicator", re.compile(r"\bexcellent communicator\b", re.I)),
    ("team player", re.compile(r"\bteam player\b", re.I)),
    ("passionate about technology", re.compile(r"\bpassionate about technology\b", re.I)),
    ("references available on request",
     re.compile(r"\breferences available (up)?on request\b", re.I)),
]
WEAK_OPENERS = ("responsible for", "worked on", "helped with", "assisted in",
                "was involved in")
# ~120 characters is one rendered line at CV widths; two is the stated ceiling.
MAX_BULLET_CHARS = 240
# Two bullets sharing an opening verb is variation; three is a template.
REPEAT_VERB_THRESHOLD = 3

_BULLET_RE = re.compile(r"^\s*[-*]\s+(?P<text>.+?)\s*$")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")


def findings_for(text: str, name: str = "cv.md") -> list:
    out, openers = [], {}
    for n, line in enumerate(text.split("\n"), 1):
        m = _BULLET_RE.match(line)
        if not m:
            continue
        body = m.group("text")
        hits = [label for label, rx in CLICHES if rx.search(body)]
        if hits:
            out.append(f"CLICHE: {name}:{n} contains {', '.join(repr(h) for h in hits)} "
                       f"— say the specific thing instead")
        low = body.lower()
        for opener in WEAK_OPENERS:
            if low.startswith(opener):
                out.append(f"WEAK_OPENER: {name}:{n} opens with "
                           f"{body[:len(opener)]!r} — open with an action verb and "
                           f"the result")
                break
        if len(body) > MAX_BULLET_CHARS:
            out.append(f"LONG_BULLET: {name}:{n} is {len(body)} characters "
                       f"(limit {MAX_BULLET_CHARS} ≈ two rendered lines) — it is "
                       f"either two bullets or it is padded")
        first = _WORD_RE.match(body)
        if first and len(first.group(0)) >= 4:
            openers.setdefault(first.group(0).lower(), []).append(n)
    for verb, lines in sorted(openers.items()):
        if len(lines) >= REPEAT_VERB_THRESHOLD:
            out.append(f"REPEATED_VERB: {verb!r} opens {len(lines)} bullets (lines "
                       f"{', '.join(str(x) for x in lines)}) — vary the verb; "
                       f"repetition is the first thing that reads as generated")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--cv", default=None, help="default: <workspace>/cv.md")
    args = ap.parse_args(argv)
    ws = pathlib.Path(args.workspace)
    if not ws.is_dir():
        # journal.receipt() would mkdir it, and a gate that creates the
        # workspace it is auditing has manufactured its own evidence.
        print(f"cannot run {GATE}: workspace {ws} does not exist", file=sys.stderr)
        return 2
    path = pathlib.Path(args.cv) if args.cv else ws / "cv.md"
    if not path.exists():
        journal.receipt(ws, GATE, {}, "could_not_run", [f"MISSING_INPUT: {path}"])
        print(f"cannot run {GATE}: {path} does not exist", file=sys.stderr)
        return 2
    findings = findings_for(path.read_text(encoding="utf-8"), path.name)
    for f in findings:
        print(f)
    journal.receipt(ws, GATE, {path.name: journal.sha256_file(path)},
                    "fail" if findings else "pass", findings)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
