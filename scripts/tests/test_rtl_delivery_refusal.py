"""A tolerated RTL PDF refusal must survive rerendering and final delivery."""
import json
import pathlib
import sys

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import deliver
import render_cv


# The stale PDF must be THIS workspace's earlier delivery for the refusal to owe
# its removal: deliver.py treats unrecorded client files in a fresh --to folder as
# another workspace's and leaves them alone. So the earlier delivery is this
# workspace's in the two ways one can be: an older deliver.py writing into the
# default folder named after the workspace (which recorded nothing), and a
# current one writing to a shared --to (which recorded it in the manifest).
@pytest.mark.parametrize("owner", ["default-folder", "manifest"])
@pytest.mark.parametrize("text", ["مرشح افتراضي", "מועמד לדוגמה"])
def test_rtl_rerender_removes_stale_source_and_delivery_keeps_refusal(
        tmp_path, capsys, monkeypatch, text, owner):
    import hashlib
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
    if owner == "default-folder":
        monkeypatch.setattr(deliver, "DEFAULT_ROOT", tmp_path / "Downloads")
        dest = tmp_path / "Downloads" / ws.name
        args = ["--workspace", str(ws)]
    else:
        dest = tmp_path / "delivery"
        args = ["--workspace", str(ws), "--to", str(dest)]
    (dest / "简历").mkdir(parents=True)
    (dest / "简历" / "简历.pdf").write_bytes(b"%PDF previous delivery")
    (dest / "简历" / "简历.tex").write_text("previous source", encoding="utf-8")
    (dest / "unrelated.tex").write_text("keep this", encoding="utf-8")
    if owner == "manifest":
        (dest / deliver.MANIFEST_NAME).write_text(json.dumps({"format": 1, "deliveries": [{
            "workspace": str(ws.resolve()), "workspace_name": ws.name,
            "mode": deliver.journal.current_mode(ws), "folder": "",
            "files": {"简历/简历.pdf": hashlib.sha256(b"%PDF previous delivery").hexdigest()},
        }]}), encoding="utf-8")
    assert deliver.main(args) == 2
    output = capsys.readouterr()
    assert "NOTICE_PDF_REFUSED" in output.err
    assert "right-to-left" in output.err
    assert (dest / "简历" / "简历.md").is_file()
    assert (dest / "简历" / "简历.docx").is_file()
    assert not list(dest.rglob("*.pdf"))
    assert not (dest / "简历" / "简历.tex").exists()
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
