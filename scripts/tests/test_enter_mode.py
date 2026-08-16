"""enter_mode is the one script that was allowed to create a workspace.

Four gates carry the same comment explaining why nothing may: "a helper that created
directories would materialise an empty workspace on a typo, and the resume lookup would
then find a shell". check_apply, check_letter, check_pages and check_personal_data each
refuse to journal into a directory that is not there — and then step 0 of every mode ran
`enter_mode.py`, whose journal.append() mkdir'd it. One mistyped `--workspace` produced a
directory holding a single mode_entry line, and the "resume an in-progress application"
lookup finds that by shape and offers to continue from it.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import enter_mode


def skill_root(tmp_path, modes=("apply", "assess", "discover", "interview")):
    root = tmp_path / "skill"
    (root / "modes").mkdir(parents=True, exist_ok=True)
    for mode in modes:
        (root / "modes" / f"{mode}.md").write_text(f"# Mode: {mode}\n", encoding="utf-8")
    return root


def test_a_workspace_that_does_not_exist_is_refused_and_not_created(tmp_path, capsys):
    root = skill_root(tmp_path)
    ws = tmp_path / "typpo-engineer-2026-08-16"
    assert enter_mode.main(["--workspace", str(ws), "--mode", "apply",
                            "--skill-root", str(root)]) == 2
    assert not ws.exists()
    err = capsys.readouterr().err
    assert str(ws) in err
    # The message has to say what to do, or the reader's next move is to re-run it.
    assert "mkdir" in err


def test_an_existing_workspace_still_enters_the_mode(tmp_path, capsys):
    """The quiet direction, and the one that matters: a real run must be untouched."""
    root = skill_root(tmp_path)
    ws = tmp_path / "acme-engineer-2026-08-16"
    ws.mkdir()
    assert enter_mode.main(["--workspace", str(ws), "--mode", "apply",
                            "--skill-root", str(root)]) == 0
    capsys.readouterr()
    records = [json.loads(line) for line in
               (ws / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["action"] for r in records] == ["mode_entry"]
    assert records[0]["mode"] == "apply"
    assert enter_mode.latest_mode_entry(ws, "apply") == records[0]


def test_a_missing_mode_file_in_a_real_workspace_still_leaves_its_trace(tmp_path, capsys):
    """The other refusal, unchanged. A failed entry that left no trace looks exactly
    like an entry nobody attempted — the silence the record exists to break."""
    root = skill_root(tmp_path, modes=())
    ws = tmp_path / "acme-engineer-2026-08-16"
    ws.mkdir()
    assert enter_mode.main(["--workspace", str(ws), "--mode", "apply",
                            "--skill-root", str(root)]) == 2
    capsys.readouterr()
    records = [json.loads(line) for line in
               (ws / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["action"] for r in records] == ["mode_entry_failed"]
    assert enter_mode.latest_mode_entry(ws, "apply") is None


def test_the_workspace_check_comes_before_the_mode_file_check(tmp_path, capsys):
    """Both are wrong; only one of them can be reported without creating something.
    Writing mode_entry_failed first would mkdir the very directory being refused."""
    root = skill_root(tmp_path, modes=())
    ws = tmp_path / "typpo-engineer-2026-08-16"
    assert enter_mode.main(["--workspace", str(ws), "--mode", "apply",
                            "--skill-root", str(root)]) == 2
    assert not ws.exists()
