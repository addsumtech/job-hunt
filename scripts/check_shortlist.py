#!/usr/bin/env python3
"""Gate: is this shortlist real? (spec §5.1, risk register rows 1-3)

A fabricated shortlist is internally consistent, perfectly formatted, and every
field has the right shape — so shape is not what gets checked. What gets checked
is that each row's identifier appears VERBATIM in a raw capture from the site it
claims, because that is the one thing a fabricated row cannot do.

Exit codes: 0 = passed, 1 = findings on stdout, 2 = could not run. On exit 2 one
receipt with verdict "could_not_run" is appended — EXCEPT when the workspace
directory itself does not exist, because then there is nothing to append to. If
you find no receipt at all, that is the case you are in.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import yaml  # noqa: E402

import journal  # noqa: E402  (Plan 1)
from vocab import EFFORT, VERDICTS  # noqa: E402  (Plan 1 — the ONE vocabulary)

GATE = "check_shortlist"

# The seventeen fields of a shortlist row: the thirteen JobListingEvidence base
# fields, plus the four this skill adds on top of them. This tuple is the single
# enumeration — modes/discover.md documents the same seventeen and the mode-doc
# test asserts every one of them is findable there.
REQUIRED_ROW_FIELDS = (
    "id", "title", "company", "location", "salary", "url", "source_site",
    "source_id", "extraction_method", "retrieved_at", "quality",
    "verification", "raw_text", "why_matched", "verdict", "provisional",
    "effort",
)

# VERDICTS and EFFORT are imported, never re-spelled: a second copy of a closed
# set is a second thing to forget to update. VERDICTS is ordinal, strongest
# first, so the detail-fetch cap is a slice of it rather than a third list that
# could silently disagree with the other two.
TOP_THREE = VERDICTS[:3]
EXTRACTION_METHODS = ("adapter_search", "adapter_detail", "user_paste",
                      "public_page")
QUALITIES = ("complete", "partial", "card_only")
VERIFICATIONS = ("fresh_verified", "collected_unverified", "stale_possible")

# Shorter than this and a verbatim substring search would match almost any
# capture, which makes the provenance check vacuous rather than strict.
MIN_SOURCE_ID_LEN = 4


def load_raw_texts(workspace):
    """{site: {filename: text}} over raw/<site>-*.json. Never parsed as JSON:
    the check is a verbatim substring search over the bytes we captured."""
    out = {}
    raw_dir = pathlib.Path(workspace) / "raw"
    if not raw_dir.is_dir():
        return out
    for path in sorted(raw_dir.glob("*.json")):
        if "-" not in path.name:
            continue
        site = path.name.split("-", 1)[0]
        out.setdefault(site, {})[path.name] = path.read_text(
            encoding="utf-8", errors="replace")
    return out


def _check_provenance(label, row, site, raw_texts):
    findings = []
    source_id = str(row.get("source_id") or "").strip()
    if not source_id:
        findings.append(f"NO_SOURCE_ID: {label} has no source_id")
        return findings
    if len(source_id) < MIN_SOURCE_ID_LEN:
        findings.append(
            f"SUSPICIOUS_SOURCE_ID: {label} source_id {source_id!r} is shorter "
            f"than {MIN_SOURCE_ID_LEN} characters; a verbatim search for it "
            "would match almost any capture")
        return findings
    if not site:
        return findings
    captures = raw_texts.get(site)
    if not captures:
        findings.append(
            f"NO_RAW_CAPTURE_FOR_SITE: {label} claims source_site {site!r} but "
            f"raw/ holds no {site}-*.json capture")
        return findings
    if not any(source_id in text for text in captures.values()):
        findings.append(
            f"SOURCE_ID_NOT_IN_RAW: {label} source_id {source_id!r} does not "
            f"appear verbatim in any of {', '.join(sorted(captures))}")
    url = str(row.get("url") or "").strip()
    if url:
        stem = url.split("?", 1)[0].split("#", 1)[0]
        if not any(stem in text for text in captures.values()):
            findings.append(
                f"URL_NOT_FROM_ADAPTER: {label} url {url!r} was not returned by "
                f"an adapter ({stem!r} appears in no {site}-*.json capture)")
    return findings


def check_rows(shortlist, raw_texts):
    findings = []
    for index, row in enumerate(shortlist.get("rows") or []):
        if not isinstance(row, dict):
            findings.append(f"BAD_ROW: row {index} is not a mapping")
            continue
        label = f"row {index} (id={row.get('id', '<no id>')!r})"
        for field in REQUIRED_ROW_FIELDS:
            if field not in row:
                findings.append(f"MISSING_FIELD: {label} has no `{field}`")
        site = str(row.get("source_site") or "").strip()
        if not site:
            findings.append(
                f"NO_SOURCE_SITE: {label} has no source_site — the row cannot be "
                "traced back to a capture")
        if not str(row.get("title") or "").strip():
            findings.append(
                f"EMPTY_TITLE: {label} has an empty title — the identifying "
                f"field was never recovered (run the detail command for "
                f"{site or 'this site'})")
        if not str(row.get("why_matched") or "").strip():
            findings.append(f"NO_WHY_MATCHED: {label} has no why_matched")
        if not str(row.get("retrieved_at") or "").strip():
            findings.append(f"NO_RETRIEVED_AT: {label} has no retrieved_at")
        if row.get("verdict") not in VERDICTS:
            findings.append(
                f"BAD_VERDICT: {label} verdict {row.get('verdict')!r} is not one "
                f"of {', '.join(VERDICTS)}")
        if row.get("provisional") is not True:
            findings.append(
                f"MISSING_PROVISIONAL: {label} has no `provisional: true` stamp. "
                "A discover verdict is based on a card, not on a full JD, so it "
                "may not be rendered without the stamp and is never carried into "
                "an assessment — assess always recomputes.")
        for field, allowed in (("extraction_method", EXTRACTION_METHODS),
                               ("quality", QUALITIES),
                               ("verification", VERIFICATIONS),
                               ("effort", EFFORT)):
            if field in row and row.get(field) not in allowed:
                findings.append(
                    f"BAD_ENUM: {label} {field}={row.get(field)!r} is not one of "
                    f"{', '.join(allowed)}")
        findings.extend(_check_provenance(label, row, site, raw_texts))

    # One retrieved row may not become two shortlist rows. Without this, count
    # conservation is decorative: the source report can honestly say "2 rows
    # returned" while the shortlist below it lists the same posting three times.
    seen = {}
    for index, row in enumerate(shortlist.get("rows") or []):
        if not isinstance(row, dict):
            continue
        key = (str(row.get("source_site") or "").strip(),
               str(row.get("source_id") or "").strip())
        if not key[1]:
            continue
        if key in seen:
            findings.append(
                f"DUPLICATE_SOURCE_ID: row {index} (id={row.get('id')!r}) repeats "
                f"source_id {key[1]!r} from row {seen[key]} on the same site — one "
                "retrieved row became two shortlist rows")
        else:
            seen[key] = index
    return findings


def _fail_to_run(workspace, message):
    journal.receipt(workspace, GATE, {}, "could_not_run", [message])
    print(message, file=sys.stderr)
    return 2


def main(argv=None):
    parser = argparse.ArgumentParser(description="Gate: the shortlist is real.")
    parser.add_argument("--workspace", required=True, type=pathlib.Path)
    args = parser.parse_args(argv)
    workspace = args.workspace

    if not workspace.is_dir():
        print(f"workspace not found: {workspace}", file=sys.stderr)
        return 2
    shortlist_path = workspace / "shortlist.yaml"
    if not shortlist_path.is_file():
        return _fail_to_run(workspace, f"missing input: {shortlist_path}")
    try:
        shortlist = yaml.safe_load(shortlist_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return _fail_to_run(workspace, f"unparsable shortlist.yaml: {exc}")
    if not isinstance(shortlist, dict):
        return _fail_to_run(
            workspace, "shortlist.yaml must be a mapping with a `rows:` list")

    raw_texts = load_raw_texts(workspace)
    findings = check_rows(shortlist, raw_texts)

    input_hashes = {"shortlist.yaml": journal.sha256_file(shortlist_path)}
    for site in sorted(raw_texts):
        for name in sorted(raw_texts[site]):
            input_hashes[f"raw/{name}"] = journal.sha256_file(
                workspace / "raw" / name)

    journal.receipt(workspace, GATE, input_hashes,
                    "fail" if findings else "pass", findings)
    for line in findings:
        print(line)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
