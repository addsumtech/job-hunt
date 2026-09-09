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
import html
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

import journal
import lint_no_prediction
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
_HAN = re.compile(r"[㐀-䶿一-鿿]")
_JAPANESE = re.compile(r"[぀-ヿ]")
_KOREAN = re.compile(r"[가-힯]")
_MD_LINK = re.compile(r"\[([^\]]+)]\((?:<)?([^\s)>]+)(?:>)?\)")
_MD_BOLD = re.compile(r"\*\*(.+?)\*\*")
_MD_CODE = re.compile(r"`([^`]+)`")
_ANGLE_URL = re.compile(r"&lt;(https?://[^\s]+?)&gt;")
_RAW_ANGLE_URL = re.compile(r"<(https?://[^\s>]+)>")


def has_cjk(text: str) -> bool:
    return bool(_CJK.search(text))


def has_han(text: str) -> bool:
    """Whether text contains Han ideographs."""
    return bool(_HAN.search(text))


def is_chinese_report(text: str) -> bool:
    """Use the Chinese layout only for Chinese, not Japanese/Korean reports.

    Japanese uses Han ideographs too, so `has_han()` alone would route a normal
    Japanese report through a Chinese-only font path. Keep the established
    Japanese/Korean Pandoc probing path whenever either native script appears.
    """
    return has_han(text) and not _JAPANESE.search(text) and not _KOREAN.search(text)


def cjk_chars(text: str) -> int:
    return len(_CJK.findall(text))


def _url_stem(value: str) -> str:
    """Comparable HTTP(S) destination, without volatile query/fragment text."""
    try:
        parsed = urlsplit(html.unescape(value))
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path}".rstrip("/")


def clickable_urls(source: str) -> set[str]:
    """HTTP(S) destinations authored as PDF-renderable Markdown or angle links."""
    urls = [match.group(2) for match in _MD_LINK.finditer(source)]
    urls.extend(match.group(1) for match in _RAW_ANGLE_URL.finditer(source))
    return {stem for value in urls if (stem := _url_stem(value))}


def _pdf_link_problem(pdf: pathlib.Path, source: str) -> str:
    """Return a reason when a PDF lost an authored clickable HTTP(S) link."""
    expected = clickable_urls(source)
    if not expected:
        return ""
    try:
        import pymupdf
        with pymupdf.open(pdf) as document:
            actual = {
                stem for page in document for link in page.get_links()
                if (uri := link.get("uri")) and (stem := _url_stem(str(uri)))
            }
    except Exception as exc:
        return f"PDF_LINKS_UNVERIFIED: {exc}"
    missing = sorted(expected - actual)
    if missing:
        return "PDF_LINKS_MISSING: " + ", ".join(missing)
    return ""



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


def _discover_handoff_problem(workspace: pathlib.Path) -> str:
    """Refuse a discover report that skipped its machine-readable shortlist.

    Delivery is deliberately not a general gate runner. Discover is the one
    exception worth recognising here: without a checked `shortlist.yaml` and
    `shortlist.md`, the report can look complete while omitting the actionable
    per-posting URLs and the evidence chain behind them.
    """
    if journal.current_mode(workspace) != "discover":
        return ""
    missing = [name for name in ("shortlist.yaml", "shortlist.md")
               if not (workspace / name).is_file()]
    if missing:
        return "discover requires " + ", ".join(missing)
    receipts = journal.read_receipts(workspace, "check_shortlist")
    if not receipts:
        return "discover requires a check_shortlist receipt before delivery"
    last = receipts[-1]
    if not journal.receipt_intact(last) or last.get("verdict") != "pass":
        return "discover requires the latest intact check_shortlist receipt to pass"
    try:
        shortlist = journal.load_yaml(workspace / "shortlist.yaml", dict)
    except journal.YamlUnreadable as exc:
        return f"discover shortlist.yaml cannot be read: {exc.reason}"
    required = {
        stem for row in (shortlist.get("rows") or []) if isinstance(row, dict)
        if (stem := _url_stem(str(row.get("url") or "")))
    }
    try:
        report_source = (workspace / "report.md").read_text(encoding="utf-8")
    except OSError as exc:
        return f"discover report.md cannot be read: {exc}"
    missing = sorted(required - clickable_urls(report_source))
    if missing:
        return ("discover report.md omits clickable direct posting link(s): "
                + ", ".join(missing))
    return ""


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


def _reportlab_font() -> tuple[str | None, str]:
    """Register a clean Chinese sans-serif face, with a PDF-native fallback."""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfbase.ttfonts import TTFError, TTFont
    except ImportError:
        return None, "ReportLab is unavailable"

    candidates = ("Hiragino Sans GB", "PingFang SC", "Heiti SC", "Arial Unicode MS")
    for index, family in enumerate(candidates):
        try:
            result = subprocess.run(
                ["fc-match", "-f", "%{file}", family], capture_output=True,
                text=True, timeout=5, check=False,
            )
            path = pathlib.Path(result.stdout.strip())
            if not path.is_file():
                continue
            name = f"JobHuntCJK{index}"
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(path), subfontIndex=0))
            return name, ""
        except (OSError, TypeError, ValueError, TTFError, subprocess.SubprocessError):
            continue

    try:
        name = "STSong-Light"
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(UnicodeCIDFont(name))
        return name, ""
    except (OSError, ValueError):
        return None, "no usable Chinese ReportLab font"


def _reportlab_inline(text: str) -> str:
    """Preserve Markdown emphasis and links without exposing raw URLs."""
    value = html.escape(text)

    def link(match: re.Match) -> str:
        label, url = match.group(1), html.unescape(match.group(2))
        return f'<link href="{html.escape(url, quote=True)}" color="#1D4ED8">{label}</link>'

    def raw_url(match: re.Match) -> str:
        url = html.unescape(match.group(1))
        host = urlsplit(url).netloc.removeprefix("www.")
        label = html.escape(host or url, quote=False)
        return f'<link href="{html.escape(url, quote=True)}" color="#1D4ED8">{label}</link>'

    value = _MD_LINK.sub(link, value)
    value = _ANGLE_URL.sub(raw_url, value)
    value = _MD_BOLD.sub(r"<b>\1</b>", value)
    return _MD_CODE.sub(r'<font face="Courier">\1</font>', value)


def _table_cells(line: str) -> list[str]:
    return [part.strip() for part in line.strip().strip("|").split("|")]


def _is_table_rule(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _reportlab_table(lines: list[str], styles: dict, width: float):
    """Render wide shortlist tables as scan-friendly Chinese job cards."""
    from reportlab.lib import colors
    from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

    rows = [_table_cells(line) for line in lines]
    if len(rows) < 3 or not _is_table_rule(rows[1]):
        return [Paragraph(_reportlab_inline(line), styles["body"]) for line in lines]
    header, data = rows[0], rows[2:]
    if len(header) >= 5:
        cards = []
        for row in data:
            if len(row) != len(header):
                continue
            title = " ".join(part for part in (row[0], row[1]) if part)
            fields = [
                (header[index], value) for index, value in enumerate(row[2:], start=2)
                if value
            ]

            def field(label: str, value: str) -> Paragraph:
                return Paragraph(
                    f"<b>{html.escape(label)}:</b> {_reportlab_inline(value)}",
                    styles["card_body"],
                )

            # A long company/location line reads better on its own. Pair the
            # remaining short metadata fields, then leave evidence/gaps full
            # width. This saves vertical space without shrinking Chinese text.
            details = [field(*fields[0])] if fields else []
            remaining = fields[1:]
            for start in range(0, len(remaining), 2):
                pair = remaining[start:start + 2]
                if len(pair) == 1:
                    details.append(field(*pair[0]))
                    continue
                row_table = Table(
                    [[field(*pair[0]), field(*pair[1])]],
                    colWidths=[(width - 14) / 2, (width - 14) / 2],
                    hAlign="LEFT",
                )
                row_table.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]))
                details.append(row_table)
            card = Table(
                [[Paragraph(_reportlab_inline(title), styles["card_title"])],
                 [details]],
                colWidths=[width], hAlign="LEFT",
            )
            card.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF1F8")),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9D5E3")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.35, colors.HexColor("#C9D5E3")),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            cards.append(KeepTogether([card, Spacer(1, 10)]))
        return cards

    rendered = [[Paragraph(_reportlab_inline(cell), styles["table"]) for cell in row]
                for row in [header, *data] if len(row) == len(header)]
    if not rendered:
        return []
    table = Table(rendered, colWidths=[width / len(header)] * len(header), repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF1F8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#16324F")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C9D5E3")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return [table, Spacer(1, 10)]


def _render_reportlab_cjk(md: pathlib.Path, pdf: pathlib.Path) -> tuple[bool, str]:
    """Render Chinese reports without TeX font discovery or stretched glyphs."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate
    except ImportError:
        return False, "ReportLab is unavailable"

    font, why = _reportlab_font()
    if font is None:
        return False, why
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("title", parent=base["Title"], fontName=font,
                                fontSize=18, leading=25, alignment=TA_CENTER,
                                textColor=colors.HexColor("#102A43"), spaceAfter=7 * mm,
                                keepWithNext=1),
        "heading": ParagraphStyle("heading", parent=base["Heading2"], fontName=font,
                                  fontSize=13, leading=19, alignment=TA_LEFT,
                                  textColor=colors.HexColor("#16324F"), spaceBefore=5 * mm,
                                  spaceAfter=2.5 * mm, keepWithNext=1),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontName=font,
                               fontSize=9.6, leading=15.5, alignment=TA_LEFT,
                               textColor=colors.HexColor("#243B53"), spaceAfter=2.4 * mm),
        "list": ParagraphStyle("list", parent=base["BodyText"], fontName=font,
                               fontSize=9.6, leading=15.5, alignment=TA_LEFT,
                               leftIndent=5 * mm, firstLineIndent=-4 * mm,
                               textColor=colors.HexColor("#243B53"), spaceAfter=1.5 * mm),
        "card_title": ParagraphStyle("card_title", parent=base["BodyText"], fontName=font,
                                     fontSize=11, leading=16, textColor=colors.HexColor("#102A43")),
        "card_body": ParagraphStyle("card_body", parent=base["BodyText"], fontName=font,
                                    fontSize=9.3, leading=15, textColor=colors.HexColor("#243B53")),
        "table": ParagraphStyle("table", parent=base["BodyText"], fontName=font,
                                fontSize=8.2, leading=12.5, textColor=colors.HexColor("#243B53")),
    }
    width = A4[0] - 40 * mm
    story, lines, index = [], md.read_text(encoding="utf-8").splitlines(), 0
    while index < len(lines):
        line = lines[index].strip()
        index += 1
        if not line:
            continue
        if line.startswith("|"):
            block = [line]
            while index < len(lines) and lines[index].strip().startswith("|"):
                block.append(lines[index].strip())
                index += 1
            story.extend(_reportlab_table(block, styles, width))
        elif line.startswith("# "):
            story.append(Paragraph(_reportlab_inline(line[2:]), styles["title"]))
        elif line.startswith("## "):
            story.append(Paragraph(_reportlab_inline(line[3:]), styles["heading"]))
        elif line.startswith("### "):
            story.append(Paragraph(_reportlab_inline(line[4:]), styles["heading"]))
        elif line.startswith(("- ", "* ")):
            story.append(KeepTogether([
                Paragraph("- " + _reportlab_inline(line[2:]), styles["list"])
            ]))
        elif re.match(r"\d+\.\s+", line):
            story.append(KeepTogether([
                Paragraph(_reportlab_inline(line), styles["list"])
            ]))
        elif line.startswith("> "):
            story.append(KeepTogether([
                Paragraph(_reportlab_inline(line[2:]), styles["list"])
            ]))
        else:
            story.append(Paragraph(_reportlab_inline(line), styles["body"]))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D9E2EC"))
        canvas.line(20 * mm, 14 * mm, A4[0] - 20 * mm, 14 * mm)
        canvas.setFillColor(colors.HexColor("#627D98"))
        canvas.setFont(font, 8)
        canvas.drawString(20 * mm, 8 * mm, "职业咨询报告")
        canvas.drawRightString(A4[0] - 20 * mm, 8 * mm, f"第 {document.page} 页")
        canvas.restoreState()

    try:
        pdf.unlink(missing_ok=True)
        SimpleDocTemplate(
            str(pdf), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
            topMargin=18 * mm, bottomMargin=21 * mm,
        ).build(story, onFirstPage=footer, onLaterPages=footer)
    except (OSError, ValueError) as exc:
        pdf.unlink(missing_ok=True)
        return False, str(exc)
    return pdf.is_file() and pdf.stat().st_size > 0, ""


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


def _verify_pdf(pdf: pathlib.Path, source: str, needs_cjk: bool) -> tuple[bool, str]:
    """Reject a rendered PDF that lost text or painted broken glyphs."""
    problems = glyph_findings(pdf)
    if problems:
        pdf.unlink(missing_ok=True)
        return False, "; ".join(problems)
    # A document with an authored URL must identify a missing PDF annotation
    # even if the deliberately minimal regression fixture has no body text.
    link_problem = _pdf_link_problem(pdf, source)
    if link_problem:
        pdf.unlink(missing_ok=True)
        return False, link_problem
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

    # Chinese reports use an in-process renderer first. It avoids Tectonic's
    # platform-dependent font discovery and gives wide shortlist tables a
    # readable card layout rather than six cramped columns. Japanese and Korean
    # retain the existing CJK font-probe path because their scripts share Han.
    if is_chinese_report(source):
        ok, why = _render_reportlab_cjk(md, pdf)
        if ok:
            return _verify_pdf(pdf, source, needs_cjk)
        reportlab_problem = why
    else:
        reportlab_problem = ""

    if needs_cjk and font is None:
        suffix = f"; ReportLab fallback: {reportlab_problem}" if reportlab_problem else ""
        return False, ("no CJK font on this machine that survives a render "
                       f"round-trip (tried {len(CJK_FONTS)}); the Markdown ships, "
                       "the PDF is refused rather than handed over full of boxes" + suffix)
    if not _pandoc(md, pdf, font if needs_cjk else None):
        pdf.unlink(missing_ok=True)
        suffix = f"; ReportLab fallback: {reportlab_problem}" if reportlab_problem else ""
        return False, "pandoc/tectonic produced no PDF" + suffix
    return _verify_pdf(pdf, source, needs_cjk)


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
                # Chinese sources take the ReportLab path in render_pdf(), so a
                # Tectonic font-probe cannot delay or fail their delivery first.
                if glyphs and not is_chinese_report(source) and glyphs not in fonts:
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

    try:
        findings = lint_no_prediction.scan_text(
            (ws / "report.md").read_text(encoding="utf-8"), "report.md",
            lint_no_prediction.capture_corpus(ws))
    except (OSError, UnicodeError) as exc:
        print(f"DELIVER_REPORT_UNREADABLE: {exc}", file=sys.stderr)
        return 2
    if findings:
        print("DELIVER_REPORT_PREDICTION: " + "\n".join(findings), file=sys.stderr)
        return 2

    discover_problem = _discover_handoff_problem(ws)
    if discover_problem:
        print(f"DELIVER_DISCOVER_INCOMPLETE: {discover_problem}", file=sys.stderr)
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
