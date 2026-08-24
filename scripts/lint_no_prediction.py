#!/usr/bin/env python3
"""Ban invented numbers and prediction vocabulary from anything a reader sees.

There is no data behind "45-65% chance of an interview"; it is a made-up number that
reads with the authority of arithmetic. Collapsing strong / partial / gap into one
score needs a weight for a partial match, and any weight would be invented too. So the
conclusion is a word, the counts are printed with the evidence behind each row, and
this lint keeps the made-up numbers out.

Four things are masked before any scan, and every one of them was a live false
positive on output this skill's own files mandate:

* The verdict labels. 大概率被筛掉 -- the human-facing label for likely_screen_out --
  literally contains 概率. Without masking, this lint fires on the most common verdict
  the skill prints, and a gate that cries wolf on ordinary output is one people switch
  off. A bare 大概率 elsewhere still fires. The labels come from scripts/vocab.py and
  are never re-typed here: a hand-copied second spelling would silently un-mask the
  verdict it was copied from.
* URLs. https://www.gov.uk/2026/08/09/x matches the n/m score pattern and %20 matches
  the percent ban. A URL is an identifier, not a claim -- the same reason a citation's
  title is exempt from the digit ban in the market tables.
* The 30/60/90 planning horizon. modes/assess.md §10 REQUIRES a 30/60/90 table on
  exactly the two verdicts where the "what to do instead" half is the whole value, and
  _SCORE matches the 30/60 inside it. One token is masked; 8/11 still fires.
* The payload of a `quote=` field, inside a MOCK-*-V1 block only. An interview
  transcript is the one place in this skill where a number a HUMAN said out loud is the
  evidence, and "roughly 40% faster" is exactly the over-claim the provenance assessor
  is there to tag. Failing the file would force the transcript to be laundered, which
  deletes the finding and keeps the file. The assessor's own prose on the same line,
  and every line outside the block, is scanned as usual.

The one allowlist: where an employer publishes its own rubric, the skill may walk the
candidate through THAT scale, in the employer's wording, with the source named. Quoting
an employer's scale is reporting. Treating it as a conclusion is inventing.

Exit 2 still writes a receipt, verdict "could_not_run", unless the workspace directory
itself is absent -- there is nothing to append to.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import journal  # noqa: E402
import vocab  # noqa: E402

GATE = "lint_no_prediction"

# Derived, never re-typed. The zh labels and the banned-word list are two views of
# the same closed set -- 大概率被筛掉 contains 概率 -- so a second hand-written copy
# here would un-mask whichever label drifted. Longest first, so masking a short
# label can never leave the tail of a longer one behind.
VERDICT_LABELS = tuple(sorted(
    tuple(vocab.VERDICT_ZH.values()) + tuple(vocab.VERDICTS) + (vocab.REFUSAL,),
    key=len, reverse=True))

_URL = re.compile(r"https?://\S+")
# A planning horizon, not a score. modes/assess.md §10 mandates the table.
ROADMAP_HORIZON = re.compile(r"(?<![0-9])30\s*/\s*60\s*/\s*90(?![0-9])")
_MOCK_OPEN = re.compile(r"^\s*MOCK-[A-Z]+-V1\s*$")
_MOCK_CLOSE = re.compile(r"^\s*END-MOCK-[A-Z]+-V1\s*$")
_QUOTE_FIELD = re.compile(r"quote=")
# Fullwidth forms are the same claim in the same language. `％` (U+FF05) and `／`
# (U+FF0F) are what a Chinese IME produces by default, and `０-９` likewise — so
# the ASCII-only classes these replace left the ban unenforced in exactly the
# text it was most needed in.
#
# NOT solved by NFKC-normalising the line first, which is the obvious fix and the
# wrong one: `mask_exempt_spans` blanks URLs and verdict labels by replacing them
# with runs of spaces OF THE SAME LENGTH so the reported span still lines up with
# the original text. NFKC changes lengths (`％`→`%` is 1:1, but `㍑`→`リットル`
# is not), and a normalising pass would silently break that alignment. Widening
# the character classes keeps every offset exactly where it was.
_PERCENT = re.compile(r"[%％]")
_SCORE = re.compile(r"(?<![0-9０-９])[0-9０-９]+\s*[/／]\s*[0-9０-９]+(?![0-9０-９])")

# The Chinese half was four hand-listed words, so 「成功率」「入围率」「七成」 and
# 「百分之七十」 all shipped clean — and `--lang zh` is the DEFAULT
# (count_coverage.py:170), which made this the skill's primary output language.
#
# A bare `X率` would be wrong in the other direction: 效率, 利率, 增长率 and
# 采样率 are ordinary words on an engineer's CV. The character class is bounded
# to the words that describe getting the job, so it cannot reach them.
#
# 可能性 is deliberately ABSENT. The mandated disclaimer is
# 「本 skill 不给出面试或录用的可能性估计」 — banning the word would make the
# required text fail its own gate, which is the defect layer 1 already had once.
# Spelled out, not a character class. `[通过入围命中录取用成功面试中签]{1,3}率`
# matched any 1-3 of those characters before 率, so it fired inside ordinary
# business words the skill's own market cards use: 达成率 ("成率"), 交付率,
# 出勤率. A ban that fires on honest, mandated content is a ban that gets
# switched off. These are the words that describe GETTING THE JOB, and
# nothing else.
_ZH_RATE = ("概率|通过率|命中率|录取率|录用率|成功率|入围率|中签率|面试率|"
            "机率|機率|錄取率|錄用率|成功機會|勝算")
# 七成 = 70%. The lookahead keeps 成功/成长/成员/成果/成本/成熟/成为 out; those are
# the ordinary compounds a Chinese numeral can legitimately sit in front of.
_ZH_TENTHS = r"[一二三四五六七八九]成(?![功长员果本熟为立就分])"
_ZH_PERCENT_SPELLED = r"百分之[零一二三四五六七八九十百]+"

_WORDS = re.compile(
    r"\bchances?\b|\bprobabilit(?:y|ies)\b|\bodds\b|\blikelihood\b"
    r"|\blikely to be (?:hired|interviewed|shortlisted|rejected)\b"
    r"|\b(?:strong|weak) candidate\b|\bwould pass\b|\bno-hire\b"
    r"|\b\d+(?:\.\d+)?\s*(?:percent|per cent)\b"
    r"|\bout of (?:10|100)\b"
    # Forecasts that name no number. The ban is on PREDICTING the outcome, and a
    # verification pass found the numberless English forms sailing through while
    # their Chinese analogues fired — the gate enforced in one language only.
    r"|\bshoo-?in\b|\ba lock\b|\bin the bag\b"
    r"|(?:\b(?:will|would|should)\b|'ll|’ll)\s*(?:almost certainly\s+|certainly\s+|surely\s+|"
    r"probably\s+|likely\s+)?(?:get|land|receive|secure)\s+(?:an?\s+|the\s+)?"
    r"(?:interview|offer|job|role|position)\b"
    r"|\bexpect\s+(?:an?\s+|the\s+)?(?:interview|offer)\b"
    r"|\byou'?re? (?:a )?(?:strong|weak|clear|obvious) (?:fit|match|candidate)\b"
    # 確率 is the Japanese/traditional spelling of 概率.
    r"|確率"
    r"|" + _ZH_RATE + r"|" + _ZH_TENTHS + r"|" + _ZH_PERCENT_SPELLED,
    re.IGNORECASE)
_ATTRIBUTION = re.compile(r"^\s*>?\s*(?:—|--|-|Source:|来源[:：])\s+.*https?://\S+")

CHECKS = (("PERCENT", _PERCENT), ("SCORE_PATTERN", _SCORE), ("PREDICTION_WORD", _WORDS))


def mask_exempt_spans(line: str) -> str:
    """Blank out URLs, verdict labels and the roadmap horizon, preserving length so
    the reported span still lines up with the original text."""
    masked = _URL.sub(lambda m: " " * len(m.group(0)), line)
    masked = ROADMAP_HORIZON.sub(lambda m: " " * len(m.group(0)), masked)
    for label in VERDICT_LABELS:
        if label in masked:
            masked = masked.replace(label, " " * len(label))
    return masked


def mock_block_lines(lines: list[str]) -> set[int]:
    """0-based indices of lines inside a closed MOCK-*-V1 block.

    An unterminated block is NOT exempt. A block that never closes is a malformed
    artifact, and treating it as an exemption would make "type the opening line" a
    way to switch this lint off.
    """
    inside: set[int] = set()
    opened_at: int | None = None
    for index, line in enumerate(lines):
        if opened_at is None:
            if _MOCK_OPEN.match(line):
                opened_at = index
        elif _MOCK_CLOSE.match(line):
            inside.update(range(opened_at, index + 1))
            opened_at = None
    return inside


def mask_mock_quote(line: str) -> str:
    """Blank the payload of a `quote=` field, preserving length.

    `quote=` is last on the line and runs to its end, so everything after it is the
    candidate's own words. Only the payload is masked -- the tag, the ref and any
    prose before `quote=` are scanned exactly as before.
    """
    match = _QUOTE_FIELD.search(line)
    if not match:
        return line
    return line[:match.end()] + " " * len(line[match.end():])


def blockquote_allowlist(lines: list[str]) -> set[int]:
    exempt: set[int] = set()
    index = 0
    while index < len(lines):
        if not lines[index].lstrip().startswith(">"):
            index += 1
            continue
        start = index
        while index < len(lines) and lines[index].lstrip().startswith(">"):
            index += 1
        end = index - 1
        window = [lines[end]] + lines[end + 1:end + 3]
        if any(_ATTRIBUTION.match(candidate) for candidate in window):
            exempt.update(range(start, end + 1))
    return exempt


def scan_text(text: str, label: str) -> list[str]:
    lines = text.splitlines()
    exempt = blockquote_allowlist(lines)
    in_mock = mock_block_lines(lines)
    findings: list[str] = []
    for number, line in enumerate(lines):
        if number in exempt:
            continue
        masked = mask_exempt_spans(
            mask_mock_quote(line) if number in in_mock else line)
        for code, pattern in CHECKS:
            for match in pattern.finditer(masked):
                original = line[match.start():match.end()]
                findings.append(f"{code}: {label}:{number + 1}: {original!r} "
                                f"in {line.strip()!r}")
    return findings


def cannot_run(workspace: pathlib.Path, reason: str) -> int:
    """Exactly one receipt on the could-not-run path, then exit 2."""
    print(f"cannot run: {reason}", file=sys.stderr)
    if workspace.is_dir():
        journal.receipt(workspace, GATE, {}, "could_not_run", [f"NO_INPUT: {reason}"])
    return 2


def target_files(workspace: pathlib.Path) -> list[pathlib.Path]:
    found = []
    for relative in ("fit-assessment.md", "shortlist.md", "cheatsheet.md",
                     "mock/cheatsheet.md"):
        path = workspace / relative
        if path.exists():
            found.append(path)
    found += sorted((workspace / "mock").glob("assessment-*.md"))
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ban predictions and invented numbers.")
    parser.add_argument("--workspace", required=True, type=pathlib.Path)
    parser.add_argument("--files", nargs="*", type=pathlib.Path, default=None)
    args = parser.parse_args(argv)

    workspace = args.workspace
    if not workspace.is_dir():
        return cannot_run(workspace, f"workspace {workspace} does not exist")
    files = list(args.files) if args.files else target_files(workspace)
    if not files:
        return cannot_run(workspace,
                          f"no rendered file to scan under {workspace}")

    findings: list[str] = []
    hashes: dict[str, str] = {}
    for path in files:
        try:
            relative = str(path.relative_to(workspace))
        except ValueError:
            relative = path.name
        hashes[relative] = journal.sha256_file(path)
        findings += scan_text(path.read_text(encoding="utf-8"), relative)

    for finding in findings:
        print(finding)
    journal.receipt(workspace, GATE, hashes,
                    "fail" if findings else "pass", findings)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
