#!/usr/bin/env python3
"""Gate: apply mode may not claim success without evidence for each claim.

Composition, not new judgement. Each upstream gate already decided one thing;
this asserts that each of them actually ran, on this workspace, and passed —
because a skipped script produces no output and no output is exactly what a
clean run looks like.

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

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import enter_mode
import journal
import paths
import rounds
import vocab

GATE = "check_apply"
# parse_verdicts is in this list for a reason that is easy to miss:
# judge-round-<n>.json is a plain JSON file, so without its receipt a
# hand-written `combined_verdict: PASS` passes this gate with no evidence the
# parser ever ran — the exact substitution parse_verdicts.py exists to prevent.
REQUIRED_GATES = ("check_personal_data", "check_claims", "check_render_freshness",
                  "parse_verdicts", "lint_cv")
CLASSIFICATIONS = ("poorly_built", "honest_stretch")
VERDICTS = vocab.VERDICTS
PASSING_VERDICTS = ("pass", "recorded")


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
    required = list(REQUIRED_GATES)
    if (ws / "letter.yaml").exists():
        required.append("check_letter")
    for gate in required:
        receipts = journal.read_receipts(ws, gate)
        if not receipts:
            # `CODE: subject` — the subject comes first so a reader (and a test)
            # can grep `MISSING_RECEIPT: check_claims` the way every other
            # finding in this skill is greppable.
            findings.append(f"MISSING_RECEIPT: {gate} has no receipt in "
                            f"journal.jsonl — the gate was never run, and a "
                            f"skipped gate looks exactly like a clean one")
            continue
        last = receipts[-1]
        if last.get("verdict") not in PASSING_VERDICTS:
            detail = "; ".join(last.get("findings") or []) or "no findings recorded"
            findings.append(f"UPSTREAM_FAILED: {gate} verdict={last.get('verdict')} "
                            f"({detail})")

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
            stop = yaml.safe_load(stop_path.read_text(encoding="utf-8")) or {}
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
