#!/usr/bin/env python3
"""Gate: the rendered PDF is as long as the market says it may be — and it still
says who the candidate is and where they worked.

Nothing else in the pipeline measures the artifact that is actually submitted.
The three judges read `cv.md`; `render_cv.py` reports success on any compile that
returns 0; and `references/cv-craft.md:224-228` states a hard length table that no
program has ever checked. A three-page CV for a five-year candidate renders
perfectly, passes every existing gate, and is a common silent screen-out.

The text-coverage half was added after a measured defect of the same shape: the
renderer emitted a pdfLaTeX preamble for a XeTeX engine, every character above
Latin-1 was dropped with an exit-0 warning, and `Łukasz Wójcik` reached recruiters
as `ukasz Wójcik`. `cv.md` was intact, so all three judges saw the right name. The
renderer now fails on those warnings, but this gate is the independent check on
the delivered bytes: a CV whose PDF does not contain the candidate's own name is
the one thing worth asserting mechanically.

Exit 0 = within budget and readable. Exit 1 = findings. Exit 2 = no PDF to measure.
"""
from __future__ import annotations

import argparse
import datetime
import pathlib
import re
import shutil
import subprocess
import sys
import unicodedata
import zlib

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import journal

GATE = "check_pages"
_PAGE = re.compile(rb"/Type\s*/Page(?![sA-Za-z])")
_PAGES_COUNT = re.compile(rb"/Type\s*/Pages\b[^>]{0,200}?/Count\s+(\d+)", re.S)
_YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
ACADEMIC = ("academic", "research")


def _streams(data: bytes) -> list:
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
    return parts


def _haystack(data: bytes) -> bytes:
    return b"\n".join(_streams(data))


def page_count(path):
    """Number of pages, or None when the file cannot be read as a PDF."""
    hay = _haystack(pathlib.Path(path).read_bytes())
    n = len(_PAGE.findall(hay))
    if n:
        return n
    counts = [int(c) for c in _PAGES_COUNT.findall(hay)]
    return max(counts) if counts else None


# ── PDF text extraction ───────────────────────────────────────────────────────
#
# Dependency-free on purpose: requirements.txt is PyYAML + python-docx, and a gate
# that only runs where poppler or pypdf happens to be installed is a gate that
# reports "clean" by being absent. `pdftotext` is used when it is there, but only
# as a rescue after the built-in reader — see `extract_text`.
#
# What does NOT work, measured: inflating the FlateDecode streams and reading the
# bytes. tectonic writes text as glyph indices into a subset font, so the content
# stream for "Łukasz" contains no letters at all. What works is the /ToUnicode
# CMap the same PDF carries to make itself copy-pasteable: it maps those indices
# back to Unicode. This reads every CMap in the file and decodes the text runs
# with each one in turn, rather than resolving which font each run belongs to —
# that resolution needs the page resource dictionary, which lives inside a
# compressed object stream. Decoding with the wrong CMap yields noise, and noise
# does not accidentally spell a candidate's name, so the union of the decodings is
# a sound thing to search: a needle found in any of them really is in the PDF.

_BFCHAR = re.compile(rb"beginbfchar(.*?)endbfchar", re.S)
_BFRANGE = re.compile(rb"beginbfrange(.*?)endbfrange", re.S)
_HEXTOK = re.compile(rb"<([0-9A-Fa-f\s]*)>")
_RANGE3 = re.compile(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>")
# A PDF string is either <hex> or (literal); both appear in real output — tectonic
# writes hex for its fontspec/Identity-H fonts and literals for 8-bit T1 fonts.
_PDFSTR = re.compile(rb"<([0-9A-Fa-f\s]+)>|\(((?:\\.|[^\\()])*)\)", re.S)
_ESCAPES = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f",
            b"(": b"(", b")": b")", b"\\": b"\\"}
_MAX_RANGE = 4096          # a bfrange spanning more than this is malformed input


def _utf16(hexdigits: bytes) -> str:
    clean = re.sub(rb"\s", b"", hexdigits)
    try:
        return bytes.fromhex(clean.decode("ascii")).decode("utf-16-be", "replace")
    except ValueError:
        return ""


def _tounicode_maps(blobs) -> list:
    """Every /ToUnicode CMap in the file, as {code: text} dicts."""
    maps = []
    for blob in blobs:
        if b"beginbfchar" not in blob and b"beginbfrange" not in blob:
            continue
        table: dict = {}
        for chunk in _BFCHAR.findall(blob):
            toks = _HEXTOK.findall(chunk)
            for i in range(0, len(toks) - 1, 2):
                src = re.sub(rb"\s", b"", toks[i])
                if src:
                    table[int(src, 16)] = _utf16(toks[i + 1])
        for chunk in _BFRANGE.findall(blob):
            for m in _RANGE3.finditer(chunk):
                lo, hi = int(m.group(1), 16), int(m.group(2), 16)
                base = _utf16(m.group(3))
                if not base or hi < lo or hi - lo > _MAX_RANGE:
                    continue
                for code in range(lo, hi + 1):
                    try:
                        table[code] = base[:-1] + chr(ord(base[-1]) + (code - lo))
                    except ValueError:
                        break      # ran past U+10FFFF; the rest of the range is junk
        if table:
            maps.append(table)
    return maps


def _unescape(raw: bytes) -> bytes:
    out, i = bytearray(), 0
    while i < len(raw):
        ch = raw[i:i + 1]
        if ch == b"\\" and i + 1 < len(raw):
            nxt = raw[i + 1:i + 2]
            if nxt in _ESCAPES:
                out += _ESCAPES[nxt]
                i += 2
                continue
            octal = re.match(rb"[0-7]{1,3}", raw[i + 1:i + 4])
            if octal:
                out.append(int(octal.group(0), 8) & 0xFF)
                i += 1 + len(octal.group(0))
                continue
            i += 2
            continue
        out += ch
        i += 1
    return bytes(out)


def _text_runs(blobs) -> list:
    """Every string literal from every content stream, in order."""
    runs = []
    for blob in blobs:
        if b"Tj" not in blob and b"TJ" not in blob:
            continue
        for m in _PDFSTR.finditer(blob):
            if m.group(1) is not None:
                hexdigits = re.sub(rb"\s", b"", m.group(1))
                if len(hexdigits) % 2:
                    hexdigits += b"0"
                runs.append(bytes.fromhex(hexdigits.decode("ascii")))
            else:
                runs.append(_unescape(m.group(2)))
    return runs


def _decode(run: bytes, table: dict, two_byte: bool) -> str:
    if two_byte:
        return "".join(table.get((run[i] << 8) | run[i + 1], "")
                       for i in range(0, len(run) - 1, 2))
    return "".join(table.get(b, "") for b in run)


def _pdftotext(path) -> str:
    """poppler's extractor, if this machine has it. Not a dependency, a rescue."""
    exe = shutil.which("pdftotext")
    if not exe:
        return ""
    try:
        proc = subprocess.run([exe, "-q", str(path), "-"], capture_output=True,
                              text=True, errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout if proc.returncode == 0 else ""


def extract_text(path) -> list:
    """Candidate readings of the PDF's text. Empty list = could not read it.

    Empty is NOT "the PDF has no text": the two are indistinguishable from here,
    which is exactly why the caller turns it into an UNVERIFIED finding instead of
    a pass. A gate that cannot run must not look like a gate that passed.
    """
    try:
        blobs = _streams(pathlib.Path(path).read_bytes())
    except OSError:
        return []
    runs = _text_runs(blobs)
    readings = []
    for table in _tounicode_maps(blobs):
        for two_byte in (True, False):
            text = "".join(_decode(run, table, two_byte) for run in runs)
            if text.strip():
                readings.append(text)
    if not readings:
        rescue = _pdftotext(path)
        if rescue.strip():
            readings.append(rescue)
    return readings


# Everything the typesetter is entitled to change between the YAML and the page.
# Whitespace, because word spacing in a PDF is usually a positioning move with no
# space glyph behind it. Hyphens and dashes, because LaTeX hyphenates across line
# breaks and render_cv rewrites "—" as "---". Quotes, because render_cv rewrites
# the curly ones as ASCII (`_LATEX_REPLACEMENTS`), so "Moody's" typed with U+2019
# is set with U+0027. NFKC on top, because "fi" is set as one ligature glyph and
# "…" as three periods.
#
# Deleting these cannot turn a missing name into a found one: the needles are
# whole names and employers, and "Zoë Nowak" does not fall out of noise because
# the apostrophes were dropped from both sides.
_IGNORED_IN_MATCH = re.compile(r"[\s­\-‐-―'\"‘’“”`´]+")


def _squash(text: str) -> str:
    return _IGNORED_IN_MATCH.sub("", unicodedata.normalize("NFKC", text))


def pdf_contains(readings, needle: str) -> bool:
    return any(_squash(needle) in _squash(text) for text in readings)


def text_findings(cv_pdf, profile) -> list:
    """The candidate's name and every employer must survive into the PDF."""
    name = str((profile.get("meta") or {}).get("name") or "").strip()
    orgs = [str((ex or {}).get("org") or "").strip()
            for ex in (profile.get("experience") or []) if isinstance(ex, dict)]
    wanted = [("meta.name", name)] + [("experience[].org", o) for o in orgs if o]
    wanted = [(where, what) for where, what in wanted if what]
    if not wanted:
        return []

    label = pathlib.Path(cv_pdf).name
    readings = extract_text(cv_pdf)
    if not readings:
        return [f"UNVERIFIED_PDF_TEXT: no text could be extracted from {label}, so "
                f"nothing here checked that the candidate's name and employers "
                f"actually appear in the file that gets sent. This is NOT a pass. "
                f"Open the PDF, confirm by eye, or install poppler "
                f"(`pdftotext`) and re-run"]
    out = []
    for where, what in wanted:
        if not pdf_contains(readings, what):
            out.append(
                f"TEXT_MISSING_FROM_PDF: {label} does not contain {where} "
                f"{what!r} — the compile reported success but the glyphs did not "
                f"survive into the delivered file (cv.md and cv.docx can look "
                f"perfect while this is true). Re-render; if it repeats, the font "
                f"does not cover these characters — set meta.main_font")
    return out


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
        # Only worth asking once the file is readable at all: an unreadable PDF
        # has already been reported and would produce a second, derivative finding.
        out += text_findings(cv_pdf, profile)
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
