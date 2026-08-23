"""The three CLIs, composed, on a workspace built from the real 51job capture.

Unit tests prove each gate fires. This proves they compose: the wrapper's journal
record is the same record the gates read back, through the real command-line
interfaces rather than through Python imports.
"""
import json
import pathlib
import re
import subprocess
import sys

import discover_fixtures as fx

CJK = re.compile(r"[　-〿一-鿿＀-￯]")

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"


def run(script, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True, text=True)


def journal_records(workspace):
    return [json.loads(line) for line
            in (workspace / "journal.jsonl").read_text(
                encoding="utf-8").strip().splitlines()]


def test_the_whole_chain_passes_on_a_real_capture(tmp_path):
    workspace = fx.build_workspace(tmp_path)
    # Strip the pre-seeded gate receipts: this test exists to prove the real
    # Step 10 scripts write them, and seeding them would make that true by
    # construction — the failure mode this whole audit kept finding.
    fx.write_journal(workspace, fx.JOURNAL, gate_receipts=False)

    detail = workspace / "raw" / "51job-detail-173199597.json"
    classify = run("check_opencli_result.py",
                   "--workspace", str(workspace),
                   "--site", "51job", "--command", "detail",
                   "--exit-code", "0",
                   "--stdout-file", str(detail),
                   "--command-line",
                   "opencli 51job detail 173199597 --window background -f json")
    assert classify.returncode == 0, classify.stderr
    assert json.loads(classify.stdout)["classification"] == "ok"

    no_write = run("check_no_write.py", "--workspace", str(workspace), "--no-fetch")
    assert no_write.returncode == 0, no_write.stdout + no_write.stderr
    assert no_write.stdout == ""

    lint = run("lint_no_prediction.py", "--workspace", str(workspace))
    assert lint.returncode == 0, lint.stdout + lint.stderr
    assert lint.stdout == ""

    shortlist = run("check_shortlist.py", "--workspace", str(workspace))
    assert shortlist.returncode == 0, shortlist.stdout + shortlist.stderr
    assert shortlist.stdout == ""

    records = journal_records(workspace)
    assert sum(1 for r in records if r.get("action") == "adapter_call") == 3
    gates = [r for r in records if r.get("action") == "gate"]
    assert {g["gate"] for g in gates} == {
        "check_no_write", "lint_no_prediction", "check_shortlist"}
    assert all(g["verdict"] == "pass" for g in gates)


def test_skipping_a_step_10_gate_is_reported_not_silently_clean(tmp_path):
    """check_shortlist is the last gate in the mode, so it is the only thing that
    can report a sibling that never ran. Until it did, discover's two
    load-bearing invariants — read-only, and no predicted numbers — rested on
    scripts a run could simply not execute, leaving no trace either way."""
    workspace = fx.build_workspace(tmp_path)
    fx.write_journal(workspace, fx.JOURNAL, gate_receipts=False)

    shortlist = run("check_shortlist.py", "--workspace", str(workspace))
    assert shortlist.returncode == 1
    codes = {line.split(":", 1)[0] for line in shortlist.stdout.splitlines() if line}
    assert "MISSING_RECEIPT" in codes
    assert "check_no_write" in shortlist.stdout
    assert "lint_no_prediction" in shortlist.stdout


def test_a_hand_corrupted_source_id_is_caught_through_the_cli(tmp_path):
    workspace = fx.build_workspace(tmp_path)
    assert run("check_shortlist.py", "--workspace", str(workspace)).returncode == 0

    data = fx.load_shortlist(workspace)
    data["rows"][0]["source_id"] = "173190000"     # plausible, and not in raw/
    fx.save_shortlist(workspace, data)

    result = run("check_shortlist.py", "--workspace", str(workspace))
    assert result.returncode == 1
    assert result.stdout.startswith("SOURCE_ID_NOT_IN_RAW:")
    assert "51job-1.json" in result.stdout

    receipt = journal_records(workspace)[-1]
    assert receipt["gate"] == "check_shortlist"
    assert receipt["verdict"] == "fail"


def test_an_english_shortlist_passes_the_whole_chain(tmp_path):
    """The acceptance test for a monolingual English round (spec §10: the
    shortlist follows the USER's language, not the market's).

    Not a unit test of two constants: an English capture, English rows and an
    English shortlist.md, through the real command lines, with the document
    asserted to contain no CJK at all. Before the literals were paired, this
    document's only options were a gate failure or a Chinese sentence stapled
    into an English page — and the second one gated green, which is worse,
    because it reads to the user as a bug and no check reports it.
    """
    workspace = fx.build_english_workspace(tmp_path)

    no_write = run("check_no_write.py", "--workspace", str(workspace), "--no-fetch")
    assert no_write.returncode == 0, no_write.stdout + no_write.stderr

    shortlist = run("check_shortlist.py", "--workspace", str(workspace))
    assert shortlist.returncode == 0, shortlist.stdout + shortlist.stderr
    assert shortlist.stdout == ""

    body = (workspace / "shortlist.md").read_text(encoding="utf-8")
    found = CJK.findall(body)
    assert not found, f"Chinese scaffolding in an English shortlist: {found}"

    receipt = journal_records(workspace)[-1]
    assert receipt["gate"] == "check_shortlist"
    assert receipt["verdict"] == "pass"


def test_an_english_degraded_run_passes_with_an_english_disclosure_block(tmp_path):
    workspace = fx.build_english_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"] = []
    data["sources"] = []
    data["shortfall_reason"] = (
        "No adapter returned a usable row this round; see the disclosure in §0.2.")
    fx.save_shortlist(workspace, data)
    fx.write_journal(workspace, [dict(fx.JOURNAL_EN[0], exit_code=1,
                                      classification="not_logged_in", row_count=0,
                                      auth_state="not_logged_in",
                                      error_message="HTTP 403 Forbidden")])
    fx.write_md(workspace, fx.DISCLOSURE_MD_EN)

    result = run("check_shortlist.py", "--workspace", str(workspace))
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""
    found = CJK.findall(fx.DISCLOSURE_MD_EN)
    assert not found, f"Chinese scaffolding in an English disclosure: {found}"


def test_a_blanked_english_disclosure_answer_is_caught_like_the_chinese_one(tmp_path):
    # The backstop the pairing must not lose. The answers ship pre-filled as
    # no/否 so that concealing a retry is an active overwrite, not an omission —
    # if only the Chinese spellings were checked for a filled-in answer, the
    # English half would ship without the one thing the block is for.
    workspace = fx.build_english_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"] = []
    data["sources"] = []
    data["shortfall_reason"] = "No adapter returned a usable row this round."
    fx.save_shortlist(workspace, data)
    fx.write_journal(workspace, [dict(fx.JOURNAL_EN[0], exit_code=1,
                                      classification="not_logged_in", row_count=0)])
    label = "Bypassed any platform control:"
    fx.write_md(workspace, "\n".join(
        label if label in line else line
        for line in fx.DISCLOSURE_MD_EN.splitlines()))

    result = run("check_shortlist.py", "--workspace", str(workspace))
    assert result.returncode == 1
    assert "DISCLOSURE_INCOMPLETE" in result.stdout
    assert "active overwrite" in result.stdout


def test_a_hand_added_fabricated_row_is_caught_through_the_cli(tmp_path):
    # The failure this whole mode exists to prevent: a plausible row nobody
    # retrieved, with every field the right shape.
    workspace = fx.build_workspace(tmp_path)
    data = fx.load_shortlist(workspace)
    data["rows"].append({
        "id": "51job-173200001",
        "title": "资深计算机视觉算法工程师",
        "company": "某知名半导体设备公司",
        "location": "上海",
        "salary": "4-7万",
        "url": "https://jobs.51job.com/shanghai/173200001.html",
        "source_site": "51job",
        "source_id": "173200001",
        "extraction_method": "adapter_search",
        "retrieved_at": "2026-08-09T14:02:11Z",
        "quality": "card_only",
        "verification": "collected_unverified",
        "raw_text": "资深计算机视觉算法工程师 | 上海 | 4-7万",
        "why_matched": "标题与 brief.target_titles 高度一致",
        "verdict": "strong_apply",
        "provisional": True,
        "effort": "quick",
    })
    fx.save_shortlist(workspace, data)

    result = run("check_shortlist.py", "--workspace", str(workspace))
    assert result.returncode == 1
    codes = {line.split(":", 1)[0] for line in result.stdout.strip().splitlines()}
    assert "SOURCE_ID_NOT_IN_RAW" in codes
    assert "URL_NOT_FROM_ADAPTER" in codes
