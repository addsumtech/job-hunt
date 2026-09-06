#!/usr/bin/env python3
"""What this machine can and cannot do, and how to fix what it cannot.

Run it once for a new user, before the first mode. Every check answers a
CAPABILITY question rather than a binary-name question, because the binary-name
version has already been wrong here: an earlier check looked for `xelatex`, did
not find it, and concluded PDF rendering was at risk — while `tectonic` was
installed and every PDF rendered fine. So the PDF check renders a PDF.

Two classes of missing thing, handled differently on purpose:

  Python packages   installed for you with --install. They are small, scoped to
                    the interpreter already running, and listed in
                    requirements.txt, which is parsed rather than duplicated
                    here.

  System binaries   NEVER installed for you. A LaTeX engine is a package-manager
                    action of several hundred megabytes; running one unasked on
                    someone's machine is the same class of act as running
                    `opencli <site> login` for them, which source-policy.md keeps
                    on its Red list. The exact command is printed for the
                    platform detected, and the user runs it.

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

REPO = pathlib.Path(__file__).resolve().parent.parent
REQUIREMENTS = REPO / "requirements.txt"

# Which import each requirement actually provides. A requirement's install name
# and its module name differ often enough (python-docx -> docx, PyYAML -> yaml)
# that guessing from the install name reports a working machine as broken.
IMPORT_NAME = {"pyyaml": "yaml", "python-docx": "docx"}


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
    engines = [e for e in ("tectonic", "xelatex", "lualatex", "pdflatex")
               if shutil.which(e)]
    if not engines:
        return False, "no LaTeX engine (tectonic, xelatex, lualatex or pdflatex)"
    with tempfile.TemporaryDirectory() as tmp:
        d = pathlib.Path(tmp)
        md = d / "probe.md"
        md.write_text("# probe\n\nHello.\n", encoding="utf-8")
        pdf = d / "probe.pdf"
        try:
            subprocess.run(["pandoc", str(md), "-o", str(pdf),
                            f"--pdf-engine={engines[0]}"],
                           capture_output=True, timeout=180, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            return False, f"pandoc + {engines[0]} failed to run: {exc}"
        if pdf.is_file() and pdf.stat().st_size > 0:
            return True, f"pandoc + {engines[0]}"
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
            shutil.which(e) for e in ("tectonic", "xelatex", "lualatex", "pdflatex")):
        missing.append("PDF rendering (pandoc + a LaTeX engine)")
    if not shutil.which("pdftotext"):
        missing.append("pdftotext")
    if not shutil.which("opencli"):
        missing.append("opencli")
    return missing


def install_hint(binary: str) -> str:
    mac = platform.system() == "Darwin"
    brew = {"pandoc": "brew install pandoc", "tectonic": "brew install tectonic",
            "pdftotext": "brew install poppler",
            "opencli": "npm install -g @jackwener/opencli"}
    apt = {"pandoc": "sudo apt install pandoc", "tectonic": "sudo apt install tectonic",
           "pdftotext": "sudo apt install poppler-utils",
           "opencli": "npm install -g @jackwener/opencli"}
    return (brew if mac else apt).get(binary, f"install {binary}")


def checks() -> list[dict]:
    """Every capability, what it costs when absent, and how to get it."""
    out = []
    for pkg, module in requirements():
        out.append({
            "what": f"python package {pkg}",
            "ok": importable(module),
            "cost": ("nothing in this skill runs without it"
                     if module == "yaml" else
                     f".docx output is unavailable ({module})"),
            "fix": f"{sys.executable} -m pip install {pkg}",
            "auto": True,
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
        "cost": "discover mode cannot retrieve postings; assess, apply and "
                "interview still work from a posting you paste",
        "fix": install_hint("opencli"), "auto": False,
    })
    return out


def install_python(missing: list[dict]) -> int:
    installed = 0
    for c in missing:
        print(f"installing: {c['fix']}")
        r = subprocess.run(c["fix"].split(), capture_output=True, text=True)
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
                    help="install the missing PYTHON packages (never system binaries)")
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
        print("\nRe-run with --install to install the Python packages above. "
              "System binaries are never installed for you — run their command "
              "yourself.")
    else:
        print("\nSystem binaries are never installed for you: a LaTeX engine is a "
              "package-manager action of several hundred megabytes, and running "
              "one unasked is not this skill's call. Run the commands above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
