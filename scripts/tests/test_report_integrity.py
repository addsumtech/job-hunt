"""Regressions for real table mismatches, render binding and CJK layout."""
import json
import pathlib
import sys

import pymupdf
import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import check_layout
import deliver
import journal
import layout_requirements
import render_report
from test_check_layout import reviewed_report


@pytest.mark.parametrize("changed", ["产品造假演示岗位", "产品完全不同职位", "会计师"])
def test_a_shared_prefix_cannot_stand_in_for_a_complete_cell(changed):
    md = f"| 公司 | 岗位 | 地点 |\n|---|---|---|\n| 海川软件 | {changed} | 上海 |\n"
    assert layout_requirements.report_text_problems(md, ["公司 岗位 地点\n海川软件 产品经理 上海\n"])


@pytest.mark.parametrize("page", [
    "公司 岗位 地点\n海川软 产品经 上海\n件 理\n",
    "公司岗位地点\n海川软件产品经理上海\n",
    "公司\n岗位\n地点\n海川\n软件\n产品\n经理\n上海\n",
])
def test_complete_wrapped_or_glued_cells_still_bind(page):
    md = "| 公司 | 岗位 | 地点 |\n|---|---|---|\n| 海川软件 | 产品经理 | 上海 |\n"
    assert layout_requirements.report_text_problems(md, [page]) == []


def test_columns_with_shared_prefixes_cannot_be_reassigned_character_by_character():
    md = "| 原岗位 | 新岗位 |\n|---|---|\n| 产品助理 | 产品经理 |\n"
    assert layout_requirements.report_text_problems(md, ["原岗位 新岗位\n产品经理 产品助理\n"])


@pytest.mark.parametrize("change", ["delete_paragraph", "link_only", "pdf", "missing_record", "bad_record"])
def test_review_hashes_cannot_bless_a_stale_render_pair(tmp_path, change):
    ws = reviewed_report(tmp_path)
    if change in ("delete_paragraph", "link_only"):
        # The review may be refreshed; the actual rendering record may not.
        source = "# Candidate\n" if change == "delete_paragraph" else "# [Test Candidate](https://new.example.test)\n"
        (ws / "report.md").write_text(source)
        review = yaml.safe_load((ws / "report-layout-review.yaml").read_text())
        review["source_sha256"] = journal.sha256_file(ws / "report.md")
        (ws / "report-layout-review.yaml").write_text(yaml.safe_dump(review))
    elif change == "pdf":
        with (ws / "report.pdf").open("ab") as out:
            out.write(b"\n% another export")
    elif change == "missing_record":
        (ws / "report-render.json").unlink()
    else:
        (ws / "report-render.json").write_text("[]")
    problems, _ = check_layout.inspect(ws, report=True)
    assert any("REPORT_RENDER" in problem for problem in problems)
    written, _ = deliver.deliver(ws, tmp_path / "out", "report")
    assert written == []


def test_a_noop_renderer_cannot_rebind_an_old_pdf(tmp_path):
    ws = reviewed_report(tmp_path)
    old = (ws / "report.pdf").read_bytes()
    ok, reason = render_report.render_with(ws / "report.md", ws / "report.pdf", lambda *_: (True, ""))
    assert not ok and "REPORT_NOT_RENDERED" in reason
    assert (ws / "report.pdf").read_bytes() == old
    assert not (ws / "report-render.json").exists()


def test_source_edit_during_render_is_not_bound(tmp_path):
    ws = reviewed_report(tmp_path)
    old = (ws / "report.pdf").read_bytes()

    def renderer(source, target):
        source.write_text("# Changed during render\n")
        target.write_bytes(old)
        return True, ""

    ok, reason = render_report.render_with(ws / "report.md", ws / "report.pdf", renderer)
    assert not ok and "REPORT_SOURCE_CHANGED" in reason
    assert not (ws / "report-render.json").exists()


@pytest.mark.parametrize("columns", [3, 4, 5])
def test_default_pdf_tables_and_cards_bind_with_clickable_links(tmp_path, columns):
    headers = ["公司", "岗位", "地点", "判断", "原链接"]
    values = ["海川软件", "产品经理", "上海", "需要补充项目证据", "[打开职位](https://example.test/job)"]
    row = values[:columns - 1] + [values[-1]]
    head = headers[:columns - 1] + [headers[-1]]
    md, pdf = tmp_path / "report.md", tmp_path / "report.pdf"
    md.write_text("# 求职建议\n\n| " + " | ".join(head) + " |\n|" + "---|" * columns
                  + "\n| " + " | ".join(row) + " |\n")
    assert render_report.main(["--workspace", str(tmp_path)]) == 0
    pair = json.loads((tmp_path / "report-render.json").read_text())
    assert pair["source_sha256"] == journal.sha256_file(md)
    assert pair["pdf_sha256"] == journal.sha256_file(pdf)
    with pymupdf.open(pdf) as doc:
        assert layout_requirements.report_text_problems(md.read_text(), [page.get_text() for page in doc]) == []
        assert any(link.get("uri") == "https://example.test/job" for page in doc for link in page.get_links())


@pytest.mark.parametrize("text", [
    "已完成客户需求梳理，接下来核对实际交付。",
    "证据来自CV-001，核对JD-002后再补写。",
    "请核对（独立负责的部分），保留真实职责。",
    "Validate the customer-facing requirement before the release.",
    "https://example.test/" + "averylongpath" * 20,
    "特别长的中文段落。" * 100,
])
def test_wrapping_preserves_all_text_and_font_size_without_overflow(text):
    font = pymupdf.Font("cjk")
    measure = lambda value, size: font.text_length(value, fontsize=size)
    lines = deliver._wrap_report_text(text, 11.5, 105, measure)
    assert "".join("".join(lines).split()) == "".join(text.split())
    assert all(measure(line, 11.5) <= 105.01 for line in lines)
    assert not any(line.startswith(tuple("，。；：！？、）】》”’")) for line in lines)
    assert not any(line.endswith(tuple("（【《“‘")) for line in lines)
    for token in ("CV-001", "JD-002"):
        if token in text:
            assert any(token in line for line in lines)


def test_two_row_table_does_not_split_when_it_fits_on_a_fresh_page(tmp_path):
    source = ("# 求职建议\n\n" + "已有经验，需要补充具体的项目说明。\n\n" * 24
              + "| 加分项 | 现有证据 |\n|---|---|\n| CRM经历 | 客服后台验收 |\n| 独立从零到一 | 尚无证据 |\n")
    md, pdf = tmp_path / "report.md", tmp_path / "report.pdf"
    md.write_text(source)
    assert deliver.render_pdf(md, pdf, None) == (True, "")
    with pymupdf.open(pdf) as doc:
        pages = [page.get_text() for page in doc]
        assert next(i for i, text in enumerate(pages) if "CRM经历" in text) == next(
            i for i, text in enumerate(pages) if "独立从零到一" in text)


@pytest.mark.parametrize("text", ["分母可以逐条审计", "本 skill 不给出面试估计", "The denominator can be audited row by row."])
def test_internal_assessment_narration_is_kept_out_of_client_reports(text):
    assert deliver.report_audience_findings(text)
