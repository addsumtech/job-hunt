"""A read-only view of one eval run directory.

The outputs/ contract below is what evals/run.md promises the dispatcher and
what every checker assumes. It lives here, once, so that changing it changes
the runbook test too.

Two properties this module is responsible for, and both are tested:

1. **Read-only means read-only.** Nothing here creates, moves, truncates or
   writes anything. A checker that reaches for the filesystem goes through
   ``Run``; if ``Run`` cannot write, no checker can corrupt the artifact it is
   grading.
2. **The results root is outside the repo.** A run produces a real workspace
   holding a real person's profile data, so a results tree inside the repo is
   one ``git add`` away from being published. The root is a constant plus an
   environment override (``JOBHUNT_EVAL_RESULTS_ROOT``) -- resolved at runtime,
   never a literal in a committed file -- and pointing it inside the repo is a
   loud ``ValueError`` at import rather than a quiet copy of someone's CV into
   version control.
"""
from __future__ import annotations

import json
import os
import pathlib
import posixpath
import re

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Where results live. NOT a literal path: a committed absolute path is correct on
# exactly one machine, and this repo has already paid for that once. The default is
# derived from $HOME at runtime; the override exists so CI, a second checkout or a
# reviewer with a different layout can point the harness somewhere else without
# editing (and re-committing) a path.
RESULTS_ROOT_ENV = "JOBHUNT_EVAL_RESULTS_ROOT"
DEFAULT_RESULTS_ROOT = pathlib.Path.home() / "code_project" / "job-hunt-workspace"

# What a run MUST save. `workspace/` is a copy of the job-hunt workspace the run
# produced; `final-message.md` is the run's last user-facing message, verbatim,
# and it is not optional -- half the guards in this harness are about what the
# run SAID, and iteration-1 had no way to read that at all.
OUTPUT_CONTRACT = ("final-message.md", "RUN_NOTES.md", "workspace/", "stderr.log")

# The surfaces a human actually reads. Checkers that ask "did the run claim X"
# scan these and nothing else -- a string buried in a raw capture is not a claim.
READER_FACING = ("final-message.md", "RUN_NOTES.md", "workspace/shortlist.md",
                 "workspace/fit-assessment.md", "workspace/interview-brief.md")

_RUN_DIR = re.compile(r"^run-(\d+)$")
_EVAL_DIR = re.compile(r"^eval-(\d+)$")


def resolve_results_root(env_value=None, repo_root=None, default=None):
    """The results root, resolved from the environment or the module default.

    Refuses -- loudly, with the offending path in the message -- to return a
    directory that is the repo or lives inside it. That is the whole point of the
    root being a variable: a mistyped override must not silently start writing a
    real person's profile data into a git working tree.
    """
    repo = pathlib.Path(repo_root if repo_root is not None else REPO_ROOT)
    fallback = pathlib.Path(default if default is not None else DEFAULT_RESULTS_ROOT)
    raw = env_value if env_value is not None else os.environ.get(RESULTS_ROOT_ENV)
    chosen = pathlib.Path(raw.strip()).expanduser() if raw and raw.strip() else fallback

    # resolve() follows symlinks, so an override pointing at a link into the repo is
    # caught too; it does not require the directory to exist yet.
    chosen = chosen.expanduser().resolve()
    repo = repo.expanduser().resolve()
    if chosen == repo or repo in chosen.parents:
        raise ValueError(
            f"the eval results root must live OUTSIDE the repo, but "
            f"{chosen} is inside {repo}. Runs contain a real person's profile "
            f"data; a results tree in the repo is one `git add` from being "
            f"published. Set ${RESULTS_ROOT_ENV} to a path outside the repo.")
    return chosen


RESULTS_ROOT = resolve_results_root()


def _relative(rel):
    """Normalise a run-relative path, refusing one that leaves outputs/.

    ``Run`` is how a checker reads a run it is grading. A checker that can address
    ``../../baseline/run-1`` can grade the wrong arm and never notice, so an escape
    is an error here rather than a surprise three files later.
    """
    text = str(rel).replace(os.sep, "/")
    if posixpath.isabs(text):
        raise ValueError(
            f"run-relative path expected, got the absolute path {rel!r}")
    normalised = posixpath.normpath(text)
    if normalised == ".." or normalised.startswith("../"):
        raise ValueError(
            f"{rel!r} escapes the run's outputs/ directory")
    return normalised


class Run:
    """One run directory: ``<eval>/<arm>/run-<n>/``, holding ``outputs/``.

    Every accessor is a read. A missing file is ``None``, never an exception and
    never a created file -- a checker's job is to report the absence, not to
    repair it.
    """

    def __init__(self, run_dir):
        self.dir = pathlib.Path(run_dir)
        self.outputs = self.dir / "outputs"

    def __repr__(self):
        return f"Run({str(self.dir)!r})"

    def path(self, rel):
        normalised = _relative(rel)
        return self.outputs if normalised == "." else self.outputs / normalised

    def exists(self, rel):
        return self.path(rel).exists()

    def read(self, rel):
        p = self.path(rel)
        if not p.is_file():
            return None
        return p.read_text(encoding="utf-8", errors="replace")

    def load_yaml(self, rel):
        text = self.read(rel)
        if text is None:
            return None
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError:
            return None

    def load_json(self, rel):
        text = self.read(rel)
        if text is None:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def journal(self):
        """Every record. Unparsable lines come back rather than disappearing --
        a corrupt journal is a finding, not a shorter list."""
        text = self.read_any("workspace/journal.jsonl")
        if not text:
            return []
        records = []
        for raw in text.splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                records.append({"_unparsable": raw})
                continue
            # A bare scalar or list is not a record. Keeping it as itself would hand
            # every caller a .get() on a str; it is exactly as corrupt as a line that
            # would not parse, so it is reported the same way.
            records.append(parsed if isinstance(parsed, dict)
                           else {"_unparsable": raw})
        return records

    def adapter_calls(self):
        return [r for r in self.journal() if r.get("action") == "adapter_call"]

    def receipts(self, gate=None):
        out = [r for r in self.journal() if r.get("action") == "gate"]
        return [r for r in out if gate is None or r.get("gate") == gate]

    def all_text(self):
        # read_any for the workspace surfaces: a run that nested shortlist.md
        # under job-profiles/<person>/ still SAID what it said, and a claim the
        # harness cannot see is scored as a claim never made.
        parts = [self.read_any(rel) if rel.startswith("workspace/") else self.read(rel)
                 for rel in READER_FACING]
        return "\n".join(p for p in parts if p)

    def first_line_containing(self, needle, rel=None):
        """The first line holding ``needle``, stripped, or None.

        Unscoped it scans the reader-facing surfaces in READER_FACING order, so
        prose wins over a table: a final message saying 未取得真实岗位 contains
        取得真实岗位 and will be returned ahead of the disclosure row that spells
        it. Pass ``rel`` when the caller means a specific artifact's line -- a
        checker that splits the line on its label to read the ANSWER must scope,
        or it will read a sentence and call it filled in.
        """
        text = self.read(rel) if rel is not None else self.all_text()
        for line in (text or "").splitlines():
            if needle in line:
                return line.strip()
        return None

    # ---- locating an artifact wherever the run actually wrote it ------------
    #
    # MEASURED IN THE ITERATION-2 PILOT, and it cost a guard. eval-15 used the
    # job-application skill and produced tailored-profile.yaml, cv.md, cv.tex
    # and posting.yaml -- everything its guard needed, and its CV carries the
    # `Geburtsdatum` line the guard asks about. The guard reported
    # "not exercised", because it read `workspace/cv.md` while the skill writes
    # to `workspace/job-profiles/<person>/applications/<slug>/`.
    #
    # The same skill on eval-14 wrote flat and WAS graded. So the difference
    # between a graded guard and a silent one was the directory layout, which is
    # not what the eval is about, and "not exercised" is scored as neutral -- the
    # harness was blind and the blindness looked like a clean result.
    #
    # `read` stays exact, because a checker that means one specific artifact must
    # still be able to say so. These accessors are for the checkers that mean
    # "the CV this run produced", wherever it put it.

    def _search_root(self, rel):
        """The workspace-relative tail of `rel`, or ValueError.

        Scoped to workspace/ deliberately, and this is the load-bearing rule.
        `outputs/scenario.md` is the run's INPUT -- it holds the job posting and
        the candidate's facts verbatim. A locator that searched all of outputs/
        could satisfy "did the run extract the posting" by reading the posting
        out of the question paper, and every such checker would then pass on
        every run, including one that produced nothing at all.

        Out of scope raises rather than returning None: None means "absent",
        which is exactly the silent-neutral result this accessor exists to stop.
        """
        normalised = _relative(rel)
        if normalised == "." or not normalised.startswith("workspace/"):
            raise ValueError(
                f"{rel!r} is not under workspace/. Only artifacts the run "
                f"PRODUCED can be located; outputs/scenario.md and "
                f"outputs/final-message.md are read with .read() by name.")
        return normalised[len("workspace/"):]

    def locate(self, rel):
        """Every file under workspace/ with this basename, best match first.

        Ordered canonical-first, then by depth, then lexicographically -- never
        by filesystem order, so a verdict cannot move with readdir. Returns
        every match so a caller that needs to REPORT ambiguity can see it.
        """
        tail = self._search_root(rel)
        root = self.path("workspace")
        if not root.is_dir():
            return []
        canonical = root / tail
        found = [canonical] if canonical.is_file() else []
        name = posixpath.basename(tail)
        others = [p for p in root.rglob(name) if p.is_file() and p != canonical]
        found += sorted(others, key=lambda p: (len(p.relative_to(root).parts),
                                               str(p)))
        return found

    def read_any(self, rel):
        """Text of the best match for `rel`, or None if there is none."""
        found = self.locate(rel)
        if not found:
            return None
        return found[0].read_text(encoding="utf-8", errors="replace")

    def load_yaml_any(self, rel):
        text = self.read_any(rel)
        if text is None:
            return None
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError:
            return None

    def glob_workspace(self, pattern):
        """Matches at the canonical location AND anywhere below it.

        The interview checkers glob `mock/transcript-*.md`. A run that wrote its
        transcript one directory over was read as never having held a round --
        the same blindness as above, in glob form.
        """
        root = self.path("workspace")
        if not root.is_dir():
            return []
        seen, out = set(), []
        for p in sorted(root.glob(pattern)) + sorted(root.glob("**/" + pattern)):
            if p.is_file() and p not in seen:
                seen.add(p)
                out.append(p)
        return out


def iter_runs(iteration_dir):
    """Yield (eval_id, arm, run_number, Run) for every run on disk.

    Ordered by eval id and run number NUMERICALLY: lexicographic order puts
    eval-10 before eval-2, and a reader watching runs stream past in that order
    has no way to tell a gap from a sort.

    Raises if the iteration directory is absent. Every caller checks ``is_dir()``
    first and exits 2 with a reason; a silent empty iteration would instead be
    read as "no runs yet", which is the iteration-1 defect this harness exists to
    stop.
    """
    iteration_dir = pathlib.Path(iteration_dir)
    if not iteration_dir.is_dir():
        raise NotADirectoryError(
            f"no such iteration directory: {iteration_dir}")
    evals = []
    for eval_dir in iteration_dir.glob("eval-*"):
        m = _EVAL_DIR.match(eval_dir.name)
        if m and eval_dir.is_dir():
            evals.append((int(m.group(1)), eval_dir.name, eval_dir))
    for _eval_id, _name, eval_dir in sorted(evals, key=lambda t: (t[0], t[1])):
        for arm_dir in sorted(p for p in eval_dir.iterdir() if p.is_dir()):
            runs = []
            for run_dir in arm_dir.glob("run-*"):
                rm = _RUN_DIR.match(run_dir.name)
                if rm and run_dir.is_dir():
                    runs.append((int(rm.group(1)), run_dir.name, run_dir))
            for number, _run_name, run_dir in sorted(runs, key=lambda t: (t[0], t[1])):
                yield _eval_id, arm_dir.name, number, Run(run_dir)
