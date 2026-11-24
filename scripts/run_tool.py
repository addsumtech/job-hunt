#!/usr/bin/env python3
"""Invoke a prepared private tool without shell-profile changes."""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import uuid

from fs_paths import ensure_directory
from runtime_config import default_root
from setup_dependencies import SKILL


class RuntimeMissing(ValueError):
    """Setup has not prepared a required tool."""


def run_prepared(command, **kwargs):
    try:
        return subprocess.run(command, **kwargs)
    except FileNotFoundError as exc:
        if exc.filename == command[0]:
            raise RuntimeMissing(f"Prepared executable is missing: {exc.filename}") from exc
        raise


def login_handoff(output, browser):
    try:
        rows = json.loads(output)
    except ValueError:
        # OpenCLI's default table output omits the logged_in column.
        sites = re.findall(r"^│\s*([\w-]+)\s*│\s*not_logged_in\s*│[^│\n]*│\s*full\s*│",
                           output.decode("utf-8", errors="replace"), re.MULTILINE)
    else:
        sites = [row["site"] for row in rows if isinstance(row, dict)
                 and row.get("status") == "not_logged_in" and row.get("checked") == "full"
                 and isinstance(row.get("site"), str)] if isinstance(rows, list) else []
    if sites:
        names = ", ".join("BOSS直聘" if site == "boss" else site for site in sites)
        window = "Chrome" if browser == "chrome" else "Edge"
        print(f"SITE_LOGIN_HANDOFF: Full login check: {names}. If a site is needed for "
              "this search, make the login handoff your next message to the user. "
              f"Name the site and their usual {window} window, ask them to click 登录 "
              "and reply ‘已登录’. Wait for their reply before searching any other source. "
              "Continue with public sources if they explicitly ask to skip login.",
              file=sys.stderr)


class SessionUnavailable(ValueError):
    """A browser connection needs recovery, with wording for the user."""

    def __init__(self, detail, browser):
        super().__init__(detail)
        self.browser = "Chrome" if browser == "chrome" else "Edge"

    def handoff(self):
        detail = str(self)
        if ("Do not reconnect automatically" in detail
                or detail.startswith("The browser session was stopped.")):
            return (f"Tell the user now: “和{self.browser}的连接已中断。请保持平时用的"
                    f"{self.browser}窗口打开。准备好后回复‘继续找岗位’，我会接着处理。”")
        if "chrome://inspect/#remote-debugging" in detail:
            return ("Tell the user now: “请在你平时用的 Chrome 窗口打开 "
                    "chrome://inspect/#remote-debugging，勾选‘允许此浏览器实例进行远程调试’"
                    "（以页面上的文字为准），然后回复‘已开启’。”")
        if "waiting_for_consent" in detail:
            lead = "Check status once. If it still waits for consent, tell the user now: "
        else:
            lead = ("Follow the session recovery above. If no session has started, start it once. "
                    "When it waits for consent, tell the user now: ")
        return (lead + f"“请在你平时用的{self.browser}窗口找到连接提示，点‘允许’"
                       "（以弹窗上的按钮文字为准）。点完回复‘已允许’，我就继续找岗位。”"
                       " Send this request on its own and wait for the reply.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=default_root())
    ap.add_argument("--browser", choices=("chrome", "edge"))
    ap.add_argument("--workspace", type=Path, help="owning discovery round; preregister its source plan")
    ap.add_argument("tool", choices=("python", "opencli", "anysearch", "browser", "browser-session"))
    ap.add_argument("args", nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)
    if args.workspace is not None:
        # The launcher must still start on an old system Python, so it does not
        # go through cli_io; it refuses a workspace inside the skill directly.
        import paths
        reason = paths.skill_workspace_refusal(args.workspace)
        if reason:
            print(reason, file=sys.stderr)
            return 2
    budget_file = None
    record = args.root.expanduser() / "runtime.json"
    try:
        runtime = json.loads(record.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeMissing(f"Runtime configuration is missing: {record}") from exc
    if not isinstance(runtime, dict):
        raise ValueError(f"Expected a JSON object in {record}")
    required = ("python",) if args.tool == "python" else ("python", "node", "opencli")
    missing = [name for name in required if not runtime.get(name)]
    if missing:
        raise RuntimeMissing(f"Runtime is missing: {', '.join(missing)}")
    env = os.environ.copy()
    paths = [str(Path(runtime["python"]).parent)]
    if runtime.get("node") and runtime.get("opencli"):
        paths += [str(Path(runtime["node"]).parent), str(Path(runtime["opencli"]).parents[4] / ".bin")]
    env["PATH"] = os.pathsep.join(paths + [env.get("PATH", "")])
    env["JOBHUNT_RUNTIME_ROOT"] = str(args.root.expanduser())
    if ((args.workspace or (args.tool == 'browser' and '--budget-plan' in args.args))
            and os.path.abspath(sys.executable) != os.path.abspath(runtime['python'])):
        # Budget validation uses the prepared Python dependencies, even when
        # this lightweight launcher was invoked with the system Python.
        return run_prepared([runtime['python'], str(Path(__file__).resolve()),
                               *(sys.argv[1:] if argv is None else argv)], env=env).returncode
    if args.tool == "python":
        command = [runtime["python"]]
    else:
        node = runtime["node"]
        browser = args.browser or runtime.get("browser")

        def session_endpoint():
            if not browser:
                raise ValueError("Select the user's daily browser via --browser chrome|edge")
            probe = run_prepared([node, str(SKILL / "scripts/browser_session.mjs"),
                "endpoint", "--root", str(args.root.expanduser()), "--browser", browser],
                capture_output=True, encoding="utf-8", errors="replace")
            if probe.returncode:
                raise SessionUnavailable(probe.stderr.strip(), browser)
            return probe.stdout.strip()

        if args.tool == "opencli":
            # Help/version/offline factory checks need no browser consent.
            offline = not args.args or any(x in args.args for x in ("--help", "-h", "--version", "-V")) or args.args[0] in ("list", "validate")
            if args.workspace and not offline:
                from search_capture import preflight
                from opencli_meta import access_for
                if len(args.args) < 2:
                    raise ValueError('Recorded OpenCLI reads require site and command')
                preflight(args.workspace, args.args[0])
                if not args.args[0].replace('_', '').isalnum():
                    raise ValueError('Invalid OpenCLI source name')
                cache = args.workspace.resolve() / 'raw' / 'opencli-help'
                ensure_directory(cache, parents=True)
                metadata = run_prepared([node, runtime['opencli'], args.args[0], '--help', '-f', 'yaml'],
                                          capture_output=True, env=env)
                if metadata.returncode:
                    raise ValueError('Cannot verify OpenCLI command access')
                (cache / (args.args[0] + '.yaml')).write_bytes(metadata.stdout)
                if access_for(args.args[0], args.args[1], cache, False) != 'read':
                    raise ValueError('Recorded discovery commands must publish access: read')
            if not offline:
                env["OPENCLI_CDP_ENDPOINT"] = session_endpoint()
            command = [node, runtime["opencli"]]
        elif args.tool == "anysearch":
            command = [node, str(SKILL / "third_party/anysearch/anysearch_cli.js")]
        elif args.tool == "browser-session":
            if not browser:
                raise ValueError("Select the user's daily browser via --browser chrome|edge")
            action = args.args[0] if args.args else "status"
            command = [node, str(SKILL / "scripts/browser_session.mjs"), action,
                       "--root", str(args.root.expanduser()), "--browser", browser]
            args.args = args.args[1:]
        else:
            # The wrapper owns round consumption. A caller supplies only DOM
            # contracts, never a self-declared remaining allowance.
            if '--budget-file' in args.args:
                raise ValueError('Use --budget-plan; remaining allowance is derived from the journal')
            if '--budget-plan' in args.args:
                from record_browser_capture import read_retrieval_calls, validate_record, check_stop_order
                from browser_budget import prepare
                def take(flag, remove=True):
                    if args.args.count(flag) != 1:
                        raise ValueError(f'{flag} is required with --budget-plan')
                    i = args.args.index(flag)
                    if i + 1 >= len(args.args):
                        raise ValueError(f'{flag} requires a value')
                    value = args.args[i + 1]
                    if remove:
                        del args.args[i:i + 2]
                    return value
                workspace, site = Path(take('--workspace')).resolve(), take('--site')
                from search_capture import preflight
                preflight(workspace, site, take('--url', False))
                plan = json.loads(Path(take('--budget-plan')).read_text())
                output = Path(take('--output', False)).resolve()
                if (output.parent != workspace / 'raw' or not output.name.startswith(site + '-')
                        or output.suffix != '.json' or output.exists()):
                    raise ValueError('Budgeted output must be raw/<site>-*.json in its round')
                calls = read_retrieval_calls(workspace)
                url = take('--url', False)
                if check_stop_order(calls + [{'action':'browser_call', 'site':site, 'url':url}]):
                    raise ValueError('READ_AFTER_STOP: resolve the source refusal before resuming')
                budget = prepare(workspace, site, plan, calls, validate_record)
            elif args.workspace:
                from search_capture import preflight
                if any(x in args.args for x in ('--steps-file', '--click-text')):
                    raise ValueError('Navigation requires --budget-plan; a workspace alone cannot account for intermediate catalogs')
                if '--site' not in args.args or '--url' not in args.args or '--output' not in args.args:
                    raise ValueError('Recorded browser reads require --site, --url and --output')
                i = args.args.index('--site')
                site = args.args[i + 1]
                del args.args[i:i + 2]
                workspace = args.workspace.resolve()
                output = Path(args.args[args.args.index('--output') + 1]).resolve()
                if output.parent != workspace / 'raw' or not output.name.startswith(site + '-') or output.exists():
                    raise ValueError('Browser output must be a new raw/<site>-*.json in its owning round')
                preflight(workspace, site, args.args[args.args.index('--url') + 1])
            elif any(x in args.args for x in ('--steps-file', '--click-text')):
                raise ValueError('Navigation requires --workspace, --site and --budget-plan; intermediate catalogs cannot be omitted')
            command = [node, str(SKILL / "scripts/browser_cdp.mjs")]
            if browser:
                command += ["--browser", browser]
            if "--endpoint" in args.args and env.get("CODEBUDDY_SANDBOX_BROKER_EXECUTION_ATTEMPT_ID"):
                raise ValueError("WorkBuddy browser reads must use the shared browser session. Omit --endpoint.")
            if "--endpoint" not in args.args and "--help" not in args.args:
                env["JOBHUNT_SHARED_CDP_ENDPOINT"] = session_endpoint()
                command += ["--endpoint", env["JOBHUNT_SHARED_CDP_ENDPOINT"]]
    try:
        if args.workspace and args.tool == 'anysearch':
            from search_capture import run
            return run(args.workspace, command, args.args, env, execute=run_prepared)
        if args.workspace and args.tool == 'opencli' and not offline:
            from check_opencli_result import main as record_opencli
            root = args.workspace.resolve()
            prefix = args.args[0] + '-' + uuid.uuid4().hex
            out, err = root / 'raw' / (prefix + '.json'), root / 'raw' / (prefix + '.stderr.txt')
            result = run_prepared(command + args.args, env=env, capture_output=True)
            out.write_bytes(result.stdout)
            err.write_bytes(result.stderr)
            classification = io.StringIO()
            with contextlib.redirect_stdout(classification):
                status = record_opencli(['--workspace', str(root), '--site', args.args[0],
                    '--command', args.args[1], '--exit-code', str(result.returncode),
                    '--stdout-file', str(out), '--stderr-file', str(err),
                    '--command-line', shlex.join(['opencli', *args.args])])
            print(classification.getvalue(), end='', file=sys.stderr)
            print(out.read_text(encoding='utf-8', errors='replace'), end='')
            print(err.read_text(encoding='utf-8', errors='replace'), end='', file=sys.stderr)
            return status
        if args.tool == 'browser' and 'budget' in locals():
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
                budget_file = Path(f.name)
                json.dump(budget, f, ensure_ascii=False)
            args.args += ['--budget-file', str(budget_file)]
        if (args.tool == "opencli" and not offline and args.args[:2] == ["auth", "status"]
                and "--full" in args.args):
            result = run_prepared(command + args.args, env=env, stdout=subprocess.PIPE)
            sys.stdout.buffer.write(result.stdout)
            if result.returncode == 0:
                login_handoff(result.stdout, browser)
            return result.returncode
        return run_prepared(command + args.args, env=env).returncode
    finally:
        if budget_file:
            budget_file.unlink(missing_ok=True)


if __name__ == "__main__":
    from cli_io import configure_utf8

    configure_utf8()
    try:
        sys.exit(main())
    except SessionUnavailable as exc:
        print(f"BROWSER_SESSION_UNAVAILABLE: {exc}", file=sys.stderr)
        print(exc.handoff(), file=sys.stderr)
        sys.exit(1)
    except RuntimeMissing as exc:
        print(f"TOOL_UNAVAILABLE: {exc}. Run scripts/setup_dependencies.py "
              "(add --discovery for browser and search tools).", file=sys.stderr)
        sys.exit(1)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"TOOL_UNAVAILABLE: {exc}", file=sys.stderr)
        sys.exit(1)
