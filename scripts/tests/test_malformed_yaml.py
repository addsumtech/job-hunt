"""One malformed input file, across every gate that reads one.

REPRODUCED 2026-08-16, before journal.load_yaml existed. On a workspace whose
fit-assessment.yaml has an unclosed quote:

    consistency          exit=1   (a yaml parse traceback on stderr)
    count_coverage       exit=1   (a yaml parse traceback on stderr)
    journal.jsonl        2 lines  — written only by the two gates that exited 2 cleanly

exit 1 in this repo's contract means "the gate ran and found problems". So a caller
reading exit codes is told there are findings, a caller reading the journal sees
nothing, and check_apply — whose entire composition rule is reading those receipts —
sees a gate that never ran. The one state the journal exists to make visible is the
one state that produced no journal line.

Four shapes reach that same place and are all covered here: an unparseable document,
a document whose top level is a list, one whose top level is a string (`.get()` then
raises AttributeError), and a file that cannot be read at all. Each is proved against
several gates rather than one, because the defect was never in a gate — it was in the
25 call sites that each re-implemented the read.

Every test comes in both directions. The firing case is above; the quiet case is
`test_*_is_quiet_on_a_good_file`, which is what keeps these from becoming the line a
reader learns to skip.
"""
import json
import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import check_assessment
import check_evidence_refs
import check_letter
import check_pages
import check_personal_data
import check_shortlist
import check_word_limits
import consistency
import count_coverage
import journal

# The four shapes. `unreadable` raises PermissionError at the file read.
UNPARSEABLE = 'verdict: "unclosed\neffort: quick\n'
TOP_LEVEL_LIST = "- verdict: strong_apply\n- effort: quick\n"
TOP_LEVEL_STRING = "just a sentence somebody pasted instead of a document\n"
BROKEN_TEXT = {
    "unparseable": UNPARSEABLE,
    "top_level_list": TOP_LEVEL_LIST,
    "top_level_string": TOP_LEVEL_STRING,
}

GOOD_ASSESSMENT = """verdict: worth_applying
effort: evening
level_direction: lateral
requirements: []
actions: []
"""
GOOD_PROFILE = """personal:
  name: Test User
  email: test@example.com
"""

def workspace(tmp_path):
    """A workspace shaped like the real one — profile_dir_of() has to resolve."""
    ws = tmp_path / "job-profiles" / "demo" / "applications" / "acme-eng-2026-08-16"
    (ws).mkdir(parents=True)
    return ws


def receipts(ws, gate):
    return journal.read_receipts(ws, gate)


# --------------------------------------------------------------- the gate table
#
# Nine gates, and for two of them both of the files they read, because the defect was
# never in a gate — it was in 25 call sites that each re-implemented the read.
# `quiet_exit=0` where a minimal fixture is genuinely clean; None where the gate has
# other things to say about a skeleton workspace and only the could-not-run path is
# under test.

GOOD_POSTING = "company: Acme BV\nrole_title: Engineer\nmust_haves: []\n"
GOOD_LETTER = (pathlib.Path(__file__).resolve().parent / "fixtures"
               / "sample_letter.yaml").read_text(encoding="utf-8")
GOOD_SHORTLIST = "rows: []\n"
GOOD_BRIEF = "role: Engineer\n"


def _blocks(ws):
    (ws / "evidence-blocks.json").write_text(
        json.dumps({"blocks": [{"id": "JD-001", "source": "jd", "text": "x" * 20}]}),
        encoding="utf-8")
    (ws / "fit-assessment.md").write_text("# a\n", encoding="utf-8")


def _statement(ws):
    (ws / "supporting-statement.md").write_text("plain prose, no headings\n",
                                                encoding="utf-8")


def _posting(ws):
    (ws / "posting.yaml").write_text(GOOD_POSTING, encoding="utf-8")


def _letter(ws):
    (ws / "letter.yaml").write_text(GOOD_LETTER, encoding="utf-8")


def _cv_pdf(ws):
    (ws / "cv.pdf").write_bytes(
        b"%PDF-1.5\n2 0 obj\n<< /Type /Page /Parent 1 0 R >>\nendobj\n"
        b"trailer\n<< >>\n%%EOF\n")


def _brief(ws):
    (ws / "brief.yaml").write_text(GOOD_BRIEF, encoding="utf-8")


def _shortlist(ws):
    (ws / "shortlist.yaml").write_text(GOOD_SHORTLIST, encoding="utf-8")


GATES = [
    pytest.param(consistency, "fit-assessment.yaml", GOOD_ASSESSMENT, None, 0,
                 id="consistency"),
    pytest.param(count_coverage, "fit-assessment.yaml", GOOD_ASSESSMENT, None, 0,
                 id="count_coverage"),
    pytest.param(check_evidence_refs, "fit-assessment.yaml", GOOD_ASSESSMENT, _blocks,
                 0, id="check_evidence_refs"),
    pytest.param(check_personal_data, "tailored-profile.yaml", GOOD_PROFILE, None, 0,
                 id="check_personal_data"),
    pytest.param(check_word_limits, "posting.yaml", GOOD_POSTING, _statement, 0,
                 id="check_word_limits"),
    pytest.param(check_letter, "letter.yaml", GOOD_LETTER, _posting, None,
                 id="check_letter-letter"),
    pytest.param(check_letter, "posting.yaml", GOOD_POSTING, _letter, None,
                 id="check_letter-posting"),
    pytest.param(check_pages, "tailored-profile.yaml", GOOD_PROFILE, _cv_pdf, None,
                 id="check_pages"),
    pytest.param(check_shortlist, "shortlist.yaml", GOOD_SHORTLIST, _brief, None,
                 id="check_shortlist-shortlist"),
    pytest.param(check_shortlist, "brief.yaml", GOOD_BRIEF, _shortlist, None,
                 id="check_shortlist-brief"),
    pytest.param(check_assessment, "fit-assessment.yaml", GOOD_ASSESSMENT, _blocks,
                 None, id="check_assessment"),
]


def stage(tmp_path, filename, good, extra, text):
    ws = workspace(tmp_path)
    if extra:
        extra(ws)
    (ws / filename).write_text(text if text is not None else good, encoding="utf-8")
    return ws


@pytest.mark.parametrize("module,filename,good,extra,quiet_exit", GATES)
@pytest.mark.parametrize("shape", sorted(BROKEN_TEXT))
def test_a_malformed_file_is_exit_2_with_a_receipt(tmp_path, capsys, module,
                                                   filename, good, extra, quiet_exit,
                                                   shape):
    ws = stage(tmp_path, filename, good, extra, BROKEN_TEXT[shape])
    code = module.main(["--workspace", str(ws)])
    assert code == 2, capsys.readouterr()
    found = receipts(ws, module.GATE)
    assert len(found) == 1, f"{module.GATE} left {len(found)} receipts, not one"
    assert found[0]["verdict"] == "could_not_run"
    assert len(found[0]["findings"]) == 1
    finding = found[0]["findings"][0]
    assert finding.startswith("UNREADABLE_INPUT: "), finding
    assert filename in finding, finding
    # NO_INPUT means the file is absent. This file is present and unusable, and the
    # reader has to be able to tell those apart before they go looking for it.
    assert not finding.startswith("NO_INPUT")


@pytest.mark.parametrize("module,filename,good,extra,quiet_exit", GATES)
def test_an_unreadable_file_is_exit_2_with_a_receipt(tmp_path, capsys, module,
                                                     filename, good, extra,
                                                     quiet_exit, deny_file_reads):
    ws = stage(tmp_path, filename, good, extra, None)
    deny_file_reads(ws / filename)
    code = module.main(["--workspace", str(ws)])
    assert code == 2, capsys.readouterr()
    found = receipts(ws, module.GATE)
    assert len(found) == 1
    assert found[0]["verdict"] == "could_not_run"
    assert found[0]["findings"][0].startswith("UNREADABLE_INPUT: ")
    assert filename in found[0]["findings"][0]


@pytest.mark.parametrize("module,filename,good,extra,quiet_exit", GATES)
def test_the_same_gate_is_quiet_on_a_good_file(tmp_path, capsys, module,
                                               filename, good, extra, quiet_exit):
    """The other direction. A check that fires on ordinary output is worse than no
    check: the reader learns to skip the line, and it stops working on the run that
    mattered."""
    ws = stage(tmp_path, filename, good, extra, None)
    code = module.main(["--workspace", str(ws)])
    assert code != 2, capsys.readouterr()
    if quiet_exit is not None:
        assert code == quiet_exit, capsys.readouterr()
    found = receipts(ws, module.GATE)
    assert len(found) == 1
    assert found[0]["verdict"] != "could_not_run"
    assert not [f for f in found[0]["findings"] if f.startswith("UNREADABLE_INPUT")]


@pytest.mark.parametrize("module,filename,good,extra,quiet_exit", GATES)
def test_a_missing_workspace_still_exits_2_with_no_receipt(tmp_path, capsys, module,
                                                           filename, good, extra,
                                                           quiet_exit):
    """The documented exception, unchanged: there is nothing to append to, and
    creating the directory would materialise a workspace on a typo."""
    missing = tmp_path / "nope"
    assert module.main(["--workspace", str(missing)]) == 2
    assert not (missing / "journal.jsonl").exists()
    assert not missing.exists()


# ------------------------------------------------- the sites that are NOT gates
#
# A renderer has no workspace, so no receipt and no exit-2-with-a-receipt. What it
# does have is the exit code, and it spends it: 2 = "could not read the input",
# which stays distinct from 1 = "rendered, and the PDF step failed". Before this,
# an unparseable profile exited 1 with a yaml traceback — the same code the PDF
# failure uses, and no sentence a reader could act on.

@pytest.mark.parametrize("shape", sorted(BROKEN_TEXT))
def test_render_cv_refuses_an_unusable_profile_with_exit_2(tmp_path, capsys, shape):
    import render_cv
    bad = tmp_path / "profile.yaml"
    bad.write_text(BROKEN_TEXT[shape], encoding="utf-8")
    code = render_cv.main([str(bad), "--format", "md", "--out", str(tmp_path / "cv.md")])
    assert code == 2
    err = capsys.readouterr().err
    assert "cannot render" in err and str(bad) in err
    assert "Traceback" not in err
    assert not (tmp_path / "cv.md").exists()


@pytest.mark.parametrize("shape", sorted(BROKEN_TEXT))
def test_render_letter_refuses_an_unusable_letter_with_exit_2(tmp_path, capsys, shape):
    import render_letter
    bad = tmp_path / "letter.yaml"
    bad.write_text(BROKEN_TEXT[shape], encoding="utf-8")
    code = render_letter.main(
        [str(bad), "--format", "md", "--out", str(tmp_path / "letter.md")])
    assert code == 2
    err = capsys.readouterr().err
    assert "cannot render" in err and str(bad) in err
    assert "Traceback" not in err


def test_render_cv_still_renders_a_good_profile(tmp_path, capsys):
    """The quiet direction for the renderers."""
    import render_cv
    good = tmp_path / "profile.yaml"
    good.write_text("meta:\n  name: Test User\ncontact:\n  email: t@example.com\n",
                    encoding="utf-8")
    out = tmp_path / "cv.md"
    assert render_cv.main([str(good), "--format", "md", "--out", str(out)]) == 0
    assert "Test User" in out.read_text(encoding="utf-8")


def test_render_cv_keeps_its_own_missing_field_error_separate(tmp_path, capsys):
    """A profile that PARSES and is missing a required field is a different answer
    from one that could not be read, and it keeps its own ValueError. Collapsing the
    two would tell a user with a typo'd field name to go looking for a syntax error."""
    import render_cv
    thin = tmp_path / "profile.yaml"
    thin.write_text("personal:\n  name: Test User\n", encoding="utf-8")
    try:
        render_cv.load_profile(thin)
    except journal.YamlUnreadable:                     # pragma: no cover
        raise AssertionError("a parseable profile must not be reported as unreadable")
    except ValueError as exc:
        assert "missing required field" in str(exc)
    else:
        raise AssertionError("expected the missing-required-field ValueError")


@pytest.mark.parametrize("help_output", ["a bare string\n", "- one\n- two\n"])
def test_opencli_meta_refuses_help_output_that_is_not_a_mapping(help_output):
    """The third shape, at a site load_yaml cannot serve: this parses a STRING that
    came back from a subprocess, not a file. `doc.get("commands")` on a bare string
    raised AttributeError, which is not MetadataUnavailable, so the caller's
    could-not-run path never saw it."""
    import unittest.mock as mock

    import opencli_meta
    with mock.patch.object(opencli_meta, "_help_yaml", return_value=help_output):
        with pytest.raises(opencli_meta.MetadataUnavailable) as caught:
            opencli_meta.load_site_metadata("nowcoder")
    assert "not a mapping" in str(caught.value)


def test_opencli_meta_is_quiet_on_ordinary_help_output():
    import unittest.mock as mock
    import opencli_meta
    doc = "commands:\n  - name: search\n    access: read\n"
    with mock.patch.object(opencli_meta, "_help_yaml", return_value=doc):
        table = opencli_meta.load_site_metadata("nowcoder")
    assert table["search"]["access"] == "read"


def test_check_opencli_result_refuses_an_unusable_signals_file(tmp_path, capsys):
    """Not a gate either — it appends an adapter_call record, never a receipt — so
    exit 2 and a stderr line is the whole report available. Returning an empty
    matcher list would be the worst outcome here: every risk-control signal stops
    matching and the classifier reports `ok` on a login wall."""
    import check_opencli_result
    ws = workspace(tmp_path)
    signals = tmp_path / "risk-control-signals.yaml"
    signals.write_text(UNPARSEABLE, encoding="utf-8")
    stdout = tmp_path / "out.txt"
    stdout.write_text("{}", encoding="utf-8")
    code = check_opencli_result.main(
        ["--workspace", str(ws), "--site", "nowcoder", "--command", "search",
         "--exit-code", "0", "--stdout-file", str(stdout),
         "--signals-file", str(signals)])
    assert code == 2
    assert "UNREADABLE_INPUT" in capsys.readouterr().err
    assert not (ws / "journal.jsonl").exists()
