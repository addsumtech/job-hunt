import ast
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import journal

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent


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


# ── the verdict vocabulary is closed, and nothing but this pins it ───────────


def test_the_receipt_docstring_names_every_verdict_and_no_others():
    """The docstring IS the spec a gate author reads. It listed four verdicts while
    the code used four spellings for five meanings, and the two that shared a
    spelling — setup vs. a clean check — were the pair check_apply.py had to tell
    apart. A prose list nothing compares against drifts silently."""
    doc = journal.receipt.__doc__
    for verdict in journal.VERDICTS:
        assert f'"{verdict}"' in doc, f"receipt()'s docstring never names {verdict!r}"
    quoted = set(re.findall(r'"([a-z_]+)"', doc.split("`mode`")[0]))
    assert quoted == set(journal.VERDICTS), (
        f"receipt()'s docstring documents {sorted(quoted)} but journal.VERDICTS is "
        f"{sorted(journal.VERDICTS)} — a verdict named in only one of the two is a "
        f"verdict some gate will invent and some composer will misread")


def _receipt_verdict_literals(path):
    """Every string constant a file passes as journal.receipt()'s `verdict`.

    An expression (`"fail" if findings else "pass"`) yields both of its branches,
    which is exactly the shape most gates use. A verdict computed elsewhere yields
    nothing and is simply not covered — this is a lint, not a proof.

    Only the VALUE positions are read. `ast.walk` over the whole subtree would also
    pick up the string in the condition — `"fail" if combined == "AMBIGUOUS" else
    …` — and report a verdict nobody writes, which is the kind of false finding
    that gets a check deleted.
    """
    def values(node):
        if isinstance(node, ast.IfExp):
            return values(node.body) + values(node.orelse)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return [node.value]
        return []

    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr == "receipt"
                and isinstance(fn.value, ast.Name) and fn.value.id == "journal"):
            continue
        arg = None
        for kw in node.keywords:
            if kw.arg == "verdict":
                arg = kw.value
        if arg is None and len(node.args) >= 4:
            arg = node.args[3]
        if arg is None:
            continue
        out += values(arg)
    return out


def test_no_gate_writes_a_verdict_outside_the_vocabulary():
    """A gate that invents a fifth spelling of "fine" is read by every composer as
    a failure — or, worse, added to a PASSING_VERDICTS tuple to make the red go
    away, which is how "recorded" came to mean two different things. Deterministic,
    because prose asking nicely is what did not work."""
    seen = 0
    for path in sorted(SCRIPTS.glob("*.py")):
        for verdict in _receipt_verdict_literals(path):
            seen += 1
            assert verdict in journal.VERDICTS, (
                f"{path.name} passes journal.receipt() the verdict {verdict!r}, which "
                f"is not in journal.VERDICTS {journal.VERDICTS}")
    assert seen >= 20, (
        f"only {seen} verdict literals found across scripts/ — the AST walk stopped "
        f"matching the call shape, so this lint is passing by looking at nothing")
