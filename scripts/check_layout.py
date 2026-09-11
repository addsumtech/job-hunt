#!/usr/bin/env python3
"""Require a current, page-by-page visual layout review for rendered CVs.

This validates the review record and its artifact hashes. It does not pretend
that a text parser has visually compared a template with the final document.
Exit 2 means there is no rendered CV to review; exit 1 means review findings.
"""
from __future__ import annotations

import argparse
import datetime
import pathlib
import sys

import journal

GATE = "check_layout"
CHECKS = ("fonts", "font_sizes", "page_geometry", "headings_and_rules",
          "dates_and_alignment", "paragraph_spacing", "content_order",
          "pagination_and_clipping")


def inspect(ws: pathlib.Path):
    findings, hashes = [], {}
    path = ws / "layout-review.yaml"
    if not path.is_file():
        return ["NO_LAYOUT_REVIEW: render and inspect every CV page against the supplied template, then write layout-review.yaml"], hashes
    hashes[path.name] = journal.sha256_file(path)
    try:
        review = journal.load_yaml(path, dict)
    except journal.InputProblem as exc:
        return [f"BAD_LAYOUT_REVIEW: {exc.reason}"], hashes

    def bind(raw, expected, label, local=True):
        if not isinstance(raw, str) or not raw.strip():
            findings.append(f"BAD_LAYOUT_REVIEW: {label} has no path")
            return None
        target = pathlib.Path(raw)
        target = target.resolve() if target.is_absolute() else (ws / target).resolve()
        if local and not target.is_relative_to(ws.resolve()):
            findings.append(f"BAD_LAYOUT_REVIEW: {label} must be inside the workspace")
            return None
        if not target.is_file():
            findings.append(f"MISSING_LAYOUT_INPUT: {label}: {raw}")
            return None
        key = str(target.relative_to(ws.resolve())) if target.is_relative_to(ws.resolve()) else str(target)
        now = journal.sha256_file(target)
        hashes[key] = now
        if expected != now:
            findings.append(f"STALE_LAYOUT_REVIEW: {label} changed or was never fingerprinted; inspect the final version again")
        return target

    if not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip():
        findings.append("BAD_LAYOUT_REVIEW: name the reviewer")
    try:
        stamp = datetime.datetime.fromisoformat(review.get("reviewed_at", ""))
        if stamp.tzinfo is None:
            raise ValueError("missing timezone")
    except (TypeError, ValueError):
        findings.append("BAD_LAYOUT_REVIEW: reviewed_at must be an ISO timestamp with timezone")
    if "reference" not in review:
        findings.append("BAD_LAYOUT_REVIEW: name the supplied template, or set reference: null when none was supplied")
    elif review["reference"] is not None:
        ref = journal.as_mapping(review["reference"])
        bind(ref.get("path"), ref.get("sha256"), "reference template", local=False)
    overrides = review.get("user_overrides")
    if not isinstance(overrides, list) or any(not isinstance(v, str) or not v.strip() for v in overrides):
        findings.append("BAD_LAYOUT_REVIEW: user_overrides must list the user's changes to the reference, or be []")
    checks = journal.as_mapping(review.get("checks"))
    for name in CHECKS:
        check = journal.as_mapping(checks.get(name))
        if check.get("status") != "pass" or not isinstance(check.get("detail"), str) or not check["detail"].strip():
            findings.append(f"LAYOUT_NOT_PASSED: {name} needs a passed comparison and a concrete observation")
    if review.get("unresolved_differences") != []:
        findings.append("LAYOUT_DIFFERENCES: resolve all unapproved layout differences before delivery")

    artifacts = journal.as_mapping(review.get("artifacts"))
    for name in ("cv.docx", "cv.pdf"):
        if not (ws / name).is_file():
            continue
        item = journal.as_mapping(artifacts.get(name))
        artifact = bind(name, item.get("sha256"), name)
        pages = item.get("pages")
        if type(pages) is not int or pages < 1:
            findings.append(f"BAD_LAYOUT_REVIEW: {name} needs its rendered page count")
            continue
        if name.endswith(".pdf") and artifact:
            try:
                import pymupdf
                with pymupdf.open(artifact) as doc:
                    if len(doc) != pages:
                        findings.append(f"LAYOUT_PAGE_COUNT: {name} has {len(doc)} pages, review recorded {pages}")
            except Exception as exc:
                findings.append(f"UNREADABLE_LAYOUT_PDF: {name}: {exc}")
        previews = item.get("previews")
        seen = []
        if not isinstance(previews, list):
            previews = []
        for i, raw in enumerate(previews):
            preview = journal.as_mapping(raw)
            seen.append(preview.get("page"))
            image = bind(preview.get("path"), preview.get("sha256"), f"{name} preview {i + 1}")
            if image:
                try:
                    import pymupdf
                    pix = pymupdf.Pixmap(image)
                    if pix.width < 1 or pix.height < 1:
                        raise ValueError("empty image")
                except Exception:
                    findings.append(f"UNREADABLE_LAYOUT_PREVIEW: {image.name}")
        if any(type(n) is not int for n in seen) or sorted(seen) != list(range(1, pages + 1)):
            findings.append(f"UNREVIEWED_LAYOUT_PAGE: {name} needs exactly one inspected preview for every rendered page")
    return findings, hashes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=pathlib.Path)
    args = parser.parse_args(argv)
    ws = args.workspace.resolve()
    if not ws.is_dir():
        print(f"cannot run {GATE}: workspace {ws} does not exist", file=sys.stderr)
        return 2
    if not any((ws / name).is_file() for name in ("cv.docx", "cv.pdf")):
        findings, hashes = ["NO_LAYOUT_ARTIFACT: no rendered CV exists"], {}
        journal.receipt(ws, GATE, hashes, "could_not_run", findings)
        print(findings[0], file=sys.stderr)
        return 2
    else:
        findings, hashes = inspect(ws)
    for finding in findings:
        print(finding)
    journal.receipt(ws, GATE, hashes, "fail" if findings else "pass", findings)
    return 1 if findings else 0


if __name__ == "__main__":
    from cli_io import configure_output
    configure_output()
    sys.exit(main())
