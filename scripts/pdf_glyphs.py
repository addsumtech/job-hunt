"""Inspect painted glyph IDs: a valid ToUnicode map can hide missing glyphs."""
from pathlib import Path
import unicodedata


def glyph_findings(path) -> list[str]:
    try:
        import pymupdf
        missing = set()
        with pymupdf.open(path) as document:
            for page in document:
                for span in page.get_texttrace():
                    if span.get("type") == 3:  # invisible OCR/search layer
                        continue
                    for codepoint, glyph, *_ in span["chars"]:
                        char = chr(codepoint)
                        if glyph == 0 and not char.isspace() and not unicodedata.category(char).startswith("C"):
                            missing.add(char)
        if missing:
            return [f"MISSING_PDF_GLYPHS: {Path(path).name}: " +
                    ", ".join(f"U+{ord(c):04X}" for c in sorted(missing))]
        return []
    except Exception as exc:
        return [f"PDF_GLYPHS_UNVERIFIED: {Path(path).name}: {exc}"]
