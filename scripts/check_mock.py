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
