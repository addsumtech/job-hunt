import json

import pytest

from evals import aggregate

DOC = {"evals": [
    {"id": 5, "name": "discover-blocked-adapter", "mode": "discover",
     "baseline_kind": "no_skill", "scenario": "s.md",
     "assertions": [
         {"id": "A5-1", "text": "no absence claim", "role": "discriminating",
          "expected_baseline": "fail", "falsifier": "x" * 30,
          "checker": "absence_claim_matches_journal"}]},
    {"id": 7, "name": "discover-honest-zero", "mode": "discover",
     "baseline_kind": "no_skill", "scenario": "s.md",
     "assertions": [
         {"id": "A7-1", "text": "zero is stated", "role": "regression",
          "expected_baseline": "pass", "falsifier": "y" * 30,
          "checker": "honest_zero_is_stated"}]}]}


def write_run(root, eval_id, arm, n, *, rows, seconds=100.0, tokens=1000):
    d = root / f"eval-{eval_id}" / arm / f"run-{n}"
    (d / "outputs").mkdir(parents=True)
    decided = [r for r in rows if r["passed"] is not None]
    passed = sum(1 for r in decided if r["passed"])
    (d / "grading.json").write_text(json.dumps({
        "eval_id": eval_id, "expectations": rows,
        "summary": {"passed": passed, "failed": len(decided) - passed,
                    "total": len(decided), "not_exercised": len(rows) - len(decided),
                    "pass_rate": (passed / len(decided)) if decided else None}}),
        encoding="utf-8")
    (d / "timing.json").write_text(json.dumps({
        "total_tokens": tokens, "duration_ms": int(seconds * 1000),
        "total_duration_seconds": seconds}), encoding="utf-8")


def row(aid, text, role, passed, evidence="cv.md:3 'quoted'"):
    return {"assertion_id": aid, "text": text, "role": role, "passed": passed,
            "evidence": evidence}


@pytest.fixture
def iteration(tmp_path):
    for n in (1, 2, 3):
        write_run(tmp_path, 5, "with_skill", n,
                  rows=[row("A5-1", "no absence claim", "discriminating", True)],
                  seconds=300.0 + n, tokens=80000 + n)
        write_run(tmp_path, 5, "baseline", n,
                  rows=[row("A5-1", "no absence claim", "discriminating", False,
                            "says 没有匹配 with no adapter at exit 0")],
                  seconds=200.0 + n, tokens=60000 + n)
    write_run(tmp_path, 7, "with_skill", 1,
              rows=[row("A7-1", "zero is stated", "regression", True)])
    write_run(tmp_path, 7, "baseline", 1,
              rows=[row("A7-1", "zero is stated", "regression", True)])
    return tmp_path


def test_run_counts_come_from_disk(iteration):
    s = aggregate.summarise(iteration, DOC)
    assert s["run_counts"]["5"]["with_skill"] == 3
    assert s["run_counts"]["7"]["with_skill"] == 1
    assert s["uniform_runs"] is False


def test_the_delta_is_with_skill_minus_baseline(iteration):
    s = aggregate.summarise(iteration, DOC)
    assert s["delta_with_minus_baseline"]["pass_rate"] > 0, (
        "with_skill passes more than baseline here; a negative delta would be "
        "the iteration-1 sign inversion")


def test_dispersion_is_omitted_for_a_single_run(iteration):
    md = aggregate.render_markdown(aggregate.summarise(iteration, DOC))
    assert "n=1, no dispersion" in md
    assert "± 0" not in md


def test_a_pass_rate_is_printed_with_its_denominator(iteration):
    md = aggregate.render_markdown(aggregate.summarise(iteration, DOC))
    assert "3/3" in md or "1/1" in md


def test_roles_are_scored_in_separate_tables(iteration):
    md = aggregate.render_markdown(aggregate.summarise(iteration, DOC))
    assert "## Discriminating assertions" in md
    assert "## Regression assertions" in md
    disc = md.split("## Discriminating")[1].split("## Regression")[0]
    assert "A5-1" in disc and "A7-1" not in disc


def test_a_non_discriminating_assertion_is_flagged(tmp_path):
    for arm in ("baseline", "with_skill"):
        write_run(tmp_path, 5, arm, 1,
                  rows=[row("A5-1", "no absence claim", "discriminating", True)])
    s = aggregate.summarise(tmp_path, {"evals": [DOC["evals"][0]]})
    assert "A5-1" in s["non_discriminating"]
    assert "NON_DISCRIMINATING" in aggregate.render_markdown(s)


def test_a_missing_arm_is_an_error_not_a_footnote(tmp_path):
    write_run(tmp_path, 5, "with_skill", 1,
              rows=[row("A5-1", "no absence claim", "discriminating", True)])
    code = aggregate.main(["--iteration", str(tmp_path)])
    assert code == 1


def test_allow_partial_stamps_the_summary_instead_of_hiding_it(tmp_path, capsys):
    write_run(tmp_path, 5, "with_skill", 1,
              rows=[row("A5-1", "no absence claim", "discriminating", True)])
    code = aggregate.main(["--iteration", str(tmp_path), "--allow-partial"])
    assert code == 0
    md = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "PARTIAL" in md and "eval-5 baseline" in md


def test_the_benchmark_patch_fixes_both_known_defects(iteration):
    s = aggregate.summarise(iteration, DOC)
    plugin = {"metadata": {"runs_per_configuration": 3},
              "run_summary": {"delta": {"pass_rate": "-0.12"}}, "notes": []}
    patched = aggregate.patch_benchmark(plugin, s)
    assert patched["metadata"]["runs_per_configuration"] != 3
    assert isinstance(patched["metadata"]["runs_per_configuration"], dict)
    assert any("with_skill − baseline" in n for n in patched["notes"])


def test_the_written_record_contains_no_hand_typed_number(iteration):
    aggregate.main(["--iteration", str(iteration), "--write-record",
                    "--record-path", str(iteration / "record.md")])
    text = (iteration / "record.md").read_text(encoding="utf-8")
    assert "Generated by evals/aggregate.py" in text
    assert "3/3" in text
