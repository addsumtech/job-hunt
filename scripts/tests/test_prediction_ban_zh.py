"""The prediction ban, in the language the skill actually outputs.

Decision D2 — no probabilities, no 0–100 scores — is the promise in this skill's
own frontmatter, and `lint_no_prediction.py` is its only executable half. An
audit on 2026-08-23 found that half unenforced in Chinese:

    _PERCENT = re.compile(r"%")            # ASCII U+0025 only
    _SCORE   = re.compile(r"\\b\\d+\\s*/\\s*\\d+\\b")  # ASCII digits and solidus
    ... |概率|通过率|命中率|录取率         # four hand-listed words

So 「面试成功率约七成」, 「入围率约三成」, 「匹配度：85％」 and 「评分 8／10」 all
shipped at exit 0 — two lines under a disclaimer swearing the skill does not do
this. `--lang zh` is the DEFAULT (count_coverage.py:170), so this was the primary
output path, not an edge case.

Two things this file pins that are easy to get wrong when widening a ban:

  * the mandated disclaimer must not fail its own gate. It contains 「可能性」,
    so 可能性 is deliberately NOT banned — layer 1 has already shipped a
    self-failing disclaimer once (commit 9809599).
  * ordinary engineering words must survive. 效率, 利率, 增长率, 采样率 are
    normal on a CV; 成功/成长/成员/成果/成本 are normal after a numeral. A ban
    that fires on honest text is a ban everyone learns to switch off.
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_assessment
import lint_no_prediction as L

REPO = pathlib.Path(__file__).resolve().parents[2]


def hits(text):
    return L.scan_text(text, "x.md")


# ── must fire ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "你面试成功率不低，大概七成",
    "入围率约三成",
    "录取率不高",
    "通过率约 60%",
    "命中率高",
    "中签率低",
    "录用率约两成",
    "百分之七十的可能",
    "匹配度：85％",          # fullwidth percent sign
    "评分 8／10",            # fullwidth solidus
    "面试概率约为 70%",
])
def test_a_chinese_prediction_is_caught(text):
    assert hits(text), f"{text!r} shipped clean"


@pytest.mark.parametrize("text", [
    "we estimate a seventy percent likelihood",
    "70 percent likely",
    "scored 7 out of 10",
    "his odds are good",
])
def test_an_english_prediction_is_caught(text):
    assert hits(text), f"{text!r} shipped clean"


# ── must NOT fire ─────────────────────────────────────────────────────────────

def test_the_mandated_disclaimer_does_not_fail_its_own_gate():
    """The exact text SKILL.md:419 and modes/assess.md:285 require. It contains
    「可能性」, which is why that word is not in the ban."""
    text = "本 skill 不给出面试或录用的可能性估计，也不给 0–100 分。要不要投，由你决定。"
    assert hits(text) == []


@pytest.mark.parametrize("anchor", check_assessment.DISCLAIMER_ANCHORS)
def test_every_required_disclaimer_anchor_survives_the_lint(anchor):
    """Pinned against check_assessment's own constant rather than a copy, so a
    reworded disclaimer cannot drift out of this test's sight."""
    assert hits(anchor) == []


@pytest.mark.parametrize("text", [
    "提升了采样效率",
    "当前利率环境",
    "年增长率数据由雇主公布",
    "把采样率提高到 2 kHz",
])
def test_ordinary_rate_words_are_not_banned(text):
    """A bare `X率` would have caught all of these. The character class is
    bounded to the words that describe getting the job."""
    assert hits(text) == [], f"{text!r} is an ordinary engineering phrase"


@pytest.mark.parametrize("text", [
    "他是团队的成功案例",
    "成长很快",
    "三成员工参与",
    "完成了三项改造",
    "达成目标",
    "五成本科毕业",
])
def test_numerals_before_ordinary_compounds_are_not_banned(text):
    """七成 = 70% is the idiom being banned; 成功/成长/成员/成果/成本 are not."""
    assert hits(text) == [], f"{text!r} tripped the 「N成」 rule"


def test_the_roadmap_horizon_is_still_exempt():
    """modes/assess.md §10 MANDATES a 30/60/90 table. The widened score pattern
    must not eat the thing the mode requires."""
    assert hits("30/60/90 天计划") == []


def test_the_cv_is_deliberately_outside_the_scan_set(tmp_path):
    """Why widening the scan set would be the WRONG fix, stated as a test.

    A CV bullet reading "Cut runtime by 40%" DOES trip this lint — and SKILL.md's
    Quantification ladder requires exactly that shape ("Reduced latency by 38%").
    There a number is a measured past achievement; in a fit card the same number
    is a claim about the future. So the defect was the registry's "anything
    rendered" wording, not the scan set, and `cv.md` must stay out of it.
    """
    assert hits("Cut offline reconstruction runtime by 40% on the 3T cohort.")
    workspace = tmp_path
    for name in ("cv.md", "letter.md", "fit-assessment.md"):
        (workspace / name).write_text("Reduced latency by 38%\n", encoding="utf-8")
    scanned = {p.name for p in L.target_files(workspace)}
    assert "fit-assessment.md" in scanned
    assert "cv.md" not in scanned and "letter.md" not in scanned


def _target_names():
    import inspect
    return inspect.getsource(L.target_files)


# ── the scan set, and the claim SKILL.md makes about it ───────────────────────

def test_shortlist_md_is_scanned_and_discover_now_runs_the_lint():
    """`target_files()` named shortlist.md and a passing test asserted it, but no
    flow ever scanned it: discover Step 10 ran only check_no_write and
    check_shortlist. A dead target plus a green test is a false coverage signal."""
    assert "shortlist.md" in _target_names()
    step10 = (REPO / "modes" / "discover.md").read_text(encoding="utf-8")
    assert "lint_no_prediction.py" in step10


def test_skill_md_no_longer_claims_the_lint_covers_anything_rendered():
    """The registry said "in anything rendered", which was never true and could
    not become true — the CV is the one artifact where a percentage is required.
    Overstating a gate is how a reader stops checking the artifact themselves."""
    text = (REPO / "SKILL.md").read_text(encoding="utf-8")
    row = next(line for line in text.splitlines()
               if line.startswith("| Prediction lint |"))
    assert "anything rendered" not in row
    assert "fit-assessment.md" in row and "shortlist.md" in row


@pytest.mark.parametrize("mode_file", ["assess.md", "discover.md"])
def test_the_mode_files_carrying_the_disclaimer_are_lint_clean(mode_file):
    """Not a lint target, but if the prose a run copies verbatim into its output
    cannot itself pass, the run cannot pass either."""
    text = (REPO / "modes" / mode_file).read_text(encoding="utf-8")
    assert L.scan_text(text, mode_file) == []


# ---------------------------------------------------------------------------
# The no-forecast rule, in the languages this skill actually writes in.
# Audited 2026-09-05: English and Chinese were enforced and nothing else was, so
# the same sentence shipped or failed depending on the candidate's language.
# ---------------------------------------------------------------------------

_FORECASTS = [
    "Sie werden das Vorstellungsgespräch sicher bekommen.",
    "Die Chancen stehen gut.",
    "Die Chancen auf eine Einladung sind hoch.",
    "Die Wahrscheinlichkeit ist hoch.",
    "De waarschijnlijkheid is groot.",
    "De kans op een aanbod is klein.",
    "Je krijgt zeker een uitnodiging voor een gesprek.",
    "Je hebt een grote kans op een gesprek.",
    "La probabilité est élevée.",
    "La probabilidad es alta.",
    "面接に呼ばれる可能性が高いです。",
    "합격 확률은 높습니다.",
    "You will certainly get the interview.",
]
_ORDINARY = [
    # Found by an adversarial re-read of my own widening, 2026-09-05. `Chance`
    # and `kans` are the ORDINARY words for "opportunity" in German and Dutch —
    # this is what postings actually say — and banning them bare fired on both.
    # English keeps its bare `chances?`: "chance" rarely carries that sense
    # there, so the collision rate is a fact about the language.
    "Wir bieten Chancen zur Weiterbildung.",
    "Wir bieten gute Aussichten auf Weiterbildung.",
    "Chancengleichheit ist uns wichtig.",
    "Er zijn goede kansen voor groei binnen het team.",
    "Gelijke kansen voor iedereen.",
    "Die Stelle ist in Amsterdam.",
    "Werden Sie Teil des Teams.",
    "Het salaris is marktconform.",
    "We werken met Python en PyTorch.",
    "この職務は東京にあります。",
    "이 직무는 서울에 있습니다.",
    "Le poste est basé à Paris.",
    "El puesto está en Madrid.",
]


@pytest.mark.parametrize("text", _FORECASTS, ids=range(len(_FORECASTS)))
def test_an_outcome_forecast_is_banned_in_every_language(text):
    assert L.scan_text(text, "fit-assessment.md"), text


@pytest.mark.parametrize("text", _ORDINARY, ids=range(len(_ORDINARY)))
def test_an_ordinary_sentence_about_the_job_is_not(text):
    """The longer list on purpose: `werden` and `kans` are common words, and a
    lint that fires on "Werden Sie Teil des Teams" is one that gets switched
    off."""
    assert L.scan_text(text, "fit-assessment.md") == [], text


@pytest.mark.parametrize("text,fires", [
    ("通过的比例约为 5‰", True), ("a 5 pct uplift", True), ("5% uplift", True),
    ("the expected uplift", False), ("Octet and pctl are field names", False),
])
def test_the_remaining_percent_spellings(text, fires):
    assert bool(L.scan_text(text, "fit-assessment.md")) is fires, text


# ---------------------------------------------------------------------------
# `chances?` was bare, and this pattern is case-insensitive — so once the skill
# started writing GERMAN assessments it fired on `Chance`, which is spelled
# identically and is that language's ordinary word for opportunity. An
# independent pass found six honest recruiting sentences failing the gate, and
# the cause was the English rule, not the German one.
# ---------------------------------------------------------------------------

_OPPORTUNITY = [
    "a chance to work with a great team",
    "I would welcome the chance to discuss this",
    "Wir bieten dir die Chance, in diesem Job viel zu lernen.",
    "Nutze die Chance und bewirb dich noch heute auf die Stelle.",
    "Das Gespräch war eine gute Chance, das Team kennenzulernen.",
    "Deze baan biedt de kans om veel te leren.",
    "Grijp de kans en solliciteer op deze baan.",
    "Wij bieden de kans op een vaste baan na een succesvol proefjaar.",
    "Dit is een unieke kans om ervaring op te doen.",
]
_ODDS = [
    "Your chances here are good.",
    "Boost your chances of success in this role.",
    "chances of an interview",
    "your chances of being shortlisted",
    "Die Chancen stehen gut.",
    "Die Chancen auf eine Einladung sind hoch.",
    "Je hebt een grote kans op een gesprek.",
    "De kans op een aanbod is klein.",
]


@pytest.mark.parametrize("text", _OPPORTUNITY, ids=range(len(_OPPORTUNITY)))
def test_the_word_for_opportunity_is_not_a_forecast(text):
    assert L.scan_text(text, "fit-assessment.md") == [], text


@pytest.mark.parametrize("text", _ODDS, ids=range(len(_ODDS)))
def test_a_claim_about_this_candidates_odds_still_is(text):
    assert L.scan_text(text, "fit-assessment.md"), text
