import ast
import json
import os
import pathlib
import re
import sys

import pytest

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


# ------------------------------------------------------------------- load_yaml

def test_a_good_mapping_loads(tmp_path):
    p = tmp_path / "posting.yaml"
    p.write_text("role_title: MR engineer\nmust_haves: [C++]\n", encoding="utf-8")
    assert journal.load_yaml(p) == {"role_title": "MR engineer", "must_haves": ["C++"]}


def test_an_empty_file_is_the_empty_mapping_not_none(tmp_path):
    """`yaml.safe_load("") or {}` is the idiom every call site used, and every caller
    downstream indexes the result. Returning None here would move the crash one line."""
    p = tmp_path / "posting.yaml"
    p.write_text("", encoding="utf-8")
    assert journal.load_yaml(p) == {}


def test_a_comment_only_file_is_the_empty_mapping(tmp_path):
    p = tmp_path / "posting.yaml"
    p.write_text("# nothing here yet\n", encoding="utf-8")
    assert journal.load_yaml(p) == {}


def test_an_empty_file_expecting_a_list_is_the_empty_list(tmp_path):
    p = tmp_path / "claims.yaml"
    p.write_text("\n", encoding="utf-8")
    assert journal.load_yaml(p, expect=list) == []


def test_a_good_list_loads_when_a_list_is_expected(tmp_path):
    p = tmp_path / "claims.yaml"
    p.write_text("- term: GPU batching\n", encoding="utf-8")
    assert journal.load_yaml(p, expect=list) == [{"term": "GPU batching"}]


def test_an_unparseable_document_raises_and_names_the_file(tmp_path):
    p = tmp_path / "fit-assessment.yaml"
    p.write_text('verdict: "unclosed\neffort: quick\n', encoding="utf-8")
    with pytest.raises(journal.YamlUnreadable) as caught:
        journal.load_yaml(p)
    assert str(p) in str(caught.value)
    assert "parse" in str(caught.value)


def test_a_top_level_list_where_a_mapping_is_expected_raises(tmp_path):
    """`.get()` on a list raises AttributeError, which lands in exactly the same
    place as a parse traceback: exit 1 and no receipt."""
    p = tmp_path / "fit-assessment.yaml"
    p.write_text("- verdict: strong_apply\n", encoding="utf-8")
    with pytest.raises(journal.YamlUnreadable) as caught:
        journal.load_yaml(p)
    assert "list" in str(caught.value) and "mapping" in str(caught.value)


def test_a_top_level_string_where_a_mapping_is_expected_raises(tmp_path):
    p = tmp_path / "fit-assessment.yaml"
    p.write_text("just a sentence\n", encoding="utf-8")
    with pytest.raises(journal.YamlUnreadable) as caught:
        journal.load_yaml(p)
    assert "str" in str(caught.value) and "mapping" in str(caught.value)


def test_a_top_level_mapping_where_a_list_is_expected_raises(tmp_path):
    p = tmp_path / "claims.yaml"
    p.write_text("term: GPU batching\n", encoding="utf-8")
    with pytest.raises(journal.YamlUnreadable) as caught:
        journal.load_yaml(p, expect=list)
    assert "dict" in str(caught.value) and "list" in str(caught.value)


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                    reason="chmod 000 does not stop root")
def test_an_unreadable_file_raises_rather_than_escaping_as_an_oserror(tmp_path):
    p = tmp_path / "fit-assessment.yaml"
    p.write_text("verdict: worth_applying\n", encoding="utf-8")
    p.chmod(0o000)
    try:
        with pytest.raises(journal.YamlUnreadable) as caught:
            journal.load_yaml(p)
    finally:
        p.chmod(0o644)
    assert str(p) in str(caught.value)


def test_a_file_that_is_not_utf8_raises(tmp_path):
    p = tmp_path / "posting.yaml"
    p.write_bytes(b"role_title: caf\xe9\n")
    with pytest.raises(journal.YamlUnreadable) as caught:
        journal.load_yaml(p)
    assert "UTF-8" in str(caught.value)


def test_the_finding_carries_a_stable_code_that_is_not_no_input(tmp_path):
    """NO_INPUT means the file is absent; this file is present and unusable. A reader
    told NO_INPUT goes looking for a file that is right there."""
    p = tmp_path / "fit-assessment.yaml"
    p.write_text("- a\n", encoding="utf-8")
    try:
        journal.load_yaml(p)
    except journal.YamlUnreadable as exc:
        assert exc.finding.startswith("UNREADABLE_INPUT: ")
        assert "fit-assessment.yaml" in exc.finding
    else:
        raise AssertionError("expected YamlUnreadable")


def test_a_missing_file_also_raises_rather_than_crashing(tmp_path):
    """Most callers check existence first and report NO_INPUT. The ones that do not
    must still land in the could-not-run path rather than on a FileNotFoundError."""
    with pytest.raises(journal.YamlUnreadable):
        journal.load_yaml(tmp_path / "not-here.yaml")


def test_expect_only_takes_dict_or_list(tmp_path):
    """A programmer error, raised as one. Silently accepting `expect=str` would make
    every value pass the shape check and the guard would be gone with no red anywhere."""
    p = tmp_path / "a.yaml"
    p.write_text("a: 1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        journal.load_yaml(p, expect=str)


def test_no_script_calls_yaml_safe_load_on_a_file_it_read_itself():
    """The lint that keeps the 25th call site from coming back.

    `yaml.safe_load(path.read_text(...))` is the exact shape that produced the
    reproduction in journal.load_yaml's docstring: a parse error escapes as a
    traceback, the gate exits 1 — which in this contract means "ran, found problems"
    — and no receipt is written at all. Two call sites parse a STRING that came from
    a subprocess rather than a file; those are listed by name below, because an
    exemption nobody can see is an exemption that grows."""
    text_parse_only = {"check_opencli_result.py", "opencli_meta.py"}
    offenders = []
    for path in sorted(SCRIPTS.glob("*.py")):
        # journal.py IS load_yaml — it is the one place the raw call is correct, and
        # its docstring quotes the broken idiom so a future reader can recognise it.
        if path.name == "journal.py" or path.name in text_parse_only:
            continue
        for match in re.finditer(r"safe_load\(([^\n]*)", path.read_text(encoding="utf-8")):
            if "read_text" in match.group(1) or "open(" in match.group(1):
                offenders.append(f"{path.name}: safe_load({match.group(1)[:50]}")
    assert not offenders, (
        "these read a file and parse it inline instead of using journal.load_yaml, so "
        "a malformed file exits 1 with no receipt:\n  " + "\n  ".join(offenders))
