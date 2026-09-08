"""A test that reports PASS while checking nothing is worse than no test.

This repo has now shipped that shape three times, and each one was found by
accident rather than by a check:

  `mutants.py`'s `survives()` counted a whole-suite failure as "mutant killed",
  so any unrelated red made EVERY mutant look caught — 99% coverage, measured,
  and false.

  The opt-in motif check in a sibling repo reported 0 findings on the very deck
  that motivated it, because nothing had opted in.

  `test_the_advertised_test_count_is_the_real_one` returned early when a README
  stated no count. After the five-language rewrite dropped every count it
  reported `5 passed` and inspected nothing — measured 2026-09-08.

The last one is the shape this file bans, because it is the one a reader cannot
see: `pytest -q` prints a dot either way. `pytest.skip` prints an `s` and a
reason in the summary, so an empty run is legible instead of silent.

The rule is absolute on purpose. An allowlist here would be the first thing to
grow, and every entry in it would be invisible again.
"""
import ast
import pathlib

import pytest

TESTS = pathlib.Path(__file__).resolve().parent
FILES = sorted(TESTS.glob("test_*.py"))


def _early_returns(tree):
    """(function, lineno) for every bare `return` that exits having verified nothing.

    NOT every bare return is the defect, and the first draft of this file said
    it was — it flagged seven files and four of them were correct. A return that
    comes AFTER an assertion has already done its job:

        assert reasons == [render_letter.render_cv.NO_ENGINE], reasons
        return                      # the environment answer, already checked

    What is banned is exiting with nothing checked and nothing said. A
    `pytest.skip` counts as saying so: it prints an `s` and a reason.

    A `return` carrying a value is a different thing (pytest warns about it
    separately), so only bare ones are considered.

    KNOWN LIMIT, stated rather than hidden: "already verified" is judged by line
    order, not by which branch actually runs. A function whose only assertion
    sits inside an `if` that did not fire, and which then returns from a later
    branch, exits having checked nothing and is not reported. Catching that needs
    path analysis; naming it here is the honest alternative to implying this
    check is complete.
    """
    out = []
    for node in ast.walk(tree):
        # AsyncFunctionDef too: the repo has no async tests today, and a guard
        # that silently ignores a whole syntax form is the same defect it exists
        # to catch. Measured — an `async def test_x` with a silent return went
        # unreported until this line named it.
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        nested = {n for d in ast.walk(node)
                  if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef)) and d is not node
                  for n in ast.walk(d)}
        verified = sorted(
            sub.lineno for sub in ast.walk(node) if sub not in nested and (
                isinstance(sub, ast.Assert)
                or (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr in ("skip", "fail", "xfail"))))
        for sub in ast.walk(node):
            if not (isinstance(sub, ast.Return) and sub.value is None) or sub in nested:
                continue
            if not any(line < sub.lineno for line in verified):
                out.append((node.name, sub.lineno))
    return out


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_no_test_function_returns_early_without_saying_so(path):
    """Use `pytest.skip(reason)`; a bare `return` hides the empty run."""
    found = _early_returns(ast.parse(path.read_text(encoding="utf-8")))
    assert not found, (
        f"{path.name} returns early without skipping: "
        + ", ".join(f"{fn}:{line}" for fn, line in found)
        + ". Use pytest.skip('why') so an unchecked run is visible in the summary.")


def test_this_check_can_actually_see_the_defect():
    """The guard's own guard. A detector nobody proved can detect is the same
    failure one level up — which is exactly how the three defects above shipped.
    """
    bad = ast.parse(
        "def test_x():\n"
        "    if not thing:\n"
        "        return\n"
        "    assert thing\n")
    assert _early_returns(bad) == [("test_x", 3)]

    good = ast.parse(
        "def test_y():\n"
        "    if not thing:\n"
        "        pytest.skip('nothing to check')\n"
        "    assert thing\n")
    assert _early_returns(good) == []

    # A helper returning a value, and a nested function, are both fine.
    other = ast.parse(
        "def test_z():\n"
        "    def inner():\n"
        "        return\n"
        "    assert inner() is None\n")
    assert _early_returns(other) == []

    # A return AFTER an assertion is not the defect. The first version of this
    # detector said it was, and flagged four correct tests — a checker that
    # cries wolf gets deleted, which would leave the real three unwatched.
    checked_first = ast.parse(
        "def test_w():\n"
        "    assert reasons == [NO_ENGINE]\n"
        "    return\n")
    assert _early_returns(checked_first) == []

    # Every syntax form a test can be written in, because a detector blind to one
    # of them is exactly the silent no-op it is here to prevent.
    for src, expected in [
        ("async def test_a():\n    if x:\n        return\n    assert x\n", 3),
        ("@deco\ndef test_b(a):\n    if not a:\n        return\n    assert a\n", 4),
        ("class TestX:\n    def test_c(self):\n        if not x:\n"
         "            return\n        assert x\n", 4),
        ("def test_d():\n    try:\n        if x:\n            return\n"
         "    finally:\n        pass\n    assert x\n", 4),
    ]:
        found = _early_returns(ast.parse(src))
        assert [line for _, line in found] == [expected], (src, found)
