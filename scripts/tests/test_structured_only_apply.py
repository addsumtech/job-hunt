"""Actual gate runs for explicitly confirmed, no-CV structured applications."""
import json
import pathlib
import sys
import pytest
import yaml
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import check_apply
import check_claims
import check_personal_data
import check_render_freshness
import check_word_limits
import enter_mode
import journal


def _write(path, value):
    path.write_text(yaml.safe_dump(value) if isinstance(value, (dict, list)) else value, encoding="utf-8")


def _fresh(ws, inputs=None):
    files = inputs or ["supporting-statement.md", "posting.yaml", "application-plan.yaml", "input.md"]
    args = ["--workspace", str(ws), "--round", "1"]
    assert check_render_freshness.main(args + ["--record"] + [str(ws / f) for f in files]) == 0
    assert check_render_freshness.main(args) == 0


def _workspace(tmp_path):
    ws = tmp_path / "structured"
    ws.mkdir()
    root = tmp_path / "skill"
    (root / "modes").mkdir(parents=True)
    _write(root / "modes" / "apply.md", "# Apply\n")
    assert enter_mode.main(["--workspace", str(ws), "--mode", "apply", "--skill-root", str(root), "--because", "Supporting statement requested"]) == 0
    p = {"meta": {"name": "Fictional Admin", "language": "en", "target_market": "uk"}, "contact": {"email": "admin@example.invalid"}, "skills": {"Tools": ["Excel"]}}
    for filename in ("profile.yaml", "tailored-profile.yaml"):
        _write(ws / filename, p)
    _write(ws / "claims.yaml", [])
    _write(ws / "posting.yaml", {"application_type": "structured", "must_haves": ["Excel"]})
    _write(ws / "input.md", "Submit a supporting statement only. No CV upload is accepted.\n")
    _write(ws / "application-plan.yaml", {"application_type": "structured", "cv_required": False, "source_ref": "input.md", "source_quote": "No CV upload is accepted."})
    _write(ws / "supporting-statement.md", "### Excel (100 words)\n\nI used Excel to maintain the appointment register.\n")
    _write(ws / "interview-brief.md", "Explain how you maintained the appointment register.\n")
    assert check_claims.main(["--workspace", str(ws), "--master", str(ws / "profile.yaml"), "--record"]) == 0
    for gate in (check_claims, check_personal_data, check_word_limits):
        assert gate.main(["--workspace", str(ws)]) == 0
    _fresh(ws)
    return ws, root


def _check(ws, root):
    return check_apply.main(["--workspace", str(ws), "--skill-root", str(root)])


def test_statement_only_actual_gates_pass_without_cv_judges(tmp_path, capsys):
    ws, root = _workspace(tmp_path)
    capsys.readouterr()
    assert _check(ws, root) == 0
    assert capsys.readouterr().out == ""
    receipt = journal.read_receipts(ws, "check_apply")[-1]
    for file in ("application-plan.yaml", "input.md"):
        assert receipt["input_hashes"][file] == journal.sha256_file(ws / file)
    assert not (ws / "cv.md").exists()
    assert not journal.read_receipts(ws, "parse_verdicts")


@pytest.mark.parametrize("state", ["missing_receipt", "failed", "stale", "missing_statement"])
def test_statement_gate_remains_mandatory(tmp_path, capsys, state):
    ws, root = _workspace(tmp_path)
    if state == "missing_receipt":
        rows = (ws / "journal.jsonl").read_text().splitlines()
        _write(ws / "journal.jsonl", "\n".join(r for r in rows if json.loads(r).get("gate") != "check_word_limits") + "\n")
    elif state == "failed":
        _write(ws / "supporting-statement.md", "### Excel (100 words)\n\n" + "word " * 101)
        assert check_word_limits.main(["--workspace", str(ws)]) == 1
        _fresh(ws)
    elif state == "stale":
        with (ws / "supporting-statement.md").open("a") as f: f.write("Changed after review.\n")
    else:
        (ws / "supporting-statement.md").unlink()
    capsys.readouterr()
    assert _check(ws, root) == 1
    expected = {"missing_receipt": "MISSING_RECEIPT: check_word_limits", "failed": "UPSTREAM_FAILED: check_word_limits", "stale": "STALE_RECEIPT: check_word_limits", "missing_statement": "RECEIPT_INPUT_MISSING"}
    assert expected[state] in capsys.readouterr().out


@pytest.mark.parametrize("ext", ["md", "docx", "pdf", "tex"])
def test_any_cv_artifact_restores_three_judge_requirement(tmp_path, capsys, ext):
    ws, root = _workspace(tmp_path)
    _write(ws / f"cv.{ext}", "CV artifact")
    capsys.readouterr()
    assert _check(ws, root) == 1
    output = capsys.readouterr().out
    assert "MISSING_RECEIPT: parse_verdicts" in output
    assert "MISSING_RECEIPT: lint_cv" in output


@pytest.mark.parametrize("change", ["missing_plan", "string_false", "unstructured", "uppercase_structured", "cv_required_true", "outside_source", "symlink_source", "missing_quote", "generated_source", "nul_source", "empty_source", "dot_source"])
def test_no_implicit_or_unsubstantiated_review_bypass(tmp_path, capsys, change):
    ws, root = _workspace(tmp_path)
    plan = yaml.safe_load((ws / "application-plan.yaml").read_text())
    if change == "missing_plan":
        (ws / "application-plan.yaml").unlink()
    elif change in ("unstructured", "uppercase_structured"):
        _write(ws / "posting.yaml", {"application_type": "cv" if change == "unstructured" else "STRUCTURED"})
    else:
        if change == "string_false": plan["cv_required"] = "false"
        elif change == "cv_required_true": plan["cv_required"] = True
        elif change == "outside_source": plan["source_ref"] = "../outside.txt"
        elif change == "symlink_source":
            outside = tmp_path / "outside.txt"
            _write(outside, "No CV upload is accepted.")
            (ws / "input.md").unlink()
            (ws / "input.md").symlink_to(outside)
        elif change == "missing_quote": plan["source_quote"] = "A quote never supplied."
        elif change == "generated_source": plan["source_ref"] = "interview-brief.md"
        elif change == "nul_source": plan["source_ref"] = "raw/bad\x00.txt"
        elif change == "empty_source": plan["source_ref"] = ""
        elif change == "dot_source": plan["source_ref"] = "."
        _write(ws / "application-plan.yaml", plan)
    capsys.readouterr()
    assert _check(ws, root) == 1
    assert "MISSING_RECEIPT: parse_verdicts" in capsys.readouterr().out


@pytest.mark.parametrize("file", ["application-plan.yaml", "input.md", "posting.yaml"])
def test_routing_inputs_cannot_change_after_review(tmp_path, capsys, file):
    ws, root = _workspace(tmp_path)
    assert _check(ws, root) == 0
    with (ws / file).open("a") as f: f.write("\n# changed after review\n")
    capsys.readouterr()
    assert _check(ws, root) == 1
    assert f"STALE_RECEIPT: check_render_freshness passed on {file}" in capsys.readouterr().out


def test_freshness_must_cover_statement_posting_and_routing_source(tmp_path, capsys):
    ws, root = _workspace(tmp_path)
    _fresh(ws, ["supporting-statement.md"])
    capsys.readouterr()
    assert _check(ws, root) == 1
    assert "STRUCTURED_INPUT_NOT_REVIEWED" in capsys.readouterr().out
