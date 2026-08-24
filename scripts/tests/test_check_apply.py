import contextlib
import importlib
import io
import json
import pathlib
import sys

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from findings import assert_finding, assert_no_finding, assert_clean
import check_apply
import check_claims
import check_render_freshness as crf
import enter_mode
import journal
import parse_verdicts as pv
import rounds

REQUIRED = ("check_personal_data", "check_claims", "check_render_freshness",
            "parse_verdicts", "lint_cv")

# A master profile and a tailoring that fabricates against it, for the tests that
# run the REAL check_claims instead of forging its receipt.
MASTER = {
    "meta": {"name": "Test User"},
    "skills": {"languages": ["Python", "C++"]},
    "experience": [{"title": "Research Engineer", "org": "Acme",
                    "bullets": ["Built a reconstruction pipeline."]}],
}
FABRICATED = {**MASTER,
              "skills": {"languages": ["Python", "C++"], "infra": ["Kubernetes"]},
              "certifications": ["AWS Certified Solutions Architect"]}

# Every upstream workspace gate, with the extra arguments argparse demands
# before main() can reach its workspace guard. check_apply has its own case
# below (test_a_missing_workspace_is_exit_2_and_creates_nothing).
GATE_ARGS = {
    "check_personal_data": [],
    "check_claims": [],
    "check_render_freshness": ["--round", "1"],
    "parse_verdicts": ["--round", "1", "--ats", "a.txt",
                       "--recruiter", "r.txt", "--hiring-manager", "h.txt"],
    "lint_cv": [],
    "check_letter": [],
    "check_pages": [],
    "check_word_limits": [],
}


def _skill_root(tmp_path, body="# Apply mode\n\nartifact: honest-stop.yaml\n"):
    root = tmp_path / "skill"
    (root / "modes").mkdir(parents=True, exist_ok=True)
    (root / "modes" / "apply.md").write_text(body, encoding="utf-8")
    return root


def _good_workspace(tmp_path, root, skip=()):
    """A workspace that passes, with `skip` naming the gates NOT forged here.

    `skip` exists because forging all five receipts is what hid the defect this
    file is now pinned against: `journal.receipt(..., "pass")` can write a state
    the real gate cannot emit, so a fixture built entirely out of forgeries never
    lets record-vs-verify — or a cleanly-parsed REJECT — into a test at all. A
    test that cares what a gate really writes skips it here and runs it for real.
    """
    ws = tmp_path / "acme-engineer-2026-08-09"
    ws.mkdir(parents=True, exist_ok=True)
    # enter_mode prints "entered mode apply; read …" — setup noise. Left in the
    # capture it lands in every "passes silently" assertion below and makes them
    # fail for a reason that has nothing to do with the gate under test.
    with contextlib.redirect_stdout(io.StringIO()):
        enter_mode.main(["--workspace", str(ws), "--mode", "apply",
                         "--skill-root", str(root)])
    for gate in REQUIRED:
        if gate in skip:
            continue
        # parse_verdicts stamps the round it parsed, so check_apply can tell
        # whether that receipt is about the round in the workspace. A forgery
        # that omits it is not a forgery of what the gate writes — it is a
        # forgery of the older, round-blind receipt, and every test built on it
        # would be asserting against a shape the skill no longer produces.
        extra = {"round": 1} if gate == "parse_verdicts" else None
        journal.receipt(ws, gate, {}, "pass", extra=extra)
    rounds.merge_round(ws, 1, {"round": 1, "combined_verdict": "PASS"})
    (ws / "interview-brief.md").write_text("# Interview brief\n", encoding="utf-8")
    return ws


def _claims_workspace(tmp_path, root, tailored):
    """A workspace whose check_claims receipts come from the real gate.

    Runs exactly what modes/apply.md's "On entering this mode" block runs, and
    nothing more: `check_claims --record`, the setup step that fingerprints the
    master. The verification pass is deliberately left to the caller.
    """
    ws = _good_workspace(tmp_path, root, skip=("check_claims",))
    master = tmp_path / "profile.yaml"
    master.write_text(yaml.safe_dump(MASTER, allow_unicode=True), encoding="utf-8")
    (ws / "tailored-profile.yaml").write_text(
        yaml.safe_dump(tailored, allow_unicode=True), encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()):
        assert check_claims.main(["--workspace", str(ws), "--master", str(master),
                                  "--record"]) == 0
    return ws, master


def _record_claims(ws, master):
    with contextlib.redirect_stdout(io.StringIO()):
        return check_claims.main(["--workspace", str(ws), "--master", str(master),
                                  "--record"])


def _verify_claims(ws):
    with contextlib.redirect_stdout(io.StringIO()):
        return check_claims.main(["--workspace", str(ws)])


def _freshness_workspace(tmp_path, root):
    """Same shape for check_render_freshness: the dispatch record and no verify."""
    ws = _good_workspace(tmp_path, root, skip=("check_render_freshness",))
    (ws / "cv.md").write_text("# Test User\n\n## Experience\n", encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()):
        assert crf.main(["--workspace", str(ws), "--round", "1",
                         "--record", str(ws / "cv.md")]) == 0
    return ws


def _parse_round(ws, n, verdicts):
    """Run the REAL parse_verdicts over three transcripts and return its exit code.

    Not forged: the whole point of the honest-stretch tests below is the receipt
    the program actually emits for a state it can actually reach.
    """
    argv = ["--workspace", str(ws), "--round", str(n)]
    for flag, name, verdict in zip(("--ats", "--recruiter", "--hiring-manager"),
                                   ("ats", "recruiter", "hiring-manager"), verdicts):
        p = ws / f"judge-{n}-{name}.txt"
        p.write_text(f"VERDICT: {verdict}\nTOP_FEEDBACK:\n  - none\n", encoding="utf-8")
        argv += [flag, str(p)]
    with contextlib.redirect_stdout(io.StringIO()):
        return pv.main(argv)


def _argv(ws, root):
    return ["--workspace", str(ws), "--skill-root", str(root)]


def test_the_required_list_this_file_forges_is_the_one_the_gate_reads():
    """REQUIRED above is a copy. A copy that drifts makes every fixture in this
    file build a workspace the gate no longer considers complete — and the tests
    would still pass, because they only assert what they themselves forged."""
    assert REQUIRED == check_apply.REQUIRED_GATES


def test_a_complete_apply_run_passes_silently(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    assert check_apply.main(_argv(ws, root)) == 0
    assert capsys.readouterr().out.strip() == ""


def test_a_missing_upstream_receipt_is_reported_by_name(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    (ws / "journal.jsonl").write_text(
        "\n".join(l for l in (ws / "journal.jsonl").read_text(encoding="utf-8")
                  .splitlines() if "check_claims" not in l) + "\n", encoding="utf-8")
    assert check_apply.main(_argv(ws, root)) == 1
    out = capsys.readouterr().out
    assert "MISSING_RECEIPT: check_claims" in out
    assert "never run" in out


def test_a_hand_written_round_file_without_a_parse_verdicts_receipt_fails(tmp_path, capsys):
    """judge-round-1.json is a plain JSON file. Without this, anyone (or any
    model) can write `combined_verdict: PASS` into it and check_apply agrees —
    with no evidence the parser ever ran, which is the exact substitution
    parse_verdicts.py exists to prevent."""
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    (ws / "journal.jsonl").write_text(
        "\n".join(l for l in (ws / "journal.jsonl").read_text(encoding="utf-8")
                  .splitlines() if "parse_verdicts" not in l) + "\n", encoding="utf-8")
    assert check_apply.main(_argv(ws, root)) == 1
    assert "MISSING_RECEIPT: parse_verdicts" in capsys.readouterr().out


def test_a_failed_upstream_gate_is_reported(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    journal.receipt(ws, "lint_cv", {}, "fail", ["CLICHE: cv.md:4 contains 'synergy'"])
    assert check_apply.main(_argv(ws, root)) == 1
    assert "UPSTREAM_FAILED: lint_cv" in capsys.readouterr().out


def test_the_latest_receipt_wins_so_a_rerun_can_clear_a_failure(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    journal.receipt(ws, "lint_cv", {}, "fail", ["CLICHE"])
    journal.receipt(ws, "lint_cv", {}, "pass")
    assert check_apply.main(_argv(ws, root)) == 0


def test_check_letter_is_required_only_when_a_letter_exists(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    assert check_apply.main(_argv(ws, root)) == 0
    (ws / "letter.yaml").write_text("sender: {}\n", encoding="utf-8")
    capsys.readouterr()
    assert check_apply.main(_argv(ws, root)) == 1
    assert "MISSING_RECEIPT: check_letter" in capsys.readouterr().out


def test_a_rejected_round_without_an_honest_stop_fails(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    rounds.merge_round(ws, 1, {"combined_verdict": "REJECT"})
    assert check_apply.main(_argv(ws, root)) == 1
    out = capsys.readouterr().out
    # The CODE at line start, not a free substring. All three of the strings this
    # used to assert also occur inside a NEIGHBOURING finding's prose, so deleting
    # the branch that emits NO_PASS_NO_STOP left every test in this file passing —
    # and that branch is what tells a stretch candidate whether the package was
    # badly built or simply a reach. See scripts/tests/findings.py.
    line = assert_finding(out, "NO_PASS_NO_STOP")
    assert "poorly_built" in line and "honest_stretch" in line, (
        "the finding itself must offer both classifications, not merely appear "
        "in output that mentions them somewhere")


# The "a complete honest stop passes" case lives at the bottom of this file as
# test_an_honest_stretch_reaches_exit_0_with_the_real_parser. It used to be here,
# forging `parse_verdicts: pass` beside a REJECT round — a state the program cannot
# emit — and that forgery is exactly what hid the fact that no honest stretch could
# ever reach exit 0 in a real run.


def test_an_honest_stop_with_a_made_up_classification_fails(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    rounds.merge_round(ws, 1, {"combined_verdict": "REJECT"})
    (ws / "honest-stop.yaml").write_text(yaml.safe_dump({
        "classification": "needs_work", "verdict": "stretch",
        "reason": "x", "evidence": ["y"]}), encoding="utf-8")
    assert check_apply.main(_argv(ws, root)) == 1
    assert "BAD_STOP_CLASSIFICATION" in capsys.readouterr().out


def test_an_honest_stop_with_an_off_vocabulary_verdict_fails(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    rounds.merge_round(ws, 1, {"combined_verdict": "REJECT"})
    (ws / "honest-stop.yaml").write_text(yaml.safe_dump({
        "classification": "honest_stretch", "verdict": "maybe",
        "reason": "x", "evidence": ["y"]}), encoding="utf-8")
    assert check_apply.main(_argv(ws, root)) == 1
    out = capsys.readouterr().out
    assert "BAD_STOP_VERDICT" in out and "worth_applying" in out


def test_an_honest_stop_with_no_evidence_fails(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    rounds.merge_round(ws, 1, {"combined_verdict": "REJECT"})
    (ws / "honest-stop.yaml").write_text(yaml.safe_dump({
        "classification": "poorly_built", "verdict": "worth_applying",
        "reason": "x", "evidence": []}), encoding="utf-8")
    assert check_apply.main(_argv(ws, root)) == 1
    assert "INCOMPLETE_STOP" in capsys.readouterr().out


def test_a_missing_interview_brief_fails(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    (ws / "interview-brief.md").unlink()
    assert check_apply.main(_argv(ws, root)) == 1
    assert "NO_BRIEF" in capsys.readouterr().out


def test_no_mode_entry_fails(tmp_path, capsys):
    """The layer-1.5 backstop: modes/apply.md is not optional, and the journal
    is what proves it was loaded."""
    root = _skill_root(tmp_path)
    ws = tmp_path / "no-entry"
    ws.mkdir()
    for gate in REQUIRED:
        journal.receipt(ws, gate, {}, "pass")
    rounds.merge_round(ws, 1, {"combined_verdict": "PASS"})
    (ws / "interview-brief.md").write_text("x\n", encoding="utf-8")
    assert check_apply.main(_argv(ws, root)) == 1
    assert "NO_MODE_ENTRY" in capsys.readouterr().out


def test_an_edited_mode_file_invalidates_the_entry(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    (root / "modes" / "apply.md").write_text("# Apply mode\n\nrewritten\n",
                                             encoding="utf-8")
    assert check_apply.main(_argv(ws, root)) == 1
    assert "MODE_FILE_CHANGED" in capsys.readouterr().out


def test_no_round_at_all_fails(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    rounds.round_path(ws, 1).unlink()
    assert check_apply.main(_argv(ws, root)) == 1
    assert "NO_ROUND" in capsys.readouterr().out


def test_the_highest_numbered_round_is_the_one_that_counts(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    rounds.merge_round(ws, 1, {"combined_verdict": "REJECT"})
    rounds.merge_round(ws, 2, {"round": 2, "combined_verdict": "PASS"})
    # Round 2 was parsed by the gate, which is what makes this the ordinary
    # second round rather than the substitution the test below pins.
    journal.receipt(ws, "parse_verdicts", {}, "pass", extra={"round": 2})
    assert check_apply.main(_argv(ws, root)) == 0


def test_a_round_the_parser_never_saw_cannot_carry_the_package(tmp_path, capsys):
    """The bypass the round stamp closes, and the reason the fixture above had to
    gain a line.

    judge-round-<n>.json is a plain JSON file. From round 2 onward, skipping
    `parse_verdicts --round 2` and hand-writing `combined_verdict: "PASS"` left
    round 1's receipt vouching for a round the judges never returned — measured
    ending exit 0 over a REJECT on disk. Round 1 alone was protected, by
    MISSING_RECEIPT.
    """
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)          # carries a round-1 receipt
    rounds.merge_round(ws, 1, {"combined_verdict": "REJECT"})
    rounds.merge_round(ws, 2, {"round": 2, "combined_verdict": "PASS"})
    assert check_apply.main(_argv(ws, root)) == 1
    assert "PARSE_VERDICTS_STALE_ROUND" in capsys.readouterr().out


def test_a_failed_mode_entry_leaves_a_trace_in_the_journal(tmp_path):
    """The layer-1.5 backstop's own failure must not be the one silent thing in
    the system. An exit-2 mode entry that wrote nothing would be
    indistinguishable from a mode entry nobody attempted — risk-register #12,
    in the exact place this plan calls the backstop."""
    root = tmp_path / "skill"
    (root / "modes").mkdir(parents=True)
    ws = tmp_path / "ws"
    # The workspace has to exist for this test to be about what it says it is about.
    # enter_mode no longer creates it — see scripts/tests/test_enter_mode.py — and a
    # non-existent workspace exits 2 on a different branch, before the mode file is
    # ever looked at, so it would pass this test while proving nothing about traces.
    ws.mkdir()
    assert enter_mode.main(["--workspace", str(ws), "--mode", "apply",
                            "--skill-root", str(root)]) == 2
    recs = [json.loads(l) for l in
            (ws / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["action"] for r in recs] == ["mode_entry_failed"]
    assert recs[0]["mode"] == "apply" and "apply.md" in recs[0]["mode_file"]
    assert enter_mode.latest_mode_entry(ws, "apply") is None


def test_a_missing_workspace_is_exit_2_and_creates_nothing(tmp_path, capsys):
    """The single place the one-receipt-per-exit rule yields: there is no
    journal to append to. A gate that mkdir'd the workspace it was told does
    not exist would manufacture the evidence directory it is checking."""
    root = _skill_root(tmp_path)
    ws = tmp_path / "never-created"
    assert check_apply.main(_argv(ws, root)) == 2
    assert "does not exist" in capsys.readouterr().err
    assert not ws.exists()


def test_it_leaves_exactly_one_receipt(tmp_path):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    check_apply.main(_argv(ws, root))
    assert [r["verdict"] for r in journal.read_receipts(ws, "check_apply")] == ["pass"]


# ── (a) a setup receipt is not a verification receipt ────────────────────────
#
# modes/apply.md runs `check_claims --record` and `check_render_freshness --record`
# as documented mode-entry / pre-dispatch steps. Both store a baseline and check
# nothing. While their verdict was in check_apply.PASSING_VERDICTS, a run that did
# only the setup — or that re-ran the setup after a real failure, which a resume or
# a round 2 does — satisfied the gate whose entire job is proving the checks ran.


def test_the_documented_setup_alone_does_not_satisfy_check_claims(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws, _ = _claims_workspace(tmp_path, root, FABRICATED)
    capsys.readouterr()
    assert check_apply.main(_argv(ws, root)) == 1
    out = capsys.readouterr().out
    assert "NOT_VERIFIED: check_claims" in out
    # The diagnosis has to be "never ran", not "failed". Nothing failed here, and a
    # finding that says it did sends the reader looking for a defect that is not there.
    assert "UPSTREAM_FAILED" not in out
    # And the verification pass it never ran is not a formality on this workspace.
    assert _verify_claims(ws) == 1


def test_running_the_verification_pass_makes_the_setup_workspace_quiet(tmp_path, capsys):
    """The other direction. A run that did BOTH steps prints nothing — otherwise
    the finding above fires on every honest application and stops being read."""
    root = _skill_root(tmp_path)
    ws, _ = _claims_workspace(tmp_path, root, MASTER)
    assert _verify_claims(ws) == 0
    capsys.readouterr()
    assert check_apply.main(_argv(ws, root)) == 0
    assert capsys.readouterr().out.strip() == ""


def test_re_recording_after_a_failed_verification_does_not_clear_it(tmp_path, capsys):
    """The worst shape of it: run the real check, watch it FAIL, then run the
    documented `--record` entry step again — a resume or a round 2 does — and the
    latest receipt was a passing one. The failure is gone from the composer's view."""
    root = _skill_root(tmp_path)
    ws, master = _claims_workspace(tmp_path, root, FABRICATED)
    assert _verify_claims(ws) == 1
    assert _record_claims(ws, master) == 0
    assert [r["verdict"] for r in journal.read_receipts(ws, "check_claims")][-1] \
        not in ("pass",)
    capsys.readouterr()
    assert check_apply.main(_argv(ws, root)) == 1
    assert "NOT_VERIFIED: check_claims" in capsys.readouterr().out


def test_a_recorded_dispatch_is_not_a_verified_round(tmp_path, capsys):
    """check_render_freshness's two receipts are otherwise identical — same gate,
    same input hashes, same shape — so the verdict is the only thing that can tell
    "hashed the files before dispatch" from "confirmed the judges read them"."""
    root = _skill_root(tmp_path)
    ws = _freshness_workspace(tmp_path, root)
    capsys.readouterr()
    assert check_apply.main(_argv(ws, root)) == 1
    out = capsys.readouterr().out
    assert "NOT_VERIFIED: check_render_freshness" in out
    assert "UPSTREAM_FAILED" not in out


def test_verifying_the_round_makes_the_freshness_workspace_quiet(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _freshness_workspace(tmp_path, root)
    with contextlib.redirect_stdout(io.StringIO()):
        assert crf.main(["--workspace", str(ws), "--round", "1"]) == 0
    capsys.readouterr()
    assert check_apply.main(_argv(ws, root)) == 0
    assert capsys.readouterr().out.strip() == ""


@pytest.mark.parametrize("gate", ("check_claims", "check_render_freshness"))
def test_the_setup_verdict_is_outside_the_passing_set(gate, tmp_path):
    """Pinned in both directions, on the real gates, because patching
    PASSING_VERDICTS by hand left the whole suite green: nothing held the token."""
    root = _skill_root(tmp_path)
    ws = (_claims_workspace(tmp_path, root, MASTER)[0] if gate == "check_claims"
          else _freshness_workspace(tmp_path, root))
    verdict = journal.read_receipts(ws, gate)[-1]["verdict"]
    assert verdict in check_apply.SETUP_VERDICTS
    assert verdict not in check_apply.PASSING_VERDICTS
    assert verdict in journal.VERDICTS


# ── (b) any gate that ran and failed, named or not ───────────────────────────


def test_a_failing_gate_nobody_named_still_blocks_the_package(tmp_path, capsys):
    """A gate can RUN, print CV_TOO_LONG, write `verdict: fail` — and while
    check_apply only inspected the gates it enumerates, it wrote its own `pass`
    three lines below that receipt in the same journal.jsonl. There is no cv.pdf
    here, so check_pages is not required by name: only the general rule can catch it."""
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    journal.receipt(ws, "check_pages", {}, "fail",
                    ["CV_TOO_LONG: cv.pdf is 3 pages; the length table allows 2"])
    assert check_apply.main(_argv(ws, root)) == 1
    out = capsys.readouterr().out
    assert "UPSTREAM_FAILED: check_pages" in out and "CV_TOO_LONG" in out


def test_a_gate_that_could_not_run_and_was_not_required_stays_quiet(tmp_path, capsys):
    """The cry-wolf case for the rule above. A Markdown-only run leaves a
    `could_not_run` check_pages receipt and is a perfectly deliverable package."""
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    journal.receipt(ws, "check_pages", {}, "could_not_run",
                    [f"MISSING_INPUT: {ws / 'cv.pdf'}"])
    assert check_apply.main(_argv(ws, root)) == 0
    assert capsys.readouterr().out.strip() == ""


def test_re_running_an_unnamed_gate_to_a_pass_clears_it(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    journal.receipt(ws, "check_pages", {}, "fail", ["CV_TOO_LONG: 3 pages"])
    journal.receipt(ws, "check_pages", {}, "pass")
    assert check_apply.main(_argv(ws, root)) == 0
    assert capsys.readouterr().out.strip() == ""


def test_another_mode_s_failing_gate_is_not_this_composer_s_finding(tmp_path, capsys):
    """check_mock writes into this same workspace. A mock-interview round that
    failed is a real finding for check_mock and none of check_apply's business —
    a composer that reports another mode's failures is one people learn to argue
    with, and there is no edit in apply mode that clears it."""
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    journal.append(ws, {"action": "gate", "gate": "check_mock", "mode": "interview",
                        "verdict": "fail", "findings": ["DRIFT: answer 2"],
                        "input_hashes": {}})
    assert check_apply.main(_argv(ws, root)) == 0
    assert capsys.readouterr().out.strip() == ""


def test_an_unstamped_failing_receipt_is_still_checked(tmp_path, capsys):
    """The exclusion above keys on a stamp that names a DIFFERENT mode. A receipt
    written before any mode entry carries "unknown", and skipping those would put
    the hole straight back."""
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    journal.append(ws, {"action": "gate", "gate": "check_pages", "mode": "unknown",
                        "verdict": "fail", "findings": ["CV_TOO_LONG: 4 pages"],
                        "input_hashes": {}})
    assert check_apply.main(_argv(ws, root)) == 1
    assert "UPSTREAM_FAILED: check_pages" in capsys.readouterr().out


# ── (c) the two gates the required list forgot ───────────────────────────────


def _pdf(path, pages=1):
    path.write_bytes(b"%PDF-1.4\n" + b"/Type /Page\n" * pages + b"%%EOF\n")


def test_check_pages_is_required_once_there_is_a_pdf_to_measure(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    (ws / "tailored-profile.yaml").write_text("meta: {}\n", encoding="utf-8")
    assert check_apply.main(_argv(ws, root)) == 0          # no PDF yet: quiet
    capsys.readouterr()
    _pdf(ws / "cv.pdf")
    assert check_apply.main(_argv(ws, root)) == 1
    out = capsys.readouterr().out
    assert "MISSING_RECEIPT: check_pages" in out and "cv.pdf" in out


def test_check_pages_is_not_demanded_without_the_profile_it_measures_against(
        tmp_path, capsys):
    """Both files are its inputs. Demanding the receipt when tailored-profile.yaml
    is absent would demand one the gate can only answer `could_not_run` to — and
    the missing profile is already check_claims' finding, not this one's."""
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    _pdf(ws / "cv.pdf")
    assert check_apply.main(_argv(ws, root)) == 0
    assert capsys.readouterr().out.strip() == ""


def test_a_check_pages_receipt_that_could_not_run_does_not_satisfy_it(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    (ws / "tailored-profile.yaml").write_text("meta: {}\n", encoding="utf-8")
    _pdf(ws / "cv.pdf")
    journal.receipt(ws, "check_pages", {}, "could_not_run", ["MISSING_INPUT: cv.pdf"])
    assert check_apply.main(_argv(ws, root)) == 1
    assert "UPSTREAM_FAILED: check_pages verdict=could_not_run" in capsys.readouterr().out


def test_check_word_limits_is_required_once_a_supporting_statement_exists(
        tmp_path, capsys):
    """references/structured-applications.md routes all three judges away from the
    supporting statement, so check_word_limits is the ONLY reader of the artifact
    that is actually scored. It was not on the required list."""
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    (ws / "supporting-statement.md").write_text(
        "### Making Effective Decisions (250 words)\n\nI did a thing.\n", encoding="utf-8")
    assert check_apply.main(_argv(ws, root)) == 1
    out = capsys.readouterr().out
    assert "MISSING_RECEIPT: check_word_limits" in out
    assert "supporting-statement.md" in out


def test_a_structured_posting_with_no_statement_at_all_is_reported(tmp_path, capsys):
    """The scored artifact missing entirely must not be quieter than a long one."""
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    (ws / "posting.yaml").write_text("application_type: structured\n", encoding="utf-8")
    assert check_apply.main(_argv(ws, root)) == 1
    assert "MISSING_RECEIPT: check_word_limits" in capsys.readouterr().out


def test_an_ordinary_posting_does_not_demand_the_word_limit_gate(tmp_path, capsys):
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    (ws / "posting.yaml").write_text(
        "role_title: MR Reconstruction Engineer\napplication_type: standard\n",
        encoding="utf-8")
    assert check_apply.main(_argv(ws, root)) == 0
    assert capsys.readouterr().out.strip() == ""


def test_an_unparseable_posting_does_not_turn_into_a_word_limit_finding(
        tmp_path, capsys):
    """A broken posting.yaml still must not become a WORD-LIMIT demand: guessing
    "structured" from a file we could not read would fire on a run with no
    supporting statement anywhere in sight. That half is unchanged.

    What changed is the other half. This used to exit 0 in silence, and in the
    no-letter.yaml configuration — the normal shape of an NHS or Civil Service
    application — nothing else in apply mode reads posting.yaml, so one malformed
    character both removed the check_word_limits requirement and swallowed the
    reason. The file is now reported as unreadable, which is a different finding
    from the one this test exists to keep out.
    """
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    (ws / "posting.yaml").write_text("role_title: [unclosed\n", encoding="utf-8")
    assert check_apply.main(_argv(ws, root)) == 1
    out = capsys.readouterr().out
    assert any(line.startswith("UNREADABLE_POSTING") for line in out.splitlines())
    # The CODE, not a free substring: "check_word_limits" appears inside
    # UNREADABLE_POSTING's own explanation, and asserting on the bare word would
    # be satisfied by prose — the exact test-quality defect this audit found in
    # NO_PASS_NO_STOP's assertion.
    assert "MISSING_RECEIPT: check_word_limits" not in out, \
        "an unreadable posting must still not DEMAND the word-limit gate"


def test_the_conditional_gates_the_gate_can_demand_are_the_declared_ones(tmp_path):
    """conditional_gates() is what SKILL.md's self-check is pinned against, so a
    name it can return that is not in CONDITIONAL_GATES would be a required gate
    the checklist never mentions."""
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root)
    (ws / "letter.yaml").write_text("sender: {}\n", encoding="utf-8")
    (ws / "tailored-profile.yaml").write_text("meta: {}\n", encoding="utf-8")
    _pdf(ws / "cv.pdf")
    (ws / "supporting-statement.md").write_text("### A (250 words)\n\nx\n",
                                                encoding="utf-8")
    named = [g for g, _ in check_apply.conditional_gates(ws)]
    assert named == list(check_apply.CONDITIONAL_GATES)
    assert not set(check_apply.CONDITIONAL_GATES) & set(check_apply.REQUIRED_GATES)


# ── the honest stretch check_apply could never pass ──────────────────────────


def test_an_honest_stretch_reaches_exit_0_with_the_real_parser(tmp_path, capsys):
    """The whole honest-stop.yaml branch — validated four findings deep, and the
    reason that code exists — was unreachable: parse_verdicts wrote `fail` on any
    REJECT round and is in REQUIRED_GATES, so every stretch application failed the
    composer at the last step and was reported to the user as a failed review."""
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root, skip=("parse_verdicts",))
    assert _parse_round(ws, 1, ("PASS", "REJECT", "PASS")) == 1
    (ws / "honest-stop.yaml").write_text(yaml.safe_dump({
        "classification": "honest_stretch",
        "verdict": "stretch",
        "reason": ("The package is as strong as it can truthfully be; the only unmet "
                   "must-have is 5 years of clinical PACS integration."),
        "evidence": ["hiring_manager requirement_match: 3/5 — no clinical PACS work"],
    }, allow_unicode=True), encoding="utf-8")
    capsys.readouterr()
    assert check_apply.main(_argv(ws, root)) == 0
    assert capsys.readouterr().out.strip() == ""


def test_a_round_no_judge_actually_judged_still_cannot_reach_exit_0(tmp_path, capsys):
    """The fix that would have been wrong. Exempting parse_verdicts outright — or
    treating every non-PASS as "parsed fine" — lets a round where a judge emitted
    no usable VERDICT line exit 0 behind an honest-stop.yaml, which is a silent
    failure traded for a silent failure."""
    root = _skill_root(tmp_path)
    ws = _good_workspace(tmp_path, root, skip=("parse_verdicts",))
    assert _parse_round(ws, 1, ("PASS", "PASS (with reservations)", "PASS")) == 1
    (ws / "honest-stop.yaml").write_text(yaml.safe_dump({
        "classification": "honest_stretch", "verdict": "stretch",
        "reason": "x", "evidence": ["y"]}), encoding="utf-8")
    assert check_apply.main(_argv(ws, root)) == 1
    assert "UPSTREAM_FAILED: parse_verdicts" in capsys.readouterr().out


@pytest.mark.parametrize("gate", sorted(GATE_ARGS))
def test_no_gate_creates_a_workspace_it_was_pointed_at(gate, tmp_path, capsys):
    """journal.receipt() mkdirs, so before the guard existed a typo'd
    --workspace silently materialised an empty workspace and the
    resume-in-progress lookup then found a shell — measured on lint_cv, and
    true of every gate except check_apply. This is the whole set, held to the
    one rule; scripts/enter_mode.py is the only script allowed to create a
    workspace, because it opens the mode."""
    ws = tmp_path / "typo-workspace"
    mod = importlib.import_module(gate)
    assert mod.main(["--workspace", str(ws)] + GATE_ARGS[gate]) == 2
    assert "does not exist" in capsys.readouterr().err
    assert not ws.exists()
