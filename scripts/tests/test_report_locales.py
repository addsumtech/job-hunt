"""Native report contracts still enforce evidence, counts and disclosures."""
import copy
import json

import pytest
import yaml

import check_assessment as ca
import check_shortlist as cs
import consistency
import count_coverage as cc
import discover_fixtures as fx
import lint_no_prediction as prediction
import report_locales as locales
from test_check_assessment import ASSESSMENT, TODAY, build
from test_check_shortlist_run import DEAD_CALL, EMPTY_CALL, make_empty
from test_count_coverage import ASSESSMENT as COUNT_INPUT

# Written as native-language specimens, independently of the production maps.
SPECIMENS = {
    "ja": ("求人カードの情報だけに基づく暫定判断", "これは根拠の集計であり、結果を予測するものではありません。",
           "## 応募を妨げる必須条件", "## 次に取る方針", "確認基準", "成果物",
           "必須条件の強い根拠: 全6項目中2項目 (部分的 2, 不足 1, 根拠なし 1)", "未評価"),
    "ko": ("채용 카드 정보만을 바탕으로 한 잠정 판단", "이는 근거를 집계한 것이며 결과를 예측하는 것이 아닙니다.",
           "## 지원을 막는 필수 조건", "## 다음 행동", "완료 기준", "산출물",
           "필수 요건의 강한 근거: 6개 중 2개 (부분 충족 2, 부족 1, 근거 없음 1)", "미평가"),
    "es": ("valoración provisional basada únicamente en las fichas", "Este es un recuento de evidencias; no es una predicción del resultado.",
           "## Requisitos excluyentes", "## Qué hacer a continuación", "Criterio de aceptación", "Entregable",
           "Requisitos obligatorios con evidencia sólida: 2 de 6 (parcial 2, carencia 1, sin evidencia 1)", "sin evaluar"),
}


@pytest.mark.parametrize("lang", SPECIMENS)
def test_native_count_cli_preserves_the_counts_and_does_not_invent_judgements(tmp_path, capsys, lang):
    (tmp_path / "fit-assessment.yaml").write_text(yaml.safe_dump(COUNT_INPUT), encoding="utf-8")
    assert cc.main(["--workspace", str(tmp_path), "--lang", lang]) == 0
    output = capsys.readouterr().out
    assert output.splitlines()[0] == SPECIMENS[lang][6]
    assert "/" not in output and "%" not in output
    payload = json.loads((tmp_path / "coverage.json").read_text())
    assert payload[f"block_{lang}"] == output.rstrip("\n")
    assert payload["must_strong"] == 2 and payload["must_total"] == 6
    assert payload["resp_demonstrated"] == 1 and payload["resp_total"] == 3
    assert cc.render_block({}, cc.coverage([]), lang).count(SPECIMENS[lang][7]) == 2
    for bad in (None, "typo", ["worth_applying"], {"wrong": True}):
        block = cc.render_block(dict(verdict=bad), cc.coverage([]), lang)
        assert locales.CARD_TEXT[lang]["verdicts"]["insufficient_evidence"] in block


@pytest.mark.parametrize("lang", SPECIMENS)
def test_native_shortlist_stamp_passes_and_its_removal_fails(tmp_path, lang):
    ws = fx.build_workspace(tmp_path)
    path = ws / "shortlist.md"
    original = path.read_text(encoding="utf-8")
    path.write_text(original.replace("基于卡片信息的初判", SPECIMENS[lang][0]), encoding="utf-8")
    assert cs.main(["--workspace", str(ws)]) == 0
    path.write_text(original.replace("基于卡片信息的初判", ""), encoding="utf-8")
    assert cs.main(["--workspace", str(ws)]) == 1


@pytest.mark.parametrize("lang", SPECIMENS)
@pytest.mark.parametrize("defect", (None, "disclaimer", "blockers", "strategy", "acceptance", "deliverable", "counts", "order"))
def test_native_assessment_contract_passes_and_required_content_stays_required(tmp_path, lang, defect):
    _, disclaimer, blockers, strategy, acceptance, deliverable, _, _ = SPECIMENS[lang]
    assessment = copy.deepcopy(ASSESSMENT)
    assessment.update(verdict="blocked", effort="not_closable", conventions_rendered=[])
    assessment["requirements"][1]["screening"] = "knockout"
    block = cc.render_block(assessment, cc.coverage(assessment["requirements"]), lang)
    header = f"{blockers}\n\n- **R2** — Kubernetes\n\n"
    md = header + f"```text\n{block}\n```\n\n{disclaimer}\n\n" + (
        f"{strategy}\n\n`skill_sprint`\n\n| {acceptance} | {deliverable} |\n|---|---|\n| demo | repo |\n")
    removals = dict(disclaimer=disclaimer, blockers=blockers, strategy=strategy,
                    acceptance=acceptance, deliverable=deliverable)
    if defect in removals:
        md = md.replace(removals[defect], "REMOVED")
    elif defect == "counts":
        md = md.replace(block.splitlines()[0], block.splitlines()[0] + " altered")
    elif defect == "order":
        md = md.replace(header, "") + header
    ws, market, root = build(tmp_path, assessment=assessment, markdown=md)
    findings = ca.check(ws, market, TODAY, root)
    if defect is None:
        assert findings == []
    else:
        expected = {"disclaimer": "NO_DISCLAIMER", "blockers": "NO_DISQUALIFIER_SECTION",
                    "strategy": "NO_STRATEGY_SECTION", "acceptance": "NO_ACCEPTANCE_COLUMN",
                    "deliverable": "NO_ACCEPTANCE_COLUMN", "counts": "COUNT_MISMATCH",
                    "order": "DISQUALIFIER_AFTER_VERDICT"}[defect]
        assert any(f.startswith(expected + ":") for f in findings), findings


@pytest.mark.parametrize("lang", SPECIMENS)
def test_native_refusal_cannot_still_print_a_verdict(tmp_path, lang):
    assessment = copy.deepcopy(ASSESSMENT)
    assessment.update(verdict="insufficient_evidence", conventions_rendered=[])
    ws, market, root = build(tmp_path, assessment=assessment, markdown=SPECIMENS[lang][1])
    assert ca.check(ws, market, TODAY, root) == []
    path = ws / "fit-assessment.md"
    path.write_text(path.read_text() + "\n" + cc.render_block(assessment, cc.coverage([]), lang))
    assert any(f.startswith("REFUSAL_WITH_VERDICT:") for f in ca.check(ws, market, TODAY, root))


@pytest.mark.parametrize("lang", SPECIMENS)
def test_native_degraded_disclosure_requires_all_six_answers(tmp_path, lang):
    labels = locales.GATE_TEXT[lang]["disclosure"]
    md = "## §0\n\n## §0.1\n\n" + "\n".join(f"{label} —" for label in labels)
    ws = make_empty(tmp_path, [DEAD_CALL], md)
    assert cs.main(["--workspace", str(ws)]) == 0
    for label in labels:
        fx.write_md(ws, md.replace(f"{label} —", label))
        assert cs.main(["--workspace", str(ws)]) == 1
    empty_claim = locales.GATE_TEXT[lang]["empty"][0]
    fx.write_md(ws, md + "\n" + empty_claim)
    assert cs.main(["--workspace", str(ws)]) == 1
    fx.write_journal(ws, [EMPTY_CALL])
    assert cs.main(["--workspace", str(ws)]) == 0


@pytest.mark.parametrize("lang", SPECIMENS)
def test_native_notice_passes_but_omitting_it_fails(tmp_path, lang):
    assessment = copy.deepcopy(ASSESSMENT)
    assessment.update(verdict="strong_apply", effort="multi_day", conventions_rendered=[])
    notice = consistency.notices(assessment)[0]
    md = cc.render_block(assessment, cc.coverage(assessment["requirements"]), lang)
    md += "\n\n" + SPECIMENS[lang][1] + "\n\n" + notice[f"text_{lang}"]
    ws, market, root = build(tmp_path, assessment=assessment, markdown=md)
    assert ca.check(ws, market, TODAY, root) == []
    (ws / "fit-assessment.md").write_text(md.replace(notice[f"text_{lang}"], ""), encoding="utf-8")
    assert any(f.startswith("NOTICE_NOT_ATTACHED:") for f in ca.check(ws, market, TODAY, root))


@pytest.mark.parametrize("lang", SPECIMENS)
def test_localised_verdict_labels_and_disclaimers_do_not_trigger_prediction_lint(lang):
    for verdict in locales.CARD_TEXT[lang]["verdicts"]:
        md = cc.render_block(dict(COUNT_INPUT, verdict=verdict), cc.coverage(COUNT_INPUT["requirements"]), lang)
        assert prediction.scan_text(md + "\n" + SPECIMENS[lang][1], "fit-assessment.md") == []


@pytest.mark.parametrize("lang", SPECIMENS)
def test_full_documented_disclaimer_passes_prediction_lint(lang):
    from pathlib import Path
    import re
    guide = (Path(__file__).resolve().parents[2] / "references" / "report-localization.md").read_text()
    disclaimer = re.search(rf"\*\*{lang}\*\*\s+> (.+)", guide).group(1)
    assert locales.GATE_TEXT[lang]["disclaimer"] in disclaimer
    assert prediction.scan_text(disclaimer, "fit-assessment.md") == []


@pytest.mark.parametrize("lang", SPECIMENS)
def test_consistency_cli_prints_a_native_notice_without_changing_the_finding(tmp_path, capsys, lang):
    assessment = dict(ASSESSMENT, verdict="strong_apply", effort="multi_day")
    (tmp_path / "fit-assessment.yaml").write_text(yaml.safe_dump(assessment))
    assert consistency.main(["--workspace", str(tmp_path), "--lang", lang]) == 0
    output = capsys.readouterr().out
    assert output.startswith("NOTICE_VERDICT_EFFORT:")
    assert locales.NOTICE_TEXT["NOTICE_VERDICT_EFFORT"][lang][0] in output
