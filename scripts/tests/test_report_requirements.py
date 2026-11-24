"""report_requirements.py writes the bundled renderer's defaults; a real render must
measure clean against them, so the two cannot drift apart unnoticed."""
import pathlib
import sys

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import deliver  # noqa: E402
import check_layout  # noqa: E402
import journal  # noqa: E402
import layout_pages  # noqa: E402
import layout_requirements  # noqa: E402
import report_requirements  # noqa: E402
import render_report  # noqa: E402

pytest.importorskip("pymupdf")

REPORTS = {
    "zh": "# 字节跳动搜索算法岗位投递评估\n\n评估日期：2026 年 10 月 30 日\n\n"
          "[结论：可以冲刺](#结论可以冲刺)\n\n[投递前要做的事](#投递前要做的事)\n\n"
          "## 结论：可以冲刺\n\n建议投，但要当冲刺岗位来投。\n\n### 依据\n\n- 列表项\n\n"
          "| 要求 | 证据 |\n|---|---|\n| C++ | 无 |\n\n## 投递前要做的事\n\n先补一个手机号。\n",
    "en": "# J.P. Morgan EMEA Technology M&A application review\n\nReviewed on 30 October 2026.\n\n"
          "## Verdict: a stretch worth sending\n\nApply, but treat it as a stretch.\n\n"
          "## Before you send it\n\nAdd a phone number.\n",
}


def _workspace(tmp_path, text):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "report.md").write_text(text, encoding="utf-8")
    return ws


@pytest.mark.parametrize("lang", sorted(REPORTS))
def test_a_bundled_render_measures_clean_against_the_written_defaults(tmp_path, lang):
    ws = _workspace(tmp_path, REPORTS[lang])
    assert report_requirements.main(["--workspace", str(ws)]) == 0
    req = yaml.safe_load((ws / "report-layout-requirements.yaml").read_text(encoding="utf-8"))
    assert req["reference"] is None
    assert set(req["expectations"]) == {
        "fonts", "font_sizes", "page_geometry", "headings_and_rules", "dates_and_alignment",
        "paragraph_spacing", "content_order", "pagination_and_clipping"}
    style = deliver._portable_report_style(REPORTS[lang])
    ok, why = deliver._render_portable_report(ws / "report.md", ws / "report.pdf", style)
    assert ok, why
    assert layout_requirements.measure(ws, req, report=True) == []


def test_requirements_are_not_rewritten_to_fit_an_output(tmp_path, capsys):
    ws = _workspace(tmp_path, REPORTS["zh"])
    (ws / "report-layout-requirements.yaml").write_text("reference: null\n")
    assert report_requirements.main(["--workspace", str(ws)]) == 2
    assert "already exists" in capsys.readouterr().err
    assert (ws / "report-layout-requirements.yaml").read_text() == "reference: null\n"


def test_a_report_without_a_section_heading_cannot_be_sampled(tmp_path, capsys):
    ws = _workspace(tmp_path, "# Title only\n\nOne paragraph.\n")
    assert report_requirements.main(["--workspace", str(ws)]) == 2
    assert "no heading text" in capsys.readouterr().err
    assert not (ws / "report-layout-requirements.yaml").exists()


def test_a_heading_the_contents_list_repeats_is_not_sampled(tmp_path):
    """The contents list prints every section heading again at 10.5 pt, and the gate
    checks every line holding a sample, so a repeated heading fails a correct report."""
    ws = _workspace(tmp_path, REPORTS["zh"])
    assert report_requirements.main(["--workspace", str(ws)]) == 0
    req = yaml.safe_load((ws / "report-layout-requirements.yaml").read_text(encoding="utf-8"))
    heading = next(s for s in req["text_samples"] if s["role"] == "heading")
    assert heading["text"].startswith("依据") and heading["size_pt"] == report_requirements.SIZES["subheading"]


DISCOVER_REPORT = """# 北京产品岗位建议

2026 年 11 月 24 日｜北京｜职位比较

- [优先尝试的岗位](#优先尝试的岗位)
- [还有哪些机会](#还有哪些机会)

## 优先尝试的岗位

优先查看能用现有项目说明职责的岗位。

## 还有哪些机会

准备面试时，把独立完成的工作单独列出来。
"""


def test_duplicate_contents_and_dateline_through_the_default_report_review(tmp_path):
    ws = _workspace(tmp_path, DISCOVER_REPORT)
    args = ["--workspace", str(ws)]
    assert report_requirements.main(args) == 0
    req = yaml.safe_load((ws / "report-layout-requirements.yaml").read_text(encoding="utf-8"))
    _, heading, body = req["text_samples"]
    assert heading["occurrence"] == 2 and heading["size_pt"] == deliver.REPORT_SIZES["heading"]
    assert body["text"].startswith("优先查看")
    assert render_report.main(args) == 0
    assert layout_requirements.measure(ws, req, report=True) == []
    wrong_size = {**req, "text_samples": [{**heading, "size_pt": deliver.REPORT_SIZES["contents"]},
                                         req["text_samples"][0], body]}
    assert any("expected 10.5" in issue for issue in layout_requirements.measure(ws, wrong_size, report=True))

    generated = layout_pages.prepare(ws, report=True)
    assert generated["review_required"] == [1]
    draft = yaml.safe_load(pathlib.Path(generated["draft"]).read_text(encoding="utf-8"))
    draft["checks"] = {key: {"status": "pass", "detail": f"Test comparison of {key}."}
                       for key in check_layout.CHECKS}
    draft["artifacts"]["report.pdf"]["previews"][0]["review_status"] = "pass"
    draft["unresolved_differences"] = []
    (ws / "report-layout-review.yaml").write_text(yaml.safe_dump(draft), encoding="utf-8")
    assert check_layout.main([*args, "--report"]) == 0

    (ws / "report.md").write_text(DISCOVER_REPORT + "\n再核对每个职位的面试流程。\n", encoding="utf-8")
    assert render_report.main(args) == 0
    findings, _ = check_layout.inspect(ws, report=True)
    assert any("STALE_LAYOUT_REVIEW" in issue and "layout_pages.py" in issue for issue in findings)
    refreshed = layout_pages.prepare(ws, report=True)
    assert refreshed["review_required"] == [1]
    new_draft = yaml.safe_load(pathlib.Path(refreshed["draft"]).read_text(encoding="utf-8"))
    assert new_draft["artifacts"]["report.pdf"]["sha256"] == journal.sha256_file(ws / "report.pdf")
    assert new_draft["artifacts"]["report.pdf"]["sha256"] != draft["artifacts"]["report.pdf"]["sha256"]
    assert new_draft["artifacts"]["report.pdf"]["previews"][0]["review_status"] == "pending"


def test_dateline_is_never_the_default_body_sample(tmp_path):
    source = DISCOVER_REPORT.replace("- [优先尝试的岗位](#优先尝试的岗位)", "")
    ws = _workspace(tmp_path, source)
    args = ["--workspace", str(ws)]
    assert report_requirements.main(args) == 0
    req = yaml.safe_load((ws / "report-layout-requirements.yaml").read_text(encoding="utf-8"))
    assert render_report.main(args) == 0
    assert layout_requirements.measure(ws, req, report=True) == []
