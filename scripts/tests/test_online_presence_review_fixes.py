"""Fixes from the final whole-branch review (2026-11-01)."""
import datetime
import json
import pathlib
import sys

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import online_presence as op
import paths
from test_online_presence_github import API, fake, repo

D = datetime.date(2026, 11, 1)


@pytest.fixture
def store(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path / "store")
    op.record_answer("Jane Doe", "github", "given", "janedoe", "janedoe")
    return paths.profile_dir("Jane Doe") / "applications" / "acme-x-2026-11-01"


def test_refused_check_is_retried_next_run_and_never_called_fresh(store):
    refused = fake({f"{API}/users/janedoe/repos?per_page=100&type=owner": (429, {"message": "slow down"})})
    assert op.check("Jane Doe", store, D, force=False, get=refused)["checked"]["github"] == "refused"
    nxt = D + datetime.timedelta(days=1)
    st = op.status("Jane Doe", nxt)
    assert "github" in st["stale"] and st["refused"] == ["github"]
    ok = fake({f"{API}/users/janedoe/repos?per_page=100&type=owner": (200, [])})
    result = op.check("Jane Doe", store, nxt, force=False, get=ok)
    assert ok.calls and result["checked"]["github"] == "ok"


def test_failed_transport_check_is_retried_too(store):
    op.check("Jane Doe", store, D, force=False, get=lambda url: (0, b""))
    assert "github" in op.status("Jane Doe", D + datetime.timedelta(days=1))["stale"]


def test_short_name_project_in_master_is_not_reproposed_via_check(store):
    directory = paths.profile_dir("Jane Doe")
    (directory / "profile.yaml").write_text(yaml.safe_dump(
        {"meta": {"name": "Jane Doe", "language": "en"}, "projects": [{"name": "nufft"}]}), encoding="utf-8")
    get = fake({f"{API}/users/janedoe/repos?per_page=100&type=owner": (200, [repo("janedoe/nufft", "janedoe")])})
    assert op.check("Jane Doe", store, D, force=False, get=get)["shown"] == []


def test_owner_listing_follows_pages():
    first = [repo(f"janedoe/r{i}", "janedoe") for i in range(100)]
    second = [repo(f"janedoe/s{i}", "janedoe") for i in range(3)]
    routes = {f"{API}/users/janedoe/repos?per_page=100&type=owner": (200, first),
              f"{API}/users/janedoe/repos?per_page=100&type=owner&page=2": (200, second)}
    result = op.fetch_github("janedoe", [], fake(routes))
    assert result["outcome"] == "ok" and len(result["repos"]) == 103


def test_listing_past_the_page_cap_is_not_reported_complete():
    full = [repo(f"janedoe/r{i}", "janedoe") for i in range(100)]
    routes = {f"{API}/users/janedoe/repos?per_page=100&type=owner": (200, full)}
    for page in range(2, op.MAX_PAGES + 2):
        routes[f"{API}/users/janedoe/repos?per_page=100&type=owner&page={page}"] = (200, full)
    result = op.fetch_github("janedoe", [], fake(routes))
    assert result["outcome"] == "failed" and result["repos"] == [] and "partial" in result["reason"]


def test_scholar_text_without_recognised_papers_is_not_an_empty_profile(tmp_path):
    lines = ["Jane Doe", "Title", "Cited by", "Year"] + [f"Some layout line {i}" for i in range(40)]
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"url": "u", "text": "\n".join(lines), "http_status": 200}))
    result = op.ingest_scholar(path)
    assert result["outcome"] == "failed" and "no papers recognised" in result["reason"]


def test_ingest_cli_reports_how_many_papers_it_parsed(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path / "s")
    text = "\n".join(["Title", "A Paper", "J Doe, X", "Venue, 2025"])
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"url": "u", "text": text, "http_status": 200}))
    assert op.main(["ingest", "--name", "Jane Doe", "--source", "scholar", "--capture", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["papers"] == 1
