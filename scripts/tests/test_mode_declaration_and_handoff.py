"""Three things the model decides, and nothing checked any of them.

RAISED BY THE USER after watching a real apply run, 2026-09-02.

1. WHICH MODE. SKILL.md says "Decide before anything else, and say which one you
   picked" — the choice is an inference from the user's words, and it names its
   own failure: a "find me roles" request answered in apply's voice, with no
   discover gate ever run. But `check_apply` only ever asked whether an apply
   mode_entry EXISTS. A wrong inference produces a perfectly valid apply entry,
   so nothing could see it. The reason is now recorded beside the choice.

2. THAT NO ASSESSMENT WAS MADE. modes/apply.md, Entry conditions: "No assessment
   at all is not a blocker either: run apply, and say plainly that no fit
   assessment was made." Measured on the same run — no assess mode was run and
   the disclosure was never made, because nothing required it. It cannot be a
   FAILURE (apply.md explicitly permits the case), so the gate states the fact
   itself and the completion message carries it.

3. WHAT COMES NEXT. discover.md is emphatic that it "never chains into apply —
   thirty rows do not become thirty CVs", and it is right. But a model reading
   that can conclude it must not even OFFER, which leaves the user at the end of
   a mode with no idea the other three exist. Offering is not chaining: the
   distinction is whether a person chose.
"""
import json
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))
import enter_mode  # noqa: E402


def workspace(tmp_path):
    ws = tmp_path / "job-profiles" / "t" / "applications" / "acme-eng-2026-09-02"
    ws.mkdir(parents=True)
    return ws


def enter(ws, mode="apply", *extra):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "enter_mode.py"), "--workspace", str(ws),
         "--mode", mode, *extra],
        capture_output=True, text=True, encoding="utf-8", cwd=str(REPO))


def test_the_reason_for_the_mode_is_recorded_beside_the_choice(tmp_path):
    ws = workspace(tmp_path)
    proc = enter(ws, "apply", "--because", "user pasted a posting and their CV")
    assert proc.returncode == 0, proc.stderr
    rec = enter_mode.latest_mode_entry(ws, "apply")
    assert rec["because"] == "user pasted a posting and their CV", (
        "the inference that picked this mode has to be recorded, or a wrong one "
        "looks exactly like a right one")


def test_entering_without_a_reason_still_works_but_records_its_absence(tmp_path):
    """Optional on purpose: four mode docs and ten test files call this script,
    and breaking them to force a field would cost more than it buys. Absence is
    recorded so the gate can say so."""
    ws = workspace(tmp_path)
    assert enter(ws).returncode == 0
    rec = enter_mode.latest_mode_entry(ws, "apply")
    assert "because" in rec and rec["because"] is None


def test_entry_records_whether_an_assessment_was_there(tmp_path):
    ws = workspace(tmp_path)
    enter(ws)
    assert enter_mode.latest_mode_entry(ws, "apply")["assessment_present"] is False
    (ws / "fit-assessment.yaml").write_text("verdict: stretch\n", encoding="utf-8")
    enter(ws)
    assert enter_mode.latest_mode_entry(ws, "apply")["assessment_present"] is True


def _check_apply(ws):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "check_apply.py"), "--workspace", str(ws)],
        capture_output=True, text=True, encoding="utf-8", cwd=str(REPO))


def test_check_apply_says_when_no_assessment_was_made(tmp_path):
    ws = workspace(tmp_path)
    enter(ws)
    # stderr: stdout is the findings channel and stays quiet on a clean run.
    out = _check_apply(ws).stderr
    assert "NO_ASSESSMENT" in out, (
        "apply.md requires the run to say plainly that no fit assessment was "
        f"made; the gate must state it so the completion message carries it:\n{out}")
    assert "fit assessment" in out.lower()


def test_the_no_assessment_notice_is_not_a_failure(tmp_path):
    """apply.md: 'No assessment at all is not a blocker either.' A notice that
    failed the run would contradict the rule it exists to serve."""
    ws = workspace(tmp_path)
    enter(ws)
    before = _check_apply(ws)
    (ws / "fit-assessment.yaml").write_text("verdict: stretch\n", encoding="utf-8")
    enter(ws)
    after = _check_apply(ws)
    assert "NO_ASSESSMENT" not in after.stderr
    # Both runs are incomplete for other reasons; what matters is that the
    # notice itself did not change the verdict.
    assert before.returncode == after.returncode


def test_a_clean_gate_run_still_says_nothing_on_stdout(tmp_path):
    """The notices must not become noise. stdout is one finding per line with a
    stable CODE prefix; an always-on line there trains the reader to skip it."""
    ws = workspace(tmp_path)
    enter(ws)
    assert "NEXT_MODES" not in _check_apply(ws).stdout, (
        "the hand-off is the mode file's job, not a gate's — a gate that tells "
        "you what to do next is prompting, not checking")


def test_apply_mode_ends_by_offering_the_next_modes(tmp_path):
    """Where the model actually reads it, at the end of the mode."""
    apply_md = (REPO / "modes" / "apply.md").read_text(encoding="utf-8")
    assert "Step 7.6" in apply_md, "apply mode has no hand-off step"
    block = apply_md.split("Step 7.6")[1].split("### Step 7.5")[0].lower()
    assert "interview" in block and "assess" in block and "discover" in block
    assert "unasked" in block or "never run" in block, (
        "the step must say the modes are offered, not run")


def test_the_handoff_rule_is_written_down_where_the_model_reads_it():
    """A behaviour only a gate mentions is a behaviour the model learns after
    it has already finished."""
    skill = (REPO / "SKILL.md").read_text(encoding="utf-8")
    assert "## Hand-off" in skill, "SKILL.md needs the hand-off rule"
    block = skill.split("## Hand-off")[1].split("\n## ")[0].lower()
    assert "offer" in block and "never" in block
    for mode in ("discover", "assess", "apply", "interview"):
        assert mode in block, f"the hand-off table omits {mode}"
    assert "chain" in block, (
        "it must name the rule it is distinguished from, or a reader takes it "
        "as permission to chain")


def test_a_mode_entry_written_before_the_field_existed_is_still_checked(tmp_path):
    """Old records cannot answer a question that did not exist when they were
    written. Defaulting them to "an assessment was there" suppressed the notice
    on precisely the workspaces most likely to need it — measured on the real
    run that prompted this change."""
    ws = workspace(tmp_path)
    enter(ws)
    # Strip the field, as a pre-existing journal would have it.
    path = ws / "journal.jsonl"
    kept = []
    for line in path.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        rec.pop("assessment_present", None)
        kept.append(json.dumps(rec))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")

    assert "NO_ASSESSMENT" in _check_apply(ws).stderr, (
        "the gate trusted a missing field instead of looking at the workspace")

    (ws / "fit-assessment.yaml").write_text("verdict: stretch\n", encoding="utf-8")
    assert "NO_ASSESSMENT" not in _check_apply(ws).stderr, (
        "and it must go quiet once an assessment really is there")
