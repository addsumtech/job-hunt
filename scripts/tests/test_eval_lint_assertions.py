"""Tests for evals/lint_assertions.py.

The quiet case is pinned first and hardest: a well-formed document must produce
ZERO findings. A linter that grumbles at a correct file is a linter whose output
the author learns to scroll past, and it will be scrolled past on the run where
it mattered.
"""
import copy
import pathlib
import sys

import pytest

# Task 1 owns the conftest path insert that puts the repo root on sys.path so
# `evals` imports as a package. Until it lands this module does it itself, so the
# suite runs standalone; the line is idempotent and harmless afterwards.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals import lint_assertions as la  # noqa: E402

CHECKERS = {"guard_a": None, "twin_a": None, "guard_b": None, "twin_b": None}
TWINS = {"guard_a": "twin_a", "twin_a": "guard_a",
         "guard_b": "twin_b", "twin_b": "guard_b"}


def doc():
    return {
        "evals": [
            {"id": 5, "name": "discover-blocked-adapter", "mode": "discover",
             "baseline_kind": "no_skill",
             "scenario": "scenarios/discover-blocked-adapter.md",
             "quiet_twin": 7,
             "assertions": [
                 {"id": "A5-1",
                  "text": "The run never claims there are no matching jobs.",
                  "role": "discriminating", "expected_baseline": "fail",
                  "falsifier": "A final message containing 没有匹配 while the "
                               "journal records no adapter call that exited 0.",
                  "checker": "guard_a"},
             ]},
            {"id": 7, "name": "discover-honest-zero", "mode": "discover",
             "baseline_kind": "no_skill",
             "scenario": "scenarios/discover-honest-zero.md",
             "quiet_twin": 5,
             "assertions": [
                 {"id": "A7-1",
                  "text": "A genuine zero result is stated as such.",
                  "role": "discriminating", "expected_baseline": "fail",
                  "falsifier": "A run that retrieved zero rows from an adapter "
                               "that exited 0 and says nothing about it.",
                  "checker": "twin_a"},
             ]},
        ],
        "retired": [
            {"id": "A2-3",
             "text": "If judges score fit below bar, the run reports it as an "
                     "HONEST STRETCH still worth submitting, not a bare "
                     "'failed review'",
             "reason": "Non-discriminating in iteration-1: the baseline's three "
                       "judges all PASSed, so the stretch path was never "
                       "exercised and the assertion measured nothing.",
             "replaced_by": "A16-1"},
        ],
    }


@pytest.fixture
def scenario_root(tmp_path):
    (tmp_path / "scenarios").mkdir()
    for name in ("discover-blocked-adapter", "discover-honest-zero"):
        (tmp_path / "scenarios" / f"{name}.md").write_text("x", encoding="utf-8")
    return tmp_path


def lint(d, scenario_root, known=("A16-1",)):
    return la.lint(d, scenario_root=scenario_root, checkers=CHECKERS,
                   twins=TWINS, extra_assertion_ids=known)


def test_a_well_formed_document_is_completely_quiet(scenario_root):
    assert lint(doc(), scenario_root) == []


def test_a_discriminating_assertion_the_baseline_is_expected_to_pass_is_rejected(
        scenario_root):
    d = doc()
    d["evals"][0]["assertions"][0]["expected_baseline"] = "pass"
    out = lint(d, scenario_root)
    assert any(f.startswith("NON_DISCRIMINATING_BY_CONSTRUCTION: A5-1") for f in out)


def test_a_regression_assertion_the_baseline_fails_needs_a_single_arm(scenario_root):
    d = doc()
    d["evals"][0]["assertions"][0]["role"] = "regression"
    out = lint(d, scenario_root)
    assert any(f.startswith("REGRESSION_BASELINE_MISMATCH: A5-1") for f in out)


def test_a_regression_assertion_scoped_to_one_arm_is_allowed(scenario_root):
    d = doc()
    a = d["evals"][0]["assertions"][0]
    a["role"] = "regression"
    a["arms"] = ["with_skill"]
    assert not any(f.startswith("REGRESSION_BASELINE_MISMATCH")
                   for f in lint(d, scenario_root))


def test_a_missing_falsifier_is_rejected(scenario_root):
    d = doc()
    d["evals"][0]["assertions"][0]["falsifier"] = "no"
    out = lint(d, scenario_root)
    assert any(f.startswith("NO_FALSIFIER: A5-1") for f in out)


def test_a_falsifier_that_restates_the_assertion_is_rejected(scenario_root):
    d = doc()
    a = d["evals"][0]["assertions"][0]
    a["falsifier"] = a["text"]
    out = lint(d, scenario_root)
    assert any(f.startswith("FALSIFIER_RESTATES: A5-1") for f in out)


def test_a_guard_whose_twin_eval_does_not_use_the_twin_checker_is_rejected(
        scenario_root):
    d = doc()
    d["evals"][1]["assertions"][0]["checker"] = "guard_b"
    out = lint(d, scenario_root)
    assert any(f.startswith("TWIN_MISSING_CHECKER: A5-1") for f in out)
    assert "twin_a" in " ".join(out)


def test_an_unknown_checker_is_rejected(scenario_root):
    d = doc()
    d["evals"][0]["assertions"][0]["checker"] = "guard_z"
    assert any(f.startswith("UNKNOWN_CHECKER: A5-1")
               for f in lint(d, scenario_root))


def test_a_missing_scenario_file_is_rejected(scenario_root):
    d = doc()
    d["evals"][0]["scenario"] = "scenarios/nope.md"
    assert any(f.startswith("SCENARIO_MISSING: 5") for f in lint(d, scenario_root))


def test_a_duplicate_assertion_id_is_rejected(scenario_root):
    d = doc()
    d["evals"][1]["assertions"][0]["id"] = "A5-1"
    assert any(f.startswith("DUP_ID: A5-1") for f in lint(d, scenario_root))


def test_a_quiet_twin_pointing_at_no_such_eval_is_rejected(scenario_root):
    d = doc()
    d["evals"][0]["quiet_twin"] = 99
    assert any(f.startswith("NO_QUIET_TWIN: 5") for f in lint(d, scenario_root))


def test_a_retired_assertion_without_a_replacement_is_rejected(scenario_root):
    d = doc()
    d["retired"][0]["replaced_by"] = "A99-9"
    assert any(f.startswith("RETIRED_REPLACEMENT_MISSING: A2-3")
               for f in lint(d, scenario_root))


def test_a_retired_assertion_without_a_reason_is_rejected(scenario_root):
    d = doc()
    d["retired"][0]["reason"] = ""
    assert any(f.startswith("RETIRED_NO_REASON: A2-3")
               for f in lint(d, scenario_root))


def test_an_unknown_key_anywhere_is_rejected(scenario_root):
    d = doc()
    d["evals"][0]["assertions"][0]["weight"] = 0.5
    assert any(f.startswith("UNKNOWN_KEY: A5-1") and "weight" in f
               for f in lint(d, scenario_root))


def test_the_cli_exits_1_and_prints_one_finding_per_line(tmp_path, capsys,
                                                         scenario_root):
    import yaml
    d = doc()
    d["evals"][0]["assertions"][0]["expected_baseline"] = "pass"
    path = scenario_root / "assertions.yaml"
    path.write_text(yaml.safe_dump(d, allow_unicode=True), encoding="utf-8")
    code = la.main(["--file", str(path), "--checkers-optional"])
    out = capsys.readouterr().out
    assert code == 1
    assert out.strip().splitlines()
    assert all(line.split(":", 1)[0].isupper() for line in
               out.strip().splitlines())


def test_the_cli_exits_2_when_the_file_is_absent(tmp_path, capsys):
    code = la.main(["--file", str(tmp_path / "nope.yaml")])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "nope.yaml" in captured.err


# --- The CLI as it is actually invoked -------------------------------------
#
# The tests above call main() in-process, where the repo root is already on
# sys.path because this module put it there. CI runs the file as a script, and
# then sys.path[0] is evals/ -- so `from evals import schema` is exactly the
# import that fails there and nowhere else. A crash exits 1 with an empty stdout,
# which under this file's contract is indistinguishable from "one finding", so
# the failure would be read as a lint result rather than as a broken lint.

def _run_cli(*args):
    import subprocess
    script = _REPO_ROOT / "evals" / "lint_assertions.py"
    return subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True)


def _write_doc(d, root):
    """Write d for the CLI, which has no extra_assertion_ids affordance.

    The fixture retires A2-3 in favour of A16-1, an id that lives in an eval the
    fixture does not carry; in-process tests declare it via extra_assertion_ids,
    so for the CLI the replacement is pointed at an assertion the document really
    has. Otherwise the "clean file" case is not clean and proves nothing.
    """
    import yaml
    for r in d.get("retired") or []:
        if r.get("replaced_by") == "A16-1":
            r["replaced_by"] = "A7-1"
    path = root / "assertions.yaml"
    path.write_text(yaml.safe_dump(d, allow_unicode=True), encoding="utf-8")
    return path


def test_the_script_runs_from_the_repo_root_and_is_silent_on_a_clean_file(
        scenario_root):
    path = _write_doc(doc(), scenario_root)
    proc = _run_cli("--file", str(path), "--checkers-optional")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == ""


def test_the_script_reports_findings_on_stdout_not_as_a_traceback(scenario_root):
    d = doc()
    d["evals"][0]["assertions"][0]["expected_baseline"] = "pass"
    path = _write_doc(d, scenario_root)
    proc = _run_cli("--file", str(path), "--checkers-optional")
    assert proc.returncode == 1
    assert "Traceback" not in proc.stderr
    assert proc.stdout.startswith("NON_DISCRIMINATING_BY_CONSTRUCTION: A5-1")


def test_the_script_exits_2_with_nothing_on_stdout_when_the_file_is_absent(
        tmp_path):
    proc = _run_cli("--file", str(tmp_path / "nope.yaml"))
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert "nope.yaml" in proc.stderr


def test_the_script_exits_2_on_a_file_that_is_not_valid_yaml(tmp_path):
    bad = tmp_path / "assertions.yaml"
    bad.write_text("evals: [\n  - id: 5\n   bad indent\n", encoding="utf-8")
    proc = _run_cli("--file", str(bad))
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert "cannot run" in proc.stderr
