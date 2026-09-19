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
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit, urlunsplit

import journal
import check_layout
import lint_no_prediction
import vocab
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
_PDF_WARNING = "\u26a0"


def report_audience_findings(source: str) -> list[str]:
    """Keep fixture provenance in the private audit, not the client report.

    Match fixture provenance only, not words such as '测试' or '模拟面试':
    those are ordinary job requirements and preparation advice. Practice scope
    ('本轮只练了技术面', 'a mock is not a real interview') is normal advice to a
    real client, and 'synthetic candidate' is chemistry vocabulary.
    """
    markers = ("固定虚构履历", "固定的虚构履历", "fixed fictional profile",
               "synthetic candidate profile")
    folded = source.casefold()
    return [f"REPORT_INTERNAL_NARRATION: {marker!r}; move test-process notes to the private audit and write advice for the client"
            for marker in markers if marker in folded]


def _replace_unsupported_pdf_symbols(document: object) -> bool:
    """Apply the former Pandoc filter to text nodes without changing Markdown.

    Some TeX font stacks cannot render the warning glyph. Pandoc's JSON AST lets
    this stay exactly scoped to ordinary text (`Str`) nodes: code, URLs and the
    source Markdown retain their original bytes.
    """
    changed = False

    def visit(value: object) -> None:
        nonlocal changed
        if isinstance(value, dict):
            if value.get("t") == "Str" and isinstance(value.get("c"), str):
                text = value["c"]
                rendered = text.replace("\u26a0\ufe0f", "[!]").replace(
                    _PDF_WARNING, "[!]")
                if rendered != text:
                    value["c"] = rendered
                    changed = True
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(document)
    return changed


def _pandoc_json_with_readable_symbols(md: pathlib.Path) -> bytes | None:
    """Return a Pandoc AST with unsupported warning symbols made readable."""
    try:
        parsed = subprocess.run(
            ["pandoc", str(md), "-t", "json"], capture_output=True,
            timeout=180, check=False, cwd=str(md.parent))
        if parsed.returncode != 0:
            return None
        output = parsed.stdout
        if isinstance(output, bytes):
            payload = output.decode("utf-8")
        elif isinstance(output, str):
            payload = output
        else:
            return None
        document = json.loads(payload)
        if not isinstance(document, dict):
            return None
        _replace_unsupported_pdf_symbols(document)
        return json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (OSError, UnicodeError, json.JSONDecodeError, subprocess.SubprocessError):
        return None


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

    # A quoted employer or original posting title may use a different script
    # from the consultation. Choose the labels from the dominant prose, while
    # choosing a font separately that also covers those preserved quotations.
    han = len(_HAN.findall(text))
    japanese = len(_JAPANESE.findall(text))
    korean = len(_KOREAN.findall(text))
    latin = len(re.findall(r"[A-Za-zÀ-ɏ]", text))
    cjk = han + japanese + korean
    if cjk > latin and japanese * 3 > han and japanese > korean:
        style = {"font": "japan", "footer": "キャリア相談レポート",
                 "page": "{number} ページ", "link": "リンク：", "separator": "："}
    elif cjk > latin and korean > japanese and korean > han:
        style = {"font": "korea", "footer": "커리어 상담 보고서",
                 "page": "{number}쪽", "link": "링크: ", "separator": ": "}
    elif cjk > latin and han:
        style = {"font": "china-s", "footer": "职业咨询报告",
                 "page": "第 {number} 页", "link": "链接：", "separator": "："}
    elif len(re.findall(r"\b(?:de|la|el|los|las|para|con|una|un|y|que|tu|tus|"
                        r"candidaturas?|experiencia|puestos?|salario|evidencia|"
                        r"vacante|recomendaci[oó]n|ubicaci[oó]n)\b", text, re.I)) >= 2:
        style = {"font": "helv", "footer": "Informe de orientación profesional",
                 "page": "Página {number}", "link": "Enlace: ", "separator": ": "}
    else:
        style = {"font": "helv", "footer": "Career consultation report",
                 "page": "Page {number}", "link": "Link: ", "separator": ": "}

    if cjk:
        style["font"] = "japan" if japanese else "korea" if korean else "china-s"

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
    """Comparable HTTP(S) destination, retaining the exact posting identity."""
    try:
        parsed = urlsplit(html.unescape(value))
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(),
                       parsed.path, parsed.query, parsed.fragment))


def clickable_urls(source: str) -> set[str]:
    """HTTP(S) destinations authored as PDF-renderable Markdown or angle links."""
    source = "\n".join(line for line, literal in _report_lines(source) if not literal)
    source = _MD_CODE.sub("", source)
    urls = [match.group(2) for match in _MD_LINK.finditer(source)]
    urls.extend(match.group(1) for match in _RAW_ANGLE_URL.finditer(source))
    return {stem for value in urls if (stem := _url_stem(value))}


def _report_lines(source: str):
    """Yield visible lines, distinguishing fenced code from Markdown prose."""
    fence = None
    for line in source.splitlines():
        if fence is not None:
            if re.fullmatch(r" {0,3}" + re.escape(fence[0]) +
                            r"{" + str(len(fence)) + r",}\s*", line):
                fence = None
            else:
                yield line, True
            continue
        opening = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if opening and not (opening[1][0] == "`" and "`" in opening[2]):
            fence = opening[1]
            continue
        yield line, False


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


def is_deliverable(path: pathlib.Path, workspace: pathlib.Path,
                   include_applications: bool = True) -> bool:
    rel = path.relative_to(workspace)
    # Explicit client artifacts only. completion.md can contain tool diagnostics.
    return ((include_applications or rel.stem == "report")
            and len(rel.parts) == 1 and rel.stem in {
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


def _checked_discover_round(workspace: pathlib.Path) -> tuple[dict, str]:
    missing = [name for name in ("shortlist.yaml", "shortlist.md")
               if not (workspace / name).is_file()]
    if missing:
        return {}, "discover requires " + ", ".join(missing)
    receipts = journal.read_receipts(workspace, "check_shortlist")
    if not receipts:
        return {}, "discover requires a check_shortlist receipt before delivery"
    last = receipts[-1]
    if not journal.receipt_intact(last) or last.get("verdict") != "pass":
        return {}, "discover requires the latest intact check_shortlist receipt to pass"
    for name, expected in last.get("input_hashes", {}).items():
        if pathlib.Path(name).name == "journal.jsonl":
            continue  # Appending the receipt changes its own journal, as in check_shortlist.
        if pathlib.Path(name).is_absolute() or ".." in pathlib.Path(name).parts:
            return {}, f"discover receipt input is outside the round: {name}"
        path = workspace / name
        if not path.is_file() or journal.sha256_file(path) != expected:
            return {}, f"discover check_shortlist receipt is stale: {name}"
    try:
        return journal.load_yaml(workspace / "shortlist.yaml", dict), ""
    except journal.YamlUnreadable as exc:
        return {}, f"discover shortlist.yaml cannot be read: {exc.reason}"


def _unavailable_detail_supported(workspace: pathlib.Path, row: dict,
                                  exception: dict, report: str) -> bool:
    """An access failure is a traceable exception, not a substitute for doing the read."""
    from check_candidate_match import _safe_path, _record_mentions_row
    from record_browser_capture import read_retrieval_calls, STOP_CLASSES
    reason, name = exception.get("reason"), exception.get("capture")
    if not isinstance(reason, str) or not reason.strip() or reason not in report:
        return False
    path = _safe_path(workspace, name, raw=True)
    if path is None:
        return False
    source = path.read_text(encoding="utf-8")
    for call in read_retrieval_calls(workspace):
        if (call.get("site") != row.get("source_site")
                or call.get("classification") in (None, "ok")
                or name not in [call.get(k) for k in ("stdout_file", "stderr_file", "snapshot_file")]):
            continue
        if call.get("classification") in STOP_CLASSES:
            return True  # A site-level stop prohibits another attempt for each row.
        if (call.get("command") in ("detail", "job-detail", "job")
                and _record_mentions_row(call, row, source)):
            return True
    return False


def _discover_detail_problem(workspace: pathlib.Path, shortlist: dict,
                             rows: list[dict], report: str, scope_config: dict | None = None) -> str:
    if not rows:
        return ""
    import check_candidate_match as match_gate
    try:
        brief = journal.load_yaml(workspace / "brief.yaml", dict)
    except (OSError, journal.YamlUnreadable) as exc:
        return f"discover requires readable brief.yaml: {exc}"
    config = brief if scope_config is None else scope_config
    scope = config.get("report_scope", "complete")
    if scope == "preliminary":
        if not isinstance(config.get("preliminary_request"), str) or not config["preliminary_request"].strip():
            return "a preliminary report requires the user's explicit request in preliminary_request"
        return ""
    if scope != "complete":
        return f"unknown discover report_scope: {scope!r}"
    exceptions = {entry.get("id"): entry for entry in shortlist.get("detail_unavailable", [])
                  if isinstance(entry, dict)} if isinstance(shortlist.get("detail_unavailable", []), list) else {}
    for row in rows:
        if row.get("quality") == "complete":
            continue
        exception = exceptions.get(row.get("id"), {})
        if row.get("verdict") in vocab.VERDICTS[:2] or not _unavailable_detail_supported(
                workspace, row, exception, report):
            return (f"full description not reviewed for {row.get('id') or row.get('url')}; "
                    "finish the read, remove the lead from this delivery, or record a "
                    "captured access failure with its reason visible in the report")
    try:
        match, profile, all_rows, brief, _ = match_gate._load_workspace(workspace, need_markdown=False)
        findings, _ = match_gate.check(workspace, match, profile, all_rows, brief,
                                       verify_rendered=False)
    except (OSError, ValueError, journal.YamlUnreadable) as exc:
        return f"discover detail evidence cannot be checked: {exc}"
    if findings:
        return "discover detail evidence is incomplete: " + "; ".join(findings)
    return ""


def _discover_handoff_problem(workspace: pathlib.Path) -> str:
    """Check every retained posting, including all rounds in a collection report."""
    collection_path = workspace / "collection.yaml"
    was_discover = any(r.get("action") == "mode_entry" and r.get("mode") == "discover"
                       for r in journal._records(workspace))
    if not was_discover and not collection_path.exists() and not (workspace / "search-coverage.yaml").exists():
        return ""
    try:
        report_source = (workspace / "report.md").read_text(encoding="utf-8")
        if collection_path.exists():
            collection = journal.load_yaml(collection_path, dict)
            rounds = collection.get("rounds")
            if not isinstance(rounds, list) or not rounds:
                return "collection.yaml requires a nonempty rounds list"
        else:
            rounds = [{"workspace": "."}]
        required = set()
        for item in rounds:
            if not isinstance(item, dict) or not isinstance(item.get("workspace"), str):
                return "each collection round requires a workspace path"
            source = (workspace / item["workspace"]).expanduser().resolve()
            shortlist, problem = _checked_discover_round(source)
            if problem:
                return f"{source.name}: {problem}"
            rows = shortlist.get("rows")
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                return "discover shortlist rows must be a list of mappings"
            if "ids" in item:
                ids = item["ids"]
                available = {row.get("id") for row in rows}
                if (not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids)
                        or len(set(ids)) != len(ids) or not set(ids) <= available):
                    return "collection round ids must select distinct existing shortlist rows"
                rows = [row for row in rows if row.get("id") in ids]
            required.update(stem for row in rows if (stem := _url_stem(str(row.get("url") or ""))))
            missing = sorted(required - clickable_urls(report_source))
            if missing:
                return "discover report.md omits clickable direct posting link(s): " + ", ".join(missing)
            problem = _discover_detail_problem(source, shortlist, rows, report_source,
                                               collection if collection_path.exists() else None)
            if problem:
                return f"{source.name}: {problem}"
    except (OSError, UnicodeError, journal.YamlUnreadable) as exc:
        return f"discover delivery sources cannot be read: {exc}"
    import check_search_coverage
    return "; ".join(check_search_coverage.inspect(workspace))


def _pandoc(md: pathlib.Path, pdf: pathlib.Path, font: str | dict | None) -> bool:
    md = md.resolve()
    pdf = pdf.resolve()
    pdf.unlink(missing_ok=True)
    engine = next((e for e in REPORT_ENGINES if shutil.which(e)), None)
    if engine is None:
        return False
    cmd = ["pandoc", str(md), "-o", str(pdf), f"--pdf-engine={engine}",
           "-V", "mainfont=Times New Roman", "-V", "papersize=a4",
           "-V", "geometry:margin=20mm", "-V", "fontsize=12pt"]
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
        source = md.read_text(encoding="utf-8")
        kwargs = {"capture_output": True, "timeout": 180, "check": False}
        if _PDF_WARNING in source:
            ast = _pandoc_json_with_readable_symbols(md)
            if ast is None:
                return False
            cmd[1:1] = ["--from=json"]
            kwargs.update(input=ast, cwd=str(md.parent))
        result = subprocess.run(cmd, **kwargs)
    except (OSError, UnicodeError, subprocess.SubprocessError):
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
    body_color = (0.09, 0.10, 0.13)
    heading_color = (23 / 255, 54 / 255, 93 / 255)
    link_color = heading_color
    font = pymupdf.Font(style["font"])
    document = pymupdf.open()
    page = None
    cursor = top
    anchors: dict[str, tuple[int, float]] = {}
    anchor_counts: dict[str, int] = {}
    internal_links = []
    outline = []

    def text_width(value: str, size: float) -> float:
        return font.text_length(value, fontsize=size)

    def wrap(value: str, size: float, width: float, literal: bool = False) -> list[str]:
        """Wrap CJK and Latin text without spacing individual Latin glyphs."""
        result: list[str] = []
        for source_line in value.splitlines() or [""]:
            rest = source_line if literal else source_line.strip()
            while rest:
                if text_width(rest, size) <= width:
                    result.append(rest)
                    break
                low, high = 1, len(rest)
                while low < high:
                    middle = (low + high + 1) // 2
                    if text_width(rest[:middle], size) <= width:
                        low = middle
                    else:
                        high = middle - 1
                end = low
                # Chinese can wrap between characters. Rewinding to a distant
                # ASCII space is useful only when this cut splits a word in a
                # space-delimited script (Latin or Korean).
                splits_word = (end < len(rest)
                               and re.match(r"[A-Za-zÀ-ɏ0-9_+/가-힯-]", rest[end - 1])
                               and re.match(r"[A-Za-zÀ-ɏ0-9_+/가-힯-]", rest[end]))
                split_at = rest.rfind(" ", 1, end + 1) if splits_word else -1
                if split_at > 0:
                    result.append(rest[:split_at].rstrip())
                    rest = rest[split_at + 1:]
                    if not literal:
                        rest = rest.lstrip()
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
        if height <= bottom - top and cursor + height > bottom:
            new_page()
        remaining = lines[:]
        while remaining:
            count = min(len(remaining), int((bottom - cursor) / leading))
            if count < 1:
                new_page()
                continue
            chunk, remaining = remaining[:count], remaining[count:]
            assert page is not None
            writer = pymupdf.TextWriter(page.rect)
            start = cursor
            for line in chunk:
                writer.append(pymupdf.Point(x, cursor + size), line, font=font,
                              fontsize=size)
                cursor += leading
            writer.write_text(page, color=color)
            if link:
                width = min(right - x, max(text_width(line, size) for line in chunk))
                rect = pymupdf.Rect(x, start, x + width, cursor)
                if link.startswith("#"):
                    internal_links.append((page.number, rect, unquote(link[1:])))
                else:
                    page.insert_link({"kind": pymupdf.LINK_URI, "from": rect, "uri": link})
            if remaining:
                new_page()
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
        standalone_link = _MD_LINK.fullmatch(value.strip()) or _RAW_ANGLE_URL.fullmatch(value.strip())
        if not standalone_link:
            if not write_lines(wrap(display, size, right - left), left, size, color,
                               size * 1.35):
                return False
            cursor += gap
        for label, url in links:
            link_label = label if url.startswith("#") else f"{style['link']}{label}"
            if not write_lines(wrap(link_label, 10.5, right - left), left,
                               10.5, link_color, 14.5, url):
                return False
            cursor += 3
        return True

    def add_entry(title: str, fields: list[tuple[str, str]]) -> bool:
        """Flow a wide table entry as labeled paragraphs, without a card frame."""
        nonlocal cursor
        title_display, _ = text_and_links(title)
        title_height = len(wrap(title_display, 12.6, right - left)) * 17
        if cursor + title_height + 36 > bottom:
            new_page()
        if not add_block(title, 12.6, heading_color, 5):
            return False
        for label, value in fields:
            if not add_block(f"{label}{style['separator']}{value}", 12, body_color, 4):
                return False
        cursor += 6
        return True

    def add_table(block: list[str]) -> bool:
        nonlocal cursor
        rows = [_table_cells(line) for line in block]
        if len(rows) < 3 or not _is_table_rule(rows[1]):
            return all(add_block(" | ".join(row), 12, body_color, 6) for row in rows)
        header, rows = rows[0], rows[2:]
        if len(header) > 3:
            for row in rows:
                if len(row) != len(header):
                    continue
                title = " ".join(piece for piece in row[:2] if piece)
                fields = [(label, value) for label, value in zip(header[2:], row[2:]) if value]
                if not add_entry(title, fields):
                    return False
            return True

        widths = ([0.32, 0.68] if len(header) == 2 else
                  [1 / len(header)] * len(header))
        widths = [fraction * (right - left) for fraction in widths]
        size, leading = 11.5, 15.5

        def cell_data(values):
            cells = []
            for value, width in zip(values, widths):
                display, links = text_and_links(value)
                entries = [(wrap(display, size, width - 12), None)]
                entries.extend((wrap(f"{style['link']}{label}", size, width - 12), url)
                               for label, url in links)
                cells.append(entries)
            return cells

        def row_height(cells):
            return max(sum(len(lines) * leading for lines, _ in entries)
                       for entries in cells) + 10

        def draw_row(cells, heading=False):
            nonlocal cursor
            assert page is not None
            start, height, x = cursor, row_height(cells), left
            if heading:
                page.draw_rect(pymupdf.Rect(left, start, right, start + height),
                               fill=(245 / 255, 247 / 255, 253 / 255), color=None)
            for entries, width in zip(cells, widths):
                cursor = start + 5
                for lines, url in entries:
                    if not write_lines(lines, x + 6, size,
                                       link_color if url else body_color, leading, url):
                        return False
                x += width
            cursor = start + height
            page.draw_line(pymupdf.Point(left, cursor), pymupdf.Point(right, cursor),
                           color=(197 / 255, 210 / 255, 227 / 255), width=0.5)
            return True

        header_cells = cell_data(header)
        header_height = row_height(header_cells)
        needs_header = True
        for row in rows:
            if len(row) != len(header):
                continue
            cells = cell_data(row)
            height = row_height(cells)
            if height + header_height > bottom - top:
                # Keep all evidence from an unusually tall row; fields can span pages.
                if not add_entry(row[0], list(zip(header[1:], row[1:]))):
                    return False
                needs_header = True
                continue
            if cursor + height + (header_height if needs_header else 0) > bottom:
                new_page()
                needs_header = True
            if needs_header:
                if not draw_row(header_cells, heading=True):
                    return False
                needs_header = False
            if not draw_row(cells):
                return False
        cursor += 6
        return True

    try:
        pdf.unlink(missing_ok=True)
        new_page()
        lines, index = list(_report_lines(md.read_text(encoding="utf-8"))), 0
        while index < len(lines):
            raw_line, literal = lines[index]
            line = raw_line.strip()
            index += 1
            if literal:
                if not write_lines(wrap(raw_line, 12, right - left, literal=True),
                                   left, 12, body_color, 16.2):
                    return False, "report code block does not fit on a page"
                continue
            if not line:
                cursor += 4
                continue
            if line.startswith("|"):
                table = [line]
                while (index < len(lines) and not lines[index][1]
                       and lines[index][0].strip().startswith("|")):
                    table.append(lines[index][0].strip())
                    index += 1
                if not add_table(table):
                    return False, "report block does not fit on a page"
                continue
            if line.startswith("# "):
                value, size, color, gap = line[2:], 18, heading_color, 8
            elif line.startswith("## "):
                value, size, color, gap = line.lstrip("# "), 14, heading_color, 6
            elif line.startswith("### "):
                value, size, color, gap = line.lstrip("# "), 12.6, heading_color, 5
            elif line.startswith(("- ", "* ")):
                value, size, color, gap = "- " + line[2:], 12, body_color, 5
            elif line.startswith("> "):
                value, size, color, gap = line[2:], 12, body_color, 5
            else:
                value, size, color, gap = line, 12, body_color, 6
            if line.startswith("#"):
                heading_text, _ = text_and_links(value)
                heading_height = len(wrap(heading_text, size, right - left)) * size * 1.35
                if cursor + heading_height + gap + 32 > bottom:
                    new_page()
                slug = re.sub(r"[^\w -]", "", heading_text.lower()).replace(" ", "-")
                duplicate = anchor_counts.get(slug, 0)
                anchor_counts[slug] = duplicate + 1
                anchor = f"{slug}-{duplicate}" if duplicate else slug
                anchors[anchor] = (page.number, cursor)
                if line.startswith("## "):
                    outline.append([1, heading_text, page.number + 1])
            if not add_block(value, size, color, gap):
                return False, "report block does not fit on a page"
        for number, current_page in enumerate(document, start=1):
            footer = pymupdf.TextWriter(current_page.rect)
            label = style["page"].format(number=number)
            footer.append(pymupdf.Point(right - text_width(label, 8), 811), label,
                          font=font, fontsize=8)
            footer.write_text(current_page, color=(0.38, 0.49, 0.60))
        for page_number, rect, anchor in internal_links:
            if anchor not in anchors:
                return False, f"unresolved report section link: #{anchor}"
            target_page, target_y = anchors[anchor]
            document[page_number].insert_link({
                "kind": pymupdf.LINK_GOTO, "from": rect, "page": target_page,
                "to": pymupdf.Point(left, max(top, target_y - 6)),
            })
        if outline:
            document.set_toc(outline)
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
        output = r.stdout
        if isinstance(output, bytes):
            text = output.decode("utf-8")
        elif isinstance(output, str):
            text = output
        else:
            text = ""
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
        # Font probes are a fallback only when the bundled report renderer has
        # no face for the source. Prove the TeX engine can render plain ASCII
        # once before trying every candidate: a sandboxed/crashed engine makes
        # every font fail identically, and repeating a 180-second probe for each
        # one neither finds a font nor gives the caller a better answer.
        engine_md, engine_pdf = d / "engine.md", d / "engine.pdf"
        engine_md.write_text("PDF engine probe\n", encoding="utf-8")
        if not _pandoc(engine_md, engine_pdf, None):
            return None
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


def _verify_pdf(pdf: pathlib.Path, source: str, needs_cjk: bool,
                link_source: str | None = None) -> tuple[bool, str]:
    """Reject a rendered PDF that lost text or painted broken glyphs."""
    problems = glyph_findings(pdf)
    if problems:
        pdf.unlink(missing_ok=True)
        return False, "; ".join(problems)
    # A document with an authored URL must identify a missing PDF annotation
    # even if the deliberately minimal regression fixture has no body text.
    link_problem = _pdf_link_problem(pdf, source if link_source is None else link_source)
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
    # The plain-text view deliberately removes destinations. Link verification
    # must inspect authored Markdown, otherwise a missing annotation is invisible.
    link_source = md.read_text(encoding="utf-8")
    if has_rtl(source):
        # Delivery must not rebuild a PDF that the CV renderer refused. A
        # nonempty English header does not prove the RTL body survived.
        pdf.unlink(missing_ok=True)
        pdf.with_suffix(".tex").unlink(missing_ok=True)
        return False, ("right-to-left text is not supported by this PDF path; "
                       "Markdown and .docx still ship")
    needs_cjk = has_cjk(source)

    # A selected font is a typography requirement, not a fallback hint.
    # Never silently replace it with a readable but different bundled face.
    if font is not None:
        if not _pandoc(md, pdf, font if needs_cjk else None):
            pdf.unlink(missing_ok=True)
            return False, "could not render the selected report font with pandoc/TeX"
        return _verify_pdf(pdf, source, needs_cjk, link_source)

    style = _portable_report_style(source)
    if style:
        # Counts blocks and source URLs are not the client's narrative language.
        prose = "\n".join(line for line, literal in _report_lines(link_source) if not literal)
        prose = _RAW_ANGLE_URL.sub("", _MD_LINK.sub(r"\1", prose))
        prose = _MD_CODE.sub("", prose)
        # An unambiguous local-language title is stronger evidence than repeated
        # English skill names. Mixed titles can contain a person's or employer's
        # name, so let the narrative decide instead of counting title letters.
        local_title = next((line[2:].strip() for line in prose.splitlines()
                            if line.startswith("# ") and has_cjk(line)
                            and not re.search(r"[A-Za-zÀ-ɏ]", line)), "")
        language_style = _portable_report_style(local_title or prose)
        if language_style:
            for key in ("footer", "page", "link", "separator"):
                style[key] = language_style[key]
    # Without an explicit selection, prefer bundled, embedded report fonts.
    # This keeps Chinese, English, Japanese, Korean and Spanish layout identical
    # across machines, while the explicit RTL refusal above remains unchanged.
    if style:
        ok, why = _render_portable_report(md, pdf, style)
        if ok:
            return _verify_pdf(pdf, source, needs_cjk, link_source)
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
    return _verify_pdf(pdf, source, needs_cjk, link_source)


def deliver(workspace: pathlib.Path, dest: pathlib.Path, slug: str,
            make_pdf: bool = True, include_applications: bool | None = None
            ) -> tuple[list[pathlib.Path], list[str]]:
    written, notes = [], []
    problem = _discover_handoff_problem(workspace)
    if problem:
        return [], [problem]
    report_source = workspace / "report.md"
    if report_source.is_file():
        try:
            problems = report_audience_findings(report_source.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            return [], [f"REPORT_UNREADABLE: {exc}"]
        if problems:
            return [], problems
    # An authored/reviewed report must survive delivery byte-for-byte. Never
    # silently replace a selected layout with the default Markdown renderer.
    reviewed_report = make_pdf and any((workspace / name).exists() for name in (
        "report.pdf", "report-layout-review.yaml", "report-layout-requirements.yaml"))
    if reviewed_report:
        problems, _ = check_layout.inspect(workspace, report=True)
        if problems:
            return [], problems
    fonts = {}
    report_font = None
    if make_pdf:
        for name in ("tailored-profile.yaml", "profile.yaml"):
            profile_path = workspace / name
            if not profile_path.is_file():
                continue
            try:
                profile = journal.load_yaml(profile_path, dict)
            except journal.YamlUnreadable as exc:
                return [], [f"cannot read report typography from {name}: {exc.reason}"]
            meta = profile.get("meta") or {}
            if isinstance(meta, dict) and meta.get("cjk_font"):
                report_font = meta["cjk_font"]
                break
    if include_applications is None:
        include_applications = journal.current_mode(workspace) not in {
            "discover", "assess", "interview"}
    sources = [p for p in sorted(workspace.rglob("*"))
               if p.is_file() and is_deliverable(p, workspace, include_applications)
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
                if src.name == "report.md" and reviewed_report:
                    shutil.copy2(workspace / "report.pdf", pdf)
                    # check_layout --report above already bound every visible
                    # Markdown line and table cell to this PDF's text. The CJK
                    # count would refuse a merged company cell, which that passes.
                    ok, why = _verify_pdf(pdf, source, False, src.read_text(encoding="utf-8"))
                    if ok:
                        written.append(pdf)
                    else:
                        notes.append(f"{pdf.name}: {why}")
                    continue
                glyphs = frozenset(_CJK.findall(source))
                # A user-selected font wins; otherwise covered bundled glyphs
                # keep delivery independent of a Tectonic font probe.
                if glyphs and report_font is not None:
                    fonts[glyphs] = report_font
                elif glyphs and not _portable_report_style(source) and glyphs not in fonts:
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
    ap.add_argument("--include-applications", action="store_true",
                    help="also copy application documents during a non-apply consultation, only when explicitly requested")
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

    written, notes = deliver(ws, dest, ws.name, make_pdf=not args.no_pdf,
                             include_applications=True if args.include_applications else None)
    if not written:
        for note in notes:
            print(f"DELIVER_LAYOUT_OR_INPUT_REFUSED: {note}", file=sys.stderr)
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
