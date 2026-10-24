"""The two refusals every entry point makes before it parses an argument.

1. An interpreter older than the documented floor. macOS ships Python 3.9 as
   /usr/bin/python3 and every mode file says `python3 scripts/...`; measured
   2026-10-24, every gate died on it with `TypeError: unsupported operand
   type(s) for |` and exit 1 — a gate's code for "findings" — because
   cli_io.py evaluated `str | None` at import.
2. A `--workspace` inside the skill directory. `modes/discover.md` said
   `--workspace .`, and `scripts/` only resolves from the skill root, so `.`
   was the skill root: snapshot_profile wrote the private candidate-profile.yaml
   into the skill and the discover gates appended journal.jsonl beside SKILL.md.
"""
import ast
import os
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

import cli_io

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"


def _source(path):
    return path.read_text(encoding="utf-8")


def entry_scripts():
    """Every script whose `__main__` goes through cli_io.configure_output."""
    return sorted(p.name for p in SCRIPTS.glob("*.py")
                  if '__name__ == "__main__"' in _source(p)
                  and "configure_output()" in _source(p))


def workspace_scripts():
    """Every script with a --workspace option."""
    return sorted(p.name for p in SCRIPTS.glob("*.py")
                  if 'add_argument("--workspace"' in _source(p))


# ---- the version floor -------------------------------------------------------

def test_an_old_python_is_refused_with_one_line_and_exit_2(capsys):
    with pytest.raises(SystemExit) as stop:
        cli_io.require_supported_python((3, 9, 6), script="scripts/enter_mode.py")
    assert stop.value.code == 2
    err = capsys.readouterr().err
    assert err.startswith("PYTHON_TOO_OLD:") and err.count("\n") == 1
    assert "3.10+" in err and "3.9.6" in err
    assert "scripts/run_tool.py python scripts/enter_mode.py" in err
    assert "setup_dependencies.py" in err
    assert err.isascii(), "printed before stdout/stderr are switched to UTF-8"


@pytest.mark.parametrize("version", [(3, 10, 0), (3, 11, 15), (3, 13, 1)])
def test_a_supported_python_passes_silently(version, capsys):
    cli_io.require_supported_python(version)
    assert capsys.readouterr().err == ""


def test_the_floor_is_the_one_the_documentation_states():
    """README.md, REFERENCE.md and references/agent-setup.md say 3.10+, and
    setup_dependencies.py enforces 3.10; a floor in cli_io that disagreed would
    refuse a Python the docs promise, or accept one setup refuses."""
    assert cli_io.MIN_PYTHON == (3, 10)
    for doc in ("README.md", "README_EN.md", "REFERENCE.md", "references/agent-setup.md"):
        assert "Python 3.10+" in _source(ROOT / doc), doc
    assert re.search(r"version_info\s*<\s*\(3,\s*10\)", _source(SCRIPTS / "setup_dependencies.py"))


@pytest.mark.parametrize("script", entry_scripts())
def test_every_entry_point_checks_the_version_before_parsing(script):
    """`--help` must not get past the floor: a check that ran after argparse
    would let an old interpreter reach whatever the script does next. Simulated
    by raising the floor in the already-imported cli_io, which every entry
    point's `from cli_io import configure_output` then reads."""
    prelude = ("import runpy, sys; sys.path.insert(0, {d!r}); import cli_io; "
               "cli_io.MIN_PYTHON = (99, 0); sys.argv = [{p!r}, '--help']; "
               "runpy.run_path({p!r}, run_name='__main__')").format(
                   d=str(SCRIPTS), p=str(SCRIPTS / script))
    proc = subprocess.run([sys.executable, "-c", prelude], capture_output=True,
                          text=True, encoding="utf-8", cwd=str(ROOT))
    assert proc.returncode == 2, (script, proc.stdout[-300:], proc.stderr[-300:])
    assert "PYTHON_TOO_OLD" in proc.stderr and "Traceback" not in proc.stderr


def _old_interpreter():
    for candidate in ("/usr/bin/python3", "python3.9", "python3.8"):
        exe = shutil.which(candidate) or (candidate if os.path.isfile(candidate) else None)
        if not exe:
            continue
        try:
            out = subprocess.run([exe, "-c", "import sys; print(sys.version_info[:2] < (3, 10))"],
                                 capture_output=True, text=True, timeout=30).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            continue
        if out == "True":
            return exe
    return None


OLD_PYTHON = _old_interpreter()


@pytest.mark.skipif(OLD_PYTHON is None, reason="no Python older than 3.10 on this host")
@pytest.mark.parametrize("script", entry_scripts())
def test_a_real_old_interpreter_gets_the_refusal_not_a_traceback(script):
    """The measured case, on the interpreter that produced it. Skipped where
    no pre-3.10 Python exists (CI runs 3.11); the two static tests below are
    what hold the line there."""
    proc = subprocess.run([OLD_PYTHON, str(SCRIPTS / script), "--help"],
                          capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT))
    assert proc.returncode == 2, (script, proc.stderr[-400:])
    assert proc.stderr.startswith("PYTHON_TOO_OLD:"), proc.stderr[-400:]
    assert "Traceback" not in proc.stderr


def _annotations(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = node.args
            for arg in a.posonlyargs + a.args + a.kwonlyargs + [a.vararg, a.kwarg]:
                if arg is not None and arg.annotation is not None:
                    yield arg.annotation
            if node.returns is not None:
                yield node.returns
        elif isinstance(node, ast.AnnAssign):
            yield node.annotation


@pytest.mark.parametrize("path", sorted(SCRIPTS.glob("*.py")), ids=lambda p: p.name)
def test_a_union_annotation_comes_with_the_future_import(path):
    """`str | None` in a signature is evaluated when the def runs, unless the
    module has `from __future__ import annotations`. cli_io.py lacked it, and
    every entry point imports cli_io, so all of them crashed on 3.9 before
    the version check could print — the check has to be importable to work."""
    tree = ast.parse(_source(path))
    unions = [ann.lineno for ann in _annotations(tree)
              if any(isinstance(x, ast.BinOp) and isinstance(x.op, ast.BitOr)
                     for x in ast.walk(ann))]
    future = any(isinstance(n, ast.ImportFrom) and n.module == "__future__"
                 and any(a.name == "annotations" for a in n.names) for n in tree.body)
    assert future or not unions, f"{path.name}: X | Y annotations at lines {unions}"


@pytest.mark.parametrize("path", sorted(SCRIPTS.glob("*.py")), ids=lambda p: p.name)
def test_every_script_still_parses_as_python_3_9(path):
    """A `match` statement is a SyntaxError on 3.9 before any code runs, so a
    script containing one could not reach the version check at all."""
    ast.parse(_source(path), filename=str(path), feature_version=(3, 9))


# ---- --workspace inside the skill ---------------------------------------------

@pytest.mark.parametrize("argv,expected", [
    (["--workspace", "x"], ["x"]),
    (["--workspace=x"], ["x"]),
    (["--mode", "apply", "--workspace", "."], ["."]),
    (["--work", "x"], ["x"]),                     # argparse accepts the prefix
    (["--workspace"], []),                        # argparse reports this itself
    (["--", "--workspace", "x"], []),
    (["--because", "--workspace is not an option here"], []),
    (["--round", "1"], []),
])
def test_workspace_arguments_are_read_the_way_argparse_reads_them(argv, expected):
    assert cli_io.workspace_arguments(argv) == expected


def test_a_workspace_outside_the_skill_is_left_alone(tmp_path):
    cli_io.refuse_skill_workspace(["--workspace", str(tmp_path)])


def test_the_skill_root_is_refused_before_anything_is_written(monkeypatch, capsys):
    monkeypatch.chdir(ROOT)
    with pytest.raises(SystemExit) as stop:
        cli_io.refuse_skill_workspace(["--workspace", "."])
    assert stop.value.code == 2
    err = capsys.readouterr().err
    assert err.startswith("WORKSPACE_IN_SKILL:") and err.count("\n") == 1


@pytest.fixture(scope="module")
def skill_copy(tmp_path_factory):
    """A copy of the skill to point the scripts at, so that a broken guard
    writes into a temporary directory and never into this checkout."""
    root = tmp_path_factory.mktemp("skill") / "job-hunt"
    ignore = shutil.ignore_patterns("tests", "__pycache__", ".git", "docs")
    for name in ("scripts", "modes", "references", "assets", "third_party", "evals"):
        shutil.copytree(ROOT / name, root / name, ignore=ignore)
    for name in ("SKILL.md", "requirements.txt"):
        shutil.copy2(ROOT / name, root / name)
    return root


def _tree(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")
                  if "__pycache__" not in p.parts)


@pytest.mark.parametrize("script", sorted(set(entry_scripts()) & set(workspace_scripts())))
def test_every_workspace_gate_refuses_the_skill_root(script, skill_copy):
    before = _tree(skill_copy)
    proc = subprocess.run([sys.executable, str(skill_copy / "scripts" / script),
                           "--workspace", "."], capture_output=True, text=True,
                          encoding="utf-8", cwd=str(skill_copy))
    assert proc.returncode == 2, (script, proc.stdout[-300:], proc.stderr[-300:])
    assert proc.stderr.startswith("WORKSPACE_IN_SKILL:"), proc.stderr[-300:]
    assert proc.stdout == ""
    assert _tree(skill_copy) == before, f"{script} wrote into the skill directory"


def test_a_directory_inside_the_skill_is_refused_too(skill_copy):
    """The in-repo eval fixture is a real workspace shape; a receipt appended to
    its tracked journal.jsonl would break the test that pins it line for line."""
    fixture = skill_copy / "evals" / "fixtures" / "workspaces" / "clean"
    before = _source(fixture / "journal.jsonl")
    proc = subprocess.run([sys.executable, str(skill_copy / "scripts" / "check_shortlist.py"),
                           f"--workspace={fixture}"], capture_output=True, text=True,
                          encoding="utf-8", cwd=str(skill_copy))
    assert proc.returncode == 2 and "is inside the job-hunt skill" in proc.stderr
    assert _source(fixture / "journal.jsonl") == before


def test_snapshot_profile_no_longer_writes_the_profile_into_the_skill(skill_copy):
    """The exact command modes/discover.md gave, run from the skill root."""
    profile = skill_copy / "profile.yaml"
    shutil.copy2(SCRIPTS / "tests" / "fixtures" / "sample_profile.yaml", profile)
    try:
        proc = subprocess.run([sys.executable, "scripts/snapshot_profile.py", "--workspace", ".",
                               "--profile", str(profile)], capture_output=True, text=True,
                              encoding="utf-8", cwd=str(skill_copy))
    finally:
        profile.unlink()
    assert proc.returncode == 2, proc.stderr
    assert not (skill_copy / "candidate-profile.yaml").exists()
    assert not (skill_copy / "journal.jsonl").exists()


# Workspace scripts that do not go through cli_io.configure_output, so the guard
# does not reach them. Recorded, not endorsed: each needs the two-line
# `from cli_io import configure_output; configure_output()` in its `__main__`
# (run_tool.py instead a direct paths.skill_workspace_refusal call, because it
# is the launcher that must still start on an old system Python). Shrinking
# this set is the point; this test goes red when it changes either way.
OUTSIDE_CLI_IO = {"check_search_coverage.py", "render_report.py", "run_tool.py"}


def test_the_workspace_scripts_outside_the_guard_are_exactly_the_known_ones():
    assert set(workspace_scripts()) - set(entry_scripts()) == OUTSIDE_CLI_IO
