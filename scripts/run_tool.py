#!/usr/bin/env python3
"""Invoke a prepared private tool without shell-profile changes."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from setup_dependencies import SKILL, default_root


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=default_root())
    ap.add_argument("--browser", choices=("chrome", "edge"))
    ap.add_argument("tool", choices=("python", "opencli", "anysearch", "browser", "browser-session"))
    ap.add_argument("args", nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)
    budget_file = None
    runtime = json.loads((args.root.expanduser() / "runtime.json").read_text())
    env = os.environ.copy()
    paths = [str(Path(runtime["python"]).parent)]
    if "node" in runtime:
        paths += [str(Path(runtime["node"]).parent), str(Path(runtime["opencli"]).parents[4] / ".bin")]
    env["PATH"] = os.pathsep.join(paths + [env.get("PATH", "")])
    if (args.tool == 'browser' and '--budget-plan' in args.args
            and os.path.abspath(sys.executable) != os.path.abspath(runtime['python'])):
        # Budget validation uses the prepared Python dependencies, even when
        # this lightweight launcher was invoked with the system Python.
        return subprocess.run([runtime['python'], str(Path(__file__).resolve()),
                               *(sys.argv[1:] if argv is None else argv)], env=env).returncode
    if args.tool == "python":
        command = [runtime["python"]]
    else:
        node = runtime["node"]
        browser = args.browser or runtime.get("browser")

        def session_endpoint():
            if not browser:
                raise ValueError("Select the user's daily browser via --browser chrome|edge")
            probe = subprocess.run([node, str(SKILL / "scripts/browser_session.mjs"),
                "endpoint", "--root", str(args.root.expanduser()), "--browser", browser],
                capture_output=True, text=True)
            if probe.returncode:
                raise ValueError(probe.stderr.strip() + "; use run_tool.py browser-session start once, then keep that session for this task")
            return probe.stdout.strip()

        if args.tool == "opencli":
            # Help/version/offline factory checks need no browser consent.
            offline = not args.args or any(x in args.args for x in ("--help", "-h", "--version", "-V")) or args.args[0] in ("list", "validate")
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
            elif any(x in args.args for x in ('--steps-file', '--click-text')):
                raise ValueError('Navigation requires --workspace, --site and --budget-plan; intermediate catalogs cannot be omitted')
            command = [node, str(SKILL / "scripts/browser_cdp.mjs")]
            if browser:
                command += ["--browser", browser]
            if "--endpoint" not in args.args and "--help" not in args.args:
                command += ["--endpoint", session_endpoint()]
    try:
        if args.tool == 'browser' and 'budget' in locals():
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
                budget_file = Path(f.name)
                json.dump(budget, f, ensure_ascii=False)
            args.args += ['--budget-file', str(budget_file)]
        return subprocess.run(command + args.args, env=env).returncode
    finally:
        if budget_file:
            budget_file.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"TOOL_UNAVAILABLE: {exc}; run scripts/setup_dependencies.py for the needed capability", file=sys.stderr)
        sys.exit(1)
