import pathlib
import shutil
import subprocess
import sys

import pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import doctor


def package(tmp_path, monkeypatch, supports_cdp=False):
    root = tmp_path / "OpenCLI with spaces"
    browser = root / "dist/src/browser"
    browser.mkdir(parents=True)
    (root / "package.json").write_text('{"type":"module"}')
    (browser / "index.js").write_text(
        'export class CDPBridge { constructor() { throw Error("must not connect"); } }\n'
        'export class BrowserBridge { constructor() { throw Error("must not use extension"); } }\n')
    route = "process.env.OPENCLI_CDP_ENDPOINT ? CDPBridge : BrowserBridge" if supports_cdp else "BrowserBridge"
    (root / "dist/src/runtime.js").write_text(
        'import {CDPBridge, BrowserBridge} from "./browser/index.js";\n'
        f'export function getBrowserFactory(site) {{ return {route}; }}\n')
    monkeypatch.setattr(doctor, "installed_package", lambda: root)
    return root


@pytest.mark.parametrize("supports_cdp", [False, True])
def test_installed_factory_must_select_cdp_without_instantiating_a_bridge(
        tmp_path, monkeypatch, supports_cdp):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for the real offline routing probe")
    package(tmp_path, monkeypatch, supports_cdp)
    monkeypatch.setattr(doctor.shutil, "which", lambda name: node if name == "node" else "/fake/opencli")
    ok, reason = doctor.can_use_opencli_cdp()
    assert ok is supports_cdp, reason
    if ok:
        assert "verify the selected live endpoint" in reason


@pytest.mark.parametrize("output", [
    '[OK] Extension: connected\n[OK] Connectivity: working',
    'not JSON',
    '[{"site": [], "cdp": true}]',
])
def test_extension_health_or_invalid_probe_output_never_proves_cdp(
        tmp_path, monkeypatch, output):
    package(tmp_path, monkeypatch)
    monkeypatch.setattr(doctor.shutil, "which", lambda name: "/fake/" + name)
    def run(cmd, **kwargs):
        assert cmd[0] == "/fake/node"
        assert "doctor" not in cmd
        return subprocess.CompletedProcess(cmd, 0, output, '')
    monkeypatch.setattr(doctor.subprocess, "run", run)
    assert not doctor.can_use_opencli_cdp()[0]


def test_cdp_routing_probe_has_a_bounded_timeout(tmp_path, monkeypatch):
    package(tmp_path, monkeypatch)
    monkeypatch.setattr(doctor.shutil, "which", lambda name: "/fake/" + name)
    def timeout(cmd, **kwargs):
        assert kwargs['timeout'] == 15
        raise subprocess.TimeoutExpired(cmd, kwargs['timeout'])
    monkeypatch.setattr(doctor.subprocess, 'run', timeout)
    ok, reason = doctor.can_use_opencli_cdp()
    assert not ok and 'could not complete' in reason
