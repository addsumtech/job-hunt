import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import check_render_freshness as crf
import journal
import rounds


def _ws(tmp_path):
    ws = tmp_path / "acme-engineer-2026-08-09"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "cv.md").write_text("# Test User\n\n## Experience\n", encoding="utf-8")
    (ws / "letter.md").write_text("Dear Hiring Team,\n", encoding="utf-8")
    return ws


def test_record_then_verify_unchanged_is_quiet(tmp_path, capsys):
    ws = _ws(tmp_path)
    assert crf.main(["--workspace", str(ws), "--round", "1",
                     "--record", str(ws / "cv.md"), str(ws / "letter.md")]) == 0
    capsys.readouterr()
    assert crf.main(["--workspace", str(ws), "--round", "1"]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_record_writes_the_hashes_into_the_round_file(tmp_path):
    ws = _ws(tmp_path)
    crf.main(["--workspace", str(ws), "--round", "2", "--record", str(ws / "cv.md")])
    dispatch = rounds.load_round(ws, 2)["dispatch"]
    assert dispatch["input_hashes"]["cv.md"] == journal.sha256_file(ws / "cv.md")
    assert dispatch["ts"].endswith("Z")


def test_an_edited_file_voids_the_round(tmp_path, capsys):
    ws = _ws(tmp_path)
    crf.main(["--workspace", str(ws), "--round", "1", "--record", str(ws / "cv.md")])
    capsys.readouterr()
    (ws / "cv.md").write_text("# Test User\n\n## Skills\n", encoding="utf-8")
    assert crf.main(["--workspace", str(ws), "--round", "1"]) == 1
    out = capsys.readouterr().out
    assert out.startswith("STALE: cv.md")
    assert "this round is void" in out


def test_a_deleted_file_is_reported_not_ignored(tmp_path, capsys):
    ws = _ws(tmp_path)
    crf.main(["--workspace", str(ws), "--round", "1", "--record", str(ws / "letter.md")])
    capsys.readouterr()
    (ws / "letter.md").unlink()
    assert crf.main(["--workspace", str(ws), "--round", "1"]) == 1
    assert "MISSING_FILE: letter.md" in capsys.readouterr().out


def test_verifying_a_round_that_was_never_recorded_is_exit_2(tmp_path, capsys):
    """Not a pass: an unrecorded round is one nobody can vouch for."""
    ws = _ws(tmp_path)
    assert crf.main(["--workspace", str(ws), "--round", "1"]) == 2
    assert "NO_DISPATCH_RECORD" in capsys.readouterr().err


def test_recording_a_file_that_does_not_exist_is_exit_2(tmp_path, capsys):
    ws = _ws(tmp_path)
    assert crf.main(["--workspace", str(ws), "--round", "1",
                     "--record", str(ws / "nope.md")]) == 2
    assert "nope.md" in capsys.readouterr().err


def test_recording_does_not_clobber_the_verdicts(tmp_path):
    ws = _ws(tmp_path)
    rounds.merge_round(ws, 1, {"combined_verdict": "PASS"})
    crf.main(["--workspace", str(ws), "--round", "1", "--record", str(ws / "cv.md")])
    assert rounds.load_round(ws, 1)["combined_verdict"] == "PASS"


def test_each_run_leaves_exactly_one_receipt_including_the_exit_2_paths(tmp_path):
    """An exit-2 run must leave a receipt too: 'the gate could not run' and
    'the gate was never run' produce the same silence otherwise."""
    ws = _ws(tmp_path)
    crf.main(["--workspace", str(ws), "--round", "1", "--record", str(ws / "cv.md")])
    crf.main(["--workspace", str(ws), "--round", "1"])
    crf.main(["--workspace", str(ws), "--round", "9"])                     # never recorded
    crf.main(["--workspace", str(ws), "--round", "3", "--record", str(ws / "nope.md")])
    verdicts = [r["verdict"] for r in journal.read_receipts(ws, "check_render_freshness")]
    assert verdicts == ["recorded", "pass", "could_not_run", "could_not_run"]
