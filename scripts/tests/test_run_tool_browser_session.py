"""run_tool.py reports an ended browser session as what it is.

Measured 2026-11-20: a read after an idle expiry printed the session's own
explanation and then `; run scripts/setup_dependencies.py for the needed
capability`. The runtime was installed and intact; the suffix sent the agent to
reinstall it instead of starting the session again.

These tests never reach a browser. The `endpoint` probe refuses an ended record
before it looks for any debugging endpoint, and the records below name a pid
that cannot exist.
"""
import json
import pathlib
import shutil
import subprocess
import sys

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "run_tool.py"
NODE = shutil.which("node")
DEAD_PID = 2147483646


def _root(tmp_path, record=None):
    root = tmp_path / "runtime"
    root.mkdir()
    (root / "runtime.json").write_text(json.dumps({
        "python": sys.executable, "node": NODE,
        "opencli": str(root / "opencli/node_modules/@jackwener/opencli/dist/main.js")}))
    if record is not None:
        (root / "browser-session-chrome.json").write_text(json.dumps({
            "pid": DEAD_PID, "browser": "chrome",
            "source_endpoint": "ws://127.0.0.1:1/devtools/browser/fixture",
            "endpoint": "ws://127.0.0.1:1/devtools/browser/x", **record}))
    return root


def _read(root, tmp_path):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "--browser", "chrome",
         "browser", "--url", "https://example.com/", "--output", str(tmp_path / "capture.json")],
        capture_output=True, text=True)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("record, says", [
    ({"state": "closed", "ended_reason": "idle_timeout"}, "expired after 30 idle minutes"),
    ({"state": "connected"}, "no longer running"),
], ids=["idle_expiry", "killed_process"])
def test_an_ended_session_is_not_reported_as_a_missing_capability(tmp_path, record, says):
    out = _read(_root(tmp_path, record), tmp_path)
    assert out.returncode == 1
    assert out.stderr.startswith("BROWSER_SESSION_UNAVAILABLE: ")
    assert says in out.stderr
    assert "start once in this chat" in out.stderr
    assert "setup_dependencies" not in out.stderr
    assert "TOOL_UNAVAILABLE" not in out.stderr
    assert "chrome://inspect" not in out.stderr
    assert "点‘允许’" in out.stderr and "回复‘已允许’" in out.stderr
    assert not (tmp_path / "capture.json").exists()


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_new_search_without_session_explains_how_to_continue(tmp_path):
    out = _read(_root(tmp_path), tmp_path)
    assert out.returncode == 1
    assert "BROWSER_SESSION_UNAVAILABLE: No running browser session" in out.stderr
    assert "start it once" in out.stderr and "When it waits for consent" in out.stderr
    assert "Chrome" in out.stderr and "回复‘已允许’" in out.stderr


def test_a_missing_runtime_still_points_at_setup(tmp_path):
    """The other half: when the runtime really is absent, setup is the remedy."""
    root = tmp_path / "empty"
    root.mkdir()
    out = _read(root, tmp_path)
    assert out.returncode == 1
    assert out.stderr.startswith("TOOL_UNAVAILABLE: ")
    assert "setup_dependencies.py" in out.stderr
