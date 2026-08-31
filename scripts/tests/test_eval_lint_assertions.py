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


# ---- what the iteration-2 pilot forced into the lint ------------------------

def test_discriminating_plus_not_exercised_is_rejected_like_pass():
    """`expected_baseline: not_exercised` on a guard is as non-discriminating as
    `pass`, and the lint only rejected `pass`.

    "Not exercised" is not "fail". An author who writes it is saying the
    baseline never even reaches the branch — so passing it says nothing about
    the skill, which is the exact sentence the `pass` rule already carries.
    Twelve of the iteration-2 pilot's 26 guards came back not-exercised; the
    lint had no way to say that was declared in advance.
    """
    d = doc()
    d["evals"][0]["assertions"][0]["expected_baseline"] = "not_exercised"
    out = la.lint(d, scenario_root=pathlib.Path("evals"), checkers=CHECKERS,
                  twins=TWINS)
    assert any(f.startswith("NON_DISCRIMINATING_BY_CONSTRUCTION") for f in out), out
    assert any("not_exercised" in f for f in out), (
        "the finding must name the value, or the author cannot see which rule "
        "they tripped")


# ---- the eval may not quietly re-role itself into measuring nothing ---------
#
# Every fix the iteration-2 pilot pointed at is a REDUCTION: re-role the guard,
# scope it to one arm, retire it. Each is honest on its own and the sequence has
# an obvious terminus — an eval with no discriminating assertions at all, which
# exits 0 because there is nothing left that could fail. Somebody has to notice
# a mode losing its last guard, and "somebody" cannot be a person reading a
# diff.

def _mode_doc(**overrides):
    d = doc()
    d["evals"][0]["mode"] = "discover"
    d["evals"][1]["mode"] = "discover"
    d.update(overrides)
    return d


def _lint(d):
    return la.lint(d, scenario_root=pathlib.Path("evals"), checkers=CHECKERS,
                   twins=TWINS)


def test_a_mode_that_lost_its_last_guard_is_a_finding():
    d = _mode_doc()
    for a in d["evals"][0]["assertions"] + d["evals"][1]["assertions"]:
        a["role"] = "regression"
        a["expected_baseline"] = "pass"
    out = _lint(d)
    assert any(f.startswith("MODE_HAS_NO_GUARD") for f in out), out
    assert any("discover" in f for f in out)


def test_declaring_the_mode_makes_it_a_statement_rather_than_an_accident():
    d = _mode_doc(coverage={"modes_without_a_guard": {
        "discover": "Every discover property the harness can check is one the "
                    "bare model already satisfies; measured, iteration-2."}})
    for a in d["evals"][0]["assertions"] + d["evals"][1]["assertions"]:
        a["role"] = "regression"
        a["expected_baseline"] = "pass"
    assert not any(f.startswith("MODE_HAS_NO_GUARD") for f in _lint(d))


def test_a_declaration_too_thin_to_check_is_rejected():
    d = _mode_doc(coverage={"modes_without_a_guard": {"discover": "n/a"}})
    for a in d["evals"][0]["assertions"] + d["evals"][1]["assertions"]:
        a["role"] = "regression"
        a["expected_baseline"] = "pass"
    assert any(f.startswith("THIN_COVERAGE_REASON") for f in _lint(d))


def test_a_stale_declaration_is_also_a_finding():
    """Symmetric on purpose. A mode listed as having no guard, which then gets
    one, leaves a note claiming the eval is weaker than it is — and the next
    person re-roles the new guard away without ever seeing a red line."""
    d = _mode_doc(coverage={"modes_without_a_guard": {
        "discover": "Every discover property the harness can check is one the "
                    "bare model already satisfies; measured, iteration-2."}})
    out = _lint(d)   # the fixture's discover guards are still discriminating
    assert any(f.startswith("STALE_COVERAGE_DECLARATION") for f in out), out


def test_an_unknown_mode_in_the_declaration_is_caught():
    d = _mode_doc(coverage={"modes_without_a_guard": {
        "discovery": "a typo that would silently exempt nothing at all, while "
                     "looking exactly like an exemption that works."}})
    assert any(f.startswith("UNKNOWN_MODE") for f in _lint(d))


def test_an_assertion_scoped_to_one_arm_does_not_count_as_a_guard():
    """arms: [with_skill] means the baseline is never graded on it. It is an
    audit of the skill, not a comparison, and counting it would let a mode look
    guarded while nothing compares the arms."""
    d = _mode_doc()
    for a in d["evals"][0]["assertions"] + d["evals"][1]["assertions"]:
        a["arms"] = ["with_skill"]
    out = _lint(d)
    assert any(f.startswith("MODE_HAS_NO_GUARD") for f in out), out


def test_an_unknown_top_level_key_is_caught():
    """`coverage:` is load-bearing — it is how a mode declares it has no guard.
    A typo'd `coverages:` would parse fine, exempt nothing, and look exactly
    like a working declaration. Eval and assertion keys were already checked;
    the document's own were not."""
    d = _mode_doc(coverages={"modes_without_a_guard": {}})
    out = _lint(d)
    assert any(f.startswith("UNKNOWN_KEY") and "coverages" in f for f in out), out


def test_a_not_exercised_assertion_must_carry_its_reason_in_the_file():
    """`expected_baseline: not_exercised` says the baseline cannot even reach
    this assertion. That is the surprising declaration in the whole schema —
    it removes a comparison — so the reason belongs next to it, where the next
    reader of assertions.yaml will see it. A commit message does not survive
    into the file."""
    d = _mode_doc()
    a = d["evals"][0]["assertions"][0]
    a.update(role="regression", expected_baseline="not_exercised",
             arms=["with_skill"])
    out = _lint(d)
    assert any(f.startswith("UNEXPLAINED_SCOPING") for f in out), out
    a["note"] = ("The checker reads job-hunt's own journal, which a bare agent "
                 "never writes; measured not-exercised in the iteration-2 pilot.")
    assert not any(f.startswith("UNEXPLAINED_SCOPING") for f in _lint(d))


# ---- the same rule one level down, which mutation testing found untested ----
#
# The MODE-level rules above were tested; the EVAL-level ones were not, and the
# data test only reads the real assertions.yaml — which is currently clean, so
# it cannot notice the rule being switched off. Deleting EVAL_HAS_NO_GUARD and
# its stale-declaration counterpart left the whole suite green.

def _guardless(d):
    for a in d["evals"][0]["assertions"] + d["evals"][1]["assertions"]:
        a["role"] = "regression"
        a["expected_baseline"] = "pass"
    return d


def test_an_eval_that_lost_its_last_guard_is_a_finding():
    out = _lint(_guardless(_mode_doc()))
    assert any(f.startswith("EVAL_HAS_NO_GUARD") for f in out), out


def test_declaring_the_eval_makes_it_a_statement():
    d = _guardless(_mode_doc(coverage={
        "modes_without_a_guard": {
            "discover": "Every discover property the harness can check is one "
                        "the bare model already satisfies; measured 2026."},
        "evals_without_a_guard": {
            5: "Decoy by design: an ordinary successful round, so there is no "
               "defence here for the baseline to fail.",
            7: "Its guard reads job-hunt's own journal and can only audit the "
               "with_skill arm; measured in the iteration-2 pilot."}}))
    out = _lint(d)
    assert not any(f.startswith("EVAL_HAS_NO_GUARD") for f in out), out


def test_a_stale_eval_declaration_is_a_finding():
    d = _mode_doc(coverage={"evals_without_a_guard": {
        5: "Declared guard-free, but eval 5 still hosts a discriminating "
           "assertion in this fixture."}})
    out = _lint(d)
    assert any(f.startswith("STALE_COVERAGE_DECLARATION") and "5" in f
               for f in out), out


def test_a_thin_eval_declaration_is_rejected():
    d = _guardless(_mode_doc(coverage={"evals_without_a_guard": {5: "decoy"}}))
    assert any(f.startswith("THIN_COVERAGE_REASON") for f in _lint(d))


def test_declaring_an_eval_that_does_not_exist_is_caught():
    d = _guardless(_mode_doc(coverage={"evals_without_a_guard": {
        99: "An id nobody will ever look up, exempting nothing at all while "
            "looking exactly like an exemption that works."}}))
    assert any(f.startswith("UNKNOWN_EVAL") for f in _lint(d))
