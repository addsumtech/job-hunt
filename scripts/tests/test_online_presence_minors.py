"""Deferred minors from the online-presence review, and the Scholar layout seen live.

The Scholar fixture mirrors the structure of a real profile page captured on
2026-11-02 (one row = title / authors / venue / citations? / "*"? / year), with
invented titles and names: no candidate's data is stored in the repository.
"""
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

D = datetime.date(2026, 11, 2)

SCHOLAR_LIVE_SHAPE = "\n".join([
    "Cited by", "All", "Since 2021", "Citations", "186", "186", "h-index", "6", "6",
    "0", "90", "45", "2021", "2022", "2023", "2024", "2025", "2026",
    "Public access", "View all", "6 articles",
    "Jane Doe", "Example University", "Verified email at example.org",
    "Title", "Cited by", "Year",
    "Perceptual quality assessment of low-dose images",
    "W Lee, J Doe, A Smith, ...",
    "Medical Image Analysis 99, 103343",
    "58", "2025",
    "A challenge summary on universal reconstruction",
    "F Wang, J Doe, Y Li, ...",
    "IEEE Transactions on Medical Imaging",
    "18", "*", "2025",
    "Graph-driven segmentation of thin structures",
    "J Doe, Z Zhang",
    "arXiv preprint arXiv:2609.31160",
    "2026",
    "Recurrent networks for dynamic reconstruction",
    "J Doe, M Staring",
    "International Workshop on Statistical Atlases and Computational Models of …",
    "6", "2024",
    "Combining residual and windowed attention for denoising",
    "J Doe",
    "Example Institute, Example University",
    "2023",
    "Articles 1–5", "Show more", "Privacy", "Terms", "Help",
])


@pytest.fixture
def store(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path / "store")
    return paths.profile_dir("Jane Doe") / "applications" / "acme-x-2026-11-02"


def capture(tmp_path, text, url="https://scholar.google.com/citations?user=X&hl=en"):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"url": url, "text": text, "http_status": 200}), encoding="utf-8")
    return path


# ---- Scholar, as the live page lays it out --------------------------------

def test_live_scholar_layout_parses_every_row(tmp_path):
    result = op.ingest_scholar(capture(tmp_path, SCHOLAR_LIVE_SHAPE))
    assert result["outcome"] == "ok"
    papers = result["papers"]
    assert [p["title"] for p in papers] == [
        "Perceptual quality assessment of low-dose images",
        "A challenge summary on universal reconstruction",
        "Graph-driven segmentation of thin structures",
        "Recurrent networks for dynamic reconstruction",
        "Combining residual and windowed attention for denoising"]
    assert papers[1]["citations"] == 18 and papers[1]["year"] == 2025
    assert papers[2]["citations"] is None and papers[2]["year"] == 2026
    assert papers[4]["authors"] == "J Doe" and papers[4]["venue"] == "Example Institute, Example University"
    assert result["expected"] == 5 and "warning" not in result


def test_graph_years_before_the_header_are_not_papers(tmp_path):
    papers = op.ingest_scholar(capture(tmp_path, SCHOLAR_LIVE_SHAPE))["papers"]
    assert all(p["title"] not in {"2021", "Public access", "Jane Doe"} for p in papers)


def test_parsed_count_below_the_page_total_is_warned(tmp_path):
    text = SCHOLAR_LIVE_SHAPE.replace("Articles 1–5", "Articles 1–7")
    result = op.ingest_scholar(capture(tmp_path, text))
    assert result["outcome"] == "ok" and "7" in result["warning"]


def test_paper_without_year_still_counts(tmp_path):
    text = "\n".join(["Title", "Cited by", "Year", "An undated note", "J Doe", "Some venue",
                      "A dated paper", "J Doe, X", "Venue", "3", "2025", "Articles 1–2"])
    papers = op.ingest_scholar(capture(tmp_path, text))["papers"]
    assert [(p["title"], p["year"]) for p in papers] == [("An undated note", None), ("A dated paper", 2025)]


def test_page_without_the_title_header_is_failed(tmp_path):
    result = op.ingest_scholar(capture(tmp_path, "Jane Doe\nSome profile text\nwithout a list"))
    assert result["outcome"] == "failed" and "no papers recognised" in result["reason"]


def test_undated_paper_is_written_without_a_year(store):
    master_path = paths.profile_dir("Jane Doe") / "profile.yaml"
    master_path.parent.mkdir(parents=True, exist_ok=True)
    master_path.write_text(yaml.safe_dump({"meta": {"name": "Jane Doe", "language": "en"}}), encoding="utf-8")
    finding = {"id": "scholar:x", "source": "scholar", "kind": "new_paper", "status": "confirmed",
               "words": "yes", "paper": {"title": "A Note", "authors": "J Doe", "venue": "", "year": None}}
    record = op.load_record(paths.online_presence("Jane Doe"))
    record["findings"].append(finding)
    op.save_record(paths.online_presence("Jane Doe"), record)
    op.writeback("Jane Doe", "en", None)
    assert journal.load_yaml(master_path)["publications"] == ["A Note."]


def test_diff_ranks_undated_papers_without_crashing():
    found = op.diff("scholar", None, {"outcome": "ok", "papers": [
        {"title": "Undated", "authors": "J Doe", "venue": "", "year": None}]}, {}, D)
    assert [f["id"] for f in found] == ["scholar:undated"]


# ---- the eight deferred minors -------------------------------------------

def test_malformed_source_entry_is_flagged_not_reasked(store):
    path = paths.online_presence("Jane Doe")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("sources:\n  github: just-a-string\n", encoding="utf-8")
    st = op.status("Jane Doe", D)
    assert st["malformed"] == ["github"] and "github" not in st["to_ask"]


@pytest.mark.parametrize("value", ["https://github.com/janedoe", "https://www.github.com/janedoe/",
                                   "github.com/janedoe", "@janedoe", " janedoe "])
def test_github_profile_url_is_reduced_to_the_username(store, value):
    op.record_answer("Jane Doe", "github", "given", value, "mine")
    assert op.load_record(paths.online_presence("Jane Doe"))["sources"]["github"]["value"] == "janedoe"


def test_github_value_that_is_not_a_profile_is_refused(store):
    with pytest.raises(ValueError):
        op.record_answer("Jane Doe", "github", "given", "https://gitlab.com/janedoe", "mine")


@pytest.mark.parametrize("status", [202, 204])
def test_contributors_202_or_204_does_not_fail_the_fetch(status):
    routes = {f"{API}/users/janedoe/repos?per_page=100&type=owner": (200, [repo("janedoe/a", "janedoe")]),
              f"{API}/repos/janedoe/a/releases/latest": (404, {}),
              f"{API}/repos/acme/b": (200, repo("acme/b", "acme")),
              f"{API}/repos/acme/b/contributors?per_page=100": (status, b"")}
    result = op.fetch_github("janedoe", ["acme/b"], fake(routes))
    assert result["outcome"] == "ok"
    assert [r["full_name"] for r in result["repos"]] == ["janedoe/a"]


@pytest.mark.parametrize("title", ["Реконструкция МРТ сердца", "Ανακατασκευή εικόνας", "Ré-échantillonnage"])
def test_non_latin_titles_are_proposed_and_matched(title):
    current = {"outcome": "ok", "papers": [{"title": title, "authors": "J Doe, X", "venue": "V", "year": 2026}]}
    found = op.diff("scholar", None, current, {}, D)
    assert len(found) == 1 and found[0]["id"] != "scholar:"
    assert op.diff("scholar", None, current, {"publications": [title + " — V, 2026."]}, D) == []


def test_check_seeds_master_links_without_a_prior_status(store):
    directory = paths.profile_dir("Jane Doe")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "profile.yaml").write_text(yaml.safe_dump(
        {"meta": {"name": "Jane Doe", "language": "en"}, "contact": {"links": {"github": "github.com/janedoe"}}}),
        encoding="utf-8")
    get = fake({f"{API}/users/janedoe/repos?per_page=100&type=owner": (200, [])})
    result = op.check("Jane Doe", store, D, force=False, get=get)
    assert get.calls and result["checked"]["github"] == "ok"
    assert op.load_record(paths.online_presence("Jane Doe"))["sources"]["github"]["status"] == "given"


def test_writeback_skips_a_link_whose_last_check_was_404(store):
    op.record_answer("Jane Doe", "github", "given", "jandoe", "typo")
    op.record_answer("Jane Doe", "website", "given", "https://jane.example", "site")
    record = op.load_record(paths.online_presence("Jane Doe"))
    record["checks"]["github"] = {"date": D.isoformat(), "outcome": "failed", "code": 404}
    record["findings"].append({"id": "scholar:x", "source": "scholar", "kind": "new_paper",
                               "status": "confirmed", "words": "yes",
                               "paper": {"title": "X", "authors": "J Doe", "venue": "V", "year": 2026}})
    op.save_record(paths.online_presence("Jane Doe"), record)
    master = paths.profile_dir("Jane Doe") / "profile.yaml"
    master.write_text(yaml.safe_dump({"meta": {"name": "Jane Doe", "language": "en"}}), encoding="utf-8")
    op.writeback("Jane Doe", "en", None)
    links = journal.load_yaml(master)["contact"]["links"]
    assert "github" not in links and links["website"] == "https://jane.example"


def test_non_list_projects_is_left_alone_and_the_finding_stays_unwritten(store):
    master = paths.profile_dir("Jane Doe") / "profile.yaml"
    master.parent.mkdir(parents=True, exist_ok=True)
    master.write_text(yaml.safe_dump({"meta": {"name": "Jane Doe", "language": "en"},
                                      "projects": "see my website"}), encoding="utf-8")
    record = op.load_record(paths.online_presence("Jane Doe"))
    record["findings"].append({"id": "github:acme/tool", "source": "github", "kind": "new_repo",
                               "status": "confirmed", "words": "yes",
                               "repo": {"full_name": "acme/tool", "html_url": "https://github.com/acme/tool",
                                        "description": "d", "role": "owner"}})
    op.save_record(paths.online_presence("Jane Doe"), record)
    assert op.writeback("Jane Doe", "en", None) == []
    assert journal.load_yaml(master)["projects"] == "see my website"
    finding = op.load_record(paths.online_presence("Jane Doe"))["findings"][0]
    assert "written_to" not in finding and "projects" in finding["skipped_reason"]


def test_reference_tells_the_user_the_master_is_reformatted():
    text = (pathlib.Path(__file__).resolve().parents[2] / "references" / "online-presence.md").read_text()
    assert "reformatted" in text and "backup" in text
    assert "sortby=pubdate" in text and "hl=en" in text


def test_ingest_cli_prints_the_partial_warning(store, tmp_path, capsys):
    text = SCHOLAR_LIVE_SHAPE.replace("Articles 1–5", "Articles 1–7")
    assert op.main(["ingest", "--name", "Jane Doe", "--source", "scholar",
                    "--capture", str(capture(tmp_path, text))]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["papers"] == 5 and "7" in out["warning"]


def test_check_does_not_fetch_a_damaged_github_value(store):
    path = paths.online_presence("Jane Doe")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("sources:\n  github: {status: given, value: 'gitlab.com/jane', words: x}\n",
                    encoding="utf-8")
    get = fake({})
    result = op.check("Jane Doe", store, D, force=True, get=get)
    assert get.calls == [] and result["checked"]["github"] == "bad_value"


# ---- final-review fixes --------------------------------------------------

def table(*rows):
    return "\n".join(["Title", "Cited by", "Year", *rows])


def titles(tmp_path, text):
    result = op.ingest_scholar(capture(tmp_path, text))
    return [p["title"] for p in result["papers"]], result


def test_numeric_or_year_like_title_starts_a_row(tmp_path):
    found, _ = titles(tmp_path, table("2048", "A B, C D", "Nature", "1,234", "2020",
                                      "2019", "X Y", "Venue", "2019", "Articles 1–2"))
    assert found == ["2048", "2019"]


def test_misaligned_run_is_dropped_and_warned_not_turned_into_a_paper(tmp_path):
    found, result = titles(tmp_path, table("T1", "A, B", "V1", "T2", "A, B", "2020",
                                           "T3", "C, D", "V3", "2019", "Articles 1–3"))
    assert found == ["T3"] and "V1" not in found
    assert "warning" in result


def test_footer_words_as_titles_do_not_end_the_table(tmp_path):
    found, _ = titles(tmp_path, table("T1", "A, B", "V1", "2020", "Help", "A, B", "V2", "2019",
                                      "Articles 1–2", "Show more", "Privacy", "Terms", "Help"))
    assert found == ["T1", "Help"]


def test_empty_profile_has_no_warning(tmp_path):
    result = op.ingest_scholar(capture(tmp_path, table("There are no articles in this profile.")))
    assert result["outcome"] == "ok" and result["papers"] == [] and "warning" not in result


def test_check_carries_the_snapshot_warning(store, tmp_path):
    text = SCHOLAR_LIVE_SHAPE.replace("Articles 1–5", "Articles 1–7")
    assert op.main(["ingest", "--name", "Jane Doe", "--source", "scholar",
                    "--capture", str(capture(tmp_path, text))]) == 0
    result = op.check("Jane Doe", store, D, force=False, get=fake({}))
    assert "7" in result["warnings"]["scholar"]


def test_enterprise_username_with_underscore_is_accepted(store):
    op.record_answer("Jane Doe", "github", "given", "jane_acme", "mine")
    assert op.load_record(paths.online_presence("Jane Doe"))["sources"]["github"]["value"] == "jane_acme"


def test_bad_master_github_link_is_flagged_by_status(store):
    directory = paths.profile_dir("Jane Doe")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "profile.yaml").write_text(yaml.safe_dump(
        {"meta": {"name": "Jane Doe", "language": "en"},
         "contact": {"links": {"github": "github.com/jane/some-repo"}}}), encoding="utf-8")
    assert op.status("Jane Doe", D)["malformed"] == ["github"]


def test_bad_value_reason_is_not_a_source_key(store):
    path = paths.online_presence("Jane Doe")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("sources:\n  github: {status: given, value: 'gitlab.com/jane', words: x}\n",
                    encoding="utf-8")
    result = op.check("Jane Doe", store, D, force=True, get=fake({}))
    assert set(result["checked"]) <= set(op.SOURCES) and "github" in result["warnings"]


def test_writeback_cli_lists_skipped_findings(store, capsys):
    master = paths.profile_dir("Jane Doe") / "profile.yaml"
    master.parent.mkdir(parents=True, exist_ok=True)
    master.write_text(yaml.safe_dump({"meta": {"name": "Jane Doe", "language": "en"},
                                      "publications": "see website"}), encoding="utf-8")
    record = op.load_record(paths.online_presence("Jane Doe"))
    record["findings"].append({"id": "scholar:x", "source": "scholar", "kind": "new_paper",
                               "status": "confirmed", "words": "yes",
                               "paper": {"title": "X", "authors": "J", "venue": "V", "year": 2026}})
    op.save_record(paths.online_presence("Jane Doe"), record)
    assert op.main(["writeback", "--name", "Jane Doe", "--language", "en"]) == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["written"] == [] and "publications" in out["skipped"]["scholar:x"]
