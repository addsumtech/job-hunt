import json
import pathlib
import sys

import pymupdf

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import deliver
import journal
import lint_no_prediction as lint
from pdf_glyphs import glyph_findings


def test_glyph_zero_is_rejected_even_with_correct_unicode(tmp_path, monkeypatch):
    class Page:
        def get_texttrace(self):
            return [{"type": 0, "chars": [(ord("中"), 0, (), ())]}]
    class Document:
        def __enter__(self): return [Page()]
        def __exit__(self, *args): pass
    monkeypatch.setattr(pymupdf, "open", lambda path: Document())
    assert "MISSING_PDF_GLYPHS" in glyph_findings(tmp_path / "bad.pdf")[0]


def test_real_chinese_glyphs_pass(tmp_path):
    path = tmp_path / "good.pdf"
    with pymupdf.open() as doc:
        doc.new_page().insert_text((72, 72), "中文报告", fontname="china-s")
        doc.save(path)
    assert glyph_findings(path) == []


def test_client_report_required_even_when_cv_exists(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "cv.md").write_text("CV")
    assert deliver.main(["--workspace", str(ws), "--to", str(tmp_path / "out")]) == 2


def test_verified_candidate_metric_is_exempt_but_prediction_is_not(tmp_path):
    source = tmp_path / "cv-source.txt"
    source.write_text("通过优化工作流，内容产出效率提升200%。")
    (tmp_path / "evidence-blocks.json").write_text(json.dumps({"sources": {"cv": {
        "path": str(source), "sha256": journal.sha256_file(source)}}}))
    corpus = lint.capture_corpus(tmp_path)
    masked = lint.mask_copied_numbers("内容效率提升200%，但录用概率85%。", corpus)
    assert "200%" not in masked and "85%" in masked and "录用概率" in masked
    source.write_text("tampered")
    assert "200%" in lint.mask_copied_numbers("内容效率提升200%", lint.capture_corpus(tmp_path))
