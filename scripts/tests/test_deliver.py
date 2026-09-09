"""`deliver.py` — the hand-off step, and the ordering it belongs to.

A workspace under `~/.claude/job-profiles/` is where the skill works and not
where a person looks. These tests pin what gets handed over, what deliberately
does not, and the one thing a PDF pipeline must never do quietly: drop the
characters it could not render.
"""
import pathlib
import shutil
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import deliver  # noqa: E402

HAVE_PDF = bool(shutil.which("pandoc") and shutil.which("tectonic")
                and shutil.which("pdftotext"))


def build(tmp_path, md="# rows\n"):
    ws = tmp_path / "2026-09-06-round"
    (ws / "raw" / "opencli-help").mkdir(parents=True)
    (ws / "mock").mkdir()
    (ws / "report.md").write_text(md, encoding="utf-8")
    (ws / "shortlist.yaml").write_text("rows: []\n", encoding="utf-8")
    import pymupdf
    with pymupdf.open() as doc:
        doc.new_page().insert_text((72, 72), "Candidate CV")
        doc.save(ws / "cv.pdf")
    (ws / "mock" / "assessment-1.md").write_text("# round 1\n", encoding="utf-8")
    (ws / "journal.jsonl").write_text('{"action":"gate"}\n', encoding="utf-8")
    (ws / "raw" / "51job-1.json").write_text("[]", encoding="utf-8")
    (ws / "51job-1.err").write_text("boom\n", encoding="utf-8")
    (ws / ".DS_Store").write_bytes(b"\x00")
    return ws


def run(ws, dest, *extra):
    return deliver.main(["--workspace", str(ws), "--to", str(dest), *extra])


# ---- what lands, and where ------------------------------------------------

def test_client_documents_share_one_explicit_folder(tmp_path):
    ws = build(tmp_path)
    dest = tmp_path / "consultation"
    assert run(ws, dest, "--no-pdf") == 0
    assert {p.name for p in dest.iterdir()} == {"简历", "报告"}
    assert {p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file()} == {
        "报告/求职建议报告.md", "简历/简历.pdf"}


def test_default_destination_is_a_consultation_folder(tmp_path, monkeypatch):
    ws = build(tmp_path)
    monkeypatch.setattr(deliver, "DEFAULT_ROOT", tmp_path / "Downloads")
    assert deliver.main(["--workspace", str(ws), "--no-pdf"]) == 0
    assert (tmp_path / "Downloads" / ws.name / "报告" / "求职建议报告.md").is_file()


# ---- what stays behind ----------------------------------------------------

def test_the_provenance_chain_is_left_in_the_workspace(tmp_path):
    """`raw/` and the receipts are what an audit reads IN PLACE.

    Copying them makes a second, drifting copy of the only evidence any claim in
    these documents is traced to — and it is the bulk of the bytes.
    """
    ws = build(tmp_path)
    dest = tmp_path / "out"
    assert run(ws, dest, "--no-pdf") == 0
    names = {p.name for p in dest.iterdir()}
    assert not any("journal" in n or n.endswith(".err") or "51job-1.json" in n
                   for n in names), names
    assert (ws / "raw" / "51job-1.json").is_file()
    assert (ws / "journal.jsonl").is_file()


def test_it_is_a_copy_and_never_a_move(tmp_path):
    """`paths.py` owns that layout, apply mode's resume lookup finds work BY the
    path shape, and `check_claims.py` fingerprints the master profile there."""
    ws = build(tmp_path)
    before = sorted(p.relative_to(ws) for p in ws.rglob("*") if p.is_file())
    assert run(ws, tmp_path / "out", "--no-pdf") == 0
    assert before == sorted(p.relative_to(ws) for p in ws.rglob("*") if p.is_file())


# ---- the PDF, which is verified rather than trusted -----------------------

def test_a_pdf_that_dropped_characters_is_deleted_not_delivered(tmp_path, monkeypatch):
    """MEASURED: `pandoc --pdf-engine=tectonic` on a Chinese document exits 0 and
    writes a PDF whose every CJK glyph is a box — 528 characters in, 0 read back.

    A wrong artifact behind a green exit code is the failure this whole check
    exists for, so the round-trip is the gate and the exit code is not.
    """
    ws = build(tmp_path, md="# 岗位候选\n\n这是中文内容。\n")
    dest = tmp_path / "out"
    monkeypatch.setattr(deliver, "_render_reportlab_cjk",
                        lambda *args: (False, "disabled for this regression"))
    monkeypatch.setattr(deliver, "pick_cjk_font", lambda *args: "SomeFont")
    monkeypatch.setattr(deliver, "_pandoc",
                        lambda md, pdf, font: (pdf.write_bytes(b"%PDF"), True)[1])
    monkeypatch.setattr(deliver, "pdf_text", lambda pdf: "boxes only, no CJK")
    assert run(ws, dest) == 2
    assert not (dest / "报告" / "求职建议报告.pdf").exists()
    assert (dest / "报告" / "求职建议报告.md").is_file(), "the Markdown still ships"


def test_chinese_report_uses_reportlab_when_pandoc_has_no_cjk_font(tmp_path, monkeypatch):
    ws = build(tmp_path, md=(
        "# 岗位候选\n\n这是中文内容。\n\n"
        "| 优先级 | 岗位 | 公司与地点 | 展示薪资 | 初判与投入 | 依据 |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| 1 | 大模型工程师 | 示例公司，上海 | 25-40K | worth_applying | 多模态模型经验 |\n"
    ))
    dest = tmp_path / "out"
    monkeypatch.setattr(deliver, "pick_cjk_font", lambda *args: None)
    assert run(ws, dest) == 0
    pdf = dest / "报告" / "求职建议报告.pdf"
    assert pdf.is_file()
    assert "大模型工程师" in deliver.pdf_text(pdf)


def test_cjk_detection_and_counting():
    assert deliver.has_cjk("岗位候选")
    assert deliver.has_cjk("ソフトウェア")
    assert deliver.has_cjk("소프트웨어")
    assert not deliver.has_cjk("Senior ATD Engineer - System (Open)")
    assert deliver.cjk_chars("岗位候选 x3") == 4


def test_raw_source_urls_become_short_clickable_links_in_chinese_pdfs():
    rendered = deliver._reportlab_inline(
        "来源：<https://www.zhipin.com/job_detail/abc.html?ka=search_list&foo=bar>、"
        "<https://jobs.51job.com/shanghai/123456.html>"
    )
    assert ">zhipin.com</link>" in rendered
    assert "href=\"https://www.zhipin.com/job_detail/abc.html?ka=search_list&amp;foo=bar\"" in rendered
    assert ">jobs.51job.com</link>" in rendered
    assert "href=\"https://jobs.51job.com/shanghai/123456.html\"" in rendered
    assert "&lt;https" not in rendered


def test_chinese_pdf_contains_distinct_clickable_urls(tmp_path):
    first = "https://www.zhipin.com/job_detail/abc.html?ka=search_list&foo=bar"
    second = "https://jobs.51job.com/shanghai/123456.html"
    ws = build(tmp_path, md=f"# 岗位候选\n\n- <{first}>、<{second}>\n")
    dest = tmp_path / "out"
    assert run(ws, dest) == 0
    import pymupdf
    with pymupdf.open(dest / "报告" / "求职建议报告.pdf") as pdf:
        urls = {link.get("uri") for page in pdf for link in page.get_links()}
    assert {first, second} <= urls


def test_pdf_with_an_authored_link_but_no_link_annotation_is_refused(tmp_path):
    """Blue-looking text is not an actionable link unless the PDF annotates it."""
    import pymupdf
    pdf = tmp_path / "unlinked.pdf"
    with pymupdf.open() as document:
        document.new_page().insert_text((72, 72), "Open posting")
        document.save(pdf)

    ok, why = deliver._verify_pdf(
        pdf, "[Open posting](https://jobs.example.test/roles/123)", False)
    assert not ok
    assert "PDF_LINKS_MISSING" in why
    assert not pdf.exists(), "an unclickable report PDF must not be delivered"


@pytest.mark.parametrize("source", ["研究エンジニアと機械学習", "AI 연구개발 엔지니어"])
def test_japanese_and_korean_keep_the_existing_cjk_renderer(tmp_path, monkeypatch, source):
    md, pdf = tmp_path / "report.md", tmp_path / "report.pdf"
    md.write_text(source, encoding="utf-8")
    monkeypatch.setattr(deliver, "visible_markdown", lambda _: source)
    monkeypatch.setattr(deliver, "_render_reportlab_cjk",
                        lambda *args: pytest.fail("Chinese renderer was selected"))
    monkeypatch.setattr(deliver, "_pandoc",
                        lambda _md, output, _font: (output.write_bytes(b"%PDF"), True)[1])
    monkeypatch.setattr(deliver, "glyph_findings", lambda _: [])
    monkeypatch.setattr(deliver, "pdf_text", lambda _: source)
    assert deliver.render_pdf(md, pdf, "CJK test font") == (True, "")


@pytest.mark.skipif(not HAVE_PDF, reason="needs pandoc + tectonic + pdftotext")
def test_a_chinese_document_really_round_trips_through_a_real_pdf(tmp_path):
    """The end-to-end one. Everything above can pass on a mocked renderer."""
    ws = build(tmp_path, md="# 岗位候选\n\n医学影像与图像重建方向的岗位清单。\n")
    dest = tmp_path / "out"
    assert run(ws, dest) == 0
    pdf = dest / "报告" / "求职建议报告.pdf"
    assert pdf.is_file()
    assert deliver.cjk_chars(deliver.pdf_text(pdf)) >= 15


# ---- could-not-run, never a silent success --------------------------------

def test_an_unwritable_destination_exits_2_and_copies_nothing(tmp_path, monkeypatch):
    """macOS TCC can start refusing ~/Downloads part-way through a session, and
    `os.access` says yes while the write fails — so the probe writes a real file."""
    ws = build(tmp_path)
    monkeypatch.setattr(deliver, "writable", lambda d: (False, "Operation not permitted"))
    dest = tmp_path / "blocked"
    assert deliver.main(["--workspace", str(ws), "--to", str(dest)]) == 2
    assert not dest.exists()


def test_a_missing_workspace_exits_2(tmp_path):
    assert deliver.main(["--workspace", str(tmp_path / "nope"),
                         "--to", str(tmp_path / "out")]) == 2


def test_delivering_into_the_workspace_is_refused(tmp_path):
    ws = build(tmp_path)
    assert deliver.main(["--workspace", str(ws), "--to", str(ws / "export")]) == 2
    assert deliver.main(["--workspace", str(ws), "--to", str(ws)]) == 2


def test_a_workspace_with_only_provenance_exits_2(tmp_path):
    ws = tmp_path / "empty-round"
    (ws / "raw").mkdir(parents=True)
    (ws / "raw" / "x.json").write_text("[]", encoding="utf-8")
    (ws / "journal.jsonl").write_text("{}\n", encoding="utf-8")
    assert deliver.main(["--workspace", str(ws), "--to", str(tmp_path / "out")]) == 2


def test_discover_delivery_requires_a_checked_shortlist(tmp_path):
    ws = build(tmp_path)
    deliver.journal.append(ws, {"action": "mode_entry", "mode": "discover"})
    dest = tmp_path / "out"
    assert run(ws, dest, "--no-pdf") == 2
    assert not dest.exists()

    (ws / "shortlist.md").write_text("# Shortlist\n", encoding="utf-8")
    deliver.journal.receipt(ws, "check_shortlist", {}, "pass")
    assert run(ws, dest, "--no-pdf") == 0


def test_discover_delivery_requires_every_shortlist_link_in_the_report(tmp_path):
    ws = build(tmp_path, md="# Client report\n")
    url = "https://jobs.example.test/roles/123?tracking=source"
    (ws / "shortlist.yaml").write_text(
        f"rows:\n  - url: {url}\n", encoding="utf-8")
    (ws / "shortlist.md").write_text("# Shortlist\n", encoding="utf-8")
    deliver.journal.append(ws, {"action": "mode_entry", "mode": "discover"})
    deliver.journal.receipt(ws, "check_shortlist", {}, "pass")

    dest = tmp_path / "out"
    assert run(ws, dest, "--no-pdf") == 2
    assert not dest.exists()

    (ws / "report.md").write_text(
        f"# Client report\n\n[Open posting]({url})\n", encoding="utf-8")
    assert run(ws, dest, "--no-pdf") == 0


def test_discover_delivery_refuses_an_unreadable_shortlist(tmp_path):
    """Delivery must return its normal incomplete status, never parse-crash."""
    ws = build(tmp_path)
    (ws / "shortlist.yaml").write_text("rows: [unterminated", encoding="utf-8")
    (ws / "shortlist.md").write_text("# Shortlist\n", encoding="utf-8")
    deliver.journal.append(ws, {"action": "mode_entry", "mode": "discover"})
    deliver.journal.receipt(ws, "check_shortlist", {}, "pass")

    dest = tmp_path / "out"
    assert run(ws, dest, "--no-pdf") == 2
    assert not dest.exists()


def test_it_runs_as_a_script(tmp_path):
    """The mode files tell the model to run a COMMAND. It has to work as one."""
    ws = build(tmp_path)
    dest = tmp_path / "out"
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "deliver.py"),
                        "--workspace", str(ws), "--to", str(dest), "--no-pdf"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    assert str(dest) in r.stdout, "the path to quote must be printed"


# ---- the skill has to tell the run to do this -----------------------------

@pytest.mark.parametrize("mode", ["discover", "assess", "apply", "interview"])
def test_every_mode_file_names_the_delivery_step(mode):
    """Prose in SKILL.md that only one mode repeats is prose three modes skip."""
    text = (REPO / "modes" / f"{mode}.md").read_text(encoding="utf-8")
    assert "deliver.py" in text, f"{mode}.md never tells the run to hand the files over"
    assert "~/Downloads" in text


def test_the_skill_file_lists_delivery_and_the_path_to_tell_the_user():
    text = (REPO / "SKILL.md").read_text(encoding="utf-8")
    assert "scripts/deliver.py" in text
    assert "~/Downloads" in text


# ---- flattening must not silently drop a file -----------------------------
#
# MEASURED on the first version of this script, by probing it rather than by
# reading it. `mock/notes.md` and a root-level `notes.md` both became
# `<slug>-notes.md`: one overwrote the other, and the run printed "Delivered 2
# file(s)" over a directory holding one. Interview mode writes
# `mock/transcript-n.md`, `mock/assessment-n.md` and `mock/answer-guide.md`
# beside root-level outputs, so this is the ordinary layout, not a corner.

def test_internal_reports_are_excluded_even_if_markdown(tmp_path):
    ws = build(tmp_path)
    (ws / "completion.md").write_text("TOOL BUGS")
    (ws / "mock" / "report.md").write_text("INTERNAL REVIEW")
    dest = tmp_path / "out"
    assert run(ws, dest, "--no-pdf") == 0
    assert not any("TOOL BUGS" in p.read_text() or "INTERNAL REVIEW" in p.read_text()
                   for p in dest.rglob("*.md"))


def test_the_reported_count_matches_what_actually_landed(tmp_path, capsys):
    """The overwrite was survivable; reporting two deliveries over one file was
    the part that would have gone unnoticed."""
    ws = tmp_path / "round"
    (ws / "mock").mkdir(parents=True)
    (ws / "report.md").write_text("ROOT\n", encoding="utf-8")
    (ws / "mock" / "notes.md").write_text("NESTED\n", encoding="utf-8")
    assert run(ws, tmp_path / "out", "--no-pdf") == 0
    said = capsys.readouterr().out
    landed = len([p for p in (tmp_path / "out").rglob("*") if p.is_file()])
    assert f"Delivered {landed} file(s)" in said


def test_flat_name_keeps_the_whole_relative_path():
    assert deliver.flat_name("r", pathlib.Path("mock/assessment-1.md")) == \
        "r-mock__assessment-1.md"
    assert deliver.flat_name("r", pathlib.Path("cv.md")) == "r-cv.md"


# ---- a hand-off that left no trace ----------------------------------------
#
# The gates run BEFORE delivery, so no composer can check that delivery
# happened — and a gate that says what to do next is prompting rather than
# checking, which this repo has decided against on purpose
# (test_mode_declaration_and_handoff.py: "a clean gate run still says nothing on
# stdout"). What is left is a record: a later reader can tell a run that skipped
# the last step from one that took it.

def test_a_delivery_leaves_a_record_in_the_workspace_journal(tmp_path):
    import json
    ws = build(tmp_path)
    assert run(ws, tmp_path / "out", "--no-pdf") == 0
    records = [json.loads(l) for l in
               (ws / "journal.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    delivery = [r for r in records if r.get("action") == "delivery"]
    assert len(delivery) == 1
    assert delivery[0]["destination"].endswith("out")
    assert "报告/求职建议报告.md" in delivery[0]["files"]


def test_the_record_is_not_a_gate_receipt(tmp_path):
    """Delivery decides nothing and has no verdict. Filing it as a gate would
    put a passing receipt in the journal for something that was never a check —
    and `check_apply` fails on ANY gate receipt reading `fail`, named or not."""
    import json

    def gates(ws):
        return [json.loads(l) for l
                in (ws / "journal.jsonl").read_text(encoding="utf-8").splitlines()
                if l.strip() and json.loads(l).get("action") == "gate"]

    ws = build(tmp_path)              # the fixture seeds one unrelated gate line
    before = len(gates(ws))
    assert run(ws, tmp_path / "out", "--no-pdf") == 0
    assert len(gates(ws)) == before, "delivery added a gate receipt"
    delivery = [json.loads(l) for l
                in (ws / "journal.jsonl").read_text(encoding="utf-8").splitlines()
                if l.strip() and json.loads(l).get("action") == "delivery"][0]
    assert "verdict" not in delivery and "receipt_hash" not in delivery


def test_a_refused_pdf_is_named_in_the_record(tmp_path, monkeypatch):
    """The reason a PDF is missing has to survive the session that produced it.

    Asserted over the WHOLE list, never `[0]`. How many PDFs are refused depends
    on the machine: with a LaTeX engine only the CJK one is (its font is mocked
    away), without one every .md is, and `mock/assessment-1.md` sorts first. The
    first version of this test indexed [0], passed here and failed in CI — an
    environment-dependent assertion, which is a test bug and not a finding.
    """
    import json
    ws = build(tmp_path, md="# 岗位候选\n\n中文内容。\n")
    monkeypatch.setattr(deliver, "_render_reportlab_cjk",
                        lambda *args: (False, "disabled for this regression"))
    monkeypatch.setattr(deliver, "pick_cjk_font", lambda *args: None)
    assert run(ws, tmp_path / "out") == 2
    rec = [json.loads(l) for l in
           (ws / "journal.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    delivery = [r for r in rec if r.get("action") == "delivery"][0]
    refused = delivery["pdf_refused"]
    assert refused, "a refused PDF left no trace"
    shortlist = [n for n in refused if "求职建议报告.pdf" in n]
    assert shortlist, f"the CJK document is not named among {refused}"
    assert "CJK font" in shortlist[0], (
        "the entry must carry WHY, not just that something was refused: "
        f"{shortlist[0]}")


def test_an_unwritable_workspace_journal_does_not_fail_the_delivery(tmp_path, monkeypatch):
    """The files are already copied at that point. Failing here would report a
    delivery that did happen as one that did not."""
    ws = build(tmp_path)
    monkeypatch.setattr(deliver.journal, "append",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("read-only")))
    assert run(ws, tmp_path / "out", "--no-pdf") == 0


@pytest.mark.parametrize('text', ['You have an 80% chance of getting an interview.',
                                  'You are likely to be hired.'])
def test_delivery_refuses_predictions_in_client_report(tmp_path, text):
    ws = build(tmp_path, md=text)
    dest = tmp_path / 'out'
    assert run(ws, dest, '--no-pdf') == 2
    assert not dest.exists()
