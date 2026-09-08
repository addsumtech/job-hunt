#!/usr/bin/env python3
"""Gate: a scored supporting statement stays inside its stated word limits.

`references/structured-applications.md:25` — "respect the limit exactly:
over-limit statements are cut or penalised", and ":52" makes the statement, not
the CV, the thing that gets scored. Nothing checked it: the three CV judges are
routed away from a structured application by design, so the one artifact that is
actually marked had no reader at all.

The limit is written into the criterion heading, in the employer's own number:

    ### Making Effective Decisions (250 words)
    ### Communicating and Influencing (max 250 words)

When the posting states no limit, say so once, at the top of the file:

    <!-- word-limits: none stated in the posting -->

That marker is required rather than optional because "the posting gave no limit"
and "nobody recorded the limit" are the same silence otherwise, and only one of
them is safe.

Exit 0 = clean. Exit 1 = findings. Exit 2 = no supporting statement to check.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import journal
import prose_tells

GATE = "check_word_limits"
NO_LIMIT_MARKER = re.compile(r"<!--\s*word-limits:\s*none stated", re.I)
_HEADING = re.compile(r"^###\s+(?P<title>.+?)\s*$", re.M)
# The unit and the "at most" cue in every language this skill writes CVs in.
# With `words?|字` only, `Motivation (max. 300 Wörter)`, `(maximaal 300 woorden)`,
# `(300 mots maximum)` and `(500자 이내)` all parsed as NO limit — and for a
# posting that is not `structured`, no limit means no finding at all, so a
# 600-word answer against a stated 300-word cap passed in silence.
_LIMIT = re.compile(
    r"\(?\s*(?:max\.?\s*|maximaal\s*|maximum\s*|hoechstens\s*|höchstens\s*|"
    r"bis zu\s*|tot\s*|jusqu'?à\s*|hasta\s*|fino a\s*|"
    r"word limit:?\s*|up to\s*)?"
    r"(?P<n>\d{2,4})\s*"
    r"(?:words?|woorden|w[oö]rter|mots|palabras|parole|字|자|文字)"
    r"\s*(?:or less|maximum|max\.?|ou moins|o menos|以内|이내|以下)?\s*\)?", re.I)
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def _words(text: str) -> int:
    """Latin words plus CJK characters — a criterion answered in Chinese or
    Japanese must be counted, not measured as one enormous word."""
    # Count each Han/kana/Hangul character, plus each remaining Latin word.
    # Splitting also preserves Latin words attached to CJK without whitespace.
    cjk = r"[㐀-鿿぀-ヿ가-힣ᄀ-ᇿ㄰-㆏]"
    return len(re.findall(cjk, text)) + len(_WORD.findall(re.sub(cjk, " ", text)))


def sections(text: str) -> list:
    """[(title, declared_limit|None, body_word_count, body)] for each `###` heading."""
    out, marks = [], list(_HEADING.finditer(text))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        title = m.group("title")
        lim = _LIMIT.search(title)
        body = text[m.end():end]
        out.append((title, int(lim.group("n")) if lim else None, _words(body), body))
    return out


def findings_for(text: str, posting: dict) -> list:
    out = []
    structured = str(posting.get("application_type") or "").strip().lower() == "structured"
    rows = sections(text)
    if not rows:
        if structured:
            out.append("NO_CRITERIA: application_type is 'structured' but the "
                       "supporting statement has no `### <criterion>` headings — the "
                       "form is scored criterion by criterion, so an unlabelled essay "
                       "cannot be marked against it")
        return out
    for title, limit, words, body in rows:
        # A criterion answer is 250 words of connected prose written to persuade a
        # marker — the same register as a motivation letter, and the one artifact
        # that is actually SCORED here, since the three CV judges are routed away
        # from a structured application by design. Until now the statement carrying
        # spearheaded, pivotal, "not just X — it is Y", three tricolons and a
        # "valuable asset" close exited 0 clean. Measured per criterion rather than
        # over the file, so a dense 250-word answer is not diluted by a sparse one
        # and the finding names which criterion to rewrite.
        out += prose_tells.vocabulary_findings(body, f"{title!r}")
        out += prose_tells.prose_findings(body, f"{title!r}")
        if words == 0:
            out.append(f"EMPTY_CRITERION: {title!r} has no body — an unaddressed "
                       f"Essential criterion is usually an auto-reject")
        elif limit is not None and words > limit:
            out.append(f"OVER_LIMIT: {title!r} is {words} words against its stated "
                       f"limit of {limit} — over-limit statements are cut or "
                       f"penalised, so the tail you wrote may simply not be read")
    if structured and not any(l is not None for _, l, _, _ in rows) \
            and not NO_LIMIT_MARKER.search(text):
        out.append("NO_LIMIT_DECLARED: no criterion heading carries a word limit and "
                   "the file does not say the posting stated none. Add the employer's "
                   "number to each heading, e.g. '### Making Effective Decisions "
                   "(250 words)', or record '<!-- word-limits: none stated in the "
                   "posting -->' — otherwise 'no limit given' and 'nobody checked' "
                   "look identical")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--statement", default=None,
                    help="default: <workspace>/supporting-statement.md")
    ap.add_argument("--posting", default=None, help="default: <workspace>/posting.yaml")
    args = ap.parse_args(argv)
    ws = pathlib.Path(args.workspace)
    if not ws.is_dir():
        # journal.receipt() would mkdir it, and a gate that creates the
        # workspace it is auditing has manufactured its own evidence.
        print(f"cannot run {GATE}: workspace {ws} does not exist", file=sys.stderr)
        return 2
    sp = pathlib.Path(args.statement) if args.statement else ws / "supporting-statement.md"
    pp = pathlib.Path(args.posting) if args.posting else ws / "posting.yaml"
    for p in (sp, pp):
        if not p.exists():
            journal.receipt(ws, GATE, {}, "could_not_run", [f"MISSING_INPUT: {p}"])
            print(f"cannot run {GATE}: {p} does not exist", file=sys.stderr)
            return 2
    try:
        posting = journal.load_yaml(pp)
    except journal.YamlUnreadable as exc:
        journal.receipt(ws, GATE, {}, "could_not_run", [exc.finding])
        print(f"cannot run {GATE}: {exc}", file=sys.stderr)
        return 2
    findings = findings_for(sp.read_text(encoding="utf-8"), posting)
    for f in findings:
        print(f)
    journal.receipt(ws, GATE, {sp.name: journal.sha256_file(sp)},
                    "fail" if findings else "pass", findings)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
