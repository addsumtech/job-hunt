"""Private installation must preserve existing tools and use bundled clients."""
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import setup_dependencies as setup
import run_tool


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'C:\\escape'])
@pytest.mark.parametrize('kind', ['zip', 'tar'])
def test_archive_rejects_escaping_paths_before_writing(tmp_path, name, kind):
    archive = tmp_path / 'archive'
    if kind == 'zip':
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('safe/file', 'ok')
            z.writestr(name, 'bad')
    else:
        with tarfile.open(archive, 'w') as t:
            for member in ('safe/file', name):
                item = tarfile.TarInfo(member)
                item.size = 3
                t.addfile(item, io.BytesIO(b'bad'))
    with pytest.raises(ValueError, match='Unsafe'):
        setup.extract_archive(archive, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_archive_does_not_follow_symlinks(tmp_path):
    archive = tmp_path / 'archive.tar'
    with tarfile.open(archive, 'w') as t:
        link = tarfile.TarInfo('bin/link')
        link.type = tarfile.SYMTYPE
        link.linkname = '../../outside'
        t.addfile(link)
        file = tarfile.TarInfo('bin/node')
        file.mode = 0o755
        file.size = 2
        t.addfile(file, io.BytesIO(b'OK'))
    setup.extract_archive(archive, tmp_path / 'out')
    assert not (tmp_path / 'out/bin/link').exists()
    assert (tmp_path / 'out/bin/node').read_bytes() == b'OK'


def test_patch_checks_all_files_before_mutating_and_is_idempotent(tmp_path, monkeypatch):
    assets = tmp_path / 'assets'
    assets.mkdir()
    package = tmp_path / 'package'
    package.mkdir()
    (package / 'package.json').write_text('{"version":"test"}')
    entries = []
    for name in ('a.js', 'b.js'):
        (package / name).write_text('original')
        (assets / name).write_text('patched')
        entries.append(dict(path=name, original=setup.digest(package / name), patched=setup.digest(assets / name)))
    (assets / 'manifest.json').write_text(json.dumps(dict(version='test', files=entries)))
    monkeypatch.setattr(setup, 'PATCHES', assets)
    (package / 'b.js').write_text('custom')
    with pytest.raises(RuntimeError, match='Unrecognized'):
        setup.patch_opencli(package)
    assert (package / 'a.js').read_text() == 'original'
    assert not list(package.glob('*.job-hunt-original'))
    (package / 'b.js').write_text('original')
    setup.patch_opencli(package)
    setup.patch_opencli(package)
    assert (package / 'a.js').read_text() == 'patched'
    assert (package / 'a.js.job-hunt-original').read_text() == 'original'


def test_tool_wrapper_preserves_paths_arguments_and_needs_no_global_cli(tmp_path, monkeypatch):
    root = tmp_path / 'root with spaces'
    root.mkdir()
    runtime = {'python':'/runtime with spaces/bin/python', 'node':'/node with spaces/bin/node',
               'opencli':'/private/node_modules/@jackwener/opencli/dist/src/main.js'}
    (root / 'runtime.json').write_text(json.dumps(runtime))
    calls=[]
    monkeypatch.setattr(run_tool.subprocess, 'run', lambda cmd, **kw: calls.append((cmd, kw)) or subprocess.CompletedProcess(cmd,0))
    assert run_tool.main(['--root',str(root),'anysearch','search','data science jobs']) == 0
    cmd, kw = calls[0]
    assert cmd == [runtime['node'],str(setup.SKILL/'third_party/anysearch/anysearch_cli.js'),'search','data science jobs']
    assert '/private/node_modules/.bin' in kw['env']['PATH']


def test_bundled_clients_run_without_installed_skills():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node unavailable')
    result = subprocess.run([node, str(setup.SKILL/'third_party/anysearch/anysearch_cli.js'), 'doc'], capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    assert 'batch_search' in result.stdout
    result = subprocess.run([node, '--test', str(Path(__file__).with_name('browser-cdp.test.mjs')), str(Path(__file__).with_name('browser-session.test.mjs'))], capture_output=True,text=True)
    assert result.returncode == 0, result.stdout + result.stderr
