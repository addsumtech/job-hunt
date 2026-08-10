import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import mock_blocks as MB
import mock_vocab as V

ROOT = pathlib.Path(__file__).resolve().parents[2]
PASS1 = ROOT / "agents" / "mock-assessor-transcript.md"
PASS2 = ROOT / "agents" / "mock-assessor-provenance.md"


def _example(path: pathlib.Path, kind: str) -> str:
    """The fenced example block under '## Example output block'."""
    text = path.read_text(encoding="utf-8")
    after = text.split("## Example output block", 1)
    assert len(after) == 2, f"{path.name} has no '## Example output block' section"
    fenced = re.findall(r"```\n(.*?)```", after[1], re.S)
    assert fenced, f"{path.name}: the example section has no fenced block"
    for candidate in fenced:
        if kind in candidate:
            return candidate
    raise AssertionError(f"{path.name}: no fenced example containing {kind}")


def test_pass1_example_block_parses():
    block = MB.parse_block(_example(PASS1, MB.ASSESSMENT), MB.ASSESSMENT)
    assert block.header["ROUND-TYPE"] in V.ROUND_TYPES
    assert block.header["MARKET"] in V.MOCK_MARKET_KEYS


def test_pass2_example_block_parses():
    block = MB.parse_block(_example(PASS2, MB.PROVENANCE), MB.PROVENANCE)
    assert block.header["ROUND"].isdigit()


def test_pass1_example_uses_only_tags_pass1_may_emit():
    block = MB.parse_block(_example(PASS1, MB.ASSESSMENT), MB.ASSESSMENT)
    for record in block.records:
        if record.kind == "FINDING":
            assert record.fields["tag"] in V.TRANSCRIPT_TAGS


def test_pass2_example_uses_only_tags_pass2_may_emit():
    block = MB.parse_block(_example(PASS2, MB.PROVENANCE), MB.PROVENANCE)
    for record in block.records:
        if record.kind == "FINDING":
            assert record.fields["tag"] in V.PROVENANCE_TAGS


def test_every_example_record_carries_a_quote():
    for path, kind in ((PASS1, MB.ASSESSMENT), (PASS2, MB.PROVENANCE)):
        block = MB.parse_block(_example(path, kind), kind)
        for record in block.records:
            if record.kind in ("FINDING", "BAND"):
                assert MB.normalize_quote(record.fields["quote"]), (
                    f"{path.name}: {record.kind} on line {record.line_no} has no quote"
                )


@pytest.mark.parametrize(
    "path, must_not_see",
    [(PASS1, ("interview-brief.md", "claims.yaml")), (PASS2, ("rubric",))],
)
def test_each_agent_states_what_it_is_not_given(path, must_not_see):
    text = path.read_text(encoding="utf-8")
    assert "## What you are deliberately NOT given, and why" in text
    section = text.split("## What you are deliberately NOT given, and why", 1)[1]
    section = section.split("\n## ", 1)[0]
    for item in must_not_see:
        assert item in section, f"{path.name} does not name {item!r} as withheld"


def test_pass1_is_told_it_may_not_emit_the_provenance_tags():
    text = PASS1.read_text(encoding="utf-8")
    for tag in V.PROVENANCE_TAGS:
        assert tag in text
    assert "WRONG_PASS" in text


def test_neither_agent_is_allowed_to_number_the_bands():
    for path in (PASS1, PASS2):
        text = path.read_text(encoding="utf-8")
        assert "do not average" in text.lower() or "cannot be averaged" in text.lower()
