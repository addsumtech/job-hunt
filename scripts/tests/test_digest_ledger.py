"""Weekly digest, task 3: the ledger of roles already sent."""
import datetime
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import digest_ledger as ledger
import paths

D = datetime.date(2026, 11, 9)
ROW = {"company": "Acme B.V.", "title": "Sr. ML Engineer", "location": "Amsterdam", "url": "https://a/1"}


def sent(*rows):
    return ledger.record_sent({"roles": []}, list(rows), D)


def test_same_url_is_seen():
    assert ledger.is_seen(dict(ROW, company="Other", title="Other"), sent(ROW))


def test_repost_new_url_is_seen():
    assert ledger.is_seen(dict(ROW, url="https://b/9", company="ACME"), sent(ROW))


def test_other_city_is_new():
    assert not ledger.is_seen(dict(ROW, url="https://b/9", location="Utrecht"), sent(ROW))


def test_remote_matches_any_city():
    remote = dict(ROW, location="Remote (Netherlands)", url="https://r")
    assert ledger.is_seen(dict(ROW, location="Utrecht", url="https://x"), sent(remote))
    assert ledger.is_seen(dict(remote, url="https://y"), sent(ROW))


def test_multi_location_matches_any_city():
    multi = dict(ROW, location="Amsterdam; Utrecht; Eindhoven", url="https://m")
    assert ledger.is_seen(dict(ROW, location="Eindhoven", url="https://z"), sent(multi))


def test_title_variants_normalise():
    assert ledger.norm_title("Senior ML-Engineer") == ledger.norm_title("Sr. ML Engineer")
    assert ledger.norm_company("ACME b.v.") == ledger.norm_company("Acme")
    assert ledger.norm_company("Philips GmbH") == ledger.norm_company("philips")


def test_near_titles_stay_distinct():
    assert ledger.norm_title("ML Engineer II") != ledger.norm_title("ML Engineer")


def test_non_latin_titles_normalise():
    key = ledger.norm_title("机器学习工程师（上海）")
    assert key and key == ledger.norm_title("机器学习工程师 (上海)")


def test_company_that_is_only_a_suffix_is_not_emptied():
    assert ledger.norm_company("B.V.")


def test_empty_identity_is_matched_by_url_only():
    bare = {"company": "", "title": "", "location": "", "url": "https://u"}
    assert not ledger.is_seen(dict(bare, url="https://other"), sent(bare))
    assert ledger.is_seen(bare, sent(bare))


def test_filter_new_keeps_order_and_drops_duplicates_within_the_batch():
    other = dict(ROW, title="Data Scientist", url="https://c")
    out = ledger.filter_new([ROW, dict(ROW, url="https://dup"), other], {"roles": []})
    assert out == [ROW, other]


def test_record_sent_merges_urls_and_locations():
    led = sent(ROW)
    led = ledger.record_sent(led, [dict(ROW, url="https://b/9")], D)
    assert len(led["roles"]) == 1 and led["roles"][0]["urls"] == ["https://a/1", "https://b/9"]


def test_prune_drops_entries_older_than_180_days():
    led = ledger.record_sent({"roles": []}, [ROW], D - datetime.timedelta(days=181))
    led = ledger.record_sent(led, [dict(ROW, title="Data Scientist", url="https://c")], D)
    assert [r["title"] for r in ledger.prune(led, D)["roles"]] == ["data scientist"]  # stored normalised


def test_load_and_save_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path)
    assert ledger.load_ledger("Jane Doe") == {"roles": []}
    ledger.save_ledger("Jane Doe", sent(ROW))
    assert ledger.is_seen(ROW, ledger.load_ledger("Jane Doe"))
