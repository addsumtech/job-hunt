#!/usr/bin/env python3
"""Score an iteration honestly.

Three things the plugin's aggregator cannot do, each of which iteration-1 got
wrong:

  1. It hardcodes metadata.runs_per_configuration = 3 whatever is on disk. This
     one counts run-* directories per (eval, arm) and reports them.
  2. Its delta is configs[0] - configs[1], which with our directory names reads
     baseline - with_skill; iteration-1's pass rate rose 0.875 -> 1.0 and printed
     "-0.12". This one emits delta_with_minus_baseline.
  3. It has no notion of an assertion role, so ten regression rows both arms pass
     can drown one guard that failed. This one scores the two in separate tables
     and flags any discriminating assertion the baseline passed everywhere.

A missing arm exits 1. It is the iteration-1 defect and it must be loud.
"""
import argparse
import json
import pathlib
import statistics
import sys

import yaml

# Importable as `from evals import aggregate` (repo root on sys.path) AND runnable as
# `python3 evals/aggregate.py`, where sys.path[0] is evals/ and the package would
# otherwise not import at all. A ModuleNotFoundError traceback exits 1, which is
# this file's code for "findings" -- so without this, a broken invocation and a
# real finding look identical to anything reading the exit code.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals import runlib  # noqa: E402
from evals import schema  # noqa: E402

ASSERTIONS = pathlib.Path(__file__).resolve().parent / "assertions.yaml"


def _stat(values):
    if not values:
        return None
    if len(values) == 1:
        return {"value": values[0], "n": 1}
    return {"mean": round(statistics.fmean(values), 4),
            "stddev": round(statistics.stdev(values), 4),
            "min": min(values), "max": max(values), "n": len(values)}


def _fmt(stat, unit=""):
    if stat is None:
        return "—"
    if stat.get("n") == 1:
        return f"{stat['value']:g}{unit} (n=1, no dispersion)"
    return (f"{stat['mean']:g}{unit} ± {stat['stddev']:g}{unit} "
            f"({stat['min']:g}–{stat['max']:g}{unit}, n={stat['n']})")


def summarise(iteration_dir, doc):
    by_id = {e["id"]: e for e in doc["evals"]}
    role_of = {a["id"]: a["role"] for e in doc["evals"] for a in e["assertions"]}

    run_counts, per_arm, rows = {}, {a: {"pass": 0, "total": 0, "seconds": [],
                                         "tokens": []} for a in schema.ARMS}, {}
    per_eval = {}
    for eval_id, arm, _n, run in runlib.iter_runs(iteration_dir):
        per_eval.setdefault(str(eval_id), {a: {"seconds": [], "tokens": []}
                                           for a in schema.ARMS})
        run_counts.setdefault(str(eval_id), {a: 0 for a in schema.ARMS})
        run_counts[str(eval_id)][arm] = run_counts[str(eval_id)].get(arm, 0) + 1
        grading = json.loads((run.dir / "grading.json").read_text(
            encoding="utf-8"))
        timing_path = run.dir / "timing.json"
        if timing_path.is_file():
            timing = json.loads(timing_path.read_text(encoding="utf-8"))
            per_arm[arm]["seconds"].append(timing.get("total_duration_seconds", 0))
            per_arm[arm]["tokens"].append(timing.get("total_tokens", 0))
            per_eval[str(eval_id)][arm]["seconds"].append(
                timing.get("total_duration_seconds", 0))
            per_eval[str(eval_id)][arm]["tokens"].append(
                timing.get("total_tokens", 0))
        for row in grading.get("expectations", []):
            if row.get("passed") is None:
                rows.setdefault(row.get("assertion_id"), {}).setdefault(
                    "not_exercised", []).append(f"eval-{eval_id}/{arm}")
                continue
            bucket = rows.setdefault(row.get("assertion_id"), {})
            bucket.setdefault(arm, []).append(bool(row["passed"]))
            bucket["text"] = row.get("text")
            bucket["role"] = row.get("role") or role_of.get(
                row.get("assertion_id"), "regression")
            bucket.setdefault("evidence", {}).setdefault(
                arm, row.get("evidence", ""))
            per_arm[arm]["total"] += 1
            per_arm[arm]["pass"] += 1 if row["passed"] else 0

    missing = [f"eval-{eid} {arm}" for eid in sorted(by_id, key=int)
               for arm in schema.ARMS
               if not run_counts.get(str(eid), {}).get(arm)]
    non_discriminating = sorted(
        aid for aid, b in rows.items()
        if b.get("role") == "discriminating" and b.get("baseline")
        and all(b["baseline"]))

    counts = [c for e in run_counts.values() for c in e.values()]
    delta = {}
    for metric, key in (("pass_rate", None), ("seconds", "seconds"),
                        ("tokens", "tokens")):
        if key is None:
            a = (per_arm["with_skill"]["pass"] /
                 per_arm["with_skill"]["total"]) if per_arm["with_skill"]["total"] else 0
            b = (per_arm["baseline"]["pass"] /
                 per_arm["baseline"]["total"]) if per_arm["baseline"]["total"] else 0
        else:
            a = statistics.fmean(per_arm["with_skill"][key]) if \
                per_arm["with_skill"][key] else 0
            b = statistics.fmean(per_arm["baseline"][key]) if \
                per_arm["baseline"][key] else 0
        delta[metric] = round(a - b, 4)

    return {
        "iteration_dir": str(iteration_dir),
        "run_counts": run_counts,
        "uniform_runs": len(set(counts)) <= 1,
        "missing_arms": missing,
        "per_arm": {a: {"passed": per_arm[a]["pass"],
                        "total": per_arm[a]["total"],
                        "seconds": _stat(per_arm[a]["seconds"]),
                        "tokens": _stat(per_arm[a]["tokens"])} for a in schema.ARMS},
        "per_eval_cost": {
            eid: {a: {"seconds": _stat(v[a]["seconds"]),
                      "tokens": _stat(v[a]["tokens"])} for a in schema.ARMS}
            for eid, v in per_eval.items()},
        "assertions": rows,
        "non_discriminating": non_discriminating,
        "delta_with_minus_baseline": delta,
        "partial": bool(missing),
    }


def _cell(bucket, arm):
    results = bucket.get(arm)
    if not results:
        return "—"
    return f"{sum(1 for r in results if r)}/{len(results)}"


def _table(summary, role):
    lines = ["| assertion | baseline | with_skill | note |",
             "|---|---|---|---|"]
    for aid in sorted(k for k, b in summary["assertions"].items()
                      if b.get("role") == role):
        b = summary["assertions"][aid]
        note = ""
        if aid in summary["non_discriminating"]:
            note = ("**NON_DISCRIMINATING** — the baseline passed it in every "
                    "run; it is not evidence about the skill")
        lines.append(f"| `{aid}` {b.get('text','')} | {_cell(b,'baseline')} | "
                     f"{_cell(b,'with_skill')} | {note} |")
    return "\n".join(lines)


def render_markdown(summary):
    out = [f"# iteration summary — {summary['iteration_dir']}", ""]
    if summary["partial"]:
        out += ["> **PARTIAL** — these arms have no runs on disk: "
                + ", ".join(summary["missing_arms"])
                + ". Every number below is computed over what exists, and a "
                  "missing arm is exactly the iteration-1 defect.", ""]
    out += ["## Runs (counted from disk)", ""]
    for eid in sorted(summary["run_counts"], key=int):
        counts = summary["run_counts"][eid]
        out.append(f"- eval-{eid}: " + ", ".join(
            f"{arm} n={counts.get(arm, 0)}" for arm in schema.ARMS))
    out += ["", "## Discriminating assertions", "",
            _table(summary, "discriminating"), "",
            "## Regression assertions", "", _table(summary, "regression"), "",
            "## Cost", ""]
    out += ["Per eval, because a mean over different scenarios measures "
            "nothing: eval-5 and eval-7 are different tasks, and pooling them "
            "also hides an eval that ran once.", ""]
    for eid in sorted(summary.get("per_eval_cost") or {}, key=int):
        cost = summary["per_eval_cost"][eid]
        for arm in schema.ARMS:
            out.append(f"- eval-{eid} **{arm}**: "
                       f"time {_fmt(cost[arm]['seconds'], 's')}; "
                       f"tokens {_fmt(cost[arm]['tokens'])}")
    out += ["", "Pooled across every eval. Run-count weighted, so an eval with "
            "more runs pulls it; the per-eval rows above are the like-for-like "
            "comparison.", ""]
    for arm in schema.ARMS:
        a = summary["per_arm"][arm]
        out.append(f"- **{arm}**: {a['passed']}/{a['total']} assertions; "
                   f"time {_fmt(a['seconds'], 's')}; "
                   f"tokens {_fmt(a['tokens'])}")
    d = summary["delta_with_minus_baseline"]
    out += ["", f"**delta (with_skill − baseline)**: pass rate "
                f"{d['pass_rate']:+.4f}, time {d['seconds']:+.1f}s, "
                f"tokens {d['tokens']:+.0f}", ""]
    if summary["non_discriminating"]:
        out += ["## Not evidence", "",
                "These are marked `role: discriminating` and the baseline "
                "passed them in every run. Re-role them or change the scenario "
                "that was supposed to force the branch:", ""]
        out += [f"- `{aid}`" for aid in summary["non_discriminating"]]
        out.append("")
    not_exercised = {aid: b["not_exercised"]
                     for aid, b in summary["assertions"].items()
                     if b.get("not_exercised")}
    if not_exercised:
        out += ["## Not exercised", "",
                "Excluded from every denominator above. Not a pass.", ""]
        out += [f"- `{aid}` — {', '.join(where)}"
                for aid, where in sorted(not_exercised.items())]
        out.append("")
    return "\n".join(out)


def patch_benchmark(benchmark, summary):
    """Fix the plugin's two known defects in its own output file, so the viewer
    cannot tell a different story from summary.md."""
    benchmark.setdefault("metadata", {})["runs_per_configuration"] = \
        summary["run_counts"]
    d = summary["delta_with_minus_baseline"]
    notes = benchmark.setdefault("notes", [])
    notes.append(
        f"delta as printed above is baseline − with_skill (configs[0] − "
        f"configs[1]) and reads inverted. Signed the other way: "
        f"with_skill − baseline = pass rate {d['pass_rate']:+.4f}, time "
        f"{d['seconds']:+.1f}s, tokens {d['tokens']:+.0f}.")
    notes.append("runs_per_configuration is counted from disk here, not the "
                 "hardcoded 3 the aggregation script writes.")
    for aid in summary["non_discriminating"]:
        notes.append(f"NON_DISCRIMINATING: {aid} passed in every baseline run.")
    return benchmark


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iteration", required=True)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--write-record", action="store_true")
    parser.add_argument("--record-path", default=None)
    args = parser.parse_args(argv)

    iteration = pathlib.Path(args.iteration)
    if not iteration.is_dir():
        print(f"cannot run: {iteration} does not exist", file=sys.stderr)
        return 2
    doc = yaml.safe_load(ASSERTIONS.read_text(encoding="utf-8"))
    summary = summarise(iteration, doc)
    markdown = render_markdown(summary)

    (iteration / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    (iteration / "summary.md").write_text(markdown + "\n", encoding="utf-8")

    benchmark_path = iteration / "benchmark.json"
    if benchmark_path.is_file():
        patched = patch_benchmark(
            json.loads(benchmark_path.read_text(encoding="utf-8")), summary)
        benchmark_path.write_text(
            json.dumps(patched, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")

    if args.write_record:
        record = pathlib.Path(args.record_path or (
            pathlib.Path(__file__).resolve().parent / "iterations" /
            f"{iteration.name}.md"))
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(
            "<!-- Generated by evals/aggregate.py --write-record. Do not edit "
            "by hand: every number here is counted, and a hand-typed one would "
            "be the only unsourced figure in the repo. -->\n\n" + markdown
            + "\n", encoding="utf-8")

    if summary["missing_arms"] and not args.allow_partial:
        print("MISSING_ARM: " + ", ".join(summary["missing_arms"]))
        print("Three of iteration-1's five evals had no baseline arm and the "
              "aggregate absorbed it. Re-run them, or pass --allow-partial to "
              "stamp the summary PARTIAL.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
