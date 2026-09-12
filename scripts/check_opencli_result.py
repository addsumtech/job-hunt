#!/usr/bin/env python3
"""Classify one opencli adapter invocation. A wrapper, not a gate.

Exit codes here are deliberately NOT the gate contract:
  0 = classified; one JSON object printed to stdout
  2 = could not classify (workspace or stdout file missing)
A `not_logged_in` adapter is information the discover mode acts on, not a
failure of the run, so it must not exit 1.

THE ONE RULE: branch on the exit code BEFORE interpreting stdout. A login wall
gives exit 1, EMPTY stdout and a YAML error body on stderr even under -f json
(measured 2026-08-09 on 1point3acres), so `JSON.parse(stdout || '[]')` silently
converts a 403 into a zero-result success.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import yaml  # noqa: E402

import journal  # noqa: E402  (Plan 1)
import paths    # noqa: E402  (Plan 1)  — SKILL_ROOT lives here, not in __file__ math

ADAPTER_CALL_ACTION = "adapter_call"

CLASSIFICATIONS = ("ok", "platform_limit", "not_logged_in", "no_auth_adapter",
                   "transport")

# The column that makes a search row self-sufficient. Measured from
# `opencli <site> --help -f yaml` columns on 2026-08-09: boss calls it `name`,
# everyone else calls it `title`.
IDENTITY_FIELD = {"boss": "name"}
IDENTITY_FIELD_DEFAULT = "title"

# The documented command that recovers a row whose identity field came back
# empty. Measured from the same help output.
DETAIL_COMMAND = {
    "51job": "opencli 51job detail <jobId>",
    "indeed": "opencli indeed job <id>",
    "boss": "opencli boss detail <security_id>",
    "linkedin": "opencli linkedin job-detail <job-url>",
    "upwork": "opencli upwork detail <id>",
    "nowcoder": "opencli nowcoder detail <id>",
    "1point3acres": "opencli 1point3acres thread <tid>",
}

# A refusal that means "you are not signed in". Checked BEFORE the risk-control
# signals so that the measured 403 resolves against `opencli auth status`
# rather than being swallowed as a generic platform limit.
# One Chinese phrase and three English ones meant `请先登录后查看`,
# `ログインが必要です`, `로그인이 필요합니다` and `Bitte melden Sie sich an` all fell
# through to `classification: transport`, whose remedy diagnoses the connection —
# when the correct remedy is to hand the user `opencli <site> login`. A wrong
# remedy costs more than no remedy: it sends them to debug a working adapter.
#
# The CJK entries carry no `\b`: there is no word boundary between 登录 and the
# character beside it.
LOGIN_WALL_PATTERNS = (
    re.compile(r"HTTP 40[13]\b"),
    re.compile(r"\bForbidden\b", re.I),
    re.compile(r"\bUnauthorized\b", re.I),
    re.compile(r"\blogin required\b", re.I),
    re.compile(r"\bnot logged in\b", re.I),
    # The prefix is REQUIRED. Bare `sign in` matched "500 Internal Server Error
    # while loading your sign in preferences page" and "Connection reset while
    # rendering the 'Log In' navbar link" — genuine transport faults routed to
    # "run opencli <site> login", which is the wrong-remedy failure this list
    # exists to prevent, just pointing the other way.
    re.compile(r"\b(?:please|you must|you need to|must|to continue,?)\s+"
               r"(?:sign|log)\s?in\b", re.I),
    re.compile(r"\b(?:sign|log)\s?in\s+(?:is\s+)?(?:required|to view|to continue|"
               r"to access)\b", re.I),
    re.compile(r"\bauthentication (?:required|failed)\b", re.I),
    re.compile(r"\bsession (?:expired|invalid)\b", re.I),
    re.compile(r"登录|登入|登錄|登陆|未登录|請先登入"),
    re.compile(r"ログイン|サインイン|認証が必要"),
    re.compile(r"로그인|인증이 필요"),
    # German separable verb: "anmelden" appears as "melden Sie sich an", so the
    # dictionary form alone matches nothing a site actually prints.
    re.compile(r"\banmeld(?:en|ung)\b|\bnicht angemeldet\b"
               r"|\bmelden Sie sich\b.{0,12}\ban\b", re.I),
    re.compile(r"\binloggen\b|\bniet ingelogd\b", re.I),
    re.compile(r"\bconnexion requise\b|\bveuillez vous connecter\b", re.I),
)

DEFAULT_SIGNALS_FILE = paths.SKILL_ROOT / "references" / "risk-control-signals.yaml"


def load_signals(path):
    """Compile references/risk-control-signals.yaml into matchers.

    Raises journal.YamlUnreadable, which main() turns into exit 2. An empty matcher
    list on a file that failed to parse would be the worst outcome available here:
    every risk-control signal would stop matching and the classifier would report
    `ok` on a login wall.
    """
    if path is None:
        raise journal.YamlUnreadable(DEFAULT_SIGNALS_FILE, "stop-signal file was not supplied")
    data = journal.load_yaml(path)
    entries = data.get("signals")
    if not isinstance(entries, list) or not entries:
        raise journal.YamlUnreadable(path, "signals must be a non-empty list")
    out = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("pattern"), str) or not entry["pattern"]:
            raise journal.YamlUnreadable(path, "each signal requires a non-empty pattern string")
        pattern = entry["pattern"]
        try:
            matcher = re.compile(pattern)
        except re.error as exc:
            raise journal.YamlUnreadable(path, f"invalid stop-signal pattern: {exc}") from exc
        out.append({
            "id": entry.get("id") or pattern,
            "site": entry.get("site") or "*",
            "verified": bool(entry.get("verified")),
            "regex": matcher,
        })
    return out


def _auth_state(site, auth_rows):
    """'logged_in' | 'not_logged_in' | 'unknown' | 'absent' | 'unchecked'.

    Never reads row['logged_in']: on an `unknown` row that field is an EMPTY
    STRING, not false, so `if not row['logged_in']` misreads it as logged out.
    """
    if auth_rows is None:
        return "unchecked"
    for row in auth_rows:
        if isinstance(row, dict) and row.get("site") == site:
            status = row.get("status")
            if status in ("logged_in", "not_logged_in", "unknown"):
                return status
            return "unknown"
    return "absent"


def _error_message(stderr_text):
    text = (stderr_text or "").strip()
    if not text:
        return ""
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError:
        return text
    if isinstance(parsed, dict):
        err = parsed.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
    return text


def _error_code(stderr_text):
    try:
        body = yaml.safe_load(stderr_text or "")
    except yaml.YAMLError:
        return None
    error = body.get("error") if isinstance(body, dict) else None
    return error.get("code") if isinstance(error, dict) else None


def recovery_guidance(kind="platform"):
    """Operator guidance only: a user reply is required, never a retry token."""
    actions = {
        "login": "Ask the user to finish login in the connected browser.",
        "verification": "Ask the user to open the site in the connected browser and complete the human verification themselves; do not describe it as a missing login.",
        "rate_limit": "Explain the rate limit and any displayed wait time; login is not a fix. Do not poll or automatically retry after a timer.",
        "platform": "Ask the user to inspect the site in the connected browser: complete login or human verification only if the page asks for it. A permission or account restriction may not be fixable by logging in.",
    }
    return (actions[kind] + " Pause this source and keep the retrieved results. "
            "Wait for explicit user confirmation that the required action is done "
            "and they want to continue; elapsed time is not confirmation. Then "
            "start one new bounded round linked to the paused workspace, using "
            "the same source and backend, and verify access with one read. "
            "Preserve the old journal; never clear its stop lock. If refused "
            "again, pause and ask again. Offer partial results, other sources "
            "or a pasted posting instead of silently abandoning the task. "
            "See references/user-recovery.md.")


def classify(site, command, exit_code, stdout_text, stderr_text,
             auth_rows=None, signals=()):
    """Classify one invocation. Returns a JSON-serialisable dict."""
    result = {
        "site": site,
        "command": command,
        "exit_code": exit_code,
        "classification": None,
        "row_count": 0,
        "empty_result": False,
        "identity_field": IDENTITY_FIELD.get(site, IDENTITY_FIELD_DEFAULT),
        "empty_identity_rows": [],
        "needs_detail_recovery": False,
        "detail_command": DETAIL_COMMAND.get(site),
        "auth_state": _auth_state(site, auth_rows),
        "signal_id": None,
        "error_message": None,
        "remedy": None,
    }

    # ---- exit code first, always -------------------------------------
    if exit_code != 0:
        message = _error_message(stderr_text)
        result["error_message"] = message

        # A machine-readable refusal remains a refusal when its English wording
        # changes. Measured on 51job 1.8.7: ANTI_BOT / Aliyun WAF slider, which
        # matched none of the old Chinese-only slider patterns.
        if _error_code(stderr_text) == "ANTI_BOT":
            result["classification"] = "platform_limit"
            result["signal_id"] = "opencli-anti-bot"
            result["remedy"] = (
                "OpenCLI reported ANTI_BOT. Stop this site for this round: "
                "do not retry, refresh the session, or switch tools to route around it. "
                + recovery_guidance("verification"))
            return result

        # Matched against the WHOLE stderr of the failed call, not just the
        # message we extracted from it. `references/risk-control-signals.yaml`
        # states the rule that way for a reason: a real risk-control body puts
        # the wall in a `body:`/`detail:` field while `message:` stays generic,
        # and a search over `message` alone would classify that as `transport`
        # and let the round carry on. Searching stderr cannot cry wolf either —
        # a successful call has EMPTY stderr, and we are already inside the
        # `exit_code != 0` branch.
        haystack = f"{message}\n{stderr_text or ''}"
        for signal in signals:
            if signal["site"] in ("*", site) and signal["regex"].search(haystack):
                result["classification"] = "platform_limit"
                result["signal_id"] = signal["id"]
                result["remedy"] = (
                    f"platform stop-signal {signal['id']!r} matched. Stop this "
                    "site for this round: do not retry, do not change "
                    "parameters and retry, do not route around it. "
                    + recovery_guidance("rate_limit" if signal["id"] in {
                        "http-429-rate-limited", "too-frequent-cn"}
                        else "verification" if signal["id"] in {
                            "indeed-cloudflare-challenge", "verify-human-en",
                            "captcha-interstitial", "slider-verification-cn",
                            "security-verification-cn"} else "platform")
                )
                return result


        if any(p.search(message) for p in LOGIN_WALL_PATTERNS):
            state = result["auth_state"]
            if state == "absent":
                result["classification"] = "no_auth_adapter"
                result["remedy"] = (
                    f"{site} has no auth adapter — it is absent from "
                    f"`opencli auth status` and `opencli {site} login` does not "
                    "exist. Do not invent a login command or assume the browser "
                    "session is missing. Stop this site for this round. "
                    + recovery_guidance()
                )
            elif state == "logged_in":
                result["classification"] = "platform_limit"
                result["remedy"] = (
                    "auth status says logged_in and the site still refused. "
                    "Treat it as a platform control. Stop this site for this "
                    "round: do not retry, do not change parameters and retry, "
                    "do not route around it. " + recovery_guidance()
                )
            elif state == "unknown":
                result["classification"] = "not_logged_in"
                result["remedy"] = (
                    "auth status returned `unknown` (its logged_in field is an "
                    "EMPTY STRING, not false). Re-probe before concluding "
                    f"anything: opencli auth status --site {site} --full "
                    "--timeout 40 -f json, then classify again. "
                    + recovery_guidance("login")
                )
            else:
                result["classification"] = "not_logged_in"
                result["remedy"] = (
                    f"Hand `opencli {site} login` to the user to run — it is a "
                    "write command and this skill never runs one. Do not retry "
                    "the read: the refusal is deterministic while logged out. "
                    + recovery_guidance("login")
                )
                if state == "unchecked":
                    result["remedy"] += (
                        " Auth state was not supplied; run `opencli auth status "
                        f"--site {site} --full -f json` first."
                    )
            return result

        result["classification"] = "transport"
        result["remedy"] = (
            "Unrecognised failure. Check the selected daily-browser CDP session "
            "and the offline website routing probe in `scripts/doctor.py`; "
            "follow `references/network-recovery.md`. Preserve the error and "
            "inspect the actual page before concluding that the adapter is broken. "
            "Do not run an extension-oriented health probe."
        )
        return result

    # ---- exit 0: only NOW may stdout be interpreted -------------------
    try:
        rows = json.loads(stdout_text)
    except (json.JSONDecodeError, TypeError):
        result["classification"] = "transport"
        result["remedy"] = (
            "Exit 0 but stdout is not JSON. Preserve the output and check the "
            "selected daily-browser CDP session and offline website routing "
            "with `scripts/doctor.py`; follow `references/network-recovery.md` "
            "before any bounded retry. Do not run an extension-oriented health probe."
        )
        return result
    if not isinstance(rows, list):
        result["classification"] = "transport"
        result["remedy"] = "exit 0 but stdout was not a JSON array"
        return result

    # Measured 2026-09-09: Indeed's detail adapter returns exit 0 and the
    # sign-in heading as a job title, with an empty company and description.
    # Match the observed shape, not login words in legitimate job prose.
    if site == "indeed" and command in {"job", "detail", "view"} and any(
        isinstance(row, dict)
        and str(row.get("title") or "").strip().casefold()
            == "ready to take the next step?"
        and not str(row.get("company") or "").strip()
        and not str(row.get("description") or "").strip()
        for row in rows
    ):
        result["classification"] = "not_logged_in"
        result["signal_id"] = "indeed-sign-in-interstitial"
        result["error_message"] = "Indeed returned its sign-in page instead of a job detail"
        result["remedy"] = (
            "Stop this site for this round. Do not count the sign-in page as a "
            "job or retry the read. Indeed has no OpenCLI login command. "
            + recovery_guidance("login"))
        return result

    result["classification"] = "ok"
    result["row_count"] = len(rows)
    result["empty_result"] = not rows

    field = result["identity_field"]
    result["empty_identity_rows"] = [
        index for index, row in enumerate(rows)
        if not isinstance(row, dict) or not str(row.get(field, "")).strip()
    ]
    if result["empty_identity_rows"]:
        result["needs_detail_recovery"] = True
        result["remedy"] = (
            f"{len(result['empty_identity_rows'])} of {len(rows)} rows came back "
            f"with an empty `{field}`. Recover each one with "
            f"`{result['detail_command']}` and report the gap. The rows exist — "
            "never read blank fields as 'this site has no such jobs'."
        )
    return result


def read_journal(workspace):
    """Every journal line, in order, each carrying `_lineno`.

    An unparsable line comes back as {"_lineno": n, "_unparsable": raw} rather
    than being dropped: a write command hidden in a malformed line must stay
    visible to check_no_write.py.
    """
    path = pathlib.Path(workspace) / "journal.jsonl"
    if not path.is_file():
        return []
    records = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError:
            records.append({"_lineno": lineno, "_unparsable": stripped})
            continue
        if not isinstance(record, dict):
            records.append({"_lineno": lineno, "_unparsable": stripped})
            continue
        record["_lineno"] = lineno
        records.append(record)
    return records


def read_adapter_calls(workspace):
    return [r for r in read_journal(workspace)
            if r.get("action") == ADAPTER_CALL_ACTION]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Classify one opencli adapter invocation (wrapper, not a gate)."
    )
    parser.add_argument("--workspace", required=True, type=pathlib.Path)
    parser.add_argument("--site", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--exit-code", required=True, type=int)
    parser.add_argument("--stdout-file", required=True, type=pathlib.Path)
    parser.add_argument("--stderr-file", type=pathlib.Path)
    parser.add_argument("--auth-status-file", type=pathlib.Path)
    parser.add_argument("--signals-file", type=pathlib.Path,
                        default=DEFAULT_SIGNALS_FILE)
    parser.add_argument("--command-line", default="")
    args = parser.parse_args(argv)

    if not args.workspace.is_dir():
        print(f"workspace not found: {args.workspace}", file=sys.stderr)
        return 2
    if args.exit_code == 0 and not args.stdout_file.is_file():
        print(f"stdout file not found: {args.stdout_file}", file=sys.stderr)
        return 2

    stdout_text = (args.stdout_file.read_text(encoding="utf-8", errors="replace")
                   if args.stdout_file.is_file() else "")
    stderr_text = ""
    if args.stderr_file and args.stderr_file.is_file():
        stderr_text = args.stderr_file.read_text(encoding="utf-8", errors="replace")

    auth_rows = None
    if args.auth_status_file and args.auth_status_file.is_file():
        try:
            loaded = json.loads(args.auth_status_file.read_text(encoding="utf-8"))
            auth_rows = loaded if isinstance(loaded, list) else None
        except json.JSONDecodeError:
            auth_rows = None

    # Not a gate — this wrapper appends an adapter_call record, never a receipt — so
    # exit 2 and a message on stderr is the whole of "could not run" available here.
    try:
        signals = load_signals(args.signals_file)
    except journal.YamlUnreadable as exc:
        print(f"{journal.UNREADABLE_INPUT}: {exc}", file=sys.stderr)
        return 2

    result = classify(args.site, args.command, args.exit_code, stdout_text,
                      stderr_text, auth_rows, signals)

    record = dict(result)
    record["action"] = ADAPTER_CALL_ACTION
    record["ts"] = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    record["stdout_file"] = str(args.stdout_file)
    record["stderr_file"] = str(args.stderr_file) if args.stderr_file else None
    record["command_line"] = args.command_line
    journal.append(args.workspace, record)

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    from cli_io import configure_output

    configure_output()
    raise SystemExit(main())
