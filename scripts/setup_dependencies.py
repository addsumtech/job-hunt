#!/usr/bin/env python3
"""Prepare job-hunt's private runtime. Python 3.10+; no bootstrap pip imports.

Default: Python packages for all offline modes and bundled report PDFs.
--discovery: also prepare Node 22+ and pinned CDP-only OpenCLI. No extensions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

from delivery_paths import choose_delivery_root
from runtime_config import default_root, read_runtime, runtime_lock, update_runtime
from fs_paths import ensure_directory

SKILL = Path(__file__).resolve().parent.parent
PATCHES = SKILL / "assets" / "opencli-cdp"


def run(argv, **kwargs):
    return subprocess.run([str(x) for x in argv], check=True, **kwargs)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def extract_archive(archive, dest):
    """Extract regular files only; npm is invoked via its JS entry, not symlinks."""
    def output(name):
        path = PurePosixPath(name.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts or any(":" in x for x in path.parts):
            raise ValueError(f"Unsafe archive path: {name}")
        return dest.joinpath(*path.parts)

    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            entries = [(info, output(info.filename)) for info in z.infolist()]
            for info, target in entries:
                if info.is_dir() or ((info.external_attr >> 16) & 0o170000) == 0o120000:
                    continue
                ensure_directory(target.parent, parents=True)
                with z.open(info) as source, target.open("wb") as out:
                    shutil.copyfileobj(source, out)
    else:
        with tarfile.open(archive) as tar:
            entries = [(info, output(info.name)) for info in tar.getmembers()]
            for info, target in entries:
                if not info.isfile():
                    continue
                ensure_directory(target.parent, parents=True)
                with tar.extractfile(info) as source, target.open("wb") as out:
                    shutil.copyfileobj(source, out)
                target.chmod(info.mode & 0o755)


def node_ok(path):
    if not path:
        return False
    try:
        result = run([path, "-p", "Number(process.versions.node.split('.')[0]) >= 22 && typeof WebSocket === 'function'"], capture_output=True, text=True)
        return result.stdout.strip() == "true"
    except (OSError, subprocess.SubprocessError):
        return False


def download(url, output):
    with urllib.request.urlopen(url, timeout=60) as response, output.open("wb") as dest:
        shutil.copyfileobj(response, dest)


def prepare_node(root, explicit=None):
    candidates = [explicit] if explicit else [shutil.which("node"), *root.glob("node/node-v*/bin/node"), *root.glob("node/node-v*/node.exe")]
    for candidate in candidates:
        if node_ok(candidate):
            return Path(candidate).resolve()
    if explicit:
        raise RuntimeError("The selected Node executable must support Node 22+ and WebSocket")
    system = {"Darwin": "darwin", "Linux": "linux", "Windows": "win"}.get(platform.system())
    arch = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64", "AMD64": "x64"}.get(platform.machine())
    if not system or not arch:
        raise RuntimeError("No bundled Node binary for this OS/architecture; agent must prepare Node 22+")
    with urllib.request.urlopen("https://nodejs.org/dist/index.json", timeout=60) as response:
        releases = json.load(response)
    version = next(r["version"] for r in releases if r["version"].startswith("v22.") and r.get("lts"))
    name = f"node-{version}-{system}-{arch}"
    filename = name + (".zip" if system == "win" else ".tar.gz")
    base = f"https://nodejs.org/dist/{version}/"
    with tempfile.TemporaryDirectory(prefix="node-download-", dir=root) as temp:
        temp = Path(temp)
        download(base + "SHASUMS256.txt", temp / "checksums")
        checksums = dict((line.split()[1].lstrip("*"), line.split()[0]) for line in (temp / "checksums").read_text().splitlines() if line.strip())
        download(base + filename, temp / filename)
        if digest(temp / filename) != checksums[filename]:
            raise RuntimeError("Official Node archive checksum mismatch")
        extract_archive(temp / filename, temp / "extracted")
        install = root / "node" / name
        ensure_directory(install.parent, parents=True)
        if install.exists():
            raise RuntimeError(f"Incomplete Node installation exists; inspect before replacing: {install}")
        shutil.move(str(temp / "extracted" / name), install)
    node = install / ("node.exe" if system == "win" else "bin/node")
    if not node_ok(node):
        raise RuntimeError("Downloaded Node cannot run; inspect OS runtime compatibility")
    return node.resolve()


def npm_entry(node):
    candidates = [node.parent.parent / "lib/node_modules/npm/bin/npm-cli.js",
                  node.parent / "node_modules/npm/bin/npm-cli.js"]
    npm = shutil.which("npm")
    if npm:
        candidates.append(Path(npm).resolve())
    for candidate in candidates:
        if candidate.is_file() and candidate.suffix == ".js":
            return candidate
    raise RuntimeError("Node works but npm is missing; agent must prepare npm or use an official Node distribution")


def patch_opencli(package):
    """Verify every source and replacement before changing the private package."""
    manifest = json.loads((PATCHES / "manifest.json").read_text())
    if json.loads((package / "package.json").read_text())["version"] != manifest["version"]:
        raise RuntimeError("OpenCLI patch version mismatch; existing package left unchanged")
    pending = []
    for entry in manifest["files"]:
        target = package / entry["path"]
        replacement = PATCHES / target.name
        if digest(replacement) != entry["patched"]:
            raise RuntimeError(f"Bundled patch checksum mismatch: {target.name}")
        current = digest(target)
        known = (entry["original"], entry["patched"], *entry.get("previous_patched", []))
        if current not in known:
            raise RuntimeError(f"Unrecognized OpenCLI edits, left unchanged: {entry['path']}")
        if current != entry["patched"]:
            pending.append((target, replacement))
    for target, replacement in pending:
        backup = target.with_name(target.name + ".job-hunt-original")
        if not backup.exists():
            shutil.copy2(target, backup)
        shutil.copy2(replacement, target)


def prepare_opencli(root, node):
    prefix = root / "opencli"
    package = prefix / "node_modules/@jackwener/opencli"
    if not (package / "package.json").exists():
        env = dict(os.environ, PATH=str(node.parent) + os.pathsep + os.environ.get("PATH", ""))
        run([node, npm_entry(node), "install", "--prefix", prefix, "@jackwener/opencli@1.8.7",
             "--ignore-scripts", "--no-audit", "--no-fund"], env=env)
    patch_opencli(package)
    entry = package / "dist/src/main.js"
    run([node, entry, "--version"])
    # Offline identity probe; never instantiate the extension bridge.
    run([node, "--input-type=module", "-e",
         "const r=await import(process.argv[1]);const c=await import(process.argv[2]);if(r.getBrowserFactory('weixin')!==c.CDPBridge)process.exit(1)",
         (package / "dist/src/runtime.js").as_uri(), (package / "dist/src/browser/cdp.js").as_uri()])
    return entry


def python_candidates():
    names = ("python3", *(f"python3.{minor}" for minor in range(15, 9, -1)), "python")
    seen = set()
    base = getattr(sys, "_base_executable", sys.executable)
    for candidate in (base, *(shutil.which(name) for name in names)):
        if candidate:
            executable = Path(candidate).resolve()
            if executable not in seen:
                seen.add(executable)
                yield executable


def prepare_python(root):
    environment = root / "venv"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    def verify():
        run([python, "-I", "-c", "import encodings, ssl, venv"], capture_output=True)

    def ensure_pip():
        run([python, "-I", "-m", "ensurepip", "--upgrade", "--default-pip"], capture_output=True)

    if environment.exists():
        try:
            verify()
            try:
                run([python, "-I", "-c", "import pip"], capture_output=True)
            except subprocess.CalledProcessError:
                ensure_pip()
            return python
        except (OSError, subprocess.SubprocessError):
            shutil.rmtree(environment)

    # Check the child before ensurepip: some standalone Python builds can
    # create a venv whose executable cannot even load the standard library.
    modes = ("--copies",) if os.name == "nt" else ("--copies", "--symlinks")
    for base in python_candidates():
        for mode in modes:
            try:
                run([base, "-I", "-c",
                     "import sys, venv; assert sys.version_info >= (3, 10); "
                     "venv.main(sys.argv[1:])", "--without-pip", mode, environment],
                    capture_output=True)
                verify()
                ensure_pip()
                return python
            except (OSError, subprocess.SubprocessError):
                if environment.exists():
                    shutil.rmtree(environment)

    raise RuntimeError("Could not prepare Python for job-hunt. Install Python 3.12 from python.org "
                       "(or Homebrew on macOS) and rerun setup with that Python.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=default_root())
    ap.add_argument("--discovery", action="store_true")
    ap.add_argument("--node", help="Reuse this Node 22+ executable")
    ap.add_argument("--browser", choices=("chrome", "edge"), help="User's selected daily browser")
    args = ap.parse_args(argv)
    if sys.version_info < (3, 10):
        raise RuntimeError("Agent must prepare Python 3.10+ first")
    root = args.root.expanduser().resolve()
    with runtime_lock(root, ".setup.lock"):
        python = prepare_python(root)
        run([python, "-I", "-m", "pip", "install", "--disable-pip-version-check",
             "-r", SKILL / "requirements.txt"])
        run([python, "-I", "-c", "import yaml, docx, pymupdf"])
        updates = {"python": str(python)}
        if args.discovery:
            node = prepare_node(root, args.node)
            updates.update(node=str(node), opencli=str(prepare_opencli(root, node)))
            run([node, SKILL / "third_party/anysearch/anysearch_cli.js", "doc"], stdout=subprocess.DEVNULL)
        if args.browser:
            updates["browser"] = args.browser
        try:
            folder = choose_delivery_root(read_runtime(root))
        except OSError as exc:
            print(f"Delivery folder: {exc}", file=sys.stderr)
        else:
            updates["delivery_root"] = str(folder)
        runtime = update_runtime(root, updates)
    print(json.dumps({"runtime": str(root / "runtime.json"), "tools": runtime,
                      "delivery_folder": updates.get("delivery_root")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    from cli_io import configure_utf8

    configure_utf8()
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"SETUP_INCOMPLETE: {exc}", file=sys.stderr)
        sys.exit(1)
