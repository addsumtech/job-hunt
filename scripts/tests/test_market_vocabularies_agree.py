"""Two market tables, one relationship, pinned.

This skill has TWO market vocabularies and they answer different questions, so
merging them would be wrong:

  * `vocab.MARKET_KEYS` — which markets have a convention table under
    `references/market-conventions/`. Five, and adding a sixth means writing and
    sourcing a whole table.
  * `render_cv._CLUSTER_*` — which CV-writing convention a country follows.
    Around fifty codes and names, because a candidate targeting Japan still
    needs to know a photo is normal there even though no convention table
    exists for it.
  * `check_shortlist.MARKET_TOKENS` — how a country is NAMED inside a free-text
    location string, for the five table markets only.

The 2026-09-05 audit called them "four unreconciled vocabularies". They are
not reconcilable into one — but the RELATIONSHIP between them is checkable, and
nothing was checking it. That is what drifts: a market added to one table and
forgotten in another looks identical to a market nobody added.
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import check_shortlist
import render_cv
import vocab


@pytest.mark.parametrize("key", vocab.MARKET_KEYS)
def test_every_market_with_a_convention_table_resolves_to_a_cluster(key):
    """A market the skill has researched conventions for must be one the
    renderer can place. Otherwise assess prints a convention card while the
    renderer treats the same market as unknown and — since 2026-09-05 —
    withholds personal data from it."""
    assert render_cv.resolve_cluster(key) is not None, key


@pytest.mark.parametrize("key", vocab.MARKET_KEYS)
def test_every_market_with_a_convention_table_is_nameable_in_a_location(key):
    assert key in check_shortlist.MARKET_TOKENS, key


def test_the_two_tables_name_the_same_five_markets():
    assert set(check_shortlist.MARKET_TOKENS) == set(vocab.MARKET_KEYS)


@pytest.mark.parametrize("key,tokens", sorted(check_shortlist.MARKET_TOKENS.items()))
def test_a_country_name_used_by_the_shortlist_resolves_the_same_way(key, tokens):
    """`nederland` was a recognised Netherlands token to check_shortlist and
    unknown to render_cv — one gate reading a location as the Netherlands while
    the other read the same string as no market at all."""
    expected = render_cv.resolve_cluster(key)
    for token in tokens:
        if token in check_shortlist.CITY_TOKENS:
            continue          # a city is not in a table of countries
        got = render_cv.resolve_cluster(token)
        assert got == expected, (
            f"{token!r} names {key!r} to check_shortlist but resolves to cluster "
            f"{got!r} in render_cv, where {key!r} is cluster {expected!r}")


def test_no_market_is_the_one_token_for_having_no_table():
    """`other` must not accidentally become a country: it is the token that says
    a market has no convention data, and a cluster for it would mean the
    renderer silently picked conventions for a market that declared it had
    none."""
    assert vocab.NO_MARKET not in vocab.MARKET_KEYS
    assert render_cv.resolve_cluster(vocab.NO_MARKET) is None


def test_every_declared_city_token_is_actually_used():
    """An exemption nobody can see is indistinguishable from a token nobody
    remembered to add — and one left behind after its token was deleted quietly
    widens what the next city may skip."""
    used = {t for tokens in check_shortlist.MARKET_TOKENS.values() for t in tokens}
    assert check_shortlist.CITY_TOKENS <= used, (
        check_shortlist.CITY_TOKENS - used)
