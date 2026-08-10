import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
MAKEFILE = ROOT / "Makefile"
WORKFLOW = ROOT / ".github" / "workflows" / "checks.yml"


def test_both_entry_points_exist():
    assert MAKEFILE.is_file() and WORKFLOW.is_file()


def test_the_makefile_and_the_workflow_run_the_same_three_checks():
    """Two entry points that run different things is worse than one: the local
    one passes, the remote one fails, and nobody knows which is authoritative."""
    mk, wf = MAKEFILE.read_text(encoding="utf-8"), WORKFLOW.read_text(encoding="utf-8")
    for needle in ("pytest scripts/tests", "check_skill_lossless.py",
                   "check_conventions.py"):
        assert needle in mk, f"Makefile does not run {needle}"
        assert needle in wf, f"checks.yml does not run {needle}"


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
        return
    for f in (MAKEFILE, WORKFLOW):
        assert "-f scripts/check_conventions.py" not in f.read_text(encoding="utf-8"), (
            f"{f.name} still guards check_conventions.py behind a file test — the "
            f"script exists now; run it unconditionally")
