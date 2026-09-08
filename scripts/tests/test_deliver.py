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
    (ws / "shortlist.md").write_text(md, encoding="utf-8")
    (ws / "shortlist.yaml").write_text("rows: []\n", encoding="utf-8")
    (ws / "cv.pdf").write_bytes(b"%PDF-1.4\n")
    (ws / "mock" / "assessment-1.md").write_text("# round 1\n", encoding="utf-8")
    (ws / "journal.jsonl").write_text('{"action":"gate"}\n', encoding="utf-8")
    (ws / "raw" / "51job-1.json").write_text("[]", encoding="utf-8")
    (ws / "51job-1.err").write_text("boom\n", encoding="utf-8")
    (ws / ".DS_Store").write_bytes(b"\x00")
    return ws


def run(ws, dest, *extra):
    return deliver.main(["--workspace", str(ws), "--to", str(dest), *extra])


# ---- what lands, and where ------------------------------------------------

def test_files_land_flat_with_the_round_as_a_filename_prefix(tmp_path):
    """No folder: the user asked for the result files themselves.

    The prefix is not a folder in disguise. Two rounds both produce
    `shortlist.md`, and a bare name would have the second silently overwrite the
    first in a directory the user also keeps everything else in.
    """
    ws = build(tmp_path)
    dest = tmp_path / "out"
    assert run(ws, dest, "--no-pdf") == 0
    assert (dest / "2026-09-06-round-shortlist.md").is_file()
    assert (dest / "2026-09-06-round-shortlist.yaml").is_file()
    assert (dest / "2026-09-06-round-cv.pdf").is_file()
    assert not (dest / "2026-09-06-round").exists(), "no subdirectory"
    assert not (dest / "shortlist.md").exists(), "unprefixed name would collide"


def test_a_nested_output_is_flattened_with_its_directory_in_the_name(tmp_path):
    """`mock/assessment-1.md` keeps `mock` in the delivered name, joined by `__`.

    Flattening on the basename alone is what let two same-named files in
    different directories overwrite each other — see the collision tests below.
    """
    ws = build(tmp_path)
    dest = tmp_path / "out"
    assert run(ws, dest, "--no-pdf") == 0
    assert (dest / "2026-09-06-round-mock__assessment-1.md").is_file()
    assert not (dest / "2026-09-06-round-assessment-1.md").exists()


def test_the_default_destination_is_downloads_itself():
    """The user named Downloads. A default nobody can find is the bug this
    script exists to fix, and a subfolder under it was the first version's."""
    assert deliver.DEFAULT_ROOT == pathlib.Path.home() / "Downloads"


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
    monkeypatch.setattr(deliver, "pick_cjk_font", lambda *args: "SomeFont")
    monkeypatch.setattr(deliver, "_pandoc",
                        lambda md, pdf, font: (pdf.write_bytes(b"%PDF"), True)[1])
    monkeypatch.setattr(deliver, "pdf_text", lambda pdf: "boxes only, no CJK")
    assert run(ws, dest) == 0
    assert not (dest / "2026-09-06-round-shortlist.pdf").exists()
    assert (dest / "2026-09-06-round-shortlist.md").is_file(), "the Markdown still ships"


def test_no_cjk_font_refuses_the_pdf_and_still_ships_the_markdown(tmp_path, monkeypatch):
    ws = build(tmp_path, md="# 岗位候选\n\n这是中文内容。\n")
    dest = tmp_path / "out"
    monkeypatch.setattr(deliver, "pick_cjk_font", lambda *args: None)
    assert run(ws, dest) == 0
    assert not (dest / "2026-09-06-round-shortlist.pdf").exists()
    assert (dest / "2026-09-06-round-shortlist.md").is_file()


def test_cjk_detection_and_counting():
    assert deliver.has_cjk("岗位候选")
    assert deliver.has_cjk("ソフトウェア")
    assert deliver.has_cjk("소프트웨어")
    assert not deliver.has_cjk("Senior ATD Engineer - System (Open)")
    assert deliver.cjk_chars("岗位候选 x3") == 4


@pytest.mark.skipif(not HAVE_PDF, reason="needs pandoc + tectonic + pdftotext")
def test_a_chinese_document_really_round_trips_through_a_real_pdf(tmp_path):
    """The end-to-end one. Everything above can pass on a mocked renderer."""
    ws = build(tmp_path, md="# 岗位候选\n\n医学影像与图像重建方向的岗位清单。\n")
    dest = tmp_path / "out"
    assert run(ws, dest) == 0
    pdf = dest / "2026-09-06-round-shortlist.pdf"
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


def test_it_runs_as_a_script(tmp_path):
    """The mode files tell the model to run a COMMAND. It has to work as one."""
    ws = build(tmp_path)
    dest = tmp_path / "out"
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "deliver.py"),
                        "--workspace", str(ws), "--to", str(dest), "--no-pdf"],
                       capture_output=True, text=True)
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

def test_two_same_named_files_in_different_directories_both_survive(tmp_path):
    ws = tmp_path / "round"
    (ws / "mock").mkdir(parents=True)
    (ws / "notes.md").write_text("ROOT\n", encoding="utf-8")
    (ws / "mock" / "notes.md").write_text("NESTED\n", encoding="utf-8")
    dest = tmp_path / "out"
    assert run(ws, dest, "--no-pdf") == 0
    assert (dest / "round-notes.md").read_text(encoding="utf-8") == "ROOT\n"
    assert (dest / "round-mock__notes.md").read_text(encoding="utf-8") == "NESTED\n"


def test_the_reported_count_matches_what_actually_landed(tmp_path, capsys):
    """The overwrite was survivable; reporting two deliveries over one file was
    the part that would have gone unnoticed."""
    ws = tmp_path / "round"
    (ws / "mock").mkdir(parents=True)
    (ws / "notes.md").write_text("ROOT\n", encoding="utf-8")
    (ws / "mock" / "notes.md").write_text("NESTED\n", encoding="utf-8")
    assert run(ws, tmp_path / "out", "--no-pdf") == 0
    said = capsys.readouterr().out
    landed = len(list((tmp_path / "out").iterdir()))
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
    assert "2026-09-06-round-shortlist.md" in delivery[0]["files"]


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
    monkeypatch.setattr(deliver, "pick_cjk_font", lambda *args: None)
    assert run(ws, tmp_path / "out") == 0
    rec = [json.loads(l) for l in
           (ws / "journal.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    delivery = [r for r in rec if r.get("action") == "delivery"][0]
    refused = delivery["pdf_refused"]
    assert refused, "a refused PDF left no trace"
    shortlist = [n for n in refused if "shortlist.pdf" in n]
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
