"""Discover's provenance anchors, extended to the artifact a human reads.

Every anchor commit 55e4f84 added runs over `shortlist.yaml`. `shortlist.md` —
hand-authored, no renderer, the only file the user reads and acts on — was
checked for four narrow things and never reconciled row by row. An audit on
2026-08-23 found three consequences:

  1. a wholly invented posting present only in the .md passed both discover gates
  2. `company`, `location` and `salary` were never anchored at all, so a row
     could name a different employer and a fabricated pay band for a posting
     whose capture contradicts both
  3. the round caps were validated as DECLARED numbers only — thirteen journaled
     pages against `max_pages_per_site: 2` exited 0

The sharpest of the three is not in the code at all: modes/discover.md told the
round to "delete the row" on a provenance finding and never said to delete it
from the .md too, so the documented remediation moved a fabricated row out of the
checked file and left it in the read one.
"""
import contextlib
import copy
import io
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_shortlist as cs
import discover_fixtures as fx

GHOST_URL = "https://www.linkedin.com/jobs/view/8888888888/"


def run(workspace):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cs.main(["--workspace", str(workspace)])
    lines = [line for line in buf.getvalue().strip().splitlines() if line]
    return rc, sorted({line.split(":", 1)[0] for line in lines})


# ── 1. shortlist.md is reconciled against shortlist.yaml ──────────────────────

def test_the_baseline_english_workspace_is_clean(tmp_path):
    """The quiet twin, pinned as hard as the firing ones: these three checks run
    on every discover round, and one that fires on an honest round teaches the
    reader to skip the line that matters."""
    assert run(fx.build_english_workspace(tmp_path)) == (0, [])


def test_a_posting_rendered_only_in_the_md_is_reported(tmp_path):
    ws = fx.build_english_workspace(tmp_path)
    md = (ws / "shortlist.md").read_text(encoding="utf-8")
    (ws / "shortlist.md").write_text(
        md + f"\n### 4. Ghost Role — Nonexistent BV\n{GHOST_URL}\n", encoding="utf-8")
    rc, codes = run(ws)
    assert rc == 1 and "MD_ROW_NOT_IN_SHORTLIST" in codes


def test_deleting_a_flagged_row_from_the_yaml_alone_no_longer_goes_green(tmp_path):
    """The load-bearing case, and the reason the mode file changed with the code.

    Pre-fix this exact sequence ended rc=0 with the ghost row still rendered in
    the document the user reads: the gate's own remediation turned a provenance
    failure into a clean round.
    """
    ws = fx.build_english_workspace(tmp_path)
    shortlist = fx.load_shortlist(ws)
    ghost = dict(shortlist["rows"][0])
    ghost.update({"id": "linkedin-8888888888", "source_id": "8888888888",
                  "company": "Nonexistent BV", "title": "Ghost Role",
                  "url": GHOST_URL, "raw_text": "Ghost Role at Nonexistent BV"})
    shortlist["rows"].append(ghost)
    fx.save_shortlist(ws, shortlist)
    md = (ws / "shortlist.md").read_text(encoding="utf-8")
    (ws / "shortlist.md").write_text(
        md + f"\n### 4. Ghost Role — Nonexistent BV\n{GHOST_URL}\n", encoding="utf-8")

    rc, codes = run(ws)
    assert rc == 1 and "SOURCE_ID_NOT_IN_RAW" in codes, "step 1: the row is flagged"

    # Now do exactly what the finding table said: delete the row.
    shortlist = fx.load_shortlist(ws)
    shortlist["rows"] = [r for r in shortlist["rows"]
                         if r.get("source_id") != "8888888888"]
    fx.save_shortlist(ws, shortlist)

    rc, codes = run(ws)
    assert rc == 1, "deleting from the yaml alone must not produce a clean round"
    assert "MD_ROW_NOT_IN_SHORTLIST" in codes


def test_the_mode_file_says_to_delete_from_both_files(tmp_path):
    """The check is only half the fix. If the instruction still says "delete the
    row", the next run does the same thing and is merely told off for it."""
    text = (pathlib.Path(__file__).resolve().parents[2]
            / "modes" / "discover.md").read_text(encoding="utf-8")
    assert "Deleting a row means deleting it from both files." in text
    assert "MD_ROW_NOT_IN_SHORTLIST" in text


def test_a_url_the_shortlist_does_carry_is_not_reported(tmp_path):
    """No cry-wolf: the md legitimately renders every row's URL."""
    ws = fx.build_english_workspace(tmp_path)
    rows = fx.load_shortlist(ws)["rows"]
    urls = [str(r.get("url")) for r in rows if r.get("url")]
    assert urls, "fixture must carry URLs for this test to mean anything"
    md = (ws / "shortlist.md").read_text(encoding="utf-8")
    (ws / "shortlist.md").write_text(md + "\n" + "\n".join(urls) + "\n",
                                     encoding="utf-8")
    assert run(ws) == (0, [])


# ── 2. the fields the reader acts on ──────────────────────────────────────────

def test_a_company_that_contradicts_its_own_capture_is_reported(tmp_path):
    ws = fx.build_english_workspace(tmp_path)
    shortlist = fx.load_shortlist(ws)
    shortlist["rows"][0]["company"] = "Koninklijke Philips N.V."
    fx.save_shortlist(ws, shortlist)
    rc, codes = run(ws)
    assert rc == 1 and "COMPANY_NOT_IN_RAW" in codes


def test_an_invented_salary_is_reported(tmp_path):
    """The field a job-seeker acts on hardest, and the one a model most readily
    hallucinates out of a blank — this posting's captured salary is empty."""
    ws = fx.build_english_workspace(tmp_path)
    shortlist = fx.load_shortlist(ws)
    shortlist["rows"][0]["salary"] = "EUR 95,000 - 120,000"
    fx.save_shortlist(ws, shortlist)
    rc, codes = run(ws)
    assert rc == 1 and "SALARY_NOT_IN_RAW" in codes


def test_an_empty_company_or_salary_is_not_reported(tmp_path):
    """Empty is honest — it means the capture carried nothing. Only a non-empty
    value that the capture contradicts is a finding."""
    ws = fx.build_english_workspace(tmp_path)
    shortlist = fx.load_shortlist(ws)
    shortlist["rows"][0]["salary"] = ""
    fx.save_shortlist(ws, shortlist)
    assert run(ws) == (0, [])


# ── 3. caps compared to the run, not only to the ceiling ──────────────────────

def _search_calls(ws):
    return [r for r in fx.JOURNAL_EN if r.get("command") == "search"] \
        if hasattr(fx, "JOURNAL_EN") else []


def test_a_paginated_crawl_against_a_declared_cap_is_reported(tmp_path):
    ws = fx.build_english_workspace(tmp_path)
    records = list(getattr(fx, "JOURNAL_EN", []))
    base = next(r for r in records if r.get("command") == "search")
    extra = []
    for page in range(2, 14):
        call = copy.deepcopy(base)
        call["command_line"] = f'opencli linkedin search "MRI" --page {page}'
        extra.append(call)
    fx.write_journal(ws, records + extra)
    rc, codes = run(ws)
    assert rc == 1 and "PAGES_ABOVE_CAP" in codes


def test_both_language_queries_on_one_page_are_one_page(tmp_path):
    """modes/discover.md Step 3 tells the round to query in BOTH languages, so
    counting search CALLS would report that honest round as a crawl. Distinct
    page numbers is the measure; source-policy.md says "pages", not "calls"."""
    ws = fx.build_english_workspace(tmp_path)
    records = list(getattr(fx, "JOURNAL_EN", []))
    base = next(r for r in records if r.get("command") == "search")
    second = copy.deepcopy(base)
    second["command_line"] = 'opencli linkedin search "MRI-reconstructie" --page 1'
    fx.write_journal(ws, records + [second])
    rc, codes = run(ws)
    assert "PAGES_ABOVE_CAP" not in codes


def test_a_search_with_no_page_argument_counts_as_page_one():
    calls = [{"command": "search", "exit_code": 0, "site": "linkedin",
              "command_line": 'opencli linkedin search "MRI"'},
             {"command": "search", "exit_code": 0, "site": "linkedin",
              "command_line": 'opencli linkedin search "MRI" --page 1'}]
    assert cs._pages_per_site(calls) == {"linkedin": {1}}


def test_failed_and_detail_calls_do_not_count_towards_the_page_cap():
    calls = [{"command": "search", "exit_code": 1, "site": "x",
              "command_line": "opencli x search q --page 2"},
             {"command": "detail", "exit_code": 0, "site": "x",
              "command_line": "opencli x detail 123 --page 3"}]
    assert cs._pages_per_site(calls) == {}


@pytest.mark.parametrize("declared", [None, 0, True, "two"])
def test_a_missing_or_nonsense_cap_is_left_to_the_existing_check(declared):
    """`_check_caps` already reports CAP_MISSING for these. Reporting them twice,
    from two codes, trains both away."""
    brief = {"max_pages_per_site": declared, "max_rows_per_round": declared}
    calls = [{"command": "search", "exit_code": 0, "site": "x",
              "command_line": "opencli x search q --page 9"}]
    assert cs._check_caps_against_the_run(brief, {}, [{}] * 99, calls) == []
