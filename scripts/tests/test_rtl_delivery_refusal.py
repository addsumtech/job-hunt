"""A tolerated RTL PDF refusal must survive rerendering and final delivery."""
import json
import pathlib
import sys

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import deliver
import render_cv


@pytest.mark.parametrize("text", ["مرشح افتراضي", "מועמד לדוגמה"])
def test_rtl_rerender_removes_stale_source_and_delivery_keeps_refusal(
        tmp_path, capsys, text):
    ws = tmp_path / "round"
    ws.mkdir()
    profile = ws / "profile.yaml"
    profile.write_text(yaml.safe_dump({
        "meta": {"name": "Fictional Candidate", "language": "en"},
        "contact": {"email": "fictional@example.invalid"},
        "summary": text,
    }, allow_unicode=True), encoding="utf-8")
    pdf = ws / "cv.pdf"
    pdf.write_bytes(b"%PDF previous round")
    pdf.with_suffix(".tex").write_text("previous round", encoding="utf-8")

    for fmt in ("md", "docx", "pdf"):
        assert render_cv.main([str(profile), "--format", fmt,
                               "--out", str(ws / f"cv.{fmt}")]) == 0
    err = capsys.readouterr().err
    assert "No LaTeX source was written" in err
    assert "LaTeX source written to" not in err
    assert not pdf.exists()
    assert not pdf.with_suffix(".tex").exists()

    (ws / "report.md").write_text(text, encoding="utf-8")
    dest = tmp_path / "delivery"
    dest.mkdir()
    (dest / "round-cv.pdf").write_bytes(b"%PDF previous delivery")
    (dest / "round-cv.tex").write_text("previous source", encoding="utf-8")
    (dest / "unrelated.tex").write_text("keep this", encoding="utf-8")
    assert deliver.main(["--workspace", str(ws), "--to", str(dest)]) == 2
    output = capsys.readouterr()
    assert "NOTICE_PDF_REFUSED" in output.err
    assert "right-to-left" in output.err
    assert (dest / "round-cv.md").is_file()
    assert (dest / "round-cv.docx").is_file()
    assert not list(dest.glob("*.pdf"))
    assert not (dest / "round-cv.tex").exists()
    assert (dest / "unrelated.tex").read_text(encoding="utf-8") == "keep this"
    receipt = json.loads((ws / "journal.jsonl").read_text().splitlines()[-1])
    assert not any(f.endswith((".pdf", ".tex")) for f in receipt["files"])
    assert any("right-to-left" in note for note in receipt["pdf_refused"])


def test_delivery_rtl_refusal_removes_old_target_without_compiling(tmp_path, monkeypatch):
    md = tmp_path / "cv.md"
    md.write_text("# English header\n\nمرشح افتراضي\n", encoding="utf-8")
    pdf = tmp_path / "cv.pdf"
    pdf.write_bytes(b"%PDF previous delivery")
    monkeypatch.setattr(deliver, "visible_markdown", lambda p: p.read_text(encoding="utf-8"))

    def unexpected_compile(*args, **kwargs):
        pytest.fail("RTL source must be refused before the PDF compiler")

    monkeypatch.setattr(deliver, "_pandoc", unexpected_compile)
    ok, reason = deliver.render_pdf(md, pdf, None)
    assert not ok
    assert "right-to-left" in reason
    assert not pdf.exists()
