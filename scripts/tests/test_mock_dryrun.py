import pathlib
import shutil
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_mock
import enter_mode
import journal
import mock_fixtures as F

FIXTURE = pathlib.Path(__file__).resolve().parent / "fixtures" / "mock-dryrun"
SLUG = "asml-mr-recon-engineer-2026-08-09"


def workspace(session):
    return session / "job-profiles" / "demo" / "applications" / SLUG


@pytest.fixture
def session(tmp_path, monkeypatch, capsys):
    shutil.copytree(FIXTURE, tmp_path / "run")
    root = tmp_path / "run" / "skill"
    # Step 0 of a real session. Run it here rather than checking a journal.jsonl into
    # the fixture: the record carries a hash of modes/interview.md, and a checked-in
    # hash is a fixture that silently rots the first time that file is edited.
    enter_mode.main(["--workspace", str(workspace(tmp_path / "run")),
                     "--mode", "interview", "--skill-root", str(root)])
    capsys.readouterr()          # discard enter_mode's reminder
    monkeypatch.setattr(check_mock, "_default_scanner", lambda: F.no_vocab)
    return tmp_path / "run"


def gate(session, capsys):
    code = check_mock.main(
        ["--workspace", str(workspace(session)), "--round", "2", "--today", "2026-08-09",
         "--skill-root", str(session / "skill")]
    )
    return code, capsys.readouterr().out.strip().splitlines()


def apply_walkback(session):
    brief = workspace(session) / "interview-brief.md"
    fix = (session / "fixes" / "walkback.md").read_text(encoding="utf-8")
    brief.write_text(brief.read_text(encoding="utf-8") + fix, encoding="utf-8")


def apply_promotion(session):
    claims = workspace(session) / "claims.yaml"
    fix = (session / "fixes" / "claims-promotion.yaml").read_text(encoding="utf-8")
    claims.write_text(claims.read_text(encoding="utf-8") + fix, encoding="utf-8")


# ------------------------------------------------------------------ stage A

def test_stage_a_the_gate_demands_the_walkback(session, capsys):
    code, out = gate(session, capsys)
    assert code == 1
    assert any(line.startswith("WALKBACK_MISSING:") for line in out)


def test_stage_a_the_provenance_pass_tagged_the_drift_with_its_quote(session):
    text = (workspace(session) / "mock" / "assessment-2.md").read_text(encoding="utf-8")
    assert "tag=UNSOURCED-FACT" in text
    assert "quote=on about 200 patient scans" in text
    assert "quote=I ran it myself on the department cluster" in text


def test_stage_a_the_quotes_are_really_in_the_transcript(session, capsys):
    """If they were invented, the gate would say so — it does not."""
    _, out = gate(session, capsys)
    assert not [line for line in out if line.startswith("QUOTE_NOT_IN_TRANSCRIPT:")]


def test_stage_a_the_transcript_pass_did_not_reach_for_the_brief(session, capsys):
    _, out = gate(session, capsys)
    assert not [line for line in out if line.startswith("WRONG_PASS:")]


def test_stage_a_the_mode_entry_is_recorded_and_current(session, capsys):
    _, out = gate(session, capsys)
    assert not [line for line in out
                if line.startswith(("NO_MODE_ENTRY:", "MODE_FILE_CHANGED:"))]


# ------------------------------------------------------------------ stage B

def test_stage_b_the_walkback_satisfies_the_demand_but_the_promotion_is_still_owed(
    session, capsys
):
    apply_walkback(session)
    code, out = gate(session, capsys)
    assert code == 1
    assert not [line for line in out if line.startswith("WALKBACK")]
    unresolved = [line for line in out if line.startswith("UNRESOLVED_FACT:")]
    assert len(unresolved) == 1
    assert "department cluster" in unresolved[0]


# ------------------------------------------------------------------ stage C

def test_stage_c_the_resolved_round_passes_quietly(session, capsys):
    apply_walkback(session)
    apply_promotion(session)
    code, out = gate(session, capsys)
    assert code == 0
    assert out == []


def test_every_run_left_a_receipt_in_order(session, capsys):
    gate(session, capsys)
    apply_walkback(session)
    gate(session, capsys)
    apply_promotion(session)
    gate(session, capsys)
    receipts = journal.read_receipts(workspace(session), "check_mock")
    assert [r["verdict"] for r in receipts] == ["fail", "fail", "pass"]
    assert all("mock/assessment-2.md" in r["input_hashes"] for r in receipts)
    assert all(r["mode"] == "interview" for r in receipts)


def test_the_receipt_hash_tracks_the_file_that_changed(session, capsys):
    gate(session, capsys)
    apply_walkback(session)
    gate(session, capsys)
    first, second = journal.read_receipts(workspace(session), "check_mock")
    assert first["input_hashes"]["interview-brief.md"] != \
        second["input_hashes"]["interview-brief.md"]
    assert first["input_hashes"]["mock/transcript-2.md"] == \
        second["input_hashes"]["mock/transcript-2.md"]


# ------------------------------------------------------------------ with Plan 2 present

def test_the_real_vocabulary_scanner_is_also_quiet_on_a_resolved_round(
    session, capsys, monkeypatch
):
    """Plan 2's lint_no_prediction exempts `quote=` inside a MOCK-*-V1 block. The
    candidate says "40%" in this transcript, on purpose: without that exemption an
    honest assessment file fails the vocabulary gate, and this is the test that says so."""
    pytest.importorskip("lint_no_prediction")
    monkeypatch.undo()
    apply_walkback(session)
    apply_promotion(session)
    code, out = gate(session, capsys)
    assert code == 0, out
