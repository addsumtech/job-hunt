"""Weekly digest, revision 2026-11-02: remind at the slot, run with the user present."""
import datetime
import pathlib
import shlex
import sys
import types

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import digest
import paths

NOW = datetime.datetime(2026, 11, 9, 9, 30)       # Monday, slot is Monday 09:00
SKILL = pathlib.Path("/opt/skills/job-hunt")


@pytest.fixture
def tmp_store(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path / "store")
    digest.save_settings("Jane Doe", {
        "enabled": True, "schedule": {"weekday": 0, "hour": 9}, "last_sent": "2026-11-02T09:05",
        "recipient": "jane@example.org",
        "agent": {"command": "/abs/claude", "cwd": "/home/jane", "python": "/abs/python"}})
    return tmp_path / "store"


class Recorder:
    def __init__(self, answer="run"):
        self.answer, self.asked, self.launched, self.notes = answer, [], [], []

    def ask(self, question):
        self.asked.append(question)
        return self.answer

    def launch(self, command, platform):
        self.launched.append(command)
        return "started"

    def notify(self, title, message):
        self.notes.append(message)


def tick(rec, now):
    return digest.tick("Jane Doe", now, ask=rec.ask, launch=rec.launch, notify=rec.notify)


def test_not_due_asks_nothing(tmp_store):
    rec = Recorder()
    assert tick(rec, NOW.replace(hour=8)) == "not_due:not_yet"
    assert rec.asked == [] and rec.launched == []


def test_run_now_starts_an_interactive_session(tmp_store):
    rec = Recorder("run")
    assert tick(rec, NOW) == "started"
    command = rec.launched[0]
    assert "/abs/claude" in command and "weekly-digest.md" in command
    assert "-p " not in command and "dontAsk" not in command   # the user is present
    assert command.startswith("cd /home/jane && ")
    assert f"JOBHUNT_PROFILES_ROOT={shlex.quote(str(paths.PROFILES_ROOT))}" in command
    s = digest.load_settings("Jane Doe")
    assert s["reminded_at"] == "2026-11-09T09:30" and s["attempts"] == {"2026-11-09": 1}


def test_later_asks_again_after_three_hours(tmp_store):
    rec = Recorder("later")
    assert tick(rec, NOW) == "later"
    assert tick(rec, NOW + datetime.timedelta(hours=1)) == "not_due:reminded"
    assert tick(rec, NOW + datetime.timedelta(hours=3, minutes=1)) == "later"
    assert len(rec.asked) == 2 and rec.launched == []


def test_no_answer_is_treated_like_later(tmp_store):
    rec = Recorder("no_answer")
    assert tick(rec, NOW) == "no_answer"
    assert tick(rec, NOW + datetime.timedelta(minutes=50)) == "not_due:reminded"


def test_at_most_three_reminders_a_day(tmp_store):
    rec = Recorder("later")
    for hours in (0, 4, 8):
        tick(rec, NOW + datetime.timedelta(hours=hours))
    assert tick(rec, NOW + datetime.timedelta(hours=12)) == "not_due:attempt_cap"
    assert len(rec.asked) == 3


def test_three_days_without_a_digest_stop_until_next_slot(tmp_store):
    rec = Recorder("later")
    for day in (9, 10, 11):
        for hours in (0, 4, 8):
            tick(rec, datetime.datetime(2026, 11, day, 9, 30) + datetime.timedelta(hours=hours))
    assert tick(rec, datetime.datetime(2026, 11, 12, 10, 0)) == "not_due:stuck"
    assert sum("stopped reminding" in n for n in rec.notes) == 1


def test_a_sent_digest_resets_the_reminders(tmp_store):
    tick(Recorder("later"), NOW)
    s = digest.load_settings("Jane Doe")
    s["pending_send"] = {"workspace": "/w", "subject": "x", "at": "2026-11-09T10:00"}
    digest.save_settings("Jane Doe", s)
    digest.record_attempt("Jane Doe", NOW, ok=True)
    s = digest.load_settings("Jane Doe")
    assert s["failed_days"] == [] and s.get("stuck_until") is None


def test_session_command_quotes_the_name():
    cmd = digest.session_command({"agent": {"command": "/abs/claude", "cwd": "/home/jane"}},
                                 "Jane O'Doe", SKILL, pathlib.Path("/store"))
    assert shlex.split(cmd.split(" && ", 1)[1])[-1].count("Jane O'Doe") == 1


def test_session_command_needs_absolute_paths():
    with pytest.raises(ValueError):
        digest.session_command({"agent": {"command": "claude", "cwd": "/home/jane"}}, "J", SKILL,
                               pathlib.Path("/store"))


@pytest.mark.parametrize("stdout,code,expected", [
    ("button returned:Run now, gave up:false\n", 0, "run"),
    ("button returned:Later, gave up:false\n", 0, "later"),
    ("button returned:, gave up:true\n", 0, "no_answer"),
    ("", 1, "later"),                                    # the user closed the dialog
])
def test_dialog_answer_is_parsed(stdout, code, expected):
    def run(cmd, **kwargs):
        return types.SimpleNamespace(returncode=code, stdout=stdout, stderr="")
    assert digest.ask_user("Run this week's digest now?", platform="darwin", run=run) == expected


def test_linux_has_no_dialog_and_notifies_the_command(tmp_store):
    notes = []
    result = digest.launch_session("cd /x && claude 'go'", platform="linux",
                                   run=lambda *a, **k: None, notify=lambda t, m: notes.append(m))
    assert result == "notified" and "claude 'go'" in notes[0]


def test_macos_launch_opens_terminal_with_the_command():
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")
    assert digest.launch_session('cd /x && claude "say \\"hi\\""', platform="darwin", run=run) == "started"
    script = calls[0][-1]
    assert calls[0][0] == "osascript" and 'tell application "Terminal"' in script
    literal = script.split("do script ", 1)[1].rsplit("\nend tell", 1)[0]
    decoded = literal[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    assert decoded == 'cd /x && claude "say \\"hi\\""'      # AppleScript string round-trips


def test_locked_tick_asks_nothing(tmp_store):
    digest.acquire_lock("Jane Doe", NOW)
    rec = Recorder()
    assert tick(rec, NOW) == "locked" and rec.asked == []
