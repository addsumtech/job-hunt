"""Measure a final document against requirements read from its reference.

These checks supplement, never replace, page-by-page visual comparison.
"""
from __future__ import annotations

import math
import re
import unicodedata
import zipfile
from xml.etree import ElementTree as ET

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_AUTOLINK = re.compile(r"<(https?://[^\s>]+)>")
_TAG = re.compile(r"</?[A-Za-z][^>]*>")
_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")


def _ink_key(text):
    """Letters and digits only: layout, hyphenation, ligatures and quotes vary."""
    return "".join(ch for ch in unicodedata.normalize("NFKC", text).casefold() if ch.isalnum())


def report_text_units(markdown):
    """Visible report.md text as lines and table cells, with their ink keys."""
    units, fence = [], None
    for line in _COMMENT.sub("", markdown).splitlines():
        opening = _FENCE.match(line)
        if fence:
            if opening and opening[1][0] == fence[0] and len(opening[1]) >= len(fence):
                fence = None
            continue
        if opening:
            fence = opening[1]
            continue
        line = _TAG.sub(" ", _LINK.sub(r"\1", _AUTOLINK.sub(r"\1", line)))
        for cell in (line.strip().strip("|").split("|") if line.count("|") >= 2 else [line]):
            key = _ink_key(cell)
            if len(key) >= (2 if _CJK.search(key) else 4):
                units.append((cell.strip(), key))
    return units


def missing_report_text(markdown, pdf_text):
    """Current report.md units absent from the PDF's text, in reading order.

    Binds a reviewed PDF to the Markdown it claims to render: an edited
    recommendation that was never re-rendered is absent. A merged table cell,
    a wrapped or hyphenated line and a generated contents page are not failures.
    Text deleted from the Markdown but left in the PDF is not detected here.
    """
    ink = _ink_key(pdf_text)
    return [text for text, key in report_text_units(markdown) if key not in ink]


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
        line without printing anything. Neither is text on the page.
        """
        for page in doc:
            for block in page.get_text("rawdict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        ink = [c["bbox"] for c in span["chars"] if not c["c"].isspace()]
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
