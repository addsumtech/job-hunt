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
import json
import pathlib
import platform
import re
import shutil
import subprocess
import sys
import tempfile

from opencli_compat import installed_package
from host_execution import HOST_EXECUTION_REQUIRED, tectonic_needs_host_execution

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


def _process_output(result) -> str:
    """Decode a subprocess result without assuming a particular capture mode."""
    def text(value):
        if isinstance(value, bytes):
            return value.decode("utf-8", "replace")
        return str(value or "")
    return text(getattr(result, "stdout", "")) + text(getattr(result, "stderr", ""))


def can_render_pdf() -> tuple[bool, str]:
    """Check the optional Pandoc/template PDF path by rendering one."""
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
        if tectonic_needs_host_execution(engines[0], _process_output(result)):
            return False, (f"{HOST_EXECUTION_REQUIRED}: Tectonic is installed, but this "
                           "restricted macOS process cannot initialize SystemConfiguration; "
                           "rerun PDF rendering and verification through the host's approved "
                           "trusted or elevated execution route")
    return False, f"pandoc + {engines[0]} produced no PDF"


def can_render_report() -> tuple[bool, str]:
    """The common report path uses PyMuPDF and bundled fonts, without TeX."""
    if not importable("pymupdf") or not importable("yaml"):
        return False, "report Python dependencies are missing"
    try:
        from deliver import render_pdf
        with tempfile.TemporaryDirectory() as tmp:
            md = pathlib.Path(tmp) / "report.md"
            md.write_text("# Career report\n\n求职建议。Résumé. 日本語。한국어.\n", encoding="utf-8")
            ok, detail = render_pdf(md, md.with_suffix(".pdf"), None)
            return ok, "PyMuPDF + bundled fonts" if ok else detail
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        return False, str(exc)


def fast_capabilities() -> list[str]:
    """What is missing, decided WITHOUT rendering anything. Milliseconds.

    `enter_mode.py` runs on every mode entry and cannot afford `checks()`, which
    renders a PDF. So this trades one direction of accuracy away, deliberately,
    and the asymmetry is the point:

      it is SOUND about missing   -- no pandoc means no template-based CV PDF
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
        missing.append("Template CV PDF rendering (pandoc + a LaTeX engine; optional for reports)")
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


def can_use_opencli_cdp() -> tuple[bool, str]:
    """Inspect website routing without connecting to any browser or extension.

    A CDP class existing in the package is insufficient: 1.8.7 exports one but
    selects BrowserBridge for website adapters. Probe the installed factory,
    never instantiate its result. Live endpoint/profile verification is separate.
    """
    if not shutil.which("opencli"):
        return False, "opencli is not installed"
    node = shutil.which("node")
    if not node:
        return False, "Node.js is unavailable; OpenCLI CDP routing is unverified"
    try:
        package = installed_package()
        runtime = package / "dist/src/runtime.js"
        browser = package / "dist/src/browser/index.js"
        if not runtime.is_file() or not browser.is_file():
            return False, "installed OpenCLI layout is unknown; inspect its documented CDP route"
        # The endpoint is a child-process probe value, not a connection target.
        # No connect(), browserSession(), CLI doctor or daemon command is called.
        probe = """
process.env.OPENCLI_CDP_ENDPOINT ||= 'http://127.0.0.1:0';
const {getBrowserFactory} = await import(process.argv[1]);
const {CDPBridge} = await import(process.argv[2]);
const sites = ['51job', 'indeed', 'boss', 'linkedin'];
console.log(JSON.stringify(sites.map(site => ({site,
  cdp: typeof CDPBridge === 'function' && getBrowserFactory(site) === CDPBridge}))));
"""
        result = subprocess.run([node, "--input-type=module", "-e", probe,
                                 runtime.as_uri(), browser.as_uri()], capture_output=True,
                                text=True, encoding="utf-8", timeout=15, check=False)
        routes = json.loads(result.stdout or "null") if result.returncode == 0 else None
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return False, f"OpenCLI CDP routing check could not complete: {exc}"
    sites = {"51job", "indeed", "boss", "linkedin"}
    if (isinstance(routes, list) and len(routes) == len(sites)
            and all(isinstance(route, dict) and isinstance(route.get("site"), str)
                    for route in routes)
            and {route.get("site") for route in routes} == sites
            and all(route.get("cdp") is True for route in routes)):
        return True, "website factories select CDP; verify the selected live endpoint and adapter before reading"
    return False, ("website CDP routing is not confirmed; use the diagnosed browser CDP fallback, "
                   "never an extension-backed connection")


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
    ok, detail = can_render_report()
    out.append({
        "what": "consultation report PDF (bundled fonts)", "ok": ok,
        "cost": "consultation report PDF delivery is unavailable",
        "fix": "run scripts/setup_dependencies.py and verify the bundled report fonts",
        "auto": False, "detail": detail,
    })
    ok, detail = can_render_pdf()
    pdf_fix = ("rerun only the PDF render and verification through the host's approved "
               "trusted or elevated execution route; do not reinstall Tectonic"
               if detail.startswith(HOST_EXECUTION_REQUIRED) else
               f"{install_hint('pandoc')} && {install_hint('tectonic')}")
    out.append({
        "what": "template-based CV/letter PDF (optional for reports)", "ok": ok,
        "cost": "template-based PDF CVs and letters are unavailable; "
                "bundled report PDFs, Markdown and .docx use separate capabilities",
        "fix": pdf_fix,
        "auto": False, "detail": detail,
    })
    out.append({
        "what": "read text back out of a PDF (pdftotext)",
        "ok": bool(shutil.which("pdftotext")),
        "cost": "check_pages cannot verify a template-based CV; "
                "report delivery can still verify text using PyMuPDF",
        "fix": install_hint("pdftotext"), "auto": False,
    })
    out.append({
        "what": "job adapters (opencli)", "ok": bool(shutil.which("opencli")),
        "cost": "OpenCLI adapters are unavailable; verify daily-browser CDP separately "
                "or use a pasted posting",
        "fix": install_hint("opencli"), "auto": False,
    })
    if shutil.which("opencli"):
        connected, detail = can_use_opencli_cdp()
        out.append({
            "what": "OpenCLI website CDP routing", "ok": connected,
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
        extra = f"  ({c['detail']})" if c.get("detail") else ""
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
          "Prepare the selected browser's CDP connection.")
    return 1


if __name__ == "__main__":
    from cli_io import configure_output

    configure_output()
    sys.exit(main())
