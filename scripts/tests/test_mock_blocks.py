import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import mock_blocks as MB

GOOD = """prose before the block is fine

MOCK-ASSESSMENT-V1
ROUND: 2
ROUND-TYPE: technical
MARKET: nl
FAMILY: ml-engineering
FINDING: tag=VAGUE-OUTCOME | ref=Q2 | quote=It went really well after that.
BAND: dimension=outcome | value=asserted | ref=Q2 | quote=It went really well after that.
COVERAGE: status=evidenced | must_have=MRI reconstruction | pipelines, clinical
SHAPE: status=rehearsed | round_name=technisch gesprek
END-MOCK-ASSESSMENT-V1

prose after is fine too
"""


def test_parses_a_well_formed_block():
    block = MB.parse_block(GOOD, MB.ASSESSMENT)
    assert block.header["ROUND"] == "2"
    assert block.header["FAMILY"] == "ml-engineering"
    assert [r.kind for r in block.records] == ["FINDING", "BAND", "COVERAGE", "SHAPE"]
    assert block.findings_none is False


def test_the_last_field_keeps_its_pipes():
    block = MB.parse_block(GOOD, MB.ASSESSMENT)
    coverage = [r for r in block.records if r.kind == "COVERAGE"][0]
    assert coverage.fields["must_have"] == "MRI reconstruction | pipelines, clinical"


def test_quote_field_keeps_its_pipes_too():
    text = GOOD.replace(
        "quote=It went really well after that.",
        "quote=we shipped it | then it broke | then we fixed it",
    )
    block = MB.parse_block(text, MB.ASSESSMENT)
    finding = [r for r in block.records if r.kind == "FINDING"][0]
    assert finding.fields["quote"] == "we shipped it | then it broke | then we fixed it"


def test_a_missing_sentinel_is_a_parse_error():
    with pytest.raises(MB.BlockParseError, match="exactly one start and one end"):
        MB.parse_block(GOOD.replace("END-MOCK-ASSESSMENT-V1", ""), MB.ASSESSMENT)


def test_two_blocks_of_the_same_kind_are_a_parse_error():
    with pytest.raises(MB.BlockParseError, match="exactly one start and one end"):
        MB.parse_block(GOOD + GOOD, MB.ASSESSMENT)


def test_an_unknown_record_key_is_a_parse_error():
    text = GOOD.replace("SHAPE: status=", "SHAPES: status=")
    with pytest.raises(MB.BlockParseError, match="unknown record"):
        MB.parse_block(text, MB.ASSESSMENT)


def test_a_missing_header_line_is_a_parse_error():
    text = GOOD.replace("MARKET: nl\n", "")
    with pytest.raises(MB.BlockParseError, match="missing header line"):
        MB.parse_block(text, MB.ASSESSMENT)


def test_a_record_with_the_wrong_field_order_is_a_parse_error():
    text = GOOD.replace(
        "FINDING: tag=VAGUE-OUTCOME | ref=Q2 |", "FINDING: ref=Q2 | tag=VAGUE-OUTCOME |"
    )
    with pytest.raises(MB.BlockParseError, match="expected field 'tag'"):
        MB.parse_block(text, MB.ASSESSMENT)


def test_a_record_missing_a_field_is_a_parse_error():
    text = GOOD.replace(" | quote=It went really well after that.", "", 1)
    with pytest.raises(MB.BlockParseError, match="must have fields"):
        MB.parse_block(text, MB.ASSESSMENT)


def test_findings_and_the_none_marker_together_are_a_parse_error():
    text = GOOD.replace("SHAPE: status=rehearsed | round_name=technisch gesprek",
                        "FINDINGS: none")
    with pytest.raises(MB.BlockParseError, match="never both and never neither"):
        MB.parse_block(text, MB.ASSESSMENT)


def test_neither_findings_nor_the_none_marker_is_a_parse_error():
    """Fail-closed: silence is not the same as 'nothing found'."""
    lines = [ln for ln in GOOD.splitlines() if not ln.startswith("FINDING:")]
    with pytest.raises(MB.BlockParseError, match="never both and never neither"):
        MB.parse_block("\n".join(lines), MB.ASSESSMENT)


def test_the_none_marker_alone_parses():
    text = "\n".join(
        ln for ln in GOOD.splitlines()
        if not ln.startswith(("FINDING:", "BAND:", "COVERAGE:", "SHAPE:"))
    ).replace("FAMILY: ml-engineering", "FAMILY: ml-engineering\nFINDINGS: none")
    block = MB.parse_block(text, MB.ASSESSMENT)
    assert block.findings_none is True
    assert block.records == ()


def test_the_provenance_block_refuses_assessment_records():
    text = """MOCK-PROVENANCE-V1
ROUND: 2
BAND: dimension=outcome | value=asserted | ref=Q2 | quote=whatever it was
END-MOCK-PROVENANCE-V1"""
    with pytest.raises(MB.BlockParseError, match="unknown record 'BAND'"):
        MB.parse_block(text, MB.PROVENANCE)


def test_quote_matching_ignores_wrapping_and_whitespace():
    transcript = "**Candidate:** It went\n  really well  after that."
    assert MB.quote_is_in('"It went really well after that."', transcript)


def test_quote_matching_tolerates_an_ellipsis():
    transcript = "I ran the benchmark myself on the department cluster last spring."
    assert MB.quote_is_in("I ran the benchmark ... on the department cluster", transcript)


def test_quote_matching_rejects_an_invented_quote():
    transcript = "I ran the benchmark myself on the department cluster."
    assert not MB.quote_is_in("I ran it on 200 patient scans", transcript)


def test_a_short_quote_still_matches():
    assert MB.quote_is_in("we did", "and then we did, eventually")
