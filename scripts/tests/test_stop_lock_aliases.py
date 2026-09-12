# -*- coding: utf-8 -*-
"""A site refusal must survive the site being called something else.

`references/browser-fallback.md` promised "renaming the source does not reset a
refusal". Measured 2026-09-08, the code normalised case and whitespace and
nothing more, so all of these read the site again after it had refused:

    refusal on `51job`  →  `51job.com`      not stopped
    refusal on `51job`  →  `www.51job`      not stopped
    refusal on `51job`  →  `qiancheng`      not stopped

The adversarial reading is not the interesting one. An agent that writes `51job`
on one call and `51job.com` on the next defeats the lock **without intending
to**, and the round then keeps reading a site that has already refused it —
which is the behaviour `references/source-policy.md` exists to prevent.

Three keys now: the declared name, the host actually read, and the hosts that
name has been seen using earlier in the same journal. The last one is what
joins `boss` to `zhipin.com` without anyone maintaining a table of which
adapter serves which domain — a table that would have to be right about every
market before it could be trusted at all.

What this still cannot do is join a rename that shares no text and no observed
host. That limit is stated in the reference rather than papered over.
"""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import record_browser_capture as rb  # noqa: E402


def adapter(site, classification="ok"):
    return {"action": "adapter_call", "site": site, "classification": classification}


def browser(site, url=None, classification="ok"):
    record = {"action": "browser_call", "site": site, "classification": classification}
    if url:
        record["url"] = url
    return record


STOPPED = [
    ("the same name again", [adapter("51job", "platform_limit"), browser("51job")]),
    ("a different case", [adapter("51job", "platform_limit"), browser("51JOB")]),
    ("the name with its TLD", [adapter("51job", "platform_limit"), browser("51job.com")]),
    ("the name with www", [adapter("51job", "platform_limit"), browser("www.51job")]),
    ("an unrelated name whose URL gives it away",
     [adapter("51job", "platform_limit"), browser("qiancheng", "https://we.51job.com/x")]),
    ("a rename after the host was already associated with the old name",
     [browser("boss", "https://www.zhipin.com/a"),
      adapter("boss", "platform_limit"),
      browser("zhipin", "https://www.zhipin.com/b")]),
    ("a login wall, not only a platform limit",
     [adapter("boss", "not_logged_in"), browser("boss")]),
    ("the browser refusing first, the adapter reading second",
     [browser("indeed", "https://indeed.com/q", "platform_limit"), adapter("indeed")]),
    # Only the HOST key catches this: the second name shares no text with the
    # refused one and was never associated with the host before.
    ("a fresh name reading the host that just refused",
     [browser("boss", "https://www.zhipin.com/a", "platform_limit"),
      browser("xyzsite", "https://www.zhipin.com/b")]),
    # Only the EXACT host key catches this. Every label of `hh.ru` is two
    # characters, so the length floor in `_labels` leaves nothing to compare and
    # `_linked` cannot join the host to itself — a real site (hh.ru is a Russian
    # job board), and the reason the exact-match clause is not redundant.
    ("a short host that has no comparable label",
     [browser("hh", "https://hh.ru/search", "platform_limit"),
      browser("headhunter", "https://hh.ru/vacancy/1")]),
    # Only the HISTORY key catches this: the third record carries no URL, and
    # its name is joined to the stopped host by an earlier read.
    ("a name whose earlier read used the host that later refused",
     [browser("alpha", "https://jobs.example.com/a"),
      browser("beta", "https://jobs.example.com/b", "platform_limit"),
      adapter("alpha")]),
]

ALLOWED = [
    ("BOSS security does not stop LinkedIn on the same TLD",
     [browser("boss", "https://www.zhipin.com/web/passport/zp/security.html", "platform_limit"),
      browser("linkedin", "https://www.linkedin.com/jobs")]),
    ("shared jobs subdomain does not identify a source",
     [browser("alpha", "https://jobs.alpha.com/a", "platform_limit"),
      browser("beta", "https://jobs.beta.com/b")]),
    ("a genuinely different site",
     [adapter("51job", "platform_limit"), browser("linkedin", "https://www.linkedin.com/jobs")]),
    ("a different site in the same market",
     [adapter("boss", "not_logged_in"), browser("51job", "https://we.51job.com/x")]),
    ("a read that happened BEFORE the refusal",
     [browser("51job"), adapter("51job", "platform_limit")]),
    ("two reads of one site that never refused",
     [adapter("51job"), browser("51job", "https://we.51job.com/x")]),
    # A name that only LOOKS related. Joining it would need substring matching,
    # which was measured and removed for joining `job` to `51job.com` too. The
    # reference tells the agent to use the stable name for exactly this reason.
    ("a hyphenated near-miss with no shared label and no URL",
     [adapter("51job", "platform_limit"), browser("51-job")]),
]


@pytest.mark.parametrize("why, records", STOPPED, ids=lambda v: str(v)[:34])
def test_a_refusal_stops_the_site_however_it_is_named(why, records):
    assert rb.check_stop_order(records), f"not stopped: {why}"


@pytest.mark.parametrize("why, records", ALLOWED, ids=lambda v: str(v)[:34])
def test_a_refusal_does_not_stop_anything_else(why, records):
    """The expensive half. A lock that fires on a site which never refused stops
    honest rounds, and a gate that fires on correct behaviour gets switched off."""
    assert not rb.check_stop_order(records), f"wrongly stopped: {why}"


@pytest.mark.parametrize("a, b, linked", [
    ("51job", "we.51job.com", True),
    ("51job", "51job.com", True),
    ("51job", "www.51job", True),
    ("boss", "www.zhipin.com", False),        # needs the journal, not a guess
    ("qiancheng", "we.51job.com", False),
    ("linkedin", "www.linkedin.com", True),
    ("indeed", "we.51job.com", False),
    # Whole labels only. Substring linking was measured and removed: it joined
    # `job` to `51job.com` and `ind` to `indeed.com`, which are different sites.
    ("job", "51job.com", False),
    ("ind", "indeed.com", False),
    ("job", "jobsdb.com", False),
    ("", "we.51job.com", False),
    ("51job", "", False),
    ("zhipin.com", "linkedin.com", False),
    ("jobs.alpha.org", "jobs.beta.org", False),
    ("alpha.net", "beta.net", False),
    ("com", "linkedin.com", False),
    ("com", "example.com.cn", False),
    ("51job.com", "jobs.51job.com", True),
])
def test_two_identifiers_are_linked_only_on_shared_text(a, b, linked):
    assert rb._linked(a, b) is linked, (a, b)


def test_a_two_letter_label_links_nothing():
    """`.co`, `.jp` and the like are in every host and identify no site. Without
    the length floor a refusal on one site would stop every other one."""
    assert not rb._linked("hh", "example.co.jp")
    assert rb._labels("www.example.co.jp") == {"example"}


def test_the_reference_states_the_limit_rather_than_the_promise():
    """The doc used to promise that renaming never resets a refusal. The code
    cannot deliver that for a rename with no shared text and no shared host, and
    a reference that overstates a safety property is worse than one that names
    its edge."""
    doc = (ROOT / "references" / "browser-fallback.md").read_text(encoding="utf-8")
    assert "shares no text" in doc or "no shared text" in doc, (
        "browser-fallback.md does not state what the stop lock cannot join")


# ---- the gate contract: a malformed journal must not crash the lock ---------

WRONG = ["a string", ["a", "list"], {"a": "dict"}, None, 42, True, b"bytes", 3.14]


@pytest.mark.parametrize("field", ["action", "site", "classification", "url"])
@pytest.mark.parametrize("wrong", WRONG, ids=lambda v: type(v).__name__)
def test_a_wrongly_typed_field_does_not_crash_the_lock(field, wrong):
    """journal.jsonl is a file on disk. A person can edit it and a killed run can
    half-write it, and three gates call this function while reading it.

    An exception escaping here is exit 1 with NO receipt, which a composer reads
    as a gate that never ran — the failure `journal.as_mapping`'s own docstring
    records from 2026-09-05. Fuzzed 2026-09-08: an unhashable `classification`
    and a non-mapping row each raised, in this function and in the one it
    replaced.
    """
    record = {"action": "browser_call", "site": "51job",
              "classification": "platform_limit", "url": "https://we.51job.com/x"}
    record[field] = wrong
    rb.check_stop_order([record, dict(record, classification="ok")])


@pytest.mark.parametrize("wrong", WRONG + [{}, {"action": "browser_call"}],
                         ids=lambda v: str(type(v).__name__) + str(v)[:12])
def test_a_malformed_row_does_not_crash_the_lock(wrong):
    rb.check_stop_order([wrong])


@pytest.mark.parametrize("wrong", ["a string", 42, None, {"a": 1}],
                         ids=lambda v: type(v).__name__)
def test_a_non_list_argument_does_not_crash_the_lock(wrong):
    """A string is iterable and would be walked character by character."""
    assert rb.check_stop_order(wrong) == []


@pytest.mark.parametrize("url", [
    "", "not a url", "http://", "https://[", "ftp://x", "https://" + "a" * 3000,
    "https://user:pw@host/x", "https://例え.テスト/x",
])
def test_a_malformed_url_does_not_crash_the_lock(url):
    rb.check_stop_order([{"action": "browser_call", "site": "s", "url": url,
                          "classification": "platform_limit"}])


def test_a_refusal_still_stops_when_a_neighbouring_row_is_corrupt():
    """The guard must skip the bad row, not the whole journal. Swallowing the
    refusal because the line next to it was malformed would turn a corrupt file
    into a way through the lock."""
    records = ["garbage", {"action": "adapter_call", "site": "51job",
                           "classification": "platform_limit"},
               None, {"action": "browser_call", "site": "51job"}]
    assert rb.check_stop_order(records)
