"""Measure a final document against requirements read from its reference.

These checks supplement, never replace, page-by-page visual comparison.
"""
from __future__ import annotations

import html
import math
import re
import unicodedata
import zipfile
from xml.etree import ElementTree as ET

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_REF_LINK = re.compile(r"\[([^\]]+)\]\[[^\]]*\]")
_REF_DEF = re.compile(r"^ {0,3}\[(?!\^)[^\]]+\]:\s*\S")
_FOOTNOTE_DEF = re.compile(r"^ {0,3}\[\^[^\]]+\]:\s*")
_FOOTNOTE_REF = re.compile(r"\[\^[^\]]+\]")
_AUTOLINK = re.compile(r"<(https?://[^\s>]+)>")
_TAG = re.compile(r"</?[A-Za-z][^>]*>")
_HEADING = re.compile(r"^ {0,3}#{1,6}\s+")
_LIST = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?")
_QUOTE = re.compile(r"^\s*>\s?")
_NUMBERING = re.compile(r"^\s*\d+(?:\.\d+)*[.)、]?\s+")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*$")
_GAP = r"\d{0,4}"     # a footnote number or superscript printed inside a line
_PAGE_REACH = 300     # letters/digits of page furniture tolerated around a page break
_SHORT = 3            # shorter cells ("是", "1", "No") are required but never move the cursor


# Characters that occupy a line without printing: whitespace, format characters
# (ZWSP, BOM) and the blank "filler" letters used to pad a line.
_BLANK_LETTERS = {"\u2800", "\u3164", "\uffa0", "\u115f", "\u1160"}


def is_ink(char):
    """Whether a text character paints anything on the page."""
    return not (char.isspace() or char in _BLANK_LETTERS
                or unicodedata.category(char) in ("Cf", "Cc", "Zs", "Zl", "Zp"))


def _ink_key(text):
    """Letters and digits only: layout, hyphenation, ligatures and quotes vary."""
    return "".join(ch for ch in unicodedata.normalize("NFKC", text).casefold() if ch.isalnum())


def _fragments(text):
    """Ink keys of visible inline text, split where a footnote number prints."""
    text = _LINK.sub(r"\1", _REF_LINK.sub(r"\1", _AUTOLINK.sub(r"\1", _IMAGE.sub(" ", text))))
    text = html.unescape(_TAG.sub(" ", text))
    return [k for k in (_ink_key(part) for part in _FOOTNOTE_REF.split(text)) if k]


def _report_blocks(markdown):
    """Visible report.md blocks in reading order: para, note, row or header."""
    lines = _COMMENT.sub("", markdown).splitlines()
    blocks, para, fence = [], None, None

    def flush():
        nonlocal para
        if para is not None:
            blocks.append(para)
        para = None

    for index, line in enumerate(lines):
        opening = _FENCE.match(line)
        if fence:
            if opening and opening[1][0] == fence[0] and len(opening[1]) >= len(fence):
                fence = None
            continue
        if opening:
            flush()
            fence = opening[1]
            continue
        if not line.strip() or _REF_DEF.match(line) or ("|" in line and _TABLE_SEP.match(line)):
            flush()
            continue
        if line.count("|") >= 2:
            flush()
            following = lines[index + 1] if index + 1 < len(lines) else ""
            kind = "header" if "|" in following and _TABLE_SEP.match(following) else "row"
            cells = line.strip().strip("|").split("|")
            blocks.append({"kind": kind, "text": line.strip(), "cells": [_fragments(c) for c in cells]})
            continue
        note, heading, item = _FOOTNOTE_DEF.match(line), _HEADING.match(line), _LIST.match(line)
        if note or heading or item:
            flush()
            text = (line[note.end():] if note else _NUMBERING.sub("", line[heading.end():])
                    if heading else line[item.end():])
            para = {"kind": "note" if note else "para", "text": text}
            if heading:
                flush()
            continue
        line = _QUOTE.sub("", line)
        if para is None:
            para = {"kind": "para", "text": line}
        else:
            para["text"] += " " + line
    flush()
    for block in blocks:
        if block["kind"] in ("para", "note"):
            block["fragments"] = _fragments(block["text"])
    return [b for b in blocks if b.get("fragments") or any(b.get("cells", []))]


def report_text_problems(markdown, pages):
    """Current report.md text the PDF does not carry, in order, as snippets.

    ``pages`` holds each PDF page's extracted text, one PDF line per newline.
    Paragraphs, headings and list items must occupy whole PDF lines, allowing
    only a list number, digits or another Markdown label beside them, so an
    edit that removed words ("Do not apply" -> "Apply") is caught. Table body
    rows must appear in order; a cell equal to the one above it may be a merged
    cell. Any block may cross a page break with furniture (page numbers,
    headers, a repeated table header) in between. Header rows are optional:
    card layouts omit them. Known limit: text deleted from the Markdown is not
    detected when the stale PDF still reads as whole blocks, e.g. a removed
    paragraph, and a PDF that prints link targets inline does not bind.
    """
    import bisect
    stream, spans, page_start = [], [], []
    offset = 0
    for page in pages:
        page_start.append(offset)
        for line in page.splitlines():
            key = _ink_key(line)
            if key:
                spans.append((offset, offset + len(key)))
                stream.append(key)
                offset += len(key)
    page_start.append(offset)
    stream = "".join(stream)
    line_starts = [a for a, _ in spans]
    blocks = _report_blocks(markdown)
    labels = {"".join(b["fragments"]) for b in blocks if b.get("fragments")}
    labels |= {"".join(c) for b in blocks for c in b.get("cells", []) if c}

    def beside(text):
        return not text or text.isdigit() or text in labels

    def anchored(start, end):
        at = bisect.bisect_right(line_starts, start) - 1
        until = bisect.bisect_right(line_starts, end - 1) - 1
        return (at >= 0 and until >= 0 and beside(stream[spans[at][0]:start])
                and beside(stream[end:spans[until][1]]))

    def across_breaks(start, key, breaks):
        """End of ``key`` read from ``start``, hopping page furniture at breaks."""
        same = 0
        while same < len(key) and start + same < len(stream) and stream[start + same] == key[same]:
            same += 1
        if same == len(key):
            return start + same
        if not breaks:
            return None
        # The page may end with furniture that happens to continue the text.
        for used in range(same, max(same - 8, 1), -1):
            boundary = next((b for b in page_start[1:-1] if b >= start + used), None)
            if boundary is None or boundary - (start + used) > _PAGE_REACH:
                continue
            rest = key[used:]
            resume = stream.find(rest[:8], boundary, boundary + _PAGE_REACH + 1)
            while resume >= 0:
                end = across_breaks(resume, rest, breaks - 1)
                if end is not None:
                    return end
                resume = stream.find(rest[:8], resume + 1, boundary + _PAGE_REACH + 1)
        return None

    def locate(fragments, cursor, whole):
        pattern = re.compile(_GAP.join(re.escape(f) for f in fragments))
        found, contiguous = pattern.search(stream, cursor), None
        while found:
            if not whole or anchored(found.start(), found.end()):
                contiguous = found.start(), found.end()
                break
            found = pattern.search(stream, found.start() + 1)
        key = "".join(fragments)
        if len(key) < 4 or len(pages) < 2:
            return contiguous
        # A nearer copy split by a page break wins over a later contiguous copy
        # (repeated wording, or the next paragraph saying the same thing).
        limit = contiguous[0] if contiguous else len(stream)
        lead = key[:3]  # the part before a page break may be only a few characters
        start = stream.find(lead, cursor, limit)
        while start >= 0:
            end = across_breaks(start, key, 3)
            if end is not None and (not whole or anchored(start, end)):
                return start, end
            start = stream.find(lead, start + 1, limit)
        return contiguous

    problems, cursor, above = [], 0, None
    for block in blocks:
        if block["kind"] == "header":
            above = None
            continue
        if block["kind"] == "row":
            starts = []
            for column, fragments in enumerate(block["cells"]):
                if not fragments or (above and column < len(above) and above[column] == fragments):
                    continue
                spot = locate(fragments, cursor, whole=False)
                if spot is None:
                    problems.append(" ".join(fragments))
                elif len("".join(fragments)) >= _SHORT:
                    starts.append(spot[0])
            above = block["cells"]
            if starts:
                cursor = max(starts) + 1
            continue
        above = None
        note = block["kind"] == "note"
        spot = locate(block["fragments"], 0 if note else cursor, whole=True)
        if spot is None:
            problems.append(block["text"].strip())
        elif not note:
            cursor = spot[1]
    return [p[:60] for p in problems]


def measure(ws, requirements, report=False):
    findings = []

    def fail(detail):
        findings.append("FORMAT_MISMATCH: " + detail + "; fix and render/review again")

    def close(actual, expected):
        return (type(expected) in (int, float) and math.isfinite(expected)
                and abs(actual - expected) <= 0.6)

    def font_name(value):
        # PDF subset prefixes and PostScript separators are not font changes.
        return str(value).split("+")[-1].replace("-", "").replace(" ", "").lower()

    def painted(doc):
        """(text, ink box) per span, from its non-whitespace glyphs only.

        A span's own box includes its spaces: exporters end wrapped lines with a
        trailing space past the last glyph, and NBSP-only paragraphs occupy a
        line without printing anything. Neither is text on the page. Known
        limit: text painted in the background colour is not detected.
        """
        for page in doc:
            for block in page.get_text("rawdict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        ink = [c["bbox"] for c in span["chars"] if is_ink(c["c"])]
                        if ink:
                            yield ("".join(c["c"] for c in span["chars"]).strip(),
                                   (min(b[0] for b in ink), min(b[1] for b in ink),
                                    max(b[2] for b in ink), max(b[3] for b in ink)))

    pdf = ws / ("report.pdf" if report else "cv.pdf")
    if pdf.is_file():
        try:
            import pymupdf
            with pymupdf.open(pdf) as doc:
                size = requirements.get("page_size_pt")
                if not isinstance(size, list) or len(size) != 2:
                    fail("page_size_pt must specify width and height")
                else:
                    for page in doc:
                        if not all(close(a, b) for a, b in zip(page.rect[2:], size)):
                            fail(f"page {page.number + 1} paper size")
                samples = requirements.get("text_samples")
                roles = {"title", "heading", "body"} if report else {"name", "heading", "body"}
                if not isinstance(samples, list):
                    samples = []
                if not roles <= {s.get("role") for s in samples if isinstance(s, dict)}:
                    fail("text_samples must measure " + ", ".join(sorted(roles)))
                lines = [line for page in doc for block in page.get_text("dict")["blocks"]
                         for line in block.get("lines", [])]
                minimum_bottom = requirements.get("minimum_content_bottom_pt")
                if minimum_bottom is not None:
                    if len(doc) != 1:
                        fail("minimum_content_bottom_pt requires a one-page document")
                    if type(minimum_bottom) not in (int, float) or not math.isfinite(minimum_bottom) or minimum_bottom <= 0:
                        fail("minimum_content_bottom_pt must be a positive finite number")
                    else:
                        bottom = max((box[3] for _, box in painted(doc)), default=0)
                        if bottom < minimum_bottom - .6:
                            fail(f"content ends at {bottom:.2f} pt, required at least {minimum_bottom:.2f} pt; excessive lower-page whitespace")
                for sample in samples:
                    if not isinstance(sample, dict):
                        fail("invalid text sample")
                        continue
                    needle, fonts = sample.get("text"), sample.get("fonts")
                    if not isinstance(needle, str) or not needle.strip() or not isinstance(fonts, list) or not fonts:
                        fail("every text sample needs literal text and expected fonts")
                        continue
                    matches = []
                    region = sample.get("region_pt")
                    if region is not None and (not isinstance(region, list) or len(region) != 4
                                               or any(type(v) not in (int, float) or not math.isfinite(v) for v in region)):
                        fail("region_pt must specify left, top, right, bottom")
                        continue
                    for line in lines:
                        if region is not None and not pymupdf.Rect(region).contains(pymupdf.Rect(line["bbox"])):
                            continue
                        spans = line["spans"]
                        text = "".join(s["text"] for s in spans)
                        start = text.find(needle)
                        if start < 0:
                            continue
                        offset = 0
                        for span in spans:
                            end = offset + len(span["text"])
                            if end > start and offset < start + len(needle):
                                matches.append(span)
                            offset = end
                    if not matches:
                        fail(f"sample {needle!r} missing from final PDF")
                    for span in matches:
                        if not close(span["size"], sample.get("size_pt")):
                            fail(f"{needle!r} size {span['size']:.2f} pt, expected {sample.get('size_pt')}")
                        if font_name(span["font"]) not in {font_name(f) for f in fonts}:
                            fail(f"{needle!r} font {span['font']}, expected {fonts}")
                        if "color" in sample and span["color"] != sample["color"]:
                            fail(f"{needle!r} text color")
                bounds = requirements.get("text_bounds_pt")
                if not isinstance(bounds, list) or len(bounds) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in bounds):
                    fail("text_bounds_pt must specify left, top, right, bottom")
                else:
                    for text, (x0, y0, x1, y1) in painted(doc):
                        if (x0 < bounds[0] - .6 or y0 < bounds[1] - .6
                                or x1 > bounds[2] + .6 or y1 > bounds[3] + .6):
                            fail(f"text outside required bounds: {text[:30]!r}")
        except Exception as exc:
            fail(f"cannot measure PDF: {exc}")
    elif report:
        fail("report.pdf is missing")

    docx = ws / "cv.docx"
    if not report and docx.is_file():
        try:
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            prefix = "{" + ns["w"] + "}"
            with zipfile.ZipFile(docx) as archive:
                root = ET.fromstring(archive.read("word/document.xml"))
            expected = requirements.get("docx_geometry_twips")
            keys = {"width", "height", "top", "bottom", "left", "right"}
            if not isinstance(expected, dict) or not keys <= expected.keys():
                fail("docx_geometry_twips needs paper width/height and four margins")
            else:
                for section in root.findall(".//w:sectPr", ns):
                    for key in sorted(keys):
                        node = section.find("w:pgSz" if key in {"width", "height"} else "w:pgMar", ns)
                        attr = {"width": "w", "height": "h"}.get(key, key)
                        actual = int(node.attrib[prefix + attr])
                        if actual != expected[key]:
                            fail(f"DOCX {key} {actual} twips, expected {expected[key]}")
        except Exception as exc:
            fail(f"cannot measure DOCX: {exc}")
    return findings
