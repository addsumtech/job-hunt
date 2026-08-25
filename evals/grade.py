#!/usr/bin/env python3
"""Run every checker over a run directory and write grading.json.

Field names are the viewer's, not ours: expectations[].{text,passed,evidence}.
The plugin's aggregator warns and the viewer silently drops rows that use any
other spelling.

A checker's evidence is carried VERBATIM. A grading file is read by someone
checking a claim, and a summary of the evidence is not the evidence.

A human grade already in the file WINS. The reader-graded rows are the ones a
program cannot decide; re-running the grader must not wipe the judgement that
was made about them.
"""
import argparse
import json
import pathlib
import sys

import yaml

# Importable as `from evals import grade` (repo root on sys.path) AND runnable as
# `python3 evals/grade.py`, where sys.path[0] is evals/ and the package would
# otherwise not import at all. A ModuleNotFoundError traceback exits 1, which is
# this file's code for "findings" -- so without this, a broken invocation and a
# real finding look identical to anything reading the exit code.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals import checkers as ck  # noqa: E402
from evals import runlib  # noqa: E402
from evals import schema  # noqa: E402

ASSERTIONS = pathlib.Path(__file__).resolve().parent / "assertions.yaml"
# The string evals/checkers.py hands back for a row only a reader can
# settle, and the string evals/lint_grading.py fails on. Pinned by test.
AWAITING_READER_GRADE = "AWAITING_READER_GRADE"


def _existing(run):
    """Human-decided rows from any grading.json already here, keyed by text.

    Only rows with a verdict are kept: a row still reading AWAITING_READER_GRADE
    is not a judgement to preserve, and keeping it would make the reader's
    to-do list survive every re-grade.
    """
    path = run.dir / "grading.json"
    if not path.is_file():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    if not isinstance(doc, dict):
        return {}
    return {row.get("text"): row for row in doc.get("expectations") or []
            if isinstance(row, dict) and row.get("passed") is not None}


def grade_run(run, eval_record):
    keep = _existing(run)
    rows = []
    for a in eval_record["assertions"]:
        fn = ck.CHECKERS.get(a["checker"])
        if fn is None:
            # Not a crash: assertions.yaml is linted for this, so reaching here
            # means the two drifted apart, and the run says which.
            rows.append({"text": a["text"], "passed": False,
                         "evidence": f"no checker named {a['checker']!r} is "
                                     f"registered in evals/checkers.py",
                         "assertion_id": a["id"], "role": a["role"],
                         "checker": a["checker"]})
            continue
        try:
            passed, evidence = fn(run)
        except Exception as exc:                      # noqa: BLE001
            passed, evidence = False, f"checker {a['checker']} raised {exc!r}"
        # A human grade wins ONLY where the program cannot decide -- that is,
        # where the checker itself hands the row to a reader. Preserving a
        # PROGRAMMATIC verdict would make the grader non-idempotent against the
        # artifacts: fix a run, re-grade it, and it still reports the old
        # failure, with the old evidence, and the fix is invisible. Measured
        # before this guard existed: a run whose journal was repaired from
        # verdict "error" to "pass" still graded False on the second pass.
        # The runbook's own loop is grade -> hand-grade -> lint -> re-grade, so
        # re-grading is the normal case, not the exception.
        if (passed is None and str(evidence) == AWAITING_READER_GRADE
                and a["text"] in keep):
            rows.append(dict(keep[a["text"]]))
            continue
        rows.append({"text": a["text"], "passed": passed,
                     "evidence": str(evidence), "assertion_id": a["id"],
                     "role": a["role"], "checker": a["checker"]})

    decided = [r for r in rows if r["passed"] is not None]
    passed_n = sum(1 for r in decided if r["passed"])
    total = len(decided)
    return {
        "eval_id": eval_record["id"],
        "eval_name": eval_record["name"],
        "expectations": rows,
        "summary": {
            "passed": passed_n,
            "failed": total - passed_n,
            "total": total,
            "not_exercised": len(rows) - total,
            # None, not 0.0: a pass rate over an empty denominator is not zero,
            # and 0.0 would read as "everything failed" in every table.
            "pass_rate": (passed_n / total) if total else None,
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iteration", required=True)
    parser.add_argument("--eval", type=int, default=None)
    parser.add_argument("--arm", default=None)
    args = parser.parse_args(argv)

    iteration = pathlib.Path(args.iteration)
    if not iteration.is_dir():
        print(f"cannot run: {iteration} does not exist", file=sys.stderr)
        return 2
    doc = yaml.safe_load(ASSERTIONS.read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in doc["evals"]}

    written = 0
    unknown = 0
    for eval_id, arm, run_number, run in runlib.iter_runs(iteration):
        if args.eval is not None and eval_id != args.eval:
            continue
        if args.arm is not None and arm != args.arm:
            continue
        record = by_id.get(eval_id)
        if record is None:
            print(f"UNKNOWN_EVAL: eval-{eval_id} is on disk but not in "
                  f"assertions.yaml")
            unknown += 1
            continue
        scoped = [a for a in record["assertions"]
                  if arm in (a.get("arms") or schema.ARMS)]
        graded = grade_run(run, dict(record, assertions=scoped))
        (run.dir / "grading.json").write_text(
            json.dumps(graded, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        written += 1
    print(f"graded {written} run(s)")
    if written == 0:
        # An empty iteration exiting 0 with "graded 0 run(s)" is the iteration-1
        # defect this harness exists to stop: nothing ran, and it read as fine.
        print(f"cannot run: no runs under {iteration}", file=sys.stderr)
        return 2
    return 1 if unknown else 0


if __name__ == "__main__":
    raise SystemExit(main())
