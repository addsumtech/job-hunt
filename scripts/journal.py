#!/usr/bin/env python3
"""The append-only run journal, and the receipt every gate leaves in it.

Risk-register #12: a gate that was skipped produces no output, and no output
looks exactly like a clean run. So each gate writes one receipt here before it
exits — on every exit path, including the "could not run" one — and a mode may
not claim success without quoting its receipts. The receipt carries the hashes
of what the gate actually read, so "the gate passed" is a claim about specific
bytes rather than about a moment in time.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import pathlib


def append(workspace, record: dict) -> None:
    """Append one JSON record as a line to <workspace>/journal.jsonl."""
    workspace = pathlib.Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    with open(workspace / "journal.jsonl", "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _records(workspace):
    """Every parseable JSON record in the journal, oldest first."""
    path = pathlib.Path(workspace) / "journal.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue          # a half-written line must not blind the reader
        if isinstance(rec, dict):
            out.append(rec)
    return out


def current_mode(workspace) -> str:
    """The mode of the most recent mode_entry record, or "unknown".

    Read from the journal, never guessed. The obvious alternative — an
    environment variable with a default — is worse than useless here: nothing
    in any mode sets it, so every receipt written by discover, assess and
    interview would be stamped with the default and a journal read months later
    would be confidently wrong about which mode produced which evidence.
    "unknown" is the honest answer when nothing recorded an entry, and it is
    also the shape check_apply's NO_MODE_ENTRY finding exists to catch.
    """
    mode = "unknown"
    for rec in _records(workspace):
        if rec.get("action") == "mode_entry" and rec.get("mode"):
            mode = str(rec["mode"])
    return mode


def receipt(workspace, gate: str, input_hashes: dict, verdict: str,
            findings=None) -> dict:
    """Build, journal and return one gate receipt.

    `verdict` is one of "pass" | "fail" | "could_not_run" | "recorded". `mode`
    is read from the latest mode_entry record in this workspace's journal
    (see current_mode) rather than passed in, because the gate signature is
    fixed by the shared contract and does not carry it.
    """
    record = {
        "ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": current_mode(workspace),
        "action": "gate",
        "gate": gate,
        "input_hashes": dict(input_hashes or {}),
        "verdict": verdict,
        "findings": list(findings or []),
    }
    payload = json.dumps(record, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"))
    record["receipt_hash"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    append(workspace, record)
    return record


def read_receipts(workspace, gate: str | None = None) -> list:
    """Every gate receipt in the journal, oldest first, optionally one gate."""
    return [rec for rec in _records(workspace)
            if rec.get("action") == "gate"
            and (gate is None or rec.get("gate") == gate)]
