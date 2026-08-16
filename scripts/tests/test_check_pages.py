import pathlib
import sys
import zlib

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import check_pages
import journal

JUNIOR = {"meta": {"name": "Z"}, "experience": [{"org": "A", "start": "2025-01"}]}
MID = {"meta": {"name": "Z"}, "experience": [{"org": "A", "start": "2018-03"}]}


def _pdf(path, pages, compress=False):
    """A minimal PDF with `pages` page objects. Uncompressed by default; the
    compressed variant exercises the object-stream path tectonic actually emits."""
    body = b"".join(b"%d 0 obj\n<< /Type /Page /Parent 1 0 R >>\nendobj\n" % (i + 2)
                    for i in range(pages))
    if compress:
        blob = zlib.compress(body)
        body = (b"1 0 obj\n<< /Type /ObjStm /Filter /FlateDecode /Length %d >>\nstream\n"
                % len(blob)) + blob + b"\nendstream\nendobj\n"
    path.write_bytes(b"%PDF-1.5\n" + body + b"trailer\n<< >>\n%%EOF\n")
    return path


def _ws(tmp_path, profile=MID, cv_pages=2, letter_pages=None, compress=False):
    ws = tmp_path / "acme-engineer-2026-08-09"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "tailored-profile.yaml").write_text(
        yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
    _pdf(ws / "cv.pdf", cv_pages, compress)
    if letter_pages is not None:
        _pdf(ws / "letter.pdf", letter_pages, compress)
    return ws


def test_page_count_reads_a_compressed_object_stream(tmp_path):
    """tectonic writes PDF 1.5 with compressed object streams — measured on this
    machine, a real one-page cv.pdf contains zero literal '/Type /Page' bytes. A
    counter that only scanned the raw file would report 0 pages for every CV."""
    assert check_pages.page_count(_pdf(tmp_path / "a.pdf", 3, compress=True)) == 3
    assert check_pages.page_count(_pdf(tmp_path / "b.pdf", 1)) == 1


def test_a_two_page_cv_for_a_mid_career_candidate_is_silent(tmp_path, capsys):
    """The quiet case. Two pages at eight years is exactly what cv-craft.md's
    table prescribes; firing here would teach the reader to skip this gate."""
    ws = _ws(tmp_path, MID, cv_pages=2)
    assert check_pages.main(["--workspace", str(ws), "--today", "2026-08-09"]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_a_two_page_cv_for_a_junior_candidate_is_caught(tmp_path, capsys):
    ws = _ws(tmp_path, JUNIOR, cv_pages=2)
    assert check_pages.main(["--workspace", str(ws), "--today", "2026-08-09"]) == 1
    out = capsys.readouterr().out
    assert "CV_TOO_LONG" in out and "2 pages" in out and "allows 1" in out


def test_a_three_page_cv_is_caught_unless_max_pages_says_otherwise(tmp_path, capsys):
    ws = _ws(tmp_path, MID, cv_pages=3)
    assert check_pages.main(["--workspace", str(ws), "--today", "2026-08-09"]) == 1
    assert "CV_TOO_LONG" in capsys.readouterr().out
    allowed = {**MID, "meta": {"name": "Z", "max_pages": 3}}
    ws2 = _ws(tmp_path / "override", allowed, cv_pages=3)
    assert check_pages.main(["--workspace", str(ws2), "--today", "2026-08-09"]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_an_academic_cv_has_no_page_limit(tmp_path, capsys):
    """cv-craft.md:228 — 'Academic / research CV: No page limit; list all
    publications, grants, talks.'"""
    academic = {**MID, "meta": {"name": "Z", "cv_type": "academic"}}
    ws = _ws(tmp_path, academic, cv_pages=7)
    assert check_pages.main(["--workspace", str(ws), "--today", "2026-08-09"]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_a_two_page_letter_is_caught_and_a_one_page_letter_is_not(tmp_path, capsys):
    ws = _ws(tmp_path, MID, cv_pages=2, letter_pages=1)
    assert check_pages.main(["--workspace", str(ws), "--today", "2026-08-09"]) == 0
    capsys.readouterr()
    ws2 = _ws(tmp_path / "long", MID, cv_pages=2, letter_pages=2)
    assert check_pages.main(["--workspace", str(ws2), "--today", "2026-08-09"]) == 1
    assert "LETTER_TOO_LONG" in capsys.readouterr().out


def test_a_pdf_with_no_readable_page_tree_is_reported_not_ignored(tmp_path, capsys):
    ws = _ws(tmp_path, MID, cv_pages=2)
    (ws / "cv.pdf").write_bytes(b"%PDF-1.5\ntruncated\n")
    assert check_pages.main(["--workspace", str(ws), "--today", "2026-08-09"]) == 1
    assert "UNREADABLE_PDF" in capsys.readouterr().out


def test_no_pdf_is_exit_2_not_a_pass(tmp_path, capsys):
    """A markdown-only run has no PDF to measure. That is 'could not run', not
    'within budget'.

    This docstring used to end "— check_apply only requires this receipt when
    cv.pdf exists", stated as fact while check_apply did not require the receipt
    under ANY condition: check_pages was absent from REQUIRED_GATES, so a
    three-page CV could be rendered, measured, reported CV_TOO_LONG and delivered
    anyway. It is true now — check_apply.conditional_gates() keys the receipt on
    cv.pdf AND tailored-profile.yaml, and could_not_run does not satisfy it — and
    scripts/tests/test_check_apply.py holds that end up rather than this sentence.
    """
    ws = _ws(tmp_path, MID, cv_pages=2)
    (ws / "cv.pdf").unlink()
    assert check_pages.main(["--workspace", str(ws)]) == 2
    assert "cv.pdf" in capsys.readouterr().err


def test_each_run_leaves_exactly_one_receipt_including_the_exit_2_path(tmp_path):
    ws = _ws(tmp_path, MID, cv_pages=2)
    check_pages.main(["--workspace", str(ws), "--today", "2026-08-09"])
    (ws / "cv.pdf").unlink()
    check_pages.main(["--workspace", str(ws), "--today", "2026-08-09"])
    assert [r["verdict"] for r in journal.read_receipts(ws, "check_pages")] == \
        ["pass", "could_not_run"]
