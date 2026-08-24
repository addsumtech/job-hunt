"""The runbook is the one executable-by-a-human part of this harness.

It is tested like code because it is the only place the 120-run procedure
exists: a step that quietly goes missing costs a matrix.
"""
import pathlib
import re
import subprocess
import sys

import pytest
import yaml

from evals import runlib

REPO = pathlib.Path(__file__).resolve().parents[2]
RUNBOOK = (REPO / "evals" / "run.md").read_text(encoding="utf-8") \
    if (REPO / "evals" / "run.md").is_file() else ""
DOC = yaml.safe_load((REPO / "evals" / "assertions.yaml").read_text(
    encoding="utf-8"))


def test_the_runbook_names_every_eval():
    for ev in DOC["evals"]:
        assert ev["name"] in RUNBOOK, f"{ev['name']} is not in the runbook"


def test_the_runbook_states_the_output_contract_in_full():
    for item in runlib.OUTPUT_CONTRACT:
        assert item in RUNBOOK


def test_the_runbook_orders_the_pilot_before_the_matrix():
    assert RUNBOOK.index("Stage 1 — pilot") < RUNBOOK.index("Stage 2 — the matrix")


def test_the_runbook_records_the_run_count_and_does_not_predict_the_cost():
    assert "120" in RUNBOOK
    assert re.search(r"not a prediction", RUNBOOK)


def test_the_runbook_forbids_a_login_in_the_discover_stage():
    assert "do not attempt a login" in RUNBOOK.lower()


def test_the_makefile_exposes_both_eval_targets():
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    assert "eval-lint:" in makefile
    assert "eval-verify:" in makefile


def test_ci_runs_the_assertion_lint():
    workflow = (REPO / ".github" / "workflows" / "checks.yml").read_text(
        encoding="utf-8")
    assert "evals/lint_assertions.py" in workflow


def test_the_readme_points_at_the_harness():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "evals/README.md" in readme


# ---- added beyond the plan ---------------------------------------------------

def test_every_makefile_recipe_line_is_tab_indented():
    """A Makefile recipe indented with spaces dies with `missing separator`, and
    the eval targets were appended by hand. Checked here rather than discovered
    when someone first runs `make eval-lint`."""
    lines = (REPO / "Makefile").read_text(encoding="utf-8").split("\n")
    offenders = []
    in_recipe = False
    for i, line in enumerate(lines, 1):
        if re.match(r"^[A-Za-z0-9_.-]+:", line):
            in_recipe = True
            continue
        if not line.strip():
            in_recipe = False
            continue
        if in_recipe and line.startswith("    "):
            offenders.append(f"{i}: {line!r}")
    assert not offenders, "space-indented recipe lines: " + "; ".join(offenders)


def test_the_runbook_does_not_promise_ci_runs_the_matrix():
    """`eval-verify` needs a results tree that only LLM runs produce. If CI ever
    runs it, a missing tree becomes a green tick that measured nothing — the
    exact failure mode this whole plan exists to remove."""
    workflow = (REPO / ".github" / "workflows" / "checks.yml").read_text(
        encoding="utf-8")
    assert "eval-verify" not in workflow
    assert "evals/grade.py" not in workflow
    assert "evals/aggregate.py" not in workflow


def test_the_runbook_names_the_guard_evals_the_pilot_covers():
    """The pilot is only cheap if it covers the evals that carry guards. If a
    guard eval is left out, its useless assertion is not found until the
    aggregate — which is iteration-1's mistake with extra steps."""
    guard_evals = sorted({e["name"] for e in DOC["evals"]
                          for a in e.get("assertions") or []
                          if a.get("role") == "discriminating"})
    stage1 = RUNBOOK.split("Stage 1 — pilot")[1].split("Stage 2 —")[0]
    missing = [n for n in guard_evals if n not in stage1]
    assert not missing, (
        f"the pilot stage does not name these guard-carrying evals: {missing}")


# ---- the CLI path, which 1744 passing tests could not see --------------------

@pytest.mark.parametrize("module", ["grade", "aggregate", "check_discrimination",
                                    "lint_grading", "lint_assertions"])
def test_every_eval_module_runs_as_a_script(module):
    """pytest imports `evals` as a package from the repo root, so `from evals
    import ...` always resolves under test. Run the same file as a SCRIPT and
    sys.path[0] is evals/ instead, where the package does not exist.

    Found by actually running `make eval-verify`: grade.py died with
    ModuleNotFoundError. That traceback exits 1 — which is these tools' code for
    "findings" — so a broken invocation and a real finding are indistinguishable
    to the Makefile, to CI, and to anyone reading an exit code.

    The runbook and both make targets invoke these by path, so this is the way
    they are actually used.
    """
    argv = [sys.executable, str(REPO / "evals" / f"{module}.py")]
    if module != "lint_assertions":
        argv += ["--iteration", "/tmp/job-hunt-no-such-iteration"]
    proc = subprocess.run(argv, capture_output=True, text=True, cwd=str(REPO))
    assert "ModuleNotFoundError" not in proc.stderr, (
        f"{module}.py cannot run as a script:\n{proc.stderr}")
    assert "Traceback" not in proc.stderr, (
        f"{module}.py crashed rather than reporting:\n{proc.stderr}")
    if module != "lint_assertions":
        assert proc.returncode == 2, (
            f"{module}.py on an absent results tree exited {proc.returncode}; "
            f"2 means could-not-run, and 0 or 1 would be a claim about data "
            f"that is not there")
        assert proc.stderr.strip(), f"{module}.py exited 2 silently"
