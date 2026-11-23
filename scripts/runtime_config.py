"""Paths and atomic updates for the private runtime record."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile


def default_root():
    # run_tool.py exports this for every child, including with a custom --root.
    explicit = os.environ.get("JOBHUNT_RUNTIME_ROOT", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share")) / "job-hunt"


@contextmanager
def runtime_lock(root, name):
    # The OS releases the lock if setup is interrupted. Keep the lock file so
    # concurrent invocations always lock the same inode.
    root.mkdir(parents=True, exist_ok=True)
    with (root / name).open("a+b") as lock:
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise OSError(f"Another job-hunt command is updating {root}. Try again shortly.") from exc
        yield


def read_runtime(root):
    try:
        runtime = json.loads((root / "runtime.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(runtime, dict):
        raise ValueError(f"Expected a JSON object in {root / 'runtime.json'}")
    return runtime


def update_runtime(root, updates):
    with runtime_lock(root, ".runtime.lock"):
        runtime = read_runtime(root)
        runtime.update(updates)
        temp = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=root,
                                           prefix=".runtime-", delete=False)
        temporary = Path(temp.name)
        try:
            with temp:
                json.dump(runtime, temp, ensure_ascii=False, indent=2)
                temp.write("\n")
            temporary.replace(root / "runtime.json")
        finally:
            temporary.unlink(missing_ok=True)
        return runtime
