"""The mutation harness must judge the source on disk, never a cached compile of it.

Measured 2026-09-21: the scheduled mutants job stopped with "the suite fails on
the UNMUTATED copy" although the copy was byte-identical to HEAD. The last
check_claims.py mutant turned `if __name__ == "__main__":` into `!=`, died in
under a second, and was restored within the same second it was written. Same
size, same whole-second mtime: Python kept trusting the mutated .pyc, the
restored module still exited on import, and every run after it was red.

Reproduced against the real check_claims.py before the fix: the pristine copy
went red in 5 of 6 tries. The test below rebuilds that shape in a two-file repo,
so it runs in seconds instead of needing the whole suite.
"""
import pathlib
import shutil
import subprocess
import textwrap

import pytest

import mutants

GATE = textwrap.dedent('''\
    def is_ok(x):
        return x == 1


    if __name__ == "__main__":
        raise SystemExit(2)
''')

TEST = textwrap.dedent('''\
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import gate


    def test_is_ok():
        assert gate.is_ok(1)
''')


def _repo(tmp_path: pathlib.Path) -> pathlib.Path:
    work = tmp_path / "repo"
    (work / "scripts" / "tests").mkdir(parents=True)
    (work / "scripts" / "gate.py").write_text(GATE, encoding="utf-8")
    (work / "scripts" / "tests" / "test_gate.py").write_text(TEST, encoding="utf-8")
    return work


def test_a_main_guard_mutant_is_killed_and_leaves_the_copy_green(tmp_path):
    work = _repo(tmp_path)
    assert mutants._pytest(work, []), "the two-file repo must start green"

    guard = [m for m in mutants.generate(work / "scripts" / "gate.py", "scripts/gate.py")
             if "__main__" in m.original and m.operator == "eq->ne"]
    assert len(guard) == 1, guard
    # Same length as the original line: exactly the mutant a stale .pyc hides.
    assert len(guard[0].mutated) == len(guard[0].original)

    # Before the fix this failed both ways, depending on the clock. The pristine
    # .pyc from the green run above hid the mutant, which then "survived"; or the
    # mutated .pyc outlived the restore and survives() raised Unattributable.
    assert mutants.survives(work, guard[0]) is False
    assert (work / "scripts" / "gate.py").read_text(encoding="utf-8") == GATE
    assert mutants._pytest(work, []), "the restored copy must be green again"


def test_the_harness_writes_no_bytecode_into_the_copy(tmp_path):
    """The timing above is a race; this is the mechanism, and it is not. With no
    .pyc in the copy there is nothing stale to trust, whatever the clock says."""
    work = _repo(tmp_path)
    assert mutants._pytest(work, [])
    assert sorted(work.rglob("*.pyc")) == []


def test_copy_preserves_links_and_excludes_private_output(tmp_path, monkeypatch):
    source = _repo(tmp_path)
    private = source / "output" / "old-test"
    private.mkdir(parents=True)
    (private / "profile.yaml").write_text("private candidate data")
    (private / "missing-skill").symlink_to(tmp_path / "deleted-runtime")
    (source / "broken-fixture").symlink_to(tmp_path / "absent-fixture")
    monkeypatch.setattr(mutants, "ROOT", source)
    destination = tmp_path / "copy"
    mutants._copy_repo(destination)
    assert (destination / "scripts/gate.py").read_text() == GATE
    assert not (destination / "output").exists()
    assert (destination / "broken-fixture").is_symlink()


@pytest.mark.parametrize("failure", [OSError("copy denied"), shutil.Error("copy failed")])
def test_copy_failure_removes_partial_workspace(tmp_path, monkeypatch, failure):
    source = _repo(tmp_path)
    work_root = tmp_path / "partial-mutation-copy"
    work_root.mkdir()
    monkeypatch.setattr(mutants, "ROOT", source)
    monkeypatch.setattr(mutants.tempfile, "mkdtemp", lambda **kwargs: str(work_root))

    def fail_copy(destination):
        destination.mkdir()
        (destination / "partial").write_text("incomplete")
        raise failure

    monkeypatch.setattr(mutants, "_copy_repo", fail_copy)
    assert mutants.main(["--targets", "scripts/gate.py"]) == 2
    assert not work_root.exists()


def test_linked_mutation_target_cannot_write_outside_the_copy(tmp_path, monkeypatch):
    source = _repo(tmp_path)
    outside = tmp_path / "outside.py"
    outside.write_text(GATE)
    target = source / "scripts/gate.py"
    target.unlink()
    target.symlink_to(outside)
    monkeypatch.setattr(mutants, "ROOT", source)
    monkeypatch.setattr(mutants, "_run_pytest", lambda *args: pytest.fail(
        "an external mutation target must be rejected before tests run"))
    assert mutants.main(["--targets", "scripts/gate.py"]) == 2
    assert outside.read_text() == GATE


@pytest.mark.parametrize("edit_during", ["pristine_check", "first_mutant"])
def test_mutations_and_totals_use_the_frozen_copy(tmp_path, monkeypatch, capsys,
                                                edit_during):
    source = _repo(tmp_path)
    target = source / "scripts/gate.py"
    expected = [m.key for m in mutants.generate(target, "scripts/gate.py")]
    visited = []
    monkeypatch.setattr(mutants, "ROOT", source)

    def edit_original():
        target.write_text(GATE + "\ndef added_later(x):\n    return x >= 2\n")

    def check_pristine(work, tests):
        if edit_during == "pristine_check":
            edit_original()
        return subprocess.CompletedProcess([], 0, stdout="", stderr="")

    def kill_mutant(work, mutation):
        if edit_during == "first_mutant" and not visited:
            edit_original()
        assert (work / "scripts/gate.py").read_text() == GATE
        visited.append(mutation.key)
        return False

    monkeypatch.setattr(mutants, "_run_pytest", check_pristine)
    monkeypatch.setattr(mutants, "survives", kill_mutant)
    assert mutants.main(["--targets", "scripts/gate.py"]) == 0
    assert target.read_text() != GATE
    assert visited == expected
    assert f"mutants: {len(visited)}   tested: {len(visited)}" in capsys.readouterr().out
