#!/usr/bin/env python3
"""Check/apply/revert known OpenCLI local-override patches. Never contacts a site."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

MANIFEST = Path(__file__).resolve().parents[1] / 'references/opencli-patches/1.8.7.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def installed_package():
    executable = shutil.which('opencli')
    if not executable:
        raise ValueError('OpenCLI is not installed; this helper does not install it.')
    for parent in Path(executable).resolve().parents:
        metadata = parent / 'package.json'
        if metadata.is_file():
            if json.loads(metadata.read_text()).get('name') == '@jackwener/opencli':
                return parent
    raise ValueError('Cannot locate the OpenCLI package; supply --package-dir.')


def prepare(package, config, site, action, manifest):
    metadata = json.loads((package / 'package.json').read_text())
    if (metadata.get('name'), metadata.get('version')) != (manifest['package'], manifest['version']):
        raise ValueError('Unsupported OpenCLI version. Diagnose the installed adapter; do not force this patch.')
    changes, states = [], []
    entries = [item for item in manifest['files'] if item['path'].split('/')[0] == site]
    if not entries:
        raise ValueError(f'No compatibility patch for {site}')
    for item in entries:
        relative = Path(item['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe patch path')
        original = (package / 'clis' / relative).read_bytes()
        if digest(original) != item['base_sha256']:
            raise ValueError(f'Official adapter has changed: {relative}; no files were modified.')
        patched = original.decode('utf-8')
        for replacement in item['replacements']:
            if patched.count(replacement['old']) != 1:
                raise ValueError(f'Patch anchor mismatch: {relative}')
            patched = patched.replace(replacement['old'], replacement['new'])
        patched = patched.encode('utf-8')
        if digest(patched) != item['patched_sha256']:
            raise ValueError(f'Patch checksum mismatch: {relative}')
        local = config / 'clis' / relative
        if local.is_symlink() or local.parent.is_symlink():
            raise ValueError(f'Refusing a symlinked local adapter: {relative}')
        if not local.exists():
            states.append({'file': str(relative), 'state': 'needs_eject'})
            if action != 'check':
                raise ValueError(f'Run opencli adapter eject {site} first; existing overrides are never replaced.')
            continue
        current = local.read_bytes()
        previous = digest(current) in item.get('previous_patched_sha256', [])
        if current not in (original, patched) and not previous:
            raise ValueError(f'Local edits detected: {relative}; preserve them and review manually.')
        state = 'patched' if current == patched else 'previous_patch' if previous else 'original'
        states.append({'file': str(relative), 'state': state})
        desired = original if action == 'revert' else patched
        if action != 'check' and current != desired:
            changes.append((local, current, desired))
    return changes, states


def replace_file(path, data):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
        temporary.chmod(path.stat().st_mode)
        temporary.replace(path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def execute(changes):
    completed = []
    try:
        for path, original, patched in changes:
            # Do not overwrite an edit made since preflight.
            if path.read_bytes() != original:
                raise ValueError(f'Adapter changed during patching: {path}')
            replace_file(path, patched)
            completed.append((path, original))
    except Exception:
        for path, original in reversed(completed):
            replace_file(path, original)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', required=True, choices=['indeed', '51job'])
    parser.add_argument('--action', choices=['check', 'apply', 'revert'], default='check')
    parser.add_argument('--package-dir', type=Path)
    parser.add_argument('--config-dir', type=Path,
                        default=Path(os.environ.get('OPENCLI_CONFIG_DIR', str(Path.home() / '.opencli'))))
    args = parser.parse_args(argv)
    try:
        package = args.package_dir or installed_package()
        manifest = json.loads(MANIFEST.read_text())
        override = args.config_dir / 'clis' / args.site
        if args.action == 'apply' and not override.exists() and not override.is_symlink():
            # Check version and every affected official file BEFORE creating an
            # override. copytree refuses an existing destination; never eject
            # over user files. Copy sibling utilities needed by these adapters.
            prepare(package, args.config_dir, args.site, 'check', manifest)
            shutil.copytree(package / 'clis' / args.site, override)
        changes, states = prepare(package, args.config_dir, args.site, args.action, manifest)
        execute(changes)
        print(json.dumps({'site': args.site, 'action': args.action,
                          'before': states, 'files_changed': len(changes)}))
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f'OPENCLI_COMPAT: {exc}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
