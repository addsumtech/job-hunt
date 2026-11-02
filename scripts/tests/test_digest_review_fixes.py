"""Weekly digest: fixes from the whole-branch review (C1-C4, I1-I3, I5)."""
import datetime
import json
import pathlib
import plistlib
import sys
import types

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import digest
import digest_inbox as inbox
import digest_ledger
import discover_fixtures as fx
import paths

READ = "51job-173199597"
SKILL = pathlib.Path("/opt/skills/job-hunt")
PY = "/opt/venv/bin/python"
ME = "jane@example.org"


@pytest.fixture
def ws(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path / "store")
    digest.save_settings("Jane Doe", {
        "enabled": True, "recipient": ME, "language": "en", "budget_usd": 2.0,
        "schedule": {"weekday": 0, "hour": 9}, "last_sent": "2026-11-02T09:00",
        "agent": {"command": "/abs/claude", "cwd": "/home/jane", "python": PY,
                  "path": "/home/jane/.local/bin:/usr/bin:/bin"}})
    root = paths.profile_dir("Jane Doe") / "searches"
    root.mkdir(parents=True)
    workspace = fx.build_workspace(root)
    (workspace / "digest-picks.yaml").write_text(yaml.safe_dump(
        {"roles": [{"id": READ, "why": "w", "gaps": "g"}], "unread": 0}), encoding="utf-8")
    (workspace / "digest-sources.yaml").write_text(yaml.safe_dump(
        {"checked": ["51job"], "unchecked": []}), encoding="utf-8")
    assert digest.main(["compose", "--name", "Jane Doe", "--workspace", str(workspace)]) == 0
    return workspace




# C2 — a send is recorded before it happens and resolved after
def test_presend_records_before_sending_and_sent_only_attaches_ids(ws):
    assert digest.main(["presend", "--name", "Jane Doe", "--workspace", str(ws)]) == 0
    s = digest.load_settings("Jane Doe")
    assert s["pending_send"]["workspace"] == str(ws) and s["last_sent"] != "2026-11-02T09:00"
    row = next(r for r in fx.SHORTLIST["rows"] if r["id"] == READ)
    assert digest_ledger.is_seen(row, digest_ledger.load_ledger("Jane Doe"))
    assert digest.main(["sent", "--name", "Jane Doe", "--workspace", str(ws), "--message-id", "m1"]) == 0
    s = digest.load_settings("Jane Doe")
    assert s["pending_send"] is None


def test_presend_refuses_on_gate_failure(ws):
    (ws / "digest-picks.yaml").write_text(yaml.safe_dump(
        {"roles": [{"id": "51job-173198362", "why": "w", "gaps": "g"}], "unread": 0}), encoding="utf-8")
    digest.main(["compose", "--name", "Jane Doe", "--workspace", str(ws)])
    assert digest.main(["presend", "--name", "Jane Doe", "--workspace", str(ws)]) == 1
    s = digest.load_settings("Jane Doe")
    assert s.get("pending_send") is None and s["last_sent"] == "2026-11-02T09:00"


def test_send_failed_rolls_back(ws):
    digest.main(["presend", "--name", "Jane Doe", "--workspace", str(ws)])
    assert digest.main(["send-failed", "--name", "Jane Doe", "--workspace", str(ws),
                        "--reason", "gmail error 500"]) == 0
    s = digest.load_settings("Jane Doe")
    assert s["pending_send"] is None and s["last_sent"] == "2026-11-02T09:00"
    assert digest_ledger.load_ledger("Jane Doe") == {"roles": []}


def test_sent_without_presend_is_refused(ws):
    assert digest.main(["sent", "--name", "Jane Doe", "--workspace", str(ws), "--message-id", "m1"]) == 2


def test_unconfirmed_send_makes_a_run_due_to_resolve_it(ws):
    digest.main(["presend", "--name", "Jane Doe", "--workspace", str(ws)])
    s = digest.load_settings("Jane Doe")
    at = datetime.datetime.fromisoformat(s["pending_send"]["at"])
    assert digest.due(s, at + datetime.timedelta(hours=1))[0] is False
    assert digest.due(s, at + datetime.timedelta(hours=3, minutes=1)) == (True, "unconfirmed_send")


def test_status_prints_the_pending_send(ws, capsys):
    digest.main(["presend", "--name", "Jane Doe", "--workspace", str(ws)])
    capsys.readouterr()
    assert digest.main(["status", "--name", "Jane Doe"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["pending_send"]["subject"].startswith("[job-hunt weekly]")




# I1 — cancel must be meant
@pytest.mark.parametrize("text", ["Don't cancel, I like it", "do not unsubscribe me", "别取消推送，挺好的",
                                  "#2 not relevant because it is at Cancel Corp", "不要取消"])
def test_negated_or_incidental_cancel_does_not_cancel(text):
    assert inbox.classify(text)["cancel"] is False


@pytest.mark.parametrize("text", ["cancel", "Please cancel this digest", "cancel it please", "取消推送",
                                  "不要再发了", "stop sending", "unsubscribe"])
def test_meant_cancel_still_cancels(text):
    assert inbox.classify(text)["cancel"] is True


# I2 — wrapped instruction fragments and bare header lines
def test_wrapped_own_instruction_does_not_cancel_or_pause():
    import digest_compose
    sentence = digest_compose.TEXT["zh"]["reply"]
    wrapped = sentence[:9] + "\n" + sentence[9:24] + "\n" + sentence[24:]
    c = inbox.classify("好的谢谢\n" + wrapped)
    assert c["cancel"] is False and c["pause_weeks"] is None


def test_bare_wrote_line_starts_the_quote():
    c = inbox.classify("thanks\nJane Doe\nwrote:\nreply unsubscribe to stop")
    assert c["cancel"] is False


# I3 — thread id optional; replies matched by sender and subject tag
def test_reply_matched_by_subject_tag_when_thread_unknown(ws):
    msg = {"id": "r1", "thread_id": "unknown", "from": ME, "subject": "Re: [job-hunt weekly] 2026-11-09 — 1 new role(s)",
           "date": "2026-11-10", "body": "pause 2 weeks"}
    assert inbox.apply_messages("Jane Doe", [msg], datetime.date(2026, 11, 10),
                                run=lambda *a, **k: None)["action"] == "pause"


def test_compose_writes_to_as_a_list(ws):
    assert json.loads((ws / "digest-email.json").read_text())["to"] == [ME]


# I5 — the first run waits for the slot after setup
def test_first_run_waits_for_the_first_slot_after_setup():
    s = {"enabled": True, "schedule": {"weekday": 0, "hour": 9}, "last_sent": None,
         "setup_at": "2026-11-04T15:00"}
    assert digest.due(s, datetime.datetime(2026, 11, 5, 10, 0))[0] is False
    assert digest.due(s, datetime.datetime(2026, 11, 9, 9, 0)) == (True, "due")
