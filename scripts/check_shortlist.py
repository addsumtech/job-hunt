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


import journal  # noqa: E402  (Plan 1)
import enter_mode  # noqa: E402  (Plan 1)
import paths       # noqa: E402  (Plan 1)
from check_opencli_result import read_adapter_calls  # noqa: E402
from vocab import EFFORT, VERDICTS  # noqa: E402  (Plan 1 — the ONE vocabulary)

GATE = "check_shortlist"
MODE = "discover"

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

# Wording that asserts the run found nothing. Only consulted when the shortlist
# has ZERO rows: with rows present, "没有匹配到 staff 级别的岗位" is a qualified
# statement about a slice, not a claim that the run came back empty.
EMPTINESS_PHRASES = ("没有匹配", "没有结果", "未找到", "无匹配", "零结果",
                     "no results", "no matching", "nothing found", "found nothing")

# The degraded-output disclosure block. The last four answers ship pre-filled as
# 否, so concealing a retry or a bypass has to be an active overwrite rather than
# an omission.
DISCLOSURE_LABELS = ("本次会话已登录：", "Adapter 返回：", "收到限制信号后重试：",
                     "绕过任何平台控制：", "取得真实岗位：", "降级输出类型：")

# The reader-facing half of the provisional stamp (spec §5.1 step 6: a discover
# verdict 不带这个戳就不许渲染). `provisional: true` in shortlist.yaml is the
# machine half, and nobody reading the round ever sees it — shortlist.md is what
# the user actually reads, so that is where the claim has to be qualified.
PROVISIONAL_STAMP = "基于卡片信息的初判"

# The yellow-tier round caps from references/source-policy.md, as numbers,
# because a cap enforced by a paragraph is not a cap. brief.yaml must carry both
# and neither may exceed these. This is that reference file's named backstop.
MAX_ROWS_PER_ROUND_CEILING = 25
MAX_PAGES_PER_SITE_CEILING = 2


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


def _check_disclosure(md_text):
    missing = [label for label in DISCLOSURE_LABELS if label not in md_text]
    if len(missing) == len(DISCLOSURE_LABELS):
        return ["DEGRADED_WITHOUT_DISCLOSURE: no adapter exited 0 and the "
                "shortlist is empty, so this run is a degraded output. It must "
                "carry the disclosure block (" + "、".join(DISCLOSURE_LABELS)
                + ") with every answer filled in."]
    findings = []
    if missing:
        findings.append("DISCLOSURE_INCOMPLETE: the disclosure block is missing "
                        "these lines: " + "、".join(missing))
    for label in DISCLOSURE_LABELS:
        if label in missing:
            continue
        for line in md_text.splitlines():
            if label in line:
                if not line.split(label, 1)[1].strip():
                    findings.append(
                        f"DISCLOSURE_INCOMPLETE: disclosure line {label!r} has a "
                        "blank answer. The answers ship pre-filled as 否 so that "
                        "concealment has to be an active overwrite, not an "
                        "omission.")
                break
    return findings


def _check_sources(workspace, shortlist, rows, calls):
    findings = []
    reported = {str(entry["site"]): entry
                for entry in (shortlist.get("sources") or [])
                if isinstance(entry, dict) and entry.get("site")}
    used = {str(row.get("source_site")) for row in rows
            if isinstance(row, dict) and row.get("source_site")}
    for site in sorted(used):
        if site not in reported:
            findings.append(
                f"SOURCE_REPORT_MISSING: rows cite source_site {site!r} but "
                "shortlist.yaml `sources:` has no entry for it. That entry needs "
                "the adapter's identity_field and detail_command — for any site "
                "outside the four inlined in SKILL.md they come from "
                "references/discovery-sources.md.")
    for site, entry in sorted(reported.items()):
        command = entry.get("command")
        matching = [c for c in calls if c.get("site") == site
                    and (command is None or c.get("command") == command)]
        if not matching:
            findings.append(
                f"SOURCE_REPORT_CONTRADICTS_JOURNAL: sources[{site}] reports "
                f"command {command!r} but journal.jsonl records no adapter_call "
                "for that site and command")
            continue
        recorded = {c.get("classification") for c in matching}
        if entry.get("classification") not in recorded:
            findings.append(
                f"SOURCE_REPORT_CONTRADICTS_JOURNAL: sources[{site}] reports "
                f"classification {entry.get('classification')!r} but "
                f"journal.jsonl recorded {sorted(x for x in recorded if x)}")

        # ---- 条数守恒 (spec §5.1) --------------------------------------
        # Each of these fires in ONE direction only — the dishonest one. The
        # opposite direction is either impossible or harmless, and a check that
        # also fires on the harmless case is a check people learn to ignore.
        reported_rows = entry.get("rows_returned")
        retrieved = sum(int(c.get("row_count") or 0) for c in matching)
        if isinstance(reported_rows, int) and reported_rows > retrieved:
            findings.append(
                f"SOURCE_REPORT_COUNT_MISMATCH: sources[{site}] reports "
                f"rows_returned={reported_rows} but journal.jsonl recorded "
                f"{retrieved} row(s) across {len(matching)} adapter_call(s). A "
                "run may not report more rows than the adapter returned.")
        site_rows = [r for r in rows if isinstance(r, dict)
                     and str(r.get("source_site") or "").strip() == site]
        if isinstance(reported_rows, int) and len(site_rows) > reported_rows:
            findings.append(
                f"SOURCE_REPORT_COUNT_MISMATCH: {len(site_rows)} shortlist rows "
                f"cite source_site {site!r} but sources[{site}] reports only "
                f"rows_returned={reported_rows}. De-duplication removes rows; "
                "nothing adds them.")
        reported_calls = entry.get("invocations")
        if isinstance(reported_calls, int) and reported_calls < len(matching):
            findings.append(
                f"SOURCE_REPORT_COUNT_MISMATCH: sources[{site}] reports "
                f"invocations={reported_calls} but journal.jsonl recorded "
                f"{len(matching)}. Under-reporting invocations is how a retry "
                "after a stop-signal disappears from the disclosure block.")
        reported_empty = entry.get("identity_field_empty_rows")
        observed_empty = sum(len(c.get("empty_identity_rows") or [])
                             for c in matching)
        if isinstance(reported_empty, int) and reported_empty < observed_empty:
            findings.append(
                f"SOURCE_REPORT_COUNT_MISMATCH: sources[{site}] reports "
                f"identity_field_empty_rows={reported_empty} but journal.jsonl "
                f"recorded {observed_empty}. Under-reporting a blank identity "
                "field hides exactly the gap needs_detail_recovery exists to "
                "surface.")

        for name in entry.get("raw_files") or []:
            if not (workspace / name).is_file():
                findings.append(
                    f"SOURCE_REPORT_MISSING_RAW: sources[{site}] names "
                    f"{name!r}, which does not exist")
    return findings


def _check_caps(brief):
    """The yellow-tier caps in references/source-policy.md, as a check.

    This is that reference file's named backstop: its two numbers are the only
    part of the policy a program can decide, and without them the trigger in
    SKILL.md would point at a file nothing reports you for skipping.
    """
    findings = []
    for field, ceiling in (("max_rows_per_round", MAX_ROWS_PER_ROUND_CEILING),
                           ("max_pages_per_site", MAX_PAGES_PER_SITE_CEILING)):
        value = brief.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            findings.append(
                f"CAP_MISSING: brief.yaml has no positive integer `{field}`. "
                "The yellow-tier caps are what keep pagination and detail "
                "fan-out inside references/source-policy.md; a round without "
                "them is an uncapped one.")
        elif value > ceiling:
            findings.append(
                f"CAP_ABOVE_CEILING: brief.yaml {field}={value} exceeds the "
                f"yellow-tier ceiling of {ceiling} in "
                "references/source-policy.md. Read that file before raising "
                "it: the cap is the whole difference between two pages a human "
                "asked for and a crawl.")
    return findings


def _check_detail_cap(shortlist, rows):
    findings = []
    exempt = {str(entry.get("id"))
              for entry in (shortlist.get("detail_fetch_exceptions") or [])
              if isinstance(entry, dict)}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        fetched = (row.get("quality") == "complete"
                   or row.get("extraction_method") == "adapter_detail")
        if (fetched and row.get("verdict") not in TOP_THREE
                and str(row.get("id")) not in exempt):
            findings.append(
                f"DETAIL_FETCH_OUT_OF_BAND: row {index} (id={row.get('id')!r}) "
                f"carries a detail fetch but verdict {row.get('verdict')!r} is "
                f"outside the top three ({', '.join(TOP_THREE)}). Detail "
                "fan-out is the yellow-layer cap. If the user named this row, "
                "record it in shortlist.yaml `detail_fetch_exceptions` with a "
                "reason.")
    return findings


def check_run(workspace, shortlist, brief, md_text, calls):
    findings = []
    rows = shortlist.get("rows") or []
    ok_calls = [c for c in calls
                if c.get("classification") == "ok" and c.get("exit_code") == 0]

    if not calls:
        findings.append(
            "NO_ADAPTER_RECEIPTS: journal.jsonl records no adapter_call at all, "
            "so nothing in this workspace can be traced to a live retrieval. "
            "Every adapter invocation goes through "
            "scripts/check_opencli_result.py.")

    if not str(brief.get("trigger_reason") or "").strip():
        findings.append(
            "NO_TRIGGER_REASON: brief.yaml has no trigger_reason. The reason for "
            "searching is stated BEFORE the search and written into the brief.")
    if "§0.1" not in md_text:
        findings.append(
            "NO_TRIGGER_SECTION: shortlist.md has no `§0.1` section carrying the "
            "trigger reason")

    target = brief.get("target_count")
    if isinstance(target, int) and len(rows) < target and not str(
            shortlist.get("shortfall_reason") or "").strip():
        findings.append(
            f"SHORTFALL_NO_REASON: brief.target_count is {target} but the "
            f"shortlist has {len(rows)} rows and shortfall_reason is empty. "
            "Write the reason — never pad the count.")

    findings.extend(_check_caps(brief))

    if rows and PROVISIONAL_STAMP not in md_text:
        findings.append(
            "MD_MISSING_PROVISIONAL_STAMP: shortlist.md renders rows without the "
            f"「{PROVISIONAL_STAMP}」 label. `provisional: true` in shortlist.yaml "
            "is the machine half of the stamp and no reader ever sees it; this is "
            "the half they do see, and a discover verdict may not be rendered "
            "without it.")

    if not rows:
        lowered = md_text.lower()
        hit = next((p for p in EMPTINESS_PHRASES
                    if p in md_text or p in lowered), None)
        if hit and not ok_calls:
            findings.append(
                f"EMPTY_RESULT_UNSUPPORTED: shortlist.md says {hit!r} but "
                "journal.jsonl records no adapter call that exited 0. "
                "All-adapters-failed and found-nothing have the identical "
                "shape; only the receipts tell them apart.")
        if not ok_calls:
            findings.extend(_check_disclosure(md_text))

    findings.extend(_check_sources(workspace, shortlist, rows, calls))
    findings.extend(_check_detail_cap(shortlist, rows))
    return findings


def _check_mode_entry(workspace, skill_root):
    """modes/discover.md is layer 1.5, and this is what reports it was not read.

    Mirrors check_apply.py deliberately: the same two findings, the same
    meaning, in the gate that belongs to this mode. Four modes with four
    different words for the same failure would be four things to learn.
    """
    findings = []
    entry = enter_mode.latest_mode_entry(workspace, MODE)
    mode_path = paths.mode_file(MODE, skill_root)   # mode first, root second
    if entry is None:
        findings.append(
            "NO_MODE_ENTRY: journal.jsonl has no mode_entry for discover. "
            "modes/discover.md is loaded unconditionally on entering the mode — "
            "it is the only definition of the brief, shortlist and preferences "
            "schemas — and this record is the only thing that reports it was "
            "not. Run `python3 scripts/enter_mode.py --workspace <ws> --mode "
            "discover`, then read the file.")
    elif (mode_path.is_file()
          and entry.get("mode_file_sha256") != journal.sha256_file(mode_path)):
        findings.append(
            "MODE_FILE_CHANGED: modes/discover.md changed after this run entered "
            "the mode, so the schema that was read is not the schema on disk. "
            "re-enter the mode and re-read it before trusting this shortlist.")
    return findings


def _fail_to_run(workspace, message):
    journal.receipt(workspace, GATE, {}, "could_not_run", [message])
    print(message, file=sys.stderr)
    return 2


def main(argv=None):
    parser = argparse.ArgumentParser(description="Gate: the shortlist is real.")
    parser.add_argument("--workspace", required=True, type=pathlib.Path)
    parser.add_argument("--skill-root", type=pathlib.Path,
                        default=paths.SKILL_ROOT,
                        help="repo root holding modes/ (default: paths.SKILL_ROOT)")
    args = parser.parse_args(argv)
    workspace = args.workspace

    if not workspace.is_dir():
        print(f"workspace not found: {workspace}", file=sys.stderr)
        return 2
    shortlist_path = workspace / "shortlist.yaml"
    if not shortlist_path.is_file():
        return _fail_to_run(workspace, f"missing input: {shortlist_path}")
    try:
        shortlist = journal.load_yaml(shortlist_path)
    except journal.YamlUnreadable as exc:
        return _fail_to_run(workspace, exc.finding)

    brief_path = workspace / "brief.yaml"
    if not brief_path.is_file():
        return _fail_to_run(workspace, f"missing input: {brief_path}")
    try:
        brief = journal.load_yaml(brief_path)
    except journal.YamlUnreadable as exc:
        return _fail_to_run(workspace, exc.finding)

    md_path = workspace / "shortlist.md"
    md_text = (md_path.read_text(encoding="utf-8", errors="replace")
               if md_path.is_file() else "")
    journal_path = workspace / "journal.jsonl"

    raw_texts = load_raw_texts(workspace)
    findings = _check_mode_entry(workspace, args.skill_root)
    findings.extend(check_rows(shortlist, raw_texts))
    findings.extend(check_run(workspace, shortlist, brief, md_text,
                              read_adapter_calls(workspace)))

    input_hashes = {"shortlist.yaml": journal.sha256_file(shortlist_path),
                    "brief.yaml": journal.sha256_file(brief_path)}
    if md_path.is_file():
        input_hashes["shortlist.md"] = journal.sha256_file(md_path)
    if journal_path.is_file():
        input_hashes["journal.jsonl"] = journal.sha256_file(journal_path)
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
