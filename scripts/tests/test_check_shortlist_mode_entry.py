"""The second half of the layer-1.5 backstop (spec §4.2).

A mode file is only 'loaded unconditionally' if something reports that it was
not. `check_shortlist` requires the mode_entry record, and requires the hash in
it to still match the file on disk — otherwise what was read is not what is
here, and the schema the run followed is not the schema being enforced.
"""
import hashlib
import pathlib

import check_shortlist as cs
import journal
import discover_fixtures as fx

REPO = pathlib.Path(__file__).resolve().parents[2]


def run(workspace, capsys):
    code = cs.main(["--workspace", str(workspace)])
    return code, capsys.readouterr()


def test_a_workspace_that_entered_the_mode_is_quiet(tmp_path, capsys):
    # THE quiet twin. build_workspace records the entry the way
    # scripts/enter_mode.py does, so the backstop cannot start firing on an
    # ordinary run without every other shortlist test going red at once.
    workspace = fx.build_workspace(tmp_path)
    code, captured = run(workspace, capsys)
    assert code == 0
    assert captured.out == ""


def test_no_mode_entry_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    fx.write_journal(workspace, fx.JOURNAL, mode_entry=False)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert captured.out.startswith("NO_MODE_ENTRY:")
    assert "scripts/enter_mode.py" in captured.out


def test_a_mode_file_changed_after_entry_fires(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    stale = dict(fx.mode_entry_record(),
                 mode_file_sha256=hashlib.sha256(b"an older draft").hexdigest())
    fx.write_journal(workspace, [stale] + list(fx.JOURNAL), mode_entry=False)
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "MODE_FILE_CHANGED:" in captured.out
    assert "re-enter" in captured.out


def test_the_hash_is_read_from_the_real_mode_file():
    # If this ever passes against a file that is not modes/discover.md, the
    # check is measuring nothing.
    record = fx.mode_entry_record()
    expected = hashlib.sha256(
        (REPO / "modes" / "discover.md").read_bytes()).hexdigest()
    assert record["mode_file_sha256"] == expected


def test_a_hand_written_receipt_is_reported(tmp_path, capsys):
    """Mutation-found 2026-09-05: the RECEIPT_UNVERIFIED loop in this gate was
    unpinned — deleting it left every shortlist test green."""
    workspace = fx.build_workspace(tmp_path)
    journal.append(workspace, {"action": "gate", "gate": "check_no_write",
                               "verdict": "pass", "input_hashes": {}, "findings": []})
    code, captured = run(workspace, capsys)
    assert code == 1
    assert "RECEIPT_UNVERIFIED" in captured.out


def test_a_skill_root_without_the_mode_file_is_reported_not_skipped(tmp_path, capsys):
    workspace = fx.build_workspace(tmp_path)
    empty = tmp_path / "emptyroot"
    (empty / "modes").mkdir(parents=True)
    code = cs.main(["--workspace", str(workspace), "--skill-root", str(empty)])
    assert code == 1
    assert "MODE_FILE_MISSING" in capsys.readouterr().out
