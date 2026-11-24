"""Directory creation shared by the command-line tools."""


def ensure_directory(path, *, parents=False):
    """Create a directory even on hosts that drop mkdir's exist_ok flag."""
    if path.is_dir():
        return
    try:
        path.mkdir(parents=parents)
    except FileExistsError:
        # Another invocation may have created it since the check above.
        if not path.is_dir():
            raise
