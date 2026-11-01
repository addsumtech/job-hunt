"""Task 4: snapshots become findings the user confirms."""
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
    ws = paths.profile_dir("Jane Doe") / "applications" / "acme-x-2026-11-01"
    return ws


def master(data):
    directory = paths.profile_dir("Jane Doe")
    directory.mkdir(parents=True, exist_ok=True)
    data.setdefault("meta", {"name": "Jane Doe", "language": "en"})
    (directory / "profile.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")


def owned(*repos, releases=None):
    routes = {f"{API}/users/janedoe/repos?per_page=100&type=owner": (200, list(repos))}
    for r in repos:
        tag = (releases or {}).get(r["full_name"])
        routes[f"{API}/repos/{r['full_name']}/releases/latest"] = (200, {"tag_name": tag}) if tag else (404, {})
    return fake(routes)


def test_first_check_proposes_only_what_master_lacks(store):
    master({"projects": [{"name": "slides_maker", "links": ["github.com/janedoe/slides_maker"]}]})
    result = op.check("Jane Doe", store, D, force=False,
                      get=owned(repo("janedoe/slides_maker", "janedoe"), repo("janedoe/newtool", "janedoe")))
    assert [f["id"] for f in result["shown"]] == ["github:janedoe/newtool"]
    assert result["checked"]["github"] == "ok"


def test_master_match_ignores_case_and_punctuation(store):
    master({"projects": [{"name": "Slides Maker", "description": "presentation skill"}]})
    result = op.check("Jane Doe", store, D, force=False, get=owned(repo("janedoe/slides_maker", "janedoe")))
    assert result["shown"] == []


def test_short_repo_name_is_not_hidden_by_an_unrelated_word(store):
    master({"projects": [{"name": "Toolkit for MRI", "description": "a tool"}]})
    result = op.check("Jane Doe", store, D, force=False, get=owned(repo("janedoe/tool", "janedoe")))
    assert [f["id"] for f in result["shown"]] == ["github:janedoe/tool"]


def test_new_release_is_a_finding_but_star_change_is_not(store):
    op.check("Jane Doe", store, datetime.date(2026, 10, 1), force=False,
             get=owned(repo("janedoe/tool", "janedoe", stars=5), releases={"janedoe/tool": "v1.0"}))
    op.confirm("Jane Doe", "github:janedoe/tool", "ignored", "not relevant")
    stars_only = op.check("Jane Doe", store, D, force=True,
                          get=owned(repo("janedoe/tool", "janedoe", stars=900), releases={"janedoe/tool": "v1.0"}))
    assert stars_only["shown"] == []
    released = op.check("Jane Doe", store, D, force=True,
                        get=owned(repo("janedoe/tool", "janedoe", stars=900), releases={"janedoe/tool": "v2.0"}))
    assert [(f["id"], f["kind"]) for f in released["shown"]] == [("github:janedoe/tool@v2.0", "new_release")]


def test_more_than_four_findings_keeps_the_rest_pending(store):
    repos = [repo(f"janedoe/r{i}", "janedoe", pushed=f"2026-10-{20 + i:02d}T00:00:00Z") for i in range(6)]
    result = op.check("Jane Doe", store, D, force=False, get=owned(*repos))
    assert len(result["shown"]) == 4 and result["pending_count"] == 2
    assert result["shown"][0]["id"] == "github:janedoe/r5"  # most recent first
    record = op.load_record(paths.online_presence("Jane Doe"))
    assert sum(f["status"] == "pending" for f in record["findings"]) == 6


def test_pending_findings_return_on_the_next_run_without_refetch(store):
    repos = [repo(f"janedoe/r{i}", "janedoe") for i in range(6)]
    op.check("Jane Doe", store, D, force=False, get=owned(*repos))
    for finding in op.check("Jane Doe", store, D, force=False, get=owned())["shown"]:
        op.confirm("Jane Doe", finding["id"], "ignored", "no")
    again = op.check("Jane Doe", store, D, force=False, get=owned())
    assert len(again["shown"]) == 2 and again["pending_count"] == 0


def test_ignored_finding_returns_only_when_it_changes(store):
    op.check("Jane Doe", store, datetime.date(2026, 10, 1), force=False, get=owned(repo("janedoe/x", "janedoe")))
    op.confirm("Jane Doe", "github:janedoe/x", "ignored", "skip")
    same = op.check("Jane Doe", store, D, force=True, get=owned(repo("janedoe/x", "janedoe")))
    assert same["shown"] == []
    changed = op.check("Jane Doe", store, D, force=True,
                       get=owned(repo("janedoe/x", "janedoe"), releases={"janedoe/x": "v0.1"}))
    assert [f["kind"] for f in changed["shown"]] == ["new_release"]


def test_fresh_source_is_not_refetched(store):
    op.check("Jane Doe", store, datetime.date(2026, 10, 29), force=False, get=owned())
    calls = owned()
    result = op.check("Jane Doe", store, D, force=False, get=calls)
    assert calls.calls == [] and result["checked"]["github"] == "fresh"


def test_refused_source_yields_no_findings_and_reports_it(store):
    get = fake({f"{API}/users/janedoe/repos?per_page=100&type=owner": (403, {"message": "rate limit"})})
    result = op.check("Jane Doe", store, D, force=False, get=get)
    assert result["checked"]["github"] == "refused" and result["shown"] == []
    assert op.load_record(paths.online_presence("Jane Doe"))["checks"]["github"]["outcome"] == "refused"


def test_empty_paper_list_is_ok_with_zero_findings():
    assert op.diff("scholar", None, {"outcome": "ok", "papers": []}, {}, D) == []


def test_new_paper_not_in_master_publications_is_a_finding():
    current = {"outcome": "ok", "papers": [
        {"title": "Known Paper: A Study", "authors": "J Doe, X", "venue": "V", "year": 2025},
        {"title": "Brand New Paper", "authors": "J Doe, Y", "venue": "MIDL", "year": 2026}]}
    found = op.diff("scholar", None, current, {"publications": ["Known paper - a study, V 2025."]}, D)
    assert [f["id"] for f in found] == ["scholar:brandnewpaper"]


def test_website_first_snapshot_is_a_baseline_then_added_lines_are_found():
    first = {"outcome": "ok", "url": "https://j.example", "text": "Jane\nI build tools."}
    assert op.diff("website", None, first, {}, D) == []
    second = dict(first, text="Jane\nI build tools.\nNew talk at MIDL 2026.")
    found = op.diff("website", first, second, {}, D)
    assert [f["kind"] for f in found] == ["page_changed"]
    assert "New talk at MIDL 2026." in found[0]["summary"]


def test_check_cli_prints_json(store, capsys, monkeypatch):
    monkeypatch.setattr(op, "http_get", owned(repo("janedoe/x", "janedoe")))
    assert op.main(["check", "--name", "Jane Doe", "--workspace", str(store), "--today", "2026-11-01"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["shown"][0]["id"] == "github:janedoe/x"
