#!/usr/bin/env python3
"""Read the current application round and next step without changing the workspace."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shlex
import sys

from cli_io import configure_output
import journal
from parse_verdicts import JUDGES, parse_judge
from rounds import load_round


def hashes_match(workspace, hashes):
    return bool(hashes) and all((workspace / name).is_file()
                                and journal.sha256_file(workspace / name) == digest
                                for name, digest in hashes.items())


def command(workspace, script, *args):
    return shlex.join(["python3", "scripts/run_tool.py", "python", f"scripts/{script}.py",
                       "--workspace", str(workspace), *args])


def status(workspace):
    numbers = [int(match[1]) for path in workspace.glob("judge-round-*.json")
               if (match := re.fullmatch(r"judge-round-([1-9]\d*)\.json", path.name))]
    number = max(numbers, default=1)
    info = {"workspace": str(workspace), "mode": journal.current_mode(workspace),
            "round": number}
    for names, step in (
        (("posting.yaml",), "Resume the posting step in modes/apply.md."),
        (("master-fingerprint.json",), "Resolve and fingerprint the source profile in modes/apply.md, Step 1."),
        (("tailored-profile.yaml",), "Resume tailoring in modes/apply.md, Step 4."),
    ):
        missing = [name for name in names if not (workspace / name).is_file()]
        if missing:
            return dict(info, missing=missing, next=step)

    dispatch = journal.as_mapping(load_round(workspace, number).get("dispatch"))
    hashes = dispatch.get("input_hashes") or {}
    if not isinstance(hashes, dict) or not hashes_match(workspace, hashes):
        return dict(info, dispatch="missing or stale",
                    next="Use the pre-dispatch gates and --record command in modes/apply.md.")

    info["dispatch"] = "current"
    round_args = ("--round", str(number))
    freshness = command(workspace, "check_render_freshness", *round_args)
    if "cv.md" in hashes:
        flags = [judge.replace("_", "-") for judge in JUDGES]
        transcripts = {flag: workspace / f"judge-{number}-{flag}.txt" for flag in flags}
        verdicts = {flag: parse_judge(path.read_text(encoding="utf-8"))["verdict"]
                    if path.is_file() else "missing" for flag, path in transcripts.items()}
        info["transcripts"] = verdicts
        if any(verdict in {"missing", "AMBIGUOUS"} for verdict in verdicts.values()):
            return dict(info, next="Check existing review tasks. Collect missing replies or re-dispatch "
                                   "ambiguous reviews using the current dispatch inputs.")
        receipts = journal.read_receipts(workspace, "parse_verdicts")
        latest = receipts[-1] if receipts else {}
        parsed_inputs = latest.get("input_hashes", {})
        if (not journal.receipt_intact(latest) or latest.get("round") != number
                or not hashes_match(workspace, parsed_inputs)
                or set(parsed_inputs) != {path.name for path in transcripts.values()}):
            args = [arg for flag, path in transcripts.items() for arg in (f"--{flag}", str(path))]
            return dict(info, next=command(workspace, "parse_verdicts", *round_args, *args))
        if latest.get("verdict") != "recorded":
            return dict(info, next="Read the latest parse_verdicts findings and resolve the failed review.")
        if "REJECT" in verdicts.values():
            return dict(info, next="Read the reviewers' feedback and follow the REJECT sequence "
                                   "or honest-gap stop in modes/apply.md.")

    receipts = journal.read_receipts(workspace, "check_render_freshness")
    latest = receipts[-1] if receipts else {}
    if (not journal.receipt_intact(latest) or latest.get("verdict") != "pass"
            or latest.get("input_hashes") != hashes):
        return dict(info, next=freshness)
    return dict(info, next=command(workspace, "check_apply"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    workspace = parser.parse_args(argv).workspace.expanduser().resolve()
    if not workspace.is_dir():
        parser.error(f"workspace does not exist: {workspace}")
    try:
        print(json.dumps(status(workspace), ensure_ascii=False, indent=2))
    except (OSError, ValueError) as exc:
        print(f"APPLY_STATUS_UNAVAILABLE: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    configure_output()
    sys.exit(main())
