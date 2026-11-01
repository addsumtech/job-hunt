"""Task 7: one person split across profile directories shares one record."""
import datetime
import pathlib
import sys

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import check_claims
import journal
import online_presence as op
import paths

D = datetime.date(2026, 11, 1)


@pytest.fixture
def store(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path)
    op.record_answer("Donghang Lyu", "github", "given", "dong845", "dong845")
    op.record_answer("Donghang Lyu", "scholar", "none", None, "no")
    op.record_answer("Donghang Lyu", "website", "declined", None, "no")
    paths.profile_dir("Donghang Lyu LLM").mkdir(parents=True)
    return tmp_path


def test_status_lists_other_directories_with_a_record(store):
    result = op.status("Donghang Lyu LLM", D)
    assert result["other_records"] == ["donghang-lyu"]
    assert result["to_ask"] == ["github", "scholar", "website"]


def test_linked_directory_is_not_asked_again(store):
    op.link("Donghang Lyu LLM", "Donghang Lyu", "same person")
    result = op.status("Donghang Lyu LLM", D)
    assert result["to_ask"] == [] and result["shared_with"] == "donghang-lyu"
    assert result["other_records"] == []


def test_answers_recorded_after_linking_land_in_the_shared_record(store):
    op.link("Donghang Lyu LLM", "Donghang Lyu", "same person")
    op.record_answer("Donghang Lyu LLM", "website", "given", "https://d.example", "here it is")
    shared = op.load_record(paths.online_presence("Donghang Lyu"))
    assert shared["sources"]["website"]["value"] == "https://d.example"


def test_link_to_missing_directory_exits_2(store, capsys):
    assert op.main(["link", "--name", "Donghang Lyu LLM", "--with", "Nobody", "--words", "x"]) == 2
    assert "Nobody" in capsys.readouterr().err


def test_check_claims_follows_the_link_to_the_writebacks(store, capsys):
    op.link("Donghang Lyu LLM", "Donghang Lyu", "same person")
    profile_dir = paths.profile_dir("Donghang Lyu LLM")
    ws = profile_dir / "applications" / "acme-x-2026-11-01"
    ws.mkdir(parents=True)
    master = profile_dir / "profile.yaml"
    data = {"meta": {"name": "吕东杭", "language": "zh"}, "skills": {"x": ["Python"]}}
    master.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    (ws / "tailored-profile.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    check_claims.main(["--workspace", str(ws), "--master", str(master), "--record"])
    before = journal.sha256_file(master)
    data["projects"] = [{"name": "tool"}]
    master.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    shared_path = paths.online_presence("Donghang Lyu")
    record = op.load_record(shared_path)
    record["writebacks"].append({"master": str(master), "before_sha256": before,
                                 "after_sha256": journal.sha256_file(master),
                                 "finding_ids": ["github:x/tool"], "date": "2026-11-01"})
    op.save_record(shared_path, record)
    capsys.readouterr()
    check_claims.main(["--workspace", str(ws)])
    assert "MASTER_WRITEBACK" in capsys.readouterr().out
