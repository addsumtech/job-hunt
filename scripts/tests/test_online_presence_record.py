"""Task 1: the online-presence record and the ask-once rule."""
import datetime
import json
import pathlib
import sys

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import online_presence as op
import paths

D = datetime.date(2026, 11, 1)


@pytest.fixture
def tmp_store(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path / "profiles")
    (tmp_path / "profiles").mkdir()
    return tmp_path / "profiles"


def write_master(name, data, filename="profile.yaml"):
    directory = paths.profile_dir(name)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_text(yaml.safe_dump(data), encoding="utf-8")


def test_absent_record_asks_all_three(tmp_store):
    assert op.status("Jane Doe", D)["to_ask"] == ["github", "scholar", "website"]


def test_declined_and_none_are_never_asked_again(tmp_store):
    op.record_answer("Jane Doe", "github", "declined", None, "rather not")
    op.record_answer("Jane Doe", "scholar", "none", None, "no Scholar page")
    op.record_answer("Jane Doe", "website", "given", "https://jane.example", "jane.example")
    assert op.status("Jane Doe", D)["to_ask"] == []


def test_master_links_seed_the_record_without_asking(tmp_store):
    write_master("Jane Doe", {"meta": {"name": "Jane Doe", "language": "en"},
                              "contact": {"links": {"scholar": "scholar.google.com/citations?user=X"}}})
    result = op.status("Jane Doe", D)
    assert "scholar" not in result["to_ask"]
    record = op.load_record(paths.online_presence("Jane Doe"))
    assert record["sources"]["scholar"]["status"] == "given"
    assert record["sources"]["scholar"]["value"] == "scholar.google.com/citations?user=X"


def _check(name, source, date, outcome="ok", code=None):
    path = paths.online_presence(name)
    record = op.load_record(path)
    record["checks"][source] = {"date": date.isoformat(), "outcome": outcome, "code": code}
    op.save_record(path, record)


def test_stale_after_14_days(tmp_store):
    op.record_answer("Jane Doe", "github", "given", "janedoe", "janedoe")
    _check("Jane Doe", "github", datetime.date(2026, 10, 17))
    assert op.status("Jane Doe", D)["stale"] == ["github"]
    _check("Jane Doe", "github", datetime.date(2026, 10, 19))
    assert op.status("Jane Doe", D)["stale"] == []


def test_given_but_never_checked_is_stale(tmp_store):
    op.record_answer("Jane Doe", "github", "given", "janedoe", "janedoe")
    assert op.status("Jane Doe", D)["stale"] == ["github"]


def test_failed_404_is_broken_not_reasked(tmp_store):
    op.record_answer("Jane Doe", "github", "given", "jandoe", "jandoe")
    _check("Jane Doe", "github", D, outcome="failed", code=404)
    result = op.status("Jane Doe", D)
    assert result["broken"] == ["github"]
    assert "github" not in result["to_ask"]


def test_unreadable_record_exits_2_and_is_untouched(tmp_store, capsys):
    path = paths.online_presence("Jane Doe")
    path.parent.mkdir(parents=True)
    path.write_bytes(b"sources: [unclosed\n")
    before = path.read_bytes()
    assert op.main(["status", "--name", "Jane Doe", "--today", "2026-11-01"]) == 2
    assert path.read_bytes() == before
    assert "online-presence.yaml" in capsys.readouterr().err


def test_record_requires_users_words(tmp_store):
    with pytest.raises(SystemExit) as exc:
        op.main(["record", "--name", "Jane Doe", "--source", "github", "--status", "given",
                 "--value", "janedoe"])
    assert exc.value.code == 2


def test_record_given_requires_a_value(tmp_store):
    assert op.main(["record", "--name", "Jane Doe", "--source", "github", "--status", "given",
                    "--words", "yes"]) == 2


def test_github_extra_orgs_are_kept(tmp_store):
    op.main(["record", "--name", "Jane Doe", "--source", "github", "--status", "given",
             "--value", "janedoe", "--extra", "addsumtech/slides_maker", "addsumtech",
             "--words", "janedoe, plus addsumtech"])
    source = op.load_record(paths.online_presence("Jane Doe"))["sources"]["github"]
    assert source["extra"] == ["addsumtech/slides_maker", "addsumtech"]
    assert source["words"] == "janedoe, plus addsumtech"


def test_status_with_workspace_journals_the_step(tmp_store, capsys):
    ws = paths.profile_dir("Jane Doe") / "applications" / "acme-engineer-2026-11-01"
    ws.mkdir(parents=True)
    assert op.main(["status", "--name", "Jane Doe", "--today", "2026-11-01",
                    "--workspace", str(ws)]) == 0
    lines = [json.loads(line) for line in (ws / "journal.jsonl").read_text().splitlines()]
    assert any(r.get("action") == "online_presence_status" for r in lines)
    assert json.loads(capsys.readouterr().out)["to_ask"] == ["github", "scholar", "website"]


@pytest.mark.parametrize("kind", ["applications", "searches"])
def test_online_presence_of_resolves_both_workspace_kinds(tmp_store, kind):
    ws = paths.profile_dir("Jane Doe") / kind / "x-2026-11-01"
    assert paths.online_presence_of(ws) == paths.online_presence("Jane Doe")


def test_online_presence_of_refuses_other_shapes(tmp_path):
    with pytest.raises(ValueError):
        paths.online_presence_of(tmp_path / "loose")
