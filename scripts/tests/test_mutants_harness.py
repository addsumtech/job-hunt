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
import textwrap

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
