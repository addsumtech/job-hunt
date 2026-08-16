"""The mode file is layer 1.5: loaded unconditionally on entering assess.

`modes/assess.md` §6 claimed "this schema is defined here and nowhere else" while
defining only the `requirements` rows. Three scripts read TOP-LEVEL fields that the
file named nowhere, so a faithful run wrote an assessment without them and
count_coverage.py invented the two the card prints. Two more —
`declared_work_status` and `stated_conditions` — appeared in no mode file at all,
which made both work-authorization notices unreachable on any real run: dead code
guarding a live question.

These assertions are the pairing that makes §6's sentence true. The gate requires
what the file defines; this is what requires the file to define what the gate reads.
Deriving the field list from the scripts rather than typing it out is deliberate —
a hand-written list is one more copy to drift, and the drift is silent in exactly
the direction this file exists to stop.
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import vocab

REPO = pathlib.Path(__file__).resolve().parents[2]
MODE = REPO / "modes" / "assess.md"
SCRIPTS = REPO / "scripts"

# Every top-level read of the assessment mapping, anywhere in scripts/.
_TOP_LEVEL_READ = re.compile(r'assessment\.get\(\s*"([a-z_]+)"')


def text():
    return MODE.read_text(encoding="utf-8")


def fields_the_scripts_read() -> set[str]:
    found: set[str] = set()
    for script in sorted(SCRIPTS.glob("*.py")):
        found |= set(_TOP_LEVEL_READ.findall(script.read_text(encoding="utf-8")))
    return found


def test_the_scan_actually_finds_something():
    """A regex that silently matches nothing passes every assertion below and
    proves the button exists rather than that pressing it does anything."""
    found = fields_the_scripts_read()
    assert {"verdict", "effort", "level_direction", "requirements"} <= found
    assert len(found) >= 9


def test_every_top_level_field_a_script_reads_is_defined_here():
    body = text()
    for field in sorted(fields_the_scripts_read()):
        assert f"{field}:" in body, (
            f"top-level field {field!r} is read by a script and defined in no mode "
            f"file — the model is never told to write it")


def test_every_value_of_every_top_level_enum_is_listed_here():
    body = text()
    for name in ("LEVEL_DIRECTION", "WORK_STATUS", "CONDITION_TYPES", "STANCE",
                 "EFFORT"):
        for value in getattr(vocab, name):
            assert value in body, f"{name} value {value!r} is listed nowhere"


def test_the_row_schema_is_still_here_too():
    """§6's original contents. The top-level half is an addition to this file, not
    a replacement of it."""
    body = text()
    for field in ("id", "kind", "text", "level", "screening", "match", "recency",
                  "how_to_close", "evidence"):
        assert f"{field}:" in body
    for name in ("LEVELS", "SCREENING", "MATCH", "RECENCY"):
        for value in getattr(vocab, name):
            assert value in body, f"{name} value {value!r} is listed nowhere"


def test_the_findings_a_missing_field_produces_are_named_here():
    """A schema that does not say what happens when you ignore it reads as a
    suggestion. Each of these is a hard finding from check_assessment.py."""
    body = text()
    for code in ("MISSING_LEVEL_DIRECTION", "MISSING_EFFORT", "BAD_WORK_STATUS",
                 "BAD_STATED_CONDITION", "WARN_NO_WORK_STATUS"):
        assert code in body, f"{code} fires against this file and is named nowhere in it"


def test_the_not_assessed_token_is_shown_rather_than_described():
    """The model has to recognise the string on a card it is reading back."""
    import count_coverage as cc
    body = text()
    assert cc.NOT_ASSESSED_ZH in body
    assert cc.NOT_ASSESSED_EN in body


def test_the_self_check_names_the_top_level_fields():
    """§12 is the checklist a run ticks. A rule that lives only in a schema block
    halfway up the file is a rule the last pass over the document never sees."""
    section = text().split("## 12.")[-1]
    for field in ("level_direction", "effort", "declared_work_status"):
        assert field in section, f"the self-check never mentions {field}"
