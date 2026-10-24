"""`doctor.py` — what this machine can do, checked by doing it.

The binary-name version of this check has already been wrong in this repo: an
earlier pass looked for `xelatex`, did not find it, and concluded PDF rendering
was at risk — while `tectonic` was installed and every apply run produced its
PDF. `evals/run.md` records the correction as "check for the CAPABILITY rather
than for one binary's name", and these tests hold the script to it.
"""
from skill_docs import read_guidance, skill_context
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


def test_the_pdf_check_renders_a_cv_through_render_cv_without_pandoc(monkeypatch):
    """Pinned against two measured regressions. A machine with tectonic and no
    xelatex must come back able to render — and so must one with tectonic and
    NO pandoc: render_cv compiles its own LaTeX and never calls pandoc, and the
    pandoc requirement reported a false MISS here and on every mode entry."""
    calls = []
    monkeypatch.setattr(doctor, "ENGINE_DIRS", [], raising=False)
    monkeypatch.setattr(doctor.shutil, "which",
                        lambda b: "/x/tectonic" if b == "tectonic" else None)

    def fake_run(cmd, **kw):
        calls.append(cmd)
        pathlib.Path(cmd[cmd.index("--out") + 1]).write_bytes(b"%PDF-1.4\n")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(doctor.subprocess, "run", fake_run)
    ok, detail = doctor.can_render_pdf()
    assert ok is True, detail
    assert "tectonic" in detail
    assert pathlib.Path(calls[0][1]).name == "render_cv.py", calls
    assert calls[0][calls[0].index("--format") + 1] == "pdf"
    assert not any("pandoc" in str(part) for part in calls[0]), calls


def test_no_engine_at_all_is_reported_as_missing(monkeypatch):
    monkeypatch.setattr(doctor, "ENGINE_DIRS", [], raising=False)
    monkeypatch.setattr(doctor.shutil, "which",
                        lambda b: "/x/pandoc" if b == "pandoc" else None)
    ok, detail = doctor.can_render_pdf()
    assert ok is False
    assert "LaTeX engine" in detail


def test_an_engine_that_produces_no_pdf_is_not_a_capability(monkeypatch):
    """Exit code 0 with no file is the shape this whole script exists to catch."""
    monkeypatch.setattr(doctor, "ENGINE_DIRS", [], raising=False)
    monkeypatch.setattr(doctor.shutil, "which",
                        lambda b: "/x/" + b if b in ("pandoc", "tectonic") else None)
    monkeypatch.setattr(doctor.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, "", ""))
    ok, _ = doctor.can_render_pdf()
    assert ok is False


def test_tectonic_system_configuration_panic_names_host_execution_recovery(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which",
                        lambda b: "/x/" + b if b in ("pandoc", "tectonic") else None)
    panic = ("thread 'reqwest-internal-sync-runtime' panicked\n"
             "system-configuration-0.6.1/src/dynamic_store.rs:154: "
             "Attempted to create a NULL object.")
    monkeypatch.setattr(doctor.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 101, b"", panic.encode()))
    ok, detail = doctor.can_render_pdf()
    assert not ok
    assert detail.startswith("HOST_EXECUTION_REQUIRED:")
    assert "reinstall" not in detail


def test_host_execution_diagnostic_does_not_offer_reinstall(monkeypatch):
    monkeypatch.setattr(doctor, "requirements", lambda: [])
    monkeypatch.setattr(doctor, "can_render_report", lambda: (True, "ok"))
    monkeypatch.setattr(doctor, "can_render_pdf",
                        lambda: (False, "HOST_EXECUTION_REQUIRED: restricted host"))
    monkeypatch.setattr(doctor.shutil, "which", lambda name: "/x/" + name)
    pdf_check = next(c for c in doctor.checks()
                     if c["what"].startswith("template-based CV/letter"))
    assert "reinstall" in pdf_check["fix"]
    assert "brew install" not in pdf_check["fix"]


# ---- what a missing thing costs -------------------------------------------

def test_every_check_says_what_it_costs_and_how_to_fix_it():
    """A report that only says MISSING makes the user guess whether it matters."""
    for c in doctor.checks():
        assert c["cost"].strip(), c["what"]
        assert c["fix"].strip(), c["what"]


def test_only_python_packages_are_marked_auto_installable():
    """The diagnostic's pip installer stays scoped; the agent provisions other
    tools through the separate setup workflow."""
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


def test_windows_setup_does_not_suggest_linux_package_commands(monkeypatch):
    monkeypatch.setattr(doctor.platform, "system", lambda: "Windows")
    for binary in ("opencli", "pandoc", "tectonic", "pdftotext"):
        hint = doctor.install_hint(binary)
        assert binary in hint and "references/agent-setup.md" in hint
        assert "apt install" not in hint and "brew install" not in hint


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
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode in (0, 1), r.stderr
    assert "job-hunt environment" in r.stdout


def test_the_skill_tells_a_new_user_to_run_it():
    t = read_guidance("references/agent-setup.md")
    assert "scripts/doctor.py" in t
    assert "--install" in t
    assert "references/agent-setup.md" in t


# ---- the hook that makes any of this run ----------------------------------
#
# `doctor.py` shipped named in SKILL.md and in none of the four mode files, so no
# run ever invoked it: a new user learned their machine could not render a PDF
# when a PDF failed to appear. A capability that does not enter the scaffolding
# is a capability nobody uses.
#
# `enter_mode.py` is the one choke point every mode passes through — all four
# composers require its `mode_entry` record — so the cheap half of the check
# lives there.

def test_the_fast_check_is_sound_about_missing(monkeypatch):
    """It may only warn when it is sure. A warning that fires on a working
    machine is the line everyone filters out."""
    monkeypatch.setattr(doctor.shutil, "which", lambda b: None)
    monkeypatch.setattr(doctor, "ENGINE_DIRS", [], raising=False)
    missing = doctor.fast_capabilities()
    assert ("CV/letter PDF rendering (tectonic or another LaTeX engine; "
            "optional for reports)") in missing
    assert "pdftotext" in missing and "opencli" in missing
    assert "LibreOffice (soffice) to measure Word page counts" in missing


def test_the_fast_check_accepts_tectonic_without_pandoc(monkeypatch):
    """render_cv needs an engine, not pandoc. A tectonic-only machine was told
    on every mode entry that it could not render a CV PDF."""
    monkeypatch.setattr(doctor.shutil, "which",
                        lambda b: None if b == "pandoc" else "/x/" + b)
    monkeypatch.setattr(doctor, "requirements", lambda: [])
    assert doctor.fast_capabilities() == []


def test_the_fast_check_finds_an_engine_where_render_cv_finds_it(monkeypatch, tmp_path):
    """render_cv also looks in fixed install folders off PATH; so must the check."""
    (tmp_path / "tectonic").write_text("")
    monkeypatch.setattr(doctor, "ENGINE_DIRS", [str(tmp_path)], raising=False)
    monkeypatch.setattr(doctor.shutil, "which", lambda b: None if b in ("tectonic", "xelatex", "lualatex", "pdflatex") else "/x/" + b)
    monkeypatch.setattr(doctor, "requirements", lambda: [])
    assert doctor.fast_capabilities() == []


def test_the_fast_check_names_the_cjk_limit_of_pdflatex(monkeypatch):
    monkeypatch.setattr(doctor, "ENGINE_DIRS", [], raising=False)
    monkeypatch.setattr(doctor.shutil, "which",
                        lambda b: None if b in ("tectonic", "xelatex", "lualatex") else "/x/" + b)
    monkeypatch.setattr(doctor, "requirements", lambda: [])
    assert doctor.fast_capabilities() == [
        "CJK CV/letter PDF rendering (xelatex or tectonic; lualatex/pdflatex cannot typeset CJK)"]


def test_the_fast_check_reports_missing_libreoffice(monkeypatch):
    """check_pages needs it to measure cv.docx; without it DOCX_NOT_MEASURED
    blocks check_apply, and nothing said so before the gate failed."""
    monkeypatch.setattr(doctor.shutil, "which",
                        lambda b: None if b in ("soffice", "libreoffice") else "/x/" + b)
    monkeypatch.setattr(doctor, "requirements", lambda: [])
    assert doctor.fast_capabilities() == ["LibreOffice (soffice) to measure Word page counts"]


@pytest.mark.parametrize("found", ["soffice", "libreoffice", None])
def test_checks_report_libreoffice_as_check_pages_finds_it(monkeypatch, found):
    monkeypatch.setattr(doctor, "requirements", lambda: [])
    monkeypatch.setattr(doctor, "can_render_report", lambda: (True, "ok"))
    monkeypatch.setattr(doctor, "can_render_pdf", lambda: (True, "ok"))
    monkeypatch.setattr(doctor.shutil, "which",
                        lambda b: "/x/" + b if b == found or b not in ("soffice", "libreoffice") else None)
    office = next(c for c in doctor.checks() if "LibreOffice" in c["what"])
    assert office["ok"] is (found is not None)
    assert "DOCX_NOT_MEASURED" in office["cost"]
    assert "libreoffice" in office["fix"].casefold()


def test_the_fast_check_stays_quiet_when_the_tools_are_on_path(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda b: "/x/" + b)
    monkeypatch.setattr(doctor, "requirements", lambda: [])
    assert doctor.fast_capabilities() == []


def test_the_fast_check_renders_nothing(monkeypatch):
    """It runs on every mode entry, so it must not shell out at all."""
    ran = []
    monkeypatch.setattr(doctor.subprocess, "run",
                        lambda *a, **k: ran.append(a) or None)
    monkeypatch.setattr(doctor.shutil, "which", lambda b: "/x/" + b)
    doctor.fast_capabilities()
    assert ran == [], f"fast_capabilities shelled out: {ran}"


def test_entering_a_mode_records_and_reports_what_is_missing(tmp_path, monkeypatch, capsys):
    import enter_mode
    monkeypatch.setattr(enter_mode.doctor, "fast_capabilities",
                        lambda: ["pdftotext", "opencli"])
    assert enter_mode.main(["--workspace", str(tmp_path), "--mode", "discover"]) == 0
    err = capsys.readouterr().err
    assert "NOTICE_MISSING_CAPABILITIES" in err
    assert "pdftotext" in err and "doctor.py" in err
    import json
    rec = json.loads((tmp_path / "journal.jsonl").read_text(encoding="utf-8").strip())
    assert rec["capabilities_missing"] == ["pdftotext", "opencli"]


def test_a_missing_capability_never_blocks_mode_entry(tmp_path, monkeypatch):
    """No LaTeX engine still leaves Markdown and .docx; no opencli still leaves
    assess, apply and interview from a pasted posting. Refusing the mode would
    cost more than the missing capability does."""
    import enter_mode
    monkeypatch.setattr(enter_mode.doctor, "fast_capabilities",
                        lambda: ["PDF rendering (pandoc + a LaTeX engine)"])
    assert enter_mode.main(["--workspace", str(tmp_path), "--mode", "apply"]) == 0


def test_a_complete_machine_leaves_an_empty_list_not_a_missing_field(tmp_path, monkeypatch):
    """A record written without the field cannot be told from one that found
    nothing missing — the same silence the mode_entry record exists to break."""
    import json
    import enter_mode
    monkeypatch.setattr(enter_mode.doctor, "fast_capabilities", lambda: [])
    assert enter_mode.main(["--workspace", str(tmp_path), "--mode", "assess"]) == 0
    rec = json.loads((tmp_path / "journal.jsonl").read_text(encoding="utf-8").strip())
    assert rec["capabilities_missing"] == []


def test_the_skill_says_the_check_runs_automatically():
    """Documenting a hook that does not exist is how NEXT_MODES happened. This
    one does exist, and the claim is pinned to the code that implements it."""
    t = " ".join(read_guidance("references/agent-setup.md").split())
    assert "runs on its own, every mode entry" in t
    assert "NOTICE_MISSING_CAPABILITIES" in t
    src = (REPO / "scripts" / "enter_mode.py").read_text(encoding="utf-8")
    assert "fast_capabilities()" in src
    assert "NOTICE_MISSING_CAPABILITIES" in src


def test_python_install_preserves_interpreter_path_with_spaces(monkeypatch):
    executable = "/tmp/Fresh User/python env/bin/python"
    monkeypatch.setattr(doctor.sys, "executable", executable)
    monkeypatch.setattr(doctor, "requirements", lambda: [("PyYAML", "yaml")])
    monkeypatch.setattr(doctor, "importable", lambda module: False)
    monkeypatch.setattr(doctor, "can_render_pdf", lambda: (False, "unavailable"))
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    missing = [c for c in doctor.checks() if c.get("auto")]
    calls = []

    def installer(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(doctor.subprocess, "run", installer)
    assert doctor.install_python(missing) == 1
    assert calls == [[executable, "-m", "pip", "install", "PyYAML"]]


def test_pdflatex_only_renders_latin_cvs_and_names_the_cjk_limit(monkeypatch):
    """render_cv accepts pdflatex for a Latin CV but needs XeTeX for CJK."""
    monkeypatch.setattr(doctor, 'ENGINE_DIRS', [], raising=False)
    monkeypatch.setattr(doctor.shutil, 'which', lambda name: '/bin/' + name if name in {'pandoc', 'pdflatex'} else None)

    def fake_run(cmd, **kw):
        pathlib.Path(cmd[cmd.index('--out') + 1]).write_bytes(b'%PDF-1.4\n')
        return subprocess.CompletedProcess(cmd, 0, b'', b'')

    monkeypatch.setattr(doctor.subprocess, 'run', fake_run)
    ok, detail = doctor.can_render_pdf()
    assert ok is True
    assert 'pdflatex' in detail and 'CJK' in detail and 'xelatex or tectonic' in detail


def test_opencli_setup_hint_preserves_custom_adapters(monkeypatch):
    for system in ('Darwin', 'Linux', 'Windows'):
        monkeypatch.setattr(doctor.platform, 'system', lambda: system)
        hint = doctor.install_hint('opencli')
        assert 'references/agent-setup.md' in hint and 'npm install -g' not in hint


@pytest.mark.parametrize('available', [set(), {'pdflatex'}, {'lualatex', 'pdflatex'},
                                       {'tectonic'}, {'xelatex'}, {'xelatex', 'tectonic'},
                                       {'pdflatex', 'xelatex'}])
def test_cv_engine_search_agrees_with_render_cv_without_bootstrap_import(monkeypatch, available):
    """doctor copies render_cv's engine search because render_cv needs PyYAML
    and python-docx, which a fresh machine does not have yet. A copy is only
    safe while it gives the same answer."""
    import render_cv
    assert doctor.ENGINE_DIRS == render_cv._ENGINE_DIRS
    monkeypatch.setattr(doctor, 'ENGINE_DIRS', [])
    monkeypatch.setattr(render_cv, '_ENGINE_DIRS', [])
    monkeypatch.setattr(doctor.shutil, 'which', lambda b: '/bin/' + b if b in available else None)
    for cjk in (False, True):
        assert doctor.find_cv_engine(cjk) == render_cv.find_latex_engine(cjk=cjk)
    result = subprocess.run([sys.executable, '-S', str(REPO / 'scripts/doctor.py'), '--help'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_missing_pdf_verifier_is_not_reported_as_a_word_failure(monkeypatch):
    monkeypatch.setattr(doctor, 'requirements', lambda: [('PyMuPDF', 'pymupdf')])
    monkeypatch.setattr(doctor, 'importable', lambda name: False)
    monkeypatch.setattr(doctor, 'can_render_pdf', lambda: (False, 'not checked'))
    monkeypatch.setattr(doctor.shutil, 'which', lambda name: None)
    check = doctor.checks()[0]
    assert 'PDF' in check['cost'] and '.docx' not in check['cost']
