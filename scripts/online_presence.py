#!/usr/bin/env python3
"""Ask once for a candidate's public profiles, watch them, confirm, write back.

The record lives at <profile_dir>/online-presence.yaml (scripts/paths.py). Sources
are GitHub, Google Scholar and a personal website; nothing needing a login.
Design: docs/superpowers/specs/2026-11-01-online-presence-design.md.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import sys
import tempfile

import journal
import paths

SOURCES = ("github", "scholar", "website")
ASK_STATUSES = ("given", "none", "declined")
OUTCOMES = ("ok", "refused", "failed", "not_checked")
STALE_DAYS = 14
LINK_KEYS = {"github": "github", "scholar": "scholar", "website": "website"}


def empty_record() -> dict:
    return {"sources": {}, "checks": {}, "findings": [], "writebacks": []}


def load_record(path) -> dict:
    """The record at `path`, or an empty one when absent. Unreadable raises YamlUnreadable."""
    path = pathlib.Path(path)
    if not path.exists():
        return empty_record()
    data = journal.load_yaml(path)
    record = empty_record()
    for key, kind in (("sources", dict), ("checks", dict), ("findings", list), ("writebacks", list)):
        value = data.get(key, record[key])
        if not isinstance(value, kind):
            raise journal.YamlUnreadable(path, f"`{key}` must be a {kind.__name__}")
        record[key] = value
    for key, value in data.items():
        record.setdefault(key, value)
    return record


def save_record(path, record: dict) -> None:
    """Write atomically, so a crash never leaves half a record."""
    import yaml
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".online-presence-", suffix=".yaml")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        yaml.safe_dump(record, fh, allow_unicode=True, sort_keys=False)
    os.replace(tmp, path)


def _seed_from_masters(name: str, record: dict) -> bool:
    """Copy github/scholar/website links a master already holds; True if anything changed."""
    changed = False
    for master in paths.master_profiles(name).values():
        try:
            data = journal.load_yaml(master)
        except journal.YamlUnreadable:
            continue
        links = journal.as_mapping(journal.as_mapping(data.get("contact")).get("links"))
        for source, key in LINK_KEYS.items():
            value = links.get(key)
            if isinstance(value, dict):
                value = value.get("url")
            if source not in record["sources"] and isinstance(value, str) and value.strip():
                record["sources"][source] = {"status": "given", "value": value.strip(),
                                             "words": "from master contact.links",
                                             "date": datetime.date.today().isoformat()}
                changed = True
    return changed


def status(name: str, today: datetime.date) -> dict:
    path = paths.online_presence(name)
    record = load_record(path)
    if _seed_from_masters(name, record):
        save_record(path, record)
    to_ask, stale, broken = [], [], []
    for source in SOURCES:
        answer = journal.as_mapping(record["sources"].get(source))
        if answer.get("status") not in ASK_STATUSES:
            to_ask.append(source)
            continue
        if answer["status"] != "given":
            continue
        check = journal.as_mapping(record["checks"].get(source))
        if check.get("outcome") == "failed" and check.get("code") == 404:
            broken.append(source)
            continue
        try:
            last = datetime.date.fromisoformat(str(check.get("date")))
        except ValueError:
            last = None
        if last is None or (today - last).days > STALE_DAYS:
            stale.append(source)
    return {"to_ask": to_ask, "stale": stale, "broken": broken,
            "shared_with": record.get("shared_with")}


def record_answer(name: str, source: str, status: str, value, words: str,
                  extra: list | None = None) -> None:
    if source not in SOURCES or status not in ASK_STATUSES:
        raise ValueError(f"unknown source/status {source!r}/{status!r}")
    if status == "given" and not (value or "").strip():
        raise ValueError(f"{source}: status given needs the profile value")
    if not (words or "").strip():
        raise ValueError("record the user's own words")
    path = paths.online_presence(name)
    record = load_record(path)
    entry = {"status": status, "value": (value or "").strip() or None, "words": words,
             "date": datetime.date.today().isoformat()}
    if extra:
        entry["extra"] = list(extra)
    record["sources"][source] = entry
    save_record(path, record)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    st = sub.add_parser("status", help="which profiles to ask for, which are stale or broken")
    st.add_argument("--name", required=True)
    st.add_argument("--today")
    st.add_argument("--workspace", type=pathlib.Path)
    rc = sub.add_parser("record", help="store the user's answer for one source")
    rc.add_argument("--name", required=True)
    rc.add_argument("--source", required=True, choices=SOURCES)
    rc.add_argument("--status", required=True, choices=ASK_STATUSES)
    rc.add_argument("--value")
    rc.add_argument("--extra", nargs="*", default=None,
                    help="GitHub organisations or org/repo the profile page does not list")
    rc.add_argument("--words", required=True, help="the user's answer, verbatim")
    args = ap.parse_args(argv)
    try:
        if args.command == "status":
            today = datetime.date.fromisoformat(args.today) if args.today else datetime.date.today()
            result = status(args.name, today)
            if args.workspace is not None:
                journal.append(args.workspace, {"action": "online_presence_status",
                                                "date": today.isoformat(), **result})
            print(json.dumps(result, ensure_ascii=False))
            return 0
        record_answer(args.name, args.source, args.status, args.value, args.words, args.extra)
        return 0
    except journal.YamlUnreadable as exc:
        print(f"ONLINE_PRESENCE_UNREADABLE: {exc}; fix or remove the file — it was not changed",
              file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"ONLINE_PRESENCE_BAD_INPUT: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    from cli_io import configure_output
    configure_output()
    raise SystemExit(main())
