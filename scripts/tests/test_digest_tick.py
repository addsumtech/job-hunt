"""Weekly digest, task 2: the hourly tick, the headless agent command, the scheduler."""
import datetime
import pathlib
import plistlib
import sys
import types

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import digest
import paths

NOW = datetime.datetime(2026, 11, 9, 9, 30)
SKILL = pathlib.Path("/opt/skills/job-hunt")
PY = pathlib.Path("/opt/venv/bin/python")
ROOT = pathlib.Path("/home/jane/.claude/job-profiles")


def settings(**extra):
    base = {"enabled": True, "schedule": {"weekday": 0, "hour": 9}, "last_sent": "2026-11-02T09:05",
            "recipient": "jane@example.org", "budget_usd": 2.0,
            "agent": {"command": "/abs/claude", "cwd": "/home/jane", "python": str(PY)}}
    base.update(extra)
    return base


@pytest.fixture
def tmp_store(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path / "store")
    digest.save_settings("Jane Doe", settings())
    return tmp_path / "store"


class FakeRun:
    def __init__(self, code=0, effect=None):
        self.calls, self.code, self.effect = [], code, effect

    def __call__(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        if self.effect:
            self.effect()
        return types.SimpleNamespace(returncode=self.code, stdout="", stderr="")













def test_scheduler_entries_use_absolute_paths():
    plist = digest.scheduler_entry("Jane Doe", "darwin", PY, SKILL, ROOT)
    data = plistlib.loads(plist.encode())
    assert data["ProgramArguments"][:3] == [str(PY), f"{SKILL}/scripts/digest.py", "tick"]
    assert data["StartInterval"] == 3600 and data["RunAtLoad"] is True
    assert data["EnvironmentVariables"]["JOBHUNT_PROFILES_ROOT"] == str(ROOT)
    assert data["Label"] == "com.jobhunt.digest.jane-doe"
    line = digest.scheduler_entry("Jane Doe", "linux", PY, SKILL, ROOT)
    assert line.startswith("0 * * * * ") and "# job-hunt digest jane-doe" in line
    assert f"JOBHUNT_PROFILES_ROOT={ROOT}" in line and str(PY) in line
    assert "@reboot" in line


def test_scheduler_entry_quotes_unusual_names():
    line = digest.scheduler_entry("Jane O'Doe", "linux", PY, SKILL, ROOT)
    assert "'Jane O'\"'\"'Doe'" in line


def test_windows_is_refused():
    with pytest.raises(ValueError):
        digest.scheduler_entry("Jane Doe", "win32", PY, SKILL, ROOT)


def test_install_and_uninstall_call_launchctl(tmp_store, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    run = FakeRun()
    plist = digest.install("Jane Doe", platform="darwin", run=run)
    assert plist == tmp_path / "home" / "Library" / "LaunchAgents" / "com.jobhunt.digest.jane-doe.plist"
    assert plist.is_file()
    assert any(c[0][:2] == ["launchctl", "bootstrap"] for c in run.calls)
    digest.uninstall("Jane Doe", platform="darwin", run=run)
    assert not plist.exists()
    assert any(c[0][:2] == ["launchctl", "bootout"] for c in run.calls)


def test_install_and_uninstall_edit_only_our_crontab_lines(tmp_store):
    table = {"text": "5 4 * * * backup.sh\n"}

    def run(cmd, **kwargs):
        if cmd == ["crontab", "-l"]:
            return types.SimpleNamespace(returncode=0, stdout=table["text"], stderr="")
        if cmd == ["crontab", "-"]:
            table["text"] = kwargs["input"]
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")
    digest.install("Jane Doe", platform="linux", run=run)
    digest.install("Jane Doe", platform="linux", run=run)        # idempotent
    assert table["text"].count("# job-hunt digest jane-doe") == 2  # hourly + @reboot
    assert "backup.sh" in table["text"]
    digest.uninstall("Jane Doe", platform="linux", run=run)
    assert table["text"] == "5 4 * * * backup.sh\n"


def test_cli_cancel_and_pause(tmp_store):
    assert digest.main(["pause", "--name", "Jane Doe", "--weeks", "2", "--words", "pause 2"]) == 0
    assert digest.load_settings("Jane Doe")["paused_until"]
    assert digest.main(["cancel", "--name", "Jane Doe", "--words", "stop it", "--no-uninstall"]) == 0
    assert digest.load_settings("Jane Doe")["cancelled"]["words"] == "stop it"
