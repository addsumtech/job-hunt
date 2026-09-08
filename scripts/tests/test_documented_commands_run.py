"""Every command the documentation tells the agent to run must actually work.

The docs are the program here: an agent reads them and executes what they say.
A flag that does not exist, or one the docs omit and a gate then complains about,
costs a step on every run and there is nothing to catch it — the scripts have
tests, the prose did not.

Three instances found 2026-09-06, each reproduced before it was fixed:

  `check_conventions.py --all`  exits 2 with BAD_ARGS. The real CI command is
                                `--ci`, which both the Makefile and the GitHub
                                workflow use.
  `--because`                   appeared in ZERO documents, and following the
                                documented `enter_mode` line exactly made
                                `check_apply` emit MODE_UNEXPLAINED on every run.
  `RUN_NOTES`                   was backticked as a workspace artifact. It is the
                                EVAL harness's file; no script in the skill reads
                                or writes one.

The first test below is the general one. The rest pin the three.
"""
import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
DOCS = ([ROOT / "SKILL.md"] + sorted((ROOT / "modes").glob("*.md"))
        + sorted((ROOT / "references").glob("*.md")))

# `python3 scripts/<name>.py <rest of the line>` as the docs write it.
INVOCATION = re.compile(r"`?python3 (scripts/([a-z_]+)\.py)([^`\n]*)")


def documented_invocations():
    for doc in DOCS:
        for i, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            for m in INVOCATION.finditer(line):
                yield doc.relative_to(ROOT), i, m.group(2), m.group(3)


def accepted_flags(script):
    """Long flags this script's argparse actually accepts."""
    help_text = subprocess.run([sys.executable, str(SCRIPTS / f"{script}.py"), "--help"],
                               capture_output=True, text=True, encoding="utf-8").stdout
    return set(re.findall(r"(--[a-z][a-z-]*)", help_text))


@pytest.mark.parametrize("doc, line, script, rest",
                         list(documented_invocations()),
                         ids=lambda v: str(v)[:40])
def test_a_documented_flag_exists(doc, line, script, rest):
    """The flags in a documented command line must be real.

    `check_conventions.py --all` was in `modes/assess.md` and exits 2 — an agent
    following it reads BAD_ARGS and may take it for a table failure.
    """
    path = SCRIPTS / f"{script}.py"
    assert path.is_file(), f"{doc}:{line} runs {script}.py, which does not exist"
    used = set(re.findall(r"(--[a-z][a-z-]*)", rest))
    if not used:
        return
    unknown = sorted(used - accepted_flags(script))
    assert not unknown, f"{doc}:{line} passes {unknown} to {script}.py, which rejects them"


# ---- the three specific ones ----------------------------------------------

def test_following_the_documented_mode_entry_does_not_trip_the_gate(tmp_path):
    """`--because` is a real flag that appeared in no document, so an agent
    following the docs exactly got MODE_UNEXPLAINED on every apply run."""
    subprocess.run([sys.executable, str(SCRIPTS / "enter_mode.py"),
                    "--workspace", str(tmp_path), "--mode", "apply",
                    "--because", "user pasted a posting and asked for a CV"],
                   capture_output=True, text=True, encoding="utf-8", check=True)
    r = subprocess.run([sys.executable, str(SCRIPTS / "check_apply.py"),
                        "--workspace", str(tmp_path)], capture_output=True, text=True, encoding="utf-8")
    assert "MODE_UNEXPLAINED" not in r.stdout + r.stderr


@pytest.mark.parametrize("mode", ["discover", "assess", "apply", "interview"])
def test_every_mode_file_documents_the_because_flag(mode):
    """One mode documenting it is three modes tripping the notice."""
    text = (ROOT / "modes" / f"{mode}.md").read_text(encoding="utf-8")
    assert "--because" in text, f"{mode}.md's entry command omits --because"


def test_layer_one_documents_it_too():
    assert "--because" in (ROOT / "SKILL.md").read_text(encoding="utf-8")


def test_the_ci_convention_command_is_the_one_ci_runs():
    """`--all` alone exits 2. The Makefile and the workflow both run `--ci`."""
    assert "--all`" not in (ROOT / "modes" / "assess.md").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "check_conventions.py --ci" in makefile
    r = subprocess.run([sys.executable, str(SCRIPTS / "check_conventions.py"), "--all"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 2, "if --all starts working, the doc may name it again"


def test_no_document_promises_a_run_notes_artifact():
    """`RUN_NOTES` is the eval harness's file. No script in the skill reads or
    writes one, so an agent told to write it looks for something that is not
    there. SKILL.md and modes/apply.md already say "the run notes" as prose."""
    for doc in DOCS:
        assert "RUN_NOTES" not in doc.read_text(encoding="utf-8"), doc
