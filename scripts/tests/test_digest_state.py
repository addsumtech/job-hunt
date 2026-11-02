"""Weekly digest, task 1: settings, the due rule, the lock, cancel and pause."""
import datetime
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import digest
import paths

NOW = datetime.datetime(2026, 11, 9, 9, 30)          # a Monday
S = {"enabled": True, "schedule": {"weekday": 0, "hour": 9}, "last_sent": "2026-11-02T09:05"}


@pytest.fixture
def tmp_store(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path / "store")
    return tmp_path / "store"


def test_due_at_the_slot_six_days_after_last_sent():
    assert digest.due(S, NOW) == (True, "due")
    assert digest.due(S, NOW.replace(hour=8))[0] is False


def test_slot_is_not_before_six_days():
    s = dict(S, last_sent="2026-11-04T10:00")   # a Wednesday; +6 days = Tue 10 Nov
    assert digest.due(s, NOW)[0] is False
    assert digest.due(s, datetime.datetime(2026, 11, 16, 9, 0))[0] is True


def test_missed_weeks_produce_one_due():
    s = dict(S, last_sent="2026-10-12T09:00")
    assert digest.due(s, NOW)[0] is True
    assert digest.due(s, NOW + datetime.timedelta(days=2))[0] is True  # still one digest owed


def test_never_sent_is_due_now():
    assert digest.due(dict(S, last_sent=None), NOW) == (True, "due")


def test_paused_and_cancelled_are_not_due():
    assert digest.due(dict(S, paused_until="2026-11-20"), NOW) == (False, "paused")
    assert digest.due(dict(S, paused_until="2026-11-09"), NOW)[0] is True
    assert digest.due(dict(S, cancelled={"date": "2026-11-05", "words": "stop"}), NOW) == (False, "cancelled")
    assert digest.due(dict(S, enabled=False), NOW) == (False, "disabled")


def test_three_attempts_today_stop_until_tomorrow():
    s = dict(S, attempts={"2026-11-09": 3})
    assert digest.due(s, NOW) == (False, "attempt_cap")
    assert digest.due(s, NOW + datetime.timedelta(days=1))[0] is True


def test_three_failed_days_wait_for_next_slot(tmp_store):
    digest.save_settings("Jane Doe", dict(S))
    for day in (9, 10, 11):
        digest.record_attempt("Jane Doe", datetime.datetime(2026, 11, day, 9, 30), ok=False)
    s = digest.load_settings("Jane Doe")
    assert s["stuck_until"] == "2026-11-16T09:00"
    assert digest.due(s, datetime.datetime(2026, 11, 12, 10, 0)) == (False, "stuck")
    assert digest.due(s, datetime.datetime(2026, 11, 16, 9, 0))[0] is True


def test_success_resets_failures(tmp_store):
    digest.save_settings("Jane Doe", dict(S))
    digest.record_attempt("Jane Doe", NOW, ok=False)
    digest.record_attempt("Jane Doe", NOW, ok=True)
    s = digest.load_settings("Jane Doe")
    assert s["failed_days"] == [] and s.get("stuck_until") is None


def test_lock_is_exclusive_and_stale_after_three_hours(tmp_store):
    assert digest.acquire_lock("Jane Doe", NOW) is True
    assert digest.acquire_lock("Jane Doe", NOW + datetime.timedelta(hours=2)) is False
    assert digest.acquire_lock("Jane Doe", NOW + datetime.timedelta(hours=3, minutes=1)) is True
    digest.release_lock("Jane Doe")
    assert digest.acquire_lock("Jane Doe", NOW) is True


def test_cancel_and_pause_record_the_words(tmp_store):
    digest.save_settings("Jane Doe", dict(S))
    digest.pause("Jane Doe", 2, "暂停 2 周", datetime.date(2026, 11, 9))
    s = digest.load_settings("Jane Doe")
    assert s["paused_until"] == "2026-11-23"
    assert s["answers"][-1]["words"] == "暂停 2 周"
    digest.cancel("Jane Doe", "取消推送", datetime.date(2026, 11, 10))
    s = digest.load_settings("Jane Doe")
    assert s["cancelled"] == {"date": "2026-11-10", "words": "取消推送"}


def test_pause_needs_positive_weeks(tmp_store):
    with pytest.raises(ValueError):
        digest.pause("Jane Doe", 0, "x", datetime.date(2026, 11, 9))


def test_absent_settings_are_disabled(tmp_store):
    s = digest.load_settings("Jane Doe")
    assert digest.due(s, NOW) == (False, "disabled")


def test_digest_workspace_never_reuses_an_existing_run(tmp_store):
    first = paths.digest_workspace("Jane Doe", "2026-11-09")
    assert first == paths.profile_dir("Jane Doe") / "searches" / "2026-11-09-weekly-digest"
    first.mkdir(parents=True)
    assert paths.digest_workspace("Jane Doe", "2026-11-09").name == "2026-11-09-weekly-digest-2"
    assert paths.digest_settings("Jane Doe").name == "digest.yaml"
    assert paths.digest_seen("Jane Doe").name == "digest-seen.yaml"
