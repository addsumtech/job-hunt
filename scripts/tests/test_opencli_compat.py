"""Compatibility edits must be explicit, reversible and preserve unknown files."""
import json
from pathlib import Path

import pytest
import opencli_compat as compat


def fixture(tmp_path):
    package, config = tmp_path / 'package', tmp_path / 'config'
    package.mkdir()
    (package / 'package.json').write_text(json.dumps({'name': '@jackwener/opencli', 'version': '1.8.7'}))
    entries = []
    for name in ['search.js', 'job.js']:
        original, patched = b'old();\n', b'fixed();\n'
        path = 'indeed/' + name
        for parent in [package, config]:
            target = parent / 'clis' / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original)
        entries.append({'path': path, 'base_sha256': compat.digest(original),
                        'patched_sha256': compat.digest(patched),
                        'replacements': [{'old': 'old()', 'new': 'fixed()'}]})
    manifest = {'package': '@jackwener/opencli', 'version': '1.8.7', 'files': entries}
    return package, config, manifest


def test_check_is_read_only_and_apply_is_idempotent_and_reversible(tmp_path):
    package, config, manifest = fixture(tmp_path)
    unknown = config / 'clis/indeed/custom.js'
    unknown.write_text('user code')
    changes, _ = compat.prepare(package, config, 'indeed', 'check', manifest)
    assert changes == []
    changes, _ = compat.prepare(package, config, 'indeed', 'apply', manifest)
    compat.execute(changes)
    assert (config / 'clis/indeed/job.js').read_text() == 'fixed();\n'
    assert compat.prepare(package, config, 'indeed', 'apply', manifest)[0] == []
    changes, _ = compat.prepare(package, config, 'indeed', 'revert', manifest)
    compat.execute(changes)
    assert (config / 'clis/indeed/job.js').read_bytes() == (package / 'clis/indeed/job.js').read_bytes()
    assert unknown.read_text() == 'user code'


@pytest.mark.parametrize('change', ['version', 'official', 'local', 'checksum', 'anchor'])
def test_drift_refuses_before_any_file_is_written(tmp_path, change):
    package, config, manifest = fixture(tmp_path)
    if change == 'version':
        (package / 'package.json').write_text('{"name":"@jackwener/opencli","version":"2.0.0"}')
    elif change == 'official':
        (package / 'clis/indeed/job.js').write_text('new upstream')
    elif change == 'local':
        (config / 'clis/indeed/job.js').write_text('user modifications')
    elif change == 'checksum':
        manifest['files'][1]['patched_sha256'] = 'wrong'
    else:
        manifest['files'][1]['replacements'][0]['old'] = 'absent'
    before = {p: p.read_bytes() for p in config.rglob('*.js')}
    with pytest.raises(ValueError):
        compat.prepare(package, config, 'indeed', 'apply', manifest)
    assert before == {p: p.read_bytes() for p in config.rglob('*.js')}


def test_missing_override_is_reported_and_not_created(tmp_path):
    package, config, manifest = fixture(tmp_path)
    (config / 'clis/indeed/job.js').unlink()
    assert compat.prepare(package, config, 'indeed', 'check', manifest)[1][-1]['state'] == 'needs_eject'
    with pytest.raises(ValueError, match='eject'):
        compat.prepare(package, config, 'indeed', 'apply', manifest)
    assert not (config / 'clis/indeed/job.js').exists()


def test_symlink_cannot_modify_official_package(tmp_path):
    package, config, manifest = fixture(tmp_path)
    local = config / 'clis/indeed/job.js'
    local.unlink()
    try:
        local.symlink_to(package / 'clis/indeed/job.js')
    except OSError:
        pytest.skip('symlink creation unavailable')
    with pytest.raises(ValueError, match='symlink'):
        compat.prepare(package, config, 'indeed', 'apply', manifest)
    assert (package / 'clis/indeed/job.js').read_text() == 'old();\n'


def test_write_failure_rolls_back_completed_files(tmp_path, monkeypatch):
    package, config, manifest = fixture(tmp_path)
    changes, _ = compat.prepare(package, config, 'indeed', 'apply', manifest)
    real = compat.replace_file
    def fail_second(path, data):
        if path.name == 'job.js':
            raise OSError('disk failure')
        real(path, data)
    monkeypatch.setattr(compat, 'replace_file', fail_second)
    with pytest.raises(OSError):
        compat.execute(changes)
    assert (config / 'clis/indeed/search.js').read_text() == 'old();\n'


def test_edit_after_preflight_is_preserved(tmp_path):
    package, config, manifest = fixture(tmp_path)
    changes, _ = compat.prepare(package, config, 'indeed', 'apply', manifest)
    local = config / 'clis/indeed/job.js'
    local.write_text('concurrent user edit')
    with pytest.raises(ValueError, match='during patching'):
        compat.execute(changes)
    assert local.read_text() == 'concurrent user edit'
    assert (config / 'clis/indeed/search.js').read_text() == 'old();\n'


def test_apply_creates_override_without_manual_eject(tmp_path, monkeypatch):
    import shutil
    package, config, manifest = fixture(tmp_path)
    (package / 'clis/indeed/utils.js').write_text('shared utility')
    shutil.rmtree(config / 'clis/indeed')
    data = tmp_path / 'patches.json'
    data.write_text(json.dumps(manifest))
    monkeypatch.setattr(compat, 'MANIFEST', data)
    args = ['--site', 'indeed', '--package-dir', str(package), '--config-dir', str(config)]
    assert compat.main(args) == 0
    assert not (config / 'clis/indeed').exists()
    assert compat.main(args + ['--action', 'apply']) == 0
    assert (config / 'clis/indeed/job.js').read_text() == 'fixed();\n'
    assert (config / 'clis/indeed/utils.js').read_text() == 'shared utility'
    assert (package / 'clis/indeed/job.js').read_text() == 'old();\n'
    assert compat.main(args + ['--action', 'apply']) == 0
    assert compat.main(args + ['--action', 'revert']) == 0
    assert (config / 'clis/indeed/job.js').read_text() == 'old();\n'


def test_unsupported_version_creates_no_override(tmp_path, monkeypatch):
    import shutil
    package, config, manifest = fixture(tmp_path)
    shutil.rmtree(config / 'clis/indeed')
    (package / 'package.json').write_text('{"name":"@jackwener/opencli","version":"2.0.0"}')
    data = tmp_path / 'patches.json'
    data.write_text(json.dumps(manifest))
    monkeypatch.setattr(compat, 'MANIFEST', data)
    assert compat.main(['--site', 'indeed', '--action', 'apply', '--package-dir', str(package), '--config-dir', str(config)]) == 2
    assert not (config / 'clis/indeed').exists()
