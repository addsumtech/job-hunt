"""Portable install layout tests; live machine audits are explicit opt-ins."""
import os
import pathlib
import shutil

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
REQUIRED = ('SKILL.md', 'modes/apply.md', 'scripts/check_apply.py')


def assert_install(path):
    # Both skills CLI copies and manual symlinks are supported installations.
    assert path.is_dir(), f'{path} is missing or a broken symlink'
    for relative in REQUIRED:
        installed = path / relative
        assert installed.is_file(), f'{installed} is missing'
        assert installed.read_bytes() == (ROOT / relative).read_bytes(), f'{installed} is stale'


@pytest.mark.parametrize('kind', ['copy', 'symlink'])
def test_runtime_layout_in_an_isolated_install(tmp_path, kind):
    installed = tmp_path / 'skills' / 'job-hunt'
    installed.parent.mkdir()
    if kind == 'symlink':
        installed.symlink_to(ROOT, target_is_directory=True)
    else:
        for relative in REQUIRED:
            target = installed / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
    assert_install(installed)


@pytest.mark.parametrize('broken', ['missing', 'broken-link', 'incomplete', 'stale'])
def test_a_broken_install_is_rejected(tmp_path, broken):
    installed = tmp_path / 'job-hunt'
    if broken == 'broken-link':
        installed.symlink_to(tmp_path / 'absent')
    elif broken == 'incomplete':
        installed.mkdir()
        (installed / 'SKILL.md').write_text('incomplete')
    elif broken == 'stale':
        for relative in REQUIRED:
            target = installed / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('outdated contents')
    with pytest.raises(AssertionError):
        assert_install(installed)


def test_explicit_live_install_audit(record_property):
    # A fresh checkout must never infer an installation or migration merely from
    # the existence of ~/.claude/skills (which may contain unrelated skills).
    requested = os.environ.get('JOBHUNT_CHECK_INSTALL') == '1'
    state = 'requested' if requested else 'not-requested; isolated fixtures checked'
    record_property('live_install_checks', state)
    if not requested:
        # Skip rather than return: this audit is opt-in, and a run that did not
        # perform it must say so in the summary line instead of adding a green
        # tick that looks like the live install was verified.
        pytest.skip('set JOBHUNT_CHECK_INSTALL=1 to audit the real install')
    for runtime in ('.claude', '.codex'):
        assert_install(pathlib.Path.home() / runtime / 'skills' / 'job-hunt')
    if os.environ.get('JOBHUNT_CHECK_MIGRATION_ARCHIVE') == '1':
        archive = pathlib.Path.home() / '.claude/skills/job-application'
        assert archive.is_dir() and not archive.is_symlink(), 'migration archive is missing'
