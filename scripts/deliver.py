#!/usr/bin/env python3
"""Deliver a client consultation report and requested application documents.

Default destination: <configured delivery folder>/<workspace-name>/. Use the same explicit --to
folder for all workspaces answering one consultation: a manifest in that folder
records which workspace and mode wrote each file, so a second workspace (or a
second mode of the same workspace) goes to its own subfolder instead of
overwriting the first, and a redelivery removes its own files that it no longer
produces. Client files no manifest accounts for (an older deliver.py wrote none)
count as another workspace's unless they match this round byte-for-byte or the
folder is this workspace's default one. Internal audit artifacts stay in the workspace. A report PDF is
required unless --no-pdf is explicitly requested; CV and letter PDFs are copied
from their renderers' output, never converted from Markdown here. Exit 2 means
incomplete delivery; never call that complete. The last line names the folder
the files actually went to.
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
import unicodedata
from urllib.parse import unquote, urlsplit, urlunsplit

import journal
import check_layout
import lint_no_prediction
import vocab
from render_cv import has_rtl
from pdf_glyphs import glyph_findings
from docx_content import docx_findings
from delivery_paths import writable
from runtime_config import default_root, read_runtime

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

# Which workspace and mode wrote each file in a client folder. Hidden, so the
# folder still shows the client only their documents.
MANIFEST_NAME = ".jobhunt-delivery.json"
# Documents the bundled report renderer was built for. Application documents
# (cv, letter, rirekisho, supporting statement) are never converted from
# Markdown here: the report renderer puts a "Career consultation report"
# footer on them, prints Markdown markers and bypasses render_cv's own refusals
# (NO_ENGINE, TEXT_OFF_PAGE) and check_pages; measured on a delivered CV.
REPORT_RENDERED = frozenset({"report", "interview-brief"})
# Where each application PDF has to come from, said in the note when it is absent.
APPLICATION_PDF_SOURCES = {
    "cv": ("render it with `render_cv.py <profile> --format pdf --out <ws>/cv.pdf`, "
           "or export the final cv.docx to cv.pdf, and run check_pages.py"),
    "letter": ("render it with `render_letter.py <letter.yaml> --format pdf --out "
               "<ws>/letter.pdf`, or export the final letter.docx to letter.pdf"),
}
# A second mode of the same workspace delivers beside the first, never over it.
# Named in the report's language (text_language); Chinese for an older delivery.
MODE_FOLDERS_BY_LANG = {
    "zh": {"discover": "岗位搜索", "assess": "岗位评估", "apply": "投递材料",
           "interview": "模拟面试", "prepare": "面试准备计划", "": "其他交付"},
    "en": {"discover": "Job search", "assess": "Posting assessment",
           "apply": "Application package", "interview": "Mock interview",
           "prepare": "Preparation plan", "": "Other delivery"},
    "es": {"discover": "Búsqueda de empleo", "assess": "Evaluación de la oferta",
           "apply": "Paquete de candidatura", "interview": "Entrevista simulada",
           "prepare": "Plan de preparación", "": "Otras entregas"},
    "ja": {"discover": "求人探し", "assess": "求人評価", "apply": "応募書類一式",
           "interview": "模擬面接", "prepare": "面接準備プラン", "": "その他"},
    "ko": {"discover": "채용 탐색", "assess": "공고 평가", "apply": "지원 서류 일체",
           "interview": "모의 면접", "prepare": "면접 준비 계획", "": "기타"},
}
MODE_FOLDERS = {k: v for k, v in MODE_FOLDERS_BY_LANG["zh"].items() if k}


def report_audience_findings(source: str) -> list[str]:
    """Keep fixture provenance in the private audit, not the client report.

    Match fixture provenance only, not words such as '测试' or '模拟面试':
    those are ordinary job requirements and preparation advice. Practice scope
    ('本轮只练了技术面', 'a mock is not a real interview') is normal advice to a
    real client, and 'synthetic candidate' is chemistry vocabulary.
    """
    markers = ("固定虚构履历", "固定的虚构履历", "固定虚构简历", "固定的虚构简历",
               "测试用的虚构履历", "测试用虚构履历", "测试用的虚构简历", "测试用虚构简历",
               "fixed fictional", "synthetic candidate profile",
               "分母可以逐条审计", "本 skill 不给出",
               "denominator can be audited row by row", "this skill states no interview")
    # A Markdown line break must not split a marker.
    folded = re.sub(r"\s+", " ", source.casefold())
    folded = re.sub(r"(?<=[^\x00-\x7f]) (?=[^\x00-\x7f])", "", folded)
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


_SPANISH = re.compile(r"\b(?:tus|candidaturas?|experiencia|puestos?|evidencia|"
                      r"vacantes?|recomendaci[oó]n|ubicaci[oó]n|consejos?|"
                      r"entrevistas?|necesidades|usuarios?|requisitos|"
                      r"curr[ií]culum|trabajo|responsabilidades|confirma|"
                      r"solicitud|puedes)\b")
# Function words only one of the three languages uses. Two Spanish nouns also
# turn up in an English report that quotes a Madrid posting, and in a Portuguese
# one (requisitos, entrevistas, candidatura are spelled alike); both then
# arrived in Informe/ with a Spanish footer. The small words say which language
# the sentences themselves are written in.
_WORD = re.compile(r"[^\W\d_]+")
_SPANISH_ONLY = frozenset("el la los las del y en un una con al lo tu más pero muy "
                          "también está son hay".split())
_ENGLISH_ONLY = frozenset("the and of to is you your that with for this are it be "
                          "on in".split())
_PORTUGUESE_ONLY = frozenset("os do da dos das em um uma com ao não você são na nas "
                             "e é seu sua".split())
# Words that are Spanish and not French, Italian, Portuguese or Dutch. The shared
# small words (la, un, en, con, de) cannot tell those apart, which is why the
# vocabulary above is asked for first; but a short Spanish report that happens to
# use none of those nouns was named and footed in English. Three different ones
# of these, in sentences where Spanish function words outnumber the others', are
# Spanish prose.
_SPANISH_DISTINCT = frozenset("el los las y muy pero hay también más está estás eres "
                              "tienes usted años empresa equipo puesto".split())
_REPORT_STYLES = {
    "ja": {"font": "japan", "footer": "キャリア相談レポート",
           "page": "{number} ページ", "link": "リンク：", "separator": "："},
    "ko": {"font": "korea", "footer": "커리어 상담 보고서",
           "page": "{number}쪽", "link": "링크: ", "separator": ": "},
    "zh": {"font": "china-s", "footer": "职业咨询报告",
           "page": "第 {number} 页", "link": "链接：", "separator": "："},
    "es": {"font": "helv", "footer": "Informe de orientación profesional",
           "page": "Página {number}", "link": "Enlace: ", "separator": ": "},
    "en": {"font": "helv", "footer": "Career consultation report",
           "page": "Page {number}", "link": "Link: ", "separator": ": "},
}


def text_language(text: str) -> str:
    """zh, ja, ko, es or en: the language of the dominant prose.

    The report's PDF labels and the delivered file and folder names both come
    from this, so a Spanish report never arrives in a folder called 报告/."""
    # A quoted employer or original posting title may use a different script
    # from the consultation. Choose the labels from the dominant prose, while
    # choosing a font separately that also covers those preserved quotations.
    han = len(_HAN.findall(text))
    japanese = len(_JAPANESE.findall(text))
    korean = len(_KOREAN.findall(text))
    latin = len(re.findall(r"[A-Za-zÀ-ɏ]", text))
    cjk = han + japanese + korean
    if cjk > latin and japanese * 3 > han and japanese > korean:
        return "ja"
    if cjk > latin and korean > japanese and korean > han:
        return "ko"
    if cjk > latin and han:
        return "zh"
    # Articles and prepositions such as de/la/un also occur in Dutch, French,
    # Italian and people's names. Require distinct Spanish vocabulary before
    # replacing the documented English fallback for other Latin languages.
    folded = text.casefold()
    words = Counter(_WORD.findall(folded))
    if (len(set(_SPANISH.findall(folded))) >= 2
            or sum(1 for word in _SPANISH_DISTINCT if words[word]) >= 3):
        spanish, english, portuguese = (sum(words[word] for word in group) for group in (
            _SPANISH_ONLY, _ENGLISH_ONLY, _PORTUGUESE_ONLY))
        # A tie (a table of labels with no sentences) keeps the vocabulary's answer.
        if spanish >= english and spanish >= portuguese:
            return "es"
    return "en"


def report_language(markdown: str) -> str:
    """text_language of a Markdown document's own prose: the one rule behind both
    the PDF's footer labels and the delivered file and folder names.

    Measured before the two shared it: a Chinese assessment whose links and stack
    names outnumbered its Han characters went out as Report/…Job assessment.pdf
    with a 职业咨询报告 footer, because the names counted the URLs and the footer
    did not.
    """
    # Code blocks, comments and link destinations are not the client's narrative.
    prose = "\n".join(line for line, literal in _report_lines(markdown) if not literal)
    prose = _RAW_ANGLE_URL.sub("", _MD_LINK.sub(r"\1", prose))
    prose = _MD_CODE.sub("", prose)
    # An unambiguous local-language title is stronger evidence than repeated
    # English skill names. Mixed titles can contain a person's or employer's
    # name, so let the narrative decide instead of counting title letters.
    title = next((line[2:].strip() for line in prose.splitlines()
                  if line.startswith("# ") and has_cjk(line)
                  and not re.search(r"[A-Za-zÀ-ɏ]", line)), "")
    if not title:
        return text_language(prose)
    if _JAPANESE.search(title) or _KOREAN.search(title):
        return text_language(title)
    # A title in Han alone (応募書類, 面接準備) is as Japanese as it is Chinese, and
    # read on its own it put a 职业咨询报告 footer on a Japanese report. It says the
    # report is not English; the body's own script, Latin names aside, says which.
    body = text_language(re.sub(r"[A-Za-zÀ-ɏ]", "", prose))
    return body if body in {"ja", "ko"} else "zh"


def _portable_report_style(text: str) -> dict[str, str] | None:
    """Return a bundled-font report style when every visible glyph is covered."""
    try:
        import pymupdf
    except ImportError:
        return None

    style = dict(_REPORT_STYLES[text_language(text)])
    japanese = len(_JAPANESE.findall(text))
    korean = len(_KOREAN.findall(text))
    cjk = len(_HAN.findall(text)) + japanese + korean
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
    """Yield visible Markdown lines, keeping comments inside code literal."""
    fence = None
    comment = False
    for line in source.splitlines():
        if fence is not None:
            if re.fullmatch(r" {0,3}" + re.escape(fence[0]) +
                            r"{" + str(len(fence)) + r",}\s*", line):
                fence = None
            else:
                yield line, True
            continue
        opening = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if not comment and opening and not (opening[1][0] == "`" and "`" in opening[2]):
            fence = opening[1]
            continue
        visible, position = [], 0
        while position < len(line):
            if comment:
                end = line.find("-->", position)
                if end < 0:
                    break
                comment, position = False, end + 3
                continue
            # A complete inline-code span protects any comment syntax inside
            # it. Unmatched backticks remain ordinary Markdown text.
            token = re.search(r"(?<!`)(`+)(?!`)(.*?)\1(?!`)|<!--", line[position:])
            if token is None:
                visible.append(line[position:])
                break
            visible.append(line[position:position + token.start()])
            position += token.end()
            if token.group() == "<!--":
                comment = True
            else:
                visible.append(token.group())
        if visible or not comment:
            yield "".join(visible), False


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


# Client file and folder names per language. The report name itself comes from
# report_names.report_stem; "report" here is the stem used when nothing names it.
CLIENT_NAMES_BY_LANG = {
    "zh": {"report": "求职建议报告", "cv": "简历", "letter": "求职信", "rirekisho": "履历书",
           "supporting-statement": "申请陈述", "interview-brief": "面试准备"},
    "en": {"report": "Career consultation report", "cv": "CV", "letter": "Cover letter",
           "rirekisho": "Rirekisho", "supporting-statement": "Supporting statement",
           "interview-brief": "Interview brief"},
    "es": {"report": "Informe de orientación profesional", "cv": "CV",
           "letter": "Carta de presentación", "rirekisho": "Rirekisho",
           "supporting-statement": "Declaración de méritos",
           "interview-brief": "Guía para la entrevista"},
    "ja": {"report": "キャリア相談レポート", "cv": "職務経歴書", "letter": "カバーレター",
           "rirekisho": "履歴書", "supporting-statement": "志望動機書",
           "interview-brief": "面接準備メモ"},
    "ko": {"report": "커리어 상담 보고서", "cv": "이력서", "letter": "커버레터",
           "rirekisho": "일본식 이력서", "supporting-statement": "지원 진술서",
           "interview-brief": "면접 준비 자료"},
}
CLIENT_FOLDERS_BY_LANG = {
    "zh": {"report": "报告", "interview-brief": "面试准备", "": "简历"},
    "en": {"report": "Report", "interview-brief": "Interview prep", "": "Application"},
    "es": {"report": "Informe", "interview-brief": "Entrevista", "": "Candidatura"},
    "ja": {"report": "レポート", "interview-brief": "面接準備", "": "応募書類"},
    "ko": {"report": "보고서", "interview-brief": "면접 준비", "": "지원 서류"},
}
CLIENT_NAMES = CLIENT_NAMES_BY_LANG["zh"]
CLIENT_FOLDERS = {k: v for k, v in CLIENT_FOLDERS_BY_LANG["zh"].items() if k}


def delivery_language(workspace: pathlib.Path) -> str:
    """The language the client reads: the report's, else the CV's or letter's.

    zh when there is no text to tell, which is also what every delivery before
    per-language names used."""
    for name in ("report.md", "cv.md", "letter.md"):
        path = pathlib.Path(workspace) / name
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if text.strip():
            return report_language(text)
    return "zh"


def client_path(rel: pathlib.Path, workspace: pathlib.Path | None = None,
                lang: str | None = None) -> pathlib.Path:
    """Use real candidate/target labels for reports; keep canonical source names.

    Without a workspace (and no `lang`) this is the Chinese legacy name an older
    deliver.py wrote, which is what ownership checks compare against."""
    if lang is None:
        lang = delivery_language(workspace) if workspace is not None else "zh"
    folders = CLIENT_FOLDERS_BY_LANG[lang]
    folder = folders.get(rel.stem, folders[""])
    name = CLIENT_NAMES_BY_LANG[lang][rel.stem]
    if rel.stem == "report" and workspace is not None:
        from report_names import report_stem
        name = report_stem(workspace, journal.current_mode(workspace), lang)
    return pathlib.Path(folder) / (name + rel.suffix)


# Legacy paths remain valid alongside the bounded report namespace checked by
# _client_tail_ok; neither permits cleanup of arbitrary client files.
_CLIENT_TAILS = frozenset(client_path(pathlib.Path(stem + suffix), lang=lang).as_posix()
                          for lang, names in CLIENT_NAMES_BY_LANG.items()
                          for stem in names for suffix in (".md", ".pdf", ".docx"))
_REPORT_FOLDERS = frozenset(f["report"] for f in CLIENT_FOLDERS_BY_LANG.values())
_RESERVED_FOLDERS = frozenset(name for folders in CLIENT_FOLDERS_BY_LANG.values()
                              for name in folders.values())


def _report_suffixes() -> tuple[str, ...]:
    from report_names import LEGACY_NAMES, MODE_NAMES
    return tuple({*LEGACY_NAMES.values(),
                  *(name for names in MODE_NAMES.values() for name in names.values())})


def _client_tail_ok(tail: str) -> bool:
    import unicodedata
    if tail in _CLIENT_TAILS:
        return True
    path = pathlib.PurePosixPath(tail)
    return (len(path.parts) == 2 and path.parts[0] in _REPORT_FOLDERS
            and path.suffix in {".md", ".pdf", ".docx"}
            and not any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in path.name)
            and len(path.stem.encode("utf-8")) <= 200
            # ASCII space and dot only. Before 1.5.1 a name pasted with an
            # ideographic or no-break space kept it in the stem; stripping every
            # kind of space here refused the manifest that recorded such a file,
            # and that folder then stopped every later delivery. Read, the entry
            # is cleaned up like any other and replaced under the trimmed name.
            and path.stem == path.stem.strip(" .")
            and not re.search(r'[\x00-\x1f\x7f<>:"/\\|?*]', path.name)
            and any(path.stem.endswith("－" + suffix) and len(path.stem) > len(suffix) + 1
                    for suffix in _report_suffixes()))


def is_deliverable(path: pathlib.Path, workspace: pathlib.Path,
                   include_applications: bool = True,
                   also: frozenset = frozenset()) -> bool:
    rel = path.relative_to(workspace)
    # Explicit client artifacts only. completion.md can contain tool diagnostics.
    return ((include_applications or rel.stem == "report" or rel.stem in also)
            and len(rel.parts) == 1 and rel.stem in {
        "report", "cv", "letter", "rirekisho", "supporting-statement", "interview-brief"
    } and rel.suffix in {".md", ".pdf", ".docx"})


# ---- one client folder, several workspaces --------------------------------
#
# MEASURED before this existed: two workspaces delivered to one `--to` both
# exited 0 while the second report replaced the first, and 简历/ ended up holding
# Acme's 简历.docx beside Beta's 简历.md and 简历.pdf — a mixed application the
# client could have sent. The same happened to one workspace delivering apply
# and then interview into its default folder: the debrief replaced the apply
# report. CV/letter names stay fixed and report labels can coincide, so ownership
# is still recorded beside the files.
#
# A clash goes to a SUBFOLDER rather than being refused. A refusal sends the
# agent to pick another --to (splitting the consultation it was told to keep
# together) or to clear the folder to make the command pass, which destroys the
# earlier delivery. A subfolder overwrites nothing, keeps each workspace's
# report and CV together, and the manifest sends every later redelivery of the
# same workspace and mode back to the same place.

class ManifestError(Exception):
    """The destination's manifest cannot be trusted, so ownership is unknown."""


def _manifest_rel_ok(folder: str, rel) -> bool:
    if not isinstance(rel, str):
        return False
    path = pathlib.PurePosixPath(rel)
    if path.is_absolute() or ".." in path.parts or "\\" in rel:
        return False
    parts = path.parts
    if len(parts) < 2 or not _client_tail_ok("/".join(parts[-2:])):
        return False
    return "/".join(parts[:-2]) == folder


def _manifest_folder_ok(folder) -> bool:
    if not isinstance(folder, str):
        return False
    if folder == "":
        return True
    path = pathlib.PurePosixPath(folder)
    return (not path.is_absolute() and len(path.parts) == 1 and folder not in ("..", ".")
            and "\\" not in folder and folder not in _RESERVED_FOLDERS)


def read_manifest(root: pathlib.Path) -> list[dict]:
    """The recorded deliveries in `root`, oldest first. Raises ManifestError."""
    path = root / MANIFEST_NAME
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ManifestError(f"{path} cannot be read: {exc}") from None
    deliveries = data.get("deliveries") if isinstance(data, dict) else None
    if not isinstance(deliveries, list):
        raise ManifestError(f"{path} is not a delivery manifest written by deliver.py")
    for entry in deliveries:
        if not (isinstance(entry, dict) and isinstance(entry.get("workspace"), str)
                and isinstance(entry.get("mode"), str)
                and _manifest_folder_ok(entry.get("folder"))
                and isinstance(entry.get("files"), dict)
                and all(_manifest_rel_ok(entry["folder"], rel) and isinstance(sha, str)
                        for rel, sha in entry["files"].items())):
            raise ManifestError(f"{path} holds an entry deliver.py did not write: "
                                f"{json.dumps(entry, ensure_ascii=False)[:200]}")
    return deliveries


def _alive(root: pathlib.Path, entry: dict) -> bool:
    """An entry whose files the user has all removed no longer holds its folder."""
    return any((root / rel).is_file() for rel in entry["files"])


# Client documents with no manifest entry. An older deliver.py wrote exactly these
# names straight into the destination and recorded nothing, so a folder that
# held a whole consultation before 1.3.0 looked EMPTY to the ownership check: the
# next workspace delivered into it and overwrote another workspace's report and
# CV (measured 2026-10-24). Unaccounted files therefore count as somebody else's,
# with two exceptions that prove they are this workspace's own: every one of them
# is byte-identical to what this run would copy to that name, or the destination
# is the default folder deliver.py names after this very workspace
# (DEFAULT_ROOT / <workspace name>). A report PDF the older run RENDERED cannot be
# matched in advance, so in a shared --to folder it keeps the round in a subfolder
# — the outcome that overwrites nothing.
def unaccounted_files(root: pathlib.Path, deliveries: list[dict]) -> list[str]:
    """Client documents at the top of `root` that no manifest entry recorded."""
    recorded = {rel for entry in deliveries for rel in entry["files"]}
    tails = set(_CLIENT_TAILS)
    for folder in _REPORT_FOLDERS:
        directory = root / folder
        if directory.is_dir():
            tails.update(f"{folder}/{path.name}" for path in directory.iterdir()
                         if path.is_file() and _client_tail_ok(f"{folder}/{path.name}"))
    return sorted(tail for tail in tails
                  if tail not in recorded and (root / tail).is_file())


def planned_copies(workspace: pathlib.Path, make_pdf: bool,
                   include_applications: bool | None) -> dict[str, pathlib.Path]:
    """{client path: workspace file} for what deliver() copies byte-for-byte."""
    _, sources = _delivery_sources(workspace, make_pdf, include_applications)
    planned = {client_path(src.relative_to(workspace), workspace).as_posix(): src for src in sources}
    if make_pdf and (workspace / "report.pdf").is_file():
        # A reviewed report PDF is copied, never re-rendered (see deliver()).
        planned[client_path(pathlib.Path("report.pdf"), workspace).as_posix()] = workspace / "report.pdf"
    return planned


def foreign_files(root: pathlib.Path, deliveries: list[dict], workspace: pathlib.Path,
                  make_pdf: bool, include_applications: bool | None) -> list[str]:
    """The unaccounted client documents in `root` this workspace cannot claim."""
    unaccounted = unaccounted_files(root, deliveries)
    if not unaccounted or root == (DEFAULT_ROOT / workspace.name).resolve():
        return []
    planned = planned_copies(workspace, make_pdf, include_applications)
    # Older deliveries used generic Chinese names (a generic report name, 简历/,
    # whatever the report's language). Identical bytes under that legacy name
    # establish the same ownership as before, but an unrecorded old file is retained.
    for src in tuple(planned.values()):
        planned[client_path(src.relative_to(workspace)).as_posix()] = src

    def same(rel: str) -> bool:
        try:
            return rel in planned and (root / rel).read_bytes() == planned[rel].read_bytes()
        except OSError:
            return False

    return [rel for rel in unaccounted if not same(rel)]


def legacy_twins(root: pathlib.Path, deliveries: list[dict], workspace: pathlib.Path,
                 make_pdf: bool, include_applications: bool | None) -> list[str]:
    """Unrecorded Chinese-named copies of the documents this round delivers under
    its own language's names (简历/简历.pdf for Application/CV.pdf, ...).

    Call it only when the round lands in `root` itself. The old names were
    overwritten in place; with new names they are removed instead, so a stale CV
    or brief never sits beside the current one. The generic report is left
    alone, as it always was.

    Each one has to be proven this workspace's own, exactly as foreign_files
    proves it: byte-identical to what this round copies, or `root` is the
    default folder named after this workspace. Landing in `root` is not that
    proof. A workspace the manifest already places there skips foreign_files, and
    a 简历/简历.pdf the user put in the folder afterwards was deleted under a
    notice calling it this workspace's earlier copy (measured 2026-11-20)."""
    unaccounted = set(unaccounted_files(root, deliveries))
    if not unaccounted:
        return []
    planned = planned_copies(workspace, make_pdf, include_applications)
    sources = {src.name: src for src in planned.values() if src.stem != "report"}
    own_folder = root == (DEFAULT_ROOT / workspace.name).resolve()
    twins = []
    for stem in sorted({src.stem for src in sources.values()}):
        for suffix in (".md", ".pdf", ".docx"):
            legacy = client_path(pathlib.Path(stem + suffix)).as_posix()
            current = client_path(pathlib.Path(stem + suffix), workspace).as_posix()
            if legacy == current or legacy not in unaccounted:
                continue
            if not own_folder:
                try:
                    if (root / legacy).read_bytes() != sources[stem + suffix].read_bytes():
                        continue
                except (KeyError, OSError):
                    continue  # nothing this round copies under that name vouches for it
            twins.append(legacy)
    return twins


def _same_file(one: pathlib.Path, other: pathlib.Path) -> bool:
    """Two spellings of one file: a case-insensitive or normalising volume
    (macOS, Windows) answers to both, and a string comparison cannot know."""
    try:
        return one.samefile(other)
    except OSError:
        return False


def unowned_targets(out: pathlib.Path, previous: dict, root: pathlib.Path,
                    workspace: pathlib.Path, make_pdf: bool,
                    include_applications: bool | None) -> list[str]:
    """Files this round would write into its recorded folder `out` over a file
    its own manifest entry never recorded and whose bytes it cannot match.

    The manifest sends a redelivery back to its folder without asking what else
    is there, which was safe while the names never changed. They now follow the
    report's language: after the upgrade an English report's CV lands on
    Application/CV.pdf, and a client who kept their own Application/CV.pdf in
    that shared folder had it overwritten without a word (measured 2026-11-20).
    """
    _, sources = _delivery_sources(workspace, make_pdf, include_applications)
    copies = planned_copies(workspace, make_pdf, include_applications)
    targets = set(copies)
    for src in sources:
        if make_pdf and src.suffix == ".md" and src.stem in REPORT_RENDERED:
            # Rendered here, so there are no bytes to compare in advance.
            targets.add(client_path(src.relative_to(workspace), workspace)
                        .with_suffix(".pdf").as_posix())
    recorded = [root / rel for rel in previous["files"]]
    unowned = []
    for tail in sorted(targets):
        path = out / tail
        if not path.is_file() or any(_same_file(path, known) for known in recorded):
            continue
        try:
            if tail in copies and path.read_bytes() == copies[tail].read_bytes():
                continue
        except OSError:
            pass
        unowned.append(path.relative_to(root).as_posix())
    return unowned


def _safe_folder_name(text: str) -> str:
    text = re.sub(r'[\x00-\x1f<>:"/\\|?*]+', " ", text)
    text = re.sub(r"\s+", " ", text).strip().strip(".").strip()
    return text[:80].strip()


def _posting_label(workspace: pathlib.Path) -> str:
    """`<company> <role>` from posting.yaml: what the client knows the posting by."""
    try:
        posting = journal.load_yaml(workspace / "posting.yaml", dict)
    except (OSError, journal.YamlUnreadable):
        return ""
    words = [posting.get(key) for key in ("company", "role_title")]
    if not isinstance(words[1], str):
        words[1] = posting.get("title")
    return _safe_folder_name(" ".join(w.strip() for w in words if isinstance(w, str) and w.strip()))


def choose_folder(root: pathlib.Path, deliveries: list[dict], workspace: pathlib.Path,
                  mode: str, foreign: list[str] | tuple = (), unowned=None
                  ) -> tuple[str, dict | None, dict | None]:
    """(folder, this owner's previous entry, the entry it had to step around).

    `folder` is "" for the destination itself, otherwise one subfolder name.
    `foreign` (see foreign_files) holds the destination's top level like a
    recorded delivery would; the entry stepped around is then
    `{"unaccounted": foreign}`.

    `unowned`, when given, is called with this owner's previous entry and returns
    the files in its folder this round would overwrite without owning them (see
    unowned_targets). Any such file moves the round to a fresh subfolder; the
    previous entry is still returned, so its own recorded files are cleaned up.
    """
    live = [entry for entry in deliveries if _alive(root, entry)]
    own = next((entry for entry in live if entry["workspace"] == str(workspace)
                and entry["mode"] == mode), None)
    blocked = list(unowned(own)) if own is not None and unowned is not None else []
    if own is not None and not blocked:
        return own["folder"], own, None
    taken = {entry["folder"]: entry for entry in live}
    stepped_around = taken.get("")
    if blocked:
        stepped_around = {"unaccounted": blocked}
    elif "" not in taken and foreign:
        stepped_around = taken[""] = {"unaccounted": list(foreign)}
    if stepped_around is None:
        return "", None, None
    labels = MODE_FOLDERS_BY_LANG[delivery_language(workspace)]
    mode_label = labels.get(mode, labels[""])
    same_workspace = any(entry["workspace"] == str(workspace) for entry in live)
    # Without posting.yaml (a discover or collection workspace), the workspace
    # name minus its date is the closest thing to what the client calls it.
    base = mode_label if same_workspace else (
        _posting_label(workspace)
        or _safe_folder_name(re.sub(r"[-_ ]?\d{4}-\d{2}-\d{2}$", "", workspace.name))
        or _safe_folder_name(workspace.name))
    candidates = [base]
    if not same_workspace:
        candidates.append(f"{base} {mode_label}")
    candidates += [f"{base} ({n})" for n in range(2, 100)]
    for candidate in candidates:
        candidate = _safe_folder_name(candidate)
        if not candidate or candidate in _RESERVED_FOLDERS or candidate in taken:
            continue
        place = root / candidate
        try:
            if place.exists() and (not place.is_dir() or any(place.iterdir())):
                continue  # somebody else's folder, or files no manifest accounts for
        except OSError:
            continue
        return candidate, own, stepped_around
    raise ManifestError(f"no free subfolder name for {workspace.name} in {root}")


def finish_manifest(root: pathlib.Path, deliveries: list[dict], workspace: pathlib.Path,
                    mode: str, folder: str, previous: dict | None,
                    written: list[pathlib.Path]) -> list[str]:
    """Remove this owner's stale files, then record what it wrote. Returns notices."""
    notices = []
    produced = {}
    for path in written:
        try:
            produced[path.relative_to(root).as_posix()] = journal.sha256_file(path)
        except (OSError, ValueError):
            continue
    for rel, sha in (previous or {}).get("files", {}).items():
        if rel in produced:
            continue
        path = root / rel
        try:
            if not path.is_file():
                continue
            # A report renamed in case only (acme bv -> Acme BV) is, on macOS and
            # Windows, the file this run just wrote: removing the old spelling
            # removed the delivery itself while the run said Delivered.
            if any(_same_file(path, new) for new in written):
                continue
            if journal.sha256_file(path) != sha:
                notices.append(
                    f"NOTICE_STALE_FILE_KEPT: {rel} came from an earlier delivery of this "
                    "workspace and this run did not produce it, but it was edited after "
                    "that delivery, so it was left in place; remove it if it is obsolete.")
                continue
            path.unlink()
            if path.suffix == ".pdf":
                # No LaTeX source of a stale PDF stays either (a renamed CV leaves it).
                path.with_suffix(".tex").unlink(missing_ok=True)
            if not any(path.parent.iterdir()):
                path.parent.rmdir()
        except OSError as exc:
            notices.append(f"NOTICE_STALE_FILE_KEPT: {rel} could not be removed: {exc}")
    kept =[entry for entry in deliveries if _alive(root, entry)
            and not (entry["workspace"] == str(workspace) and entry["mode"] == mode)]
    kept.append({"workspace": str(workspace), "workspace_name": workspace.name,
                 "mode": mode, "folder": folder, "files": produced,
                 "delivered_at": datetime.datetime.now().astimezone().isoformat()})
    path = root / MANIFEST_NAME
    temporary = root / (MANIFEST_NAME + ".tmp")
    try:
        temporary.write_text(json.dumps({"format": 1, "deliveries": kept},
                                        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        notices.append(f"NOTICE_MANIFEST_NOT_WRITTEN: {path}: {exc}; a later delivery "
                       "to this folder cannot tell these files apart from its own")
    return notices


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
    line = line.strip()
    cells = [""]
    escaped = False
    for char in line:
        if escaped:
            cells[-1] += char if char in "\\|" else "\\" + char
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "|":
            cells.append("")
        else:
            cells[-1] += char
    if escaped:
        cells[-1] += "\\"
    if line.startswith("|"):
        cells.pop(0)
    if line.endswith("|") and cells and cells[-1] == "":
        cells.pop()
    return [part.strip() for part in cells]


def _is_table_rule(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _wrap_report_text(value, size, width, text_width, literal=False):
    """Fit text without stranding CJK punctuation or splitting a short token."""
    closing = set("，。；：！？、）】》〉”’」』〕］｝％…,.!?;:)]}")
    opening = set("（【《〈“‘「『〔［｛([{")
    word = re.compile(r"[A-Za-zÀ-ɏ0-9_+/.@:#?&=%~가-힯-]")
    currency = set("€$£¥₩₹₽")
    separators = set(",.'’")

    def joined(text, index):
        """Whether text[index - 1] and text[index] belong to one number.

        `€4,000` once printed as `€4,` / `000`, and `€4000` as `€` / `4000`:
        a currency sign or a digit-group separator is not a word character, so
        the word rule above let the line break there.
        """
        left, right = text[index - 1], text[index]
        if left in currency and right.isdigit():
            return True
        # `€ 4000` and `4,000 €`: one space between a sign and its amount.
        after = text[index + 1] if index + 1 < len(text) else ""
        before = text[index - 2] if index > 1 else ""
        if right == " " and ((left in currency and after.isdigit())
                             or (left.isdigit() and after in currency)):
            return True
        if left == " " and ((before in currency and right.isdigit())
                            or (before.isdigit() and right in currency)):
            return True
        if left.isdigit() and right in separators:
            return index + 1 < len(text) and text[index + 1].isdigit()
        return (left in separators and right.isdigit()
                and index > 1 and text[index - 2].isdigit())

    def number_span(text, index):
        start, stop = index - 1, index + 1
        while start > 0 and joined(text, start):
            start -= 1
        while stop < len(text) and joined(text, stop):
            stop += 1
        return start, stop

    result = []
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
            if not literal:
                while True:
                    previous = end
                    if end < len(rest) and word.fullmatch(rest[end - 1]) and word.fullmatch(rest[end]):
                        start, stop = end - 1, end + 1
                        while start > 0 and word.fullmatch(rest[start - 1]):
                            start -= 1
                        while stop < len(rest) and word.fullmatch(rest[stop]):
                            stop += 1
                        # Long URLs/words still flow. A token that fits on a
                        # fresh line moves there intact, even beside CJK.
                        if start > 0 and text_width(rest[start:stop], size) <= width:
                            end = start
                    if 0 < end < len(rest) and joined(rest, end):
                        start, stop = number_span(rest, end)
                        if start > 0 and text_width(rest[start:stop], size) <= width:
                            end = start
                    while end > 1 and (rest[end] in closing or rest[end - 1] in opening):
                        end -= 1
                    if end == previous:
                        break
            result.append(rest[:end] if literal else rest[:end].rstrip())
            rest = rest[end:] if literal else rest[end:].lstrip()
        if not source_line.strip():
            result.append("")
    return result or [""]


# Report typography. One place, because report_requirements.py states these
# values to the layout gate and a test measures a rendered page against them.
REPORT_SIZES = {"title": 18, "heading": 15, "subheading": 13, "body": 12,
                "table": 11.5, "contents": 10.5, "meta": 10.5, "footer": 8}
REPORT_INK = (26 / 255, 26 / 255, 28 / 255)   # #1a1a1c, all text: the CV's black
REPORT_MUTED = (0.42, 0.42, 0.44)      # metadata line, footer
REPORT_RULE = (0.80, 0.80, 0.80)       # table row rules
_INLINE = re.compile(
    r"\[(?P<label>[^\]]+)]\((?:<)?(?P<url>[^\s)>]+)(?:>)?\)"
    r"|<(?P<raw>https?://[^\s>]+)>"
    r"|\*\*(?P<bold>.+?)\*\*"
    r"|`(?P<code>[^`]+)`")
_META_LINE = re.compile(r"[｜|·•]")


def _inline_runs(value: str):
    """One Markdown line as the PDF prints it, and where its links are.

    Returns `(display, links)`; `links` is `(start, end, url)` ranges in
    `display` offsets, recorded where the text is produced, so a label that
    occurs twice in a line is linked where it was written. Emphasis marks are
    dropped: the report is set in one weight.
    """
    out: list[str] = []
    links: list[tuple[int, int, str]] = []
    length = 0

    def put(text: str, url: str | None) -> None:
        nonlocal length
        if not text:
            return
        if url:
            links.append((length, length + len(text), url))
        out.append(text)
        length += len(text)

    def emit(text: str, url: str | None) -> None:
        position = 0
        for match in _INLINE.finditer(text):
            put(text[position:match.start()], url)
            position = match.end()
            if match.group("label") is not None:
                emit(match.group("label"), html.unescape(match.group("url")))
            elif match.group("raw") is not None:
                target = html.unescape(match.group("raw"))
                put(urlsplit(target).netloc.removeprefix("www.") or target, target)
            elif match.group("bold") is not None:
                emit(match.group("bold"), url)
            else:
                put(match.group("code"), url)
        put(text[position:], url)

    emit(value.replace("⚠️", "[!]").replace("⚠", "[!]"), None)
    return "".join(out), links


def _render_portable_report(md: pathlib.Path, pdf: pathlib.Path,
                            style: dict[str, str]) -> tuple[bool, str]:
    """Render a supported LTR report with a bundled, extractable PDF font.

    This avoids host-installed fonts and TeX font discovery for the five report
    languages the skill localizes: Chinese, English, Japanese, Korean, Spanish.

    The page is a plain document: black ink in one weight, headings told apart
    by size and the space above them, one light rule under a table's column
    labels. It was navy on a pale blue band, which the user called ugly and
    hard to scan (2026-11-20). Two redraws were rejected the same day: rules
    under every heading and row with bold labels ("too many lines", "not so
    much bold"), then bold headings with a grey conclusion box ("no bold
    needed", "looks AI-made"). Do not bring back bold, boxes or accent bars.
    """
    try:
        import pymupdf
    except ImportError:
        return False, "PyMuPDF is unavailable"

    page_width, page_height = 595.28, 841.89  # A4 in PDF points
    left, right, top, bottom = 56, 539, 64, 770
    sizes = REPORT_SIZES
    # Sizes and leading are the ones the report has always used: reading size
    # is a standing rule, and the one-page interview brief is measured at it.
    body, body_leading = sizes["body"], sizes["body"] * 1.35
    table_size, table_leading = sizes["table"], 15.5
    ink, muted = REPORT_INK, REPORT_MUTED
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
        return _wrap_report_text(value, size, width, text_width, literal)

    def place_link(rect, url: str) -> None:
        assert page is not None
        if url.startswith("#"):
            internal_links.append((page.number, rect, unquote(url[1:])))
        else:
            page.insert_link({"kind": pymupdf.LINK_URI, "from": rect, "uri": url})

    def write_lines(lines: list[str], x: float, size: float,
                    color: tuple[float, float, float], leading: float,
                    link: str | None = None, allow_split: bool = False,
                    runs=None) -> bool:
        """Paint text through TextWriter, whose CJK metrics stay compact.

        `runs` is `_inline_runs` output for the text these lines were wrapped
        from. Each line is found again in that text, so a link label is
        clickable where it is printed. `link` makes the whole block one link
        instead.
        """
        nonlocal cursor
        display, link_ranges = runs or ("", [])
        target = [-1] * len(display)
        for number, (start, end, _) in enumerate(link_ranges):
            target[start:end] = [number] * (end - start)
        offsets, position = [], 0
        for line in lines:
            found = display.find(line, position) if runs and line else -1
            offsets.append(found)
            if found >= 0:
                position = found + len(line)
        height = len(lines) * leading
        if not allow_split and height <= bottom - top and cursor + height > bottom:
            new_page()
        remaining = list(zip(lines, offsets))
        while remaining:
            count = min(len(remaining), int((bottom - cursor) / leading))
            if count < 1:
                new_page()
                continue
            chunk, remaining = remaining[:count], remaining[count:]
            assert page is not None
            writer = pymupdf.TextWriter(page.rect)
            start = cursor
            for line, offset in chunk:
                writer.append(pymupdf.Point(x, cursor + size), line, font=font, fontsize=size)
                index = 0
                while offset >= 0 and index < len(line):
                    number = target[offset + index]
                    stop = index + 1
                    while stop < len(line) and target[offset + stop] == number:
                        stop += 1
                    if number >= 0:
                        x0 = x + text_width(line[:index], size)
                        x1 = x0 + text_width(line[index:stop], size)
                        place_link(pymupdf.Rect(x0, cursor, x1, cursor + leading), link_ranges[number][2])
                        page.draw_line(pymupdf.Point(x0, cursor + size + 2.2),
                                       pymupdf.Point(x1, cursor + size + 2.2),
                                       color=muted, width=0.45)
                    index = stop
                cursor += leading
            writer.write_text(page, color=color)
            if link:
                width = min(right - x, max(text_width(line, size) for line, _ in chunk))
                rect = pymupdf.Rect(x, start, x + width, cursor)
                place_link(rect, link)
                if not link.startswith("#"):
                    for row, (line, _) in enumerate(chunk):
                        y = start + row * leading + size + 2.2
                        page.draw_line(pymupdf.Point(x, y), pymupdf.Point(x + text_width(line, size), y),
                                       color=muted, width=0.45)
            if remaining:
                new_page()
        return True

    def new_page():
        nonlocal page, cursor
        page = document.new_page(width=page_width, height=page_height)
        page.draw_line(pymupdf.Point(left, 790), pymupdf.Point(right, 790),
                       color=REPORT_RULE, width=0.5)
        footer = pymupdf.TextWriter(page.rect)
        footer.append(pymupdf.Point(left, 811), style["footer"], font=font, fontsize=sizes["footer"])
        footer.write_text(page, color=muted)
        cursor = top

    def text_and_links(value: str) -> tuple[str, list[tuple[str, str]]]:
        display, links = _inline_runs(value)
        return display, [(display[start:end], url) for start, end, url in links]

    def only_a_link(value: str) -> bool:
        """Whether this whole value is one link, so its label needs painting once.

        `add_block` has always skipped the inline copy in that case. The two
        table paths below did not, which is why a directory column holding
        nothing but `[打开职位](…)` came out as dead text AND a clickable
        duplicate beneath it — on exactly the layout report-writing.md asks for.
        """
        # A trailing full stop is ordinary authoring, in either script, and it
        # must not send the cell back to the duplicate path. Only closing
        # punctuation is shed: anything else after the link is real prose that
        # still has to be painted.
        stripped = value.strip().rstrip("。．.,，、;；:：!！?？ \t")
        return bool(_MD_LINK.fullmatch(stripped) or _RAW_ANGLE_URL.fullmatch(stripped))

    def links_in_place(lines: list[str], runs):
        """Split a block's links into those linked where printed and the rest."""
        display, link_ranges = runs
        external = [item for item in link_ranges if not item[2].startswith("#")]
        spans, position = [], 0
        for line in lines:
            found = display.find(line, position) if line else -1
            if found >= 0:
                spans.append((found, found + len(line)))
                position = found + len(line)
        kept, below = [], []
        for start, end, url in link_ranges:
            whole = any(a <= start and end <= b for a, b in spans)
            if whole and (url.startswith("#") or len(external) == 1):
                kept.append((start, end, url))
            else:
                below.append((display[start:end], url))
        return (display, kept), below

    def add_block(value: str, size: float, color: tuple[float, float, float], gap: float,
                  allow_split: bool = False, indent: float = 0,
                  leading: float | None = None) -> bool:
        nonlocal cursor
        leading = leading or size * 1.35
        # A list item that is nothing but a link (a contents entry) is a
        # standalone link too: painting `- 结论` and then a clickable `结论`
        # under it printed every contents entry twice.
        standalone_link = only_a_link(value) or (
            value.startswith("- ") and only_a_link(value[2:]))
        if standalone_link:
            for label, url in text_and_links(value)[1]:
                link_label = label if url.startswith("#") else f"{style['link']}{label}"
                if not write_lines(wrap(link_label, sizes["contents"], right - left - indent),
                                   left + indent, sizes["contents"], ink, 14.5, url):
                    return False
                cursor += 3
            return True
        # A link inside prose is clickable where it is printed. It keeps a
        # line of its own beneath the paragraph in two cases only: its label
        # wrapped (one link, one target), or the paragraph holds several
        # postings, which are told apart and clicked more easily as a list.
        # Until 1.6.0 every external link was printed twice, so a paragraph
        # with one link ran a line longer and read as two things.
        runs = _inline_runs(value)
        lines = wrap(runs[0], size, right - left - indent)
        runs, below = links_in_place(lines, runs)
        if not write_lines(lines, left + indent, size, color, leading,
                           allow_split=allow_split, runs=runs):
            return False
        cursor += gap
        for label, url in below:
            link_label = label if url.startswith("#") else f"{style['link']}{label}"
            if not write_lines(wrap(link_label, sizes["contents"], right - left - indent),
                               left + indent, sizes["contents"], ink, 14.5, url):
                return False
            cursor += 3
        return True

    def entry_start_height(title: str) -> float:
        title_display, _ = text_and_links(title)
        return len(wrap(title_display, sizes["subheading"], right - left)) * 17 + 36

    def add_entry(title: str, fields: list[tuple[str, str]]) -> bool:
        """Flow a wide table entry as labeled paragraphs, without a card frame."""
        nonlocal cursor
        if cursor + entry_start_height(title) > bottom:
            new_page()
        if not add_block(title, sizes["subheading"], ink, 4):
            return False
        for label, value in fields:
            prefix = f"{_inline_runs(label)[0]}{style['separator']}"
            if only_a_link(value):
                # The field label already says what the link is, so paint one
                # clickable `原链接：打开职位` instead of that line plus a
                # `链接：打开职位` copy of it.
                for link_label, url in text_and_links(value)[1]:
                    if not write_lines(wrap(f"{prefix}{link_label}", body, right - left),
                                       left, body, ink, body_leading, url):
                        return False
                    cursor += 3
                continue
            display, link_ranges = _inline_runs(value)
            shift = len(prefix)
            runs = (prefix + display,
                    [(a + shift, b + shift, url) for a, b, url in link_ranges])
            lines = wrap(runs[0], body, right - left)
            runs, below = links_in_place(lines, runs)
            if not write_lines(lines, left, body, ink, body_leading, runs=runs):
                return False
            cursor += 4
            for link_label, url in below:
                if not write_lines(wrap(f"{style['link']}{link_label}", sizes["contents"], right - left),
                                   left, sizes["contents"], ink, 14.5, url):
                    return False
                cursor += 3
        cursor += 6
        return True

    def table_layout(header, rows):
        """Use the same wrapped cell heights for lookahead and painting."""
        # Width follows content: a column of two-word labels beside a column of
        # sentences used to get the same third of the page, so the labels sat
        # in white space and the sentences wrapped into a tall ribbon.
        longest = [max([len(text_and_links(header[col])[0])]
                       + [len(text_and_links(row[col])[0]) for row in rows])
                   for col in range(len(header))]
        weights = [min(max(length, 6), 60) ** 0.6 for length in longest]
        floor = 0.16 if len(header) > 2 else 0.24
        fractions = [max(weight / sum(weights), floor) for weight in weights]
        widths = [fraction / sum(fractions) * (right - left) for fraction in fractions]

        def cell_data(values):
            cells = []
            for value, width in zip(values, widths):
                if only_a_link(value):
                    # A cell that is nothing but a link is the clickable line alone.
                    cells.append([(wrap(f"{style['link']}{label}", table_size, width - 12), url, None)
                                  for label, url in text_and_links(value)[1]])
                    continue
                runs = _inline_runs(value)
                lines = wrap(runs[0], table_size, width - 12)
                runs, below = links_in_place(lines, runs)
                cells.append([(lines, None, runs)] + [
                    (wrap(f"{style['link']}{label}", table_size, width - 12), url, None)
                    for label, url in below])
            return cells

        header_cells = cell_data(header)
        prepared = [cell_data(row) for row in rows]
        return widths, header_cells, prepared, [table_row_height(cells) for cells in prepared]

    def table_row_height(cells):
        return max(sum(len(lines) * table_leading for lines, _, _ in entries)
                   for entries in cells) + 10

    def table_start_height(block: list[str], available: float) -> float:
        rows = [_table_cells(line) for line in block]
        if len(rows) < 3 or not _is_table_rule(rows[1]):
            display, _ = text_and_links(" | ".join(rows[0]))
            return len(wrap(display, body, right - left)) * body_leading
        header, rows = rows[0], [row for row in rows[2:] if len(row) == len(rows[0])]
        if not rows:
            return 0
        if len(header) > 4:
            return entry_start_height(" — ".join(piece for piece in rows[0][:2] if piece))
        _, header_cells, _, heights = table_layout(header, rows)
        start = table_row_height(header_cells) + heights[0]
        if start > available:
            return entry_start_height(rows[0][0])
        # The renderer keeps the final two rows together when they fit. At
        # the start of a two-row table the heading must reserve that pair too.
        if len(rows) == 2 and start + heights[1] <= available:
            start += heights[1]
        return start

    def add_table(block: list[str], keep_heading: bool = False) -> bool:
        nonlocal cursor
        rows = [_table_cells(line) for line in block]
        if len(rows) < 3 or not _is_table_rule(rows[1]):
            return all(add_block(" | ".join(row), body, ink, 6, leading=body_leading) for row in rows)
        header, rows = rows[0], rows[2:]
        rows = [row for row in rows if len(row) == len(header)]
        if len(header) > 4:
            for row in rows:
                # Preserve the employer/role boundary in wide-table entries.
                title = " — ".join(piece for piece in row[:2] if piece)
                fields = [(label, value) for label, value in zip(header[2:], row[2:]) if value]
                if not add_entry(title, fields):
                    return False
            return True

        widths, header_cells, prepared, heights = table_layout(header, rows)
        header_height = table_row_height(header_cells)

        def draw_row(cells, heading=False):
            nonlocal cursor
            assert page is not None
            start, height, x = cursor, table_row_height(cells), left
            for entries, width in zip(cells, widths):
                cursor = start + 5
                for lines, url, runs in entries:
                    if not write_lines(lines, x + 6, table_size, muted if heading else ink,
                                       table_leading, url, runs=runs):
                        return False
                x += width
            cursor = start + height
            # One rule under the column labels and none between rows: the
            # space between rows separates them, and a line under every row
            # made a page of stripes (user report, 2026-11-20).
            if heading:
                page.draw_line(pymupdf.Point(left, cursor), pymupdf.Point(right, cursor),
                               color=REPORT_RULE, width=0.6)
            return True

        complete_height = header_height + sum(heights)
        if (not keep_heading and len(rows) <= 2 and complete_height <= (bottom - top) / 2
                and cursor + complete_height > bottom):
            new_page()
        needs_header = True
        for row_index, (row, cells, height) in enumerate(zip(rows, prepared, heights)):
            if (height + header_height > bottom - top
                    or (keep_heading and row_index == 0 and cursor + height + header_height > bottom)):
                # Keep all evidence from an unusually tall row; fields can span pages.
                if not add_entry(row[0], list(zip(header[1:], row[1:]))):
                    return False
                needs_header = True
                continue
            tail_height = height
            if (row_index == len(rows) - 2 and height + heights[-1] + header_height <= bottom - top
                    and not (keep_heading and row_index == 0
                             and cursor + height + heights[-1] + header_height > bottom)):
                tail_height += heights[-1]
            if cursor + tail_height + (header_height if needs_header else 0) > bottom:
                new_page()
                needs_header = True
            if needs_header:
                if not draw_row(header_cells, heading=True):
                    return False
                needs_header = False
            if not draw_row(cells):
                return False
        cursor += 8
        return True

    def add_callout(paragraphs: list[str]) -> bool:
        """A quoted block is ordinary text set in from the margin."""
        return all(add_block(text, body, ink, 6, leading=body_leading, indent=14)
                   for text in paragraphs)

    try:
        pdf.unlink(missing_ok=True)
        new_page()
        lines, index = list(_report_lines(md.read_text(encoding="utf-8"))), 0
        after_heading = after_title = False
        while index < len(lines):
            raw_line, literal = lines[index]
            line = raw_line.strip()
            index += 1
            if literal:
                if not write_lines(wrap(raw_line, body, right - left, literal=True),
                                   left, body, ink, body_leading, allow_split=after_heading):
                    return False, "report code block does not fit on a page"
                after_heading = after_title = False
                continue
            if not line:
                cursor += 2
                continue
            if line.startswith("|"):
                table = [line]
                while (index < len(lines) and not lines[index][1]
                       and lines[index][0].strip().startswith("|")):
                    table.append(lines[index][0].strip())
                    index += 1
                if not add_table(table, keep_heading=after_heading):
                    return False, "report block does not fit on a page"
                after_heading = after_title = False
                continue
            if line == ">" or line.startswith("> "):
                quote = [line[2:].strip()] if line[2:].strip() else []
                while (index < len(lines) and not lines[index][1]
                       and (lines[index][0].strip() == ">" or lines[index][0].strip().startswith("> "))):
                    piece = lines[index][0].strip()[2:].strip()
                    if piece:
                        quote.append(piece)
                    index += 1
                if quote and not add_callout(quote):
                    return False, "report block does not fit on a page"
                after_heading = after_title = False
                continue
            options = {"leading": body_leading}
            if line.startswith("# "):
                value, size, gap, options = line[2:], sizes["title"], 8, {}
            elif line.startswith("## "):
                value, size, gap, options = line.lstrip("# "), sizes["heading"], 6, {}
            elif line.startswith("### "):
                value, size, gap, options = line.lstrip("# "), sizes["subheading"], 4, {}
            elif line.startswith(("- ", "* ")):
                value, size, gap = line[2:], body, 3
                options = {"leading": body_leading, "indent": 13}
            else:
                value, size, gap = line, body, 6
            color = ink
            if after_title and not line.startswith(("#", "- ", "* ")) and _META_LINE.search(line) \
                    and not re.search(r"[。！？]|[.!?](?:\s|$)", line):
                # `2026年9月11日｜北京｜…` under the title is a dateline, not a sentence.
                size, color, gap, options = sizes["meta"], muted, 8, {"leading": sizes["meta"] * 1.4}
            if line.startswith("#"):
                heading_text, _ = text_and_links(value)
                if line.startswith("## ") and cursor > top:
                    cursor += 12
                elif line.startswith("### ") and cursor > top:
                    cursor += 4
                heading_height = len(wrap(heading_text, size, right - left)) * size * 1.35
                rule_height = 0
                # The writer normally keeps a paragraph together. Reserve its
                # actual height before painting the heading, or it can move to
                # the next page alone despite the old two-line reservation.
                following_height, blank_height = 2 * body_leading, 0
                for next_index in range(index, len(lines)):
                    next_line, next_literal = lines[next_index]
                    next_line = next_line.strip()
                    if not next_line:
                        blank_height += 2
                        continue
                    if not next_literal and next_line.startswith("|"):
                        table = []
                        while (next_index < len(lines) and not lines[next_index][1]
                               and lines[next_index][0].strip().startswith("|")):
                            table.append(lines[next_index][0].strip())
                            next_index += 1
                        following_height = table_start_height(
                            table, bottom - top - heading_height - gap - rule_height - blank_height)
                    elif not next_literal and not next_line.startswith("#"):
                        if next_line.startswith(("- ", "* ", "> ")):
                            next_line = next_line[2:]
                        next_text, _ = text_and_links(next_line)
                        following_height = len(wrap(next_text, body, right - left)) * body_leading
                    break
                reserved = heading_height + gap + rule_height + blank_height
                if reserved + following_height > bottom - top:
                    following_height = 2 * body_leading  # A long first paragraph must flow.
                if cursor + reserved + following_height > bottom:
                    new_page()
                slug = re.sub(r"[^\w -]", "", heading_text.lower()).replace(" ", "-")
                duplicate = anchor_counts.get(slug, 0)
                anchor_counts[slug] = duplicate + 1
                anchor = f"{slug}-{duplicate}" if duplicate else slug
                anchors[anchor] = (page.number, cursor)
                if line.startswith("## "):
                    outline.append([1, heading_text, page.number + 1])
            if line.startswith(("- ", "* ")) and not only_a_link(value):
                # The mark sits in the margin of its item, so wrapped lines
                # align with the text and not with the mark.
                if cursor + body_leading > bottom:
                    new_page()
                mark = pymupdf.TextWriter(page.rect)
                mark.append(pymupdf.Point(left + 2, cursor + body), "•", font=font, fontsize=body)
                mark.write_text(page, color=ink)
            elif line.startswith(("- ", "* ")):
                value, options = "- " + value, {}
            if not add_block(value, size, color, gap,
                             allow_split=after_heading and not line.startswith("#"), **options):
                return False, "report block does not fit on a page"
            after_title = line.startswith("# ")
            after_heading = line.startswith("#")
        for number, current_page in enumerate(document, start=1):
            footer = pymupdf.TextWriter(current_page.rect)
            label = style["page"].format(number=number)
            footer.append(pymupdf.Point(right - text_width(label, sizes["footer"]), 811), label,
                          font=font, fontsize=sizes["footer"])
            footer.write_text(current_page, color=muted)
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

    On parser failure keep the original text, so loss detection fails closed,
    minus the destinations of Markdown links: `[结论](#结论)` paints 结论 once,
    never the `#结论` after it. Without pandoc (CI, many users) those targets
    were counted as text the PDF had to show; a contents block of CJK anchors
    then read back 58 of 77 characters and the PDF was deleted as lossy.
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
    return _MD_LINK.sub(r"\1", source)


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


def _notdef_hint(source: str) -> str:
    """Name the source characters most likely behind a U+FFFF finding.

    XeTeX records every glyph its font lacks as U+FFFF, so the finding alone
    does not say which character to replace. Symbols are the usual cause.
    """
    suspects = sorted({char for char in source if ord(char) > 0x7f and not _CJK.match(char)
                       and (unicodedata.category(char)[0] == "S"
                            or unicodedata.category(char) in ("Co", "Cn", "Cf")
                            or ord(char) > 0xffff)})
    named = ", ".join(f"U+{ord(char):04X} {char}" for char in suspects[:12])
    return ("U+FFFF marks a character the PDF font could not draw (it shows as a box)"
            + (f"; likely source characters: {named}" if named else "")
            + ". Replace them with words or a covered character, then deliver again")


def _verify_pdf(pdf: pathlib.Path, source: str, needs_cjk: bool,
                link_source: str | None = None) -> tuple[bool, str]:
    """Reject a rendered PDF that lost text or painted broken glyphs."""
    problems = glyph_findings(pdf)
    if problems:
        pdf.unlink(missing_ok=True)
        if any("U+FFFF" in problem for problem in problems):
            problems.append(_notdef_hint(source))
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
               font: str | dict | None = None) -> tuple[bool, str]:
    """Use portable fonts by default; bind source/PDF bytes before visual review."""
    from render_report import render_with
    result = render_with(md, pdf, lambda source, target: _render_pdf(source, target, font))
    if not result[0]:
        # A refused export must not leave last round's PDF in the client folder.
        # render_with's fresh destination protects the private render operation;
        # this public entry point retains the existing stale-output refusal.
        pdf.unlink(missing_ok=True)
        pdf.with_suffix(".tex").unlink(missing_ok=True)
    return result


def _render_pdf(md: pathlib.Path, pdf: pathlib.Path,
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
        # The labels follow the narrative (report_language, which also names the
        # delivered files); the font above still covers every quoted glyph.
        language_style = _REPORT_STYLES[report_language(link_source)]
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


def _brief_page_problem(pdf: pathlib.Path, source: pathlib.Path | None = None) -> str:
    """Keep the quick reference to one page; retain the full walk-back appendix."""
    try:
        import pymupdf
        with pymupdf.open(pdf) as document:
            pages = document.page_count
            page_texts = [page.get_text() for page in document]
    except Exception as exc:
        return f"INTERVIEW_BRIEF_PAGES_UNVERIFIED: {exc}"
    problem = (f"INTERVIEW_BRIEF_TOO_LONG: rendered {pages} pages; condense repeated "
               "wording to one page while retaining claim sources, honest gaps and "
               "reviewer questions. Do not shrink the text.")
    refusal = problem if pages > 1 else ""
    if source is None or not source.is_file():
        return refusal
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return f"INTERVIEW_BRIEF_PAGES_UNVERIFIED: {exc}"
    marker = re.search(r"^## Walk-back list[ \t]*$", text, re.M)
    if marker is None:
        return refusal
    import check_mock
    entries = check_mock.walkback_entries(text)
    if not entries or any(not entry[field] for entry in entries
                          for field in ("quote", "softened", "defect", "transcript", "status")):
        return refusal
    rest = text[marker.end():]
    if pages > 1 and re.search(r"^##\s+", rest, re.M):
        return problem  # The appendix must follow all quick-reference content.
    import layout_requirements
    missing = layout_requirements.report_text_problems(text, page_texts)
    link_problem = _pdf_link_problem(pdf, text)
    if missing or link_problem:
        return f"INTERVIEW_BRIEF_CONTENT_MISMATCH: {link_problem or missing[0]}"
    # Measure the actual PDF's first page, including custom fonts/layouts.
    # A newly rendered one-page prefix cannot vouch for a cached PDF's layout.
    if layout_requirements.report_text_problems(text[:marker.start()], page_texts[:1]):
        return problem
    return ""


def _delivery_sources(workspace: pathlib.Path, make_pdf: bool,
                      include_applications: bool | None
                      ) -> tuple[bool, list[pathlib.Path]]:
    """(applying, the workspace files deliver() copies to the client folder)."""
    # In apply the application documents are the product, so a missing CV or
    # letter PDF leaves the delivery incomplete. Elsewhere they are existing
    # source documents copied on explicit request: say what is missing, no more.
    mode = journal.current_mode(workspace)
    applying = mode not in {"discover", "assess", "interview", "prepare"}
    if include_applications is None:
        include_applications = applying
    # Interview mode appends its walk-back list to the brief, so the copy apply
    # delivered is out of date the moment the round closes. Measured in the
    # 2026-10-29 simulation: all three debriefs went out while 面试准备/ still
    # held the brief without the walk-backs the candidate had just agreed to.
    also = frozenset({"interview-brief"}) if mode == "interview" else frozenset()
    return applying, [p for p in sorted(workspace.rglob("*"))
                      if p.is_file() and is_deliverable(p, workspace, include_applications, also)
                      and not (make_pdf and p.name == "report.pdf")]


def deliver(workspace: pathlib.Path, dest: pathlib.Path, slug: str,
            make_pdf: bool = True, include_applications: bool | None = None,
            notices: list[str] | None = None
            ) -> tuple[list[pathlib.Path], list[str]]:
    """Copy and render into `dest`. Returns (written, notes).

    `notes` make the delivery incomplete. `notices`, when a list is passed,
    collects things the client should be told that do not.
    """
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
    notices = [] if notices is None else notices
    fonts = {}
    report_font, font_origin = None, ""
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
                report_font, font_origin = meta["cjk_font"], name
                break
    applying, sources = _delivery_sources(workspace, make_pdf, include_applications)

    # Validate all requested Word files before copying anything. This also covers
    # hand-authored reports/statements and formatting split across Word runs.
    word_problems = [problem for src in sources if src.suffix == ".docx"
                     for problem in docx_findings(src)]
    if word_problems:
        return [], word_problems

    claimed: dict = {}
    pdf_landed: set[str] = set()       # stems whose PDF reached the client folder
    text_copies: dict[str, list[pathlib.Path]] = {}  # application stem -> .md/.docx copies
    for src in sources:
        target = dest / client_path(src.relative_to(workspace), workspace)
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
            if src.stem == "interview-brief" and (problem := _brief_page_problem(
                    src, src.with_suffix(".md"))):
                problems.append(problem)
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
        if src.suffix == ".pdf":
            pdf_landed.add(src.stem)
        elif src.stem not in REPORT_RENDERED:
            text_copies.setdefault(src.stem, []).append(target)
        if (make_pdf and src.suffix == ".md" and src.stem in REPORT_RENDERED
                and (src.name == "report.md" or not src.with_suffix(".pdf").exists())):
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
                font = None
                if glyphs:
                    # `meta.cjk_font` lives in the CV's profile. The report
                    # honours it where it can — through pandoc + XeTeX — but a
                    # CV typography setting must not make the report depend on
                    # a toolchain it otherwise does not need. Without that
                    # toolchain the bundled renderer runs, and says so.
                    if isinstance(report_font, str) and _tex_report_path_available():
                        font = report_font
                    else:
                        if report_font is not None:
                            notices.append(_font_not_applied(pdf.name, report_font, font_origin))
                        # Covered bundled glyphs keep delivery independent of a
                        # Tectonic font probe.
                        if not _portable_report_style(source):
                            if glyphs not in fonts:
                                fonts[glyphs] = pick_cjk_font(source)
                            font = fonts[glyphs]
                ok, why = render_pdf(src, pdf, font)
                if ok and src.stem == "interview-brief" and (why := _brief_page_problem(pdf, src)):
                    pdf.unlink(missing_ok=True)
                    ok = False
            except OSError as exc:
                ok, why = False, str(exc)
            if ok:
                written.append(pdf)
                pdf_landed.add(src.stem)
            else:
                notes.append(f"{pdf.name}: {why}")

    # An application document whose own renderer produced no PDF ships as
    # Markdown/Word, and the reason is said instead of a report-styled stand-in.
    if make_pdf:
        for stem, copies in text_copies.items():
            if stem in pdf_landed or (workspace / f"{stem}.pdf").is_file():
                continue  # delivered, or refused above with its own reason
            pdf = copies[0].with_suffix(".pdf")
            # No PDF from an earlier round may stay beside this round's text.
            pdf.unlink(missing_ok=True)
            pdf.with_suffix(".tex").unlink(missing_ok=True)
            shipped = " and ".join(path.name for path in copies)
            how = APPLICATION_PDF_SOURCES.get(stem)
            if how and applying:
                notes.append(
                    f"{pdf.name}: not produced — the workspace has no {stem}.pdf, and "
                    f"deliver.py never converts {stem}.md to PDF (that would bypass the "
                    f"renderer's layout and page checks). {shipped} delivered. To add "
                    f"the PDF, {how}, then deliver again; use --no-pdf only when the "
                    "client asked for no PDF.")
            else:
                notices.append(
                    f"NOTICE_PDF_NOT_PRODUCED: {pdf.name}: the workspace has no {stem}.pdf, "
                    f"so only {shipped} was delivered; deliver.py does not convert "
                    "application documents to PDF. If a PDF is needed, "
                    + (how if how else "export it from the Word version") + ".")
    return written, notes


def _tex_report_path_available() -> bool:
    """Whether the pandoc + XeTeX report path is installed at all."""
    return bool(shutil.which("pandoc")) and any(shutil.which(e) for e in REPORT_ENGINES)


def _font_not_applied(pdf_name: str, font, origin: str) -> str:
    if not isinstance(font, str):
        return (f"NOTICE_REPORT_FONT_NOT_APPLIED: {pdf_name}: meta.cjk_font in {origin} "
                f"is {type(font).__name__}, not a font name; the report PDF uses the "
                "bundled fonts.")
    return (f"NOTICE_REPORT_FONT_NOT_APPLIED: {pdf_name}: meta.cjk_font {font!r} in "
            f"{origin} reaches a report only through pandoc + tectonic/xelatex, which "
            "this machine lacks, so the report PDF uses the bundled fonts; CV and "
            "letter renderers still use that font. If the client asked for this font "
            "in the report itself, prepare that toolchain (references/agent-setup.md) "
            "and deliver again, or tell the client which font the report uses.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", required=True, type=pathlib.Path)
    ap.add_argument("--to", type=pathlib.Path, default=None,
                    help="destination directory (default: a workspace-named folder "
                         "under the delivery root saved by setup or doctor)")
    ap.add_argument("--no-pdf", action="store_true",
                    help="do not render new PDFs; existing deliverable files are still copied")
    ap.add_argument("--include-applications", action="store_true",
                    help="also copy application documents during a non-apply consultation, only when explicitly requested")
    args = ap.parse_args(argv)

    ws = args.workspace.expanduser().resolve()
    if not ws.is_dir():
        print(f"DELIVER_NO_WORKSPACE: {ws} is not a directory", file=sys.stderr)
        return 2

    try:
        if args.to:
            dest = args.to.expanduser().resolve()
        else:
            configured = read_runtime(default_root()).get("delivery_root")
            root = pathlib.Path(configured).expanduser() if configured else DEFAULT_ROOT
            dest = (root / ws.name).resolve()
    except (OSError, TypeError, ValueError) as exc:
        print(f"DELIVER_DEST_UNAVAILABLE: {exc}. Run doctor.py, or use --to to choose "
              "a writable folder.", file=sys.stderr)
        return 2
    if dest == ws or ws in dest.parents:
        print(f"DELIVER_DEST_INSIDE_WORKSPACE: {dest} is the workspace or inside "
              "it; delivering there would copy the round into itself",
              file=sys.stderr)
        return 2

    if not (ws / "report.md").is_file():
        print("DELIVER_REPORT_REQUIRED: author report.md answering the client question", file=sys.stderr)
        return 2

    try:
        report_text = (ws / "report.md").read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"DELIVER_REPORT_UNREADABLE: {exc}", file=sys.stderr)
        return 2
    try:
        corpus = lint_no_prediction.capture_corpus(ws)
        mode = journal.current_mode(ws)
    except (OSError, UnicodeError) as exc:
        print(f"DELIVER_WORKSPACE_UNREADABLE: {exc}; nothing was copied", file=sys.stderr)
        return 2
    findings = lint_no_prediction.scan_text(report_text, "report.md", corpus)
    if findings:
        print("DELIVER_REPORT_PREDICTION: " + "\n".join(findings), file=sys.stderr)
        return 2

    discover_problem = _discover_handoff_problem(ws)
    if discover_problem:
        print(f"DELIVER_DISCOVER_INCOMPLETE: {discover_problem}", file=sys.stderr)
        return 2

    ok, why = writable(dest)
    if not ok:
        print(f"DELIVER_DEST_UNWRITABLE: cannot write to {dest}: {why}. Run doctor.py "
              "to choose a new default, or specify a writable folder with --to. "
              "No files were copied.", file=sys.stderr)
        return 2

    include_applications = True if args.include_applications else None
    try:
        deliveries = read_manifest(dest)
        foreign = foreign_files(dest, deliveries, ws, not args.no_pdf, include_applications)
        folder, previous, displaced = choose_folder(
            dest, deliveries, ws, mode, foreign,
            lambda own: unowned_targets(dest / own["folder"] if own["folder"] else dest, own,
                                        dest, ws, not args.no_pdf, include_applications))
    except ManifestError as exc:
        print(f"DELIVER_MANIFEST_UNREADABLE: {exc}. It records which workspace wrote "
              "each file here, so nothing was copied rather than risk overwriting "
              "another workspace's documents. Move that file aside after checking "
              "the folder, or pass a new --to.", file=sys.stderr)
        return 2
    out = dest / folder if folder else dest
    twins = (legacy_twins(dest, deliveries, ws, not args.no_pdf, include_applications)
             if not folder else [])

    notices: list[str] = []
    written, notes = deliver(ws, out, ws.name, make_pdf=not args.no_pdf,
                             include_applications=include_applications,
                             notices=notices)
    if not written:
        for note in notes:
            print(f"DELIVER_LAYOUT_OR_INPUT_REFUSED: {note}", file=sys.stderr)
        print(f"DELIVER_NOTHING_TO_COPY: {ws} holds no deliverable files",
              file=sys.stderr)
        return 2
    if displaced is not None:
        if "unaccounted" in displaced:
            held = ("client documents no delivery manifest accounts for "
                    f"({', '.join(displaced['unaccounted'])}: left by an older deliver.py "
                    "or placed by hand, so possibly another workspace's)")
        else:
            held = (f"the documents delivered from workspace "
                    f"{displaced.get('workspace_name') or displaced['workspace']} "
                    f"({displaced['mode']} mode)")
        notices.insert(0, (
            f"NOTICE_SEPARATE_FOLDER: {dest} already holds {held}, so this delivery went "
            f"to the subfolder {folder}/ instead of overwriting them. Quote both folders "
            "to the user."))
    for rel in twins:
        path = dest / rel
        try:
            path.unlink()
            if path.suffix == ".pdf":
                # As beside a current target: no LaTeX source of an old round stays.
                path.with_suffix(".tex").unlink(missing_ok=True)
            if not any(path.parent.iterdir()):
                path.parent.rmdir()
            notices.append(f"NOTICE_LEGACY_NAME_REPLACED: {rel} was this workspace's earlier "
                           "copy under the old Chinese name; this round's copy replaces it.")
        except OSError as exc:
            notices.append(f"NOTICE_STALE_FILE_KEPT: {rel} could not be removed: {exc}")
    notices.extend(finish_manifest(dest, deliveries, ws, mode, folder, previous, written))

    # A record, not a gate receipt: delivery decides nothing and has no verdict.
    # It exists because a hand-off that left no trace was indistinguishable from
    # one that never happened, so a composer could not tell a run that skipped
    # the last step from a run that took it.
    record = {
        "action": "delivery",
        "destination": str(out),
        "files": [q.relative_to(out).as_posix() for q in written],
        "pdf_refused": notes,
    }
    if notices:
        record["notices"] = notices
    try:
        journal.append(ws, record)
    except OSError:
        pass  # a workspace we can read but not write is not a delivery failure

    complete = not notes and (args.no_pdf or out / client_path(pathlib.Path("report.pdf"), ws) in written)
    print(f"{'Delivered' if complete else 'Incomplete delivery:'} {len(written)} file(s) to {out}")
    for p in written:
        print(f"  {p.relative_to(out)}")
    for n in notes:
        print(f"{_note_code(n)}: {n}", file=sys.stderr)
    for n in notices:
        print(n, file=sys.stderr)
    print(f"\nTell the user these files are in: {out}")
    return 0 if complete else 2


def _note_code(note: str) -> str:
    """The prefix has to name what happened.

    The list holds refused PDFs, application PDFs nobody produced, AND files
    that could not be copied at all; calling a permission error a PDF refusal
    sends the reader to the renderer.
    """
    if "not delivered" in note:
        return "NOTICE_NOT_DELIVERED"
    if "not produced" in note:
        return "NOTICE_PDF_MISSING"
    return "NOTICE_PDF_REFUSED"


if __name__ == "__main__":
    from cli_io import configure_output

    configure_output()
    sys.exit(main())
