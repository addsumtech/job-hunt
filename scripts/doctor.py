#!/usr/bin/env python3
"""What this machine can and cannot do, and how to fix what it cannot.

Run it once for a new user, before the first mode. Every check answers a
CAPABILITY question rather than a binary-name question, because the binary-name
version has already been wrong here: an earlier check looked for `xelatex`, did
not find it, and concluded PDF rendering was at risk — while `tectonic` was
installed and every PDF rendered fine. So the PDF check renders a PDF.

This diagnostic's --install option handles requirements.txt Python packages.
The agent performs other needed setup using references/agent-setup.md, including
system tools and daily-browser CDP. The user grants browser connection consent.
A diagnostic run alone never installs system tools.

Exit codes: 0 everything the skill needs is present, 1 something is missing
(the report says what it costs), 2 the check itself could not run.
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import platform
import re
import shutil
import subprocess
import sys
import tempfile

# Keep diagnostics importable before requirements.txt has been installed.
REPORT_ENGINES = ("tectonic", "xelatex")

REPO = pathlib.Path(__file__).resolve().parent.parent
REQUIREMENTS = REPO / "requirements.txt"

# Which import each requirement actually provides. A requirement's install name
# and its module name differ often enough (python-docx -> docx, PyYAML -> yaml)
# that guessing from the install name reports a working machine as broken.
IMPORT_NAME = {"pyyaml": "yaml", "python-docx": "docx", "pymupdf": "pymupdf"}


def requirements() -> list[tuple[str, str]]:
    """[(install name, import name)] parsed from requirements.txt."""
    out = []
    if not REQUIREMENTS.is_file():
        return out
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        pkg = re.split(r"[<>=!~\[]", line, maxsplit=1)[0].strip()
        out.append((pkg, IMPORT_NAME.get(pkg.lower(), pkg.replace("-", "_"))))
    return out


def importable(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def can_render_pdf() -> tuple[bool, str]:
    """Render one, rather than believe a `command -v`."""
    if not shutil.which("pandoc"):
        return False, "pandoc is not installed"
    engines = [e for e in REPORT_ENGINES
               if shutil.which(e)]
    if not engines:
        return False, "no supported report LaTeX engine (tectonic or xelatex)"
    with tempfile.TemporaryDirectory() as tmp:
        d = pathlib.Path(tmp)
        md = d / "probe.md"
        md.write_text("# probe\n\nHello.\n", encoding="utf-8")
        pdf = d / "probe.pdf"
        try:
            result = subprocess.run(["pandoc", str(md), "-o", str(pdf),
                                     f"--pdf-engine={engines[0]}",
                                     "-V", "mainfont=Times New Roman"],
                                    capture_output=True, timeout=180, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            return False, f"pandoc + {engines[0]} failed to run: {exc}"
        if result.returncode == 0 and pdf.is_file() and pdf.stat().st_size > 0:
            return True, f"pandoc + {engines[0]} (report font configuration)"
    return False, f"pandoc + {engines[0]} produced no PDF"


def fast_capabilities() -> list[str]:
    """What is missing, decided WITHOUT rendering anything. Milliseconds.

    `enter_mode.py` runs on every mode entry and cannot afford `checks()`, which
    renders a PDF. So this trades one direction of accuracy away, deliberately,
    and the asymmetry is the point:

      it is SOUND about missing   -- no pandoc on PATH means no PDF, full stop
      it is UNSOUND about present -- pandoc and an engine can both be installed
                                     and still fail to produce a file

    A warning may only fire when it is sure, or it becomes the line everyone
    filters out. Confirming that a capability WORKS stays with `doctor.py`, which
    renders one. This function never claims anything works; it only names what
    demonstrably cannot.
    """
    missing = []
    for pkg, module in requirements():
        if not importable(module):
            missing.append(f"python package {pkg}")
    if not shutil.which("pandoc") or not any(
            shutil.which(e) for e in REPORT_ENGINES):
        missing.append("PDF rendering (pandoc + a LaTeX engine)")
    if not shutil.which("pdftotext"):
        missing.append("pdftotext")
    if not shutil.which("opencli"):
        missing.append("opencli")
    return missing


def install_hint(binary: str) -> str:
    if binary == "opencli":
        return "Agent: prepare a dedicated opencli prefix via references/agent-setup.md"
    if platform.system() == "Windows":
        return (f"Agent: install {binary} with a verified Windows package or portable "
                "release; follow references/agent-setup.md")
    mac = platform.system() == "Darwin"
    brew = {"pandoc": "brew install pandoc", "tectonic": "brew install tectonic",
            "pdftotext": "brew install poppler"}
    apt = {"pandoc": "sudo apt install pandoc", "tectonic": "sudo apt install tectonic",
           "pdftotext": "sudo apt install poppler-utils"}
    return (brew if mac else apt).get(binary, f"install {binary}")


def can_reach_browser() -> tuple[bool, str]:
    """A present adapter executable does not prove its browser bridge works."""
    if not shutil.which("opencli"):
        return False, "opencli is not installed"
    try:
        result = subprocess.run(["opencli", "doctor"], capture_output=True,
                                text=True, encoding="utf-8", timeout=15, check=False)
    except (OSError, UnicodeError, subprocess.SubprocessError) as exc:
        return False, f"browser health check could not complete: {exc}"
    output = re.sub(r"\x1b\[[0-9;]*m", "", (result.stdout or "") + (result.stderr or ""))
    if re.search(r"\[(?:MISSING|FAIL)\]", output, re.I):
        return False, "Browser Bridge is disconnected or its connectivity check failed"
    if result.returncode == 0 and re.search(r"\[OK\]\s*Connectivity:", output, re.I):
        return True, "opencli doctor confirmed browser connectivity"
    return False, "opencli doctor did not confirm browser connectivity; inspect its output"


def checks() -> list[dict]:
    """Every capability, what it costs when absent, and how to get it."""
    out = []
    for pkg, module in requirements():
        out.append({
            "what": f"python package {pkg}",
            "ok": importable(module),
            "cost": ("nothing in this skill runs without it"
                     if module == "yaml" else
                     ".docx output is unavailable" if module == "docx" else
                     "PDF glyph verification and delivery are unavailable" if module == "pymupdf" else
                     f"features using {module} are unavailable"),
            "fix": f"{sys.executable} -m pip install {pkg}",
            "auto": True,
            "install_argv": [sys.executable, "-m", "pip", "install", pkg],
        })
    ok, detail = can_render_pdf()
    out.append({
        "what": "render a PDF", "ok": ok,
        "cost": "PDF CVs, letters and delivered PDFs are unavailable; "
                "Markdown and .docx still work",
        "fix": f"{install_hint('pandoc')} && {install_hint('tectonic')}",
        "auto": False, "detail": detail if ok else "",
    })
    out.append({
        "what": "read text back out of a PDF (pdftotext)",
        "ok": bool(shutil.which("pdftotext")),
        "cost": "check_pages cannot verify a rendered CV, and deliver.py cannot "
                "confirm a PDF kept its characters — both degrade to unverified",
        "fix": install_hint("pdftotext"), "auto": False,
    })
    out.append({
        "what": "job adapters (opencli)", "ok": bool(shutil.which("opencli")),
        "cost": "OpenCLI adapters are unavailable; verify daily-browser CDP separately "
                "or use a pasted posting",
        "fix": install_hint("opencli"), "auto": False,
    })
    if shutil.which("opencli"):
        connected, detail = can_reach_browser()
        out.append({
            "what": "browser-backed job adapters (Browser Bridge)", "ok": connected,
            "cost": detail + "; this OpenCLI route is unverified, not an empty result; check CDP separately",
            "fix": "verify the daily-browser CDP route in references/daily-browser.md",
            "auto": False, "detail": detail,
        })
    return out


def install_python(missing: list[dict]) -> int:
    installed = 0
    for c in missing:
        print(f"installing: {c['fix']}")
        r = subprocess.run(c["install_argv"], capture_output=True, text=True, encoding="utf-8")
        if r.returncode == 0:
            installed += 1
            print(f"  ok: {c['what']}")
        else:
            print(f"  FAILED: {c['what']}\n{(r.stderr or '').strip()[:400]}",
                  file=sys.stderr)
    return installed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--install", action="store_true",
                    help="install missing Python packages; agent handles other tools via references/agent-setup.md")
    args = ap.parse_args(argv)

    results = checks()
    if args.install:
        auto = [c for c in results if not c["ok"] and c.get("auto")]
        if auto:
            install_python(auto)
            results = checks()
        else:
            print("nothing to install: no Python package is missing")

    print(f"job-hunt environment — {platform.system()}, python "
          f"{sys.version.split()[0]}\n")
    for c in results:
        mark = "OK  " if c["ok"] else "MISS"
        extra = f"  ({c['detail']})" if c["ok"] and c.get("detail") else ""
        print(f"  [{mark}] {c['what']}{extra}")

    missing = [c for c in results if not c["ok"]]
    if not missing:
        print("\nEverything this skill needs is present.")
        return 0

    print("\nMissing, and what each one costs:\n")
    for c in missing:
        print(f"  {c['what']}")
        print(f"    without it: {c['cost']}")
        print(f"    fix:        {c['fix']}")
    auto = [c for c in missing if c.get("auto")]
    if auto and not args.install:
        print("\nRe-run with --install to install the missing Python packages.")
    print("\nAgent: resolve required missing capabilities using "
          "references/agent-setup.md, then re-run the checks. "
          "Prepare daily-browser CDP; no extension installation is required.")
    return 1


if __name__ == "__main__":
    from cli_io import configure_output

    configure_output()
    sys.exit(main())
