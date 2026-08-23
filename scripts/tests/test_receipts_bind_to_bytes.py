"""Receipts as claims about bytes, not about a moment.

journal.py's own docstring says a gate receipt is a claim about specific bytes.
An audit on 2026-08-23 grepped it: eleven sites WRITE `input_hashes`, and nothing
ever read one back. check_apply — the single gate that decides "this package may
be delivered" — composed purely on the `verdict` field, so every gate's pass kept
vouching for the package after its input changed.

Four holes, all in the same seam:

  1. `input_hashes` never re-verified — a file edited after its gate passed
  2. `parse_verdicts`' receipt carried no round, so from round 2 onward a
     hand-written `combined_verdict: "PASS"` rode round 1's receipt
  3. an unparseable journal line was silently dropped, promoting the PREVIOUS
     receipt for that gate — a truncated `fail` read as the older `pass`
  4. an unreadable posting.yaml removed the check_word_limits requirement AND
     swallowed the reason

The reachable path for (1) is the ordinary actor-critic loop, not a hand edit:
modes/apply.md gives explicit re-run instructions for check_claims and
check_render_freshness, but `check_personal_data` and `lint_cv` appear only in
the one-shot pre-dispatch block.
"""
import io
import contextlib
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_apply
import journal
import test_check_apply as T


def run(ws, root):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = check_apply.main(T._argv(ws, root))
    lines = [line for line in buf.getvalue().splitlines() if line.strip()]
    return rc, sorted({line.split(":", 1)[0] for line in lines})


def workspace_with_real_lint_receipt(tmp_path):
    """A passing workspace whose lint_cv receipt records a real file hash."""
    root = T._skill_root(tmp_path)
    ws = T._good_workspace(tmp_path, root, skip=("lint_cv",))
    cv = ws / "cv.md"
    cv.write_text("# CV\nOwned the reconstruction pipeline.\n", encoding="utf-8")
    journal.receipt(ws, "lint_cv", {"cv.md": journal.sha256_file(cv)}, "pass")
    return ws, root, cv


# ── 1. input_hashes are re-verified ───────────────────────────────────────────

def test_a_receipt_whose_input_is_unchanged_stays_quiet(tmp_path):
    ws, root, _ = workspace_with_real_lint_receipt(tmp_path)
    assert run(ws, root) == (0, [])


def test_a_file_edited_after_its_gate_passed_is_reported(tmp_path):
    """The measured case: a round-2 bullet rewrite introducing five clichés left
    check_apply at 0 while lint_cv on the same bytes exited 1."""
    ws, root, cv = workspace_with_real_lint_receipt(tmp_path)
    cv.write_text("# CV\nA results-driven synergistic team player.\n",
                  encoding="utf-8")
    rc, codes = run(ws, root)
    assert rc == 1 and "STALE_RECEIPT" in codes


def test_an_input_deleted_after_its_gate_passed_is_reported(tmp_path):
    ws, root, cv = workspace_with_real_lint_receipt(tmp_path)
    cv.unlink()
    rc, codes = run(ws, root)
    assert rc == 1 and "RECEIPT_INPUT_MISSING" in codes


def test_a_receipt_that_records_no_inputs_is_not_a_finding(tmp_path):
    """Some gates record none, and a receipt claiming nothing about files cannot
    be stale. Firing here would make every forged-receipt test in the suite red
    for a reason unrelated to what it is testing."""
    root = T._skill_root(tmp_path)
    ws = T._good_workspace(tmp_path, root)
    assert run(ws, root) == (0, [])


def test_stale_inputs_reports_each_changed_file_once(tmp_path):
    ws, root, cv = workspace_with_real_lint_receipt(tmp_path)
    other = ws / "letter.md"
    other.write_text("Dear team,\n", encoding="utf-8")
    journal.receipt(ws, "lint_cv",
                    {"cv.md": journal.sha256_file(cv),
                     "letter.md": journal.sha256_file(other)}, "pass")
    cv.write_text("changed\n", encoding="utf-8")
    other.write_text("also changed\n", encoding="utf-8")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        check_apply.main(T._argv(ws, root))
    stale = [line for line in buf.getvalue().splitlines()
             if line.startswith("STALE_RECEIPT")]
    assert len(stale) == 2
    assert any("cv.md" in line for line in stale)
    assert any("letter.md" in line for line in stale)


# ── 2. the round stamp ────────────────────────────────────────────────────────

def test_a_parse_verdicts_receipt_with_no_round_is_reported(tmp_path):
    """Every receipt written before this change lacks the stamp, and a receipt
    that cannot be tied to a round cannot vouch for one."""
    root = T._skill_root(tmp_path)
    ws = T._good_workspace(tmp_path, root, skip=("parse_verdicts",))
    journal.receipt(ws, "parse_verdicts", {}, "pass")   # the old, round-blind shape
    rc, codes = run(ws, root)
    assert rc == 1 and "PARSE_VERDICTS_ROUND_UNKNOWN" in codes


def test_parse_verdicts_stamps_the_round_it_parsed(tmp_path):
    import parse_verdicts
    ws = tmp_path / "ws"
    ws.mkdir()
    block = ("VERDICT: PASS\nCOVERAGE: 9/9\nSCREEN_NOTE: fine\n"
             "MISSING_OR_WEAK:\n- none\nTOP_FEEDBACK:\n- none\n")
    for name in ("ats", "recruiter", "hiring-manager"):
        (ws / f"judge-{name}.txt").write_text(block, encoding="utf-8")
    assert parse_verdicts.main([
        "--workspace", str(ws), "--round", "3",
        "--ats", str(ws / "judge-ats.txt"),
        "--recruiter", str(ws / "judge-recruiter.txt"),
        "--hiring-manager", str(ws / "judge-hiring-manager.txt")]) == 0
    last = journal.read_receipts(ws, "parse_verdicts")[-1]
    assert last["round"] == 3


def test_parse_verdicts_records_its_inputs_by_path_not_by_judge_name(tmp_path):
    """`input_hashes` is now re-verified against disk, and a key like "ats" names
    no file — so the three judge transcripts, the evidence the whole review loop
    rests on, would have been the one required gate whose receipt could not be
    checked."""
    import parse_verdicts
    ws = tmp_path / "ws"
    ws.mkdir()
    block = "VERDICT: PASS\nCOVERAGE: 9/9\n"
    for name in ("ats", "recruiter", "hiring-manager"):
        (ws / f"judge-{name}.txt").write_text(block, encoding="utf-8")
    parse_verdicts.main([
        "--workspace", str(ws), "--round", "1",
        "--ats", str(ws / "judge-ats.txt"),
        "--recruiter", str(ws / "judge-recruiter.txt"),
        "--hiring-manager", str(ws / "judge-hiring-manager.txt")])
    recorded = journal.read_receipts(ws, "parse_verdicts")[-1]["input_hashes"]
    assert set(recorded) == {"judge-ats.txt", "judge-recruiter.txt",
                             "judge-hiring-manager.txt"}
    for label in recorded:
        assert (ws / label).is_file(), f"{label} must resolve to a real file"


# ── 3. a corrupt journal is not a clean one ───────────────────────────────────

def test_a_truncated_journal_line_is_reported(tmp_path):
    root = T._skill_root(tmp_path)
    ws = T._good_workspace(tmp_path, root)
    with (ws / "journal.jsonl").open("a", encoding="utf-8") as fh:
        fh.write('{"action": "gate", "ga\n')
    rc, codes = run(ws, root)
    assert rc == 1 and "JOURNAL_CORRUPT" in codes


def test_reading_receipts_still_survives_a_half_written_line(tmp_path):
    """The property test_journal.py pins, kept intact. Dropping a bad line is
    right for READING — a later gate must still see that an earlier one ran — and
    wrong for COMPOSING. The two answers now live in two functions."""
    ws = tmp_path / "ws"
    journal.receipt(ws, "lint_cv", {}, "pass")
    with (ws / "journal.jsonl").open("a", encoding="utf-8") as fh:
        fh.write('{"action": "gate", "ga\n')
    journal.receipt(ws, "check_claims", {}, "pass")
    assert [r["gate"] for r in journal.read_receipts(ws)] == ["lint_cv", "check_claims"]
    assert journal.corrupt_lines(ws) == [2]


def test_corrupt_lines_is_empty_on_a_clean_journal(tmp_path):
    ws = tmp_path / "ws"
    journal.receipt(ws, "lint_cv", {}, "pass")
    assert journal.corrupt_lines(ws) == []
    assert journal.corrupt_lines(tmp_path / "never-used") == []


# ── the receipt record itself ─────────────────────────────────────────────────

def test_extra_fields_are_recorded_and_covered_by_the_receipt_hash(tmp_path):
    ws = tmp_path / "ws"
    rec = journal.receipt(ws, "parse_verdicts", {}, "pass", extra={"round": 2})
    assert rec["round"] == 2
    plain = journal.receipt(ws, "parse_verdicts", {}, "pass")
    assert "round" not in plain
    assert rec["receipt_hash"] != plain["receipt_hash"]


def test_extra_cannot_overwrite_a_core_receipt_field(tmp_path):
    ws = tmp_path / "ws"
    rec = journal.receipt(ws, "lint_cv", {}, "pass",
                          extra={"verdict": "forged", "gate": "other"})
    assert rec["verdict"] == "pass" and rec["gate"] == "lint_cv"


# ── the quiet cases these changes must not have cost ──────────────────────────

def test_a_markdown_only_run_is_still_deliverable(tmp_path, capsys):
    """The cry-wolf case. A `could_not_run` check_pages receipt is what a
    Markdown-only run leaves, and that package is perfectly deliverable — an
    earlier draft of this change blocked on every `could_not_run` and would have
    made the ordinary run fail."""
    root = T._skill_root(tmp_path)
    ws = T._good_workspace(tmp_path, root)
    journal.receipt(ws, "check_pages", {}, "could_not_run",
                    [f"MISSING_INPUT: {ws / 'cv.pdf'}"])
    assert run(ws, root) == (0, [])
