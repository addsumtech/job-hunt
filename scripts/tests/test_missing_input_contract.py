"""One contract, every gate: a missing primary input exits 2 and leaves a receipt.

The rule each gate's own docstring states — "a check that did not run must not
look like a check that passed" — is implemented as a missing-input guard in
eighteen scripts and was pinned in almost none of them. An audit on 2026-08-23
deleted those guards one at a time and the suite stayed green for at least:
check_personal_data:61, check_letter:117, check_conventions:330, consistency:234,
count_coverage:177, evidence_blocks:201, check_shortlist:696/704,
check_opencli_result:306 — including `check_conventions --ci`, the exact command
CI runs.

The guards WORK. What was missing was anything that would notice if they stopped.
A per-gate test for each would be eighteen chances to forget the nineteenth, so
this is one parameterised contract instead, and adding a gate to GATES is the
only work a new gate needs.

ONE CORRECTION TO THAT AUDIT, measured here rather than argued. Deleting
check_personal_data's guard leaves the suite green AND leaves this contract
satisfied — `journal.load_yaml` then raises, a downstream handler catches it, and
the run still exits 2 with exactly one `could_not_run` receipt, differing only in
the finding code (`UNREADABLE_INPUT` instead of `MISSING_INPUT`). So that guard is
an EQUIVALENT MUTANT with respect to this contract: it buys a clearer message,
not the contract itself, and a test that failed on it would be asserting the
wording rather than the behaviour.

What this file does discriminate, verified by mutation on the same guard:

    return 2  ->  return 0                     1 failed, 20 passed
    the journal.receipt(...) line deleted      1 failed, 20 passed

which are the two ways the contract actually breaks: a gate that could not run
reporting success, and a gate that could not run leaving no trace.

THE FOUR EXEMPTIONS ARE LISTED, NOT OMITTED. Each names the lines of its own
source where it declares itself an exception — an exemption nobody can see is
indistinguishable from a gate nobody remembered to add.
"""
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
TODAY = "2026-08-24"


# (script, extra argv, what makes it "could not run")
# Every entry was MEASURED — exit code and receipt count observed, not assumed.
GATES = [
    ("check_personal_data.py", [], "tailored-profile.yaml"),
    ("check_letter.py", [], "letter.yaml"),
    ("check_word_limits.py", [], "supporting-statement.md"),
    ("check_pages.py", [], "cv.pdf"),
    ("lint_cv.py", [], "cv.md"),
    ("consistency.py", [], "fit-assessment.yaml"),
    ("count_coverage.py", [], "fit-assessment.yaml"),
    ("check_evidence_refs.py", [], "evidence-blocks.json"),
    ("evidence_blocks.py", [], "posting-source.txt"),
    ("lint_no_prediction.py", [], "nothing scannable"),
    ("check_assessment.py", ["--today", TODAY], "fit-assessment.yaml"),
    ("check_shortlist.py", [], "shortlist.yaml"),
    ("check_no_write.py", ["--no-fetch"], "journal.jsonl"),
    ("check_mock.py", ["--round", "1", "--today", TODAY], "mock/transcript-1.md"),
    ("check_render_freshness.py", ["--round", "1"], "judge-round-1.json"),
]

# Gates whose argv names files outside the workspace, so "absent" has to be spelled.
PARAMETERISED = [
    ("parse_verdicts.py",
     lambda ws: ["--round", "1", "--ats", f"{ws}/ats.md",
                 "--recruiter", f"{ws}/recruiter.md",
                 "--hiring-manager", f"{ws}/hm.md"],
     "the --ats transcript"),
    ("check_claims.py",
     lambda ws: ["--record", "--master", f"{ws}/master.yaml"],
     "the --master profile"),
    ("check_conventions.py",
     lambda ws: ["--market-file", f"{ws}/nl.yaml", "--today", TODAY],
     "the --market-file table"),
]

# Deliberate exceptions, each citing where its own source says so. Listed rather
# than omitted: a gate quietly dropped from GATES and a gate that never belonged
# there look identical in a green run.
EXEMPT = {
    "check_apply.py":
        "composes upstream receipts and has no per-file primary input — a missing "
        "receipt or artifact IS the defect it reports, so it exits 1 with findings "
        "(check_apply.py:34-37). Measured on an empty workspace: exit 1, one receipt.",
    "check_skill_lossless.py":
        "a repo-level CI check with no --workspace: it imports no journal and writes "
        "no receipt, and says so at check_skill_lossless.py:22-24. Requiring a "
        "receipt would be requiring evidence that cannot exist.",
    "check_opencli_result.py":
        "a wrapper, not a gate (check_opencli_result.py:2-8). It appends an "
        "adapter_call record and never a receipt, so exit 2 plus a stderr line is "
        "the whole of 'could not run' available to it.",
    "check_conventions.py --ci":
        "--ci lints files that live in the REPO, not artifacts in a workspace, and "
        "is a named exception at check_conventions.py:299-303 and :319-325. The "
        "non---ci form is covered above, with --market-file.",
}


def workspace(tmp_path) -> pathlib.Path:
    """A workspace of the shape paths.py defines, and nothing inside it.

    The shape matters: check_personal_data resolves the profile root by walking
    up from `applications/<x>`, and a bare tmp_path would fail for that reason
    rather than for the missing input this test is about.
    """
    ws = tmp_path / "job-profiles" / "tester" / "applications" / "acme-eng-2026-08-24"
    ws.mkdir(parents=True)
    return ws


def run(script, argv, ws):
    return subprocess.run([sys.executable, str(SCRIPTS / script),
                           "--workspace", str(ws)] + argv,
                          capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT))


def receipts(ws):
    path = ws / "journal.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and record.get("action") == "gate":
            out.append(record)
    return out


def assert_contract(script, proc, ws, missing):
    assert proc.returncode == 2, (
        f"{script} with {missing} absent exited {proc.returncode}, not 2.\n"
        f"stdout: {proc.stdout}\nstderr: {proc.stderr}")
    assert proc.stderr.strip(), (
        f"{script} exited 2 silently — exit 2 means 'could not run', and the "
        f"reason is the whole of the report")
    written = receipts(ws)
    assert len(written) == 1, (
        f"{script} appended {len(written)} gate receipts, expected exactly one: "
        f"{[r.get('gate') for r in written]}")
    assert written[0]["verdict"] == "could_not_run", (
        f"{script} wrote verdict {written[0]['verdict']!r} — a gate that could "
        f"not run must not leave a receipt that reads like one that did")


@pytest.mark.parametrize("script,argv,missing", GATES, ids=[g[0] for g in GATES])
def test_a_missing_primary_input_exits_2_and_leaves_one_could_not_run_receipt(
        tmp_path, script, argv, missing):
    ws = workspace(tmp_path)
    assert_contract(script, run(script, argv, ws), ws, missing)


@pytest.mark.parametrize("script,build_argv,missing", PARAMETERISED,
                         ids=[g[0] for g in PARAMETERISED])
def test_a_missing_named_input_exits_2_and_leaves_one_could_not_run_receipt(
        tmp_path, script, build_argv, missing):
    ws = workspace(tmp_path)
    assert_contract(script, run(script, build_argv(ws), ws), ws, missing)


def test_every_gate_is_either_covered_here_or_listed_as_an_exception():
    """The test that keeps this file honest.

    Without it, the way to make this suite pass is to delete a row from GATES —
    and a gate silently dropped looks exactly like a gate that never existed.
    Every check_*/lint_* script must be in one list or the other, with the
    exemptions carrying a written reason.
    """
    covered = {g[0] for g in GATES} | {g[0] for g in PARAMETERISED}
    exempt = {name.split()[0] for name in EXEMPT}
    unaccounted = []
    for path in sorted(SCRIPTS.glob("*.py")):
        name = path.name
        if not (name.startswith("check_") or name.startswith("lint_")
                or name in ("consistency.py", "count_coverage.py",
                            "evidence_blocks.py", "parse_verdicts.py")):
            continue
        if name not in covered and name not in exempt:
            unaccounted.append(name)
    assert not unaccounted, (
        "these gates are in neither GATES nor EXEMPT: " + ", ".join(unaccounted))


def test_every_exemption_states_where_its_source_says_so():
    """An exemption whose reason is 'it is different' is a hole with a comment on
    it. Each must point at the lines of its own file that declare the exception,
    so the next reader can check the claim rather than inherit it."""
    for name, reason in EXEMPT.items():
        script = name.split()[0]
        assert (SCRIPTS / script).is_file(), f"{script} is exempt but does not exist"
        assert ".py:" in reason, f"{name}'s exemption cites no source lines"
        assert len(reason) > 80, f"{name}'s exemption is too thin to check"


def test_check_apply_reports_rather_than_refuses_on_an_empty_workspace():
    """The most load-bearing exemption, asserted rather than asserted-about.

    check_apply composes receipts, so an empty workspace is not "cannot run" — it
    is the defect. If this ever starts exiting 2, the gate that authorises
    delivery has become silent on the case it exists for.
    """
    import tempfile
    tmp = pathlib.Path(tempfile.mkdtemp())
    ws = workspace(tmp)
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "check_apply.py"), "--workspace", str(ws)],
        capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT))
    assert proc.returncode == 1, f"expected findings, got {proc.returncode}"
    assert proc.stdout.strip(), "check_apply must SAY what is missing"
