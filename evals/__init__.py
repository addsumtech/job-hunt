"""The job-hunt evaluation harness.

Not part of the skill's runtime. Nothing under scripts/ imports this package;
this package imports from scripts/ so that the harness tracks the skill's own
closed sets instead of keeping a second copy of them.
"""
import pathlib
import sys

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
