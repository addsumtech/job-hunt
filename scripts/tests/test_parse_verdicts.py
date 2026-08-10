import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import journal
import parse_verdicts as pv
import rounds

ATS_PASS = """I reviewed the CV against the posting.

```
VERDICT: PASS
COVERAGE: 89% (7 present, 2 partial of 9 must-haves)
MISSING_OR_WEAK:
  - real-time processing — partial [Prose] (appears in one experience bullet)
  - Spark — partial [Prose] (mentioned in a project bullet)
FORMAT_ISSUES:
  - none
TOP_FEEDBACK:
  - Move 'Apache Spark' into the Skills section if truthful
```
"""

REC_PASS = """
VERDICT: PASS
SCORES:
  must_have_fit: 4/5 — solid overlap
  readability: 5/5 — skims well
  communication: 4/5 — clear
  logistics: 5/5 — no blockers
  targeting: 4/5 — on target
SCREEN_NOTE: Clears the screen easily — advance to the hiring manager
TOP_FEEDBACK:
  - Lead the summary with the recon work
SUPPLEMENTARY_QUESTIONS_FOR_CANDIDATE:
  - none
"""

HM_PASS = """
VERDICT: PASS
SCORES:
  requirement_match: 4/5 — real overlap
  evidence: 4/5 — concrete
  clarity: 4/5 — readable
  credibility: 5/5 — consistent
  letter_fit: n/a — no letter provided
LEVELING: correctly leveled — senior IC scope matches the posting
STANDOUT_SIGNAL: Core maintainer of a widely-used recon library — surfaced well
TOP_FEEDBACK:
  - Name the scanner vendors in the first bullet
SUPPLEMENTARY_QUESTIONS_FOR_CANDIDATE:
  - Did the Philips collaboration involve direct clinical deployment?
"""


def _files(tmp_path, ats=ATS_PASS, rec=REC_PASS, hm=HM_PASS):
    ws = tmp_path / "acme-engineer-2026-08-09"
    ws.mkdir(parents=True, exist_ok=True)
    for name, text in (("ats.txt", ats), ("rec.txt", rec), ("hm.txt", hm)):
        (ws / name).write_text(text, encoding="utf-8")
    return ws, ["--workspace", str(ws), "--round", "1",
                "--ats", str(ws / "ats.txt"),
                "--recruiter", str(ws / "rec.txt"),
                "--hiring-manager", str(ws / "hm.txt")]


def test_three_clean_passes_are_a_pass_and_print_nothing(tmp_path, capsys):
    ws, argv = _files(tmp_path)
    assert pv.main(argv) == 0
    assert capsys.readouterr().out.strip() == ""
    data = rounds.load_round(ws, 1)
    assert data["combined_verdict"] == "PASS"
    assert data["round"] == 1
    assert set(data["judges"]) == {"ats", "recruiter", "hiring_manager"}


def test_one_reject_makes_the_round_a_reject(tmp_path, capsys):
    ws, argv = _files(tmp_path, hm=HM_PASS.replace("VERDICT: PASS", "VERDICT: REJECT"))
    assert pv.main(argv) == 1
    assert "REJECT: hiring_manager" in capsys.readouterr().out
    assert rounds.load_round(ws, 1)["combined_verdict"] == "REJECT"


def test_a_hedged_verdict_is_ambiguous_not_a_pass(tmp_path, capsys):
    """The whole reason this program exists: a model reading prose treats
    'PASS (with reservations)' as a pass and ships a package that looks fully
    reviewed."""
    ws, argv = _files(tmp_path, ats=ATS_PASS.replace(
        "VERDICT: PASS", "VERDICT: PASS (with reservations)"))
    assert pv.main(argv) == 1
    out = capsys.readouterr().out
    assert "AMBIGUOUS: ats" in out and "re-dispatch" in out
    data = rounds.load_round(ws, 1)
    assert data["combined_verdict"] == "AMBIGUOUS"
    assert data["redispatch"] == ["ats"]


def test_a_missing_verdict_line_is_ambiguous(tmp_path, capsys):
    ws, argv = _files(tmp_path, rec="I think this CV is quite good overall.\n")
    assert pv.main(argv) == 1
    assert "NO_VERDICT: recruiter" in capsys.readouterr().out
    assert rounds.load_round(ws, 1)["combined_verdict"] == "AMBIGUOUS"


def test_lowercase_verdict_is_accepted(tmp_path):
    ws, argv = _files(tmp_path, ats=ATS_PASS.replace("VERDICT: PASS", "verdict: pass"))
    assert pv.main(argv) == 0


def test_the_last_verdict_line_wins(tmp_path):
    """A judge pasted its own agent file echoes the template block
    ('VERDICT: PASS | REJECT') and two worked examples. The contract says the
    real block is last."""
    echoed = "VERDICT: PASS | REJECT\nCOVERAGE: <NN>%\n\n" + ATS_PASS
    ws, argv = _files(tmp_path, ats=echoed)
    assert pv.main(argv) == 0


def test_coverage_is_kept_verbatim_including_n_a(tmp_path):
    ws, argv = _files(tmp_path, ats=ATS_PASS.replace(
        "COVERAGE: 89% (7 present, 2 partial of 9 must-haves)",
        "COVERAGE: n/a (rirekisho form — not ATS-screened)"))
    pv.main(argv)
    assert rounds.load_round(ws, 1)["judges"]["ats"]["coverage"] == \
        "n/a (rirekisho form — not ATS-screened)"


def test_a_single_none_bullet_becomes_an_empty_list(tmp_path):
    ws, argv = _files(tmp_path)
    pv.main(argv)
    judges = rounds.load_round(ws, 1)["judges"]
    assert judges["ats"]["format_issues"] == []
    assert judges["recruiter"]["supplementary_questions_for_candidate"] == []
    assert judges["hiring_manager"]["supplementary_questions_for_candidate"] == [
        "Did the Philips collaboration involve direct clinical deployment?"]


def test_advisory_and_score_fields_are_extracted(tmp_path):
    ws, argv = _files(tmp_path)
    pv.main(argv)
    hm = rounds.load_round(ws, 1)["judges"]["hiring_manager"]
    assert hm["leveling"].startswith("correctly leveled")
    assert hm["standout_signal"].startswith("Core maintainer")
    assert hm["scores"]["credibility"] == "5/5 — consistent"
    assert hm["scores"]["letter_fit"] == "n/a — no letter provided"
    rec = rounds.load_round(ws, 1)["judges"]["recruiter"]
    assert rec["screen_note"].startswith("Clears the screen easily")
    assert rec["scores"]["must_have_fit"] == "4/5 — solid overlap"


def test_merge_round_does_not_clobber_another_writer(tmp_path):
    ws, argv = _files(tmp_path)
    rounds.merge_round(ws, 1, {"dispatch": {"input_hashes": {"cv.md": "ab"}}})
    pv.main(argv)
    data = rounds.load_round(ws, 1)
    assert data["dispatch"]["input_hashes"] == {"cv.md": "ab"}
    assert data["combined_verdict"] == "PASS"


def test_a_missing_transcript_is_exit_2(tmp_path, capsys):
    ws, argv = _files(tmp_path)
    (ws / "rec.txt").unlink()
    assert pv.main(argv) == 2
    assert "rec.txt" in capsys.readouterr().err


def test_every_exit_path_leaves_exactly_one_receipt(tmp_path):
    ws, argv = _files(tmp_path)
    pv.main(argv)
    assert len(journal.read_receipts(ws, "parse_verdicts")) == 1
    (ws / "rec.txt").unlink()
    pv.main(argv)
    receipts = journal.read_receipts(ws, "parse_verdicts")
    assert len(receipts) == 2 and receipts[-1]["verdict"] == "could_not_run"
