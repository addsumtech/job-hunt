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


def _portable_report_style(text: str) -> dict[str, str] | None:
    """Return a bundled-font report style when every visible glyph is covered."""
    try:
        import pymupdf
    except ImportError:
        return None

    if _JAPANESE.search(text):
        style = {"font": "japan", "footer": "キャリア相談レポート",
                 "page": "{number} ページ", "link": "リンク：", "separator": "："}
    elif _KOREAN.search(text):
        style = {"font": "korea", "footer": "커리어 상담 보고서",
                 "page": "{number}쪽", "link": "링크: ", "separator": ": "}
    elif has_han(text):
        style = {"font": "china-s", "footer": "职业咨询报告",
                 "page": "第 {number} 页", "link": "链接：", "separator": "："}
    elif (re.search(r"[áéíóúüñ¿¡]", text, re.I)
          or re.search(r"\b(?:candidaturas?|experiencia|puestos?|salario|evidencia|"
                       r"vacante|recomendaci[oó]n|ubicaci[oó]n)\b", text, re.I)):
        style = {"font": "helv", "footer": "Informe de orientación profesional",
                 "page": "Página {number}", "link": "Enlace: ", "separator": ": "}
    else:
        style = {"font": "helv", "footer": "Career consultation report",
                 "page": "Page {number}", "link": "Link: ", "separator": ": "}

    # The rendered form intentionally substitutes a readable [!] for the one
    # warning symbol a built-in PDF font cannot carry. Source Markdown stays
    # untouched, as required by the delivery contract.
    visible = text.replace("⚠️", "[!]").replace("⚠", "[!]")
    font = pymupdf.Font(style["font"])
    if any(not char.isspace() and not font.has_glyph(ord(char)) for char in visible):
        return None
    return style


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


def _inline_pdf_markup(text: str) -> str:
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


def _render_portable_report(md: pathlib.Path, pdf: pathlib.Path,
                            style: dict[str, str]) -> tuple[bool, str]:
    """Render a supported LTR report with a bundled, extractable PDF font.

    This avoids host-installed fonts and TeX font discovery for the five report
    languages the skill localizes: Chinese, English, Japanese, Korean, Spanish.
    """
    try:
        import pymupdf
    except ImportError:
        return False, "PyMuPDF is unavailable"

    page_width, page_height = 595.28, 841.89  # A4 in PDF points
    left, right, top, bottom = 56, 539, 64, 770
    body_color = (0.14, 0.23, 0.33)
    heading_color = (0.06, 0.16, 0.26)
    link_color = (0.11, 0.31, 0.85)
    font = pymupdf.Font(style["font"])
    document = pymupdf.open()
    page = None
    cursor = top

    def text_width(value: str, size: float) -> float:
        return font.text_length(value, fontsize=size)

    def wrap(value: str, size: float, width: float) -> list[str]:
        """Wrap CJK and Latin text without spacing individual Latin glyphs."""
        result: list[str] = []
        for source_line in value.splitlines() or [""]:
            rest = source_line.strip()
            while rest:
                if text_width(rest, size) <= width:
                    result.append(rest)
                    break
                end = len(rest)
                while end > 1 and text_width(rest[:end], size) > width:
                    end -= 1
                split_at = rest.rfind(" ", 1, end + 1)
                if split_at > 0:
                    result.append(rest[:split_at].rstrip())
                    rest = rest[split_at + 1:].lstrip()
                else:
                    result.append(rest[:end])
                    rest = rest[end:]
            if not source_line.strip():
                result.append("")
        return result or [""]

    def write_lines(lines: list[str], x: float, size: float,
                    color: tuple[float, float, float], leading: float,
                    link: str | None = None) -> bool:
        """Paint text through TextWriter, whose CJK metrics stay compact."""
        nonlocal cursor
        height = len(lines) * leading
        if cursor + height > bottom:
            new_page()
        if cursor + height > bottom:
            return False
        assert page is not None
        writer = pymupdf.TextWriter(page.rect)
        start = cursor
        for line in lines:
            writer.append(pymupdf.Point(x, cursor + size), line, font=font,
                          fontsize=size)
            cursor += leading
        writer.write_text(page, color=color)
        if link:
            width = min(right - x, max(text_width(line, size) for line in lines))
            page.insert_link({
                "kind": pymupdf.LINK_URI,
                "from": pymupdf.Rect(x, start, x + width, cursor),
                "uri": link,
            })
        return True

    def new_page():
        nonlocal page, cursor
        page = document.new_page(width=page_width, height=page_height)
        page.draw_line(pymupdf.Point(left, 790), pymupdf.Point(right, 790),
                       color=(0.85, 0.89, 0.93), width=0.5)
        footer = pymupdf.TextWriter(page.rect)
        footer.append(pymupdf.Point(left, 811), style["footer"], font=font, fontsize=8)
        footer.write_text(page, color=(0.38, 0.49, 0.60))
        cursor = top

    def text_and_links(value: str) -> tuple[str, list[tuple[str, str]]]:
        links: list[tuple[str, str]] = []

        def markdown_link(match: re.Match) -> str:
            label, url = match.group(1), html.unescape(match.group(2))
            links.append((label, url))
            return label

        def raw_link(match: re.Match) -> str:
            url = html.unescape(match.group(1))
            label = urlsplit(url).netloc.removeprefix("www.") or url
            links.append((label, url))
            return label

        value = value.replace("⚠️", "[!]").replace("⚠", "[!]")
        value = _MD_LINK.sub(markdown_link, value)
        value = _RAW_ANGLE_URL.sub(raw_link, value)
        value = _MD_BOLD.sub(r"\1", value)
        return _MD_CODE.sub(r"\1", value), links

    def add_block(value: str, size: float, color: tuple[float, float, float], gap: float) -> bool:
        nonlocal cursor
        display, links = text_and_links(value)
        if not write_lines(wrap(display, size, right - left), left, size, color,
                           size * 1.55):
            return False
        cursor += gap
        for label, url in links:
            if not write_lines(wrap(f"{style['link']}{label}", 9.2, right - left), left,
                               9.2, link_color, 14.5, url):
                return False
            cursor += 3
        return True

    def add_card(title: str, fields: list[tuple[str, str]]) -> bool:
        """Draw a short-list row as a card rather than a cramped wide table."""
        nonlocal cursor
        title_display, title_links = text_and_links(title)
        title_lines = wrap(title_display, 11, right - left - 18)
        entries: list[tuple[list[str], str | None]] = []
        for label, value in fields:
            display, links = text_and_links(value)
            entries.append((wrap(f"{label}{style['separator']}{display}", 9.4,
                                 right - left - 18), None))
            entries.extend((wrap(f"{style['link']}{link_label}", 9.2, right - left - 18), url)
                           for link_label, url in links)
        entries.extend((wrap(f"{style['link']}{link_label}", 9.2, right - left - 18), url)
                       for link_label, url in title_links)
        title_height = len(title_lines) * 17
        body_height = sum(len(lines) * 14.5 + 3 for lines, _ in entries)
        height = 10 + title_height + 7 + body_height + 8
        if height > bottom - top:
            # A single unusually long evidence field still ships, just without
            # a visual frame that could not fit on one page.
            if not add_block(title, 11, heading_color, 4):
                return False
            return all(add_block(f"{label}{style['separator']}{value}", 9.4, body_color, 3)
                       for label, value in fields)
        if cursor + height > bottom:
            new_page()
        assert page is not None
        start = cursor
        page.draw_rect(pymupdf.Rect(left, start, right, start + height),
                       color=(0.79, 0.84, 0.89), fill=(0.98, 0.99, 1.0), width=0.5)
        page.draw_rect(pymupdf.Rect(left, start, right, start + 10 + title_height),
                       color=(0.79, 0.84, 0.89), fill=(0.92, 0.95, 0.98), width=0.5)
        cursor += 7
        if not write_lines(title_lines, left + 9, 11, heading_color, 17):
            return False
        cursor += 4
        for lines, url in entries:
            color = link_color if url else body_color
            size = 9.2 if url else 9.4
            if not write_lines(lines, left + 9, size, color, 14.5, url):
                return False
            cursor += 3
        cursor = start + height + 10
        return True

    def add_table(block: list[str]) -> bool:
        rows = [_table_cells(line) for line in block]
        if len(rows) < 3 or not _is_table_rule(rows[1]):
            return all(add_block(" | ".join(row), 9.6, body_color, 6) for row in rows)
        header, rows = rows[0], rows[2:]
        for row in rows:
            if len(row) != len(header):
                continue
            title = " ".join(piece for piece in row[:2] if piece)
            fields = [(label, value) for label, value in zip(header[2:], row[2:]) if value]
            if not add_card(title, fields):
                return False
        return True

    try:
        pdf.unlink(missing_ok=True)
        new_page()
        lines, index = md.read_text(encoding="utf-8").splitlines(), 0
        while index < len(lines):
            line = lines[index].strip()
            index += 1
            if not line:
                cursor += 4
                continue
            if line.startswith("|"):
                table = [line]
                while index < len(lines) and lines[index].strip().startswith("|"):
                    table.append(lines[index].strip())
                    index += 1
                if not add_table(table):
                    return False, "report block does not fit on a page"
                continue
            if line.startswith("# "):
                value, size, color, gap = line[2:], 18, heading_color, 15
            elif line.startswith(("## ", "### ")):
                value, size, color, gap = line.lstrip("# "), 13, heading_color, 9
            elif line.startswith(("- ", "* ")):
                value, size, color, gap = "- " + line[2:], 9.6, body_color, 5
            elif line.startswith("> "):
                value, size, color, gap = line[2:], 9.6, body_color, 5
            else:
                value, size, color, gap = line, 9.6, body_color, 7
            if not add_block(value, size, color, gap):
                return False, "report block does not fit on a page"
        for number, current_page in enumerate(document, start=1):
            footer = pymupdf.TextWriter(current_page.rect)
            label = style["page"].format(number=number)
            footer.append(pymupdf.Point(right - text_width(label, 8), 811), label,
                          font=font, fontsize=8)
            footer.write_text(current_page, color=(0.38, 0.49, 0.60))
        document.save(pdf, garbage=4, deflate=True)
    except (OSError, RuntimeError, ValueError) as exc:
        pdf.unlink(missing_ok=True)
        return False, str(exc)
    finally:
        document.close()
    return pdf.is_file() and pdf.stat().st_size > 0, ""


def pdf_text(pdf: pathlib.Path) -> str:
    """Read PDF text with Poppler, then the bundled PyMuPDF reader if needed.

    Older Poppler builds can return an empty string for a valid PDF that uses a
    MuPDF bundled font. Treating that transport-specific limitation as an empty
    document rejected readable localized reports in CI. Both readers still have
    to fail before the verifier accepts "no extractable text" as a result.
    """
    try:
        r = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True,
                           timeout=60, check=False)
        # Decode in this thread: Windows subprocess text readers can lose a
        # UnicodeDecodeError in a background thread and return stdout=None.
        text = r.stdout.decode("utf-8")
        if text.strip():
            return text
    except (OSError, UnicodeError, subprocess.SubprocessError):
        pass
    try:
        import pymupdf
        with pymupdf.open(pdf) as document:
            return "\n".join(page.get_text("text") for page in document)
    except Exception:
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

    style = _portable_report_style(source)
    # Every supported left-to-right report uses a bundled, embedded font first.
    # This keeps Chinese, English, Japanese, Korean and Spanish layout identical
    # across machines, while the explicit RTL refusal above remains unchanged.
    if style:
        ok, why = _render_portable_report(md, pdf, style)
        if ok:
            return _verify_pdf(pdf, source, needs_cjk)
        portable_renderer_problem = why
    else:
        portable_renderer_problem = ""

    if needs_cjk and font is None:
        suffix = f"; bundled report renderer: {portable_renderer_problem}" if portable_renderer_problem else ""
        return False, ("no CJK font on this machine that survives a render "
                       f"round-trip (tried {len(CJK_FONTS)}); the Markdown ships, "
                       "the PDF is refused rather than handed over full of boxes" + suffix)
    if not _pandoc(md, pdf, font if needs_cjk else None):
        pdf.unlink(missing_ok=True)
        suffix = f"; bundled report renderer: {portable_renderer_problem}" if portable_renderer_problem else ""
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
                # Bundled report fonts take precedence whenever every visible
                # glyph is covered, so a Tectonic probe cannot delay delivery.
                if glyphs and not _portable_report_style(source) and glyphs not in fonts:
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
