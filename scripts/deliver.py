#!/usr/bin/env python3
"""Deliver a client consultation report and requested application documents.

Default destination: ~/Downloads/<workspace-name>/. Use the same explicit --to
folder for all workspaces answering one consultation. Internal audit artifacts
stay in the workspace. A report PDF is required unless --no-pdf is explicitly
requested. Exit 2 means incomplete delivery; never call that complete.
"""
from __future__ import annotations

from collections import Counter
import argparse
import datetime
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

import journal
from render_cv import has_rtl
from pdf_glyphs import glyph_findings

SKIP_DIRS = {"raw"}
SKIP_NAMES = {"journal.jsonl", ".DS_Store", "master-fingerprint.json"}
SKIP_SUFFIXES = {".err", ".pyc"}

DEFAULT_ROOT = pathlib.Path.home() / "Downloads"
# Report font setup uses fontspec and xeCJK, so both supported engines use XeTeX.
REPORT_ENGINES = ("tectonic", "xelatex")

# Probed in order. macOS first, then the common Linux packages. The list exists
# because "it worked on my machine" is how a PDF full of boxes ships.
CJK_FONTS = ("SimSun", "PingFang SC", "Hiragino Sans GB", "Songti SC", "STSong",
             "Noto Sans CJK SC", "Noto Serif CJK SC", "Source Han Sans SC",
             "WenQuanYi Zen Hei", "SimSun", "Microsoft YaHei")

_CJK = re.compile(r"[㐀-䶿一-鿿぀-ヿ가-힯]")


def has_cjk(text: str) -> bool:
    return bool(_CJK.search(text))


def cjk_chars(text: str) -> int:
    return len(_CJK.findall(text))



def flat_name(slug: str, rel: pathlib.Path) -> str:
    """`mock/assessment-1.md` -> `<slug>-mock-assessment-1.md`.

    The whole relative path goes into the name, not just the basename. Flattening
    on the basename alone silently overwrites: interview mode writes
    `mock/transcript-1.md` and `mock/answer-guide.md` beside root-level files,
    and two same-named files in different directories became one delivered file
    while the run reported it had delivered both.

    The separator is `__`, not `-`. Joining with `-` only moved the collision one
    level up: `mock/answer/guide.md`, `mock/answer-guide.md` and
    `mock-answer-guide.md` all flattened to the same name, and the run reported
    three deliveries over two files. `__` cannot appear in a path SEPARATOR
    position, so distinct relative paths give distinct names; a filename that
    literally contains `__` is reported below rather than silently overwritten.
    """
    return f"{slug}-" + "__".join(rel.parts)


def client_path(rel: pathlib.Path) -> pathlib.Path:
    """Client names never expose the company/role workspace slug."""
    names = {"report": "求职建议报告", "cv": "简历", "letter": "求职信",
             "rirekisho": "履历书", "supporting-statement": "申请陈述"}
    folder = "报告" if rel.stem == "report" else "简历"
    return pathlib.Path(folder) / (names[rel.stem] + rel.suffix)


def is_deliverable(path: pathlib.Path, workspace: pathlib.Path) -> bool:
    rel = path.relative_to(workspace)
    # Explicit client artifacts only. completion.md can contain tool diagnostics.
    return (len(rel.parts) == 1 and rel.stem in {
        "report", "cv", "letter", "rirekisho", "supporting-statement"
    } and rel.suffix in {".md", ".pdf", ".docx"})


def writable(directory: pathlib.Path) -> tuple[bool, str]:
    """Can we actually create a file here?

    Not `os.access` and not `is_dir()`. On macOS `~/Downloads` sits behind TCC:
    the directory exists, `os.access` says yes, and the write still fails — and
    it can start failing part-way through a session. The only honest test is to
    write something.
    """
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".jobhunt-write-probe"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return True, ""
    except OSError as exc:
        return False, str(exc)


def _pandoc(md: pathlib.Path, pdf: pathlib.Path, font: str | dict | None) -> bool:
    pdf.unlink(missing_ok=True)
    engine = next((e for e in REPORT_ENGINES if shutil.which(e)), None)
    if engine is None:
        return False
    cmd = ["pandoc", str(md), "-o", str(pdf), f"--pdf-engine={engine}",
           "--lua-filter", str(pathlib.Path(__file__).with_name("pdf_symbols.lua")),
           "-V", "mainfont=Times New Roman"]
    if font:
        main = font["main"] if isinstance(font, dict) else font
        cmd += ["-V", f"CJKmainfont={main}"]
        if main == "SimSun":
            cmd += ["-V", "CJKoptions=AutoFakeBold=2"]
        if isinstance(font, dict):
            fallback = ",".join(font["fallbacks"])
            cmd += ["-V", "header-includes=" +
                    r"\xeCJKsetup{AutoFallBack=true}\setCJKfallbackfamilyfont{\CJKrmdefault}{" + fallback + "}"]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=180, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and pdf.is_file() and pdf.stat().st_size > 0


def pdf_text(pdf: pathlib.Path) -> str:
    try:
        r = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True,
                           timeout=60, check=False)
        # Decode in this thread: Windows subprocess text readers can lose a
        # UnicodeDecodeError in a background thread and return stdout=None.
        return r.stdout.decode("utf-8")
    except (OSError, UnicodeError, subprocess.SubprocessError):
        return ""


def visible_markdown(md: pathlib.Path) -> str:
    """Use the same Markdown parser as the renderer; link targets are not ink.

    On parser failure keep the original text, so loss detection fails closed.
    """
    source = md.read_text(encoding="utf-8", errors="replace")
    try:
        result = subprocess.run(["pandoc", str(md), "-t", "plain", "--wrap=none"],
                                capture_output=True, timeout=60,
                                check=False)
        if result.returncode == 0:
            return result.stdout.decode("utf-8")
    except (OSError, UnicodeError, subprocess.SubprocessError):
        pass
    return source


def pick_cjk_font(source: str = "测试中文渲染") -> str | dict | None:
    """The first candidate that survives a render-and-read-back round trip."""
    with tempfile.TemporaryDirectory() as tmp:
        d = pathlib.Path(tmp)
        probe_md = d / "probe.md"
        glyphs = set(_CJK.findall(source))
        probe_md.write_text("".join(sorted(glyphs)) + "\n", encoding="utf-8")
        preferred = []
        if re.search(r"[가-힯]", source):
            preferred += ["Noto Sans CJK KR", "Apple SD Gothic Neo", "Malgun Gothic"]
        if re.search(r"[぀-ヿ]", source):
            preferred += ["Noto Sans CJK JP", "Hiragino Sans W3", "Yu Gothic"]
        # Chinese-only reports must use the requested Song font, not a silent
        # readable-but-different substitute. Other scripts retain their fonts.
        candidates = preferred + list(CJK_FONTS) if preferred else ["SimSun"]
        for font in dict.fromkeys(candidates):
            out = d / f"probe-{abs(hash(font))}.pdf"
            if _pandoc(probe_md, out, font) and not glyph_findings(out) and glyphs <= set(_CJK.findall(pdf_text(out))):
                return font
        if not preferred:
            return None
        # Mixed reports can quote a posting in another script. No single macOS
        # face necessarily covers all of them; probe an explicit fallback chain.
        for main, fallbacks in [
                ("Apple SD Gothic Neo", ["Hiragino Sans W3", "PingFang SC"]),
                ("Noto Sans CJK KR", ["Noto Sans CJK JP", "Noto Sans CJK SC"])]:
            selection = {"main": main, "fallbacks": fallbacks}
            out = d / "probe-fallback.pdf"
            out.unlink(missing_ok=True)
            if _pandoc(probe_md, out, selection) and not glyph_findings(out) and glyphs <= set(_CJK.findall(pdf_text(out))):
                return selection
    return None


def render_pdf(md: pathlib.Path, pdf: pathlib.Path,
               font: str | dict | None) -> tuple[bool, str]:
    """Render, then READ IT BACK. A PDF that dropped characters is not a PDF."""
    source = visible_markdown(md)
    if has_rtl(source):
        # Delivery must not rebuild a PDF that the CV renderer refused. A
        # nonempty English header does not prove the RTL body survived.
        pdf.unlink(missing_ok=True)
        pdf.with_suffix(".tex").unlink(missing_ok=True)
        return False, ("right-to-left text is not supported by this PDF path; "
                       "Markdown and .docx still ship")
    needs_cjk = has_cjk(source)
    if needs_cjk and font is None:
        return False, ("no CJK font on this machine that survives a render "
                       f"round-trip (tried {len(CJK_FONTS)}); the Markdown ships, "
                       "the PDF is refused rather than handed over full of boxes")
    if not _pandoc(md, pdf, font if needs_cjk else None):
        pdf.unlink(missing_ok=True)
        return False, "pandoc with a supported XeTeX engine produced no PDF"

    problems = glyph_findings(pdf)
    if problems:
        pdf.unlink(missing_ok=True)
        return False, "; ".join(problems)
    back = pdf_text(pdf)
    if not back.strip():
        pdf.unlink(missing_ok=True)
        return False, "the rendered PDF has no extractable text"
    if needs_cjk:
        wanted = Counter(_CJK.findall(source))
        observed = Counter(_CJK.findall(back))
        want = sum(wanted.values())
        got = sum((wanted & observed).values())
        # A PDF that silently dropped its CJK reads back as zero, so any large
        # shortfall is the failure this check exists for. Some loss is normal --
        # pandoc drops table furniture and code fences.
        if got < want * 0.8:
            pdf.unlink(missing_ok=True)
            return False, (f"the PDF lost CJK characters: source has {want}, the "
                           f"rendered PDF reads back {got}. Deleted rather than "
                           "delivered.")
    return True, ""


def deliver(workspace: pathlib.Path, dest: pathlib.Path, slug: str,
            make_pdf: bool = True) -> tuple[list[pathlib.Path], list[str]]:
    written, notes = [], []
    fonts = {}
    sources = [p for p in sorted(workspace.rglob("*"))
               if p.is_file() and is_deliverable(p, workspace)
               and not (make_pdf and p.name == "report.pdf")]

    claimed: dict = {}
    for src in sources:
        target = dest / client_path(src.relative_to(workspace))
        # A REDELIVERY must land on the same name. The previous version renamed
        # to `-2` whenever the bytes differed, which froze the obvious filename
        # at round 1 forever: a user opening `<slug>-cv.md` in Downloads after
        # three judge rounds read the FIRST draft and could send it to the
        # employer. Same source path, same destination, overwritten.
        if target in claimed:
            notes.append(f"{target.name}: not delivered — {claimed[target]} and "
                         f"{src.relative_to(workspace)} flatten to the same name. "
                         f"Rename one; a filename containing '__' is the only way "
                         f"this happens.")
            continue
        claimed[target] = src.relative_to(workspace)
        if src.suffix == ".pdf":
            problems = glyph_findings(src)
            if problems:
                target.unlink(missing_ok=True)
                notes.extend(problems)
                continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
        except OSError as exc:
            # One unreadable file, or a name past the OS limit, must not abandon
            # the rest of the round with a traceback and exit 1 — this script's
            # contract is 0 or 2, never 1, and a partial delivery that left no
            # journal record could not be told from one that never happened.
            notes.append(f"{src.relative_to(workspace)}: not delivered — {exc}")
            continue
        written.append(target)
        if make_pdf and src.suffix == ".md" and (src.name == "report.md" or not src.with_suffix(".pdf").exists()):
            pdf = target.with_suffix(".pdf")
            try:
                source = visible_markdown(src)
                glyphs = frozenset(_CJK.findall(source))
                if glyphs and glyphs not in fonts:
                    fonts[glyphs] = pick_cjk_font(source)
                ok, why = render_pdf(src, pdf, fonts.get(glyphs))
            except OSError as exc:
                ok, why = False, str(exc)
            if ok:
                written.append(pdf)
            else:
                notes.append(f"{pdf.name}: {why}")
    return written, notes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", required=True, type=pathlib.Path)
    ap.add_argument("--to", type=pathlib.Path, default=None,
                    help=f"destination directory (default: {DEFAULT_ROOT})")
    ap.add_argument("--no-pdf", action="store_true",
                    help="copy the Markdown only; do not render PDFs")
    args = ap.parse_args(argv)

    ws = args.workspace.expanduser().resolve()
    if not ws.is_dir():
        print(f"DELIVER_NO_WORKSPACE: {ws} is not a directory", file=sys.stderr)
        return 2

    dest = (args.to.expanduser() if args.to else DEFAULT_ROOT / ws.name).resolve()
    if dest == ws or ws in dest.parents:
        print(f"DELIVER_DEST_INSIDE_WORKSPACE: {dest} is the workspace or inside "
              "it; delivering there would copy the round into itself",
              file=sys.stderr)
        return 2

    if not (ws / "report.md").is_file():
        print("DELIVER_REPORT_REQUIRED: author report.md answering the client question", file=sys.stderr)
        return 2

    ok, why = writable(dest)
    if not ok:
        print(f"DELIVER_DEST_UNWRITABLE: cannot write to {dest}: {why}. On macOS "
              "this is usually TCC blocking ~/Downloads for this process; grant "
              "access, or pass --to with a directory that works. Nothing was "
              "copied and the workspace is untouched.", file=sys.stderr)
        return 2

    written, notes = deliver(ws, dest, ws.name, make_pdf=not args.no_pdf)
    if not written:
        print(f"DELIVER_NOTHING_TO_COPY: {ws} holds no deliverable files",
              file=sys.stderr)
        return 2

    # A record, not a gate receipt: delivery decides nothing and has no verdict.
    # It exists because a hand-off that left no trace was indistinguishable from
    # one that never happened, so a composer could not tell a run that skipped
    # the last step from a run that took it.
    try:
        journal.append(ws, {
            "action": "delivery",
            "destination": str(dest),
            "files": [q.relative_to(dest).as_posix() for q in written],
            "pdf_refused": notes,
        })
    except OSError:
        pass  # a workspace we can read but not write is not a delivery failure

    complete = not notes and (args.no_pdf or dest / client_path(pathlib.Path("report.pdf")) in written)
    print(f"{'Delivered' if complete else 'Incomplete delivery:'} {len(written)} file(s) to {dest}")
    for p in written:
        print(f"  {p.relative_to(dest)}")
    for n in notes:
        # The prefix has to name what happened: this list holds refused PDFs AND
        # files that could not be copied at all, and calling a permission error a
        # PDF refusal sends the reader to the renderer.
        code = "NOTICE_NOT_DELIVERED" if "not delivered" in n else "NOTICE_PDF_REFUSED"
        print(f"{code}: {n}", file=sys.stderr)
    print(f"\nTell the user these files are in: {dest}")
    return 0 if complete else 2


if __name__ == "__main__":
    from cli_io import configure_output

    configure_output()
    sys.exit(main())
