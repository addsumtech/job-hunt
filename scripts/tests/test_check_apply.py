import contextlib
import importlib
import io
import json
import pathlib
import sys

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import check_apply
import enter_mode
import journal
import rounds

REQUIRED = ("check_personal_data", "check_claims", "check_render_freshness",
            "parse_verdicts", "lint_cv")

# Every upstream workspace gate, with the extra arguments argparse demands
# before main() can reach its workspace guard. check_apply has its own case
# below (test_a_missing_workspace_is_exit_2_and_creates_nothing).
GATE_ARGS = {
    "check_personal_data": [],
    "check_claims": [],
    "check_render_freshness": ["--round", "1"],
    "parse_verdicts": ["--round", "1", "--ats", "a.txt",
                       "--recruiter", "r.txt", "--hiring-manager", "h.txt"],
    "lint_cv": [],
    "check_letter": [],
    "check_pages": [],
    "check_word_limits": [],
}


def _skill_root(tmp_path, body="# Apply mode\n\nartifact: honest-stop.yaml\n"):
    root = tmp_path / "skill"
    (root / "modes").mkdir(parents=True, exist_ok=True)
    (root / "modes" / "apply.md").write_text(body, encoding="utf-8")
    return root


def _good_workspace(tmp_path, root):
    ws = tmp_path / "acme-engineer-2026-08-09"
    ws.mkdir(parents=True, exist_ok=True)
    # enter_mode prints "entered mode apply; read …" — setup noise. Left in the
    # capture it lands in every "passes silently" assertion below and makes them
    # fail for a reason that has nothing to do with the gate under test.
    with contextlib.redirect_stdout(io.StringIO()):
        enter_mode.main(["--workspace", str(ws), "--mode", "apply",
                         "--skill-root", str(root)])
    for gate in REQUIRED:
        journal.receipt(ws, gate, {}, "pass")
    rounds.merge_round(ws, 1, {"round": 1, "combined_verdict": "PASS"})
    (ws / "interview-brief.md").write_text("# Interview brief\n", encoding="utf-8")
    return ws


def _argv(ws, root):
    return ["--workspace", str(ws), "--skill-root", str(root)]


def test_a_complete_apply_run_passes_silently(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    assert check_apply.main(_argv(ws, root)) == 0
    assert capsys.readouterr().out.strip() == ""


def test_a_missing_upstream_receipt_is_reported_by_name(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    (ws / "journal.jsonl").write_text(
        "\n".join(l for l in (ws / "journal.jsonl").read_text(encoding="utf-8")
                  .splitlines() if "check_claims" not in l) + "\n", encoding="utf-8")
    assert check_apply.main(_argv(ws, root)) == 1
    out = capsys.readouterr().out
    assert "MISSING_RECEIPT: check_claims" in out
    assert "never run" in out


def test_a_hand_written_round_file_without_a_parse_verdicts_receipt_fails(tmp_path, capsys):
    """judge-round-1.json is a plain JSON file. Without this, anyone (or any
    model) can write `combined_verdict: PASS` into it and check_apply agrees —
    with no evidence the parser ever ran, which is the exact substitution
    parse_verdicts.py exists to prevent."""
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    (ws / "journal.jsonl").write_text(
        "\n".join(l for l in (ws / "journal.jsonl").read_text(encoding="utf-8")
                  .splitlines() if "parse_verdicts" not in l) + "\n", encoding="utf-8")
    assert check_apply.main(_argv(ws, root)) == 1
    assert "MISSING_RECEIPT: parse_verdicts" in capsys.readouterr().out


def test_a_failed_upstream_gate_is_reported(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    journal.receipt(ws, "lint_cv", {}, "fail", ["CLICHE: cv.md:4 contains 'synergy'"])
    assert check_apply.main(_argv(ws, root)) == 1
    assert "UPSTREAM_FAILED: lint_cv" in capsys.readouterr().out


def test_the_latest_receipt_wins_so_a_rerun_can_clear_a_failure(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    journal.receipt(ws, "lint_cv", {}, "fail", ["CLICHE"])
    journal.receipt(ws, "lint_cv", {}, "pass")
    assert check_apply.main(_argv(ws, root)) == 0


def test_check_letter_is_required_only_when_a_letter_exists(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    assert check_apply.main(_argv(ws, root)) == 0
    (ws / "letter.yaml").write_text("sender: {}\n", encoding="utf-8")
    capsys.readouterr()
    assert check_apply.main(_argv(ws, root)) == 1
    assert "MISSING_RECEIPT: check_letter" in capsys.readouterr().out


def test_a_rejected_round_without_an_honest_stop_fails(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    rounds.merge_round(ws, 1, {"combined_verdict": "REJECT"})
    assert check_apply.main(_argv(ws, root)) == 1
    out = capsys.readouterr().out
    assert "NO_PASS_NO_STOP" in out
    assert "poorly_built" in out and "honest_stretch" in out


def test_a_rejected_round_with_a_complete_honest_stop_passes(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    rounds.merge_round(ws, 1, {"combined_verdict": "REJECT"})
    (ws / "honest-stop.yaml").write_text(yaml.safe_dump({
        "classification": "honest_stretch",
        "verdict": "stretch",
        "reason": ("The package is as strong as it can truthfully be; the only "
                   "unmet must-have is 5 years of clinical PACS integration, "
                   "which the candidate genuinely lacks."),
        "evidence": ["hiring_manager requirement_match: 3/5 — no clinical PACS work"],
    }, allow_unicode=True), encoding="utf-8")
    assert check_apply.main(_argv(ws, root)) == 0
    assert capsys.readouterr().out.strip() == ""


def test_an_honest_stop_with_a_made_up_classification_fails(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    rounds.merge_round(ws, 1, {"combined_verdict": "REJECT"})
    (ws / "honest-stop.yaml").write_text(yaml.safe_dump({
        "classification": "needs_work", "verdict": "stretch",
        "reason": "x", "evidence": ["y"]}), encoding="utf-8")
    assert check_apply.main(_argv(ws, root)) == 1
    assert "BAD_STOP_CLASSIFICATION" in capsys.readouterr().out


def test_an_honest_stop_with_an_off_vocabulary_verdict_fails(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    rounds.merge_round(ws, 1, {"combined_verdict": "REJECT"})
    (ws / "honest-stop.yaml").write_text(yaml.safe_dump({
        "classification": "honest_stretch", "verdict": "maybe",
        "reason": "x", "evidence": ["y"]}), encoding="utf-8")
    assert check_apply.main(_argv(ws, root)) == 1
    out = capsys.readouterr().out
    assert "BAD_STOP_VERDICT" in out and "worth_applying" in out


def test_an_honest_stop_with_no_evidence_fails(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    rounds.merge_round(ws, 1, {"combined_verdict": "REJECT"})
    (ws / "honest-stop.yaml").write_text(yaml.safe_dump({
        "classification": "poorly_built", "verdict": "worth_applying",
        "reason": "x", "evidence": []}), encoding="utf-8")
    assert check_apply.main(_argv(ws, root)) == 1
    assert "INCOMPLETE_STOP" in capsys.readouterr().out


def test_a_missing_interview_brief_fails(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    (ws / "interview-brief.md").unlink()
    assert check_apply.main(_argv(ws, root)) == 1
    assert "NO_BRIEF" in capsys.readouterr().out


def test_no_mode_entry_fails(tmp_path, capsys):
    """The layer-1.5 backstop: modes/apply.md is not optional, and the journal
    is what proves it was loaded."""
    root = _skill_root(tmp_path)
    ws = tmp_path / "no-entry"
    ws.mkdir()
    for gate in REQUIRED:
        journal.receipt(ws, gate, {}, "pass")
    rounds.merge_round(ws, 1, {"combined_verdict": "PASS"})
    (ws / "interview-brief.md").write_text("x\n", encoding="utf-8")
    assert check_apply.main(_argv(ws, root)) == 1
    assert "NO_MODE_ENTRY" in capsys.readouterr().out


def test_an_edited_mode_file_invalidates_the_entry(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    (root / "modes" / "apply.md").write_text("# Apply mode\n\nrewritten\n",
                                             encoding="utf-8")
    assert check_apply.main(_argv(ws, root)) == 1
    assert "MODE_FILE_CHANGED" in capsys.readouterr().out


def test_no_round_at_all_fails(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    rounds.round_path(ws, 1).unlink()
    assert check_apply.main(_argv(ws, root)) == 1
    assert "NO_ROUND" in capsys.readouterr().out


def test_the_highest_numbered_round_is_the_one_that_counts(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    rounds.merge_round(ws, 1, {"combined_verdict": "REJECT"})
    rounds.merge_round(ws, 2, {"round": 2, "combined_verdict": "PASS"})
    assert check_apply.main(_argv(ws, root)) == 0


def test_a_failed_mode_entry_leaves_a_trace_in_the_journal(tmp_path):
    """The layer-1.5 backstop's own failure must not be the one silent thing in
    the system. An exit-2 mode entry that wrote nothing would be
    indistinguishable from a mode entry nobody attempted — risk-register #12,
    in the exact place this plan calls the backstop."""
    root = tmp_path / "skill"
    (root / "modes").mkdir(parents=True)
    ws = tmp_path / "ws"
    assert enter_mode.main(["--workspace", str(ws), "--mode", "apply",
                            "--skill-root", str(root)]) == 2
    recs = [json.loads(l) for l in
            (ws / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["action"] for r in recs] == ["mode_entry_failed"]
    assert recs[0]["mode"] == "apply" and "apply.md" in recs[0]["mode_file"]
    assert enter_mode.latest_mode_entry(ws, "apply") is None


def test_a_missing_workspace_is_exit_2_and_creates_nothing(tmp_path, capsys):
    """The single place the one-receipt-per-exit rule yields: there is no
    journal to append to. A gate that mkdir'd the workspace it was told does
    not exist would manufacture the evidence directory it is checking."""
    root = _skill_root(tmp_path)
    ws = tmp_path / "never-created"
    assert check_apply.main(_argv(ws, root)) == 2
    assert "does not exist" in capsys.readouterr().err
    assert not ws.exists()


def test_it_leaves_exactly_one_receipt(tmp_path):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    check_apply.main(_argv(ws, root))
    assert [r["verdict"] for r in journal.read_receipts(ws, "check_apply")] == ["pass"]


@pytest.mark.parametrize("gate", sorted(GATE_ARGS))
def test_no_gate_creates_a_workspace_it_was_pointed_at(gate, tmp_path, capsys):
    """journal.receipt() mkdirs, so before the guard existed a typo'd
    --workspace silently materialised an empty workspace and the
    resume-in-progress lookup then found a shell — measured on lint_cv, and
    true of every gate except check_apply. This is the whole set, held to the
    one rule; scripts/enter_mode.py is the only script allowed to create a
    workspace, because it opens the mode."""
    ws = tmp_path / "typo-workspace"
    mod = importlib.import_module(gate)
    assert mod.main(["--workspace", str(ws)] + GATE_ARGS[gate]) == 2
    assert "does not exist" in capsys.readouterr().err
    assert not ws.exists()
