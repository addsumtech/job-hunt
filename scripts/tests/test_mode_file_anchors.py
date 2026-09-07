"""A composer greps its mode file for literal strings. Rename one and nothing tells you.

`check_assessment` decides a card is defective unless it finds `## 硬性阻断项`,
`## Hard blockers`, `已过复核期`, `验收标准` and a dozen more — strings that ONLY
`modes/assess.md` teaches the model to write. `check_shortlist` does the same to
`modes/discover.md`. Nothing held the two sides together.

Reproduced 2026-09-07 on a copy of the repo. Renaming four headings in
modes/assess.md — `## 硬性阻断项` to `## 硬性阻断事项`, `## Hard blockers` to
`## Hard blocking items`, `## 那该怎么办` to `## 接下来怎么办`, `## What to do
instead` to `## What to do next`:

    python3 -m pytest scripts/tests -q     3243 passed, 1 skipped
    bash scripts/tests/check_assess_anchors.sh    all anchors present

Both green. A model then follows layer 1.5 verbatim and `check_assessment`
rejects the card it produced with NO_DISQUALIFIER_SECTION. The `.sh` above was
written to pin exactly this and could not: it was not a pytest file, it was in
neither the Makefile nor CI, and it opened
`cd /Users/donghanglyu/code_project/job-hunt`, so wherever it ran it audited one
absolute path rather than the tree it lived in. Flagged in the 2026-08-16 audit,
half-fixed — `test_assess_mode_doc.py` took over the SCHEMA half (fields, enums,
finding codes) and never covered the prose literals. Deleted with this file.

The needles are DERIVED from the gate module, never retyped, so adding a literal
to a gate makes it a required anchor automatically. And `test_every_string_constant_is_classified`
is the half that keeps that true: a new string constant belongs to the mode file
or is exempt with a reason, and until someone says which, this file goes red.
"""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_assessment  # noqa: E402
import check_shortlist  # noqa: E402

# Constants whose strings the MODE FILE has to teach the model to write, because
# the gate greps the produced document for them.
ANCHORS = {
    "assess": (check_assessment, [
        "DISCLAIMER_ANCHORS", "VERDICT_MARKERS", "DISQUALIFIER_HEADINGS",
        "STALE_BANNER", "STRATEGIES", "STRATEGY_HEADINGS", "ACCEPTANCE_COLUMNS",
    ]),
    "discover": (check_shortlist, [
        "DISCLOSURE_LABELS", "PROVISIONAL_STAMP",
        "REQUIRED_ROW_FIELDS", "VERDICTS", "EFFORT", "QUALITIES",
        "EXTRACTION_METHODS", "VERIFICATIONS",
    ]),
}

# Everything else, with the reason it is not the mode file's job. Kept beside the
# list above so the two together must cover the module — see the last test.
NOT_ANCHORS = {
    "GATE": "the gate's own name, written into its receipt",
    "MODE": "the mode name in the receipt, not prose in the document",
    "UPSTREAM_GATES": "names of other gates whose receipts are required",
    "PASSING_VERDICTS": "receipt statuses in journal.jsonl",
    "TOP_THREE": "a slice of VERDICTS, already covered by it",
    "CITY_TOKENS": "a matcher for text the SITE returns, not text we ask for",
    "MARKET_TOKENS": "the same — location text a job board wrote, matched not written",
    # These two were anchors in the first draft and both were wrong, in the
    # direction this repo punishes hardest. A gate that fires on correct output
    # gets switched off, so each exemption below says what the gate actually does
    # with the constant rather than what its name suggests.
    "OTHER_HALF_VERDICTS": "compared against the PARSED verdict value "
                           "(`if verdict in OTHER_HALF_VERDICTS`), never grepped from "
                           "the card. The five verdicts are a closed vocabulary in "
                           "vocab.py, taught by SKILL.md, not prose the mode file spells",
    "EMPTINESS_PHRASES": "nine ways a model might SAY it found nothing, so the gate can "
                         "check the claim is supported. A detector for what the model "
                         "wrote, not a template it must follow — requiring all nine in "
                         "modes/discover.md would fire on every correct round",
}


def _strings(value):
    """Flatten a constant to the strings a document would have to contain.

    Total by construction: an int, a float or a compiled regex yields nothing.
    The first draft assumed every uppercase name held strings and died on
    `MIN_SOURCE_ID_LEN = 2` — an audit that crashes reports nothing about the
    thing it was auditing.
    """
    if isinstance(value, str):
        return [value]
    if isinstance(value, (tuple, list, set, frozenset, dict)):
        out = []
        for item in value:
            out += _strings(item)
        return out
    return []


def _needles(mode):
    module, names = ANCHORS[mode]
    out = []
    for name in names:
        assert hasattr(module, name), (
            f"{module.__name__}.{name} is gone — this list is stale, and a stale "
            f"list silently checks nothing")
        found = _strings(getattr(module, name))
        assert found, f"{module.__name__}.{name} holds no strings"
        out += [(name, s) for s in found]
    return out


def _cases():
    return [(mode, name, needle)
            for mode in sorted(ANCHORS)
            for name, needle in _needles(mode)]


@pytest.mark.parametrize("mode, const, needle", _cases(),
                         ids=lambda v: str(v)[:34])
def test_the_mode_file_teaches_every_literal_its_gate_greps_for(mode, const, needle):
    """The gate reads the produced document for this string. If layer 1.5 never
    shows it, the model has no way to know to write it — and the failure lands on
    the user as a rejected card, not here."""
    body = (ROOT / "modes" / f"{mode}.md").read_text(encoding="utf-8")
    assert needle in body, (
        f"{const} contains {needle!r}, which modes/{mode}.md never shows. "
        f"The gate greps the card for it, so a run that follows the mode file "
        f"verbatim produces a card the gate rejects.")


@pytest.mark.parametrize("mode", sorted(ANCHORS))
def test_every_string_constant_is_classified(mode):
    """The half that stops the anchor list going quietly stale.

    A new literal added to a gate has to be either an anchor the mode file must
    teach or an exemption with a reason. Until someone decides, this is red —
    which is the point: the 2026-08-16 audit's word for the alternative was
    "silently unguarded".
    """
    module, names = ANCHORS[mode]
    unclassified = []
    for attr in dir(module):
        if not attr[0].isupper() or attr in names or attr in NOT_ANCHORS:
            continue
        if _strings(getattr(module, attr)):
            unclassified.append(attr)
    assert not unclassified, (
        f"{module.__name__} has string constants nobody classified: {unclassified}. "
        f"Add each to ANCHORS[{mode!r}] if modes/{mode}.md must teach it, or to "
        f"NOT_ANCHORS with the reason it does not.")


def test_the_absolute_path_script_is_gone():
    """`check_assess_anchors.sh` opened `cd /Users/<name>/code_project/job-hunt`,
    so a clone audited the original author's tree and reported it as its own."""
    assert not (ROOT / "scripts" / "tests" / "check_assess_anchors.sh").exists()
    hits = [p for p in ROOT.rglob("*.sh")
            if "/Users/" in p.read_text(encoding="utf-8", errors="replace")]
    assert not hits, f"a shell script hardcodes a home directory: {hits}"


def test_the_posting_field_list_does_not_advertise_a_language_field():
    """Carried over from the deleted `check_assess_anchors.sh`, which was the only
    place it lived.

    There is no `language` field on a posting: the CV's language follows the
    market and lives in `meta.language` on the profile. A mode file that lists one
    teaches the model to extract a field every downstream reader ignores.
    """
    body = (ROOT / "modes" / "assess.md").read_text(encoding="utf-8")
    assert "language: en" not in body
