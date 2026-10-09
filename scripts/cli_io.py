"""The command-line text protocol is UTF-8, including redirected output.

Windows can default redirected Python streams to an ANSI code page. A gate
then crashes while printing a Chinese finding, after appearing to return the
same exit code as a genuine rejection. Configure only command-line entry
points; importing a library must not replace its caller's streams.
"""
import sys


def configure_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors=stream.errors, newline="\n")


def pass_notice(gate: str, mode: str | None = None) -> None:
    """One line on STDERR when a gate finds nothing.

    Not stdout. `references/workflow-checklist.md` fixes stdout as one finding
    per line with a stable CODE prefix, because an always-on line there trains
    the reader to skip the channel that reports real findings; twenty
    assertions across six test files pin that silence, and they stay true.

    But total silence is the other failure, and it is the one that was
    measured. On 2026-10-08 two agents walked discover and apply using only
    what the files and scripts print, and both stopped at the first green
    light and reported the round finished — the four discover completion gates
    exit 0 with zero bytes of stdout between them, while report.md, the
    coverage check, the render and the delivery were all still to do.

    This says the one thing a gate alone cannot: passing is not finishing. It
    deliberately does NOT name the next command. Which command follows depends
    on the mode and the step, the mode file owns that order, and a per-gate
    successor list here would go stale the first time a step moved.

    It names `modes/<mode>.md` only when that file is really there. The caller
    is `journal.receipt`, which passes `journal.current_mode`'s answer, and
    that answer is the string "unknown" when nothing recorded a mode_entry —
    the shape check_apply's NO_MODE_ENTRY finding exists to catch. Interpolated
    blindly, the line sent the reader to `modes/unknown.md`, a file the skill
    does not ship. The guard asks the filesystem rather than the one sentinel,
    so the next sentinel, a typo or a renamed mode degrades to the generic
    wording instead of printing a path to nothing.
    """
    known = False
    if mode:
        try:
            import paths
            known = paths.mode_file(mode).exists()
        except (ImportError, OSError):
            known = False
    where = f"the {mode} run" if known else "the run"
    print(f"PASS: {gate} — no findings. This is not the end of {where}; return to "
          f"{'modes/' + mode + '.md' if known else 'the mode file'} and continue "
          "from the step that ran it.", file=sys.stderr)
