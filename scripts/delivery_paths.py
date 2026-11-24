"""Choose a delivery folder by trying an actual write in it."""
import os
from pathlib import Path
from fs_paths import ensure_directory


PROBE_NAME = ".jobhunt-write-probe"


def prepare_delivery_directory(directory):
    ensure_directory(directory, parents=True)
    if not os.access(directory, os.W_OK | os.X_OK):
        raise PermissionError(f"Cannot write to {directory}")


def writable(directory):
    try:
        prepare_delivery_directory(directory)
        # Permission bits alone can miss a host's write restrictions. Open a
        # reusable marker for writing and leave it in place.
        with (directory / PROBE_NAME).open("ab"):
            pass
    except OSError as exc:
        return False, str(exc)
    return True, ""


def choose_delivery_root(runtime):
    home = Path.home()
    configured = runtime.get("delivery_root")
    candidates = [home / "Downloads", home / "Documents" / "job-hunt", home / "job-hunt"]
    if isinstance(configured, str) and configured:
        candidates.insert(0, Path(configured).expanduser())
    tried = []
    for candidate in dict.fromkeys(candidates):
        try:
            candidate = candidate.resolve()
        except (OSError, RuntimeError):
            continue
        tried.append(str(candidate))
        ok, _ = writable(candidate)
        if ok:
            return candidate
    raise OSError(f"Could not save files in: {', '.join(tried)}. "
                  "Ask the user: “你想把求职文件放在哪个文件夹？请告诉我完整路径。” "
                  "Pass that path to deliver.py --to and tell the user the full delivery path.")
