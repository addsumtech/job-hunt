#!/usr/bin/env python3
"""Reject a grading file whose evidence records nothing.

A grading.json is the one artifact here a human edits, and "looks good" in the
evidence field turns a benchmark back into an impression. AWAITING_READER_GRADE
is a hard failure rather than a skip: the judgement-based assertions are the
ones no program can cover, so letting them stay ungraded quietly shrinks the
eval to whatever a program could already decide.
"""
import argparse
import json
import pathlib
import sys

CONTENTLESS = ("ok", "okay", "passed", "pass", "fail", "failed", "yes", "no",
               "looks good", "as expected", "correct", "fine", "good", "n/a",
               "-", "done")
MIN_EVIDENCE_CHARS = 12


def check(doc, path):
    findings = []
    rows = doc.get("expectations") or []
    if not rows:
        return [f"NO_EXPECTATIONS: {path} grades nothing"]
    for row in rows:
        text = (row.get("text") or "")[:48]
        evidence = (row.get("evidence") or "").strip()
        if row.get("passed") is None:
            if evidence == "AWAITING_READER_GRADE":
                findings.append(
                    f"AWAITING_READER_GRADE: {path} row {text!r} still needs a "
                    "reader's judgement. Grade it or re-role the assertion; do "
                    "not aggregate around it.")
            elif not evidence.lower().startswith("not exercised"):
                findings.append(
                    f"UNEXPLAINED_NULL: {path} row {text!r} is null with no "
                    "'not exercised: ...' reason")
            continue
        if not evidence:
            findings.append(f"NO_EVIDENCE: {path} row {text!r} has none")
        elif evidence.lower().strip(".") in CONTENTLESS:
            findings.append(
                f"CONTENTLESS_EVIDENCE: {path} row {text!r} records "
                f"{evidence!r}, which a later reader cannot check")
        elif len(evidence) < MIN_EVIDENCE_CHARS:
            findings.append(f"THIN_EVIDENCE: {path} row {text!r} records "
                            f"{evidence!r}")

    decided = [r for r in rows if r.get("passed") is not None]
    summary = doc.get("summary") or {}
    expected_passed = sum(1 for r in decided if r["passed"])
    if summary.get("total") != len(decided) or \
            summary.get("passed") != expected_passed:
        findings.append(
            f"SUMMARY_MISMATCH: {path} summary says "
            f"{summary.get('passed')}/{summary.get('total')} but the rows say "
            f"{expected_passed}/{len(decided)}")
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iteration", required=True)
    args = parser.parse_args(argv)
    root = pathlib.Path(args.iteration)
    if not root.is_dir():
        print(f"cannot run: {root} does not exist", file=sys.stderr)
        return 2
    graded = sorted(root.glob("eval-*/*/run-*/grading.json"))
    if not graded:
        print(f"cannot run: no grading.json under {root} -- run evals/grade.py "
              f"first", file=sys.stderr)
        return 2
    findings = []
    for path in graded:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            findings.append(f"UNPARSABLE: {path} is not JSON: {exc}")
            continue
        findings += check(doc, str(path.relative_to(root)))
    for f in findings:
        print(f)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
