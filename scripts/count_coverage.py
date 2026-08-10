#!/usr/bin/env python3
"""The one place a number in an assessment comes from.

The skill this replaces computed must-have coverage twice, with two formulas, over the
same list. The two never agreed, and prose was left managing the disagreement. There is
one function here, one rendered block, and check_assessment.py requires the block in
fit-assessment.md to be byte-identical to what this produces. A second number cannot
survive that.

No percentage, and no slash score. Collapsing strong / partial / gap into one number
needs a weight for a partial match, and any weight would be invented. The block shows
exactly what was counted and claims nothing that was not; every counted row is printed
in the requirement table beside its evidence reference, so the denominator is auditable
row by row and a reader can object to any single line.

Exit 2 still writes a receipt, verdict "could_not_run", unless the workspace directory
itself is absent -- there is nothing to append to.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import journal  # noqa: E402
import vocab  # noqa: E402
import yaml  # noqa: E402

GATE = "count_coverage"

MATCHES = vocab.MATCH
RECENCIES = vocab.RECENCY
KINDS = ("must_have", "responsibility")

# These two maps are this module's own. VERDICT_ZH is not: lint_no_prediction.py
# masks against the same map, and two copies of it means one of them eventually
# stops matching the label the other one prints.
LEVEL_DIRECTION_ZH = {"step_up": "上跳", "lateral": "平级", "step_down": "下沉",
                      "unclear": "不明"}
EFFORT_ZH = {"quick": "当天", "evening": "一晚", "multi_day": "数日",
             "not_closable": "补不上"}
VERDICT_ZH = vocab.VERDICT_ZH


def cannot_run(workspace: pathlib.Path, reason: str) -> int:
    """Exactly one receipt on the could-not-run path, then exit 2."""
    print(f"cannot run: {reason}", file=sys.stderr)
    if workspace.is_dir():
        journal.receipt(workspace, GATE, {}, "could_not_run", [f"NO_INPUT: {reason}"])
    return 2


def coverage(rows: list[dict] | None) -> dict:
    counts = {"must_total": 0, "must_strong": 0, "must_partial": 0, "must_gap": 0,
              "must_no_evidence": 0, "resp_total": 0, "resp_demonstrated": 0,
              "invalid": []}
    for index, item in enumerate(rows or []):
        item = item or {}
        identifier = item.get("id", f"#{index + 1}")
        match = item.get("match")
        recency = item.get("recency")
        if match not in MATCHES:
            counts["invalid"].append(
                f"INVALID_MATCH: row {identifier} has match {match!r}, "
                f"not one of {MATCHES}")
            match = None
        if recency not in RECENCIES:
            counts["invalid"].append(
                f"INVALID_RECENCY: row {identifier} has recency {recency!r}, "
                f"not one of {RECENCIES}")
            recency = None
        # Evidence that is only dated satisfies the keyword and reads as rusty to a
        # human, so it lands on partial. `undated` does NOT downgrade: a CV that omits
        # dates is a formatting fact, not a staleness fact.
        effective = "partial" if (match == "strong" and recency == "dated") else match
        kind = item.get("kind")
        if kind == "responsibility":
            counts["resp_total"] += 1
            if effective == "strong":
                counts["resp_demonstrated"] += 1
        elif kind == "must_have":
            counts["must_total"] += 1
            if effective == "strong":
                counts["must_strong"] += 1
            elif effective == "partial":
                counts["must_partial"] += 1
            elif effective == "gap":
                counts["must_gap"] += 1
            elif effective == "no_evidence":
                counts["must_no_evidence"] += 1
        else:
            # Counted into neither total, so the printed numbers still add up and
            # the row simply vanishes. That is why this one has to be reported.
            counts["invalid"].append(
                f"INVALID_KIND: row {identifier} has kind {kind!r}, "
                f"not one of {KINDS}")
    return counts


def render_block(assessment: dict, counts: dict, lang: str = "zh") -> str:
    verdict = assessment.get("verdict", "insufficient_evidence")
    direction = assessment.get("level_direction", "unclear")
    effort = assessment.get("effort", "not_closable")
    if lang == "zh":
        return (
            f"must-have 强证据：   {counts['must_strong']} of {counts['must_total']}   "
            f"（partial {counts['must_partial']}，gap {counts['must_gap']}，"
            f"无证据 {counts['must_no_evidence']}）\n"
            f"核心职责已证实：     {counts['resp_demonstrated']} of {counts['resp_total']}\n"
            f"职级匹配：           {LEVEL_DIRECTION_ZH.get(direction, '不明')}\n"
            f"可补缺口所需投入：   {EFFORT_ZH.get(effort, '补不上')}\n"
            f"投递建议：           {VERDICT_ZH.get(verdict, '证据不足—不出结论')}")
    return (
        f"must-haves strongly evidenced:   {counts['must_strong']} of "
        f"{counts['must_total']}   (partial {counts['must_partial']}, "
        f"gap {counts['must_gap']}, no evidence {counts['must_no_evidence']})\n"
        f"core responsibilities demonstrated: {counts['resp_demonstrated']} of "
        f"{counts['resp_total']}\n"
        f"level match:                     {direction}\n"
        f"effort to close the gaps:        {effort}\n"
        f"apply verdict:                   {verdict}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Count must-have and responsibility "
                                                 "coverage. The only counting path.")
    parser.add_argument("--workspace", required=True, type=pathlib.Path)
    parser.add_argument("--lang", choices=("zh", "en"), default="zh")
    args = parser.parse_args(argv)

    path = args.workspace / "fit-assessment.yaml"
    if not args.workspace.is_dir():
        return cannot_run(args.workspace,
                          f"workspace {args.workspace} does not exist")
    if not path.exists():
        return cannot_run(args.workspace,
                          f"fit-assessment.yaml not found at {path}")

    assessment = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    counts = coverage(assessment.get("requirements"))
    findings = list(counts["invalid"])
    block = render_block(assessment, counts, args.lang)

    payload = dict(counts)
    payload["block_zh"] = render_block(assessment, counts, "zh")
    payload["block_en"] = render_block(assessment, counts, "en")
    (args.workspace / "coverage.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for finding in findings:
        print(finding)
    print(block)
    journal.receipt(args.workspace, GATE,
                    {"fit-assessment.yaml": journal.sha256_file(path)},
                    "fail" if findings else "recorded", findings)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
