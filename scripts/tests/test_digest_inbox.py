"""Weekly digest, task 4: cancel, pause and feedback by reply."""
import datetime
import json
import pathlib
import sys
import types

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import digest
import digest_inbox as inbox
import journal
import paths

D = datetime.date(2026, 11, 9)
ME = "jane@example.org"


@pytest.fixture
def tmp_store(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path / "store")
    digest.save_settings("Jane Doe", {
        "enabled": True, "schedule": {"weekday": 0, "hour": 9}, "recipient": ME,
        "threads": ["t1"], "sent_digests": {"t1": ["ML Engineer — Acme", "Data Scientist — Beta",
                                                   "Research Engineer — Gamma"]}})
    prefs = paths.search_prefs("Jane Doe")
    prefs.write_text(yaml.safe_dump({"updated": "2026-11-01", "avoid": ["sales"]}), encoding="utf-8")
    return tmp_path / "store"


def msg(body, sender=f"Jane <{ME}>", thread="t1", mid="m1"):
    return {"id": mid, "thread_id": thread, "from": sender, "date": "2026-11-08", "body": body}


def noop_run(*a, **k):
    return types.SimpleNamespace(returncode=0, stdout="", stderr="")


def test_quoted_instructions_do_not_cancel():
    body = "谢谢\n\n在 2026年11月9日 写道：\n> 回复「取消推送」即可停止"
    assert inbox.classify(body)["cancel"] is False
    body = "Thanks!\n\nOn Mon, 9 Nov 2026 at 09:00, Jane <j@x> wrote:\n> reply unsubscribe to stop"
    assert inbox.classify(body)["cancel"] is False
    assert inbox.classify("ok\n-----Original Message-----\nunsubscribe")["cancel"] is False


def test_own_cancel_wins_over_everything():
    c = inbox.classify("第 2 个不错，但还是取消推送吧")
    assert c["cancel"] is True


@pytest.mark.parametrize("text", ["取消推送", "退订", "Unsubscribe please", "please stop sending these", "afmelden"])
def test_cancel_words(text):
    assert inbox.classify(text)["cancel"] is True


@pytest.mark.parametrize("text,weeks", [("暂停 3 周", 3), ("pause 2 weeks", 2), ("pauzeer 1 week", 1),
                                        ("先暂停", 4), ("暂停三周", 3), ("暂停两周", 2)])
def test_pause_weeks(text, weeks):
    assert inbox.classify(text)["pause_weeks"] == weeks


def test_feedback_by_index():
    c = inbox.classify("第 3 个不相关，因为要德语")
    assert c["feedback"] == [{"index": 3, "text": "第 3 个不相关，因为要德语", "reason": "要德语"}]
    c = inbox.classify("#2 not relevant because it needs a PhD")
    assert c["feedback"][0]["index"] == 2 and c["feedback"][0]["reason"] == "it needs a PhD"


@pytest.mark.parametrize("text,expected", [("是", ["*"]), ("是的", ["*"]), ("yes", ["*"]),
                                           ("是 A", ["A"]), ("Yes B.", ["B"]), ("是不是要改", [])])
def test_yes_names_a_question(text, expected):
    assert inbox.classify(text)["yes"] == expected


def test_wrong_sender_or_thread_is_ignored(tmp_store):
    out = inbox.apply_messages("Jane Doe", [msg("取消推送", sender="evil@x.org"),
                                            msg("取消推送", thread="other", mid="m2")], D, run=noop_run)
    assert out["action"] == "continue" and len(out["ignored"]) == 2
    assert not digest.load_settings("Jane Doe")["cancelled"]


def test_processed_message_is_not_applied_twice(tmp_store):
    inbox.apply_messages("Jane Doe", [msg("暂停 1 周")], D, run=noop_run)
    digest.save_settings("Jane Doe", dict(digest.load_settings("Jane Doe"), paused_until=None))
    out = inbox.apply_messages("Jane Doe", [msg("暂停 1 周")], D, run=noop_run)
    assert out["action"] == "continue" and digest.load_settings("Jane Doe")["paused_until"] is None


def test_cancel_uninstalls_and_reports_cancel(tmp_store):
    calls = []
    out = inbox.apply_messages("Jane Doe", [msg("取消推送")], D,
                               run=lambda cmd, **k: calls.append(cmd) or noop_run())
    assert out["action"] == "cancel"
    assert digest.load_settings("Jane Doe")["cancelled"]["words"] == "取消推送"
    assert calls  # the scheduler entry was removed


def test_pause_reports_pause(tmp_store):
    assert inbox.apply_messages("Jane Doe", [msg("暂停 2 周")], D, run=noop_run)["action"] == "pause"
    assert digest.load_settings("Jane Doe")["paused_until"] == "2026-11-23"


def test_feedback_becomes_a_pending_question_not_a_preference(tmp_store):
    before = paths.search_prefs("Jane Doe").read_bytes()
    inbox.apply_messages("Jane Doe", [msg("第 3 个不相关，因为要德语")], D, run=noop_run)
    q = digest.load_settings("Jane Doe")["pending_questions"]
    assert q == [{"id": "A", "avoid": "要德语", "role": "Research Engineer — Gamma",
                  "words": "第 3 个不相关，因为要德语", "date": "2026-11-09", "asked": 0}]
    assert paths.search_prefs("Jane Doe").read_bytes() == before


def test_yes_writes_avoid_with_backup(tmp_store):
    inbox.apply_messages("Jane Doe", [msg("第 3 个不相关，因为要德语")], D, run=noop_run)
    inbox.apply_messages("Jane Doe", [msg("是", mid="m2")], D, run=noop_run)
    prefs = journal.load_yaml(paths.search_prefs("Jane Doe"))
    assert prefs["avoid"] == ["sales", "要德语"] and prefs["updated"] == "2026-11-09"
    assert (paths.search_prefs("Jane Doe").parent / "search-preferences.yaml.bak-2026-11-09").is_file()
    assert digest.load_settings("Jane Doe")["pending_questions"] == []


def test_plain_yes_with_two_questions_changes_nothing(tmp_store):
    inbox.apply_messages("Jane Doe", [msg("第 1 个不相关，因为要德语"),
                                      msg("第 2 个不相关，因为是销售", mid="m2")], D, run=noop_run)
    out = inbox.apply_messages("Jane Doe", [msg("yes", mid="m3")], D, run=noop_run)
    assert journal.load_yaml(paths.search_prefs("Jane Doe"))["avoid"] == ["sales"]
    assert any("which" in i["reason"] for i in out["ignored"])
    inbox.apply_messages("Jane Doe", [msg("是 B", mid="m4")], D, run=noop_run)
    assert journal.load_yaml(paths.search_prefs("Jane Doe"))["avoid"] == ["sales", "是销售"]


def test_question_asked_twice_is_dropped(tmp_store):
    inbox.apply_messages("Jane Doe", [msg("第 3 个不相关，因为要德语")], D, run=noop_run)
    s = digest.load_settings("Jane Doe")
    s["pending_questions"][0]["asked"] = 2
    digest.save_settings("Jane Doe", s)
    inbox.apply_messages("Jane Doe", [], D, run=noop_run)
    assert digest.load_settings("Jane Doe")["pending_questions"] == []


def test_cli_reads_messages_and_prints_the_action(tmp_store, tmp_path, capsys):
    path = tmp_path / "m.json"
    path.write_text(json.dumps([msg("暂停 1 周")]), encoding="utf-8")
    assert digest.main(["inbox", "--name", "Jane Doe", "--messages", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["action"] == "pause"


def test_unreadable_inbox_stops_and_notifies(tmp_store, capsys, monkeypatch):
    notes = []
    monkeypatch.setattr(digest, "notify", lambda *a: notes.append(a))
    assert digest.main(["inbox", "--name", "Jane Doe", "--unreadable", "gmail tool missing"]) == 0
    assert json.loads(capsys.readouterr().out)["action"] == "stop"
    assert notes and "gmail tool missing" in digest.log_path("Jane Doe").read_text()


@pytest.mark.parametrize("header", [
    "Jane Doe <jane@example.org> 于2026年11月9日周一 09:00写道：",
    "Jane Doe <jane@example.org> wrote:",
    "Op ma 9 nov 2026 om 09:00 schreef Jane <j@x>:",
])
def test_other_quote_headers_are_cut(header):
    assert inbox.classify(f"谢谢\n{header}\n回复「取消推送」即可停止")["cancel"] is False


def test_our_own_instruction_line_never_cancels_even_unquoted():
    import digest_compose
    for lang in ("zh", "en"):
        line = digest_compose.TEXT[lang]["reply"]
        assert inbox.classify(f"thanks\n{line}")["cancel"] is False
        assert inbox.classify(f"thanks\n{line}")["pause_weeks"] is None


def test_a_users_own_wrote_line_is_not_a_quote_header():
    assert inbox.classify("As I wrote: please unsubscribe me")["cancel"] is True
    assert inbox.classify("我之前写道：取消推送")["cancel"] is True
    assert inbox.classify("As I already wrote:\nplease unsubscribe me")["cancel"] is True
    assert inbox.classify("我之前写道：\n取消推送")["cancel"] is True
