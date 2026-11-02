"""Weekly digest, task 5: composing the email and recording the send."""
import datetime
import json
import pathlib
import sys

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import digest
import digest_compose
import digest_ledger
import discover_fixtures as fx
import paths

READ = "51job-173199597"


@pytest.fixture
def ws(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path / "store")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    digest.save_settings("Jane Doe", {
        "enabled": True, "recipient": "jane@example.org", "language": "zh",
        "schedule": {"weekday": 0, "hour": 9}, "last_sent": "2026-11-02T09:00",
        "pending_questions": [{"id": "A", "avoid": "要德语", "role": "X — Y", "words": "w",
                               "date": "2026-11-02", "asked": 0},
                              {"id": "B", "avoid": "old", "role": None, "words": "w",
                               "date": "2026-10-01", "asked": 2}]})
    root = paths.profile_dir("Jane Doe") / "searches"
    root.mkdir(parents=True)
    workspace = fx.build_workspace(root)
    write(workspace, "digest-picks.yaml",
          {"roles": [{"id": READ, "why": "Python/C++ 与你的项目一致", "gaps": "要求 3 年经验"}], "unread": 1})
    write(workspace, "digest-sources.yaml",
          {"checked": ["51job"], "unchecked": [{"site": "indeed", "reason": "出现人机验证"}]})
    return workspace


def write(workspace, name, data):
    (workspace / name).write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def compose(ws):
    assert digest.main(["compose", "--name", "Jane Doe", "--workspace", str(ws), "--today", "2026-11-09"]) == 0
    return json.loads((ws / "digest-email.json").read_text(encoding="utf-8"))


def test_body_has_link_why_gaps_and_reply_instructions(ws):
    mail = compose(ws)
    body = mail["body"]
    assert mail["to"] == ["jane@example.org"]
    assert mail["subject"].startswith("[job-hunt weekly] 2026-11-09")
    for text in ("高级AI算法工程师(J10032)", "https://jobs.51job.com/haining/173199597.html",
                 "Python/C++ 与你的项目一致", "要求 3 年经验", "indeed", "出现人机验证",
                 "取消推送", "暂停", "第 N 个", "1 个"):
        assert text in body, text
    assert "不在自动推送范围" not in body          # revision 2026-11-02: the user runs it, LinkedIn included
    assert "要德语" in body and "是 A" in body
    assert "old" not in body                       # asked twice already
    assert (ws / "digest-email.txt").read_text(encoding="utf-8") == body


def test_empty_week_names_checked_sources(ws):
    write(ws, "digest-picks.yaml", {"roles": [], "unread": 0})
    body = compose(ws)["body"]
    assert "本周没有新的合适岗位" in body and "51job" in body


def test_english_template(ws):
    s = digest.load_settings("Jane Doe")
    s["language"] = "en"
    digest.save_settings("Jane Doe", s)
    body = compose(ws)["body"]
    assert "Why it fits" in body and "unsubscribe" in body


def test_sent_refuses_when_gate_fails(ws, capsys):
    compose(ws)
    write(ws, "digest-picks.yaml", {"roles": [{"id": "51job-173198362", "why": "w", "gaps": "g"}], "unread": 0})
    assert digest.main(["presend", "--name", "Jane Doe", "--workspace", str(ws)]) == 1
    assert digest.load_settings("Jane Doe")["last_sent"] == "2026-11-02T09:00"
    assert digest_ledger.load_ledger("Jane Doe") == {"roles": []}


def test_sent_records_ledger_threads_and_last_sent(ws):
    compose(ws)
    assert digest.main(["presend", "--name", "Jane Doe", "--workspace", str(ws)]) == 0
    assert digest.main(["sent", "--name", "Jane Doe", "--workspace", str(ws),
                        "--message-id", "m1", "--thread-id", "t1"]) == 0
    s = digest.load_settings("Jane Doe")
    assert s["last_sent"] != "2026-11-02T09:00" and s["threads"] == ["t1"]
    assert s["sent_digests"]["t1"] == ["高级AI算法工程师(J10032) — 拓荆键科（海宁）半导体设备"]
    assert [q["asked"] for q in s["pending_questions"] if q["id"] == "A"] == [1]
    row = next(r for r in fx.SHORTLIST["rows"] if r["id"] == READ)
    assert digest_ledger.is_seen(row, digest_ledger.load_ledger("Jane Doe"))
    assert '"action": "digest_sent"' in (ws / "journal.jsonl").read_text(encoding="utf-8")


def test_deliver_file_writes_html_and_counts_as_sent(ws, tmp_path):
    compose(ws)
    assert digest.main(["deliver-file", "--name", "Jane Doe", "--workspace", str(ws)]) == 0
    files = list((tmp_path / "home" / "Downloads" / "job-digest").glob("*.html"))
    assert len(files) == 1 and "高级AI算法工程师" in files[0].read_text(encoding="utf-8")
    assert digest.load_settings("Jane Doe")["last_sent"] != "2026-11-02T09:00"


def test_compose_refuses_a_workspace_outside_the_profile(ws, tmp_path):
    other = tmp_path / "elsewhere"
    other.mkdir()
    assert digest.main(["compose", "--name", "Jane Doe", "--workspace", str(other)]) == 2


def test_role_label():
    assert digest_compose.role_label({"title": "T", "company": "C"}) == "T — C"


def test_filter_prints_only_unsent_rows(ws, capsys):
    assert digest.main(["filter", "--name", "Jane Doe", "--workspace", str(ws)]) == 0
    assert json.loads(capsys.readouterr().out) == {"new": [READ, "51job-173198362"]}
    row = next(r for r in fx.SHORTLIST["rows"] if r["id"] == READ)
    digest_ledger.save_ledger("Jane Doe", digest_ledger.record_sent({"roles": []}, [row],
                                                                    datetime.date(2026, 11, 2)))
    assert digest.main(["filter", "--name", "Jane Doe", "--workspace", str(ws)]) == 0
    assert json.loads(capsys.readouterr().out) == {"new": ["51job-173198362"]}


def test_empty_week_with_unread_roles_does_not_say_more(ws):
    s = digest.load_settings("Jane Doe")
    s["language"] = "en"
    digest.save_settings("Jane Doe", s)
    write(ws, "digest-picks.yaml", {"roles": [], "unread": 1})
    body = compose(ws)["body"]
    assert "1 new role could not be read in full" in body and "more" not in body
