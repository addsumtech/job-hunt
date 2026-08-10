import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import vocab

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent


def test_the_five_verdicts_are_exactly_these_in_this_order():
    assert vocab.VERDICTS == ("strong_apply", "worth_applying", "stretch",
                              "likely_screen_out", "blocked")


def test_the_refusal_is_not_a_sixth_verdict():
    """A refusal is orthogonal to the scale. Folding it in would let a caller
    sort it, average it, or read 'cannot tell' as a weak recommendation."""
    assert vocab.REFUSAL == "insufficient_evidence"
    assert vocab.REFUSAL not in vocab.VERDICTS


def test_every_verdict_and_the_refusal_have_a_zh_label():
    assert set(vocab.VERDICT_ZH) == set(vocab.VERDICTS) | {vocab.REFUSAL}
    assert vocab.VERDICT_ZH["blocked"] == "硬性阻断"
    assert vocab.VERDICT_ZH[vocab.REFUSAL] == "证据不足—不出结论"


def test_market_keys_and_the_no_table_token():
    assert vocab.MARKET_KEYS == ("cn", "nl", "de", "uk", "us")
    assert vocab.NO_MARKET == "other"
    assert vocab.NO_MARKET not in vocab.MARKET_KEYS


def test_requirement_row_enums():
    assert vocab.LEVELS == ("required", "preferred", "unclear")
    assert vocab.SCREENING == ("knockout", "weighted", "nice_to_have")
    assert vocab.MATCH == ("strong", "partial", "gap", "no_evidence")
    assert vocab.RECENCY == ("current", "recent", "dated", "undated")
    assert vocab.EFFORT == ("quick", "evening", "multi_day", "not_closable")


def test_mock_bands_are_unnumbered_and_contradicted_is_not_one_of_them():
    assert vocab.BANDS == ("not_present", "asserted", "instanced", "held_under_probe")
    assert vocab.CONTRADICTED == "contradicted"
    assert vocab.CONTRADICTED not in vocab.BANDS
    assert vocab.DEFECT_TAGS == ("UNSOURCED-FACT", "OVER-CLAIM", "CONTRADICTED",
                                 "PROBE-COLLAPSE")


def test_every_closed_set_is_an_immutable_tuple():
    """A list would let a caller append to the shared vocabulary at import
    time, and the drift this module exists to stop would come back invisible."""
    for name in ("VERDICTS", "MARKET_KEYS", "LEVELS", "SCREENING", "MATCH",
                 "RECENCY", "EFFORT", "BANDS", "DEFECT_TAGS"):
        assert isinstance(getattr(vocab, name), tuple), f"{name} must be a tuple"
    assert isinstance(vocab.VERDICT_ZH, dict)


def test_no_other_script_redeclares_a_closed_set():
    """The whole point. A second copy fails on the day it is written rather
    than on the day the two copies disagree. `MOCK_MARKET_KEYS` (Plan 4's
    documented superset) is deliberately still allowed — the anchored regex
    only rejects a bare re-declaration."""
    for f in sorted(SCRIPTS.glob("*.py")):
        if f.name == "vocab.py":
            continue
        text = f.read_text(encoding="utf-8")
        assert "strong_apply" not in text, \
            f"{f.name} spells out a verdict — import it from vocab.py"
        assert not re.search(r"^\s*MARKET_KEYS\s*=", text, re.M), \
            f"{f.name} re-declares MARKET_KEYS — import it from vocab.py"
        assert not re.search(r"^\s*DEFECT_TAGS\s*=", text, re.M), \
            f"{f.name} re-declares DEFECT_TAGS — import it from vocab.py"
