#!/usr/bin/env python3
"""Invoke a prepared private tool without shell-profile changes."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from setup_dependencies import SKILL, default_root


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=default_root())
    ap.add_argument("--browser", choices=("chrome", "edge"))
    ap.add_argument("tool", choices=("python", "opencli", "anysearch", "browser", "browser-session"))
    ap.add_argument("args", nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)
    runtime = json.loads((args.root.expanduser() / "runtime.json").read_text())
    env = os.environ.copy()
    paths = [str(Path(runtime["python"]).parent)]
    if "node" in runtime:
        paths += [str(Path(runtime["node"]).parent), str(Path(runtime["opencli"]).parents[4] / ".bin")]
    env["PATH"] = os.pathsep.join(paths + [env.get("PATH", "")])
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
            command = [node, str(SKILL / "scripts/browser_cdp.mjs")]
            if browser:
                command += ["--browser", browser]
            if "--endpoint" not in args.args and "--help" not in args.args:
                command += ["--endpoint", session_endpoint()]
    return subprocess.run(command + args.args, env=env).returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"TOOL_UNAVAILABLE: {exc}; run scripts/setup_dependencies.py for the needed capability", file=sys.stderr)
        sys.exit(1)
