"""A store the host will not let us write fails with one actionable line, not a traceback.

Codex's default sandbox allows writes only inside its working directory. A bare
PermissionError traceback from paths.py left the agent to improvise a location.
"""
import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import doctor
import paths
import save_profile

pytestmark = pytest.mark.skipif(
    os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="chmod does not make a directory unwritable here")


@pytest.fixture
def locked(tmp_path, monkeypatch):
    root = tmp_path / "store"
    root.mkdir()
    root.chmod(0o555)
    monkeypatch.setattr(paths, "PROFILES_ROOT", root)
    yield root
    root.chmod(0o755)


def test_paths_reports_an_unwritable_store_and_exits_2(locked, capsys):
    assert paths.main(["--name", "Test Person", "--company", "Acme", "--role", "Nurse"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("STORE_UNWRITABLE:") and "JOBHUNT_PROFILES_ROOT" in err


def test_save_profile_reports_an_unwritable_store_and_exits_2(locked, tmp_path, capsys):
    profile = tmp_path / "p.yaml"
    profile.write_text("meta:\n  language: en\nname: Test Person\n", encoding="utf-8")
    assert save_profile.main(["--name", "Test Person", "--profile", str(profile)]) == 2
    assert "STORE_UNWRITABLE:" in capsys.readouterr().err


def test_doctor_probes_writes_without_creating_the_folder(locked):
    ok, detail = doctor.can_write(locked / "not-yet")
    assert not ok and "Permission denied" in detail
    assert not (locked / "not-yet").exists()
    ok, _ = doctor.can_write(locked.parent / "free" / "deeper")
    assert ok and not (locked.parent / "free").exists()
