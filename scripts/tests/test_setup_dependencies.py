"""Private installation must preserve existing tools and use bundled clients."""
from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import setup_dependencies as setup
import run_tool
from delivery_paths import choose_delivery_root, writable
from fs_paths import ensure_directory


def test_delivery_probe_can_create_without_deleting(tmp_path, monkeypatch):
    home = tmp_path / "home"
    downloads = home / "Downloads"
    downloads.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    original = tempfile.NamedTemporaryFile

    @contextmanager
    def no_delete(*args, **kwargs):
        with original(*args, **kwargs, delete=False) as probe:
            yield probe
        raise PermissionError("host refuses to remove the probe")

    def deny_unlink(*args, **kwargs):
        pytest.fail("probing a delivery directory must never delete a file")

    with monkeypatch.context() as patch:
        patch.setattr(tempfile, "NamedTemporaryFile", no_delete)
        patch.setattr(Path, "unlink", deny_unlink)
        assert choose_delivery_root({}) == downloads.resolve()
        assert choose_delivery_root({}) == downloads.resolve()
    assert list(downloads.iterdir()) == [downloads / ".jobhunt-write-probe"]


def test_no_writable_delivery_folder_asks_for_a_full_path(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    def deny_open(path, *args, **kwargs):
        raise PermissionError(f"host refuses to write to {path}")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", deny_open)
        assert not writable(tmp_path)[0]
        with pytest.raises(OSError) as error:
            choose_delivery_root({})
    for folder in ("Downloads", "Documents/job-hunt", "job-hunt"):
        assert str(tmp_path.resolve() / folder) in str(error.value)
    assert "完整路径" in str(error.value)
    assert "deliver.py --to" in str(error.value)
    assert not list(tmp_path.rglob(".jobhunt-write-probe*"))


def test_ensure_directory_tolerates_a_race_but_refuses_files(tmp_path, monkeypatch):
    original = Path.mkdir
    calls = []

    def broker_mkdir(path, *, parents=False):
        calls.append(path)
        if not path.exists():
            original(path, parents=parents)
        raise FileExistsError(path)

    directory, file = tmp_path / "folder", tmp_path / "file"
    file.touch()
    with monkeypatch.context() as patch:
        patch.setattr(Path, "mkdir", broker_mkdir)
        ensure_directory(directory)
        ensure_directory(directory)
        with pytest.raises(FileExistsError):
            ensure_directory(file)
    assert calls == [directory, file]
    assert directory.is_dir() and file.is_file()


@pytest.mark.parametrize("leftover", [False, True])
def test_setup_replaces_a_broken_venv_before_installing_packages(tmp_path, monkeypatch,
                                                            capsys, leftover):
    root = tmp_path / "runtime"
    environment = root / "venv"
    home = tmp_path / "home"
    first = tmp_path / "standalone-python"
    second = tmp_path / "working-python"
    if leftover:
        environment.mkdir(parents=True)
        (environment / "partial").touch()
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr(setup, "python_candidates", lambda: (first, second))
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        if "--without-pip" in argv:
            assert not environment.exists()
            environment.mkdir()
            (environment / "base").write_text(str(argv[0]), encoding="utf-8")
        elif "import encodings, ssl, venv" in argv:
            if not (environment / "base").is_file() or (environment / "base").read_text() == str(first):
                raise subprocess.CalledProcessError(1, argv, stderr=b"No module named 'encodings'")
        elif "ensurepip" in argv:
            assert (environment / "base").read_text() == str(second)

    monkeypatch.setattr(setup, "run", run)
    assert setup.main(["--root", str(root)]) == 0
    modes = ["--copies"] if os.name == "nt" else ["--copies", "--symlinks"]
    assert [argv[-2] for argv in calls if argv[0] == first] == modes
    ensure_index = next(i for i, argv in enumerate(calls) if "ensurepip" in argv)
    assert calls[ensure_index - 1][-1] == "import encodings, ssl, venv"
    tools = json.loads((root / "runtime.json").read_text(encoding="utf-8"))
    assert tools["delivery_root"] == str((home / "Downloads").resolve())
    assert json.loads(capsys.readouterr().out)["delivery_folder"] == tools["delivery_root"]


def test_setup_cleans_last_failed_attempt_and_suggests_a_working_python(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "python_candidates", lambda: (sys.executable,))

    def run(argv, **kwargs):
        if "--without-pip" in argv:
            (tmp_path / "venv").mkdir()
        else:
            raise subprocess.CalledProcessError(1, argv)

    monkeypatch.setattr(setup, "run", run)
    with pytest.raises(RuntimeError, match="Install Python 3.12 from python.org"):
        setup.main(["--root", str(tmp_path)])
    assert not (tmp_path / "venv").exists()
    assert not (tmp_path / "runtime.json").exists()


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


def test_a_previous_shipped_patch_upgrades_without_accepting_custom_changes(tmp_path, monkeypatch):
    assets, package = tmp_path / 'assets', tmp_path / 'package'
    assets.mkdir()
    package.mkdir()
    (package / 'package.json').write_text('{"version":"test"}')
    (package / 'cdp.js').write_text('previous shipped patch')
    (assets / 'cdp.js').write_text('current patch')
    old_hash = setup.digest(package / 'cdp.js')
    entry = dict(path='cdp.js', original='upstream-hash',
                 previous_patched=[old_hash], patched=setup.digest(assets / 'cdp.js'))
    (assets / 'manifest.json').write_text(json.dumps(dict(version='test', files=[entry])))
    monkeypatch.setattr(setup, 'PATCHES', assets)
    setup.patch_opencli(package)
    setup.patch_opencli(package)
    assert (package / 'cdp.js').read_text() == 'current patch'
    assert (package / 'cdp.js.job-hunt-original').read_text() == 'previous shipped patch'
    (package / 'cdp.js').write_text('custom local changes')
    with pytest.raises(RuntimeError, match='Unrecognized'):
        setup.patch_opencli(package)
    assert (package / 'cdp.js').read_text() == 'custom local changes'


def test_bundled_clients_run_without_installed_skills():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node unavailable')
    result = subprocess.run([node, str(setup.SKILL/'third_party/anysearch/anysearch_cli.js'), 'doc'], capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    assert 'batch_search' in result.stdout
    result = subprocess.run([node, '--test', str(Path(__file__).with_name('browser-cdp.test.mjs')), str(Path(__file__).with_name('browser-session.test.mjs')), str(Path(__file__).with_name('opencli-handoff.test.mjs'))], capture_output=True,text=True)
    assert result.returncode == 0, result.stdout + result.stderr
