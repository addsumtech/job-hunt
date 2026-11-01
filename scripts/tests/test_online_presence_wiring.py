"""Task 8: the online-presence step is wired into apply, discover and assess."""
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import online_presence as op

ROOT = pathlib.Path(__file__).resolve().parents[2]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_three_modes_name_the_step_before_freezing_the_profile():
    apply_md = read("modes/apply.md")
    assert "online_presence.py" in apply_md
    assert apply_md.index("online_presence.py") < apply_md.index("check_claims.py --workspace <workspace> \\\n    --master")
    discover = read("modes/discover.md")
    assert discover.index("online_presence.py") < discover.index("snapshot_profile.py --workspace <ws> --profile")
    assess = read("modes/assess.md")
    assert assess.index("online_presence.py") < assess.index("evidence_blocks.py --workspace <ws>")


def test_assess_no_longer_says_never_writes_without_the_exception():
    assess = read("modes/assess.md")
    assert "never writes it." not in assess
    assert "confirmed online-presence write-back" in assess


def test_skill_entry_step_points_to_the_reference():
    section = read("SKILL.md").split("## Enter a full mode", 1)[1].split("\n## ", 1)[0]
    assert "references/online-presence.md" in section
    reference = read("references/online-presence.md")
    for anchor in ("status", "record", "ingest", "check", "confirm", "writeback", "link",
                   "LinkedIn", "at most four", "never re-ask"):
        assert anchor in reference, anchor


def test_step_notice_is_empty_once_status_was_journaled(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    assert "NOTICE_NO_ONLINE_PRESENCE_STEP" in op.step_notice(ws)
    (ws / "journal.jsonl").write_text(json.dumps({"action": "online_presence_status"}) + "\n")
    assert op.step_notice(ws) == ""


def test_gates_notice_on_stderr_and_keep_their_exit_codes(tmp_path, capsys):
    import check_apply
    import check_shortlist
    ws = tmp_path / "ws"
    ws.mkdir()
    before = (check_apply.main(["--workspace", str(ws)]), check_shortlist.main(["--workspace", str(ws)]))
    err = capsys.readouterr().err
    assert err.count("NOTICE_NO_ONLINE_PRESENCE_STEP") == 2
    (ws / "journal.jsonl").write_text(json.dumps({"action": "online_presence_status"}) + "\n")
    after = (check_apply.main(["--workspace", str(ws)]), check_shortlist.main(["--workspace", str(ws)]))
    assert "NOTICE_NO_ONLINE_PRESENCE_STEP" not in capsys.readouterr().err
    assert before == after
