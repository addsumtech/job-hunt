"""Task 5: confirmed findings are written into the master through save_profile."""
import datetime
import json
import pathlib
import sys

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import journal
import online_presence as op
import paths
from test_online_presence_github import API, fake, repo

D = datetime.date(2026, 11, 1)
HEADER = "# Master career profile for Jane Doe.\n# Never mutated by tailoring.\n"


@pytest.fixture
def store(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path / "store")
    op.record_answer("Jane Doe", "github", "given", "janedoe", "janedoe",
                     extra=["acme/slides_maker"])
    return paths.profile_dir("Jane Doe") / "applications" / "acme-x-2026-11-01"


def write_master(data, filename="profile.yaml"):
    directory = paths.profile_dir("Jane Doe")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(HEADER + yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def found_repo(store, *repos):
    routes = {f"{API}/users/janedoe/repos?per_page=100&type=owner": (200, [r for r in repos if r["owner"]["login"] == "janedoe"])}
    for r in repos:
        routes[f"{API}/repos/{r['full_name']}"] = (200, r)
        routes[f"{API}/repos/{r['full_name']}/contributors?per_page=100"] = (200, [{"login": "janedoe"}])
        routes[f"{API}/repos/{r['full_name']}/releases/latest"] = (200, {"tag_name": "v6.1.0"})
    return op.check("Jane Doe", store, D, force=True, get=fake(routes))


def base_master():
    return {"meta": {"name": "Jane Doe", "language": "en"},
            "contact": {"email": "j@example.org", "links": {}},
            "projects": [{"name": "Old project", "description": "Written by Jane, keep as is."}],
            "publications": ["Known Paper — Venue, 2024."]}


def test_confirmed_repo_becomes_a_project_without_star_counts(store):
    master = write_master(base_master())
    found_repo(store, repo("acme/slides_maker", "acme", stars=646, forks=59))
    op.confirm("Jane Doe", "github:acme/slides_maker", "confirmed", "yes, I lead it",
               {"role": "Creator and lead maintainer"})
    assert op.writeback("Jane Doe", "en", store) == ["github:acme/slides_maker"]
    data = journal.load_yaml(master)
    entry = data["projects"][-1]
    assert entry["name"] == "slides_maker"
    assert entry["role"] == "Creator and lead maintainer"
    assert entry["links"] == ["https://github.com/acme/slides_maker"]
    text = json.dumps(entry)
    assert "646" not in text and "59" not in text and "v6.1.0" not in text
    assert data["contact"]["links"]["github"] == "github.com/janedoe"
    assert master.read_text(encoding="utf-8").startswith(HEADER)


def test_confirmed_paper_becomes_a_publication(store):
    master = write_master(base_master())
    record_path = paths.online_presence("Jane Doe")
    record = op.load_record(record_path)
    record["findings"].append({"id": "scholar:newpaper", "source": "scholar", "kind": "new_paper",
                               "summary": "New Paper — MIDL, 2026 (J Doe, X)", "status": "pending",
                               "paper": {"title": "New Paper", "venue": "MIDL", "year": 2026,
                                         "authors": "J Doe, X"}})
    op.save_record(record_path, record)
    op.confirm("Jane Doe", "scholar:newpaper", "confirmed", "yes")
    op.writeback("Jane Doe", "en", None)
    assert journal.load_yaml(master)["publications"][-1] == "New Paper — MIDL, 2026."


def test_writeback_backs_up_and_logs_shas(store):
    master = write_master(base_master())
    before = journal.sha256_file(master)
    found_repo(store, repo("acme/slides_maker", "acme"))
    op.confirm("Jane Doe", "github:acme/slides_maker", "confirmed", "yes")
    op.writeback("Jane Doe", "en", store)
    backups = list(master.parent.glob("profile.yaml.bak-*"))
    assert len(backups) == 1 and journal.sha256_file(backups[0]) == before
    log = op.load_record(paths.online_presence("Jane Doe"))["writebacks"][-1]
    assert log["before_sha256"] == before and log["after_sha256"] == journal.sha256_file(master)
    assert log["finding_ids"] == ["github:acme/slides_maker"] and log["master"] == str(master)
    assert '"action": "master_writeback"' in (store / "journal.jsonl").read_text()


def test_no_master_leaves_confirmed_unwritten(store):
    found_repo(store, repo("acme/slides_maker", "acme"))
    op.confirm("Jane Doe", "github:acme/slides_maker", "confirmed", "yes")
    assert op.writeback("Jane Doe", "en", None) == []
    finding = op.load_record(paths.online_presence("Jane Doe"))["findings"][0]
    assert finding["status"] == "confirmed_unwritten"
    write_master(base_master())
    assert op.writeback("Jane Doe", "en", None) == ["github:acme/slides_maker"]


def test_unconfirmed_findings_are_never_written(store):
    master = write_master(base_master())
    found_repo(store, repo("acme/slides_maker", "acme"))
    before = master.read_bytes()
    assert op.writeback("Jane Doe", "en", None) == []
    assert master.read_bytes() == before


def test_user_text_in_existing_entry_is_not_edited(store):
    data = base_master()
    data["projects"].append({"name": "Slides Maker", "description": "My own words about it."})
    master = write_master(data)
    found_repo(store, repo("acme/slides_maker", "acme"))
    record_path = paths.online_presence("Jane Doe")
    record = op.load_record(record_path)
    record["findings"].append({"id": "github:acme/slides_maker@v6.1.0", "source": "github",
                               "kind": "new_release", "summary": "released v6.1.0", "status": "pending",
                               "repo": {"full_name": "acme/slides_maker",
                                        "html_url": "https://github.com/acme/slides_maker"}})
    op.save_record(record_path, record)
    op.confirm("Jane Doe", "github:acme/slides_maker@v6.1.0", "confirmed", "yes")
    op.writeback("Jane Doe", "en", None)
    projects = journal.load_yaml(master)["projects"]
    assert {"name": "Slides Maker", "description": "My own words about it."} in projects
    assert sum("slides" in p["name"].lower() for p in projects) == 1


def test_other_language_master_is_offered_not_rewritten(store):
    write_master(base_master())
    zh = base_master()
    zh["meta"]["language"] = "zh"
    zh_path = write_master(zh, "profile.zh.yaml")
    zh_before = zh_path.read_bytes()
    found_repo(store, repo("acme/slides_maker", "acme"))
    op.confirm("Jane Doe", "github:acme/slides_maker", "confirmed", "yes")
    op.writeback("Jane Doe", "en", None)
    assert zh_path.read_bytes() == zh_before
    assert op.status("Jane Doe", D)["pending_for_master"] == {"zh": ["github:acme/slides_maker"]}


def test_writeback_cli(store, capsys):
    write_master(base_master())
    found_repo(store, repo("acme/slides_maker", "acme"))
    assert op.main(["confirm", "--name", "Jane Doe", "--finding", "github:acme/slides_maker",
                    "--decision", "confirmed", "--words", "yes"]) == 0
    assert op.main(["writeback", "--name", "Jane Doe", "--language", "en",
                    "--workspace", str(store)]) == 0
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1])["written"] == ["github:acme/slides_maker"]
