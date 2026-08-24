#!/usr/bin/env python3
"""Detect an assertion that cannot tell the arms apart.

--pilot runs BEFORE the with-skill arm is dispatched, over one baseline run per
guard eval. A discriminating assertion the baseline passes is not evidence about
the skill, and finding that out after one run costs one run; finding it out
after the full matrix costs the matrix, which is what iteration-1 did.

Without --pilot it runs over the finished iteration and flags any discriminating
assertion the baseline passed in EVERY run. One baseline failure anywhere is
enough to show the assertion can discriminate; unanimity is the signal.
"""
import argparse
import json
import pathlib
import sys

import yaml

from evals import runlib
from evals import schema

ASSERTIONS = pathlib.Path(__file__).resolve().parent / "assertions.yaml"


def _baseline_rows(iteration_dir):
    """eval_id -> assertion_id -> list of passed values, baseline arm only."""
    out = {}
    for eval_id, arm, _n, run in runlib.iter_runs(iteration_dir):
        if arm != "baseline":
            continue
        path = run.dir / "grading.json"
        if not path.is_file():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        for row in doc.get("expectations", []):
            out.setdefault(eval_id, {}).setdefault(
                row.get("assertion_id"), []).append(row.get("passed"))
    return out


def _guards(doc):
    return [(e["id"], a) for e in doc["evals"] for a in e["assertions"]
            if a["role"] == "discriminating"
            and "baseline" in (a.get("arms") or schema.ARMS)]


def pilot(iteration_dir, doc):
    rows = _baseline_rows(iteration_dir)
    findings = []
    for eval_id, a in _guards(doc):
        if eval_id not in rows:
            findings.append(
                f"NO_PILOT_RUN: eval-{eval_id} has no graded baseline run. The "
                "pilot exists so a useless assertion costs one run instead of "
                "the whole matrix — do not dispatch with_skill yet.")
            continue
        results = rows[eval_id].get(a["id"], [])
        if not results:
            findings.append(f"NO_PILOT_RUN: eval-{eval_id} baseline run does not "
                            f"grade {a['id']}")
        elif all(r is None for r in results):
            findings.append(
                f"GUARD_NOT_EXERCISED: {a['id']} was not exercised in the "
                "baseline pilot. The scenario does not reach the branch — fix "
                "the scenario, not the assertion. This is exactly how "
                "iteration-1's A2-3 came to measure nothing.")
        elif all(r for r in results if r is not None):
            findings.append(
                f"BASELINE_PASSED_A_GUARD: {a['id']} is marked discriminating "
                f"and the baseline passed it. Either the scenario does not "
                f"force the branch, or the property is the model's rather than "
                f"the skill's — re-role it to regression with a written reason, "
                f"or rewrite the scenario. Do not run the with_skill arm on it "
                f"as it stands. Falsifier on record: {a['falsifier']}")
    return findings


def posthoc(iteration_dir, doc):
    rows = _baseline_rows(iteration_dir)
    findings = []
    for eval_id, a in _guards(doc):
        results = [r for r in rows.get(eval_id, {}).get(a["id"], [])
                   if r is not None]
        if results and all(results):
            findings.append(
                f"NON_DISCRIMINATING: {a['id']} passed in all {len(results)} "
                "baseline run(s). It is not evidence about the skill. Re-role "
                "it or change the scenario before iteration-3; the lint will "
                "fail while it is still marked discriminating.")
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iteration", required=True)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--assertions-inline", default=None,
                        help="JSON document, for tests; otherwise "
                             "evals/assertions.yaml is read")
    args = parser.parse_args(argv)

    iteration = pathlib.Path(args.iteration)
    if not iteration.is_dir():
        print(f"cannot run: {iteration} does not exist", file=sys.stderr)
        return 2
    doc = (json.loads(args.assertions_inline) if args.assertions_inline
           else yaml.safe_load(ASSERTIONS.read_text(encoding="utf-8")))
    findings = pilot(iteration, doc) if args.pilot else posthoc(iteration, doc)
    for f in findings:
        print(f)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
