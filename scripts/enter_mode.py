#!/usr/bin/env python3
"""Record entering a mode, and the exact bytes of the mode file that was loaded.

modes/*.md is layer 1.5: loaded unconditionally on entering the mode, not "if
relevant". That distinction is only real if something reports its absence — a
reference file skipped is a silent deletion, which is the failure this whole
layering exists to avoid. So the mode's own gate requires this record, and
requires the hash to still match the file on disk.

Exit 0 = entered. Exit 2 = the mode file does not exist; a `mode_entry_failed`
record is written first, because a failed entry that left no trace looks exactly
like an entry nobody attempted — the same silence the record exists to break.

Usage: python3 scripts/enter_mode.py --workspace W --mode apply
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import journal
import paths

MODES = ("discover", "assess", "apply", "interview")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def latest_mode_entry(workspace, mode: str):
    path = pathlib.Path(workspace) / "journal.jsonl"
    if not path.exists():
        return None
    found = None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict) and rec.get("action") == "mode_entry" \
                and rec.get("mode") == mode:
            found = rec
    return found


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--mode", required=True, choices=MODES)
    ap.add_argument("--skill-root", default=None)
    args = ap.parse_args(argv)
    root = pathlib.Path(args.skill_root) if args.skill_root else paths.SKILL_ROOT
    path = paths.mode_file(args.mode, root)
    ws = pathlib.Path(args.workspace)
    if not path.exists():
        journal.append(ws, {
            "ts": _now(),
            "action": "mode_entry_failed",
            "mode": args.mode,
            "mode_file": f"modes/{args.mode}.md",
            "reason": f"{path} does not exist",
        })
        print(f"cannot enter mode {args.mode}: {path} does not exist", file=sys.stderr)
        return 2
    journal.append(ws, {
        "ts": _now(),
        "action": "mode_entry",
        "mode": args.mode,
        "mode_file": f"modes/{args.mode}.md",
        "mode_file_sha256": journal.sha256_file(path),
    })
    print(f"entered mode {args.mode}; read {path} in full before doing anything else")
    return 0


if __name__ == "__main__":
    sys.exit(main())
