"""Weekly digest: `digest.py setup` records the user's answers (plan gap, Task 6 ruling)."""
import pathlib
import sys

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import digest
import paths


@pytest.fixture
def brief(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path / "store")
    path = tmp_path / "brief.yaml"
    path.write_text(yaml.safe_dump({"slug": "2026-10-01-example-round", "target_titles": ["ML Engineer"],
                                    "markets": ["nl"], "max_rows_per_round": 25}), encoding="utf-8")
    return path


def args(brief, **over):
    base = {"--name": "Jane Doe", "--recipient": "jane@example.org", "--weekday": "0", "--hour": "9",
            "--brief": str(brief), "--language": "zh",
            "--agent-command": "/abs/claude", "--agent-cwd": "/home/jane", "--python": "/abs/python",
            "--words": "每周一早上九点，发到我自己邮箱"}
    base.update(over)
    out = ["setup"]
    for k, v in base.items():
        out += [k, v]
    return out


def test_setup_records_settings_and_enables(brief):
    assert digest.main(args(brief)) == 0
    s = digest.load_settings("Jane Doe")
    assert s["enabled"] is True and s["recipient"] == "jane@example.org"
    assert s["schedule"] == {"weekday": 0, "hour": 9}
    assert {k: s["agent"][k] for k in ("command", "cwd", "python")} == \
        {"command": "/abs/claude", "cwd": "/home/jane", "python": "/abs/python"}
    assert s["agent"]["path"] and s["setup_at"]
    assert s["standing_brief"]["target_titles"] == ["ML Engineer"]
    assert s["answers"][-1]["words"] == "每周一早上九点，发到我自己邮箱"


@pytest.mark.parametrize("flag,value", [("--weekday", "7"), ("--hour", "24"),
                                        ("--recipient", "not-an-address"), ("--agent-command", "claude")])
def test_setup_refuses_bad_values(brief, flag, value):
    assert digest.main(args(brief, **{flag: value})) == 2
    assert not paths.digest_settings("Jane Doe").exists()


def test_setup_keeps_history_and_reenables_after_cancel(brief):
    digest.main(args(brief))
    s = digest.load_settings("Jane Doe")
    s["last_sent"], s["threads"] = "2026-11-02T09:00", ["t1"]
    digest.save_settings("Jane Doe", s)
    digest.cancel("Jane Doe", "stop", __import__("datetime").date(2026, 11, 3))
    assert digest.main(args(brief, **{"--hour": "8"})) == 0
    s = digest.load_settings("Jane Doe")
    assert s["enabled"] is True and s["cancelled"] is None and s["threads"] == ["t1"]
    assert s["schedule"]["hour"] == 8


def test_workspace_command_creates_a_fresh_run_folder(brief, capsys):
    assert digest.main(["workspace", "--name", "Jane Doe", "--today", "2026-11-09"]) == 0
    first = pathlib.Path(capsys.readouterr().out.strip())
    assert first.is_dir() and first.name == "2026-11-09-weekly-digest"
    assert digest.main(["workspace", "--name", "Jane Doe", "--today", "2026-11-09"]) == 0
    assert pathlib.Path(capsys.readouterr().out.strip()).name == "2026-11-09-weekly-digest-2"
