"""A gate handed a malformed document must not exit 1 with no receipt.

The gate contract is 0 clean / 1 findings / 2 could-not-run, with exactly one
receipt per run. A Python exception escaping a gate produces exit 1 and NO
receipt — so a composer reading the journal sees a gate that never ran while the
caller reading the exit code sees "ran, found problems". `journal.load_yaml`'s
docstring records that same failure from 2026-08-16 and `journal.as_mapping`'s
from 2026-09-05; this file is the third round of it, found 2026-09-06 by mutating
every field of a valid document to a wrong type rather than by imagining inputs.

`(x or {}).get` is the idiom behind all of it. It guards None and every falsy
value and NOT a non-empty string, a list, an int or True — and `stated_conditions:
none`, `verdict: [worth_applying]` and `meta: "us"` are all things a model or a
person writes by hand.

The property test at the bottom is the one that matters. The named cases above it
are the four that were actually reproduced, kept so a regression says WHICH.
"""
import copy
import pathlib
import subprocess
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

VALID_ASSESSMENT = yaml.safe_load("""
verdict: worth_applying
level_direction: step_up
effort: evening
must_haves: [{text: "5 years C++", evidence: [JD-001], level: strong}]
responsibilities: [{text: "own the pipeline", evidence: [JD-002], level: strong}]
stated_conditions: [{type: visa_sponsorship, value: unclear, evidence: JD-003}]
declared_work_status: temporary_route
conventions_rendered: []
""")

VALID_PROFILE = yaml.safe_load(
    (ROOT / "assets" / "profile.example.yaml").read_text(encoding="utf-8"))

WRONG_SHAPES = ["a string", ["a", "list"], {"a": "dict"}, None, 42, True]


def run_gate(gate, workspace):
    r = subprocess.run([sys.executable, str(SCRIPTS / f"{gate}.py"),
                        "--workspace", str(workspace)],
                       capture_output=True, text=True, encoding="utf-8")
    journal = workspace / "journal.jsonl"
    receipts = (len([l for l in journal.read_text(encoding="utf-8").splitlines() if l.strip()])
                if journal.exists() else 0)
    return r.returncode, receipts, r.stderr


def assert_contract(gate, workspace):
    code, receipts, err = run_gate(gate, workspace)
    assert "Traceback" not in err, f"{gate} raised:\n{err[-600:]}"
    if code == 1:
        assert receipts >= 1, (
            f"{gate} exited 1 (findings) with no receipt — a composer reads that "
            f"as a gate that never ran")


# ---- the four that were reproduced ----------------------------------------

def test_a_scalar_stated_conditions_does_not_crash_consistency(tmp_path):
    """`stated_conditions: none` is a plausible way to write "there are none",
    and iterating a string yields its characters."""
    doc = copy.deepcopy(VALID_ASSESSMENT)
    doc["stated_conditions"] = "none"
    (tmp_path / "fit-assessment.yaml").write_text(
        yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    assert_contract("consistency", tmp_path)


def test_a_scalar_condition_row_does_not_crash_consistency(tmp_path):
    """`condition or {}` is the exact idiom `journal.as_mapping` replaces."""
    doc = copy.deepcopy(VALID_ASSESSMENT)
    doc["stated_conditions"] = ["visa_sponsorship"]
    (tmp_path / "fit-assessment.yaml").write_text(
        yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    assert_contract("consistency", tmp_path)


def test_an_unhashable_verdict_does_not_crash_count_coverage(tmp_path):
    """One stray bracket: `verdict: [worth_applying]` raised
    `TypeError: unhashable type: 'list'` inside a dict lookup."""
    doc = copy.deepcopy(VALID_ASSESSMENT)
    doc["verdict"] = ["worth_applying"]
    (tmp_path / "fit-assessment.yaml").write_text(
        yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    assert_contract("count_coverage", tmp_path)
    import count_coverage
    assert count_coverage._verdict_zh(["worth_applying"]) == "证据不足—不出结论"
    assert count_coverage._verdict_zh("worth_applying") == "值得投"


def test_a_non_mapping_meta_does_not_crash_the_personal_data_gate(tmp_path):
    """`meta: "us"` reached `protected_fields`, the function that decides whether
    a date of birth may be rendered — so the interlock's own gate crashed."""
    doc = copy.deepcopy(VALID_PROFILE)
    doc["meta"] = "us"
    (tmp_path / "tailored-profile.yaml").write_text(
        yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    assert_contract("check_personal_data", tmp_path)


# ---- the renderer's half of the same contract -----------------------------

@pytest.mark.parametrize("key", ["meta", "contact"])
@pytest.mark.parametrize("wrong", WRONG_SHAPES)
def test_a_malformed_profile_is_exit_2_not_a_traceback(tmp_path, key, wrong):
    """A renderer has no receipt to leave, so the exit code IS the report.

    `load_profile` already raised a clear ValueError for a missing field, and
    `main` caught only `journal.YamlUnreadable` — so a profile that parses but
    has the wrong shape escaped as a traceback at exit 1, which in this script
    already means "rendered, and the PDF step failed".
    """
    doc = copy.deepcopy(VALID_PROFILE)
    doc[key] = wrong
    profile = tmp_path / "p.yaml"
    profile.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPTS / "render_cv.py"), str(profile),
                        "--format", "md", "--out", str(tmp_path / "cv.md")],
                       capture_output=True, text=True, encoding="utf-8")
    assert "Traceback" not in r.stderr, r.stderr[-400:]
    assert r.returncode in (0, 2), f"exit {r.returncode}: {r.stderr[-300:]}"
    if r.returncode == 2:
        assert "cannot render" in r.stderr


# ---- the property, which is what actually generalises ---------------------

def _leaf_paths(obj, prefix=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield prefix + (k,)
            yield from _leaf_paths(v, prefix + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield prefix + (i,)
            yield from _leaf_paths(v, prefix + (i,))


def _set_in(doc, path, value):
    cur = doc
    for step in path[:-1]:
        cur = cur[step]
    cur[path[-1]] = value


ASSESSMENT_GATES = ["consistency", "count_coverage", "check_assessment"]


@pytest.mark.parametrize("wrong", WRONG_SHAPES)
def test_every_field_of_an_assessment_may_be_the_wrong_type(tmp_path, wrong):
    """Mutate each field in turn; no gate may break the contract on any of them.

    This is the assertion that found the defects. Naming four inputs pins four
    regressions; walking the document finds the fifth, which is how `meta: "us"`
    turned up in a sweep aimed at `stated_conditions`.
    """
    for n, path in enumerate(_leaf_paths(VALID_ASSESSMENT)):
        doc = copy.deepcopy(VALID_ASSESSMENT)
        try:
            _set_in(doc, path, wrong)
        except (KeyError, IndexError, TypeError):
            continue
        ws = tmp_path / f"ws{n}"
        ws.mkdir()
        (ws / "fit-assessment.yaml").write_text(
            yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
        for gate in ASSESSMENT_GATES:
            assert_contract(gate, ws)
