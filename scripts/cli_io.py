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
    """
    where = f"the {mode} run" if mode else "the run"
    print(f"PASS: {gate} — no findings. This is not the end of {where}; return to "
          f"{'modes/' + mode + '.md' if mode else 'the mode file'} and continue "
          "from the step that ran it.", file=sys.stderr)
