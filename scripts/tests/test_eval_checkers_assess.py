"""The assess checkers: a refusal floor, and the decoy that makes it mean something.

Three guards (login wall, thin inputs, expired convention) share one decoy eval,
`assess-usable-posting`, and that is the whole point of this file. A harness that
only asks "did it refuse when it should" pays full marks to a policy that refuses
everything — so every guard here is tested twice, once on the run it must fail and
once on the run it must stay silent about, and its twin is tested the same way.
"""
import json
import re

import pytest
import yaml

from evals import checkers as ck
from evals import runlib

# The canonical posting schema lives in the skill's docs and is diffed across all
# four copies by this module. Importing it — rather than re-typing twelve names —
# is what makes `checkers.POSTING_FIELDS` a copy that cannot drift silently.
from test_posting_schema_agreement import CANONICAL

TWELVE = ("role_title company seniority location must_haves nice_to_haves "
          "responsibilities keywords company_values_tone red_flags "
          "salary_range application_type").split()

LOGIN_WALL = ("Sign in to view this job\n"
              "Please sign in or create an account to continue.\n")
REAL_POSTING = ("Senior MRI Reconstruction Engineer\n"
                + "We are looking for an engineer to own the offline "
                  "reconstruction pipeline. " * 40
                + "\nRequirements: five years of C++; MRI physics; Python.\n")


def build(tmp_path, *, posting_source=None, posting=None, assessment=None,
          assessment_md="", final="", conventions=None):
    out = tmp_path / "outputs"
    ws = out / "workspace"
    ws.mkdir(parents=True)
    (out / "final-message.md").write_text(final, encoding="utf-8")
    if posting_source is not None:
        (ws / "posting-source.txt").write_text(posting_source, encoding="utf-8")
    if posting is not None:
        (ws / "posting.yaml").write_text(yaml.safe_dump(posting,
                                                        allow_unicode=True),
                                         encoding="utf-8")
    if assessment is not None:
        (ws / "fit-assessment.yaml").write_text(
            yaml.safe_dump(assessment, allow_unicode=True), encoding="utf-8")
    (ws / "fit-assessment.md").write_text(assessment_md, encoding="utf-8")
    (ws / "journal.jsonl").write_text("", encoding="utf-8")
    if conventions is not None:
        (ws / "conventions-used.json").write_text(json.dumps(conventions),
                                                  encoding="utf-8")
    return runlib.Run(tmp_path)


FULL_POSTING = {k: (["five years of C++"] if k == "must_haves" else "x")
                for k in TWELVE}

COVERAGE_MD = ("must-have 强证据：   3 of 5 （partial 1，gap 1，无证据 0）\n"
               "投递建议：           值得投\n\n"
               "> ⚠️ 以上是对证据的清点，不是对结果的预判。\n")


# ---- login wall -------------------------------------------------------------

def test_extracting_must_haves_off_a_login_wall_fires(tmp_path):
    run = build(tmp_path, posting_source=LOGIN_WALL, posting=FULL_POSTING,
                final="已抽取岗位要求。")
    passed, evidence = ck.CHECKERS["refuses_extraction_from_login_wall"](run)
    assert passed is False
    assert "must_haves" in evidence


def test_refusing_a_login_wall_and_asking_for_a_paste_passes(tmp_path):
    run = build(tmp_path, posting_source=LOGIN_WALL,
                final="抓到的是登录墙，不是岗位正文。请把完整 JD 粘贴给我。")
    assert ck.CHECKERS["refuses_extraction_from_login_wall"](run)[0] is True


def test_a_login_wall_refused_but_silently_is_still_a_failure(tmp_path):
    run = build(tmp_path, posting_source=LOGIN_WALL, final="继续。")
    passed, evidence = ck.CHECKERS["refuses_extraction_from_login_wall"](run)
    assert passed is False
    assert "asks" in evidence


def test_a_real_posting_does_not_exercise_the_login_wall_guard(tmp_path):
    run = build(tmp_path, posting_source=REAL_POSTING, posting=FULL_POSTING)
    assert ck.CHECKERS["refuses_extraction_from_login_wall"](run)[0] is None


def test_a_usable_posting_must_actually_be_extracted(tmp_path):
    run = build(tmp_path, posting_source=REAL_POSTING, posting=FULL_POSTING)
    assert ck.CHECKERS["extracts_posting_when_usable"](run)[0] is True


def test_refusing_a_perfectly_readable_posting_fires_the_twin(tmp_path):
    run = build(tmp_path, posting_source=REAL_POSTING,
                final="内容不足，请粘贴完整 JD。")
    passed, evidence = ck.CHECKERS["extracts_posting_when_usable"](run)
    assert passed is False
    assert "words" in evidence


def test_an_extraction_missing_two_fields_fires_the_twin(tmp_path):
    partial = {k: v for k, v in FULL_POSTING.items()
               if k not in ("salary_range", "application_type")}
    run = build(tmp_path, posting_source=REAL_POSTING, posting=partial)
    passed, evidence = ck.CHECKERS["extracts_posting_when_usable"](run)
    assert passed is False
    assert "application_type" in evidence


# ---- refusal floor ----------------------------------------------------------

def test_the_refusal_floor_passes_when_it_refuses_cleanly(tmp_path):
    run = build(tmp_path, assessment={"verdict": "insufficient_evidence"},
                assessment_md="证据不足—不出结论。缺 CV 正文。\n")
    assert ck.CHECKERS["refusal_floor_fires"](run)[0] is True


def test_a_refusal_that_still_prints_a_verdict_fires(tmp_path):
    run = build(tmp_path, assessment={"verdict": "insufficient_evidence"},
                assessment_md="证据不足—不出结论。\n投递建议：值得投\n")
    passed, evidence = ck.CHECKERS["refusal_floor_fires"](run)
    assert passed is False
    assert "值得投" in evidence


def test_producing_a_confident_verdict_on_thin_input_fires(tmp_path):
    run = build(tmp_path, assessment={"verdict": "worth_applying"},
                assessment_md=COVERAGE_MD)
    passed, evidence = ck.CHECKERS["refusal_floor_fires"](run)
    assert passed is False
    assert "worth_applying" in evidence


def test_the_decoy_requires_a_verdict_a_count_and_a_disclaimer(tmp_path):
    run = build(tmp_path, assessment={"verdict": "worth_applying"},
                assessment_md=COVERAGE_MD)
    assert ck.CHECKERS["verdict_produced_when_inputs_suffice"](run)[0] is True


def test_refusing_on_sufficient_input_fires_the_twin(tmp_path):
    run = build(tmp_path, assessment={"verdict": "insufficient_evidence"},
                assessment_md="证据不足—不出结论。\n")
    passed, evidence = ck.CHECKERS["verdict_produced_when_inputs_suffice"](run)
    assert passed is False
    assert "insufficient_evidence" in evidence


def test_a_verdict_without_the_disclaimer_fires_the_twin(tmp_path):
    run = build(tmp_path, assessment={"verdict": "worth_applying"},
                assessment_md="must-have 强证据：   3 of 5\n投递建议：值得投\n")
    passed, evidence = ck.CHECKERS["verdict_produced_when_inputs_suffice"](run)
    assert passed is False
    assert "disclaimer" in evidence


# ---- expired conventions ----------------------------------------------------

BANNER_MD = ("## 市场惯例\n\n【已过复核期】\n"
             "> Check the company in the public register of recognised sponsors\n")


def test_an_expired_card_rendered_with_the_banner_passes(tmp_path):
    run = build(tmp_path, assessment_md=BANNER_MD,
                conventions=["nl-recognised-sponsor-gate"],
                assessment={"verdict": "worth_applying",
                            "conventions_rendered": ["nl-recognised-sponsor-gate"]})
    assert ck.CHECKERS["expired_convention_banner_shown"](run)[0] is True


def test_an_expired_card_rendered_without_the_banner_fires(tmp_path):
    run = build(tmp_path, assessment_md=BANNER_MD.replace("【已过复核期】\n", ""),
                assessment={"verdict": "worth_applying",
                            "conventions_rendered": ["nl-recognised-sponsor-gate"]})
    passed, evidence = ck.CHECKERS["expired_convention_banner_shown"](run)
    assert passed is False
    assert "已过复核期" in evidence


def test_refusing_to_render_an_expired_card_at_all_also_fires(tmp_path):
    run = build(tmp_path, assessment_md="市场惯例：跳过。\n",
                assessment={"verdict": "worth_applying",
                            "conventions_rendered": []})
    passed, evidence = ck.CHECKERS["expired_convention_banner_shown"](run)
    assert passed is False
    assert "renders no convention" in evidence


def test_a_banner_on_a_current_table_fires_the_twin(tmp_path):
    run = build(tmp_path, assessment_md=BANNER_MD,
                assessment={"verdict": "worth_applying",
                            "conventions_rendered": ["nl-recognised-sponsor-gate"]})
    passed, evidence = ck.CHECKERS["no_expiry_banner_on_current_table"](run)
    assert passed is False
    assert "已过复核期" in evidence


def test_a_current_card_without_a_banner_is_quiet(tmp_path):
    run = build(tmp_path, assessment_md=BANNER_MD.replace("【已过复核期】\n", ""),
                assessment={"verdict": "worth_applying",
                            "conventions_rendered": ["nl-recognised-sponsor-gate"]})
    assert ck.CHECKERS["no_expiry_banner_on_current_table"](run)[0] is True


# ---- the CI half of the expiry rule -----------------------------------------

def test_the_ci_half_of_the_expiry_rule_is_wired(tmp_path):
    run = build(tmp_path)
    passed, evidence = ck.CHECKERS["expired_convention_fails_ci"](run)
    assert passed is True, evidence
    assert "EXPIRED" in evidence


def test_the_shipped_market_tables_are_silent(tmp_path):
    run = build(tmp_path)
    passed, evidence = ck.CHECKERS["current_tables_pass_ci"](run)
    assert passed is True, evidence
    # Pin the count. Without this the checker passes vacuously on an empty glob,
    # which is exactly how a wrong path went unnoticed: "all 0 shipped tables clean"
    # reads like success.
    assert evidence == "all 5 shipped tables clean", evidence


# ---- generality: the same rules, in the other language and at other sizes ----

def test_the_field_list_is_the_skill_s_own_posting_schema():
    """`POSTING_FIELDS` is a fifth copy of a schema already written in four files.
    A fifth copy is tolerable only while it cannot drift silently: rename or add a
    field in the skill and this goes red, instead of the twin quietly reporting a
    missing field nobody writes any more."""
    assert list(ck.POSTING_FIELDS) == CANONICAL
    assert list(ck.POSTING_FIELDS) == TWELVE


# One page per wall spelling, and each page trips ONLY its own spelling. A page
# carrying two of them (「登录后查看…请登录」) keeps passing after one is deleted
# from the regex, so the deletion is invisible — measured: removing 登录后查看
# broke nothing until these were split.
WALL_PAGES = {
    "sign in": "Sign in to view this job\n",
    "log in": "Log in to continue to the job description.\n",
    "登录后查看": "登录后查看完整职位描述\n",
    "create an account": "Create an account to see the full description.\n",
    "verify you are": "Please verify you are human before continuing.\n",
    "请登录": "请登录以查看该职位。\n",
    "同意 cookie": "同意 cookie 才能继续浏览本页。\n",
    "accept cookies": "You must accept cookies to view this page.\n",
}


def test_every_wall_spelling_has_a_page_that_trips_only_it():
    """Coverage, pinned to the regex itself. Add a spelling to `_WALL` without a
    sample here and this goes red, instead of the new alternative shipping
    untested — and each page matching exactly one alternative is what makes the
    per-page tests able to notice a deleted one."""
    inner = re.match(r"^\(\?i\)\((.*)\)$", ck._WALL.pattern, re.S)
    assert inner, ck._WALL.pattern
    alternatives = inner.group(1).split("|")
    assert sorted(alternatives) == sorted(WALL_PAGES), alternatives
    for spelling, page in WALL_PAGES.items():
        found = [m.lower() for m in ck._WALL.findall(page)]
        assert found == [spelling], (spelling, found)


@pytest.mark.parametrize("spelling", sorted(WALL_PAGES))
def test_each_login_wall_spelling_is_read_as_a_wall(tmp_path, spelling):
    """A CN-market run gets 「登录后查看」, not "Sign in"; a cookie interstitial
    gets neither. A guard that only ever sees one spelling passes every run that
    extracted must-haves off a page written in another."""
    run = build(tmp_path, posting_source=WALL_PAGES[spelling],
                posting=FULL_POSTING, final="已抽取岗位要求。")
    passed, evidence = ck.CHECKERS["refuses_extraction_from_login_wall"](run)
    assert passed is False
    assert "must_haves" in evidence


def test_an_english_ask_for_the_full_text_counts_as_a_refusal(tmp_path):
    """The refusal may be written in either language, and the evidence must quote
    the line that carried it rather than a bare None."""
    run = build(tmp_path, posting_source=LOGIN_WALL,
                final="This is a login wall, not the posting. "
                      "Please paste the full job description here.")
    passed, evidence = ck.CHECKERS["refuses_extraction_from_login_wall"](run)
    assert passed is True
    assert "paste the full job description" in evidence


def test_a_long_posting_that_merely_mentions_signing_in_is_still_graded(tmp_path):
    """The wall test is short-page AND wall-wording, in both halves.

    A nine-hundred-word posting whose benefits section says "create an account in
    our portal" is a readable posting. Treating it as a wall would make the guard
    silent (fine) and the DECOY silent too (not fine) — and a decoy that excuses
    itself on any page containing 'sign in' is exactly the hole an always-refuse
    policy walks through.
    """
    wordy = REAL_POSTING + "To apply, create an account in our candidate portal.\n"
    assert ck.CHECKERS["refuses_extraction_from_login_wall"](
        build(tmp_path / "a", posting_source=wordy, posting=FULL_POSTING))[0] is None
    passed, evidence = ck.CHECKERS["extracts_posting_when_usable"](
        build(tmp_path / "b", posting_source=wordy, posting=None,
              final="内容不足，请粘贴完整 JD。"))
    assert passed is False, evidence
    assert "no posting.yaml was written" in evidence


def test_an_english_verdict_leaking_into_a_refusal_is_caught(tmp_path):
    """VERDICTS, not just VERDICT_ZH. An English assessment prints
    `worth_applying`; a refusal that still carries it is not a refusal."""
    run = build(tmp_path, assessment={"verdict": "insufficient_evidence"},
                assessment_md="Insufficient evidence — no conclusion.\n"
                              "Recommendation: worth_applying\n")
    passed, evidence = ck.CHECKERS["refusal_floor_fires"](run)
    assert passed is False
    assert "worth_applying" in evidence


def test_a_refusal_that_still_renders_a_coverage_count_is_not_a_refusal(tmp_path):
    """No verdict word anywhere, and still not a refusal: a coverage count IS a
    conclusion, rendered as arithmetic."""
    run = build(tmp_path, assessment={"verdict": "insufficient_evidence"},
                assessment_md="证据不足—不出结论。\nmust-have 强证据：3 of 5\n")
    passed, evidence = ck.CHECKERS["refusal_floor_fires"](run)
    assert passed is False
    assert "count" in evidence


def test_the_english_disclaimer_satisfies_the_decoy(tmp_path):
    """An English run writes the English disclaimer. Requiring the Chinese one
    would fail every English run for a sentence it correctly translated."""
    run = build(tmp_path, assessment={"verdict": "stretch"},
                assessment_md="must-have evidence: 3 of 5\n"
                              "> This is a count of evidence, "
                              "not a forecast of the outcome.\n")
    passed, evidence = ck.CHECKERS["verdict_produced_when_inputs_suffice"](run)
    assert passed is True, evidence
    assert "not a forecast of the outcome" in evidence


def test_a_verdict_outside_the_closed_set_fires_the_decoy(tmp_path):
    """An invented level is not a verdict. Left unchecked it reads as a pass
    because it is neither the refusal nor a missing field."""
    run = build(tmp_path, assessment={"verdict": "probably_fine"},
                assessment_md=COVERAGE_MD)
    passed, evidence = ck.CHECKERS["verdict_produced_when_inputs_suffice"](run)
    assert passed is False
    assert "probably_fine" in evidence


# ---- the registry ------------------------------------------------------------

ASSESS_TWINS = {
    "refuses_extraction_from_login_wall": "extracts_posting_when_usable",
    "refusal_floor_fires": "verdict_produced_when_inputs_suffice",
    "expired_convention_banner_shown": "no_expiry_banner_on_current_table",
    "expired_convention_fails_ci": "current_tables_pass_ci",
}


def test_every_assess_guard_names_the_checker_that_decides_its_decoy():
    """Three refusal guards, three decoys, and the CI pair. Registered both ways
    round: a guard whose twin is declared in one direction only can be satisfied
    in the eval that names it and nowhere else."""
    for guard, twin in ASSESS_TWINS.items():
        assert guard in ck.CHECKERS, f"{guard} is not registered"
        assert twin in ck.CHECKERS, f"{twin} is not registered"
        assert ck.TWINS.get(guard) == twin
        assert ck.TWINS.get(twin) == guard
        assert ck.TWINS[ck.TWINS[guard]] == guard


def test_the_expiry_fixture_is_stale_and_otherwise_clean():
    """The fixture must produce the expiry finding AND NOTHING ELSE.

    `expired_convention_fails_ci` filters for findings starting with EXPIRED, so a
    fixture that drifts into a second defect — a bad URL, a digit in prose — would
    still let the checker pass while no longer testing the rule it names. Pin the
    whole findings list, not the one line the checker reads.
    """
    import datetime
    import pathlib

    import check_conventions

    fixture = (pathlib.Path(check_conventions.__file__).resolve().parents[1]
               / "evals" / "fixtures" / "conventions" / "expired-nl.yaml")
    findings = check_conventions.check_file(fixture, datetime.date(2026, 8, 9))
    assert len(findings) == 1, findings
    assert findings[0].startswith("EXPIRED_REVIEW_BY: "), findings[0]


# ---- the CI half, pinned to the linter that decides it ----------------------
#
# `assert passed is True and "EXPIRED" in evidence` is satisfied by a checker
# that returns a hardcoded string and never opens the fixture — verified by
# deleting the body and watching the suite stay green. These four bind the
# checker to check_conventions.py's actual answer instead.

def _expiry_fixture():
    import pathlib

    import check_conventions
    return (pathlib.Path(check_conventions.__file__).resolve().parents[1]
            / "evals" / "fixtures" / "conventions" / "expired-nl.yaml")


def test_the_ci_half_quotes_the_linter_s_own_finding(tmp_path):
    """Evidence is a quote, not a sentence about one: what the checker reports
    must be the exact line check_conventions.py returned for the fixture."""
    import datetime

    import check_conventions

    expected = [f for f in check_conventions.check_file(
        _expiry_fixture(), datetime.date(2026, 8, 9)) if f.startswith("EXPIRED")]
    assert expected, "the fixture is not expired at the harness's fixed today"
    passed, evidence = ck.CHECKERS["expired_convention_fails_ci"](build(tmp_path))
    assert passed is True
    assert evidence == expected[0], evidence


def test_the_ci_half_fires_when_the_linter_stops_finding_the_expiry(tmp_path,
                                                                   monkeypatch):
    """The failing half. If check_conventions.py ever stops returning
    EXPIRED_REVIEW_BY — the rule silently unwired, which is the defect this
    checker exists to catch — the checker must say so instead of passing."""
    import check_conventions

    monkeypatch.setattr(check_conventions, "check_file", lambda path, today: [])
    passed, evidence = ck.CHECKERS["expired_convention_fails_ci"](build(tmp_path))
    assert passed is False
    assert "expired-nl.yaml" in evidence


def test_the_shipped_table_twin_fires_when_a_table_is_noisy(tmp_path, monkeypatch):
    """The twin's failing half. It must be able to go red on a real table, or
    'all 5 shipped tables clean' is a sentence the checker prints unconditionally
    and the expiry finding it guards is noise."""
    import check_conventions

    monkeypatch.setattr(check_conventions, "check_file",
                        lambda path, today: ["BAD_DATE: x.added is 'soon'"])
    passed, evidence = ck.CHECKERS["current_tables_pass_ci"](build(tmp_path))
    assert passed is False
    assert "BAD_DATE" in evidence and ".yaml" in evidence


def test_the_shipped_table_twin_fires_when_it_globs_nothing(tmp_path, monkeypatch):
    """An empty glob must be a failure, never 'all 0 shipped tables clean'.
    That sentence reads like success and is how a wrong path survived once."""
    import check_conventions

    monkeypatch.setattr(check_conventions, "CONVENTIONS_DIR", tmp_path / "nowhere")
    passed, evidence = ck.CHECKERS["current_tables_pass_ci"](build(tmp_path))
    assert passed is False
    assert "the path is wrong" in evidence


# ---- a Chinese posting is a posting -----------------------------------------
#
# MEASURED. `_source_words` counted with `re.findall(r"\S+")`, which is blind to
# CJK: a complete 199-character Chinese posting measured as NINE tokens. Two
# consequences, both silent:
#
#   nine < USABLE_MIN_WORDS (300)  -> extracts_posting_when_usable reports
#                                     "not exercised" over a usable posting
#   nine <= WALL_MAX_WORDS  (200)  -> and if any wall word appears, a real
#                                     posting is classified as a login wall
#
# The skill is documented to work in any language and the eval set already
# carries Chinese scenarios, so this switched the assess audits off for a whole
# market rather than failing anywhere a reader would look.

ZH_POSTING = (
    "高级算法工程师（计算机视觉方向）｜上海·浦东新区｜3-5 年经验｜硕士及以上\n"
    "岗位职责：负责工业视觉检测算法的研发与落地，包括表面缺陷检测、视觉定位与"
    "尺寸测量三大方向；主导算法从原型验证到产线部署的完整流程，输出可维护的"
    "工程代码；与硬件、光学和产线工程师协作，解决现场光照变化、振动与节拍约束"
    "下的稳定性问题；参与产线现场调试与试产，跟踪上线后的良率、误检率与节拍"
    "表现，并持续迭代；沉淀算法组件与标注规范，支持新产线快速复制。\n"
    "任职要求：计算机、自动化、电子或相关专业硕士及以上学历；三年以上计算机"
    "视觉算法研发经验，有完整产线落地案例；精通 C++ 与 Python，熟悉 OpenCV、"
    "PyTorch 与常见检测分割网络；理解相机成像、光源选型与标定的基本原理；"
    "具备独立完成算法选型、数据标注方案设计与上线验证的能力；有半导体设备、"
    "锂电或 3C 自动化行业经验者优先；有 GPU 推理优化或模型压缩经验者优先。\n"
    "我们提供：具有竞争力的薪资与年终奖金、完整的真实产线数据、从算法到产品的"
    "完整闭环、以及扁平的技术团队与充分的工程自主权。工作地点为上海浦东，"
    "接受每月一到两次的外地产线出差。")


def test_a_chinese_posting_counts_as_readable_words(tmp_path):
    run = build(tmp_path, posting_source=ZH_POSTING)
    _, words = ck._source_words(run)
    # The blind count, shown here so the test says what it is protecting.
    import re as _re
    blind = len(_re.findall(r"\S+", ZH_POSTING))
    assert blind < ck.USABLE_MIN_WORDS, (
        "this fixture no longer demonstrates the defect")
    assert words >= ck.USABLE_MIN_WORDS, (
        f"a {len(ZH_POSTING)}-character Chinese posting measured {words} words, "
        f"under the {ck.USABLE_MIN_WORDS} that makes a posting usable — the "
        f"extraction audit then reports 'not exercised' over a real posting")


def test_a_chinese_posting_is_not_classified_as_a_login_wall(tmp_path):
    run = build(tmp_path, posting_source=ZH_POSTING)
    text, words = ck._source_words(run)
    assert not ck._is_login_wall(text, words), (
        "a real Chinese posting was read as a login wall")


def test_a_chinese_login_wall_is_still_caught(tmp_path):
    """The fix must not switch the wall detector off for CJK."""
    wall = "请登录后查看该职位。登录 或 注册以继续。继续即表示您接受我们的 cookie 政策。"
    run = build(tmp_path, posting_source=wall)
    text, words = ck._source_words(run)
    assert words < ck.USABLE_MIN_WORDS, words
