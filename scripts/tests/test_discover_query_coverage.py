"""A declared query that was never run is a coverage gap nobody could see.

MEASURED IN A REAL DISCOVER ROUND, 2026-09-02. `brief.target_titles` declared ten
query strings — six English, four Dutch, including "medical imaging AI" and "MRI
reconstruction". ONE was run. The first English query reached the 25-row per-site
cap on its own, so two of the user's three requested tracks were never searched
at all.

Nothing reported it. `brief.target_titles` is documented as the field that makes
a round reproducible, and `check_shortlist.py` never read it — the gap surfaced
only because the operator happened to write it into `shortfall_reason` by hand.
A round that skipped the same queries and said nothing would have been reported
as clean, and the user would have read "here are your options" over a search
that never looked where they asked.

The rule this pins is NOT "run every declared query" — a round may legitimately
stop early, hit a cap, or drop a source. It is: **if you declared it and did not
run it, say so.** That is the same bar `SHORTFALL_NO_REASON` already sets for row
counts, applied to coverage.
"""
import json
import pathlib
import subprocess
import sys

import pytest
import yaml

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"


def build(tmp_path, *, target_titles, ran, shortfall=None, rows=1):
    """A minimal discover workspace: a brief, a journal with adapter calls, a
    shortlist. Only the fields this check reads have to be real."""
    ws = tmp_path / "searches" / "2026-09-02-t"
    (ws / "raw").mkdir(parents=True)
    (ws / "brief.yaml").write_text(yaml.safe_dump(
        {"slug": "2026-09-02-t", "target_titles": target_titles,
         "target_count": rows, "max_rows_per_round": 25,
         "max_pages_per_site": 2}, allow_unicode=True), encoding="utf-8")
    lines = []
    for q in ran:
        lines.append(json.dumps({
            "action": "adapter_call", "site": "linkedin", "command": "search",
            "classification": "ok", "row_count": 5,
            "command_line": f'opencli linkedin search "{q}" --limit 25 -f json',
        }, ensure_ascii=False))
    (ws / "journal.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (ws / "shortlist.yaml").write_text(yaml.safe_dump(
        {"search_slug": "2026-09-02-t", "shortfall_reason": shortfall,
         "rows": []}, allow_unicode=True), encoding="utf-8")
    return ws


def findings(ws):
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "check_shortlist.py"), "--workspace", str(ws)],
        capture_output=True, text=True, encoding="utf-8", cwd=str(REPO))
    return proc.stdout


CODE = "QUERIES_DECLARED_NOT_RUN"


def test_a_declared_query_that_never_ran_is_reported(tmp_path):
    ws = build(tmp_path, target_titles=["machine learning engineer",
                                        "medical imaging AI", "MRI reconstruction"],
               ran=["machine learning engineer"])
    out = findings(ws)
    assert CODE in out, out
    assert "medical imaging AI" in out and "MRI reconstruction" in out, (
        "the finding must NAME the queries that were skipped — 'some queries were "
        "not run' tells the reader nothing about which tracks are unrepresented")
    assert "machine learning engineer" not in out.split(CODE)[1].split("\n")[0], (
        "the one that DID run must not be listed as skipped")


def test_running_every_declared_query_is_quiet(tmp_path):
    ws = build(tmp_path, target_titles=["a engineer", "b engineer"],
               ran=["a engineer", "b engineer"])
    assert CODE not in findings(ws)


def test_naming_the_skipped_queries_in_the_shortfall_reason_is_accepted(tmp_path):
    """Under-searching is allowed. Under-searching in silence is not."""
    ws = build(tmp_path,
               target_titles=["machine learning engineer", "medical imaging AI"],
               ran=["machine learning engineer"],
               shortfall=("One English query reached the 25-row per-site cap, so "
                          "\"medical imaging AI\" was never run this round."))
    assert CODE not in findings(ws), (
        "a skipped query named in shortfall_reason is a disclosed gap, not a "
        "silent one")


def test_a_shortfall_reason_that_names_only_some_of_them_still_reports_the_rest(tmp_path):
    ws = build(tmp_path,
               target_titles=["q one", "q two", "q three"], ran=["q one"],
               shortfall='"q two" was skipped after the cap was reached.')
    out = findings(ws)
    assert CODE in out
    assert "q three" in out
    assert "q two" not in out.split(CODE)[1].split("\n")[0]


@pytest.mark.parametrize("declared,ran", [
    ("Machine Learning Engineer", "machine learning engineer"),   # case
    ("machine  learning   engineer", "machine learning engineer"),  # whitespace
    ("machine learning engineer", "Machine Learning Engineer"),   # reversed case
])
def test_matching_is_not_defeated_by_case_or_spacing(tmp_path, declared, ran):
    """The command line is typed by a model, the brief by the same model at a
    different moment. Requiring byte equality would fire on rounds that did run
    the query, which is a false alarm — and a gate that cries wolf gets ignored."""
    ws = build(tmp_path, target_titles=[declared], ran=[ran])
    assert CODE not in findings(ws), f"{declared!r} vs {ran!r} should match"


def test_a_brief_with_no_target_titles_is_not_a_finding(tmp_path):
    """Absent is not the same as skipped. A round that declared nothing has
    nothing to be inconsistent with."""
    ws = build(tmp_path, target_titles=[], ran=["anything"])
    assert CODE not in findings(ws)


def test_a_round_with_no_adapter_calls_does_not_flood(tmp_path):
    """Every query is unrun here, but the round already fails for having no
    receipts at all; repeating it once per declared title buries that."""
    ws = build(tmp_path, target_titles=["a", "b", "c"], ran=[])
    out = findings(ws)
    assert out.count(CODE) <= 1, (
        "one finding listing the skipped queries, not one per query:\n" + out)


def test_the_out_of_band_message_names_the_demotion_cause():
    """The remedy text said only "if the user named this row". The other cause —
    the fetch is what demoted the row — is the normal, desirable one, and a
    reader told the wrong cause writes the wrong exception reason or, worse,
    deletes a fetch that was correct."""
    src = (SCRIPTS / "check_shortlist.py").read_text(encoding="utf-8")
    block = _flat(src.split("DETAIL_FETCH_OUT_OF_BAND")[1][:1200]).lower()
    assert "demot" in block, "the message never mentions a fetch-caused demotion"
    assert "named this row" in block, "and it must keep the other cause too"


def _flat(text):
    """Markdown prose wraps, so a phrase spanning a line break is not a
    substring of the file. Collapsing whitespace first is what stops these
    assertions failing on a reflow rather than on a missing rule — measured:
    "second round" was present and matched nothing because it was written
    "second\nround"."""
    return " ".join(str(text).split())


def test_discover_tells_the_reader_to_split_the_row_budget():
    """The both-languages rule and the per-round row cap collide, and following
    Step 3 at full --limit makes the second language impossible. Nothing said so
    until a measured round lost two of three tracks to it."""
    doc = _flat((REPO / "modes" / "discover.md").read_text(encoding="utf-8"))
    assert "Split the row budget" in doc, "no budget guidance in discover.md"
    block = doc.split("Split the row budget")[1][:1200]
    assert "R // N" in block or "per query" in block, (
        "the guidance must give the arithmetic, not just say 'be careful'")
    assert "second round" in block, (
        "and must say what to do when one round's cap genuinely is not enough — "
        "otherwise the reader raises the cap, which is the one thing forbidden")


def test_discover_preserves_explicit_counts_without_silently_capping_broad_searches():
    doc = _flat((REPO / "modes" / "discover.md").read_text(encoding="utf-8"))
    assert "Use an explicit requested count" in doc
    assert "state a practical working target and continue" in doc
    assert "not silently limit the search to three or five" in doc
    assert "not a stop condition by itself" in doc.replace("**", "")
    assert "Preserve source caps and refusal locks" in doc


def test_discover_says_to_run_the_most_specific_query_first():
    """Splitting the budget is not enough on its own: a broad query fills
    whatever budget it gets, so running it first strands the specific ones
    regardless of the arithmetic.

    MEASURED: a round divided nothing, ran `machine learning engineer` first at
    the full cap, and never reached `MRI reconstruction` at position six — the
    candidate's own specialism, and the one query where their PhD is a hard
    qualification rather than a background note. The first fix added the
    arithmetic and NOT this, and the omission was reported as fixed.
    """
    doc = _flat((REPO / "modes" / "discover.md").read_text(encoding="utf-8"))
    assert "most specific first" in doc, (
        "discover.md gives the budget arithmetic but never says what order to "
        "run the queries in")
    block = doc.split("most specific first")[1][:900]
    assert "broadest last" in doc.split("most specific first")[0][-80:] or \
           "broadest last" in block, "the rule must name both ends"
    assert "run order" in block, (
        "and must say that brief.target_titles is written in that order — "
        "otherwise the plan lives only in the model's head")
