#!/usr/bin/env python3
"""Gate: the rendered PDF is as long as the market says it may be.

Nothing else in the pipeline measures the artifact that is actually submitted.
The three judges read `cv.md`; `render_cv.py` reports success on any compile that
returns 0; and `references/cv-craft.md:224-228` states a hard length table that no
program has ever checked. A three-page CV for a five-year candidate renders
perfectly, passes every existing gate, and is a common silent screen-out.

Exit 0 = within budget. Exit 1 = findings. Exit 2 = no PDF to measure.
"""
from __future__ import annotations

import argparse
import datetime
import pathlib
import re
import sys
import zlib

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import journal

GATE = "check_pages"
_PAGE = re.compile(rb"/Type\s*/Page(?![sA-Za-z])")
_PAGES_COUNT = re.compile(rb"/Type\s*/Pages\b[^>]{0,200}?/Count\s+(\d+)", re.S)
_YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
ACADEMIC = ("academic", "research")


def _haystack(data: bytes) -> bytes:
    """Raw bytes plus every inflated FlateDecode stream.

    Measured: tectonic writes PDF 1.5 with compressed object streams, so the page
    objects are not in the raw bytes at all — a plain `/Type /Page` scan reports
    0 pages for a perfectly good one-page CV, which would make this gate fire on
    every single run.
    """
    parts = [data]
    for m in re.finditer(rb"stream\r?\n", data):
        start = m.end()
        end = data.find(b"endstream", start)
        if end < 0:
            continue
        try:
            parts.append(zlib.decompress(data[start:end]))
        except zlib.error:
            pass
    return b"\n".join(parts)


def page_count(path):
    """Number of pages, or None when the file cannot be read as a PDF."""
    hay = _haystack(pathlib.Path(path).read_bytes())
    n = len(_PAGE.findall(hay))
    if n:
        return n
    counts = [int(c) for c in _PAGES_COUNT.findall(hay)]
    return max(counts) if counts else None


def years_of_experience(profile, today_year: int) -> int:
    years = []
    for ex in profile.get("experience") or []:
        if not isinstance(ex, dict):
            continue
        m = _YEAR.search(str(ex.get("start") or ""))
        if m:
            years.append(int(m.group(1)))
    return max(0, today_year - min(years)) if years else 0


def max_pages(profile, today_year: int):
    """The page budget, or None when there is none.

    cv-craft.md:224-228 — 0-2 years: 1 page; 3-7: 1-2; 8-15: 2; 15+: 2, "3 only if
    roles are very distinct and all relevant"; academic/research CVs: no limit.
    The 15+/3-page case is an explicit judgement call, so it is an explicit opt-in
    (`meta.max_pages: 3`) rather than a band the gate guesses at.
    """
    meta = profile.get("meta") or {}
    if str(meta.get("cv_type") or "").strip().lower() in ACADEMIC:
        return None
    override = meta.get("max_pages")
    if isinstance(override, int) and not isinstance(override, bool) and override > 0:
        return override
    return 1 if years_of_experience(profile, today_year) < 3 else 2


def findings_for(cv_pdf, profile, today_year: int, letter_pdf=None) -> list:
    out = []
    pages = page_count(cv_pdf)
    if pages is None:
        out.append(f"UNREADABLE_PDF: {pathlib.Path(cv_pdf).name} has no readable page "
                   f"tree — the compile reported success but produced a file no "
                   f"reader can open; re-render before sending it")
    else:
        budget = max_pages(profile, today_year)
        if budget is not None and pages > budget:
            out.append(f"CV_TOO_LONG: {pathlib.Path(cv_pdf).name} is {pages} pages; "
                       f"the length table in references/cv-craft.md allows {budget} "
                       f"for {years_of_experience(profile, today_year)} years of "
                       f"experience. Cut, or set meta.max_pages with a reason")
    if letter_pdf and pathlib.Path(letter_pdf).exists():
        lp = page_count(letter_pdf)
        if lp is None:
            out.append(f"UNREADABLE_PDF: {pathlib.Path(letter_pdf).name} has no "
                       f"readable page tree")
        elif lp > 1:
            out.append(f"LETTER_TOO_LONG: {pathlib.Path(letter_pdf).name} is {lp} "
                       f"pages; motivation-letter.md says one page, always")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--cv", default=None, help="default: <workspace>/cv.pdf")
    ap.add_argument("--letter", default=None, help="default: <workspace>/letter.pdf")
    ap.add_argument("--profile", default=None,
                    help="default: <workspace>/tailored-profile.yaml")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD; default: today")
    args = ap.parse_args(argv)

    ws = pathlib.Path(args.workspace)
    if not ws.is_dir():
        # journal.receipt() would mkdir it, and a gate that creates the
        # workspace it is auditing has manufactured its own evidence.
        print(f"cannot run {GATE}: workspace {ws} does not exist", file=sys.stderr)
        return 2
    cv = pathlib.Path(args.cv) if args.cv else ws / "cv.pdf"
    letter = pathlib.Path(args.letter) if args.letter else ws / "letter.pdf"
    prof = pathlib.Path(args.profile) if args.profile else ws / "tailored-profile.yaml"
    for p in (cv, prof):
        if not p.exists():
            journal.receipt(ws, GATE, {}, "could_not_run", [f"MISSING_INPUT: {p}"])
            print(f"cannot run {GATE}: {p} does not exist", file=sys.stderr)
            return 2

    today_year = int((args.today or
                      datetime.date.today().isoformat())[:4])
    profile = yaml.safe_load(prof.read_text(encoding="utf-8")) or {}
    findings = findings_for(cv, profile, today_year, letter)
    for f in findings:
        print(f)
    journal.receipt(ws, GATE, {cv.name: journal.sha256_file(cv)},
                    "fail" if findings else "pass", findings)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
