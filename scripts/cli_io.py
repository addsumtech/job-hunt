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
