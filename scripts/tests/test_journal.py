import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import journal


def test_append_creates_the_file_and_appends_one_line_per_record(tmp_path):
    ws = tmp_path / "acme-engineer-2026-08-09"
    journal.append(ws, {"a": 1})
    journal.append(ws, {"a": 2})
    lines = (ws / "journal.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(x)["a"] for x in lines] == [1, 2]


def test_sha256_file_matches_hashlib(tmp_path):
    import hashlib
    p = tmp_path / "cv.md"
    p.write_bytes(b"# Test User\n")
    assert journal.sha256_file(p) == hashlib.sha256(b"# Test User\n").hexdigest()


def test_receipt_has_the_contract_fields_and_lands_in_the_journal(tmp_path):
    ws = tmp_path / "ws"
    rec = journal.receipt(ws, "check_claims", {"tailored-profile.yaml": "ab" * 32},
                          "pass", ["UNSOURCED: nothing"])
    assert set(rec) == {"ts", "mode", "action", "gate", "input_hashes",
                        "verdict", "findings", "receipt_hash"}
    assert rec["action"] == "gate"
    assert rec["gate"] == "check_claims"
    assert rec["verdict"] == "pass"
    assert rec["findings"] == ["UNSOURCED: nothing"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", rec["ts"])
    assert re.fullmatch(r"[0-9a-f]{64}", rec["receipt_hash"])
    on_disk = json.loads((ws / "journal.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert on_disk == rec


def test_receipt_hash_covers_the_other_fields(tmp_path):
    a = journal.receipt(tmp_path / "a", "g", {}, "pass")
    b = journal.receipt(tmp_path / "b", "g", {}, "fail")
    assert a["receipt_hash"] != b["receipt_hash"]


def test_findings_defaults_to_an_empty_list_not_none(tmp_path):
    rec = journal.receipt(tmp_path / "ws", "g", {}, "pass")
    assert rec["findings"] == []


def test_read_receipts_filters_by_gate_and_ignores_non_gate_records(tmp_path):
    ws = tmp_path / "ws"
    journal.receipt(ws, "lint_cv", {}, "pass")
    journal.receipt(ws, "check_claims", {}, "fail")
    journal.append(ws, {"action": "mode_entry", "mode": "apply"})
    assert [r["gate"] for r in journal.read_receipts(ws)] == ["lint_cv", "check_claims"]
    assert [r["verdict"] for r in journal.read_receipts(ws, "check_claims")] == ["fail"]


def test_read_receipts_survives_a_half_written_line(tmp_path):
    """A truncated line must not blind the reader — the whole point of the
    journal is that a later gate can see whether an earlier one ran."""
    ws = tmp_path / "ws"
    journal.receipt(ws, "lint_cv", {}, "pass")
    with open(ws / "journal.jsonl", "a", encoding="utf-8") as fh:
        fh.write('{"action": "gate", "ga\n')
    journal.receipt(ws, "check_claims", {}, "pass")
    assert [r["gate"] for r in journal.read_receipts(ws)] == ["lint_cv", "check_claims"]


def test_read_receipts_on_a_workspace_with_no_journal_is_empty(tmp_path):
    assert journal.read_receipts(tmp_path / "never-used") == []


def test_the_receipt_mode_comes_from_the_latest_mode_entry_not_a_default(tmp_path):
    """`mode` is read from the journal, not guessed. An environment-variable
    default of "apply" is worse than "unknown": nothing in any mode sets the
    variable, so every receipt written by discover, assess and interview would
    be stamped `apply` and a journal read months later would lie confidently."""
    ws = tmp_path / "ws"
    assert journal.current_mode(ws) == "unknown"
    assert journal.receipt(ws, "g", {}, "pass")["mode"] == "unknown"
    journal.append(ws, {"action": "mode_entry", "mode": "discover"})
    assert journal.current_mode(ws) == "discover"
    assert journal.receipt(ws, "g", {}, "pass")["mode"] == "discover"
    journal.append(ws, {"action": "mode_entry", "mode": "apply"})
    assert journal.receipt(ws, "g", {}, "pass")["mode"] == "apply"
