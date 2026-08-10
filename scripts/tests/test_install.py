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
    user has to know which to invoke."""
    old = pathlib.Path.home() / ".claude" / "skills" / "job-application"
    assert old.is_dir(), "the archive was removed; it is the migration's baseline"
    assert not old.is_symlink()
