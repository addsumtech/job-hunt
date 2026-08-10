"""The source policy must be ONE standard, and one the skill actually obeys."""
import pathlib
import re

import check_shortlist as cs

REPO = pathlib.Path(__file__).resolve().parents[2]
POLICY = REPO / "references" / "source-policy.md"


def sections():
    text = POLICY.read_text(encoding="utf-8")
    parts = re.split(r"^## ", text, flags=re.M)
    return {p.split("\n", 1)[0].strip(): p.split("\n", 1)[1] for p in parts[1:]}


def test_there_is_exactly_one_source_policy_file():
    found = sorted(p.name for p in (REPO / "references").glob("*source-polic*"))
    assert found == ["source-policy.md"]


def test_there_is_exactly_one_tier_section_of_each_colour():
    text = POLICY.read_text(encoding="utf-8")
    for colour in ("Green", "Yellow", "Red"):
        assert len(re.findall(rf"^## {colour}\b", text, flags=re.M)) == 1


def test_pagination_and_detail_fetch_are_yellow_not_red():
    blocks = sections()
    yellow, red = blocks["Yellow"], blocks["Red"]
    assert "pagination" in yellow.lower()
    assert "detail" in yellow.lower()
    for banned in ("auto-scroll", "page through", "detail page",
                   "hidden/internal API"):
        assert banned.lower() not in red.lower(), (
            f"{banned!r} is still in Red, which the skill itself does on every run")


def test_red_keeps_every_named_ban():
    red = sections()["Red"].lower()
    for phrase in ("captcha", "risk-control", "fingerprint", "proxy", "stealth",
                   "multi-account rotation", "while the user is not present",
                   "batch apply", "greeting", "auto-chat",
                   "without a fresh source signal",
                   "published `access:` is `write`"):
        assert phrase.lower() in red, f"Red no longer bans {phrase!r}"


def test_the_policy_says_account_risk_is_not_zero_in_those_words():
    assert "Account risk is not zero." in POLICY.read_text(encoding="utf-8")


def test_the_yellow_caps_are_the_ones_the_gates_enforce():
    yellow = sections()["Yellow"]
    assert "max_rows_per_round" in yellow
    assert "max_pages_per_site" in yellow
    for verdict in cs.TOP_THREE:
        assert verdict in yellow, (
            f"the detail-fetch cap must name {verdict} exactly as "
            "check_shortlist.DETAIL_FETCH_OUT_OF_BAND does")
    assert "DETAIL_FETCH_OUT_OF_BAND" in yellow
    # The two numbers are the enforceable half of this file. If the prose and
    # the gate ever disagree, the run passes a cap the policy did not set.
    assert str(cs.MAX_ROWS_PER_ROUND_CEILING) in yellow
    assert str(cs.MAX_PAGES_PER_SITE_CEILING) in yellow
    assert "CAP_ABOVE_CEILING" in yellow


def test_skill_md_carries_this_files_trigger_and_names_its_backstop():
    # Every layer-2 file needs a trigger a model can evaluate WITHOUT having
    # read it, plus something that reports skipping it. This file had neither
    # until now: its only pointer lived inside modes/discover.md's self-check,
    # which you only reach once you have already opened the mode file.
    text = (REPO / "SKILL.md").read_text(encoding="utf-8")
    assert "references/source-policy.md" in text
    assert "before the first live retrieval of any run" in text
    assert "CAP_ABOVE_CEILING" in text


def test_the_policy_does_not_ban_the_adapters_the_skill_uses():
    red = sections()["Red"]
    for site in ("51job", "indeed", "linkedin", "boss"):
        assert site not in red


def test_the_changelog_names_what_moved_and_why():
    text = POLICY.read_text(encoding="utf-8")
    assert "## What changed from the retired policy" in text
    assert "job-search-coach" in text
    assert "cookie" in text          # the honest naming of the moved red line


def test_the_required_metadata_maps_onto_the_real_row_fields():
    text = POLICY.read_text(encoding="utf-8")
    for field in ("source_site", "source_id", "retrieved_at",
                  "extraction_method", "quality", "verification"):
        assert field in text
    # The retired policy's extraction_method values are gone; the live enum wins.
    for value in cs.EXTRACTION_METHODS:
        assert value in text
    assert "visible_capture" not in text
