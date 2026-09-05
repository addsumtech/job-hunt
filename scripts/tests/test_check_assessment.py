import copy
import datetime
import json

import yaml

import check_assessment as ca
import count_coverage as cc
import enter_mode
import journal
import vocab
from findings import assert_finding, assert_no_finding

TODAY = datetime.date(2026, 8, 9)

BLOCKS = {"blocks": [
    {"id": "CV-001", "source": "cv", "text": "Built a C++ reconstruction pipeline"},
    {"id": "CV-002", "source": "cv", "text": "Ran Slurm jobs on a shared cluster"},
    {"id": "JD-001", "source": "jd", "text": "Five years of C++"},
    {"id": "JD-002", "source": "jd", "text": "You must already hold an EU work permit"},
]}

# A real table uses YAML block scalars with hard wraps, so text_zh arrives with a
# newline in the middle. A card rendered character-for-character reflows it. The
# fixture carries that newline on purpose: without it, CONVENTION_PARAPHRASED could
# be a substring check that fires on correct output and no test would notice.
CONVENTION_ZH = ("投递前先在公开的认可担保方名录里查一下这家公司，\n"
                 "再决定要不要为它定制材料。")
CONVENTION_EN = ("Check the company in the public register of recognised sponsors\n"
                 "before you invest in a tailored application.")

MARKET = {"market": "nl", "conventions": [{
    "id": "nl-recognised-sponsor-gate",
    "text_en": CONVENTION_EN,
    "text_zh": CONVENTION_ZH,
    "applies_when": "A Netherlands role that needs a work-related residence permit.",
    "added": "2026-08-09", "review_by": "2027-08-09",
    "source": {"kind": "published", "publisher": "IND",
               "title": "Highly skilled migrant",
               "url": "https://ind.nl/en/residence-permits/work/highly-skilled-migrant",
               "retrieved": "2026-08-09",
               "quote": "Only an employer recognised by the IND can apply for your permit."},
    "why": "A posting often says nothing either way about sponsor status.",
}]}

ASSESSMENT = {
    "market": "nl", "verdict": "worth_applying", "provisional": False,
    "effort": "evening", "level_direction": "lateral",
    "declared_work_status": "authorized",
    "stated_conditions": [{"type": "work_authorization", "stance": "requires_existing",
                           "evidence": [{"ref": "JD-002"}]}],
    "requirements": [
        {"id": "R1", "kind": "must_have", "text": "Five years of C++", "level": "required",
         "screening": "knockout", "match": "strong", "recency": "current",
         "effort": "quick", "how_to_close": "",
         "evidence": [{"ref": "CV-001"}, {"ref": "JD-001"}]},
        {"id": "R2", "kind": "must_have", "text": "Kubernetes in production",
         "level": "required", "screening": "weighted", "match": "no_evidence",
         "recency": "undated", "effort": "multi_day",
         "how_to_close": "", "evidence": []},
        {"id": "R3", "kind": "responsibility", "text": "Run jobs on a shared cluster",
         "level": "unclear", "screening": "nice_to_have", "match": "strong",
         "recency": "recent", "effort": "quick", "how_to_close": "",
         "evidence": [{"ref": "CV-002"}]},
    ],
    "actions": [{"action": "Read the sponsor register",
                 "acceptance": "Employer found or not found, written down",
                 "when": "before_apply"}],
    "conventions_rendered": ["nl-recognised-sponsor-gate"],
}

DISCLAIMER = ("⚠️ 以上是对证据的清点，不是对结果的预判。每一项都连同它的证据引用一起印出，"
              "分母可以逐条审计；本 skill 不给出面试或录用的可能性估计，也不给 0–100 分。"
              "要不要投，由你决定。")

# The 「那该怎么办」 half, required only on likely_screen_out and blocked.
OTHER_HALF = ("\n## 那该怎么办\n\n"
              "策略：`skill_sprint` 技能冲刺\n\n"
              "| 目标 | 行动 | 验收标准 |\n|---|---|---|\n"
              "| 补上分布式训练 | 移植到 torchrun | 仓库里有两卡运行日志 |\n\n"
              "| 阶段 | 输出物 |\n|---|---|\n"
              "| 第一阶段 | 一份可复现的两卡训练日志 |\n")

# The same half in English. count_coverage.py has --lang {zh,en}, so this is a supported
# output, not a hypothetical one.
OTHER_HALF_EN = ("\n## What to do instead\n\n"
                 "Strategy: `skill_sprint`\n\n"
                 "| Goal | Action | Acceptance criterion |\n|---|---|---|\n"
                 "| Close the orchestration gap | Ship a staging deployment | "
                 "A running deployment a colleague can reach |\n\n"
                 "| Phase | Deliverable |\n|---|---|\n"
                 "| Phase one | A reproducible deployment manifest |\n")


def _skill_root(tmp_path):
    """A skill tree with a modes/assess.md, so enter_mode has real bytes to hash."""
    root = tmp_path / "skill"
    (root / "modes").mkdir(parents=True, exist_ok=True)
    (root / "modes" / "assess.md").write_text(
        "# Mode: assess\n\nThe layer-1.5 file.\n", encoding="utf-8")
    return root


def build(tmp_path, assessment=None, markdown=None, market=None,
          enter=True, receipts=True):
    assessment = copy.deepcopy(assessment or ASSESSMENT)
    tmp_path.mkdir(parents=True, exist_ok=True)
    root = _skill_root(tmp_path)
    (tmp_path / "evidence-blocks.json").write_text(
        json.dumps(BLOCKS, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "fit-assessment.yaml").write_text(
        yaml.safe_dump(assessment, allow_unicode=True, sort_keys=False), encoding="utf-8")
    market_dir = tmp_path / "market"
    market_dir.mkdir(exist_ok=True)
    (market_dir / "nl.yaml").write_text(
        yaml.safe_dump(market or MARKET, allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    if markdown is None:
        counts = cc.coverage(assessment["requirements"])
        block = cc.render_block(assessment, counts, "zh")
        markdown = (
            "# Fit assessment\n\n"
            "## 硬性阻断项\n\n"
            "- **R2** — 该岗位明确要求你已经持有欧盟工作许可。这是法律层面的门槛，"
            "不是表述问题。\n\n"
            "## 计数\n\n"
            "```\n" + block + "\n```\n\n"
            + DISCLAIMER + "\n\n"
            "| 需求 | level | screening | match | 证据 |\n"
            "|---|---|---|---|---|\n"
            "| Five years of C++ | required | knockout | strong | CV-001, JD-001 |\n"
            "| Kubernetes in production | required | weighted | no_evidence | — |\n"
            "| Run jobs on a shared cluster | unclear | nice_to_have | strong | CV-002 |\n\n"
            "## 市场惯例\n\n"
            # Reflowed onto one line, exactly as a renderer would. Character-for-character
            # is about the words, not about where the YAML happened to wrap.
            + CONVENTION_ZH.replace("\n", "") + "\n\n"
            "你的简历没有说明当前的居留身份，因此在这条惯例上无法定位。\n")
    (tmp_path / "fit-assessment.md").write_text(markdown, encoding="utf-8")
    if enter:
        enter_mode.main(["--workspace", str(tmp_path), "--mode", "assess",
                         "--skill-root", str(root)])
    if receipts:
        for gate in ca.UPSTREAM_GATES:
            journal.receipt(tmp_path, gate, {}, "recorded")
    return tmp_path, market_dir, root


# ---------- the quiet case, pinned as hard as the firing case ----------

def test_a_well_formed_assessment_passes_with_no_findings(tmp_path):
    ws, market_dir, root = build(tmp_path)
    assert ca.check(ws, market_dir, TODAY, root) == []


def test_the_cli_passes_and_writes_exactly_one_receipt(tmp_path, capsys):
    ws, market_dir, root = build(tmp_path)
    capsys.readouterr()          # discard enter_mode's own line from the fixture
    assert ca.main(["--workspace", str(ws), "--market-dir", str(market_dir),
                    "--skill-root", str(root), "--today", "2026-08-09"]) == 0
    assert capsys.readouterr().out.strip() == ""
    own = [json.loads(l) for l in
           (ws / "journal.jsonl").read_text(encoding="utf-8").splitlines()
           if json.loads(l).get("gate") == "check_assessment"]
    assert len(own) == 1
    assert own[0]["verdict"] == "pass"


def test_a_no_evidence_row_with_an_empty_list_is_not_unsourced(tmp_path):
    ws, market_dir, root = build(tmp_path)
    assert not [f for f in ca.check(ws, market_dir, TODAY, root)
                if f.startswith("ROW_UNSOURCED")]


def test_the_english_disclaimer_is_accepted_too(tmp_path):
    ws, market_dir, root = build(tmp_path)
    md = (ws / "fit-assessment.md").read_text(encoding="utf-8").replace(
        DISCLAIMER, "⚠️ This is a count of evidence, not a forecast of the outcome. "
                    "Whether to apply is your call.")
    (ws / "fit-assessment.md").write_text(md, encoding="utf-8")
    assert not [f for f in ca.check(ws, market_dir, TODAY, root)
                if f.startswith("NO_DISCLAIMER")]


def test_a_convention_reflowed_off_the_yaml_wrap_points_is_not_a_paraphrase(tmp_path):
    # The fixture's text_zh has a hard newline in it; the rendered card does not.
    # Whitespace is not the claim.
    ws, market_dir, root = build(tmp_path)
    assert "\n" in CONVENTION_ZH
    assert CONVENTION_ZH not in (ws / "fit-assessment.md").read_text(encoding="utf-8")
    assert not [f for f in ca.check(ws, market_dir, TODAY, root)
                if f.startswith("CONVENTION_PARAPHRASED")]


def test_a_disqualifier_section_that_genuinely_paraphrases_passes(tmp_path):
    # Chinese prose that names the barrier correctly and shares no substring with the
    # posting's English wording. This is what correct output looks like.
    broken = copy.deepcopy(ASSESSMENT)
    broken["requirements"][1]["screening"] = "knockout"
    ws, market_dir, root = build(tmp_path, assessment=broken)
    md = (ws / "fit-assessment.md").read_text(encoding="utf-8").replace(
        "- **R2** — 该岗位明确要求你已经持有欧盟工作许可。这是法律层面的门槛，不是表述问题。",
        "- **R2** — 生产环境的容器编排经验是硬门槛，你目前没有可引用的证据。")
    (ws / "fit-assessment.md").write_text(md, encoding="utf-8")
    assert not [f for f in ca.check(ws, market_dir, TODAY, root)
                if f.startswith("DISQUALIFIER")]


def test_the_other_half_is_not_demanded_on_an_ordinary_verdict(tmp_path):
    ws, market_dir, root = build(tmp_path)
    assert not [f for f in ca.check(ws, market_dir, TODAY, root)
                if f.startswith("NO_STRATEGY") or f.startswith("NO_ACCEPTANCE")]


def test_a_complete_other_half_on_likely_screen_out_passes(tmp_path):
    broken = copy.deepcopy(ASSESSMENT)
    broken["verdict"] = "likely_screen_out"
    ws, market_dir, root = build(tmp_path, assessment=broken)
    md = (ws / "fit-assessment.md").read_text(encoding="utf-8") + OTHER_HALF
    (ws / "fit-assessment.md").write_text(md, encoding="utf-8")
    findings = ca.check(ws, market_dir, TODAY, root)
    assert not [f for f in findings if f.startswith("NO_STRATEGY")
                or f.startswith("STRATEGY_NOT_UNIQUE")
                or f.startswith("NO_ACCEPTANCE")]


# ---------- the two fields the card PRINTS ----------

# The §8 refusal: no verdict from the five, no coverage block, and therefore no
# level_direction and no effort either. Every new finding below must stay silent
# here — `counts["invalid"]` is appended BEFORE `refusing` is computed, so an
# unscoped check hard-fails the one path the mode file designs for.
REFUSAL = {"market": vocab.NO_MARKET, "verdict": vocab.REFUSAL, "provisional": False,
           "requirements": [], "actions": [], "conventions_rendered": []}
REFUSAL_MD = ("# Fit assessment\n\n## 证据不足\n\n"
              "岗位原文只取到一个登录墙，读不到任何 requirements 段落。"
              "请把完整的岗位描述贴给我，我再重新评估。\n")


def test_an_assessment_that_judged_no_level_direction_says_so(tmp_path):
    broken = copy.deepcopy(ASSESSMENT)
    del broken["level_direction"]
    ws, market_dir, root = build(tmp_path, assessment=broken)
    assert any(f.startswith("MISSING_LEVEL_DIRECTION:")
               for f in ca.check(ws, market_dir, TODAY, root))


def test_an_assessment_that_judged_no_effort_says_so(tmp_path):
    """The shipped card said 「可补缺口所需投入：补不上」 beside 「强烈建议投」 on an
    assessment that had judged neither. Nothing reported it: COUNT_MISMATCH
    compares render_block against render_block, so two identical invented
    strings compare equal."""
    broken = copy.deepcopy(ASSESSMENT)
    del broken["effort"]
    ws, market_dir, root = build(tmp_path, assessment=broken)
    assert any(f.startswith("MISSING_EFFORT:")
               for f in ca.check(ws, market_dir, TODAY, root))


def test_an_out_of_enum_value_for_either_field_is_reported(tmp_path):
    broken = copy.deepcopy(ASSESSMENT)
    broken["level_direction"] = "sideways"
    broken["effort"] = "a_weekend"
    ws, market_dir, root = build(tmp_path, assessment=broken)
    findings = ca.check(ws, market_dir, TODAY, root)
    assert any(f.startswith("MISSING_LEVEL_DIRECTION:") and "sideways" in f
               for f in findings)
    assert any(f.startswith("MISSING_EFFORT:") and "a_weekend" in f for f in findings)


def test_both_fields_present_and_in_enum_are_quiet(tmp_path):
    ws, market_dir, root = build(tmp_path)
    assert not [f for f in ca.check(ws, market_dir, TODAY, root)
                if f.startswith("MISSING_EFFORT")
                or f.startswith("MISSING_LEVEL_DIRECTION")]


def test_the_refusal_path_is_clean_with_neither_field(tmp_path):
    """§8 by design has no verdict from the five, no coverage block, and no
    reason to have judged either field. A check that fired here would fail the
    skill's own refusal floor — the one output that is always correct."""
    ws, market_dir, root = build(tmp_path, assessment=REFUSAL, markdown=REFUSAL_MD)
    assert ca.check(ws, market_dir, TODAY, root) == []


def test_the_refusal_path_still_exits_zero(tmp_path, capsys):
    ws, market_dir, root = build(tmp_path, assessment=REFUSAL, markdown=REFUSAL_MD)
    capsys.readouterr()
    assert ca.main(["--workspace", str(ws), "--market-dir", str(market_dir),
                    "--skill-root", str(root), "--today", "2026-08-09"]) == 0
    assert capsys.readouterr().out.strip() == ""


# ---------- the two work-authorization fields, and the notices they wake ----------

def test_a_work_auth_conflict_now_fires_and_must_be_attached(tmp_path):
    """Reachability, end to end. Both these fields were named in no mode file, so
    NOTICE_WORK_AUTH_CONFLICT could not fire on any real run — the model was never
    told the fields existed."""
    broken = copy.deepcopy(ASSESSMENT)
    broken["declared_work_status"] = "needs_sponsorship"
    ws, market_dir, root = build(tmp_path, assessment=broken)
    assert any(f.startswith("NOTICE_NOT_ATTACHED:") and "WORK_AUTH_CONFLICT" in f
               for f in ca.check(ws, market_dir, TODAY, root))


def test_a_work_auth_verify_notice_fires_on_a_student_route(tmp_path):
    broken = copy.deepcopy(ASSESSMENT)
    broken["declared_work_status"] = "student_or_graduate"
    ws, market_dir, root = build(tmp_path, assessment=broken)
    assert any(f.startswith("NOTICE_NOT_ATTACHED:") and "WORK_AUTH_VERIFY" in f
               for f in ca.check(ws, market_dir, TODAY, root))


def test_attaching_the_work_auth_notice_clears_it(tmp_path):
    broken = copy.deepcopy(ASSESSMENT)
    broken["declared_work_status"] = "needs_sponsorship"
    ws, market_dir, root = build(tmp_path, assessment=broken)
    md = (ws / "fit-assessment.md").read_text(encoding="utf-8")
    (ws / "fit-assessment.md").write_text(
        md + "\n> 岗位要求已持有工作许可，而你声明需要担保：这两条看起来冲突，"
             "请你自己向雇主核实。\n", encoding="utf-8")
    assert not [f for f in ca.check(ws, market_dir, TODAY, root)
                if f.startswith("NOTICE_NOT_ATTACHED")]


def test_a_misspelled_work_status_is_reported_not_silently_ignored(tmp_path):
    """`needs-sponsorship` with a hyphen makes work_authorization_alignment
    return None, which is indistinguishable from 'the two agree'. The notice
    switches itself off and the card looks clean."""
    broken = copy.deepcopy(ASSESSMENT)
    broken["declared_work_status"] = "needs-sponsorship"
    ws, market_dir, root = build(tmp_path, assessment=broken)
    assert any(f.startswith("BAD_WORK_STATUS:") and "needs-sponsorship" in f
               for f in ca.check(ws, market_dir, TODAY, root))


def test_a_misspelled_stance_or_condition_type_is_reported(tmp_path):
    broken = copy.deepcopy(ASSESSMENT)
    broken["declared_work_status"] = "needs_sponsorship"
    broken["stated_conditions"][0]["stance"] = "requires-existing"
    ws, market_dir, root = build(tmp_path, assessment=broken)
    findings = ca.check(ws, market_dir, TODAY, root)
    assert any(f.startswith("BAD_STATED_CONDITION:") and "requires-existing" in f
               for f in findings)
    broken["stated_conditions"][0]["stance"] = "requires_existing"
    broken["stated_conditions"][0]["type"] = "visa"
    ws2, market_dir2, root2 = build(tmp_path / "b", assessment=broken)
    assert any(f.startswith("BAD_STATED_CONDITION:") and "visa" in f
               for f in ca.check(ws2, market_dir2, TODAY, root2))


def test_every_legal_work_status_and_stance_is_quiet(tmp_path):
    """The quiet case, over the whole closed set rather than one sample of it.
    A value the schema tells the model to write must never be a finding."""
    for index, status in enumerate(vocab.WORK_STATUS):
        for stance in vocab.STANCE:
            ok = copy.deepcopy(ASSESSMENT)
            ok["declared_work_status"] = status
            ok["stated_conditions"][0]["stance"] = stance
            ws, market_dir, root = build(tmp_path / f"{index}-{stance}", assessment=ok)
            assert not [f for f in ca.check(ws, market_dir, TODAY, root)
                        if f.startswith("BAD_WORK_STATUS")
                        or f.startswith("BAD_STATED_CONDITION")
                        or f.startswith("WARN_NO_WORK_STATUS")]


def test_an_unrecorded_work_status_warns_without_failing_the_gate(tmp_path, capsys):
    """§4 already makes the model ASK. Not writing the answer down is worth a
    line, but it is not worth refusing the card: an absent status suppresses the
    notices, which is the safe direction, and §4's knockout row is the primary
    path with NO_DISQUALIFIER_SECTION behind it."""
    broken = copy.deepcopy(ASSESSMENT)
    del broken["declared_work_status"]
    ws, market_dir, root = build(tmp_path, assessment=broken)
    findings = ca.check(ws, market_dir, TODAY, root)
    assert any(f.startswith("WARN_NO_WORK_STATUS:") for f in findings)
    assert not [f for f in findings if not f.startswith("WARN_")]
    capsys.readouterr()
    assert ca.main(["--workspace", str(ws), "--market-dir", str(market_dir),
                    "--skill-root", str(root), "--today", "2026-08-09"]) == 0


def test_the_refusal_path_is_not_asked_for_a_work_status(tmp_path):
    ws, market_dir, root = build(tmp_path, assessment=REFUSAL, markdown=REFUSAL_MD)
    assert not [f for f in ca.check(ws, market_dir, TODAY, root)
                if "WORK_STATUS" in f]


# ---------- the layer-1.5 backstop ----------

def test_no_mode_entry_fails(tmp_path, capsys):
    ws, market_dir, root = build(tmp_path, enter=False)
    assert any(f.startswith("NO_MODE_ENTRY:")
               for f in ca.check(ws, market_dir, TODAY, root))


def test_an_edited_mode_file_invalidates_the_entry(tmp_path):
    ws, market_dir, root = build(tmp_path)
    (root / "modes" / "assess.md").write_text("# Mode: assess\n\nrewritten\n",
                                              encoding="utf-8")
    assert any(f.startswith("MODE_FILE_CHANGED:")
               for f in ca.check(ws, market_dir, TODAY, root))


def test_an_upstream_gate_that_never_ran_is_not_a_clean_run(tmp_path):
    ws, market_dir, root = build(tmp_path, receipts=False)
    findings = ca.check(ws, market_dir, TODAY, root)
    assert any(f.startswith("MISSING_RECEIPT:") and "count_coverage" in f
               for f in findings)


def test_an_upstream_gate_that_failed_is_reported(tmp_path):
    ws, market_dir, root = build(tmp_path)
    journal.receipt(ws, "lint_no_prediction", {}, "fail", ["PERCENT: x"])
    assert any(f.startswith("UPSTREAM_FAILED:") and "lint_no_prediction" in f
               for f in ca.check(ws, market_dir, TODAY, root))


# ---------- the firing cases ----------

def test_a_row_claiming_a_match_with_no_resolvable_ref_fails(tmp_path):
    broken = copy.deepcopy(ASSESSMENT)
    broken["requirements"][0]["evidence"] = [{"ref": "CV-999"}]
    ws, market_dir, root = build(tmp_path, assessment=broken)
    findings = ca.check(ws, market_dir, TODAY, root)
    assert any(f.startswith("ROW_UNSOURCED:") and "R1" in f for f in findings)


def test_a_missing_disclaimer_fails(tmp_path):
    ws, market_dir, root = build(tmp_path)
    md = (ws / "fit-assessment.md").read_text(encoding="utf-8").replace(DISCLAIMER, "")
    (ws / "fit-assessment.md").write_text(md, encoding="utf-8")
    assert any(f.startswith("NO_DISCLAIMER:")
               for f in ca.check(ws, market_dir, TODAY, root))


def test_a_blocking_row_with_no_disqualifier_section_fails(tmp_path):
    broken = copy.deepcopy(ASSESSMENT)
    broken["requirements"][1]["screening"] = "knockout"
    ws, market_dir, root = build(tmp_path, assessment=broken)
    md = (ws / "fit-assessment.md").read_text(encoding="utf-8")
    head, _, tail = md.partition("## 计数")
    (ws / "fit-assessment.md").write_text("# Fit assessment\n\n## 计数" + tail,
                                          encoding="utf-8")
    assert any(f.startswith("NO_DISQUALIFIER_SECTION:")
               for f in ca.check(ws, market_dir, TODAY, root))


def test_a_disqualifier_section_that_omits_the_row_id_fails(tmp_path):
    broken = copy.deepcopy(ASSESSMENT)
    broken["requirements"][1]["screening"] = "knockout"
    ws, market_dir, root = build(tmp_path, assessment=broken)
    md = (ws / "fit-assessment.md").read_text(encoding="utf-8").replace(
        "- **R2** —", "- 有一条硬门槛 —")
    (ws / "fit-assessment.md").write_text(md, encoding="utf-8")
    assert any(f.startswith("DISQUALIFIER_NOT_NAMED:") and "R2" in f
               for f in ca.check(ws, market_dir, TODAY, root))


def test_a_disqualifier_named_only_after_the_verdict_fails(tmp_path):
    broken = copy.deepcopy(ASSESSMENT)
    broken["requirements"][1]["screening"] = "knockout"
    ws, market_dir, root = build(tmp_path, assessment=broken)
    md = (ws / "fit-assessment.md").read_text(encoding="utf-8")
    head, _, tail = md.partition("## 计数")
    moved = ("# Fit assessment\n\n## 计数" + tail
             + "\n## 硬性阻断项\n\n- **R2** — 生产环境的容器编排经验是硬门槛。\n")
    (ws / "fit-assessment.md").write_text(moved, encoding="utf-8")
    assert any(f.startswith("DISQUALIFIER_AFTER_VERDICT:")
               for f in ca.check(ws, market_dir, TODAY, root))


def test_a_fired_notice_that_is_not_attached_fails(tmp_path):
    broken = copy.deepcopy(ASSESSMENT)
    broken["verdict"] = "strong_apply"
    broken["effort"] = "multi_day"
    ws, market_dir, root = build(tmp_path, assessment=broken)
    findings = ca.check(ws, market_dir, TODAY, root)
    assert any(f.startswith("NOTICE_NOT_ATTACHED:") and "NOTICE_VERDICT_EFFORT" in f
               for f in findings)


def test_attaching_the_notice_text_clears_it(tmp_path):
    broken = copy.deepcopy(ASSESSMENT)
    broken["verdict"] = "strong_apply"
    broken["effort"] = "multi_day"
    ws, market_dir, root = build(tmp_path, assessment=broken)
    md = (ws / "fit-assessment.md").read_text(encoding="utf-8")
    (ws / "fit-assessment.md").write_text(
        md + "\n> 结论与投入互相矛盾：请以下面的需求表为准。\n", encoding="utf-8")
    assert not [f for f in ca.check(ws, market_dir, TODAY, root)
                if f.startswith("NOTICE_NOT_ATTACHED")]


def test_a_hand_edited_count_fails(tmp_path):
    ws, market_dir, root = build(tmp_path)
    md = (ws / "fit-assessment.md").read_text(encoding="utf-8").replace(
        "1 of 2", "2 of 2")
    (ws / "fit-assessment.md").write_text(md, encoding="utf-8")
    assert any(f.startswith("COUNT_MISMATCH:")
               for f in ca.check(ws, market_dir, TODAY, root))


def test_a_paraphrased_convention_fails(tmp_path):
    ws, market_dir, root = build(tmp_path)
    md = (ws / "fit-assessment.md").read_text(encoding="utf-8").replace(
        CONVENTION_ZH.replace("\n", ""),
        "你必须先在名录里查到这家公司，否则不要投。")
    (ws / "fit-assessment.md").write_text(md, encoding="utf-8")
    assert any(f.startswith("CONVENTION_PARAPHRASED:") for f in
               ca.check(ws, market_dir, TODAY, root))


def test_an_unknown_convention_id_fails(tmp_path):
    broken = copy.deepcopy(ASSESSMENT)
    broken["conventions_rendered"] = ["nl-invented-by-the-model"]
    ws, market_dir, root = build(tmp_path, assessment=broken)
    assert any(f.startswith("CONVENTION_UNKNOWN_ID:")
               for f in ca.check(ws, market_dir, TODAY, root))


def test_a_prediction_word_in_the_rendered_file_fails(tmp_path):
    ws, market_dir, root = build(tmp_path)
    md = (ws / "fit-assessment.md").read_text(encoding="utf-8")
    (ws / "fit-assessment.md").write_text(md + "\n你是一个很强的候选人，录取率不低。\n",
                                          encoding="utf-8")
    assert any(f.startswith("PREDICTION_WORD:")
               for f in ca.check(ws, market_dir, TODAY, root))


def test_a_block_id_left_in_prose_fails(tmp_path):
    ws, market_dir, root = build(tmp_path)
    md = (ws / "fit-assessment.md").read_text(encoding="utf-8")
    (ws / "fit-assessment.md").write_text(md + "\n你的 C++ 经历（CV-001）很对口。\n",
                                          encoding="utf-8")
    assert any(f.startswith("STRIPPED_ID:")
               for f in ca.check(ws, market_dir, TODAY, root))


def test_a_refusal_that_still_prints_a_verdict_fails(tmp_path):
    broken = copy.deepcopy(ASSESSMENT)
    broken["verdict"] = vocab.REFUSAL
    ws, market_dir, root = build(tmp_path, assessment=broken)
    assert any(f.startswith("REFUSAL_WITH_VERDICT:")
               for f in ca.check(ws, market_dir, TODAY, root))


def test_a_provisional_discover_verdict_may_not_be_carried_in(tmp_path):
    broken = copy.deepcopy(ASSESSMENT)
    broken["provisional"] = True
    ws, market_dir, root = build(tmp_path, assessment=broken)
    assert any(f.startswith("PROVISIONAL_VERDICT:")
               for f in ca.check(ws, market_dir, TODAY, root))


def test_a_market_with_no_table_is_fine_only_if_nothing_was_rendered(tmp_path):
    broken = copy.deepcopy(ASSESSMENT)
    broken["market"] = vocab.NO_MARKET          # "other", never "none"
    broken["conventions_rendered"] = []
    ws, market_dir, root = build(tmp_path, assessment=broken)
    assert not [f for f in ca.check(ws, market_dir, TODAY, root)
                if f.startswith("CONVENTION")]
    broken["conventions_rendered"] = ["nl-recognised-sponsor-gate"]
    ws2, market_dir2, root2 = build(tmp_path / "b", assessment=broken)
    assert any(f.startswith("CONVENTION_UNKNOWN_ID:")
               for f in ca.check(ws2, market_dir2, TODAY, root2))


# ---------- the other half, on the two verdicts that require it ----------

def test_a_screen_out_verdict_with_no_strategy_fails(tmp_path):
    broken = copy.deepcopy(ASSESSMENT)
    broken["verdict"] = "blocked"
    ws, market_dir, root = build(tmp_path, assessment=broken)
    findings = ca.check(ws, market_dir, TODAY, root)
    assert any(f.startswith("NO_STRATEGY_SECTION:") for f in findings)
    assert any(f.startswith("NO_ACCEPTANCE_COLUMN:") and "验收标准" in f
               for f in findings)
    assert any(f.startswith("NO_ACCEPTANCE_COLUMN:") and "输出物" in f
               for f in findings)


def test_a_menu_of_strategies_is_not_a_recommendation(tmp_path):
    broken = copy.deepcopy(ASSESSMENT)
    broken["verdict"] = "likely_screen_out"
    ws, market_dir, root = build(tmp_path, assessment=broken)
    md = (ws / "fit-assessment.md").read_text(encoding="utf-8") + OTHER_HALF + \
        "\n也可以考虑 `reposition` 重新定位。\n"
    (ws / "fit-assessment.md").write_text(md, encoding="utf-8")
    assert any(f.startswith("STRATEGY_NOT_UNIQUE:")
               for f in ca.check(ws, market_dir, TODAY, root))


def test_an_english_card_with_a_knockout_gap_is_quiet(tmp_path):
    # The quiet case for every constant that keys on a heading or a column name. The
    # base fixture has R2 as `weighted`, so the disqualifier branch never runs on it —
    # which is exactly how a Chinese-only constant got shipped once already. Here the
    # branch runs, the card is English, and a correct card must produce no finding.
    broken = copy.deepcopy(ASSESSMENT)
    broken["requirements"][1]["screening"] = "knockout"
    broken["verdict"] = "blocked"
    ws, market_dir, root = build(tmp_path, assessment=broken)
    md = ((ws / "fit-assessment.md").read_text(encoding="utf-8")
          .replace("## 硬性阻断项", "## Hard blockers")
          .replace("- **R2** — 该岗位明确要求你已经持有欧盟工作许可。这是法律层面的门槛，"
                   "不是表述问题。",
                   "- **R2** — production container orchestration is a hard requirement "
                   "here and there is nothing in the CV to cite for it.")
          + OTHER_HALF_EN)
    (ws / "fit-assessment.md").write_text(md, encoding="utf-8")
    findings = ca.check(ws, market_dir, TODAY, root)
    assert not [f for f in findings
                if f.startswith("NO_DISQUALIFIER_SECTION")
                or f.startswith("DISQUALIFIER_NOT_NAMED")
                or f.startswith("NO_STRATEGY_SECTION")
                or f.startswith("STRATEGY_NOT_UNIQUE")
                or f.startswith("NO_ACCEPTANCE_COLUMN")], findings


def test_a_rejected_strategy_named_outside_the_section_is_not_a_menu(tmp_path):
    # 「不是 apply_anyway，而是 skill_sprint」 is how a recommendation is normally
    # written. Counted over the whole file it reads as two strategies; the count is
    # scoped to the section so that it does not.
    broken = copy.deepcopy(ASSESSMENT)
    broken["verdict"] = "likely_screen_out"
    ws, market_dir, root = build(tmp_path, assessment=broken)
    md = ((ws / "fit-assessment.md").read_text(encoding="utf-8")
          + "\n这里不是 `apply_anyway` 的场景。\n" + OTHER_HALF)
    (ws / "fit-assessment.md").write_text(md, encoding="utf-8")
    findings = ca.check(ws, market_dir, TODAY, root)
    assert not [f for f in findings if f.startswith("STRATEGY_NOT_UNIQUE")
                or f.startswith("NO_STRATEGY_SECTION")], findings


def test_a_roadmap_without_its_deliverable_column_fails(tmp_path):
    broken = copy.deepcopy(ASSESSMENT)
    broken["verdict"] = "likely_screen_out"
    ws, market_dir, root = build(tmp_path, assessment=broken)
    md = ((ws / "fit-assessment.md").read_text(encoding="utf-8")
          + OTHER_HALF.replace("输出物", "备注"))
    (ws / "fit-assessment.md").write_text(md, encoding="utf-8")
    findings = ca.check(ws, market_dir, TODAY, root)
    assert any(f.startswith("NO_ACCEPTANCE_COLUMN:") and "输出物" in f
               for f in findings)
    assert not [f for f in findings if f.startswith("NO_STRATEGY_SECTION")]


# ---------- convention expiry: CI is hard, runtime is a banner ----------

def test_an_expired_table_does_not_stop_the_skill_working(tmp_path):
    # Spec §10: 「惯例过期 | CI lint 报错；运行时不拒绝渲染，改打「已过复核期」横幅」.
    # A date passing while the code did not change must not stop the skill.
    market = copy.deepcopy(MARKET)
    market["conventions"][0]["review_by"] = "2026-08-08"
    ws, market_dir, root = build(tmp_path, market=market)
    md = (ws / "fit-assessment.md").read_text(encoding="utf-8").replace(
        "## 市场惯例\n\n", "## 市场惯例\n\n> ⚠️ 已过复核期\n\n")
    (ws / "fit-assessment.md").write_text(md, encoding="utf-8")
    findings = ca.check(ws, market_dir, TODAY, root)
    assert any(f.startswith("WARN_EXPIRED_REVIEW_BY:") for f in findings)
    assert not [f for f in findings if not f.startswith("WARN_")]
    assert ca.main(["--workspace", str(ws), "--market-dir", str(market_dir),
                    "--skill-root", str(root), "--today", "2026-08-09"]) == 0


def test_the_english_stale_banner_satisfies_the_same_rule(tmp_path):
    # STALE_BANNER was the last unpaired anchor in an otherwise bilingual gate,
    # and it starts mattering when the first `review_by` passes (2026-11-09), not
    # today — which is exactly the kind of defect that ships. Sentence-initial is
    # the natural rendering of an English banner, so the anchor is matched
    # case-insensitively: "Past its review date — …" is the same banner.
    market = copy.deepcopy(MARKET)
    market["conventions"][0]["review_by"] = "2026-08-08"
    ws, market_dir, root = build(tmp_path, market=market)
    md = (ws / "fit-assessment.md").read_text(encoding="utf-8").replace(
        "## 市场惯例\n\n",
        "## 市场惯例\n\n> ⚠️ Past its review date — re-check before relying on it.\n\n")
    (ws / "fit-assessment.md").write_text(md, encoding="utf-8")
    findings = ca.check(ws, market_dir, TODAY, root)
    assert not [f for f in findings if f.startswith("MISSING_STALE_BANNER")], findings
    assert any(f.startswith("WARN_EXPIRED_REVIEW_BY:") for f in findings)


def test_an_expired_entry_rendered_without_the_banner_fails(tmp_path):
    market = copy.deepcopy(MARKET)
    market["conventions"][0]["review_by"] = "2026-08-08"
    ws, market_dir, root = build(tmp_path, market=market)
    findings = ca.check(ws, market_dir, TODAY, root)
    assert any(f.startswith("MISSING_STALE_BANNER:")
               and "nl-recognised-sponsor-gate" in f for f in findings)


def test_a_hard_table_defect_still_fails_the_assessment(tmp_path):
    # Only EXPIRED_REVIEW_BY is downgraded. Everything else the table lint finds is
    # still a reason not to show this card to anyone.
    market = copy.deepcopy(MARKET)
    market["conventions"][0]["text_en"] = "The 30% ruling is administered here."
    ws, market_dir, root = build(tmp_path, market=market)
    assert any(f.startswith("PERCENT_IN_PROSE:")
               for f in ca.check(ws, market_dir, TODAY, root))


# ---------- could not run ----------

def test_missing_inputs_exit_two_and_still_leave_exactly_one_receipt(tmp_path, capsys):
    assert ca.main(["--workspace", str(tmp_path)]) == 2
    assert "fit-assessment.yaml" in capsys.readouterr().err
    receipts = [json.loads(line) for line in
                (tmp_path / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(receipts) == 1
    assert receipts[0]["gate"] == "check_assessment"
    assert receipts[0]["verdict"] == "could_not_run"


def test_a_workspace_that_does_not_exist_writes_no_journal(tmp_path, capsys):
    missing = tmp_path / "nope"
    assert ca.main(["--workspace", str(missing)]) == 2
    assert not missing.exists()
    assert "does not exist" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Two gates running the same lint must run the SAME lint.
#
# Found 2026-09-05. lint_no_prediction gained a capture-corpus masking on
# 2026-09-02 so that an employer's own `AI/ML Engineer (100 % remote)` title --
# which discover requires rendered verbatim -- stops failing the percent ban.
# check_assessment re-scans the same bytes and was calling scan_text without the
# corpus, so it undid that masking one gate later: the honest artifact passed one
# gate and failed the next, and no rewording could fix it because the "%" is the
# employer's.
# ---------------------------------------------------------------------------

def _captured(tmp_path, phrase):
    """A workspace whose journal names a real capture containing `phrase`."""
    (tmp_path / "raw").mkdir(parents=True, exist_ok=True)
    (tmp_path / "raw" / "linkedin-1.json").write_text(
        json.dumps([{"title": phrase}]), encoding="utf-8")
    journal.append(tmp_path, {"action": "adapter_call", "site": "linkedin",
                              "stdout_file": "raw/linkedin-1.json"})


def test_a_percentage_quoted_from_a_capture_does_not_fail_this_gate(tmp_path):
    ws, market_dir, root = build(tmp_path)
    phrase = "AI/ML Engineer (100 % remote)"
    _captured(ws, phrase)
    md = (ws / "fit-assessment.md")
    md.write_text(md.read_text(encoding="utf-8") + f"\n\n岗位标题逐字：{phrase}\n",
                  encoding="utf-8")
    findings = ca.check(ws, market_dir, TODAY, root)
    assert_no_finding("\n".join(findings), "PERCENT")


def test_an_invented_percentage_still_fails_this_gate(tmp_path):
    """The twin. Passing the corpus must not amount to switching the scan off:
    a number with no capture behind it is exactly what this lint is for."""
    ws, market_dir, root = build(tmp_path)
    _captured(ws, "AI/ML Engineer (100 % remote)")
    md = (ws / "fit-assessment.md")
    md.write_text(md.read_text(encoding="utf-8") + "\n\n匹配度约 85 % 。\n",
                  encoding="utf-8")
    findings = ca.check(ws, market_dir, TODAY, root)
    assert_finding("\n".join(findings), "PERCENT")


def test_a_hand_written_receipt_is_reported_by_this_composer(tmp_path):
    """Mutation-found 2026-09-05: deleting the RECEIPT_UNVERIFIED loop here left
    the suite green, so the check existed and nothing said it was wired in."""
    ws, market_dir, root = build(tmp_path)
    journal.append(ws, {"action": "gate", "gate": "consistency",
                        "verdict": "pass", "input_hashes": {}, "findings": []})
    assert_finding("\n".join(ca.check(ws, market_dir, TODAY, root)),
                   "RECEIPT_UNVERIFIED", about="consistency")


def test_a_workspace_whose_receipts_were_written_by_the_gates_is_quiet(tmp_path):
    ws, market_dir, root = build(tmp_path)
    assert_no_finding("\n".join(ca.check(ws, market_dir, TODAY, root)),
                      "RECEIPT_UNVERIFIED")


def test_a_skill_root_without_the_mode_file_is_reported_not_skipped(tmp_path):
    ws, market_dir, root = build(tmp_path)
    empty = tmp_path / "emptyroot"
    (empty / "modes").mkdir(parents=True)
    assert_finding("\n".join(ca.check(ws, market_dir, TODAY, empty)),
                   "MODE_FILE_MISSING")
