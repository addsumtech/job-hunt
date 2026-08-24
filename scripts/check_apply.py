#!/usr/bin/env python3
"""Gate: apply mode may not claim success without evidence for each claim.

Composition, not new judgement. Each upstream gate already decided one thing;
this asserts that each of them actually ran, on this workspace, and passed —
because a skipped script produces no output and no output is exactly what a
clean run looks like.

Three rules make "actually ran" mean something, and each closes a way this gate
used to write `pass` over a run that had not been checked:

  * A `--record` receipt is SETUP, not a check. modes/apply.md runs check_claims
    and check_render_freshness with --record at mode entry and before dispatch;
    both store a baseline and verify nothing, and both say "baseline_recorded"
    so this gate can tell them from a verification pass. NOT_VERIFIED — never
    UPSTREAM_FAILED, because nothing failed.
  * Some gates are required only when their input is on disk. The trigger is a
    file, read by conditional_gates(), so "it did not apply" is never guesswork.
  * ANY gate whose latest receipt in this journal says `fail` blocks the package,
    named on either list or not. Enumerating gates does not keep up with the
    gates: check_pages and check_word_limits were both off the list, so either
    could run, print CV_TOO_LONG or OVER_LIMIT, write `verdict: fail`, and have
    this gate write its own `pass` three lines below it in the same file.

Two things it adds. First, the round must have PASSed or the run must record an
honest stop that is classified: **poorly built** (a fixable tailoring miss) or
**honest stretch** (as strong as it can truthfully be, and the candidate is
genuinely a notch off the role). Both outcomes emit the identical machine signal
— three verdicts, at least one REJECT — so nothing distinguishes them, and a
stretch candidate told "failed" abandons an application they should have sent.
Second, the mode-entry record: modes/apply.md is loaded unconditionally, and
this is what reports it if it was not.

Exit 0 = the package may be delivered. Exit 1 = findings. Exit 2 = no workspace —
and this is the one exit path in the skill that writes NO receipt, because there
is no journal to append to and a gate that created the workspace it was told does
not exist would manufacture the evidence directory it is checking.
"""
from __future__ import annotations

import argparse
import pathlib
import sys


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import enter_mode
import journal
import paths
import rounds
import vocab

GATE = "check_apply"
MODE = "apply"
# parse_verdicts is in this list for a reason that is easy to miss:
# judge-round-<n>.json is a plain JSON file, so without its receipt a
# hand-written `combined_verdict: PASS` passes this gate with no evidence the
# parser ever ran — the exact substitution parse_verdicts.py exists to prevent.
REQUIRED_GATES = ("check_personal_data", "check_claims", "check_render_freshness",
                  "parse_verdicts", "lint_cv")
# Required too, but only when the artifact they read is on disk — see
# conditional_gates(). Declared as a tuple as well because SKILL.md's self-check
# is pinned against BOTH lists: a heading that promises "check_apply requires all
# of these" over a gate it does not require converts "I skipped it" into
# "check_apply covered it", which is worse than no checklist line at all.
CONDITIONAL_GATES = ("check_letter", "check_pages", "check_word_limits")
CLASSIFICATIONS = ("poorly_built", "honest_stretch")
VERDICTS = vocab.VERDICTS
# What a gate receipt has to say for this composer to accept it. "recorded" is
# here for parse_verdicts, whose clean verdict on a cleanly-parsed round is
# "recorded" whatever the judges decided.
PASSING_VERDICTS = ("pass", "recorded")
# ...and what a `--record` step says. It is journalled — a skipped setup must not
# be silent either — but it stores a baseline and verifies nothing, so it is not
# evidence that the gate ever checked anything, which is the only question this
# composer asks. Both spellings were "recorded" until 2026-08, and that single
# token bought nothing and cost the whole composition guarantee: a workspace that
# ran only modes/apply.md's documented entry steps exited 0 here while check_claims
# run properly on it reported UNSOURCED fabrications, and re-running the entry step
# after a real failure — which a resume or a round 2 does — put a passing receipt
# on top of the failing one.
SETUP_VERDICTS = ("baseline_recorded",)


def _stale_inputs(ws: pathlib.Path, gate: str, receipt: dict) -> list:
    """Re-verify a passing receipt's `input_hashes` against the bytes on disk.

    journal.py's own docstring says a receipt is a claim about specific bytes.
    Eleven sites wrote `input_hashes`; nothing ever read one back. So a gate's
    pass kept vouching for the package after its input changed, and check_apply
    — the single gate that decides "this may be delivered" — composed purely on
    the verdict field.

    The reachable path is the ordinary actor-critic loop, not a hand edit.
    `check_claims` and `check_render_freshness` are protected by explicit
    re-run instructions in modes/apply.md; `check_personal_data` and `lint_cv`
    appear only in the one-shot pre-dispatch block, and nothing tells the run to
    re-run them after a round-2 edit. Measured on a documented round 2: a bullet
    rewrite introducing five clichés left check_apply at 0 while `lint_cv` on the
    same bytes exited 1.

    An empty `input_hashes` is not a finding: some gates record none, and a
    receipt that claims nothing about files cannot be stale.
    """
    findings = []
    for label, recorded in sorted((receipt.get("input_hashes") or {}).items()):
        # `ws / "/abs/path"` returns the ABSOLUTE path and `ws / "../x"` walks out
        # of the workspace, so a receipt could bind its proof to any file on the
        # machine and this loop would hash it and call the gate fresh. A receipt is
        # a claim about THIS workspace or it is not evidence.
        candidate = pathlib.Path(label)
        if candidate.is_absolute() or ".." in candidate.parts:
            findings.append(
                f"RECEIPT_INPUT_OUTSIDE_WORKSPACE: {gate} recorded {label!r}, which "
                f"is not inside the workspace — a gate's proof has to be about a "
                f"file in the package being delivered")
            continue
        path = ws / label
        if not path.exists():
            findings.append(
                f"RECEIPT_INPUT_MISSING: {gate} passed on {label}, which is no "
                f"longer in the workspace — the gate's pass is about a file that "
                f"is gone. Re-run {gate}")
            continue
        if journal.sha256_file(path) != recorded:
            findings.append(
                f"STALE_RECEIPT: {gate} passed on {label}@{str(recorded)[:12]} "
                f"but disk now holds {journal.sha256_file(path)[:12]} — the file "
                f"changed after the gate checked it, so that pass says nothing "
                f"about what would be delivered. Re-run {gate}")
    return findings


def _structured(ws: pathlib.Path):
    """True | False | None (absent) | "unreadable".

    Tri-state, because the two ways of answering "no" are not the same fact.
    Guessing "structured" from a file nobody could parse would demand a gate on a
    run with no supporting statement in sight — that reasoning still holds and is
    why this does not return True. But returning a plain False ALSO swallowed the
    finding: in the no-letter.yaml configuration, which is the normal shape of an
    NHS or Civil Service application, nothing else in apply mode reads
    posting.yaml, so one malformed character both removed the check_word_limits
    requirement and suppressed any report of it. The caller now says so out loud.
    """
    p = ws / "posting.yaml"
    if not p.exists():
        return None
    try:
        posting = journal.load_yaml(p)
    except journal.YamlUnreadable:
        return "unreadable"
    return str(posting.get("application_type") or "").strip().lower() == "structured"


def conditional_gates(ws: pathlib.Path) -> list:
    """[(gate, the visible trigger)] for the gates this workspace also requires.

    Every trigger is a file on disk, as visible to this gate as it was to the run
    that should have invoked it. That is the whole test for whether a gate belongs
    here rather than in the "not required" list: if the condition cannot be read
    off the workspace, requiring it would fire on runs where it does not apply.
    """
    out = []
    if (ws / "letter.yaml").exists():
        out.append(("check_letter", "letter.yaml exists"))
    # BOTH of check_pages' inputs, not just the PDF. With tailored-profile.yaml
    # absent the gate can only answer could_not_run, and that missing profile is
    # already check_claims' finding — two gates reporting one cause is how a
    # findings list stops being read.
    if (ws / "cv.pdf").exists() and (ws / "tailored-profile.yaml").exists():
        out.append(("check_pages", "cv.pdf and tailored-profile.yaml exist"))
    # references/structured-applications.md routes all three judges away from the
    # supporting statement, so this gate is the ONLY reader of the artifact that
    # is actually scored. Keyed on the statement first — the artifact, not a proxy
    # — and on the posting second, so that a structured application whose
    # statement was never written is reported rather than being the quietest
    # outcome available.
    if (ws / "supporting-statement.md").exists():
        out.append(("check_word_limits", "supporting-statement.md exists"))
    elif _structured(ws) is True:
        out.append(("check_word_limits",
                    "posting.yaml says application_type: structured, and there is "
                    "no supporting-statement.md"))
    return out


def _latest_round(ws: pathlib.Path):
    numbers = []
    for p in ws.glob("judge-round-*.json"):
        stem = p.stem.rsplit("-", 1)[-1]
        if stem.isdigit():
            numbers.append(int(stem))
    return max(numbers) if numbers else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--skill-root", default=None)
    args = ap.parse_args(argv)
    ws = pathlib.Path(args.workspace)
    root = pathlib.Path(args.skill_root) if args.skill_root else paths.SKILL_ROOT
    if not ws.is_dir():
        # No receipt here, deliberately: journal.append() would mkdir the
        # workspace, and a gate that creates the directory it is auditing has
        # manufactured its own evidence. Documented in the docstring.
        print(f"cannot run {GATE}: workspace {ws} does not exist", file=sys.stderr)
        return 2

    findings = []

    # ── the layer-1.5 backstop ────────────────────────────────────────────
    entry = enter_mode.latest_mode_entry(ws, "apply")
    mode_path = paths.mode_file("apply", root)
    if entry is None:
        findings.append("NO_MODE_ENTRY: journal.jsonl has no mode_entry for apply — "
                        "modes/apply.md is loaded unconditionally on entering the "
                        "mode; run scripts/enter_mode.py --mode apply and read it")
    elif mode_path.exists() and entry.get("mode_file_sha256") != journal.sha256_file(mode_path):
        findings.append("MODE_FILE_CHANGED: modes/apply.md changed after this run "
                        "entered the mode, so what was read is not what is on disk — "
                        "re-enter the mode and re-read it")

    # ── the journal itself is readable ────────────────────────────────────
    # journal._records drops an unparseable line, which is right for READING (a
    # truncated line must not blind a later gate to an earlier one) and wrong for
    # COMPOSING: read_receipts returns each gate oldest-first and this gate trusts
    # receipts[-1], so a truncated NEWEST receipt silently promotes the previous
    # one. A run whose final act was writing an UNSOURCED finding, cut short by a
    # killed process or a full disk, was reported here as a clean package.
    bad_lines = journal.corrupt_lines(ws)
    if bad_lines:
        findings.append(
            "JOURNAL_CORRUPT: journal.jsonl has unparseable line(s) at "
            + ", ".join(str(n) for n in bad_lines)
            + " — a receipt that cannot be read is not a receipt that passed, and "
              "the gate above it may be the one that failed. Re-run the gates "
              "rather than trusting what is still readable")

    # ── every upstream gate ran, on this workspace, and passed ────────────
    # An unreadable posting.yaml is reported here rather than nowhere. It is not
    # a word-limit demand — guessing "structured" from a file nobody could parse
    # would fire on runs with no supporting statement in sight, and that reasoning
    # is unchanged. But in the no-letter.yaml configuration nothing else in apply
    # mode reads posting.yaml, so returning a silent False both removed the
    # check_word_limits requirement and swallowed the reason.
    if _structured(ws) == "unreadable":
        findings.append(
            "UNREADABLE_POSTING: posting.yaml exists and will not parse, so this "
            "gate cannot tell whether the application is criterion-scored — and a "
            "structured posting is the case where check_word_limits is the ONLY "
            "reader of the document the employer actually marks. Fix the YAML and "
            "re-run")

    conditional = conditional_gates(ws)
    trigger = dict(conditional)
    required = list(REQUIRED_GATES) + [g for g, _ in conditional]
    for gate in required:
        receipts = journal.read_receipts(ws, gate)
        if not receipts:
            # `CODE: subject` — the subject comes first so a reader (and a test)
            # can grep `MISSING_RECEIPT: check_claims` the way every other
            # finding in this skill is greppable.
            because = f" ({trigger[gate]})" if gate in trigger else ""
            findings.append(f"MISSING_RECEIPT: {gate} has no receipt in "
                            f"journal.jsonl{because} — the gate was never run, and a "
                            f"skipped gate looks exactly like a clean one")
            continue
        last = receipts[-1]
        verdict = last.get("verdict")
        if verdict in SETUP_VERDICTS:
            # A distinct code, and deliberately not UPSTREAM_FAILED: nothing
            # failed. Diagnosing "never ran" as "failed" sends the reader hunting
            # for a defect that is not there and, finding none, concluding the
            # gate is noisy.
            findings.append(f"NOT_VERIFIED: {gate} has only a '{verdict}' receipt — "
                            f"that is the --record step, which stores a baseline for "
                            f"a later comparison and checks nothing. Nothing failed; "
                            f"the verification pass was never run. Run {gate} again "
                            f"without --record, once the files it reads are final")
        elif verdict not in PASSING_VERDICTS:
            detail = "; ".join(last.get("findings") or []) or "no findings recorded"
            findings.append(f"UPSTREAM_FAILED: {gate} verdict={verdict} "
                            f"({detail})")
        else:
            findings.extend(_stale_inputs(ws, gate, last))

    # ── any other gate that ran and failed ────────────────────────────────
    # Enumerating gates cannot keep up with the gates: check_pages and
    # check_word_limits were both absent from the list above, so either could RUN,
    # print CV_TOO_LONG or OVER_LIMIT, write `verdict: fail` — and this gate wrote
    # its own `pass` three lines below it in the same journal.jsonl. A failing
    # receipt is a failing receipt, whether or not anyone remembered to name it.
    #
    # Scoped by the receipt's mode stamp, and only when the stamp names a
    # DIFFERENT mode: check_mock writes into this same workspace, a failed mock
    # round is check_mock's finding, and no edit available in apply mode clears
    # it. Unstamped and "unknown" receipts are checked, not skipped — a gate run
    # before the mode entry is exactly the case that must not slip through, so the
    # default is to look.
    other_modes = tuple(m for m in enter_mode.MODES if m != MODE)
    latest = {}
    for rec in journal.read_receipts(ws):
        if rec.get("gate"):
            latest[rec["gate"]] = rec
    for gate, last in latest.items():
        verdict = last.get("verdict")
        if gate == GATE or gate in required or verdict != "fail":
            continue
        if last.get("mode") in other_modes:
            continue
        detail = "; ".join(last.get("findings") or []) or "no findings recorded"
        findings.append(f"UPSTREAM_FAILED: {gate} verdict=fail ({detail}) — this gate "
                        f"is not on the required list and it still ran and failed; a "
                        f"package is not deliverable over a failing gate. Fix it and "
                        f"re-run it, or re-run it to a pass")

    # ── the round passed, or the stop is classified ───────────────────────
    n = _latest_round(ws)
    # The parse_verdicts receipt has to be about THIS round. Without the round
    # stamp, `judge-round-2.json` could be hand-written with
    # `combined_verdict: "PASS"` while round 1's receipt vouched for it, and the
    # package went out over a round the judges had rejected. Round 1 alone was
    # protected, by MISSING_RECEIPT.
    if n is not None:
        pv = journal.read_receipts(ws, "parse_verdicts")
        recorded = pv[-1].get("round") if pv else None
        if pv and recorded is None:
            findings.append(
                "PARSE_VERDICTS_ROUND_UNKNOWN: the parse_verdicts receipt records "
                "no round, so nothing ties it to judge-round-"
                f"{n}.json. Re-run parse_verdicts --round {n}")
        elif pv and int(recorded) != int(n):
            findings.append(
                f"PARSE_VERDICTS_STALE_ROUND: the latest parse_verdicts receipt is "
                f"for round {recorded}, but the highest round in the workspace is "
                f"{n}. The verdicts in judge-round-{n}.json were never parsed by "
                f"the gate — re-run parse_verdicts --round {n}")

    combined = rounds.load_round(ws, n).get("combined_verdict") if n else None
    if n is None:
        findings.append("NO_ROUND: no judge-round-<n>.json in the workspace — the "
                        "three-judge review loop is non-negotiable and leaves an "
                        "artifact")
    elif combined != "PASS":
        stop_path = ws / "honest-stop.yaml"
        if not stop_path.exists():
            findings.append(f"NO_PASS_NO_STOP: round {n} is {combined} and there is no "
                            f"honest-stop.yaml. Write one and classify it: "
                            f"poorly_built (a fixable tailoring miss) or honest_stretch "
                            f"(a well-built application for a reach role). The two emit "
                            f"the same machine signal and mean opposite things to the "
                            f"user")
        else:
            # A FINDING, not exit 2, and deliberately so: this gate composes a dozen
            # other checks and is the one that decides whether a package may be
            # delivered. Aborting the composition here would discard everything
            # already collected — the exact defect this pass exists to close — and
            # the receipt still carries the named reason either way.
            try:
                stop = journal.load_yaml(stop_path)
            except journal.YamlUnreadable as exc:
                stop = {}
                findings.append(
                    f"{exc.finding} — the stop cannot be classified from a file "
                    f"nothing can read, and an unclassified stop is the one thing "
                    f"NO_PASS_NO_STOP exists to prevent")
            if stop.get("classification") not in CLASSIFICATIONS:
                findings.append(f"BAD_STOP_CLASSIFICATION: honest-stop.yaml "
                                f"classification {stop.get('classification')!r} is not "
                                f"one of {', '.join(CLASSIFICATIONS)}")
            if stop.get("verdict") not in VERDICTS:
                findings.append(f"BAD_STOP_VERDICT: honest-stop.yaml verdict "
                                f"{stop.get('verdict')!r} is not one of "
                                f"{', '.join(VERDICTS)}")
            if not str(stop.get("reason") or "").strip():
                findings.append("INCOMPLETE_STOP: honest-stop.yaml has no reason")
            if not (stop.get("evidence") or []):
                findings.append("INCOMPLETE_STOP: honest-stop.yaml has no evidence — "
                                "name the judge findings the classification rests on")

    if not (ws / "interview-brief.md").exists():
        findings.append("NO_BRIEF: interview-brief.md is missing — it is the last "
                        "honesty checkpoint and the only one that can still walk a "
                        "claim back after every gate has already fired")

    for f in findings:
        print(f)
    journal.receipt(ws, GATE, {}, "fail" if findings else "pass", findings)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
