import pathlib
import sys
import zlib

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import pytest

import check_pages
import journal

JUNIOR = {"meta": {"name": "Zoë Nowak"},
          "experience": [{"org": "Acme BV", "start": "2025-01"}]}
MID = {"meta": {"name": "Zoë Nowak"},
       "experience": [{"org": "Acme BV", "start": "2018-03"}]}


def _profile_text(profile):
    """What a correctly rendered PDF of `profile` would say."""
    parts = [str((profile.get("meta") or {}).get("name") or "")]
    parts += [str((ex or {}).get("org") or "") for ex in profile.get("experience") or []]
    return " ".join(p for p in parts if p)


def _pdf(path, pages, compress=False, text=""):
    """A minimal PDF with `pages` page objects and, optionally, readable text.

    Uncompressed by default; the compressed variant exercises the object-stream
    path tectonic actually emits. `text` is written the way a real PDF carries
    text — a content stream of string literals plus a /ToUnicode CMap that maps
    the codes back to Unicode — because check_pages now reads the words out of
    the file, and a fixture with no words in it would be asserting against the
    "cannot read this" branch by accident.
    """
    body = b"".join(b"%d 0 obj\n<< /Type /Page /Parent 1 0 R >>\nendobj\n" % (i + 2)
                    for i in range(pages))
    if compress:
        blob = zlib.compress(body)
        body = (b"1 0 obj\n<< /Type /ObjStm /Filter /FlateDecode /Length %d >>\nstream\n"
                % len(blob)) + blob + b"\nendstream\nendobj\n"
    extra = b""
    if text:
        # Latin-1 codes with an identity /ToUnicode map — the 8-bit shape a
        # pdflatex-produced CV has.
        payload = text.encode("latin-1", "replace").replace(b"\\", b"") \
                      .replace(b"(", b"").replace(b")", b"")
        cmap = (b"begincmap\n1 beginbfrange\n<00> <FF> <0000>\n"
                b"endbfrange\nendcmap\n")
        extra = (b"90 0 obj\n<< /Length %d >>\nstream\n" % (len(cmap))
                 + cmap + b"endstream\nendobj\n"
                 + b"91 0 obj\n<< >>\nstream\nBT /F1 12 Tf (" + payload
                 + b") Tj ET\nendstream\nendobj\n")
    path.write_bytes(b"%PDF-1.5\n" + body + extra + b"trailer\n<< >>\n%%EOF\n")
    return path


def _ws(tmp_path, profile=MID, cv_pages=2, letter_pages=None, compress=False,
        cv_text=None):
    ws = tmp_path / "acme-engineer-2026-08-09"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "tailored-profile.yaml").write_text(
        yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
    _pdf(ws / "cv.pdf", cv_pages, compress,
         text=_profile_text(profile) if cv_text is None else cv_text)
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


# ── the PDF still says who the candidate is ───────────────────────────────────

def test_a_pdf_that_lost_the_candidates_name_is_caught(tmp_path, capsys):
    """The defect this half of the gate exists for, in miniature.

    Measured on this repo before the fix: render_cv emitted a pdfLaTeX
    inputenc/fontenc preamble, find_latex_engine handed the file to tectonic
    (XeTeX), and every character above Latin-1 was dropped with an exit-0
    warning — `Łukasz Wójcik` was delivered as `ukasz Wójcik`. Page count was
    right, the compile "succeeded", cv.md was perfect, and all three judges read
    the correct name. Nothing looked at the bytes the recruiter opens."""
    ws = _ws(tmp_path, MID, cv_pages=2, cv_text="Zo Nowak Acme BV")   # ë dropped
    assert check_pages.main(["--workspace", str(ws), "--today", "2026-08-09"]) == 1
    out = capsys.readouterr().out
    assert "TEXT_MISSING_FROM_PDF" in out and "meta.name" in out and "Zoë Nowak" in out


def test_a_pdf_that_lost_an_employer_is_caught(tmp_path, capsys):
    ws = _ws(tmp_path, MID, cv_pages=2, cv_text="Zoë Nowak Acme")
    assert check_pages.main(["--workspace", str(ws), "--today", "2026-08-09"]) == 1
    out = capsys.readouterr().out
    assert "TEXT_MISSING_FROM_PDF" in out and "experience[].org" in out


def test_unreadable_text_is_UNVERIFIED_not_a_pass(tmp_path, capsys):
    """A gate that cannot run must not look like a gate that passed.

    There is no way from here to tell "this PDF has no text" from "this reader
    cannot read this PDF", so the honest answer is to say so and fail, not to
    find nothing missing and report clean."""
    ws = _ws(tmp_path, MID, cv_pages=2, cv_text="")
    assert check_pages.main(["--workspace", str(ws), "--today", "2026-08-09"]) == 1
    out = capsys.readouterr().out
    assert "UNVERIFIED_PDF_TEXT" in out and "NOT a pass" in out


def test_no_name_or_orgs_declared_means_nothing_to_assert(tmp_path, capsys):
    """A profile with neither a name nor an employer gives this check nothing to
    look for, and inventing a finding there would be the cry-wolf failure the
    page-budget half was calibrated to avoid."""
    ws = _ws(tmp_path, {"meta": {}}, cv_pages=1, cv_text="")
    assert check_pages.main(["--workspace", str(ws), "--today", "2026-08-09"]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_matching_survives_typesetting_but_not_a_real_omission():
    """Line-break hyphenation, ligature glyphs and missing word spaces are things
    a typesetter is entitled to do; a dropped letter is not."""
    readings = ["ZoëNowakPolitech-nikaŚląskaoﬃce"]
    assert check_pages.pdf_contains(readings, "Zoë Nowak")
    assert check_pages.pdf_contains(readings, "Politechnika Śląska")
    assert check_pages.pdf_contains(readings, "office")
    assert not check_pages.pdf_contains(readings, "Zoe Nowak")
    assert not check_pages.pdf_contains(readings, "Politechnika Slaska")


def test_each_run_leaves_exactly_one_receipt_including_the_exit_2_path(tmp_path):
    ws = _ws(tmp_path, MID, cv_pages=2)
    check_pages.main(["--workspace", str(ws), "--today", "2026-08-09"])
    (ws / "cv.pdf").unlink()
    check_pages.main(["--workspace", str(ws), "--today", "2026-08-09"])
    assert [r["verdict"] for r in journal.read_receipts(ws, "check_pages")] == \
        ["pass", "could_not_run"]


# ---------------------------------------------------------------------------
# The pdftotext rescue must run ALWAYS, not only when the built-in reader came
# back empty. Audited 2026-09-05: a CJK font embedded as Identity-H carries no
# ToUnicode CMap, but the Latin Modern subset in the same document does — so a
# Korean CV produced four garbage readings from the Latin CMaps, `if not
# readings` never fired, and text pdftotext reads perfectly was reported
# TEXT_MISSING_FROM_PDF. Correct PDF, correct page, blocked by its own gate.
# ---------------------------------------------------------------------------

def test_the_rescue_runs_even_when_another_font_produced_a_garbage_reading(
        tmp_path, monkeypatch):
    """The condition, tested as behaviour rather than as source text.

    A document with two fonts is simulated directly: the built-in reader yields
    a non-empty but wrong reading (the Latin CMap decoding Hangul bytes), and
    pdftotext yields the real text. Under `if not readings` the real text never
    entered the list.
    """
    pdf = tmp_path / "cv.pdf"
    pdf.write_bytes(b"%PDF-1.7\n% not a real pdf, every reader here is stubbed\n")
    monkeypatch.setattr(check_pages, "_streams", lambda data: [b""])
    monkeypatch.setattr(check_pages, "_text_runs", lambda blobs: [b"\x00\x01"])
    monkeypatch.setattr(check_pages, "_tounicode_maps", lambda blobs: [{0: "?"}])
    monkeypatch.setattr(check_pages, "_decode", lambda run, table, two: "garbage")
    monkeypatch.setattr(check_pages, "_pdftotext", lambda p: "김민준 삼성전자")

    readings = check_pages.extract_text(pdf)
    assert any("김민준" in r for r in readings), readings
    assert any("garbage" in r for r in readings), "the built-in readings still count"


def test_a_name_that_is_genuinely_absent_is_still_reported(tmp_path, monkeypatch):
    """The twin. Always adding the rescue can only remove findings, so the guard
    that matters is that a real absence still fires."""
    pdf = tmp_path / "cv.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    monkeypatch.setattr(check_pages, "_streams", lambda data: [b""])
    monkeypatch.setattr(check_pages, "_text_runs", lambda blobs: [b"\x00"])
    monkeypatch.setattr(check_pages, "_tounicode_maps", lambda blobs: [{0: "?"}])
    monkeypatch.setattr(check_pages, "_decode", lambda run, table, two: "garbage")
    monkeypatch.setattr(check_pages, "_pdftotext", lambda p: "김민준 삼성전자")

    profile = {"meta": {"name": "홍길동아무개"}}
    found = check_pages.text_findings(str(pdf), profile)
    assert any(f.startswith("TEXT_MISSING_FROM_PDF") for f in found), found


# ---------------------------------------------------------------------------
# A start date this module cannot read is UNKNOWN, not zero. `_YEAR` matches
# 19xx/20xx only, so `平成31年4月` yielded nothing and years_of_experience
# returned 0 — the strictest possible answer, a one-page budget, and a
# guaranteed false CV_TOO_LONG for a seven-year candidate.
#
# Deliberately not an era-conversion table: the Republic of China calendar, the
# Thai Buddhist era and Hijri dates are all real inputs too, and a hard-coded
# table covers only the calendars someone thought of.
# ---------------------------------------------------------------------------

def test_a_gregorian_date_inside_a_japanese_string_still_reads():
    assert check_pages.years_of_experience({"experience": [{"start": "2019年4月"}]},
                                           2026) == 7


@pytest.mark.parametrize("start", ["平成31年4月", "令和元年4月", "民國108年", "๒๕๖๒"])
def test_a_date_in_another_calendar_is_unknown_not_zero(start):
    profile = {"experience": [{"start": start}]}
    assert check_pages.years_of_experience(profile, 2026) is None
    assert check_pages.max_pages(profile, 2026) == 2, "the permissive budget"
    assert check_pages.unreadable_start_dates(profile) == [start]


def test_no_start_date_at_all_is_a_genuine_zero_and_keeps_one_page():
    """The distinction that matters: a new graduate with no dated roles really
    has zero years, and the length table gives them one page. Only a date that
    IS there and cannot be read is unknown."""
    for profile in ({"experience": []}, {"experience": [{"org": "x"}]}, {}):
        assert check_pages.years_of_experience(profile, 2026) == 0
        assert check_pages.max_pages(profile, 2026) == 1
        assert check_pages.unreadable_start_dates(profile) == []


def test_one_readable_date_among_unreadable_ones_is_enough_to_score():
    profile = {"experience": [{"start": "平成31年4月"}, {"start": "2022-01"}]}
    assert check_pages.years_of_experience(profile, 2026) == 4
    assert check_pages.unreadable_start_dates(profile) == ["平成31年4月"], (
        "the unread one is still named — the reader must see why the budget moved")


def test_an_unreadable_start_date_is_named_in_the_findings(tmp_path):
    """The budget moved because the date could not be read, and a reader who
    cannot see that will not know why a one-page CV got two."""
    pdf = tmp_path / "cv.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    profile = {"meta": {"name": "x"}, "experience": [{"start": "平成31年4月"}]}
    found = check_pages.findings_for(str(pdf), profile, 2026)
    assert any(f.startswith("START_DATE_UNREAD") for f in found), found
    assert any("平成31年4月" in f for f in found)


def test_a_readable_start_date_does_not_fire_it(tmp_path):
    pdf = tmp_path / "cv.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    profile = {"meta": {"name": "x"}, "experience": [{"start": "2019-04"}]}
    found = check_pages.findings_for(str(pdf), profile, 2026)
    assert not any(f.startswith("START_DATE_UNREAD") for f in found), found
