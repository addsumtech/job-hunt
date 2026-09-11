import copy
import pathlib
import sys

import pymupdf
import pytest
import yaml
from docx import Document

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import check_apply
import check_layout
import journal


def reviewed_workspace(tmp_path):
    ws = tmp_path / "application"
    ws.mkdir()
    docx = Document()
    docx.add_paragraph("Test Candidate")
    docx.save(ws / "cv.docx")
    reference = tmp_path / "template.docx"
    docx.save(reference)
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Test Candidate")
    doc.save(ws / "cv.pdf")
    page.get_pixmap().save(ws / "preview.png")
    doc.close()
    review = {
        "reviewer": "Test reviewer", "reviewed_at": "2026-09-11T12:00:00+08:00",
        "reference": {"path": str(reference), "sha256": journal.sha256_file(reference)},
        "user_overrides": [],
        "checks": {key: {"status": "pass", "detail": "Compared to the reference."}
                   for key in check_layout.CHECKS},
        "unresolved_differences": [],
        "artifacts": {name: {"sha256": journal.sha256_file(ws / name), "pages": 1,
                             "previews": [{"page": 1, "path": "preview.png",
                                           "sha256": journal.sha256_file(ws / "preview.png")}]}
                      for name in ("cv.docx", "cv.pdf")},
    }
    write_review(ws, review)
    return ws, review


def write_review(ws, review):
    (ws / "layout-review.yaml").write_text(yaml.safe_dump(review), encoding="utf-8")


def test_absent_workspace_is_not_created(tmp_path):
    ws = tmp_path / "missing"
    assert check_layout.main(["--workspace", str(ws)]) == 2
    assert not ws.exists()


def test_rendered_cv_requires_layout_review_in_apply(tmp_path):
    ws, _ = reviewed_workspace(tmp_path)
    assert ("check_layout", "a rendered CV exists") in check_apply.conditional_gates(ws)
    (ws / "layout-review.yaml").unlink()
    assert check_layout.main(["--workspace", str(ws)]) == 1
    assert "NO_LAYOUT_REVIEW" in journal.read_receipts(ws, "check_layout")[-1]["findings"][0]


def test_complete_visual_record_is_bound_to_actual_files(tmp_path):
    ws, _ = reviewed_workspace(tmp_path)
    assert check_layout.main(["--workspace", str(ws)]) == 0
    receipt = journal.read_receipts(ws, "check_layout")[-1]
    assert receipt["input_hashes"]["cv.docx"] == journal.sha256_file(ws / "cv.docx")
    assert receipt["input_hashes"]["cv.pdf"] == journal.sha256_file(ws / "cv.pdf")
    assert journal.receipt_intact(receipt)
    assert check_apply._stale_inputs(ws, "check_layout", receipt) == []


def test_layout_receipt_cannot_bind_an_unrelated_external_file(tmp_path):
    ws, _ = reviewed_workspace(tmp_path)
    assert check_layout.main(["--workspace", str(ws)]) == 0
    receipt = journal.read_receipts(ws, "check_layout")[-1]
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_text("not the supplied template")
    receipt["input_hashes"][str(unrelated)] = journal.sha256_file(unrelated)
    findings = check_apply._stale_inputs(ws, "check_layout", receipt)
    assert any("RECEIPT_INPUT_OUTSIDE_WORKSPACE" in item for item in findings)


@pytest.mark.parametrize("changed", ["cv.docx", "cv.pdf", "preview.png", "reference"])
def test_changed_output_preview_or_template_invalidates_review(tmp_path, changed):
    ws, review = reviewed_workspace(tmp_path)
    target = pathlib.Path(review["reference"]["path"]) if changed == "reference" else ws / changed
    target.write_bytes(target.read_bytes() + b"changed")
    assert check_layout.main(["--workspace", str(ws)]) == 1
    assert any("STALE_LAYOUT_REVIEW" in s for s in journal.read_receipts(ws, "check_layout")[-1]["findings"])


@pytest.mark.parametrize("problem", ["missing_page", "duplicate_page", "wrong_count", "failed_check", "blank_check", "unresolved", "not_image"])
def test_unreviewed_or_unresolved_layout_cannot_pass(tmp_path, problem):
    ws, original = reviewed_workspace(tmp_path)
    review = copy.deepcopy(original)
    pdf = review["artifacts"]["cv.pdf"]
    if problem == "missing_page":
        pdf["previews"] = []
    elif problem == "duplicate_page":
        pdf["previews"] *= 2
    elif problem == "wrong_count":
        pdf["pages"] = 2
    elif problem == "failed_check":
        review["checks"]["page_geometry"]["status"] = "fail"
    elif problem == "blank_check":
        review["checks"]["fonts"]["detail"] = ""
    elif problem == "unresolved":
        review["unresolved_differences"] = ["Unexpected top margin."]
    elif problem == "not_image":
        (ws / "preview.png").write_text("not a rendered page")
        for item in review["artifacts"].values():
            item["previews"][0]["sha256"] = journal.sha256_file(ws / "preview.png")
    write_review(ws, review)
    assert check_layout.main(["--workspace", str(ws)]) == 1


def test_no_template_does_not_waive_page_review(tmp_path):
    ws, review = reviewed_workspace(tmp_path)
    review["reference"] = None
    write_review(ws, review)
    assert check_layout.main(["--workspace", str(ws)]) == 0
    review["artifacts"]["cv.pdf"]["previews"] = []
    write_review(ws, review)
    assert check_layout.main(["--workspace", str(ws)]) == 1
