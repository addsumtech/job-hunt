"""`doctor.py` — what this machine can do, checked by doing it.

The binary-name version of this check has already been wrong in this repo: an
earlier pass looked for `xelatex`, did not find it, and concluded PDF rendering
was at risk — while `tectonic` was installed and every apply run produced its
PDF. `evals/run.md` records the correction as "check for the CAPABILITY rather
than for one binary's name", and these tests hold the script to it.
"""
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import doctor  # noqa: E402


def test_requirements_are_parsed_not_duplicated():
    """A second hard-coded list drifts from requirements.txt the first time one
    of them changes, and the drift shows up as a working machine reported
    broken."""
    parsed = dict(doctor.requirements())
    assert parsed, "requirements.txt produced no checks"
    txt = (REPO / "requirements.txt").read_text(encoding="utf-8")
    for pkg in parsed:
        assert pkg in txt


def test_the_install_name_and_the_import_name_are_not_assumed_equal():
    """`python-docx` imports as `docx` and `PyYAML` as `yaml`. Deriving the
    module from the install name reports both as missing on a machine that has
    them."""
    parsed = dict(doctor.requirements())
    assert parsed.get("PyYAML") == "yaml"
    assert parsed.get("python-docx") == "docx"


def test_the_pdf_check_renders_a_pdf_rather_than_looking_for_xelatex(monkeypatch):
    """Pinned against the measured regression: a machine with tectonic and no
    xelatex must come back able to render."""
    calls = []
    monkeypatch.setattr(doctor.shutil, "which",
                        lambda b: "/x/" + b if b in ("pandoc", "tectonic") else None)

    def fake_run(cmd, **kw):
        calls.append(cmd)
        pathlib.Path(cmd[cmd.index("-o") + 1]).write_bytes(b"%PDF-1.4\n")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(doctor.subprocess, "run", fake_run)
    ok, detail = doctor.can_render_pdf()
    assert ok is True
    assert "tectonic" in detail
    assert any("--pdf-engine=tectonic" in c for c in calls[0]), calls


def test_no_engine_at_all_is_reported_as_missing(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which",
                        lambda b: "/x/pandoc" if b == "pandoc" else None)
    ok, detail = doctor.can_render_pdf()
    assert ok is False
    assert "LaTeX engine" in detail


def test_an_engine_that_produces_no_pdf_is_not_a_capability(monkeypatch):
    """Exit code 0 with no file is the shape this whole script exists to catch."""
    monkeypatch.setattr(doctor.shutil, "which",
                        lambda b: "/x/" + b if b in ("pandoc", "tectonic") else None)
    monkeypatch.setattr(doctor.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, "", ""))
    ok, _ = doctor.can_render_pdf()
    assert ok is False


# ---- what a missing thing costs -------------------------------------------

def test_every_check_says_what_it_costs_and_how_to_fix_it():
    """A report that only says MISSING makes the user guess whether it matters."""
    for c in doctor.checks():
        assert c["cost"].strip(), c["what"]
        assert c["fix"].strip(), c["what"]


def test_only_python_packages_are_marked_auto_installable():
    """System binaries are never installed for the user. A LaTeX engine is a
    package-manager action of several hundred megabytes, and running one unasked
    is the class of act source-policy.md keeps on its Red list."""
    for c in doctor.checks():
        if c.get("auto"):
            assert c["what"].startswith("python package"), c["what"]
        else:
            assert "pip install" not in c["fix"], c["what"]


def test_the_platform_specific_hint_is_actually_platform_specific(monkeypatch):
    monkeypatch.setattr(doctor.platform, "system", lambda: "Darwin")
    assert doctor.install_hint("pdftotext") == "brew install poppler"
    monkeypatch.setattr(doctor.platform, "system", lambda: "Linux")
    assert doctor.install_hint("pdftotext") == "sudo apt install poppler-utils"


def test_an_unknown_binary_still_gets_a_hint(monkeypatch):
    monkeypatch.setattr(doctor.platform, "system", lambda: "Linux")
    assert "wkhtmltopdf" in doctor.install_hint("wkhtmltopdf")


# ---- exit codes ------------------------------------------------------------

def test_a_complete_machine_exits_0(monkeypatch, capsys):
    monkeypatch.setattr(doctor, "checks", lambda: [
        {"what": "x", "ok": True, "cost": "c", "fix": "f", "auto": False}])
    assert doctor.main([]) == 0
    assert "Everything this skill needs is present" in capsys.readouterr().out


def test_a_missing_capability_exits_1_and_names_the_cost(monkeypatch, capsys):
    monkeypatch.setattr(doctor, "checks", lambda: [
        {"what": "render a PDF", "ok": False,
         "cost": "PDF output unavailable", "fix": "brew install tectonic",
         "auto": False}])
    assert doctor.main([]) == 1
    out = capsys.readouterr().out
    assert "PDF output unavailable" in out and "brew install tectonic" in out


def test_install_never_shells_out_for_a_system_binary(monkeypatch):
    """The guard that matters. `--install` on a machine missing only a LaTeX
    engine must run nothing at all."""
    ran = []
    monkeypatch.setattr(doctor, "checks", lambda: [
        {"what": "render a PDF", "ok": False, "cost": "c",
         "fix": "brew install tectonic", "auto": False}])
    monkeypatch.setattr(doctor.subprocess, "run",
                        lambda *a, **k: ran.append(a) or
                        subprocess.CompletedProcess([], 0, "", ""))
    assert doctor.main(["--install"]) == 1
    assert ran == [], f"--install ran a system command: {ran}"


def test_it_runs_as_a_script():
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "doctor.py")],
                       capture_output=True, text=True)
    assert r.returncode in (0, 1), r.stderr
    assert "job-hunt environment" in r.stdout


def test_the_skill_tells_a_new_user_to_run_it():
    t = (REPO / "SKILL.md").read_text(encoding="utf-8")
    assert "scripts/doctor.py" in t
    assert "--install" in t
    assert "never installed for the user" in t or "never installed for you" in t
