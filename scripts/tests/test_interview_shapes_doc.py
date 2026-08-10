import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import mock_vocab as V
import vocab

ROOT = pathlib.Path(__file__).resolve().parents[2]
DOC = ROOT / "references" / "interview-shapes.md"

# `[U]` — "could not source" — is one of the four labels the doc's own label table
# defines, and the Germany table uses it to say out loud that a round count could not
# be established. Excluding it from the regex would push the doc to drop the honest
# row rather than keep it.
LABEL = re.compile(r"^\[(F|C|S|U)\]$")


def _section(heading: str) -> str:
    """The text under an H2 heading, up to the next H2."""
    text = DOC.read_text(encoding="utf-8")
    marks = [m for m in re.finditer(r"^## (.+)$", text, re.M)]
    for i, m in enumerate(marks):
        if m.group(1).strip() == heading:
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            return text[m.end():end]
    raise AssertionError(f"references/interview-shapes.md has no '## {heading}' section")


def _table_rows(section: str) -> list[list[str]]:
    rows = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells):   # separator row
            continue
        rows.append(cells)
    return rows


def _first_col_tokens(heading: str) -> set[str]:
    rows = _table_rows(_section(heading))
    return {r[0].strip("`") for r in rows[1:]}          # skip the header row


def test_defect_tag_table_matches_the_module():
    assert _first_col_tokens("Defect tags (closed set)") == set(V.DEFECT_TAGS)


def test_answer_shape_tag_table_matches_the_module():
    assert _first_col_tokens("Answer-shape tags (closed set)") == set(V.SHAPE_TAGS)


def test_band_table_matches_the_module():
    assert _first_col_tokens("The four bands") == set(V.BANDS)


def test_the_ceiling_is_stated_in_words():
    # The doc sets the band name in backticks; assert the text as it is written
    # rather than a de-marked-up paraphrase of it.
    section = _section("The four bands")
    assert "`held_under_probe` is the ceiling" in section
    assert "not numbered" in section


def test_the_flag_is_not_presented_as_a_band():
    assert V.NON_BAND_FLAG not in _first_col_tokens("The four bands")
    assert V.NON_BAND_FLAG in _section("The four bands")   # it is still explained there


def _shape_rows(heading: str) -> list[list[str]]:
    """Every data row of every table under an H2, across its H3 sub-tables.

    'Market shapes' holds five per-country sub-tables, so the header row cannot be
    dropped by slicing `rows[1:]` once — each sub-table contributes its own. Drop
    them by name instead.
    """
    return [r for r in _table_rows(_section(heading)) if r[0].strip("`") != "Source"]


def test_every_shape_row_carries_a_source_label():
    for heading in ("Market shapes", "Role-family shapes"):
        rows = _shape_rows(heading)
        assert rows, f"{heading} has no table"
        for cells in rows:
            assert LABEL.match(cells[0].strip("`")), (
                f"{heading}: row {cells!r} does not start with a "
                "[F]/[C]/[S]/[U] source label"
            )


def test_both_shape_tables_are_actually_populated():
    """Guard on the guard: `_shape_rows` drops rows by name, so a typo in the header
    cell would silently empty the table and make the label test vacuous."""
    assert len(_shape_rows("Market shapes")) >= 25
    assert len(_shape_rows("Role-family shapes")) >= 8


def test_search_summary_material_is_barred_from_verbatim_questions():
    """Spec §10: only material that was actually read may be quoted at the candidate."""
    section = _section("Verbatim question material")
    for line in section.splitlines():
        item = line.strip().lstrip("-*").strip().strip("`")
        assert not item.startswith(("[S]", "[U]")), (
            f"a [S]/[U] item reached the verbatim-question section: {line!r}"
        )
    labels = _section("How to read the source labels")
    assert "may set round count, order, and ritual names" in labels
    assert "never be quoted" in labels


def test_the_reference_points_at_its_neighbours_rather_than_copying_them():
    text = DOC.read_text(encoding="utf-8")
    assert "references/role-families.md" in text
    assert "references/interview-prep.md" in text


def test_the_market_tuple_is_a_documented_superset_not_a_second_definition():
    """One flat scripts/ namespace: `MARKET_KEYS` belongs to vocab.py and to nothing
    else. mock_vocab extends it by exactly one token, and says which."""
    assert not hasattr(V, "MARKET_KEYS")
    assert V.MOCK_MARKET_KEYS == vocab.MARKET_KEYS + (vocab.NO_MARKET,)
    assert V.DEFECT_TAGS is vocab.DEFECT_TAGS
    assert V.BANDS is vocab.BANDS
    assert V.NON_BAND_FLAG == vocab.CONTRADICTED
