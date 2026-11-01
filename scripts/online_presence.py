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
import re
import sys
import tempfile
import urllib.error
import urllib.request

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


GITHUB_API = "https://api.github.com"
REFUSED_CODES = (401, 403, 429)


def http_get(url: str) -> tuple[int, bytes]:
    """GET `url`; (status, body). Never raises: a transport error is (0, b"")."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "job-hunt-online-presence"}
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read() if exc.fp else b""
        except OSError:
            body = b""
        return exc.code, body
    except (urllib.error.URLError, OSError, TimeoutError):
        return 0, b""


class _Stop(Exception):
    def __init__(self, outcome, code):
        self.outcome, self.code = outcome, code


def fetch_github(username: str, extra: list, get) -> dict:
    """Public repositories the user owns or contributed to, as one snapshot.

    Forks, archived repositories and organisation repositories without a commit
    by the user are left out. Any 401/403/429 refuses the whole fetch: a partial
    listing would read as "these are all the repositories".
    """
    raw = []

    def call(url, missing_ok=False):
        status, body = get(url)
        raw.append((url, status, body))
        if status in REFUSED_CODES:
            raise _Stop("refused", status)
        if status == 404 and missing_ok:
            return None
        if status != 200:
            raise _Stop("failed", status or None)
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise _Stop("failed", status)

    user = username.strip().lower()
    candidates, missing = [], []
    try:
        owned = call(f"{GITHUB_API}/users/{username}/repos?per_page=100&type=owner")
        candidates += [(r, "owner") for r in owned or []]
        for item in extra or []:
            item = item.strip().strip("/")
            if "/" in item:
                found = call(f"{GITHUB_API}/repos/{item}", missing_ok=True)
                if found is None:
                    missing.append(item)
                else:
                    candidates.append((found, None))
            elif item:
                listing = call(f"{GITHUB_API}/orgs/{item}/repos?per_page=100", missing_ok=True)
                if listing is None:
                    missing.append(item)
                else:
                    candidates += [(r, None) for r in listing]
        repos, seen = [], set()
        for data, role in candidates:
            full = data.get("full_name")
            if not full or full in seen or data.get("fork") or data.get("archived"):
                continue
            seen.add(full)
            if role is None:
                if str(journal.as_mapping(data.get("owner")).get("login", "")).lower() == user:
                    role = "owner"
                else:
                    people = call(f"{GITHUB_API}/repos/{full}/contributors?per_page=100",
                                  missing_ok=True) or []
                    logins = [str(p.get("login", "")).lower() for p in people if isinstance(p, dict)]
                    if user not in logins:
                        continue
                    role = "top_contributor" if logins[0] == user else "contributor"
            release = call(f"{GITHUB_API}/repos/{full}/releases/latest", missing_ok=True)
            repos.append({
                "full_name": full, "html_url": data.get("html_url"),
                "description": data.get("description"), "created_at": data.get("created_at"),
                "pushed_at": data.get("pushed_at"), "stars": data.get("stargazers_count"),
                "forks": data.get("forks_count"),
                "latest_release": (release or {}).get("tag_name") if isinstance(release, dict) else None,
                "topics": data.get("topics") or [], "role": role})
    except _Stop as stop:
        return {"outcome": stop.outcome, "code": stop.code, "repos": [], "missing_extra": missing,
                "raw": raw}
    return {"outcome": "ok", "code": 200, "repos": repos, "missing_extra": missing, "raw": raw}


def write_snapshot(name: str, source: str, snapshot: dict, today: datetime.date,
                   workspace=None) -> pathlib.Path:
    """Save the snapshot (without raw bodies) and each raw response beside it."""
    base = paths.online_presence_dir(name)
    (base / "snapshots").mkdir(parents=True, exist_ok=True)
    (base / "raw").mkdir(parents=True, exist_ok=True)
    stem = f"{today.isoformat()}-{source}"
    raw_files = []
    for n, (url, status, body) in enumerate(snapshot.get("raw", []), 1):
        rel = f"raw/{stem}-{n}.json"
        (base / rel).write_bytes(json.dumps({"url": url, "status": status}).encode() + b"\n" + body)
        raw_files.append(rel)
    data = {k: v for k, v in snapshot.items() if k != "raw"}
    data.update(source=source, date=today.isoformat(), raw_files=raw_files)
    path = base / "snapshots" / f"{stem}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if workspace is not None:
        journal.append(workspace, {"action": "online_presence_fetch", "source": source,
                                   "outcome": data.get("outcome"), "code": data.get("code"),
                                   "snapshot": str(path), "date": today.isoformat()})
    return path


_VENUE_YEAR = re.compile(r"^(?P<venue>.+?),\s*(?P<year>(?:19|20)\d{2})$")
_SCHOLAR_HEADERS = {"title", "cited by", "year", "show more", "articles", "cited by year"}


def _capture_outcome(data: dict) -> tuple[str, int | None]:
    """ok / refused / failed for a browser capture, using the shared stop signals."""
    status = data.get("http_status")
    code = status if isinstance(status, int) else None
    if data.get("blocked") or code in REFUSED_CODES:
        return "refused", code
    text = str(data.get("text") or "")
    import check_opencli_result
    for signal in check_opencli_result.load_signals(check_opencli_result.DEFAULT_SIGNALS_FILE):
        if signal["regex"].search(text):
            return "refused", code
    if code is not None and code >= 400:
        return "failed", code
    if not text.strip():
        return "failed", code
    return "ok", code or 200


def _read_capture(path) -> dict:
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: a browser capture is a JSON object")
    return data


def ingest_scholar(capture) -> dict:
    """Papers listed on a captured Google Scholar profile page.

    The page text lists each article as three lines: title, authors, then
    "venue, year". Papers whose author line has no comma (a single author) are
    not recognised; the diff then simply proposes nothing for them.
    """
    data = _read_capture(capture)
    outcome, code = _capture_outcome(data)
    if outcome != "ok":
        return {"outcome": outcome, "code": code, "papers": []}
    lines = [line.strip() for line in str(data.get("text", "")).splitlines() if line.strip()]
    papers, i = [], 0
    while i + 2 < len(lines):
        title, authors, venue_line = lines[i], lines[i + 1], lines[i + 2]
        match = _VENUE_YEAR.match(venue_line)
        if (match and "," in authors and not _VENUE_YEAR.match(authors)
                and title.lower() not in _SCHOLAR_HEADERS and not title.isdigit()):
            papers.append({"title": title, "authors": authors,
                           "venue": match.group("venue").strip(), "year": int(match.group("year"))})
            i += 3
        else:
            i += 1
    return {"outcome": "ok", "code": code, "papers": papers}


def ingest_website(capture) -> dict:
    data = _read_capture(capture)
    outcome, code = _capture_outcome(data)
    if outcome != "ok":
        return {"outcome": outcome, "code": code, "url": data.get("url"), "text": ""}
    return {"outcome": "ok", "code": code, "url": data.get("url"), "text": data.get("text")}


def note_check(name: str, source: str, snapshot_path, outcome: str, code, today: datetime.date) -> None:
    """Remember the latest check of `source` in the record."""
    path = paths.online_presence(name)
    record = load_record(path)
    record["checks"][source] = {"date": today.isoformat(), "outcome": outcome, "code": code,
                                "snapshot": str(snapshot_path)}
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
    ig = sub.add_parser("ingest", help="turn a Scholar or website capture into a snapshot")
    ig.add_argument("--name", required=True)
    ig.add_argument("--source", required=True, choices=("scholar", "website"))
    ig.add_argument("--capture", required=True, type=pathlib.Path)
    ig.add_argument("--workspace", type=pathlib.Path)
    ig.add_argument("--today")
    args = ap.parse_args(argv)
    try:
        if args.command == "ingest":
            today = datetime.date.fromisoformat(args.today) if args.today else datetime.date.today()
            if not args.capture.is_file():
                print(f"ONLINE_PRESENCE_MISSING_INPUT: capture {args.capture} does not exist",
                      file=sys.stderr)
                return 2
            reader = ingest_scholar if args.source == "scholar" else ingest_website
            snapshot = reader(args.capture)
            snapshot["raw"] = [(snapshot.get("url") or str(args.capture), snapshot.get("code"),
                                args.capture.read_bytes())]
            path = write_snapshot(args.name, args.source, snapshot, today, workspace=args.workspace)
            note_check(args.name, args.source, path, snapshot["outcome"], snapshot.get("code"), today)
            print(json.dumps({"source": args.source, "outcome": snapshot["outcome"],
                              "snapshot": str(path)}, ensure_ascii=False))
            return 0
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
    except (ValueError, UnicodeDecodeError) as exc:
        print(f"ONLINE_PRESENCE_BAD_INPUT: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    from cli_io import configure_output
    configure_output()
    raise SystemExit(main())
