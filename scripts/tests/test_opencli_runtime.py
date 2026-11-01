"""OpenCLI helpers inspect the copy run_tool.py actually runs.

Measured 2026-11-01 on a machine with a second, global `opencli` first on PATH:
opencli_compat.py reported "Unsupported OpenCLI version" and doctor.py reported
website CDP routing unconfirmed. Both were describing the global copy, while
every recorded read went through the prepared runtime's private 1.8.7.
"""
import json
import pathlib
import subprocess
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import doctor
import opencli_compat


def make_package(root: pathlib.Path, version: str) -> pathlib.Path:
    package = root / "node_modules/@jackwener/opencli"
    (package / "dist/src").mkdir(parents=True)
    (package / "package.json").write_text(json.dumps(
        {"name": "@jackwener/opencli", "version": version}))
    (package / "dist/src/main.js").write_text("// entry\n")
    return package


def path_opencli(tmp_path, monkeypatch, version="2.0.2"):
    """A different OpenCLI reachable on PATH, as on the measuring machine."""
    other = make_package(tmp_path / "global", version)
    binary = tmp_path / "bin/opencli"
    binary.parent.mkdir()
    binary.symlink_to(other / "dist/src/main.js")
    monkeypatch.setattr(opencli_compat.shutil, "which",
                        lambda name: str(binary) if name == "opencli" else None)
    monkeypatch.setattr(doctor.shutil, "which",
                        lambda name: str(binary) if name == "opencli" else "/path/node")
    return other


def prepare_runtime(tmp_path, monkeypatch, record):
    root = tmp_path / "runtime"
    root.mkdir()
    (root / "runtime.json").write_text(json.dumps(record))
    monkeypatch.setenv("JOBHUNT_RUNTIME_ROOT", str(root))
    return root


def test_the_prepared_runtime_wins_over_another_opencli_on_path(tmp_path, monkeypatch):
    path_opencli(tmp_path, monkeypatch)
    private = make_package(tmp_path / "private", "1.8.7")
    node = tmp_path / "node"
    node.write_text("")
    prepare_runtime(tmp_path, monkeypatch, {
        "python": sys.executable, "node": str(node),
        "opencli": str(private / "dist/src/main.js")})
    assert opencli_compat.installed_package() == private.resolve()
    opencli, used_node, problem = doctor.opencli_tools()
    assert (pathlib.Path(opencli), used_node, problem) == (private.resolve(), str(node), "")


def test_a_stale_runtime_record_is_an_error_not_a_silent_fallback(tmp_path, monkeypatch):
    path_opencli(tmp_path, monkeypatch)
    prepare_runtime(tmp_path, monkeypatch, {
        "python": sys.executable, "node": "/gone/node",
        "opencli": str(tmp_path / "gone/dist/src/main.js")})
    with pytest.raises(ValueError, match="re-run scripts/setup_dependencies.py --discovery"):
        opencli_compat.installed_package()
    opencli, _, problem = doctor.opencli_tools()
    assert opencli is None and "no @jackwener/opencli package is there" in problem
    ok, reason = doctor.can_use_opencli_cdp()
    assert not ok and reason == problem


def test_an_unreadable_runtime_record_is_reported(tmp_path, monkeypatch):
    path_opencli(tmp_path, monkeypatch)
    root = prepare_runtime(tmp_path, monkeypatch, {})
    (root / "runtime.json").write_text("{not json")
    with pytest.raises(ValueError, match="is unreadable"):
        opencli_compat.installed_package()


@pytest.mark.parametrize("record", [None, {"python": sys.executable}])
def test_without_a_prepared_opencli_path_is_still_used(tmp_path, monkeypatch, record):
    other = path_opencli(tmp_path, monkeypatch)
    if record is not None:  # prepared without --discovery: no private OpenCLI
        prepare_runtime(tmp_path, monkeypatch, record)
    assert opencli_compat.installed_package() == other.resolve()
    assert doctor.opencli_tools()[0] == str(tmp_path / "bin/opencli")


def test_the_compat_check_reports_the_runtime_version_not_the_path_one(tmp_path, monkeypatch):
    path_opencli(tmp_path, monkeypatch, version="2.0.2")
    private = make_package(tmp_path / "private", "9.9.9")
    prepare_runtime(tmp_path, monkeypatch, {
        "python": sys.executable, "opencli": str(private / "dist/src/main.js")})
    manifest = json.loads(opencli_compat.MANIFEST.read_text())
    with pytest.raises(ValueError, match="Unsupported OpenCLI version"):
        opencli_compat.prepare(opencli_compat.installed_package(), tmp_path / "cfg",
                               "linkedin", "check", manifest)
    # The same private package at the supported version gets past that check.
    (private / "package.json").write_text(json.dumps(
        {"name": "@jackwener/opencli", "version": manifest["version"]}))
    try:
        opencli_compat.prepare(opencli_compat.installed_package(), tmp_path / "cfg",
                               "linkedin", "check", manifest)
    except (ValueError, OSError) as exc:  # the fake package has no adapter files
        assert "Unsupported OpenCLI version" not in str(exc)


def test_run_tool_passes_its_root_to_children(tmp_path):
    root = tmp_path / "custom root"
    root.mkdir()
    (root / "runtime.json").write_text(json.dumps({"python": sys.executable}))
    script = pathlib.Path(__file__).resolve().parents[1] / "run_tool.py"
    out = subprocess.run(
        [sys.executable, str(script), "--root", str(root), "python", "-c",
         "import os; print(os.environ['JOBHUNT_RUNTIME_ROOT'])"],
        capture_output=True, text=True, check=True)
    assert out.stdout.strip() == str(root)
