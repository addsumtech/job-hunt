"""Task 2: GitHub fetch and snapshot, replayed through a fake `get` (no network)."""
import datetime
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import online_presence as op
import paths

API = "https://api.github.com"
D = datetime.date(2026, 11, 1)


def repo(full, owner, fork=False, archived=False, stars=3, forks=1, pushed="2026-10-30T10:00:00Z"):
    return {"full_name": full, "html_url": f"https://github.com/{full}", "owner": {"login": owner},
            "description": f"{full} description", "created_at": "2026-06-14T08:48:32Z",
            "pushed_at": pushed, "stargazers_count": stars, "forks_count": forks,
            "fork": fork, "archived": archived, "topics": ["ai"]}


def fake(routes):
    calls = []

    def get(url):
        calls.append(url)
        if url in routes:
            status, body = routes[url]
            return status, json.dumps(body).encode() if not isinstance(body, bytes) else body
        return 404, b'{"message": "Not Found"}'
    get.calls = calls
    return get


def base_routes():
    return {
        f"{API}/users/janedoe/repos?per_page=100&type=owner": (200, [
            repo("janedoe/tool", "janedoe", stars=12),
            repo("janedoe/forked", "janedoe", fork=True),
            repo("janedoe/old", "janedoe", archived=True),
        ]),
        f"{API}/repos/janedoe/tool/releases/latest": (200, {"tag_name": "v1.2.0"}),
    }


def test_forks_archived_and_no_commit_repos_are_left_out():
    routes = base_routes()
    routes[f"{API}/orgs/acme/repos?per_page=100"] = (200, [repo("acme/infra", "acme")])
    routes[f"{API}/repos/acme/infra/contributors?per_page=100"] = (200, [{"login": "someone"}])
    result = op.fetch_github("janedoe", ["acme"], fake(routes))
    assert result["outcome"] == "ok"
    assert [r["full_name"] for r in result["repos"]] == ["janedoe/tool"]


def test_extra_org_repo_is_included_with_contributor_role():
    routes = base_routes()
    routes[f"{API}/repos/addsumtech/slides_maker"] = (200, repo("addsumtech/slides_maker", "addsumtech", stars=646))
    routes[f"{API}/repos/addsumtech/slides_maker/contributors?per_page=100"] = (
        200, [{"login": "janedoe"}, {"login": "helper"}])
    routes[f"{API}/repos/addsumtech/slides_maker/releases/latest"] = (200, {"tag_name": "v6.1.0"})
    result = op.fetch_github("janedoe", ["addsumtech/slides_maker"], fake(routes))
    by_name = {r["full_name"]: r for r in result["repos"]}
    assert by_name["addsumtech/slides_maker"]["role"] == "top_contributor"
    assert by_name["addsumtech/slides_maker"]["stars"] == 646
    assert by_name["addsumtech/slides_maker"]["latest_release"] == "v6.1.0"
    assert by_name["janedoe/tool"]["role"] == "owner"


def test_lower_ranked_contributor_role():
    routes = base_routes()
    routes[f"{API}/repos/acme/lib"] = (200, repo("acme/lib", "acme"))
    routes[f"{API}/repos/acme/lib/contributors?per_page=100"] = (200, [{"login": "x"}, {"login": "janedoe"}])
    result = op.fetch_github("janedoe", ["acme/lib"], fake(routes))
    assert {r["full_name"]: r["role"] for r in result["repos"]}["acme/lib"] == "contributor"


def test_rate_limit_403_is_refused_and_has_no_repos():
    routes = base_routes()
    routes[f"{API}/users/janedoe/repos?per_page=100&type=owner"] = (
        403, {"message": "API rate limit exceeded for 1.2.3.4."})
    result = op.fetch_github("janedoe", [], fake(routes))
    assert result["outcome"] == "refused" and result["repos"] == [] and result["code"] == 403


def test_rate_limit_midway_refuses_the_whole_fetch():
    routes = base_routes()
    routes[f"{API}/repos/janedoe/tool/releases/latest"] = (429, {"message": "Too Many Requests"})
    result = op.fetch_github("janedoe", [], fake(routes))
    assert result["outcome"] == "refused" and result["repos"] == []


def test_404_user_is_failed_with_code():
    result = op.fetch_github("jandoe", [], fake({}))
    assert result["outcome"] == "failed" and result["code"] == 404 and result["repos"] == []


def test_empty_account_is_ok_with_no_repos():
    routes = {f"{API}/users/janedoe/repos?per_page=100&type=owner": (200, [])}
    result = op.fetch_github("janedoe", [], fake(routes))
    assert result["outcome"] == "ok" and result["repos"] == []


def test_mistyped_extra_is_reported_not_fatal():
    result = op.fetch_github("janedoe", ["acme/nope"], fake(base_routes()))
    assert result["outcome"] == "ok"
    assert result["missing_extra"] == ["acme/nope"]


def test_transport_error_is_failed():
    def get(url):
        return 0, b""
    result = op.fetch_github("janedoe", [], get)
    assert result["outcome"] == "failed" and result["repos"] == []


def test_snapshot_and_raw_are_written_and_journaled(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path)
    ws = paths.profile_dir("Jane Doe") / "applications" / "acme-x-2026-11-01"
    result = op.fetch_github("janedoe", [], fake(base_routes()))
    snap = op.write_snapshot("Jane Doe", "github", result, D, workspace=ws)
    assert snap == paths.online_presence_dir("Jane Doe") / "snapshots" / "2026-11-01-github.json"
    data = json.loads(snap.read_text())
    assert data["outcome"] == "ok" and "raw" not in data and data["raw_files"]
    for name in data["raw_files"]:
        assert (paths.online_presence_dir("Jane Doe") / name).is_file()
    journal_lines = [json.loads(l) for l in (ws / "journal.jsonl").read_text().splitlines()]
    assert any(r["action"] == "online_presence_fetch" and r["source"] == "github"
               and r["outcome"] == "ok" for r in journal_lines)


def test_http_get_reports_status_and_body_without_raising(monkeypatch):
    import urllib.error

    def boom(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)
    monkeypatch.setattr(op.urllib.request, "urlopen", boom)
    assert op.http_get(f"{API}/users/nobody/repos")[0] == 404
