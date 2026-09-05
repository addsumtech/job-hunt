import json

import yaml

import pytest

import check_evidence_refs as cer

BLOCKS = {"blocks": [{"id": "CV-001", "source": "cv", "text": "C++ reconstruction pipeline"},
                     {"id": "JD-001", "source": "jd", "text": "Five years of C++"}]}

CLEAN_YAML = {
    "market": "nl",
    "verdict": "worth_applying",
    "requirements": [
        {"id": "R1", "kind": "must_have", "text": "C++", "level": "required",
         "screening": "weighted", "match": "strong", "recency": "current",
         "effort": "quick", "evidence": [{"ref": "CV-001"}, {"ref": "JD-001"}]},
        {"id": "R2", "kind": "must_have", "text": "Kubernetes", "level": "required",
         "screening": "weighted", "match": "no_evidence", "recency": "undated",
         "effort": "multi_day", "evidence": []},
    ],
}

CLEAN_MD = (
    "# Fit assessment\n\n"
    "Your C++ reconstruction work lines up with the posting's C++ requirement.\n\n"
    "| Requirement | match | evidence |\n"
    "|---|---|---|\n"
    "| C++ | strong | CV-001, JD-001 |\n"
    "| Kubernetes | no_evidence | — |\n"
)


def _workspace(tmp_path, assessment=None, markdown=None, blocks=None):
    (tmp_path / "evidence-blocks.json").write_text(
        json.dumps(blocks or BLOCKS, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "fit-assessment.yaml").write_text(
        yaml.safe_dump(assessment or CLEAN_YAML, allow_unicode=True), encoding="utf-8")
    (tmp_path / "fit-assessment.md").write_text(
        markdown if markdown is not None else CLEAN_MD, encoding="utf-8")
    return tmp_path


# ---------- the quiet case, pinned as hard as the firing case ----------

def test_ordinary_assessment_passes_and_is_left_byte_identical(tmp_path, capsys):
    ws = _workspace(tmp_path)
    before_yaml = (ws / "fit-assessment.yaml").read_bytes()
    before_md = (ws / "fit-assessment.md").read_bytes()
    assert cer.main(["--workspace", str(ws)]) == 0
    assert (ws / "fit-assessment.yaml").read_bytes() == before_yaml
    assert (ws / "fit-assessment.md").read_bytes() == before_md
    out = capsys.readouterr().out
    assert "DROPPED_REF" not in out and "STRIPPED_ID" not in out


def test_ids_inside_a_markdown_table_row_are_never_stripped():
    cleaned, findings = cer.strip_block_ids("| C++ | strong | CV-001, JD-001 |\n")
    assert cleaned == "| C++ | strong | CV-001, JD-001 |\n"
    assert findings == []


def test_an_empty_evidence_list_is_not_a_finding():
    _, findings = cer.drop_unresolvable_refs(
        {"requirements": [{"id": "R2", "match": "no_evidence", "evidence": []}]},
        {"CV-001"})
    assert findings == []


def test_check_only_passes_on_the_clean_workspace(tmp_path):
    ws = _workspace(tmp_path)
    assert cer.main(["--workspace", str(ws), "--check-only"]) == 0


# ---------- the firing cases ----------

def test_an_invented_ref_is_dropped_and_listed(tmp_path, capsys):
    assessment = json.loads(json.dumps(CLEAN_YAML))
    assessment["requirements"][0]["evidence"].append({"ref": "CV-042"})
    ws = _workspace(tmp_path, assessment=assessment)
    assert cer.main(["--workspace", str(ws)]) == 0          # dropping is not a failure
    out = capsys.readouterr().out
    assert "DROPPED_REF: CV-042" in out
    rewritten = yaml.safe_load((ws / "fit-assessment.yaml").read_text(encoding="utf-8"))
    refs = [e["ref"] for e in rewritten["requirements"][0]["evidence"]]
    assert refs == ["CV-001", "JD-001"]


def test_check_only_fails_when_a_ref_would_be_dropped(tmp_path):
    assessment = json.loads(json.dumps(CLEAN_YAML))
    assessment["requirements"][0]["evidence"].append({"ref": "JD-999"})
    ws = _workspace(tmp_path, assessment=assessment)
    before = (ws / "fit-assessment.yaml").read_bytes()
    assert cer.main(["--workspace", str(ws), "--check-only"]) == 1
    assert (ws / "fit-assessment.yaml").read_bytes() == before   # check-only never writes


def test_a_block_id_in_prose_is_stripped_with_its_brackets():
    cleaned, findings = cer.strip_block_ids(
        "Your C++ port (CV-001) matches the posting (JD-001).\n")
    assert cleaned == "Your C++ port matches the posting.\n"
    assert len(findings) == 2
    assert findings[0].startswith("STRIPPED_ID: ")


def test_cjk_brackets_around_an_id_are_stripped_too():
    cleaned, _ = cer.strip_block_ids("你的 C++ 经历（CV-001）与岗位要求吻合。\n")
    assert cleaned == "你的 C++ 经历与岗位要求吻合。\n"


def test_zero_blocks_is_a_hard_failure(tmp_path, capsys):
    ws = _workspace(tmp_path, blocks={"blocks": []})
    assert cer.main(["--workspace", str(ws)]) == 1
    assert "NO_BLOCKS:" in capsys.readouterr().out


def test_missing_input_exits_two_and_still_leaves_exactly_one_receipt(tmp_path, capsys):
    # "Could not run" is the case where silence looks most like a clean run.
    assert cer.main(["--workspace", str(tmp_path)]) == 2
    assert "evidence-blocks.json" in capsys.readouterr().err
    receipts = [json.loads(line) for line in
                (tmp_path / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(receipts) == 1
    assert receipts[0]["gate"] == "check_evidence_refs"
    assert receipts[0]["verdict"] == "could_not_run"


def test_a_workspace_that_does_not_exist_writes_no_journal(tmp_path, capsys):
    missing = tmp_path / "nope"
    assert cer.main(["--workspace", str(missing)]) == 2
    assert not missing.exists()
    assert "does not exist" in capsys.readouterr().err


def test_a_receipt_is_written_exactly_once_and_says_recorded(tmp_path):
    ws = _workspace(tmp_path)
    cer.main(["--workspace", str(ws)])
    lines = (ws / "journal.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["gate"] == "check_evidence_refs"
    assert json.loads(lines[0])["verdict"] == "recorded"


def test_the_same_clean_state_never_produces_two_verdicts(tmp_path):
    # A clean run is a clean run. check_only or not, the receipt says "recorded";
    # two verdicts for one state is how a downstream PASSING_VERDICTS check starts
    # reading a success as a failure.
    ws = _workspace(tmp_path)
    cer.main(["--workspace", str(ws)])
    cer.main(["--workspace", str(ws), "--check-only"])
    verdicts = [json.loads(line)["verdict"] for line in
                (ws / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
    assert verdicts == ["recorded", "recorded"]


# ---------------------------------------------------------------------------
# `\b` does not exist between a CJK character and an ASCII letter — both are
# word characters to `re`. So `见CV-001显示` matched NOTHING while
# `see CV-001 here` matched, and internal block ids stayed in Chinese
# reader-facing prose with no STRIPPED_ID, in a skill whose default output
# language is Chinese.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", ["见CV-001显示", "参照CV-001。", "（CV-001）",
                                  "see CV-001 here", "CV-001", "[JD-004]"])
def test_a_block_id_is_found_whatever_sits_next_to_it(text):
    assert cer.REF_RE.findall(text), text


@pytest.mark.parametrize("text", ["MYCV-001x", "XCV-0012", "CV-0012", "ACV-001"])
def test_an_id_glued_to_other_ascii_is_not_a_reference(text):
    """The cry-wolf half: the boundary still has to hold on the ASCII side, or
    STRIPPED_ID starts firing on ordinary identifiers."""
    assert not cer.REF_RE.findall(text), text
