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


def _structured(ws: pathlib.Path) -> bool:
    """Does posting.yaml declare a criterion-scored application?

    An unreadable posting.yaml answers "no": it is somebody's finding, but not
    this branch's, and guessing "structured" from a file nobody could parse would
    demand a gate on a run with no supporting statement anywhere in sight.
    """
    p = ws / "posting.yaml"
    if not p.exists():
        return False
    try:
        posting = journal.load_yaml(p)
    except journal.YamlUnreadable:
        return False
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
    elif _structured(ws):
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

    # ── every upstream gate ran, on this workspace, and passed ────────────
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
        if gate == GATE or gate in required or last.get("verdict") != "fail":
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
