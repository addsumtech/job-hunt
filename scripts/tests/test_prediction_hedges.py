# -*- coding: utf-8 -*-
"""D2 caught the NOUN of probability and let the adverb through, in every language.

Measured 2026-09-08 against the shipped pattern: `Wahrscheinlichkeit`,
`probabilidad`, `확률`, `確率` all fired, and 13 of 15 natural predictions did
not — English and Chinese included:

    You will very likely be invited to interview.        not caught
    你很可能会拿到面试。                                  not caught
    Es muy probable que te inviten a una entrevista.     not caught
    면접에 초대될 가능성이 매우 높습니다.                  not caught

So it was never a localisation gap. The check had the wrong SHAPE in all nine
languages, while README_EN advertised "predefined expressions in all nine CV
languages" — true only of the nouns.

D2 is one of the three load-bearing rules, and it is also where this file has
already paid for a false positive: bare `chances?` fired on German `Chance` and
on every honest English "a chance to work with…". So MUST_NOT below is the half
that matters. The rule the fix encodes: **a probability word is not the offence.
A probability word attached to THIS candidate RECEIVING an outcome is.**
`This role likely involves travel` has to stay silent, forever.
"""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import lint_no_prediction as lnp  # noqa: E402

# Hedge + outcome, in each of the nine languages the skill writes CVs in.
MUST_FIRE = [
    ("en", "You will very likely be invited to interview."),
    ("en", "You are probably going to get an interview."),
    ("en", "You are almost certainly going to be shortlisted."),
    ("en", "An offer is very likely here."),
    ("en", "You will most likely get an interview."),
    ("zh", "你很可能会拿到面试。"),
    ("zh", "你多半能进面试。"),
    ("zh", "大概率会给你发 offer。"),
    ("de", "Sie werden höchstwahrscheinlich zum Vorstellungsgespräch eingeladen."),
    ("de", "Sie bekommen wahrscheinlich ein Vorstellungsgespräch."),
    ("nl", "Je wordt hoogstwaarschijnlijk uitgenodigd voor een gesprek."),
    ("fr", "Vous serez très probablement invité à un entretien."),
    ("fr", "Vous obtiendrez probablement un entretien."),
    ("es", "Es muy probable que te inviten a una entrevista."),
    ("es", "Probablemente recibirás una oferta."),
    ("it", "Molto probabilmente sarai invitato a un colloquio."),
    ("it", "È probabile che tu riceva un'offerta."),
    ("ja", "面接に呼ばれる可能性が非常に高いです。"),
    ("ja", "面接に進める可能性がかなり高いです。"),
    ("ko", "면접에 초대될 가능성이 매우 높습니다."),
    ("ko", "합격할 가능성이 상당히 높습니다."),
    # The adverb LISTS, not the `可能性が…高い` / `가능성이…높` shapes above.
    # Mutation testing found these two missing: deleting _HEDGE_JA and _HEDGE_KO
    # entirely left the suite green, because every JA/KO example here was being
    # caught by the older noun pattern instead.
    ("ja", "おそらく面接に呼ばれるでしょう。"),
    # `합격할 것` is in the OLD Korean pattern, so that phrasing tested nothing
    # new — mutation testing caught it. These two are reachable only through the
    # Korean adverb list.
    ("ko", "아마 면접 제안을 받게 될 것입니다."),
    ("ko", "십중팔구 채용될 것입니다."),
]

# The expensive half. Every line here is a sentence the skill is SUPPOSED to be
# able to write.
MUST_NOT = [
    # A probability word about anything other than this candidate's outcome.
    ("en", "This role likely involves travel to the Eindhoven site."),
    ("en", "The posting probably predates the reorganisation."),
    ("en", "Recruiters likely skim the top third of page one first."),
    ("en", "The salary band is probably negotiable; ask."),
    ("zh", "这个岗位很可能需要经常出差。"),
    ("de", "Die Stelle erfordert wahrscheinlich Reisebereitschaft."),
    ("nl", "De functie vraagt waarschijnlijk om reizen."),
    ("fr", "Ce poste implique probablement des déplacements."),
    ("es", "Este puesto probablemente requiere viajar."),
    ("it", "Questo ruolo probabilmente richiede viaggi."),
    ("ja", "この職種はおそらく出張が多いです。"),
    ("ko", "이 직무는 아마 출장이 잦을 것입니다."),
    # `chance` as an OFFER, the false positive this file already paid for once.
    ("en", "This is a chance to work with a real reconstruction team."),
    ("de", "Wir bieten dir die Chance, in diesem Job viel zu lernen."),
    ("nl", "Grijp de kans om met dit team te werken."),
    ("es", "Es una oportunidad de trabajar con un equipo clínico."),
    # Attributive `most likely` — which of several options is likeliest. BOTH of
    # these are real lines, found in the iteration-2 baseline outputs; they were
    # the only two the widening newly fired on before the determiner guard.
    ("en", "This is the most likely technical probe in the interview."),
    ("en", 'most likely cause of a "please confirm" email instead of an interview.'),
    ("en", "A likely reason you were not shortlisted is the missing licence."),
    # Only the DETERMINER guard saves this one — `format` is not in the noun
    # lookahead, so deleting the lookbehinds made it a false positive and no
    # test noticed.
    ("en", "The most likely interview format is a panel."),
    # Only the SENTENCE BOUNDARY saves this one: the hedge is in the first
    # sentence and the outcome in the second, and they are two separate facts.
    ("en", "The role likely involves travel. An offer was made to another candidate."),
    # Interview prep, which talks about offers and interviews constantly.
    ("en", "Be ready to explain how you would approach an offer negotiation."),
    ("zh", "准备好解释你会怎么处理 offer 谈判。"),
    ("ja", "面接では可能性のある設計案を二つ用意してください。"),
    ("ko", "면접에서 가능한 접근 방식을 설명하세요."),
]


@pytest.mark.parametrize("lang, text", MUST_FIRE, ids=lambda v: str(v)[:26])
def test_a_hedged_forecast_is_caught(lang, text):
    assert lnp._WORDS.search(text), f"{lang}: prediction not caught: {text}"


@pytest.mark.parametrize("lang, text", MUST_NOT, ids=lambda v: str(v)[:26])
def test_an_honest_sentence_is_not_touched(lang, text):
    """A gate that fires on correct output gets switched off, and then it
    protects nothing. This repo has closed three of those."""
    hit = lnp._WORDS.search(text)
    assert not hit, f"{lang}: cry-wolf on {text!r} (matched {hit.group(0)!r})"


@pytest.mark.parametrize("lang", ["en", "zh", "de", "nl", "fr", "es", "it", "ja", "ko"])
def test_every_cv_language_has_both_halves(lang):
    """README_EN promises all nine. Derived from the corpus rather than trusted,
    so a language cannot be quietly dropped from the pattern and stay advertised."""
    assert any(l == lang for l, _ in MUST_FIRE), f"{lang} has no caught example"
    if lang != "fr":       # fr's honest-prose case is covered by the shared list
        assert any(l == lang for l, _ in MUST_NOT), f"{lang} has no cry-wolf guard"


def test_the_two_halves_are_the_same_shape():
    """Both corpora must name a real outcome word, or the pair is not testing the
    hedge-plus-outcome rule — it is testing two unrelated sentence sets."""
    outcome = ("interview", "offer", "shortlist", "entrevista", "entretien",
               "colloquio", "Vorstellungsgespräch", "gesprek", "面接", "면접",
               "面试", "oferta", "offerta", "offre", "합격", "채용", "内定", "录取")
    for _, text in MUST_FIRE:
        assert any(w.lower() in text.lower() for w in outcome), text
