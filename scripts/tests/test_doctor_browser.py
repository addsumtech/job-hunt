import pathlib
import subprocess
import sys

import pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import doctor


@pytest.mark.parametrize('output,exit_code,expected', [
    ('[OK] Daemon: running\n[MISSING] Extension: not connected\n[FAIL] Connectivity: failed', 0, False),
    ('[OK] Daemon: running\n[OK] Extension: connected\n[OK] Connectivity: working', 0, True),
    ('opencli version 1.8.7', 0, False),
    ('[OK] Connectivity: working', 1, False),
])
def test_browser_health_requires_connectivity_not_just_a_binary(monkeypatch, output, exit_code, expected):
    monkeypatch.setattr(doctor.shutil, 'which', lambda name: '/fake/opencli')
    monkeypatch.setattr(doctor.subprocess, 'run', lambda *a, **kw:
                        subprocess.CompletedProcess(a[0], exit_code, output, ''))
    assert doctor.can_reach_browser()[0] is expected


def test_browser_health_has_a_bounded_timeout(monkeypatch):
    monkeypatch.setattr(doctor.shutil, 'which', lambda name: '/fake/opencli')
    def timeout(cmd, **kwargs):
        assert kwargs['timeout'] == 15
        raise subprocess.TimeoutExpired(cmd, kwargs['timeout'])
    monkeypatch.setattr(doctor.subprocess, 'run', timeout)
    ok, reason = doctor.can_reach_browser()
    assert not ok and 'could not complete' in reason
