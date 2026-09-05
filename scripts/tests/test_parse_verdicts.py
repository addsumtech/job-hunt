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


# ── the receipt reports on the parse, not on the round ───────────────────────


def test_a_cleanly_parsed_reject_is_a_recorded_receipt_not_a_failed_one(tmp_path):
    """A REJECT that parsed cleanly is a SUCCESSFUL parse. Writing `fail` here made
    check_apply's whole honest-stop.yaml branch unreachable — this gate is in
    check_apply.REQUIRED_GATES, so an honest stretch could never reach exit 0 and
    was reported to the user as a failed review. The REJECT is not lost: it is in
    judge-round-<n>.json's combined_verdict, which check_apply reads."""
    ws, argv = _files(tmp_path, rec=REC_PASS.replace("VERDICT: PASS", "VERDICT: REJECT"))
    assert pv.main(argv) == 1                              # the exit code is unchanged
    assert rounds.load_round(ws, 1)["combined_verdict"] == "REJECT"
    receipt = journal.read_receipts(ws, "parse_verdicts")[-1]
    assert receipt["verdict"] == "recorded"
    assert receipt["findings"] == ["REJECT: recruiter returned REJECT"]


def test_a_clean_pass_is_also_recorded(tmp_path):
    """One verdict for one question. The receipt says whether the PARSE worked;
    reading the round's outcome out of it is what put the two on the same axis."""
    ws, argv = _files(tmp_path)
    assert pv.main(argv) == 0
    assert journal.read_receipts(ws, "parse_verdicts")[-1]["verdict"] == "recorded"


def test_a_round_with_no_usable_verdict_still_writes_a_failed_receipt(tmp_path):
    """The direction that must NOT go quiet. combine() also returns AMBIGUOUS when
    a judge emitted no VERDICT line at all, so a blanket exemption for this gate
    would let a round nobody judged exit check_apply behind an honest-stop.yaml."""
    ws, argv = _files(tmp_path, ats=ATS_PASS.replace("VERDICT: PASS", "VERDICT: maybe"))
    assert pv.main(argv) == 1
    receipt = journal.read_receipts(ws, "parse_verdicts")[-1]
    assert receipt["verdict"] == "fail"
    assert receipt["findings"] and receipt["findings"][0].startswith("AMBIGUOUS: ats")


def test_a_judge_that_said_nothing_at_all_writes_a_failed_receipt(tmp_path):
    ws, argv = _files(tmp_path, hm="I had a look and it seems reasonable overall.\n")
    assert pv.main(argv) == 1
    receipt = journal.read_receipts(ws, "parse_verdicts")[-1]
    assert receipt["verdict"] == "fail"
    assert any(f.startswith("NO_VERDICT: hiring_manager") for f in receipt["findings"])


def test_every_verdict_this_gate_writes_is_in_the_journal_vocabulary(tmp_path):
    ws, argv = _files(tmp_path)
    pv.main(argv)
    pv.main(_files(tmp_path / "b", ats=ATS_PASS.replace("VERDICT: PASS", "x"))[1])
    (ws / "rec.txt").unlink()
    pv.main(argv)
    assert {r["verdict"] for r in journal.read_receipts(ws, "parse_verdicts")} \
        <= set(journal.VERDICTS)


def _round_argv(ws, n):
    return ["--workspace", str(ws), "--round", str(n),
            "--ats", str(ws / "ats.txt"),
            "--recruiter", str(ws / "rec.txt"),
            "--hiring-manager", str(ws / "hm.txt")]


def test_reparsing_the_previous_rounds_transcripts_fails_rather_than_records(tmp_path):
    """Stamping the round forced the parser to RUN for round n; it did not force
    it to run on round n's JUDGEMENTS. The finding printed and the gate exited 0
    with a "recorded" receipt, so check_apply — which reads that receipt and its
    round stamp — passed a round nobody judged. That is the bypass the round
    stamp exists to close, reopened one level up."""
    ws, argv = _files(tmp_path)
    assert pv.main(argv) == 0
    assert pv.main(_round_argv(ws, 2)) == 1
    last = journal.read_receipts(ws, "parse_verdicts")[-1]
    assert last["verdict"] == "fail"
    assert any(f.startswith("SAME_JUDGEMENTS_AS_ROUND_") for f in last["findings"])


def test_a_genuinely_new_round_still_records_and_exits_zero(tmp_path):
    """The twin: new transcripts must go back to a clean pass, or the fix has
    simply made round 2 impossible."""
    ws, argv = _files(tmp_path)
    assert pv.main(argv) == 0
    for name in ("ats.txt", "rec.txt", "hm.txt"):
        path = ws / name
        path.write_text(path.read_text(encoding="utf-8") + "\nRound two rewrite.\n",
                        encoding="utf-8")
    assert pv.main(_round_argv(ws, 2)) == 0
    last = journal.read_receipts(ws, "parse_verdicts")[-1]
    assert last["verdict"] == "recorded"
    assert not any(f.startswith("SAME_JUDGEMENTS") for f in last["findings"])
