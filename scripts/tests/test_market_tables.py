import datetime
import pathlib

import check_conventions as cck

ROOT = cck.CONVENTIONS_DIR
# Pinned so the suite does not start failing on a review_by date rolling past. When it
# does roll past, that is the CI lint's job to say so, not this test's.
BUILD_DAY = datetime.date(2026, 8, 9)

EXPECTED_COUNTS = {"cn": 10, "nl": 9, "de": 8, "uk": 5, "us": 6}


def test_every_market_key_has_a_table():
    for key in cck.MARKET_KEYS:
        assert (ROOT / f"{key}.yaml").exists(), key


def test_every_table_declares_the_market_its_filename_claims():
    # check_file only checks membership in MARKET_KEYS, and check_assessment selects
    # the table by FILENAME. A file called nl.yaml that declares `market: de` is
    # therefore invisible — and a wrong market card reads exactly like a right one.
    for key in cck.MARKET_KEYS:
        assert cck.load_market_file(ROOT / f"{key}.yaml")["market"] == key, key


def test_every_shipped_table_passes_the_lint_with_no_hard_finding():
    for key in cck.MARKET_KEYS:
        findings = cck.check_file(ROOT / f"{key}.yaml", BUILD_DAY)
        hard = [f for f in findings if not f.startswith("WARN_")]
        assert hard == [], f"{key}.yaml: {hard}"


def test_the_entry_counts_match_the_dispositions_the_reviewer_signed_off():
    for key, expected in EXPECTED_COUNTS.items():
        data = cck.load_market_file(ROOT / f"{key}.yaml")
        assert len(data["conventions"]) == expected, key


def test_no_id_collides_across_tables():
    seen: dict[str, str] = {}
    for key in cck.MARKET_KEYS:
        for entry_id in cck.conventions_by_id(cck.load_market_file(ROOT / f"{key}.yaml")):
            assert entry_id not in seen, f"{entry_id} in {key} and {seen[entry_id]}"
            seen[entry_id] = key


def test_the_dropped_entries_appear_in_no_table():
    dropped = ("nl-weu-be-single-permit-is-regional",
               "de-dach-ch-permit-is-employer-filed-and-capped",
               "de-dach-at-advertised-pay-is-a-floor")
    for key in cck.MARKET_KEYS:
        ids = set(cck.conventions_by_id(cck.load_market_file(ROOT / f"{key}.yaml")))
        assert ids.isdisjoint(dropped), key


def test_the_three_live_violations_the_reviewer_found_are_gone():
    # "51job" in an English body, "30% ruling" in both languages, "2023/970" in a body.
    #
    # Scoped to the PROSE fields, and that scoping is the whole point. Both needles
    # are also legitimate citation content: cn-campus-track-is-cohort-gated-and-early
    # cites the 51job.com homepage, and nl-pay-range-not-pay-history cites the EUR-Lex
    # title "Directive (EU) 2023/970 …". Grepping the whole file would leave exactly
    # one escape — deleting the citation — which is the outcome the README's exemption
    # paragraph exists to prevent.
    needles = {"cn": ("51job",), "nl": ("30%", "2023/970")}
    for key, wanted in needles.items():
        data = cck.load_market_file(ROOT / f"{key}.yaml")
        for entry in data["conventions"]:
            prose = " ".join(str(entry.get(f) or "") for f in cck.PROSE_FIELDS)
            for needle in wanted:
                assert needle not in prose, f"{entry['id']}: {needle}"


def test_the_allowlisted_proper_nouns_survived_the_digit_ban():
    us = (ROOT / "us.yaml").read_text(encoding="utf-8")
    for needle in ("H-1B", "Form I-9"):
        assert needle in us, needle
