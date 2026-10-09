import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
MAKEFILE = ROOT / "Makefile"
WORKFLOW = ROOT / ".github" / "workflows" / "checks.yml"


def test_both_entry_points_exist():
    assert MAKEFILE.is_file() and WORKFLOW.is_file()


# Every check `make check` runs, which checks.yml must run too. Adding one here
# is red until both entry points carry it, which is the point: a check wired
# into only one of them is a check whose verdict depends on who ran it.
GATE_COMMANDS = (
    "pytest scripts/tests",
    "check_skill_lossless.py",
    "check_conventions.py",
    "check_hidden_chars.py",
)


def test_the_makefile_and_the_workflow_run_the_same_checks():
    """Two entry points that run different things is worse than one: the local
    one passes, the remote one fails, and nobody knows which is authoritative."""
    mk, wf = MAKEFILE.read_text(encoding="utf-8"), WORKFLOW.read_text(encoding="utf-8")
    for needle in GATE_COMMANDS:
        assert needle in mk, f"Makefile does not run {needle}"
        assert needle in wf, f"checks.yml does not run {needle}"


def test_every_gate_command_is_reached_by_the_check_target():
    """A target defined in the Makefile but left out of `check` is one nobody
    runs before committing, and the file still lists it so it looks wired."""
    import re as _re

    mk = MAKEFILE.read_text(encoding="utf-8")
    bodies, current = {}, None
    for line in mk.splitlines():
        head = _re.match(r"([A-Za-z0-9_.\-]+):", line)
        if head and not line[:1].isspace():
            current = head.group(1)
            bodies.setdefault(current, [])
        elif current is not None and line.startswith("\t"):
            bodies[current].append(line)
        elif not line.strip():
            current = None
    assert bodies.get("test"), "Makefile parse failed; this is not a real finding"

    check_line = next(l for l in mk.splitlines() if l.startswith("check:"))
    reached = " ".join(body for target in check_line.split(":", 1)[1].split()
                       for body in bodies.get(target, []))
    for needle in GATE_COMMANDS:
        assert needle in reached, f"`make check` does not reach {needle}"


def test_ci_fetches_enough_history_for_the_lossless_baseline():
    """check_skill_lossless resolves a git TAG. A default shallow checkout has no
    tags, so the check exits 2 — 'could not read the baseline', which is exactly
    why that is a different exit code from 'content was lost'."""
    assert "fetch-depth: 0" in WORKFLOW.read_text(encoding="utf-8")


def test_the_conventions_guard_disappears_when_the_script_lands():
    """Plan 2 ships check_conventions.py. This test is red from that moment until
    both entry points stop guarding it — because a CI step that keeps skipping is
    a CI step that is not there, and spec §10 requires an expired market table to
    fail the build."""
    if not (ROOT / "scripts" / "check_conventions.py").exists():
        pytest.skip("check_conventions.py has not landed yet; nothing to unguard")
    for f in (MAKEFILE, WORKFLOW):
        assert "-f scripts/check_conventions.py" not in f.read_text(encoding="utf-8"), (
            f"{f.name} still guards check_conventions.py behind a file test — the "
            f"script exists now; run it unconditionally")


MUTANTS_WORKFLOW = ROOT / ".github" / "workflows" / "mutants.yml"


def test_mutation_testing_has_both_entry_points():
    """Same rule as the three checks above: a local entry point with no remote
    twin is one nobody runs, and a remote one with no local twin is one nobody
    can reproduce before pushing."""
    assert MUTANTS_WORKFLOW.is_file()
    assert "mutants:" in MAKEFILE.read_text(encoding="utf-8")
    assert "scripts/mutants.py --ci" in MAKEFILE.read_text(encoding="utf-8")
    assert "scripts/mutants.py --ci" in MUTANTS_WORKFLOW.read_text(encoding="utf-8")


def test_mutation_testing_is_not_wired_into_the_fast_gate():
    """It copies the repo and re-runs the suite once per mutant — minutes to
    hours. A slow step inside the gate everyone runs before every commit is how a
    check gets commented out, and a commented-out check is worse than none
    because the Makefile still lists it."""
    mk = MAKEFILE.read_text(encoding="utf-8")
    check_line = next(l for l in mk.splitlines() if l.startswith("check:"))
    assert "mutants" not in check_line, "make check must stay seconds, not hours"
    assert "mutants.py" not in WORKFLOW.read_text(encoding="utf-8"), \
        "checks.yml runs on every push and must not carry the mutation job"


def test_the_mutation_matrix_covers_exactly_the_default_targets():
    """CI runs one job per target file. A target added to mutants.py but not to
    the matrix is a file nobody mutates on schedule, and nothing would say so."""
    import yaml

    import mutants

    job = yaml.safe_load(MUTANTS_WORKFLOW.read_text(encoding="utf-8"))["jobs"]["mutants"]
    assert job["strategy"]["matrix"]["target"] == list(mutants.DEFAULT_TARGETS)
    assert job["strategy"]["fail-fast"] is False, \
        "one file's new survivor must not cancel the other files' runs"
    assert "--targets ${{ matrix.target }}" in MUTANTS_WORKFLOW.read_text(encoding="utf-8")


def test_ci_cannot_rewrite_the_mutation_baseline():
    """`--record` in CI would let the harness update its own baseline, which
    reports success by forgetting what it used to catch."""
    assert "--record" not in MUTANTS_WORKFLOW.read_text(encoding="utf-8")
