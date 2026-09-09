"""Can a host that is not Claude Code run this skill?

The enforcement layer is the half that stops this skill inventing things, and it
is checked here the only way that means anything: by running it with no agent in
the loop at all. The rest of the file holds the prose to naming a portable form
wherever it names a Claude Code tool.
"""
import ast
import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
REF = ROOT / "references" / "portability.md"
sys.path.insert(0, str(SCRIPTS))


# ---- the enforcement layer is agent-agnostic, and that is testable ---------

def test_the_scripts_import_nothing_beyond_the_standard_library_and_declared_packages():
    """`requirements.txt` is the whole dependency surface. A third package would
    be a new install step on every host, and a host-specific import would make
    the gates unrunnable off Claude Code."""
    std = set(sys.stdlib_module_names)
    local = {p.stem for p in SCRIPTS.glob("*.py")}
    external = set()
    for path in SCRIPTS.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                external.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                external.add(node.module.split(".")[0])
    assert external - std - local == {"docx", "yaml", "pymupdf"}


def test_no_script_mentions_a_claude_only_tool():
    """The gates must not assume a dispatcher. Prose may name one and then give
    the portable form; a script cannot, because it has no way to degrade."""
    banned = ("AskUserQuestion", "WebFetch", "WebSearch")
    offenders = []
    for path in SCRIPTS.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in banned:
            if token in text:
                offenders.append(f"{path.name}: {token}")
    assert not offenders, offenders


def test_a_gate_runs_with_bare_python_and_no_agent(tmp_path):
    """The real portability check: a subprocess, a workspace, no host."""
    env = {**os.environ, "JOBHUNT_PROFILES_ROOT": str(tmp_path / "store")}
    enter = subprocess.run(
        [sys.executable, str(SCRIPTS / "enter_mode.py"),
         "--workspace", str(tmp_path), "--mode", "discover"],
        capture_output=True, text=True, encoding="utf-8", env=env)
    assert enter.returncode == 0, enter.stderr
    gate = subprocess.run(
        [sys.executable, str(SCRIPTS / "check_no_write.py"), "--workspace", str(tmp_path)],
        capture_output=True, text=True, encoding="utf-8", env=env)
    assert gate.returncode == 0, gate.stderr
    assert (tmp_path / "journal.jsonl").is_file()


# ---- the profile store can move, because another host's user did not ask
#      for a ~/.claude directory ------------------------------------------

def test_the_store_honours_an_environment_override(tmp_path):
    out = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, %r); import paths; print(paths.PROFILES_ROOT)"
         % str(SCRIPTS)],
        capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "JOBHUNT_PROFILES_ROOT": str(tmp_path / "elsewhere")})
    assert out.stdout.strip() == str(tmp_path / "elsewhere"), out.stderr


def test_the_default_is_unchanged_when_the_variable_is_absent():
    """Someone running this from two agents should get ONE set of CVs, not two
    half-populated ones — so the default stays put even off Claude Code."""
    env = {k: v for k, v in os.environ.items() if k != "JOBHUNT_PROFILES_ROOT"}
    out = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, %r); import paths; print(paths.PROFILES_ROOT)"
         % str(SCRIPTS)],
        capture_output=True, text=True, encoding="utf-8", env=env)
    assert out.stdout.strip() == str(pathlib.Path.home() / ".claude" / "job-profiles")


# ---- the judge personas are what make the loop portable -------------------

@pytest.mark.parametrize("persona", [
    "ats-screener.md", "recruiter-screener.md", "hiring-manager.md",
    "mock-assessor-transcript.md", "mock-assessor-provenance.md",
])
def test_a_judge_persona_is_self_contained(persona):
    """They are pasted into a fresh context by whatever mechanism the host has —
    a subagent, `codex exec`, or a separate session. A persona that referred to
    its dispatcher, or to a file it expected to read itself, would only work on
    the host it was written for."""
    text = (ROOT / "agents" / persona).read_text(encoding="utf-8")
    assert len(text) > 500
    for token in ("AskUserQuestion", "WebFetch", "the Agent tool"):
        assert token not in text, f"{persona} names {token}"


# ---- the prose gives a portable form wherever it names a Claude tool ------

def test_the_reference_exists_and_covers_the_three_affordances():
    t = REF.read_text(encoding="utf-8")
    for topic in ("AskUserQuestion", "codex exec", "WebFetch",
                  "JOBHUNT_PROFILES_ROOT"):
        assert topic in t, topic


def test_apply_mode_gives_a_portable_form_for_asking_the_user():
    t = " ".join((ROOT / "modes" / "apply.md").read_text(encoding="utf-8").split())
    assert "the requirement is the SHAPE, not the tool" in t
    assert "one question per turn" in t, "the failure mode has to be named"
    assert "portability.md" in t


def test_both_layers_say_the_judge_dispatcher_is_replaceable():
    """SKILL.md calls the review loop non-negotiable. A run reading only layer 1
    on a host with no subagents would otherwise hit "dispatch subagents" with no
    stated alternative."""
    for f in ("SKILL.md", "modes/apply.md"):
        t = " ".join((ROOT / f).read_text(encoding="utf-8").split())
        assert "The mechanism is replaceable; the isolation is not" in t, f
        assert "codex exec" in t, f


def test_the_honest_degraded_case_is_stated_rather_than_hidden():
    """A judge sharing the author's context is not a second opinion, and no gate
    can see that it did. Reporting three PASSes as an arm's-length review would
    be the failure the whole loop exists to prevent."""
    t = " ".join((ROOT / "SKILL.md").read_text(encoding="utf-8").split())
    assert "shared the author's context" in t
    assert "never report three passes" in t.lower()


def test_the_read_when_list_points_at_it():
    t = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "references/portability.md" in t
    assert "not Claude Code" in t


def test_the_codex_path_is_recorded_as_measured_not_assumed():
    """A recipe nobody ran is a recipe that does not work. This one was run:
    three judges through `codex exec` on a real apply workspace, and
    `parse_verdicts.py` accepted all three. The claim carries its date, the CLI
    version and what was NOT tested, so a later reader can tell measurement from
    plausibility."""
    t = REF.read_text(encoding="utf-8")
    assert "Measured end to end" in t
    assert "codex-cli 0.147.0" in t
    assert "parse_verdicts.py" in t
    assert "were NOT tested" in t, "the untested hosts have to be named as untested"
