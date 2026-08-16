#!/usr/bin/env python3
"""Gate for the interview mode.

Usage:
    python3 scripts/check_mock.py --workspace <application dir> --round <n>
                                  [--answer-bank <path>] [--today YYYY-MM-DD]

exit 0 — the round holds up.
exit 1 — findings printed to stdout, one per line, each with a stable UPPERCASE code.
exit 2 — could not run (a required input is missing, or a cross-plan module is absent);
         message to stderr. Never a silent skip: a check that did not run must not look
         like a check that passed.

Every exit path appends exactly one receipt to <workspace>/journal.jsonl, with verdict
"pass", "fail" or "could_not_run". Two exceptions, both deliberate: if the workspace
directory does not exist there is nowhere to append to, so the gate prints to stderr and
exits 2 with no receipt (creating the directory would materialise a workspace on a typo);
and if the receipt write itself fails, the gate exits 2 with RECEIPT_WRITE_FAILED rather
than exiting 0 having recorded nothing, because a gate that leaves no receipt is
indistinguishable from a gate nobody ran.

Required *inputs* are the transcript and the assessment. Everything else this gate reads
(question-log.yaml, answer-bank.md, interview-brief.md, claims.yaml) is a required
*output* of the mode — its absence is the defect, so it is a finding, not an exit 2.
"""
from __future__ import annotations

import argparse
import datetime
import pathlib
import re
import sys


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import enter_mode
import journal
import mock_blocks as MB
import mock_vocab as V
import paths

GATE = "check_mock"
MODE = "interview"
_AUTO = object()


class ReceiptFailed(RuntimeError):
    """The receipt could not be written — the run has no evidence it happened."""


class InputMissing(RuntimeError):
    """A required input file is absent — the gate has nothing to check."""


class MissingDependency(RuntimeError):
    """A cross-plan module is absent — the gate cannot honestly claim to have run."""


# ----------------------------------------------------------------- transcript helpers

_Q_HEADING = re.compile(r"^##\s+(Q\d+)\b", re.M)


def transcript_refs(text: str) -> set:
    return set(_Q_HEADING.findall(text))


# ----------------------------------------------------------------- the layer-1.5 backstop

def check_mode_entry(workspace: pathlib.Path, skill_root: pathlib.Path) -> list:
    """modes/interview.md is loaded unconditionally on entering the mode, and the
    journal record is the only thing that reports it if it was not. Mirrors
    check_apply.py exactly — one mechanism, four modes."""
    entry = enter_mode.latest_mode_entry(workspace, MODE)
    mode_path = paths.mode_file(MODE, skill_root)
    if entry is None:
        return [
            f"NO_MODE_ENTRY: journal.jsonl has no mode_entry for {MODE} — "
            f"modes/{MODE}.md is loaded unconditionally on entering the mode; run "
            f"scripts/enter_mode.py --mode {MODE} and read it"
        ]
    if mode_path.exists() and entry.get("mode_file_sha256") != journal.sha256_file(mode_path):
        return [
            f"MODE_FILE_CHANGED: modes/{MODE}.md changed after this run entered the "
            "mode, so what was read is not what is on disk — re-enter the mode and "
            "re-read it"
        ]
    return []


# ----------------------------------------------------------------- assessment checks

def _check_headers(block, round_no: int, findings: list) -> None:
    label = block.kind
    raw = block.header.get("ROUND", "")
    if not raw.isdigit():
        findings.append(f"BAD_ROUND: {label}: ROUND: {raw!r} is not an integer")
    elif int(raw) != round_no:
        findings.append(
            f"ROUND_MISMATCH: {label}: ROUND: {raw}, but the gate was run with "
            f"--round {round_no} — one of the two is looking at the wrong round"
        )
    if block.kind != MB.ASSESSMENT:
        return
    round_type = block.header.get("ROUND-TYPE", "")
    if round_type not in V.ROUND_TYPES:
        findings.append(
            f"UNKNOWN_ROUND_TYPE: {round_type!r} is not one of "
            + " | ".join(V.ROUND_TYPES)
        )
    market = block.header.get("MARKET", "")
    if market not in V.MOCK_MARKET_KEYS:
        findings.append(
            f"UNKNOWN_MARKET: {market!r} is not one of "
            + " | ".join(V.MOCK_MARKET_KEYS)
        )
    if not block.header.get("FAMILY", "").strip():
        findings.append(
            "NO_FAMILY: the assessment block has an empty FAMILY line — the "
            "family-conditional tags cannot be checked without it"
        )


def _check_quote(record, label: str, transcript: str, refs: set, findings: list) -> None:
    what = record.fields.get("tag") or record.fields.get("dimension") or record.kind
    quote = record.fields.get("quote", "")
    if not MB.normalize_quote(quote):
        findings.append(
            f"NO_QUOTE: {label} line {record.line_no}: {record.kind} {what} has an "
            "empty quote= — no quote, no tag"
        )
    elif not MB.quote_is_in(quote, transcript):
        findings.append(
            f"QUOTE_NOT_IN_TRANSCRIPT: {label} line {record.line_no}: "
            f"{MB.normalize_quote(quote)[:70]!r} does not appear in the transcript"
        )
    ref = record.fields.get("ref", "")
    # `refs` empty means the transcript has no question headings at all; that is
    # reported once, by check_assessment, rather than N times here.
    if refs and ref not in refs:
        findings.append(
            f"UNKNOWN_REF: {label} line {record.line_no}: {ref!r} is not a question "
            "heading in the transcript"
        )


def _check_tag(record, block, findings: list) -> None:
    label = block.kind
    tag = record.fields["tag"]
    allowed = V.TRANSCRIPT_TAGS if label == MB.ASSESSMENT else V.PROVENANCE_TAGS
    if tag not in V.ALL_TAGS:
        findings.append(
            f"UNKNOWN_TAG: {label} line {record.line_no}: {tag!r} is not in the closed "
            "set — see references/interview-shapes.md"
        )
        return
    if tag not in allowed:
        findings.append(
            f"WRONG_PASS: {label} line {record.line_no}: {tag} may only be emitted by "
            + ("the provenance pass" if label == MB.ASSESSMENT else "the transcript pass")
            + " — that pass holds the inputs this tag is decided from"
        )
        return
    if label != MB.ASSESSMENT:
        return
    market = block.header.get("MARKET", "")
    family = block.header.get("FAMILY", "").strip().lower()
    markets = V.MARKET_CONDITIONAL.get(tag)
    if markets and market not in markets:
        findings.append(
            f"TAG_NOT_APPLICABLE: {label} line {record.line_no}: {tag} applies only in "
            f"market(s) {', '.join(markets)}, this round is MARKET: {market}"
        )
    families = V.FAMILY_CONDITIONAL.get(tag)
    if families and family not in families:
        findings.append(
            f"TAG_NOT_APPLICABLE: {label} line {record.line_no}: {tag} applies only to "
            f"family {', '.join(families)}, this round is FAMILY: {family}"
        )


def _check_band(record, label: str, findings: list) -> None:
    dimension = record.fields["dimension"]
    value = record.fields["value"]
    if dimension not in V.DIMENSIONS:
        findings.append(
            f"UNKNOWN_DIMENSION: {label} line {record.line_no}: {dimension!r} is not "
            "one of " + " | ".join(V.DIMENSIONS)
        )
    if value == V.NON_BAND_FLAG:
        findings.append(
            f"NOT_A_BAND: {label} line {record.line_no}: {V.NON_BAND_FLAG!r} is a flag, "
            "not a band — emit it as tag=CONTRADICTED from the provenance pass"
        )
    elif value not in V.BANDS:
        findings.append(
            f"UNKNOWN_BAND: {label} line {record.line_no}: {value!r} is not one of "
            + " | ".join(V.BANDS)
            + " (the bands are unnumbered on purpose)"
        )


def check_assessment(assessment_text: str, transcript_text: str, round_no: int):
    """Returns ({block kind: Block}, findings)."""
    findings: list = []
    blocks: dict = {}
    for kind in (MB.ASSESSMENT, MB.PROVENANCE):
        if kind not in assessment_text:
            findings.append(
                f"MISSING_BLOCK: {kind} — that assessment pass did not run, or its "
                "block was not copied into the file verbatim"
            )
            continue
        try:
            blocks[kind] = MB.parse_block(assessment_text, kind)
        except MB.BlockParseError as exc:
            findings.append(
                f"PARSE_FAIL: {exc} — the round is void; re-dispatch that pass rather "
                "than hand-editing its block"
            )
    refs = transcript_refs(transcript_text)
    if not refs and any(block.records for block in blocks.values()):
        # Without headings the ref= check has nothing to compare against and would
        # pass everything in silence. The headings are required by modes/interview.md,
        # so their absence is the defect — not a licence to skip the check.
        findings.append(
            "NO_QUESTION_HEADINGS: the transcript has no '## Q<n>' headings, so every "
            "ref= in the assessment is unverifiable — modes/interview.md §3 requires "
            "one heading per question"
        )
    for kind, block in blocks.items():
        _check_headers(block, round_no, findings)
        for record in block.records:
            if record.kind == "FINDING":
                _check_tag(record, block, findings)
                _check_quote(record, kind, transcript_text, refs, findings)
            elif record.kind == "BAND":
                _check_band(record, kind, findings)
                _check_quote(record, kind, transcript_text, refs, findings)
            elif record.kind == "COVERAGE":
                if record.fields["status"] not in V.COVERAGE_STATUS:
                    findings.append(
                        f"UNKNOWN_STATUS: {kind} line {record.line_no}: COVERAGE "
                        f"status {record.fields['status']!r} is not one of "
                        + " | ".join(V.COVERAGE_STATUS)
                    )
            elif record.kind == "SHAPE":
                if record.fields["status"] not in V.SHAPE_STATUS:
                    findings.append(
                        f"UNKNOWN_STATUS: {kind} line {record.line_no}: SHAPE status "
                        f"{record.fields['status']!r} is not one of "
                        + " | ".join(V.SHAPE_STATUS)
                    )
    return blocks, findings


# ----------------------------------------------------------------- question-log.yaml

def _parse_stamp(raw: str):
    """`opencli nowcoder detail` returns an ISO-8601 timestamp; accept a bare date too."""
    text = str(raw).strip().replace("Z", "")
    for cut in (len(text), 19, 10):
        try:
            return datetime.datetime.fromisoformat(text[:cut]).date()
        except ValueError:
            continue
    return None


def check_question_log(path: pathlib.Path, today: datetime.date) -> list:
    if not path.exists():
        return [
            f"NO_QUESTION_LOG: {path} is missing — modes/interview.md requires the log "
            "seeded before the round, and it is the only record of where a question came from"
        ]
    # A finding, not exit 2: the docstring's split holds — question-log.yaml is a
    # required OUTPUT of the mode, so anything wrong with it is the defect being
    # reported, not a reason the gate could not run.
    try:
        data = journal.load_yaml(path)
    except journal.YamlUnreadable as exc:
        return [f"QUESTION_LOG_UNPARSEABLE: {exc}"]

    findings: list = []
    posting_country = str(data.get("posting_country") or "").strip().upper()
    if not posting_country:
        findings.append(
            "NO_POSTING_COUNTRY: question-log.yaml must record posting_country: <ISO-2>. "
            "Without it the country rule cannot fire, and a same-name different-entity "
            "post looks exactly like a right one"
        )
    questions = data.get("questions") or []
    if not isinstance(questions, list) or not questions:
        findings.append(f"QUESTION_LOG_EMPTY: {path} has no questions: list")
        questions = []

    for entry in questions:
        if not isinstance(entry, dict):
            findings.append(f"QUESTION_LOG_UNPARSEABLE: {path}: a questions: row is not a mapping")
            continue
        qid = entry.get("id", "?")
        source = entry.get("source")
        if source not in V.QUESTION_SOURCES:
            findings.append(
                f"UNKNOWN_QUESTION_SOURCE: {qid}: {source!r} is not one of "
                + " | ".join(V.QUESTION_SOURCES)
            )
        if source != "scraped":
            continue
        if not str(entry.get("source_id") or "").strip():
            findings.append(
                f"NO_SOURCE_ID: {qid}: a scraped question needs the id that "
                "`opencli nowcoder detail <id>` was called with"
            )
        use = str(entry.get("use") or "").strip()
        if use not in ("shape", "question"):
            findings.append(f"UNKNOWN_USE: {qid}: use: must be 'shape' or 'question'")
        stamp = str(entry.get("source_time") or "").strip()
        if not stamp:
            findings.append(
                f"NO_SOURCE_TIME: {qid}: copy the `time` field from `detail` — a search "
                "row is elided and undated, and one result set held posts 3 days and "
                "9.5 months old"
            )
        else:
            when = _parse_stamp(stamp)
            if when is None:
                findings.append(f"BAD_SOURCE_TIME: {qid}: {stamp!r} is not an ISO-8601 timestamp")
            elif (today - when).days > V.SCRAPED_SPECIFIC_MAX_AGE_DAYS and use == "question":
                findings.append(
                    f"STALE_SPECIFIC: {qid}: {stamp} is {(today - when).days} days old — "
                    "it may set shape only, never be quoted as a specific question"
                )
        entity = str(entry.get("entity_country") or "").strip().upper()
        if not entity:
            findings.append(
                f"NO_ENTITY_COUNTRY: {qid}: record which country's entity the post "
                "describes; the company name matching is not evidence that the process does"
            )
        elif posting_country and entity != posting_country and not entry.get("country_named_in_post"):
            findings.append(
                f"WRONG_COUNTRY: {qid}: the source describes the {entity} entity and the "
                f"posting is {posting_country} — move it to rejected: with "
                "reason: wrong_country unless the post itself names the posting's country"
            )

    for entry in data.get("rejected") or []:
        if not isinstance(entry, dict):
            continue
        reason = str(entry.get("reason") or "")
        if reason not in V.REJECT_REASONS:
            findings.append(
                f"UNKNOWN_REJECT_REASON: {entry.get('id', '?')}: {reason!r} is not one of "
                + " | ".join(V.REJECT_REASONS)
            )
    return findings


# ----------------------------------------------------------------- answer-bank.md

# `[ \t]` throughout, never `\s`: `\s` matches a newline, so `^\s*-\s*source:\s*\S+`
# happily matches an EMPTY "- source:" line by borrowing the "-" from the next bullet.
# That is the exact defect this check exists to catch, passing itself.
_AB_HEADING = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.M)
_AB_SOURCE = re.compile(r"^[ \t]*-[ \t]*source:[ \t]*\S+", re.M)


def check_answer_bank(path: pathlib.Path) -> list:
    if not path.exists():
        return [
            f"NO_ANSWER_BANK: {path} is missing — the answer bank is the only artifact "
            "that compounds across applications, and modes/interview.md requires one "
            "entry per story banked this round (--answer-bank to point elsewhere)"
        ]
    text = path.read_text(encoding="utf-8")
    marks = list(_AB_HEADING.finditer(text))
    if not marks:
        return [f"NO_ANSWER_BANK_ENTRIES: {path} has no '## ' entries"]
    findings = []
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
        body = text[mark.end():end]
        if not _AB_SOURCE.search(body):
            findings.append(
                f"ANSWER_NO_SOURCE: answer-bank.md entry {mark.group(1)!r} has no "
                "'- source:' line — an entry whose fact cannot be traced is worse than "
                "no entry, because the candidate will say it out loud believing it was vetted"
            )
    return findings


# ----------------------------------------------------------------- banned vocabulary

def _default_scanner():
    """scripts/lint_no_prediction.py is Plan 2's. This is the ONLY adapter point —
    if its function is named differently there, change it here and nowhere else.

    Resolved with getattr, not attribute access: a rename in Plan 2 must produce a
    MissingDependency and exit 2, not an AttributeError traceback with no receipt and
    no stable exit code. Returning None IS the "could not run" signal.
    """
    try:
        import lint_no_prediction
    except ImportError:
        return None
    return getattr(lint_no_prediction, "scan_text", None)


def check_vocabulary(paths: list, scanner) -> list:
    if scanner is None:
        raise MissingDependency(
            "scripts/lint_no_prediction.py (Plan 2) is not importable — refusing to "
            "report a vocabulary check that did not run"
        )
    findings = []
    for path in paths:
        if path.exists():
            findings.extend(scanner(path.read_text(encoding="utf-8"), str(path)))
    return findings


# ----------------------------------------------------------------- write-backs

_WB_SECTION = "## Walk-back list"
_WB_HEADING = re.compile(r"^###\s+(WB-\d+)\s*(.*)$", re.M)
_CLAIM_FIELDS = ("term", "where", "source_kind", "source_ref", "session_date", "retracted")


def walkback_entries(brief_text: str) -> list:
    if _WB_SECTION not in brief_text:
        return []
    body = brief_text.split(_WB_SECTION, 1)[1]
    following = re.search(r"^##\s+", body, re.M)
    if following:
        body = body[:following.start()]
    marks = list(_WB_HEADING.finditer(body))
    entries = []
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(body)
        chunk = body[mark.end():end]
        entry = {"id": mark.group(1), "claim": mark.group(2).strip(" —-")}
        for field in ("quote", "softened", "defect", "transcript"):
            found = re.search(rf"^\s*-\s*{field}:\s*(.+)$", chunk, re.M)
            entry[field] = found.group(1).strip() if found else ""
        entries.append(entry)
    return entries


def check_walkback(blocks: dict, brief_path: pathlib.Path, claims_path: pathlib.Path,
                   transcript_name: str) -> list:
    records = [
        record
        for block in blocks.values()
        for record in block.records
        if record.kind == "FINDING"
    ]
    fired = [r for r in records if r.fields["tag"] in V.WALKBACK_TAGS]
    unsourced = [r for r in records if r.fields["tag"] == "UNSOURCED-FACT"]
    if not fired and not unsourced:
        return []

    brief_text = brief_path.read_text(encoding="utf-8") if brief_path.exists() else ""
    entries = walkback_entries(brief_text)

    findings = []
    if fired and _WB_SECTION not in brief_text:
        findings.append(
            "WALKBACK_MISSING: "
            + ", ".join(sorted({r.fields["tag"] for r in fired}))
            + f" fired, but {brief_path.name} has no '{_WB_SECTION}' section — a claim "
            "the candidate cannot defend under one follow-up is a tailoring error, not "
            "a rehearsal topic"
        )
    else:
        for record in fired:
            quote = record.fields["quote"]
            if not any(MB.quote_is_in(quote, e["quote"]) for e in entries):
                findings.append(
                    f"WALKBACK_NO_ENTRY: {record.fields['tag']} at "
                    f"{record.fields['ref']} has no '### WB-' entry quoting "
                    f"{MB.normalize_quote(quote)[:60]!r}"
                )

    for entry in entries:
        for field in ("quote", "softened", "defect"):
            if not entry[field]:
                findings.append(
                    f"WALKBACK_INCOMPLETE: {entry['id']} is missing its '- {field}:' line"
                )
        # Any of the four defect tags may land here: the three that *demand* the
        # section, plus an UNSOURCED-FACT the candidate could not stand behind, which
        # is walked back rather than promoted to claims.yaml.
        if entry["defect"] and entry["defect"] not in V.DEFECT_TAGS:
            findings.append(
                f"WALKBACK_BAD_DEFECT: {entry['id']}: defect: {entry['defect']!r} must "
                "be one of " + " | ".join(V.DEFECT_TAGS)
            )

    promoted = []
    if claims_path.exists():
        try:
            rows = journal.load_yaml(claims_path, expect=list)
        except journal.YamlUnreadable as exc:
            findings.append(f"CLAIMS_UNPARSEABLE: {exc}")
            rows = []
        for row in rows:
            if not isinstance(row, dict) or row.get("source_kind") != "session-answer":
                continue
            if transcript_name not in str(row.get("source_ref", "")):
                continue
            promoted.append(row)
            missing = [f for f in _CLAIM_FIELDS if f not in row]
            if missing:
                findings.append(
                    f"CLAIM_ROW_INCOMPLETE: the promotion row for "
                    f"{row.get('term', '?')!r} is missing {', '.join(missing)}"
                )

    for record in unsourced:
        quote = MB.normalize_quote(record.fields["quote"])
        walked = any(MB.quote_is_in(record.fields["quote"], e["quote"]) for e in entries)
        claimed = any(
            str(row.get("term", "")).strip()
            and MB.collapse_ws(str(row["term"])).lower() in quote.lower()
            for row in promoted
        )
        if not (walked or claimed):
            findings.append(
                f"UNRESOLVED_FACT: UNSOURCED-FACT at {record.fields['ref']} "
                f"({quote[:50]!r}) is neither promoted to claims.yaml "
                f"(source_kind: session-answer, source_ref naming {transcript_name}) nor "
                "walked back — ask the candidate where it came from before it enters the "
                "answer bank"
            )
    return findings


# ----------------------------------------------------------------- receipts

def _receipt(workspace: pathlib.Path, inputs: dict, verdict: str, findings: list) -> None:
    """Append exactly one receipt. Raises ReceiptFailed rather than warning.

    A warning on stderr followed by exit 0 is the worst available outcome: the caller
    reads a clean exit code, and journal.jsonl — the thing modes/interview.md §7 tells
    the model to quote — has no line for this run at all.
    """
    hashes = {}
    for label, path in inputs.items():
        if path.exists():
            hashes[label] = journal.sha256_file(path)
    try:
        journal.receipt(workspace, GATE, hashes, verdict, findings)
    except OSError as exc:
        raise ReceiptFailed(
            f"RECEIPT_WRITE_FAILED: could not append the {GATE} receipt to "
            f"{workspace}/journal.jsonl: {exc}"
        ) from exc


# ----------------------------------------------------------------- orchestration

def _answer_bank_default(workspace: pathlib.Path) -> pathlib.Path:
    """The profile-level answer bank for the profile that owns this workspace.

    paths.py owns the layout; this gate does not re-derive it. The fallback covers a
    --workspace that is not shaped like a workspace at all, which is a user error the
    answer-bank check should report as NO_ANSWER_BANK rather than crash on.
    """
    try:
        return paths.answer_bank_of(workspace)
    except ValueError:
        return workspace / paths.ANSWER_BANK_NAME


def _inputs(workspace: pathlib.Path, round_no: int, answer_bank: pathlib.Path) -> dict:
    return {
        f"mock/assessment-{round_no}.md": workspace / "mock" / f"assessment-{round_no}.md",
        f"mock/transcript-{round_no}.md": workspace / "mock" / f"transcript-{round_no}.md",
        "mock/question-log.yaml": workspace / "mock" / "question-log.yaml",
        "interview-brief.md": workspace / "interview-brief.md",
        "claims.yaml": workspace / "claims.yaml",
        "answer-bank.md": answer_bank,
    }


def _skill_root_default() -> pathlib.Path:
    # Ask paths.py rather than re-deriving `.parent.parent` here (R4). A
    # hand-derived root is correct until someone moves one file.
    return paths.SKILL_ROOT


def run(workspace, round_no: int, answer_bank=None, today=None, vocab_scanner=_AUTO,
        skill_root=None):
    workspace = pathlib.Path(workspace)
    answer_bank = pathlib.Path(answer_bank) if answer_bank else _answer_bank_default(workspace)
    skill_root = pathlib.Path(skill_root) if skill_root else _skill_root_default()
    today = today or datetime.date.today()
    scanner = _default_scanner() if vocab_scanner is _AUTO else vocab_scanner

    assessment_path = workspace / "mock" / f"assessment-{round_no}.md"
    transcript_path = workspace / "mock" / f"transcript-{round_no}.md"
    for path in (assessment_path, transcript_path):
        if not path.exists():
            raise InputMissing(f"{path} is missing — nothing to check")

    assessment_text = assessment_path.read_text(encoding="utf-8")
    transcript_text = transcript_path.read_text(encoding="utf-8")

    findings = check_mode_entry(workspace, skill_root)
    blocks, block_findings = check_assessment(assessment_text, transcript_text, round_no)
    findings += block_findings
    findings += check_question_log(workspace / "mock" / "question-log.yaml", today)
    findings += check_answer_bank(answer_bank)
    findings += check_vocabulary(
        [
            assessment_path,
            workspace / "mock" / "open-loops.md",
            workspace / "mock" / "cheatsheet.md",
        ],
        scanner,
    )
    findings += check_walkback(
        blocks,
        workspace / "interview-brief.md",
        workspace / "claims.yaml",
        f"transcript-{round_no}.md",
    )
    return findings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Gate for one mock-interview round.")
    parser.add_argument("--workspace", required=True, type=pathlib.Path)
    parser.add_argument("--round", required=True, type=int)
    parser.add_argument("--answer-bank", type=pathlib.Path, default=None)
    parser.add_argument("--skill-root", type=pathlib.Path, default=None)
    parser.add_argument(
        "--today",
        default=None,
        help="ISO date used for staleness arithmetic; defaults to the system date",
    )
    args = parser.parse_args(argv)

    # The one place a receipt is impossible: there is nothing to append to, and
    # creating the directory would materialise a workspace on a typo.
    if not args.workspace.is_dir():
        print(f"cannot run {GATE}: workspace {args.workspace} does not exist",
              file=sys.stderr)
        return 2

    today = datetime.date.fromisoformat(args.today) if args.today else datetime.date.today()
    answer_bank = args.answer_bank or _answer_bank_default(args.workspace)
    inputs = _inputs(args.workspace, args.round, answer_bank)

    try:
        findings = run(
            args.workspace,
            args.round,
            answer_bank=answer_bank,
            today=today,
            vocab_scanner=_AUTO,
            skill_root=args.skill_root,
        )
    except (InputMissing, MissingDependency) as exc:
        print(str(exc), file=sys.stderr)
        try:
            _receipt(args.workspace, inputs, "could_not_run", [str(exc)])
        except ReceiptFailed as fail:
            print(str(fail), file=sys.stderr)
        return 2

    verdict = "fail" if findings else "pass"
    try:
        _receipt(args.workspace, inputs, verdict, findings)
    except ReceiptFailed as fail:
        print(str(fail), file=sys.stderr)
        return 2
    for finding in findings:
        print(finding)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
