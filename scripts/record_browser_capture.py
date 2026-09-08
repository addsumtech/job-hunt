#!/usr/bin/env python3
"""Import an actual web-access snapshot; never execute arbitrary browser code.

Records are tamper-evident, not proof of origin or of unjournaled actions.
Exit 0: recorded (including a site refusal); 2: invalid input, nothing recorded.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys
from urllib.parse import urlsplit

import journal
from check_opencli_result import read_journal

ACTION = "browser_call"
REASONS = ("cli_missing", "bridge_disconnected", "unsupported_extraction")
STOP_CLASSES = {"platform_limit", "not_logged_in", "no_auth_adapter"}
# Look for actual wall language, not an ordinary navigation link saying Login.
WALL = re.compile(
    r"(?:enter|complete|solve) (?:the |this |a )?captcha|verify (?:that )?you are (?:a )?human|access denied|too many requests|"
    r"please (?:sign|log) in|(?:sign|log) in (?:required|to continue|to view)|"
    r"(?:请输入|请完成|请填写).{0,12}验证码|验证您是人类|访问受限|访问过于频繁|请先登[录入]|"
    r"認証が必要|ログインが必要|로그인이 필요|접근이 제한", re.I)


def web_url(value):
    if not isinstance(value, str) or any(c.isspace() for c in value):
        return False
    try:
        parsed = urlsplit(value)
        return (parsed.scheme in {"http", "https"} and bool(parsed.hostname)
                and parsed.username is None and parsed.password is None)
    except ValueError:
        return False


def validate_snapshot(snapshot, rows):
    if not isinstance(snapshot, dict) or not isinstance(rows, list):
        raise ValueError("snapshot must be an object and rows must be an array")
    if not web_url(snapshot.get("url")) or not isinstance(snapshot.get("text"), str):
        raise ValueError("snapshot requires an HTTP(S) url and original text")
    stamp = snapshot.get("retrieved_at")
    if not isinstance(stamp, str):
        raise ValueError("snapshot requires retrieved_at with a timezone")
    try:
        parsed = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid retrieved_at") from exc
    if parsed.tzinfo is None:
        raise ValueError("retrieved_at must include a timezone")
    links = snapshot.get("links")
    if not isinstance(links, list) or any(not web_url(u) for u in links):
        raise ValueError("links must be an array of original HTTP(S) URLs")
    status = snapshot.get("http_status")
    if status is not None and (type(status) is not int or not 100 <= status <= 599):
        raise ValueError("http_status must be an HTTP status integer or null")
    blocked = snapshot.get("blocked", False)
    if type(blocked) is not bool:
        raise ValueError("blocked must be boolean")
    if blocked or status in (401, 403, 429) or WALL.search(snapshot["text"]):
        if rows:
            raise ValueError("site refusal must have no extracted rows")
        return "platform_limit"
    if status is not None and status >= 400:
        raise ValueError("HTTP failure is not a successful page capture")
    urls = set(links) | {snapshot["url"]}
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("each row must be an object")
        for key in ("source_id", "url", "title", "raw_text"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError(f"each row requires {key}")
        if row["url"] not in urls:
            raise ValueError("row URL is absent from the snapshot")
        if len(row["source_id"]) < 4 or not any(
                row["source_id"] in s for s in [snapshot["text"], *urls]):
            raise ValueError("source_id is absent from the snapshot or too short")
        if row["raw_text"] not in snapshot["text"] or row["title"] not in row["raw_text"]:
            raise ValueError("title/card text must be copied verbatim from the snapshot")
        if row["source_id"] in seen:
            raise ValueError("duplicate source_id in capture")
        seen.add(row["source_id"])
    return "ok"


def check_stop_order(records):
    stopped = set()
    findings = []
    for record in records:
        if record.get("action") not in ("adapter_call", ACTION):
            continue
        site = str(record.get("site") or "").strip().lower()
        if site in stopped:
            findings.append(f"READ_AFTER_STOP: {site} was read after a site refusal; changing tools does not reset the round")
        if record.get("classification") in STOP_CLASSES:
            stopped.add(site)
    return findings


def validate_record(record, workspace):
    """Fail closed on unknown actions, altered metadata or missing raw files."""
    findings = []
    if (record.get("backend") != "web-access" or record.get("operation") != "snapshot"
            or record.get("command") not in ("search", "detail")
            or record.get("fallback_reason") not in REASONS
            or record.get("command_line")
            or not journal.receipt_intact({k: v for k, v in record.items() if k != "_lineno"})):
        return ["INVALID_BROWSER_RECORD: expected an intact read-only snapshot import"]
    root = pathlib.Path(workspace).resolve()
    try:
        files = []
        for key in ("snapshot_file", "rows_file"):
            name = record[key]
            path = (root / name).resolve()
            if (not isinstance(name, str) or not name.startswith("raw/")
                    or path.parent != root / "raw"
                    or not path.name.startswith(record["site"] + "-")):
                raise ValueError("capture must be a site-prefixed file directly under raw/")
            if journal.sha256_file(path) != record["input_hashes"][name]:
                raise ValueError("capture hash changed")
            files.append(json.loads(path.read_text(encoding="utf-8")))
        snapshot, rows = files
        classification = validate_snapshot(snapshot, rows)
        if (type(record["row_count"]) is not int
                or type(record["exit_code"]) is not int):
            raise ValueError("counts and exit code must be integers")
        if (classification != record["classification"] or len(rows) != record["row_count"]
                or record["exit_code"] != (0 if classification == "ok" else 1)
                or record["retrieved_at"] != snapshot["retrieved_at"]
                or record["url"] != snapshot["url"]
                or type(record["page"]) is not int or record["page"] < 1
                or not isinstance(record["query"], str)
                or (record["command"] == "search" and not record["query"].strip())):
            raise ValueError("capture metadata does not match the recorded result")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        findings.append(f"INVALID_BROWSER_CAPTURE: {exc}")
    return findings


def read_retrieval_calls(workspace):
    return [r for r in read_journal(workspace)
            if r.get("action") in ("adapter_call", ACTION)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=pathlib.Path)
    parser.add_argument("--site", required=True)
    parser.add_argument("--command", choices=("search", "detail"), default="search")
    parser.add_argument("--snapshot-file", required=True, type=pathlib.Path)
    parser.add_argument("--rows-file", required=True, type=pathlib.Path)
    parser.add_argument("--fallback-reason", choices=REASONS, required=True)
    parser.add_argument("--query", default="")
    parser.add_argument("--page", type=int, default=1)
    args = parser.parse_args(argv)
    try:
        if not args.workspace.is_dir():
            raise ValueError("workspace does not exist")
        if not re.fullmatch(r"[a-z0-9_]+", args.site):
            raise ValueError("site must be a stable lowercase source name without hyphens")
        if args.page < 1 or (args.command == "search" and not args.query.strip()):
            raise ValueError("search requires a query and page must be positive")
        paths = [args.snapshot_file.resolve(), args.rows_file.resolve()]
        root = args.workspace.resolve()
        if paths[0] == paths[1] or any(
                p.parent != root / "raw" or not p.name.startswith(args.site + "-")
                or p.suffix != ".json" for p in paths):
            raise ValueError("use two distinct raw/<site>-*.json files inside the workspace")
        snapshot, rows = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
        classification = validate_snapshot(snapshot, rows)
        # Check before recording; do not turn an already-stopped site into a
        # newly successful backend. Malformed prior lines fail closed too.
        records = read_journal(root)
        if any("_unparsable" in r for r in records):
            raise ValueError("journal contains an unparsable line")
        if check_stop_order(records + [{"action": ACTION, "site": args.site}]):
            raise ValueError("READ_AFTER_STOP: site already stopped in this round")
        record = {
            "action": ACTION, "backend": "web-access", "operation": "snapshot",
            "mode": journal.current_mode(root), "site": args.site,
            "command": args.command, "fallback_reason": args.fallback_reason,
            "query": args.query, "page": args.page,
            "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
            "url": snapshot["url"], "retrieved_at": snapshot["retrieved_at"],
            "classification": classification, "row_count": len(rows),
            "exit_code": 0 if classification == "ok" else 1,
            "empty_result": classification == "ok" and not rows,
            "identity_field": "title", "empty_identity_rows": [],
            "needs_detail_recovery": False, "detail_command": None,
            "snapshot_file": str(paths[0].relative_to(root)),
            "rows_file": str(paths[1].relative_to(root)),
            "input_hashes": {str(p.relative_to(root)): journal.sha256_file(p) for p in paths},
        }
        record = journal.sign_receipt(record)
        journal.append(root, record)
        print(json.dumps(record, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f"INVALID_BROWSER_CAPTURE: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
