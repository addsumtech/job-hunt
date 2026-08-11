import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILL = ROOT / "SKILL.md"

HEADING = "## Mock interview — the anti-coaching line"

# These are compared against a WHITESPACE-NORMALISED copy of SKILL.md, so a phrase may
# be broken across lines by the file's hard wrap without breaking the assertion. Case
# is NOT normalised: "One round per dispatch" is asserted as the file writes it,
# because a rule shouted or lower-cased is a different sentence and these phrases are
# the whole point of the section. Do not "fix" a failure here by rewrapping the prose —
# the wrap will drift again; fix the phrase.
REQUIRED = [
    # The line itself
    "A mock interview may help the candidate FIND, ORDER, and COMPRESS a true story they",
    "It may not help them ACQUIRE one.",
    "it is fabrication, however plausible, and it stays fabrication after the candidate agrees",
    # Rule 1
    "**Never write an answer for the candidate.**",
    "Naming a gap is feedback; filling it is ghostwriting a lie.",
    # Rule 2
    "**A leading question is a fabrication vector.**",
    "never build a question on a premise the CV does not support",
    # Rule 3
    "**An undefendable claim is a CV bug, not a story to drill.**",
    "the three CV judges only read the page and the page does not stammer",
    # Rule 4
    "**Never rehearse a gap into a non-gap.**",
    '"I haven\'t done X" must survive rehearsal intact',
    # The tripwire
    "**The tripwire.**",
    "`UNSOURCED-FACT`",
    "BEFORE it may enter the answer bank",
    "an answer-bank entry containing an unsourced fact is worse than no answer bank",
    # Session mechanics
    "One round per dispatch",
    "Flush the transcript after every answer",
    "the first assessment pass does not see `interview-brief.md` or `claims.yaml`",
]


def _normalised() -> str:
    return " ".join(SKILL.read_text(encoding="utf-8").split())


def _section() -> str:
    """This section only — up to the next H2 or EOF.

    Scoped rather than 'everything after the heading': other plans append their own
    sections to SKILL.md, and a later append landing inside this one's scanned region
    would make the no-score assertion below fail for a reason that has nothing to do
    with this section.
    """
    text = SKILL.read_text(encoding="utf-8")
    assert HEADING in text, "SKILL.md has no anti-coaching section"
    body = text.split(HEADING, 1)[1]
    following = re.search(r"^## ", body, re.M)
    return body[:following.start()] if following else body


def test_the_section_exists_exactly_once():
    text = SKILL.read_text(encoding="utf-8")
    assert text.count(HEADING) == 1


def test_every_load_bearing_sentence_survives():
    text = _normalised()
    missing = [p for p in REQUIRED if " ".join(p.split()) not in text]
    assert not missing, f"SKILL.md is missing: {missing}"


def test_the_four_rules_are_numbered_rules():
    numbers = re.findall(r"^(\d)\. \*\*", _section(), re.M)
    assert numbers[:4] == ["1", "2", "3", "4"]


def test_the_section_does_not_smuggle_in_a_score():
    section = _section()
    assert "%" not in section
    assert not re.search(r"\b\d+\s*/\s*\d+\b", section)
