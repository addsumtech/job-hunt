"""Strict parser for the two mock-assessor output blocks.

Fail-closed, for the same reason parse_verdicts.py is: a block we can only partly read
is not a block with a few odd lines, it is an assessment that did not happen. The
caller re-dispatches the pass rather than accepting a half-read one — and in
particular, a block with neither FINDING lines nor the explicit "FINDINGS: none"
marker is an error, because silence and "nothing found" must not look the same.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

ASSESSMENT = "MOCK-ASSESSMENT-V1"
PROVENANCE = "MOCK-PROVENANCE-V1"
BLOCK_KINDS = (ASSESSMENT, PROVENANCE)

HEADER_KEYS = {
    ASSESSMENT: ("ROUND", "ROUND-TYPE", "MARKET", "FAMILY"),
    PROVENANCE: ("ROUND",),
}
ALLOWED_RECORDS = {
    ASSESSMENT: ("FINDING", "BAND", "COVERAGE", "SHAPE"),
    PROVENANCE: ("FINDING",),
}
# Exactly one free-text field per record, and it is always last, so it may contain
# the pipe character a real quote sometimes contains.
RECORD_FIELDS = {
    "FINDING": ("tag", "ref", "quote"),
    "BAND": ("dimension", "value", "ref", "quote"),
    "COVERAGE": ("status", "must_have"),
    "SHAPE": ("status", "round_name"),
}
NONE_MARKER = "FINDINGS: none"


class BlockParseError(ValueError):
    """The block is not exactly the contracted shape."""


@dataclass(frozen=True)
class Record:
    kind: str
    fields: dict
    line_no: int


@dataclass(frozen=True)
class Block:
    kind: str
    header: dict
    records: tuple
    findings_none: bool


def extract_block(text: str, kind: str) -> list[str]:
    if kind not in BLOCK_KINDS:
        raise ValueError(f"unknown block kind {kind!r}")
    lines = text.splitlines()
    starts = [i for i, ln in enumerate(lines) if ln.strip() == kind]
    ends = [i for i, ln in enumerate(lines) if ln.strip() == "END-" + kind]
    if len(starts) != 1 or len(ends) != 1:
        raise BlockParseError(
            f"{kind}: expected exactly one start and one end sentinel, "
            f"found {len(starts)} start and {len(ends)} end"
        )
    if ends[0] < starts[0]:
        raise BlockParseError(f"{kind}: END sentinel appears before the start sentinel")
    return lines[starts[0] + 1:ends[0]]


def _parse_record(key: str, payload: str, line_no: int) -> Record:
    names = RECORD_FIELDS[key]
    parts = payload.split(" | ", len(names) - 1)
    if len(parts) != len(names):
        raise BlockParseError(
            f"line {line_no}: {key} must have fields "
            + " | ".join(n + "=" for n in names)
        )
    fields = {}
    for position, (name, part) in enumerate(zip(names, parts), start=1):
        prefix = name + "="
        if not part.startswith(prefix):
            raise BlockParseError(
                f"line {line_no}: expected field {name!r} at position {position}, "
                f"got {part[:24]!r}"
            )
        fields[name] = part[len(prefix):].strip()
    return Record(key, fields, line_no)


def parse_block(text: str, kind: str) -> Block:
    body = extract_block(text, kind)
    header: dict = {}
    records: list = []
    findings_none = False
    for offset, raw in enumerate(body, start=1):
        line = raw.strip()
        if not line:
            continue
        if line == NONE_MARKER:
            findings_none = True
            continue
        if ":" not in line:
            raise BlockParseError(f"line {offset}: not a record: {line[:40]!r}")
        key, payload = line.split(":", 1)
        key, payload = key.strip(), payload.strip()
        if key in HEADER_KEYS[kind]:
            if key in header:
                raise BlockParseError(f"line {offset}: duplicate header {key}")
            header[key] = payload
            continue
        if key in ALLOWED_RECORDS[kind]:
            records.append(_parse_record(key, payload, offset))
            continue
        raise BlockParseError(
            f"line {offset}: unknown record {key!r} in {kind} (allowed: "
            + ", ".join(HEADER_KEYS[kind] + ALLOWED_RECORDS[kind])
            + ")"
        )
    missing = [k for k in HEADER_KEYS[kind] if k not in header]
    if missing:
        raise BlockParseError(f"{kind}: missing header line(s) {', '.join(missing)}")
    has_findings = any(r.kind == "FINDING" for r in records)
    if has_findings == findings_none:
        raise BlockParseError(
            f"{kind}: emit either FINDING lines or the single line '{NONE_MARKER}' "
            "— never both and never neither"
        )
    return Block(kind, header, tuple(records), findings_none)


_WS = re.compile(r"\s+")
_ELLIPSIS = re.compile(r"\.\.\.|…|\[\.\.\.\]")
MIN_SEGMENT = 8


def collapse_ws(s: str) -> str:
    return _WS.sub(" ", s).strip()


def normalize_quote(s: str) -> str:
    """Collapse whitespace and strip one layer of surrounding quotation marks."""
    s = collapse_ws(s)
    if len(s) >= 2 and s[0] in "\"“'‘" and s[-1] in "\"”'’":
        s = collapse_ws(s[1:-1])
    return s


def quote_segments(quote: str) -> list[str]:
    whole = normalize_quote(quote)
    segments = [collapse_ws(p) for p in _ELLIPSIS.split(whole)]
    long_enough = [s for s in segments if len(s) >= MIN_SEGMENT]
    if long_enough:
        return long_enough
    return [whole] if whole else []


def quote_is_in(quote: str, haystack: str) -> bool:
    """True when every substantial segment of the quote appears in the haystack.

    Tolerant of line wrapping, of one layer of quotation marks, and of an elision the
    assessor put in the middle of a long quote — intolerant of an invented quote,
    which is the thing worth catching.
    """
    segments = quote_segments(quote)
    if not segments:
        return False
    hay = collapse_ws(haystack)
    return all(seg in hay for seg in segments)
