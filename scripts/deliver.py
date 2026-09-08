#!/usr/bin/env python3
"""Hand the round's result files to the user, as Markdown AND PDF.

Files land **directly in `~/Downloads`**, named `<slug>-<file>`, because that is
where the user actually looks. The slug prefix is not a folder in disguise: two
rounds both produce `shortlist.md`, and a bare name would have the second round
silently overwrite the first.

The workspace under `~/.claude/job-profiles/` stays exactly where it is. This is
a copy, one-way and deliberate: `scripts/paths.py` owns that layout,
`modes/apply.md`'s resume-an-unfinished-run lookup finds work BY the path shape,
`check_claims.py` fingerprints the master profile at that path, and `~/Downloads`
is a directory the user's own housekeeping empties.

`raw/`, `journal.jsonl` and the adapter `.err` files are NOT copied. They are the
provenance chain every claim in these documents is traced to; they are large and
unreadable to a person; and an audit has to read them where they live rather than
in an export that may have gone stale.

## The PDF, and why it is verified rather than trusted

`pandoc --pdf-engine=tectonic` on a Chinese document exits 0, prints a warning
nobody reads, and produces a PDF whose every CJK glyph is a box. Measured: the
source held 528 Chinese characters and `pdftotext` read 0 back out of the PDF.
That is a wrong artifact behind a green exit code.

So a CJK document gets a CJK font, chosen by probing the ones this machine
actually has, and **every PDF is read back with `pdftotext` and compared against
its source** before it is called delivered. A PDF that loses characters is
deleted and reported, never handed over. If no usable font exists, the Markdown
still ships and the PDF is refused loudly — the same shape as `render_cv.py`
refusing to write a reversed right-to-left PDF.

Exit codes follow the gate contract even though this is not a gate: 0 delivered,
2 could not run. Never 1 — there is no such thing as a delivery "finding".
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

SKIP_DIRS = {"raw"}
SKIP_NAMES = {"journal.jsonl", ".DS_Store", "master-fingerprint.json"}
SKIP_SUFFIXES = {".err", ".pyc"}

DEFAULT_ROOT = pathlib.Path.home() / "Downloads"

# Probed in order. macOS first, then the common Linux packages. The list exists
# because "it worked on my machine" is how a PDF full of boxes ships.
CJK_FONTS = ("PingFang SC", "Hiragino Sans GB", "Songti SC", "STSong",
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


def is_deliverable(path: pathlib.Path, workspace: pathlib.Path) -> bool:
    rel = path.relative_to(workspace)
    if set(rel.parts[:-1]) & SKIP_DIRS:
        return False
    if rel.name in SKIP_NAMES or rel.name.startswith("."):
        return False
    return rel.suffix not in SKIP_SUFFIXES


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
    cmd = ["pandoc", str(md), "-o", str(pdf), "--pdf-engine=tectonic",
           "--lua-filter", str(pathlib.Path(__file__).with_name("pdf_symbols.lua"))]
    if font:
        main = font["main"] if isinstance(font, dict) else font
        cmd += ["-V", f"CJKmainfont={main}", "-V", f"mainfont={main}"]
        if isinstance(font, dict):
            fallback = ",".join(font["fallbacks"])
            cmd += ["-V", "header-includes=" +
                    r"\xeCJKsetup{AutoFallBack=true}\setCJKfallbackfamilyfont{\CJKrmdefault}{" + fallback + "}"]
    try:
        subprocess.run(cmd, capture_output=True, timeout=180, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return pdf.is_file() and pdf.stat().st_size > 0


def pdf_text(pdf: pathlib.Path) -> str:
    try:
        r = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True,
                           timeout=60, text=True, encoding="utf-8", check=False)
        return r.stdout or ""
    except (OSError, UnicodeError, subprocess.SubprocessError):
        return ""


def visible_markdown(md: pathlib.Path) -> str:
    """Use the same Markdown parser as the renderer; link targets are not ink.

    On parser failure keep the original text, so loss detection fails closed.
    """
    source = md.read_text(encoding="utf-8", errors="replace")
    try:
        result = subprocess.run(["pandoc", str(md), "-t", "plain", "--wrap=none"],
                                capture_output=True, text=True, encoding="utf-8", timeout=60,
                                check=False)
        if result.returncode == 0:
            return result.stdout
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
        for font in dict.fromkeys(preferred + list(CJK_FONTS)) :
            out = d / f"probe-{abs(hash(font))}.pdf"
            if _pandoc(probe_md, out, font) and glyphs <= set(_CJK.findall(pdf_text(out))):
                return font
        # Mixed reports can quote a posting in another script. No single macOS
        # face necessarily covers all of them; probe an explicit fallback chain.
        for main, fallbacks in [
                ("Apple SD Gothic Neo", ["Hiragino Sans W3", "PingFang SC"]),
                ("Noto Sans CJK KR", ["Noto Sans CJK JP", "Noto Sans CJK SC"])]:
            selection = {"main": main, "fallbacks": fallbacks}
            out = d / "probe-fallback.pdf"
            out.unlink(missing_ok=True)
            if _pandoc(probe_md, out, selection) and glyphs <= set(_CJK.findall(pdf_text(out))):
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
        return False, "pandoc/tectonic produced no PDF"

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
               if p.is_file() and is_deliverable(p, workspace)]

    claimed: dict = {}
    for src in sources:
        target = dest / flat_name(slug, src.relative_to(workspace))
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
        try:
            shutil.copy2(src, target)
        except OSError as exc:
            # One unreadable file, or a name past the OS limit, must not abandon
            # the rest of the round with a traceback and exit 1 — this script's
            # contract is 0 or 2, never 1, and a partial delivery that left no
            # journal record could not be told from one that never happened.
            notes.append(f"{src.relative_to(workspace)}: not delivered — {exc}")
            continue
        written.append(target)
        if make_pdf and src.suffix == ".md":
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

    dest = (args.to.expanduser() if args.to else DEFAULT_ROOT).resolve()
    if dest == ws or ws in dest.parents:
        print(f"DELIVER_DEST_INSIDE_WORKSPACE: {dest} is the workspace or inside "
              "it; delivering there would copy the round into itself",
              file=sys.stderr)
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
            "files": [q.name for q in written],
            "pdf_refused": notes,
        })
    except OSError:
        pass  # a workspace we can read but not write is not a delivery failure

    print(f"Delivered {len(written)} file(s) to {dest}")
    for p in written:
        print(f"  {p.name}")
    for n in notes:
        # The prefix has to name what happened: this list holds refused PDFs AND
        # files that could not be copied at all, and calling a permission error a
        # PDF refusal sends the reader to the renderer.
        code = "NOTICE_NOT_DELIVERED" if "not delivered" in n else "NOTICE_PDF_REFUSED"
        print(f"{code}: {n}", file=sys.stderr)
    print(f"\nTell the user these files are in: {dest}")
    return 0


if __name__ == "__main__":
    from cli_io import configure_output

    configure_output()
    sys.exit(main())
