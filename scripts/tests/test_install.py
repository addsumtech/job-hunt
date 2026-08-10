import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
LINKS = [pathlib.Path.home() / ".claude" / "skills" / "job-hunt",
         pathlib.Path.home() / ".codex" / "skills" / "job-hunt"]


@pytest.mark.parametrize("link", LINKS, ids=lambda p: p.parent.parent.name)
def test_the_runtime_resolves_the_skill(link):
    if not link.parent.is_dir():
        pytest.skip(f"{link.parent} does not exist on this machine")
    assert link.is_symlink(), f"{link} is not a symlink — a copy would drift"
    assert link.resolve() == ROOT
    assert (link / "SKILL.md").is_file()
    assert (link / "modes" / "apply.md").is_file()
    assert (link / "scripts" / "check_apply.py").is_file()


def test_the_old_skill_is_archived_but_not_symlinked():
    """Two skills with overlapping descriptions fight for the trigger and the
    user has to know which to invoke.

    Machine-local, like the test above: it inspects an install, not the repo. It skips
    where there is no skills directory at all — a fresh CI runner — because there is
    then no install to protect. It does NOT skip merely because the archive is missing:
    a machine that has the skills directory and has lost job-application has lost the
    lossless baseline, and that is the whole thing this is here to catch."""
    skills = pathlib.Path.home() / ".claude" / "skills"
    if not skills.is_dir():
        pytest.skip(f"{skills} does not exist on this machine — nothing is installed here")
    old = skills / "job-application"
    assert old.is_dir(), "the archive was removed; it is the migration's baseline"
    assert not old.is_symlink()


def test_this_module_says_out_loud_when_it_checked_nothing(record_property):
    """Every test in this file skips on a machine with no install — which on CI is all
    of them. Three green-looking skips and a green build is how 'we never checked the
    install' comes to look identical to 'the install is fine'. This records the state
    in the run's own output so the answer is visible rather than inferred from a count
    of dots."""
    skills = pathlib.Path.home() / ".claude" / "skills"
    state = "checked" if skills.is_dir() else "not-installed-here"
    record_property("install_checks", state)
    print(f"\nINSTALL CHECKS: {state} ({skills})")
    assert state in ("checked", "not-installed-here")
