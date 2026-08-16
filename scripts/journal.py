#!/usr/bin/env python3
"""The append-only run journal, the receipt every gate leaves in it, and the one
reader that keeps a malformed input file from skipping both.

Risk-register #12: a gate that was skipped produces no output, and no output
looks exactly like a clean run. So each gate writes one receipt here before it
exits — on every exit path, including the "could not run" one — and a mode may
not claim success without quoting its receipts. The receipt carries the hashes
of what the gate actually read, so "the gate passed" is a claim about specific
bytes rather than about a moment in time.

`load_yaml` lives here rather than in paths.py because it exists FOR that
contract, not as a general YAML utility: its whole job is to turn the three ways
a file can be unusable into the could-not-run receipt above. paths.py is pure
path arithmetic and says so; a reader who found a file-parsing function there
would reasonably conclude the two modules were interchangeable.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import pathlib

import yaml

# The closed set a receipt's verdict may take. The last two are NOT synonyms and
# the difference is load-bearing:
#
#   "recorded"          — the gate ran and has no pass/fail to report. The
#                         assess-mode reporters (consistency, count_coverage,
#                         check_evidence_refs, evidence_blocks) and parse_verdicts
#                         on a cleanly-parsed round. A clean CHECK.
#   "baseline_recorded" — the `--record` half of a two-step gate: it stored a
#                         fingerprint for a later comparison and verified nothing.
#                         SETUP, not a check.
#
# They shared the token "recorded" until 2026-08. check_apply.py treated it as
# passing — correctly, for the reporters — so a workspace that ran only the
# documented mode-entry setup satisfied the one gate whose entire job is proving
# the checks ran, and re-running the setup after a real failure erased it.
VERDICTS = ("pass", "fail", "could_not_run", "recorded", "baseline_recorded")


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

    `verdict` is one of `VERDICTS` above: "pass" | "fail" | "could_not_run" |
    "recorded" | "baseline_recorded" — read that comment before picking one, the
    last two mean different things. `mode`
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


# --------------------------------------------------------------- reading YAML input

# The code every gate prints and journals when an input file is present and
# unusable. Deliberately NOT "NO_INPUT", which the same gates use for a file that
# is absent: a reader told NO_INPUT goes looking for a file that is right there,
# and "the file could not be parsed" is a different instruction from "the file
# says something wrong".
UNREADABLE_INPUT = "UNREADABLE_INPUT"


class YamlUnreadable(Exception):
    """An input file could not be turned into the document shape a gate expects.

    Carries `.path`, `.reason` and `.finding` — the last already prefixed with
    UNREADABLE_INPUT, so a gate routing this into its cannot_run path does not
    have to re-spell the code and cannot spell it differently from its neighbour.
    """

    def __init__(self, path, reason: str):
        self.path = pathlib.Path(path)
        self.reason = reason
        super().__init__(f"{self.path}: {reason}")

    @property
    def finding(self) -> str:
        return f"{UNREADABLE_INPUT}: {self.path}: {self.reason}"


_EMPTY = {dict: "mapping", list: "list"}


def load_yaml(path, expect: type = dict):
    """Parse a YAML file into `expect` (dict or list), or raise YamlUnreadable.

    WHY THIS EXISTS — reproduced 2026-08-16, and worth reading before anyone
    "simplifies" it back to `yaml.safe_load(path.read_text(...)) or {}`. On a
    workspace whose fit-assessment.yaml had one unclosed quote:

        consistency          exit=1   (a yaml parse traceback)
        count_coverage       exit=1   (a yaml parse traceback)
        journal.jsonl        2 lines  — only from the gates that exited 2 cleanly

    In this repo's contract exit 1 means "the gate ran and found problems". So a
    caller reading exit codes was told there were findings, a caller reading the
    journal saw nothing, and check_apply — whose whole composition rule is reading
    those receipts — saw a gate that never ran. The one state the journal exists to
    make visible was the one state that produced no journal line. There were 25
    `yaml.safe_load` call sites and 8 of them caught YAMLError.

    Three failures land in that same place and all three are handled here:

      * the document does not parse (yaml.YAMLError);
      * the file cannot be read at all — absent, unreadable, not UTF-8 (OSError,
        UnicodeDecodeError);
      * the document parses to a string or a list where a mapping is expected, so
        the caller's very next `.get()` raises AttributeError.

    An empty or comment-only file is NOT one of those: it yields the empty mapping
    (or list), which is what every call site's `or {}` meant and what the callers
    downstream are written against.

    The caller catches YamlUnreadable and routes it to its own cannot_run / exit-2
    path, so the workspace-does-not-exist exception stays where each gate documents
    it: nothing to append to, stderr only, no receipt.
    """
    if expect not in _EMPTY:
        raise ValueError(f"expect must be dict or list, not {expect!r}")
    path = pathlib.Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise YamlUnreadable(path, f"is not valid UTF-8 ({exc.reason})") from exc
    except OSError as exc:
        raise YamlUnreadable(
            path, f"could not be read ({exc.strerror or exc})") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        detail = " ".join(str(exc).split())
        raise YamlUnreadable(path, f"did not parse as YAML ({detail})") from exc
    if data is None:
        return expect()
    if not isinstance(data, expect):
        raise YamlUnreadable(
            path,
            f"parses to a {type(data).__name__}, not a {_EMPTY[expect]} — "
            f"the gate reads named fields off it and cannot read them off this")
    return data
