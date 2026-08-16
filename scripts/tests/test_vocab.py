import pathlib
import re
import sys

import pytest

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


def test_the_top_level_assessment_enums():
    """The fields the coverage card PRINTS, and the two the work-authorization
    notices read. Before these lived here, `level_direction` was spelled in no
    module at all and `declared_work_status`/`stance` in none either — so
    count_coverage.py invented a value for a field no vocabulary defined, and a
    typo in `stance` silently switched a notice off with nothing to compare
    against."""
    assert vocab.LEVEL_DIRECTION == ("step_up", "lateral", "step_down", "unclear")
    assert vocab.WORK_STATUS == ("authorized", "needs_sponsorship",
                                 "student_or_graduate", "temporary_route", "unknown")
    assert vocab.CONDITION_TYPES == ("sponsorship", "work_authorization", "citizenship",
                                     "clearance", "licence", "onsite_location", "other")
    assert vocab.STANCE == ("requires_existing", "offers_support", "unclear")


def test_unknown_is_a_work_status_and_not_an_absence():
    """consistency.py treats a missing declared_work_status and an explicit
    `unknown` identically — neither may downgrade anyone. The token has to be IN
    the set for the mode file to be able to tell the model to write it."""
    assert "unknown" in vocab.WORK_STATUS


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
                 "RECENCY", "EFFORT", "LEVEL_DIRECTION", "WORK_STATUS",
                 "CONDITION_TYPES", "STANCE", "BANDS", "DEFECT_TAGS"):
        assert isinstance(getattr(vocab, name), tuple), f"{name} must be a tuple"
    assert isinstance(vocab.VERDICT_ZH, dict)


def test_no_other_script_redeclares_a_closed_set():
    """The whole point. A second copy fails on the day it is written rather
    than on the day the two copies disagree. `MOCK_MARKET_KEYS` (Plan 4's
    documented superset) is deliberately still allowed — the anchored regex
    only rejects a bare re-declaration.

    A bare alias to the one source — `MARKET_KEYS = vocab.MARKET_KEYS`, which
    `check_conventions.py` uses for readability — is allowed too, and only in
    exactly that form. It is a second *name*, not a second *spelling*: it cannot
    drift, because there is nothing in it to drift from. Anything else on the
    right-hand side, a literal tuple most of all, still fails."""
    alias = re.compile(r"^\s*(MARKET_KEYS|DEFECT_TAGS)\s*=\s*vocab\.\1\s*$", re.M)
    for f in sorted(SCRIPTS.glob("*.py")):
        if f.name == "vocab.py":
            continue
        text = alias.sub("", f.read_text(encoding="utf-8"))
        assert "strong_apply" not in text, \
            f"{f.name} spells out a verdict — import it from vocab.py"
        assert not re.search(r"^\s*MARKET_KEYS\s*=", text, re.M), \
            f"{f.name} re-declares MARKET_KEYS — import it from vocab.py"
        assert not re.search(r"^\s*DEFECT_TAGS\s*=", text, re.M), \
            f"{f.name} re-declares DEFECT_TAGS — import it from vocab.py"


def test_the_alias_carve_out_does_not_admit_a_real_second_copy(tmp_path, monkeypatch):
    """Pin the carve-out from both sides. The exact alias passes; a literal tuple
    under the same name does not — otherwise the widening quietly deletes the guard."""
    import test_vocab as self_mod

    ok = tmp_path / "ok.py"
    ok.write_text("import vocab\nMARKET_KEYS = vocab.MARKET_KEYS\n", encoding="utf-8")
    bad = tmp_path / "bad.py"
    bad.write_text('MARKET_KEYS = ("cn", "nl", "de", "uk", "us")\n', encoding="utf-8")

    monkeypatch.setattr(self_mod, "SCRIPTS", tmp_path)
    ok_only = tmp_path / "keep"
    ok_only.mkdir()
    (ok_only / "ok.py").write_text(ok.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setattr(self_mod, "SCRIPTS", ok_only)
    self_mod.test_no_other_script_redeclares_a_closed_set()  # quiet case: must not raise

    monkeypatch.setattr(self_mod, "SCRIPTS", tmp_path)
    with pytest.raises(AssertionError, match="re-declares MARKET_KEYS"):
        self_mod.test_no_other_script_redeclares_a_closed_set()
