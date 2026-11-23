"""Choose a delivery folder by trying an actual write in it."""
from pathlib import Path
import tempfile


def writable(directory):
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".jobhunt-write-probe-"):
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
    for candidate in dict.fromkeys(candidates):
        try:
            candidate = candidate.resolve()
        except (OSError, RuntimeError):
            continue
        ok, _ = writable(candidate)
        if ok:
            return candidate
    raise OSError("No writable delivery folder found. Choose a folder you can write to with --to.")
