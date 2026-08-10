#!/usr/bin/env python3
"""Whether an assessment may be shown to the person who asked for it.

Composes the five checks that stand on their own -- evidence refs, the prediction lint,
the contradiction detectors, the counting path, the market-table lint -- and adds the
rules that only make sense once all five outputs sit in the same document.

Composition means requiring the receipts, not recomputing the answers. A gate that was
never run produces no output, and no output looks exactly like a clean run, so this
gate reads journal.jsonl and refuses to pass when an upstream receipt is missing or
records a failure. It re-derives their logic on top of that as a belt-and-braces check
on the SHIPPED bytes, which is a different question from "did the gate run".

Each added rule closes a way an assessment can be internally consistent and still
wrong: counts without the disclaimer read as a prediction; a hard barrier printed after
the conclusion is a barrier nobody registered; a contradiction found in code and absent
from the page is one the reader averages away; a convention restated by the model is how
a "usually" becomes a "must" with nothing to check it against; a 大概率被筛掉 with no
「那该怎么办」 half is a door closed with nothing behind it.

Two comparisons are deliberately loose, because the tight version fires on correct
output and a gate that cries wolf is a gate people stop reading:

* Conventions are compared with ALL whitespace removed. The tables use YAML block
  scalars with hard wraps; demanding the model reproduce the wrap points would fail a
  card rendered character-for-character.
* Disqualifiers are keyed on the `## 硬性阻断项` section and the ROW IDS it lists, never
  on the posting's own wording. A Chinese section naming an English requirement is a
  paraphrase by construction, and that is the correct output, not the defect.

One finding is deliberately downgraded. check_conventions.py fails hard on an expired
review_by because it is the CI lint and that is where a stale date should stop a build.
Here it becomes WARN_EXPIRED_REVIEW_BY and the card must instead carry a 「已过复核期」
banner (spec §10). A date passing while the code did not change must not stop the skill
working -- but rendering a stale card without saying so is worse than either.

A mode may not claim success without a receipt. Exit 2 writes one too, verdict
"could_not_run", unless the workspace directory itself is absent.
"""
from __future__ import annotations

import argparse
import copy
import datetime
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import check_conventions as conventions  # noqa: E402
import check_evidence_refs as refs  # noqa: E402
import consistency  # noqa: E402
import count_coverage as coverage  # noqa: E402
import enter_mode  # noqa: E402
import journal  # noqa: E402
import lint_no_prediction as prediction  # noqa: E402
import paths  # noqa: E402
import vocab  # noqa: E402
import yaml  # noqa: E402

GATE = "check_assessment"
MODE = "assess"

# Every heading and column name this gate keys on is a PAIR. An English card is a
# first-class output here — count_coverage.py has --lang {zh,en} and render_block emits
# "apply verdict:" — so a constant that knows only the Chinese spelling reports a defect
# on a correct English assessment. A check that cries wolf on ordinary output is worse
# than no check: the reader learns to skip the line, and it stops working on the run
# that mattered. modes/assess.md §4 and §10 print both spellings for the same reason.
DISCLAIMER_ANCHORS = ("不是对结果的预判", "not a forecast of the outcome")
VERDICT_MARKERS = ("投递建议：", "apply verdict:")
DISQUALIFIER_HEADINGS = ("## 硬性阻断项", "## Hard blockers")
STALE_BANNER = "已过复核期"

# The closed set modes/assess.md §10 defines. Exactly one of these, inside the section
# below, on exactly the two verdicts below; the two column headers are where the
# section's whole value sits. One spelling of each pair is enough.
STRATEGIES = ("apply_anyway", "reposition", "skill_sprint", "side_door", "change_track")
STRATEGY_HEADINGS = ("## 那该怎么办", "## What to do instead")
OTHER_HALF_VERDICTS = ("likely_screen_out", "blocked")
ACCEPTANCE_COLUMNS = (("验收标准", "Acceptance criterion"), ("输出物", "Deliverable"))

# Composition: each of these must have run on THIS workspace and not failed.
UPSTREAM_GATES = ("evidence_blocks", "count_coverage", "consistency",
                  "check_evidence_refs", "lint_no_prediction")
PASSING_VERDICTS = ("pass", "recorded")

_ROW_ID = re.compile(r"\bR\d+\b")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s")


def _squeeze(text: str) -> str:
    """Whitespace is not the claim."""
    return re.sub(r"\s+", "", text)


def _verdict_line_index(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if any(marker in line for marker in VERDICT_MARKERS):
            return index
    return None


def _section_lines(lines: list[str], heading: str) -> tuple[int, list[str]] | None:
    """The lines of the first `heading` section, up to the next heading of any level."""
    for index, line in enumerate(lines):
        if line.strip().startswith(heading):
            body = []
            for later in lines[index + 1:]:
                if _HEADING.match(later):
                    break
                body.append(later)
            return index, body
    return None


def _first_section(lines: list[str], headings) -> tuple[int, list[str]] | None:
    """The first section matching any spelling of the heading. Both spellings are
    correct output, so trying only one turns a translation into a finding."""
    for heading in headings:
        found = _section_lines(lines, heading)
        if found is not None:
            return found
    return None


def cannot_run(workspace: pathlib.Path, reason: str) -> int:
    """Exactly one receipt on the could-not-run path, then exit 2."""
    print(f"cannot run: {reason}", file=sys.stderr)
    if workspace.is_dir():
        journal.receipt(workspace, GATE, {}, "could_not_run", [f"NO_INPUT: {reason}"])
    return 2


def check(workspace: pathlib.Path, market_dir: pathlib.Path,
          today: datetime.date, skill_root: pathlib.Path | None = None) -> list[str]:
    findings: list[str] = []
    root = pathlib.Path(skill_root) if skill_root else paths.SKILL_ROOT
    assessment = yaml.safe_load(
        (workspace / "fit-assessment.yaml").read_text(encoding="utf-8")) or {}
    markdown = (workspace / "fit-assessment.md").read_text(encoding="utf-8")
    lines = markdown.splitlines()
    squeezed = _squeeze(markdown)
    block_ids = refs.load_block_ids(workspace / "evidence-blocks.json")

    # 0. The layer-1.5 backstop, mirrored from check_apply.py. modes/assess.md is
    #    loaded unconditionally on entering the mode; this is what makes that real.
    entry = enter_mode.latest_mode_entry(workspace, MODE)
    mode_path = paths.mode_file(MODE, root)
    if entry is None:
        findings.append("NO_MODE_ENTRY: journal.jsonl has no mode_entry for assess — "
                        "modes/assess.md is loaded unconditionally on entering the "
                        "mode; run scripts/enter_mode.py --mode assess and read it")
    elif (mode_path.exists()
          and entry.get("mode_file_sha256") != journal.sha256_file(mode_path)):
        findings.append("MODE_FILE_CHANGED: modes/assess.md changed after this run "
                        "entered the mode, so what was read is not what is on disk — "
                        "re-enter the mode and re-read it")

    # 0b. Every upstream gate ran, on this workspace, and did not fail.
    for gate in UPSTREAM_GATES:
        receipts = journal.read_receipts(workspace, gate)
        if not receipts:
            findings.append(f"MISSING_RECEIPT: no journal.jsonl receipt for {gate} — "
                            f"the gate was never run, and a skipped gate looks exactly "
                            f"like a clean one")
            continue
        last = receipts[-1]
        if last.get("verdict") not in PASSING_VERDICTS:
            detail = "; ".join(last.get("findings") or []) or "no findings recorded"
            findings.append(f"UPSTREAM_FAILED: {gate} verdict={last.get('verdict')} "
                            f"({detail})")

    # 1. Evidence references, in check-only form: nothing may still need dropping.
    _, dropped = refs.drop_unresolvable_refs(copy.deepcopy(assessment), block_ids)
    findings += dropped
    _, stripped = refs.strip_block_ids(markdown)
    findings += stripped

    # 2. Row-level sourcing. `no_evidence` with an empty list is the honest shape.
    for row in assessment.get("requirements") or []:
        row = row or {}
        resolvable = [e for e in (row.get("evidence") or [])
                      if str((e or {}).get("ref", "")).strip() in block_ids]
        if row.get("match") == "no_evidence":
            if row.get("evidence"):
                findings.append(f"ROW_UNSOURCED: row {row.get('id')} is no_evidence but "
                                f"carries references; one of the two is wrong")
        elif not resolvable:
            findings.append(f"ROW_UNSOURCED: row {row.get('id')} claims "
                            f"match={row.get('match')!r} with no reference that resolves "
                            f"to a block")

    # 3. The prediction lint, over every rendered surface in the workspace.
    for path in prediction.target_files(workspace):
        findings += prediction.scan_text(path.read_text(encoding="utf-8"),
                                         str(path.relative_to(workspace)))

    # 4. Consistency notices must be attached where they fired.
    for notice in consistency.notices(assessment):
        if notice["anchor_zh"] not in markdown and notice["anchor_en"] not in markdown:
            findings.append(f"NOTICE_NOT_ATTACHED: {notice['code']} fired and its text "
                            f"is nowhere in fit-assessment.md; attach it beside the "
                            f"thing it qualifies")

    # 5. The counting path is the only counting path.
    counts = coverage.coverage(assessment.get("requirements"))
    findings += counts["invalid"]
    verdict = assessment.get("verdict")
    refusing = verdict == vocab.REFUSAL
    if not refusing:
        rendered = [coverage.render_block(assessment, counts, lang) for lang in ("zh", "en")]
        if not any(block in markdown for block in rendered):
            findings.append("COUNT_MISMATCH: fit-assessment.md does not contain the "
                            "block count_coverage.py produces; a second number written "
                            "by hand cannot be reconciled with this one")
        if not any(anchor in markdown for anchor in DISCLAIMER_ANCHORS):
            findings.append("NO_DISCLAIMER: the required disclaimer is absent; a count "
                            "without it reads as a prediction")

    # 6. The refusal floor is a refusal, not a sixth level.
    if refusing:
        for marker in VERDICT_MARKERS:
            if marker in markdown:
                findings.append(f"REFUSAL_WITH_VERDICT: verdict is "
                                f"{vocab.REFUSAL} but {marker!r} still renders a "
                                f"conclusion")
    elif verdict not in vocab.VERDICTS:
        findings.append(f"BAD_VERDICT: {verdict!r} is not one of "
                        f"{vocab.VERDICTS} or {vocab.REFUSAL!r}")
    if assessment.get("provisional"):
        findings.append("PROVISIONAL_VERDICT: a discover-stage 基于卡片信息的初判 was "
                        "carried into an assessment; assess always recomputes")

    # 7. Disqualifiers render before the verdict, in a section that names their ids.
    blocking = [row or {} for row in (assessment.get("requirements") or [])
                if (row or {}).get("screening") == "knockout"
                and (row or {}).get("match") in ("gap", "no_evidence")]
    if blocking:
        section = _first_section(lines, DISQUALIFIER_HEADINGS)
        if section is None:
            findings.append(
                f"NO_DISQUALIFIER_SECTION: {len(blocking)} knockout requirement(s) are "
                f"not met and there is no '{DISQUALIFIER_HEADINGS[0]}' / "
                f"'{DISQUALIFIER_HEADINGS[1]}' section; a wall the reader is never "
                f"shown is a wall they walk into")
        else:
            heading_index, body = section
            named = set(_ROW_ID.findall("\n".join(body)))
            for row in blocking:
                if str(row.get("id")) not in named:
                    findings.append(
                        f"DISQUALIFIER_NOT_NAMED: row {row.get('id')} is a knockout the "
                        f"candidate does not meet and the disqualifier section does not "
                        f"list its id; paraphrase the barrier freely, but name the row")
            verdict_index = _verdict_line_index(lines)
            if verdict_index is not None and heading_index > verdict_index:
                findings.append(
                    "DISQUALIFIER_AFTER_VERDICT: the disqualifier section renders below "
                    "the verdict line; a wall printed after the conclusion is a wall "
                    "nobody read")

    # 8. The "what to do instead" half, on the two verdicts that require it. Scoped to
    #    the section, because that is what the finding names claim and because a
    #    contrast sentence elsewhere ("not apply_anyway but skill_sprint") is ordinary
    #    prose, not a menu — counting it as one is the cry-wolf case again.
    if verdict in OTHER_HALF_VERDICTS:
        strategy_section = _first_section(lines, STRATEGY_HEADINGS)
        body = "\n".join(strategy_section[1]) if strategy_section else ""
        chosen = [name for name in STRATEGIES if name in body]
        if not chosen:
            findings.append(
                f"NO_STRATEGY_SECTION: verdict is {verdict} and no strategy from "
                f"{STRATEGIES} appears under '{STRATEGY_HEADINGS[0]}' / "
                f"'{STRATEGY_HEADINGS[1]}'; a verdict without the other half is a door "
                f"closed with nothing behind it")
        elif len(chosen) > 1:
            findings.append(
                f"STRATEGY_NOT_UNIQUE: {chosen} all appear in that section; pick "
                f"exactly one. A menu hands the choice back to the reader, which is "
                f"the work they asked for")
        for pair in ACCEPTANCE_COLUMNS:
            if not any(column in markdown for column in pair):
                findings.append(
                    f"NO_ACCEPTANCE_COLUMN: verdict is {verdict} and no '{pair[0]}' / "
                    f"'{pair[1]}' column is present; that column is what turns advice "
                    f"into something checkable, and it is the whole value of this "
                    f"section")

    # 9. Market conventions: allowlisted by id, rendered verbatim, staleness banner-ed.
    market = assessment.get("market")
    table = market_dir / f"{market}.yaml"
    known: dict[str, dict] = {}
    expired: set[str] = set()
    if market in conventions.MARKET_KEYS:
        if not table.exists():
            findings.append(f"CONVENTION_TABLE_MISSING: {table} does not exist")
        else:
            for finding in conventions.check_file(table, today):
                if finding.startswith("EXPIRED_REVIEW_BY:"):
                    # CI keeps this hard. At runtime it is a banner, not a refusal.
                    expired.add(finding.split(":", 1)[1].strip().split()[0])
                    findings.append("WARN_" + finding)
                else:
                    findings.append(finding)
            known = conventions.conventions_by_id(conventions.load_market_file(table))
    for entry_id in assessment.get("conventions_rendered") or []:
        convention = known.get(entry_id)
        if convention is None:
            findings.append(f"CONVENTION_UNKNOWN_ID: {entry_id} is not an entry in "
                            f"{table.name}; the model may not author a convention")
            continue
        if not any(_squeeze(str(convention.get(field, ""))) and
                   _squeeze(str(convention[field])) in squeezed
                   for field in ("text_en", "text_zh")):
            findings.append(f"CONVENTION_PARAPHRASED: {entry_id} was listed as rendered "
                            f"but neither text_en nor text_zh appears verbatim in "
                            f"fit-assessment.md")
        if entry_id in expired and STALE_BANNER not in markdown:
            findings.append(f"MISSING_STALE_BANNER: {entry_id} is past its review_by and "
                            f"was rendered without the 「{STALE_BANNER}」 banner; the card "
                            f"still renders, but the reader has to be told it is stale")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The assess-mode gate.")
    parser.add_argument("--workspace", required=True, type=pathlib.Path)
    parser.add_argument("--market-dir", type=pathlib.Path, default=None)
    parser.add_argument("--skill-root", type=pathlib.Path, default=None)
    parser.add_argument("--today", default=None)
    args = parser.parse_args(argv)

    workspace = args.workspace
    market_dir = args.market_dir or conventions.CONVENTIONS_DIR
    skill_root = args.skill_root or paths.SKILL_ROOT
    today = (datetime.date.fromisoformat(args.today) if args.today
             else datetime.date.today())

    if not workspace.is_dir():
        return cannot_run(workspace, f"workspace {workspace} does not exist")
    required = [workspace / "fit-assessment.yaml", workspace / "fit-assessment.md",
                workspace / "evidence-blocks.json"]
    for path in required:
        if not path.exists():
            return cannot_run(workspace, f"{path.name} not found at {path}")

    findings = check(workspace, market_dir, today, skill_root)
    hard = [f for f in findings if not f.startswith("WARN_")]
    for finding in findings:
        print(finding)
    journal.receipt(workspace, GATE,
                    {path.name: journal.sha256_file(path) for path in required},
                    "fail" if hard else "pass", findings)
    return 1 if hard else 0


if __name__ == "__main__":
    raise SystemExit(main())
