"""Tests for evals/schema.py — the one definition of the harness's closed sets.

A schema module is easy to write a test for that cannot fail: assert the tuple
equals the tuple. Every test here is instead anchored to something outside the
module — the skill's own `modes/` directory, the linter's rules, the other files
in `evals/` — so that a set drifting out of step with what uses it goes red.

The path insert is this module's own, not conftest's: Task 1 owns the conftest
change, and until it lands these tests still have to run.
"""
import ast
import pathlib
import sys

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals import schema  # noqa: E402

EVALS_DIR = _REPO_ROOT / "evals"

CLOSED_SETS = ("ARMS", "BASELINE_KINDS", "ROLES", "EXPECTED_BASELINE", "MODES",
               "EVAL_KEYS", "REQUIRED_EVAL_KEYS", "ASSERTION_KEYS",
               "REQUIRED_ASSERTION_KEYS", "RETIRED_KEYS")


@pytest.mark.parametrize("name", CLOSED_SETS)
def test_every_closed_set_is_an_immutable_tuple_of_unique_names(name):
    """A list here is a closed set any importer can quietly reopen."""
    value = getattr(schema, name)
    assert isinstance(value, tuple), f"{name} is {type(value).__name__}, not a tuple"
    assert value, f"{name} is empty"
    assert all(isinstance(v, str) and v.strip() for v in value)
    assert len(set(value)) == len(value), f"{name} repeats a member"


def test_there_are_exactly_two_arms_and_baseline_sorts_first():
    """`aggregate_benchmark.py` deltas configs[0] against configs[1] in SORTED
    order and discovers them by listing directories. Two names keep the headline
    comparison well-defined; baseline sorting first is what makes the plugin's
    delta `baseline - with_skill` rather than an unpredictable direction."""
    assert schema.ARMS == ("baseline", "with_skill")
    assert list(schema.ARMS) == sorted(schema.ARMS)


def test_the_kind_of_baseline_is_a_field_and_never_an_arm_name():
    """The two baseline kinds must not leak into ARMS -- a third directory name
    is the exact failure the two-arm rule exists to prevent."""
    assert set(schema.BASELINE_KINDS) == {"old_skill", "no_skill"}
    assert not set(schema.BASELINE_KINDS) & set(schema.ARMS)


def test_the_modes_are_the_skill_s_own_four_modes():
    """Read from disk, not re-typed: a fifth mode added to the skill without a
    scenario, or a mode renamed, must break this rather than leave the harness
    unable to express an eval for it."""
    on_disk = sorted(p.stem for p in (_REPO_ROOT / "modes").glob("*.md"))
    assert on_disk, "modes/ has no mode documents -- the fixture, not the schema, moved"
    assert sorted(schema.MODES) == on_disk


def test_not_exercised_is_an_expected_baseline_and_not_a_role():
    """`passed: null` is a third outcome, never a pass and never a role. If it
    were a role it could be scored; it is excluded from the denominator instead."""
    assert set(schema.EXPECTED_BASELINE) == {"pass", "fail", "not_exercised"}
    assert set(schema.ROLES) == {"discriminating", "regression"}
    assert "not_exercised" not in schema.ROLES


@pytest.mark.parametrize("required,allowed", [
    ("REQUIRED_EVAL_KEYS", "EVAL_KEYS"),
    ("REQUIRED_ASSERTION_KEYS", "ASSERTION_KEYS"),
])
def test_a_required_key_is_always_an_allowed_key(required, allowed):
    """Otherwise a record is unsatisfiable: supplying the key trips UNKNOWN_KEY
    and omitting it trips MISSING_KEY."""
    missing = set(getattr(schema, required)) - set(getattr(schema, allowed))
    assert not missing, f"{required} demands {sorted(missing)}, which {allowed} forbids"


def test_the_fields_the_discrimination_rules_read_are_all_required():
    """`role`, `expected_baseline`, `falsifier` and `checker` are what
    NON_DISCRIMINATING_BY_CONSTRUCTION, NO_FALSIFIER and TWIN_MISSING_CHECKER
    are decided from. If any of them were optional, omitting it would be the way
    round the lint."""
    for key in ("id", "role", "expected_baseline", "falsifier", "checker"):
        assert key in schema.REQUIRED_ASSERTION_KEYS, f"{key} is optional"
    for key in ("id", "mode", "baseline_kind", "scenario", "assertions"):
        assert key in schema.REQUIRED_EVAL_KEYS, f"{key} is optional"


def test_a_retired_assertion_records_why_and_what_replaced_it():
    assert set(schema.RETIRED_KEYS) >= {"id", "reason", "replaced_by"}


@pytest.mark.parametrize("shrug", ["no", "it fails", "wrong output", "bad answer",
                                   "does not pass"])
def test_the_falsifier_floor_is_above_a_shrug(shrug):
    """The floor is not decoration: every string below is something an author
    has actually written into a falsifier field. Lower the constant and one of
    them becomes acceptable evidence that the assertion can fail."""
    assert isinstance(schema.MIN_FALSIFIER_CHARS, int)
    assert len(shrug) < schema.MIN_FALSIFIER_CHARS


def _module_level_assignments(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def test_no_other_harness_module_re_spells_a_closed_set():
    """One definition. A second module assigning ROLES or ARMS at module level is
    how the harness comes to hold two answers to the same question -- import it
    from schema, or the rename that fixes one leaves the other measuring a value
    nobody emits."""
    owned = set(CLOSED_SETS) | {"MIN_FALSIFIER_CHARS"}
    offenders = []
    for path in sorted(EVALS_DIR.glob("*.py")):
        if path.name == "schema.py":
            continue
        for name in sorted(_module_level_assignments(path) & owned):
            offenders.append(f"{path.name}:{name}")
    assert offenders == [], f"re-spelled closed sets: {offenders}"


@pytest.mark.parametrize("prefix", ["/Users/", "/home/", "/private/tmp",
                                    "/var/folders/", "/tmp/"])
def test_no_harness_module_carries_a_machine_specific_absolute_path(prefix):
    """A committed absolute path passes on the machine that wrote it and fails
    everywhere else, usually blaming an unrelated module. Paths are computed from
    __file__ or come in as a parameter."""
    # EVERY committed file under evals/, not only *.py. The scan used to glob
    # "*.py", and the file that actually burned this project was a test FIXTURE
    # (.yaml) carrying a scratchpad path: `make check` then failed on every
    # machine but the one that wrote it, with a message naming an unrelated
    # module. Scenarios, fixtures, assertions.yaml and the stub are exactly the
    # files most likely to grow a path someone pasted from their own shell.
    import subprocess  # local: only this test shells out
    listed = subprocess.run(["git", "ls-files", "evals"], cwd=str(_REPO_ROOT),
                            capture_output=True, text=True, encoding="utf-8")
    assert listed.returncode == 0, "could not list committed evals files"
    committed = [_REPO_ROOT / rel for rel in listed.stdout.split() if rel.strip()]
    assert len(committed) > 20, (
        f"only {len(committed)} committed files found under evals/ — the scan is "
        f"not reaching the tree it is supposed to guard")
    for path in committed:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue                     # a binary fixture cannot carry a path
        assert prefix not in text, \
            f"{path.relative_to(_REPO_ROOT)} carries the machine-specific path {prefix!r}"
