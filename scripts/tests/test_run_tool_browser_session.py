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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import run_tool

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


def test_a_bad_runtime_gives_its_actual_error(tmp_path):
    root = _root(tmp_path)
    (root / "runtime.json").write_text("unfinished {")
    out = _read(root, tmp_path)
    assert out.returncode == 1
    assert "Expecting value" in out.stderr
    assert "setup_dependencies.py" not in out.stderr


@pytest.mark.parametrize("output", [
    b'[{"site":"boss","status":"not_logged_in","checked":"full"},'
    b'{"site":"linkedin","status":"unknown","checked":"full"}]',
    "│ boss │ not_logged_in │ │ full │ │\n".encode(),
])
def test_full_login_status_interrupts_search_and_preserves_stdout(tmp_path, monkeypatch, capsys, output):
    root = _root(tmp_path)
    record = root / "runtime.json"
    record.write_text(json.dumps({**json.loads(record.read_text()), "node": "node"}))

    def run(cmd, **kwargs):
        if "endpoint" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="ws://127.0.0.1:1")
        return subprocess.CompletedProcess(cmd, 0, stdout=output)

    monkeypatch.setattr(run_tool.subprocess, "run", run)
    assert run_tool.main(["--root", str(root), "--browser", "chrome", "opencli",
                          "auth", "status", "--site", "boss", "--full"]) == 0
    out = capsys.readouterr()
    assert out.out.encode() == output
    assert "SITE_LOGIN_HANDOFF" in out.err and "BOSS直聘" in out.err
    assert "next message" in out.err and "before searching any other source" in out.err
    assert "linkedin" not in out.err


def test_recorded_opencli_search_reaches_the_process_with_existing_raw(
        tmp_path, monkeypatch, capsys):
    import check_opencli_result
    import opencli_meta
    import search_capture

    root = _root(tmp_path)
    record = root / "runtime.json"
    record.write_text(json.dumps({**json.loads(record.read_text()), "node": "node"}))
    ws = tmp_path / "round"
    raw = ws / "raw"
    raw.mkdir(parents=True)
    original = pathlib.Path.mkdir

    def broker_mkdir(path, *args, **kwargs):
        if path.exists():
            raise FileExistsError(path)
        return original(path, *args, **kwargs)

    def run(cmd, **kwargs):
        if "endpoint" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="ws://127.0.0.1:1")
        if "--help" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout=b"captured help")
        return subprocess.CompletedProcess(cmd, 0, stdout=b'[]\n', stderr=b'')

    monkeypatch.setattr(pathlib.Path, "mkdir", broker_mkdir)
    monkeypatch.setattr(run_tool.subprocess, "run", run)
    monkeypatch.setattr(search_capture, "preflight", lambda *args: None)
    monkeypatch.setattr(opencli_meta, "access_for", lambda *args: "read")
    monkeypatch.setattr(check_opencli_result, "main", lambda *args: 0)
    args = ["--root", str(root), "--browser", "chrome", "--workspace", str(ws),
            "opencli", "51job", "search", "--keyword", "AI 产品经理", "-f", "json"]
    assert run_tool.main(args) == 0
    assert run_tool.main(args) == 0
    assert (raw / "opencli-help" / "51job.yaml").read_bytes() == b"captured help"
    assert len(list(raw.glob("51job-*.json"))) == 2
    assert capsys.readouterr().out == "[]\n[]\n"
