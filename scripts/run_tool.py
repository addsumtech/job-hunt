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
    ap.add_argument("tool", choices=("python", "opencli", "anysearch", "browser"))
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
        if args.tool == "opencli":
            browser = args.browser or runtime.get("browser")
            # Help/version/offline factory checks need no browser consent.
            offline = not args.args or any(x in args.args for x in ("--help", "-h", "--version", "-V")) or args.args[0] in ("list", "validate")
            if not offline:
                if not browser:
                    raise ValueError("Select the user's daily browser via --browser chrome|edge")
                probe = subprocess.run([node, "--input-type=module", "-e",
                    "const m=await import(process.argv[1]);console.log(await m.dailyEndpoint(process.argv[2]));",
                    (SKILL / "scripts/browser_cdp.mjs").as_uri(), browser], check=True, capture_output=True, text=True)
                env["OPENCLI_CDP_ENDPOINT"] = probe.stdout.strip()
            command = [node, runtime["opencli"]]
        elif args.tool == "anysearch":
            command = [node, str(SKILL / "third_party/anysearch/anysearch_cli.js")]
        else:
            command = [node, str(SKILL / "scripts/browser_cdp.mjs")]
            browser = args.browser or runtime.get("browser")
            if browser:
                command += ["--browser", browser]
    return subprocess.run(command + args.args, env=env).returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"TOOL_UNAVAILABLE: {exc}; run scripts/setup_dependencies.py for the needed capability", file=sys.stderr)
        sys.exit(1)
