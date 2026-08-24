"""The real assertions.yaml, linted with the real checker registry.

This is the test that keeps the data honest as the set grows: it runs the same
lint CI runs, and it separately asserts the properties the lint cannot know
about — that all twenty evals are present, that every scenario named on disk is
used, that every fixture an eval names exists, that no assertion rests on an
unmeasured fixture while claiming to be evidence about the skill, and that the
retired iteration-1 assertion is recorded rather than deleted.

The second half of the file pins the two linter rules Task 10 added, because
writing the data is what revealed the need for them: one decoy serves three
guards, so `quiet_twin` has to be a list; and the escape hatch for judgement-
based assertions must not become a way to smuggle an untwinned guard into the
set.
"""
import json
import pathlib
import sys

import pytest
import yaml

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals import checkers as ck        # noqa: E402
from evals import lint_assertions as la  # noqa: E402
from evals import schema                # noqa: E402

REPO = _REPO_ROOT
EVALS = REPO / "evals"
DOC = yaml.safe_load((EVALS / "assertions.yaml").read_text(encoding="utf-8"))

ASSERTIONS = [a for e in DOC["evals"] for a in e["assertions"]]


# ---- the document itself ----------------------------------------------------

def test_the_real_document_lints_clean():
    findings = la.lint(DOC, scenario_root=EVALS, checkers=ck.CHECKERS,
                       twins=ck.TWINS)
    assert findings == [], "\n".join(findings)


def test_all_twenty_evals_are_present_with_contiguous_ids():
    assert sorted(e["id"] for e in DOC["evals"]) == list(range(20))


def test_every_scenario_file_on_disk_is_used_by_an_eval():
    used = {pathlib.Path(e["scenario"]).name for e in DOC["evals"]}
    on_disk = {p.name for p in (EVALS / "scenarios").glob("*.md")}
    assert on_disk - used == set(), f"unused scenario files: {on_disk - used}"


def test_every_eval_has_at_least_one_assertion_and_the_guards_discriminate():
    guards = [e for e in DOC["evals"] if e["id"] >= 5 and "decoy" not in
              (e.get("notes") or "")]
    for ev in DOC["evals"]:
        assert ev["assertions"], f"eval {ev['id']} has no assertions"
    for ev in guards:
        roles = {a["role"] for a in ev["assertions"]}
        assert "discriminating" in roles, (
            f"guard eval {ev['id']} has no discriminating assertion, so a "
            "passing run says nothing about the skill")


def test_every_eval_declares_a_baseline_arm():
    """Three of iteration-1's five evals had 'baseline': null and therefore
    measured nothing comparative at all."""
    for ev in DOC["evals"]:
        assert ev["baseline_kind"] in ("old_skill", "no_skill")


def test_the_apply_evals_baseline_against_the_old_skill_and_the_rest_do_not():
    """§2: apply mode IS the archived job-application skill, so the honest
    baseline there is old_skill. Pointing a discover/assess/interview eval at it
    would measure a skill being asked to do something it never claimed to do."""
    for ev in DOC["evals"]:
        expected = "old_skill" if ev["mode"] == "apply" else "no_skill"
        assert ev["baseline_kind"] == expected, (
            f"eval {ev['id']} is mode {ev['mode']} with baseline_kind "
            f"{ev['baseline_kind']!r}")


def test_the_iteration_1_non_discriminating_assertion_is_retired_not_deleted():
    retired = {r["id"]: r for r in DOC["retired"]}
    assert "A2-3" in retired
    entry = retired["A2-3"]
    assert "HONEST STRETCH" in entry["text"]
    assert "non-discriminating" in entry["reason"].lower()
    assert entry["replaced_by"] == "A16-1"


def test_the_retired_replacement_lives_in_this_same_file():
    """lint_assertions.main() passes no extra_assertion_ids, so a `replaced_by`
    pointing outside the document is RETIRED_REPLACEMENT_MISSING at CI time.
    Pinned here too because the CLI-level failure names the linter, not the
    edit that caused it."""
    ids = {a["id"] for a in ASSERTIONS}
    for r in DOC["retired"]:
        assert r["replaced_by"] in ids, r


def test_every_registered_checker_is_used_by_at_least_one_assertion():
    used = {a["checker"] for a in ASSERTIONS}
    unused = sorted(set(ck.CHECKERS) - used)
    assert unused == [], (
        f"registered but never used: {unused}. A checker nothing calls is a "
        "test that never runs.")


def test_no_assertion_id_is_reused_and_each_names_its_eval():
    ids = [a["id"] for a in ASSERTIONS]
    assert len(ids) == len(set(ids)), "duplicate assertion id"
    for ev in DOC["evals"]:
        for a in ev["assertions"]:
            assert a["id"].startswith(f"A{ev['id']}-"), (
                f"{a['id']} sits in eval {ev['id']}")


# ---- the constraints the lint cannot see ------------------------------------

@pytest.mark.parametrize("prefix", ["/Users/", "/home/", "/private/tmp",
                                    "/var/folders/", "/tmp/"])
def test_the_data_file_carries_no_machine_specific_absolute_path(prefix):
    """The lint's own abs-path guard globs evals/*.py and never sees this file.
    A scratchpad path committed here passes on one machine and fails on every
    other, blaming whichever module happens to read it."""
    text = (EVALS / "assertions.yaml").read_text(encoding="utf-8")
    assert prefix not in text, f"assertions.yaml carries {prefix!r}"


@pytest.mark.parametrize("key", ["fixture", "prepared_workspace"])
def test_every_fixture_an_eval_names_exists_on_disk(key):
    """`scenario` is checked by the lint; these two are not, and a typo in one
    surfaces as a run that silently used the wrong capture."""
    named = [(e["id"], e[key]) for e in DOC["evals"] if e.get(key)]
    assert named, f"no eval names a {key} — the wiring, not the test, moved"
    for eid, rel in named:
        assert (EVALS / rel).exists(), f"eval {eid} names {rel}, which is absent"


def test_no_assertion_resting_on_an_unmeasured_fixture_claims_to_be_evidence():
    """The plan's "no fabricated inputs" constraint, mechanised.

    A fixture carrying `"measured": false` is a shape nobody captured. An
    assertion graded against it may still catch a regression, but calling it
    `discriminating` presents a guess as measured evidence about the skill.
    evals/fixtures/opencli/51job-zero.json is the one such body, and it says so
    in its own `source` field.
    """
    offenders = []
    for ev in DOC["evals"]:
        rel = ev.get("fixture")
        if not rel:
            continue
        body = json.loads((EVALS / rel).read_text(encoding="utf-8"))
        if body.get("measured") is not False:
            continue
        for a in ev["assertions"]:
            if a["role"] == "discriminating":
                offenders.append(f"{a['id']} (fixture {rel})")
    assert offenders == [], (
        "these assertions rest on an unmeasured fixture yet claim to be "
        f"evidence about the skill: {offenders}")


def test_at_least_one_fixture_is_actually_marked_unmeasured():
    """Guards the test above against passing because nothing is flagged: if
    every fixture were `measured: true` the rule would be vacuous."""
    flags = [json.loads((EVALS / e["fixture"]).read_text(encoding="utf-8"))
             .get("measured")
             for e in DOC["evals"] if e.get("fixture")]
    assert False in flags, "no fixture carries measured: false any more"


def test_every_role_and_expected_baseline_comes_from_the_schema():
    """Imported, never re-spelled: a value renamed in evals/schema.py must break
    this file rather than leave the data using a word the linter dropped."""
    for a in ASSERTIONS:
        assert a["role"] in schema.ROLES, a["id"]
        assert a["expected_baseline"] in schema.EXPECTED_BASELINE, a["id"]
    for ev in DOC["evals"]:
        assert ev["mode"] in schema.MODES, ev["id"]
        assert ev["baseline_kind"] in schema.BASELINE_KINDS, ev["id"]


def test_the_untwinned_checkers_are_the_declared_ones_and_carry_no_guard():
    """UNTWINNED_BY_DESIGN is an exemption with a name, not a hole. Every member
    must be registered, none may be twinned, and none may decide a
    discriminating assertion that has not named its own twin_assertion."""
    assert ck.UNTWINNED_BY_DESIGN <= set(ck.CHECKERS)
    assert not (ck.UNTWINNED_BY_DESIGN & set(ck.TWINS))
    assert set(ck.CHECKERS) - set(ck.TWINS) == set(ck.UNTWINNED_BY_DESIGN)
    for a in ASSERTIONS:
        if a["checker"] in ck.UNTWINNED_BY_DESIGN and a["role"] == "discriminating":
            assert a.get("twin_assertion"), a["id"]


def test_every_named_twin_assertion_exists_and_is_not_in_its_own_eval():
    ids_by_eval = {e["id"]: {a["id"] for a in e["assertions"]}
                   for e in DOC["evals"]}
    for ev in DOC["evals"]:
        for a in ev["assertions"]:
            named = a.get("twin_assertion")
            if not named:
                continue
            assert named not in ids_by_eval[ev["id"]], (
                f"{a['id']} names a twin_assertion inside its own eval")
            assert any(named in s for s in ids_by_eval.values()), named


def test_a_decoy_is_named_by_every_guard_it_decoys():
    """quiet_twin is declared one way round in the data; a checker-twinned
    pairing is only useful if it holds both ways, so the decoy must name its
    guards back.

    The one legitimate one-way reference is an eval named ONLY to host a
    `twin_assertion` — eval 0 names eval 3 so A0-3 ("lead with the credential")
    can be pinned by A3-1 ("lead with the executive summary"), and eval 3 is a
    carried-forward regression eval that decoys nothing. That case is allowed
    here and nowhere else.
    """
    declared = {e["id"]: set(la._declared_twins(e)) for e in DOC["evals"]}
    for eid, twins in declared.items():
        ev = next(e for e in DOC["evals"] if e["id"] == eid)
        hosted = {int(a["twin_assertion"].split("-")[0].lstrip("A"))
                  for a in ev["assertions"] if a.get("twin_assertion")}
        for twin_id in twins:
            assert eid in declared[twin_id] or twin_id in hosted, (
                f"eval {eid} names {twin_id} as its quiet twin, {twin_id} does "
                f"not name {eid} back, and no assertion in {eid} names a "
                f"twin_assertion living in {twin_id}")
    assert declared[8] == {5, 6, 9}
    assert declared[12] == {10, 11, 13}


# ---- the two linter rules this data forced ----------------------------------

CHECKERS = {"guard_a": None, "twin_a": None, "guard_b": None, "twin_b": None,
            "loose": None}
TWINS = {"guard_a": "twin_a", "twin_a": "guard_a",
         "guard_b": "twin_b", "twin_b": "guard_b"}


def _doc():
    """Two guards decoyed by ONE eval — the shape the real file needed."""
    return {"evals": [
        {"id": 5, "name": "g1", "mode": "discover", "baseline_kind": "no_skill",
         "scenario": "scenarios/discover-blocked-adapter.md", "quiet_twin": 8,
         "assertions": [
             {"id": "A5-1", "text": "The run never claims there are no jobs.",
              "role": "discriminating", "expected_baseline": "fail",
              "falsifier": "A final message saying 没有匹配 with no exit-0 call.",
              "checker": "guard_a"}]},
        {"id": 6, "name": "g2", "mode": "discover", "baseline_kind": "no_skill",
         "scenario": "scenarios/discover-blank-identity-rows.md",
         "quiet_twin": 8,
         "assertions": [
             {"id": "A6-1", "text": "Blank rows are recovered or reported.",
              "role": "discriminating", "expected_baseline": "fail",
              "falsifier": "A run reading an exit-0 blank-title body as absence.",
              "checker": "guard_b"}]},
        {"id": 8, "name": "decoy", "mode": "discover",
         "baseline_kind": "no_skill",
         "scenario": "scenarios/discover-clean-retrieval.md",
         "quiet_twin": [5, 6],
         "assertions": [
             {"id": "A8-1", "text": "A clean round prints no disclosure block.",
              "role": "discriminating", "expected_baseline": "fail",
              "falsifier": "Six disclosure lines under a shortlist of real rows.",
              "checker": "twin_a"},
             {"id": "A8-2", "text": "No recovery is claimed that did not happen.",
              "role": "discriminating", "expected_baseline": "fail",
              "falsifier": "§0 saying 已取详情补齐 with no detail call logged.",
              "checker": "twin_b"}]},
    ]}


def _lint(d):
    return la.lint(d, scenario_root=EVALS, checkers=CHECKERS, twins=TWINS)


def test_the_shape_the_real_file_needed_lints_clean():
    assert _lint(_doc()) == []


def test_one_decoy_can_serve_several_guards_via_a_list_valued_quiet_twin():
    """A scalar quiet_twin on eval 8 can only name one of its two guards, and
    the other guard's twin checker then looks unused. The list is the fix, so
    both halves are pinned: the list is quiet, the scalar is not."""
    assert _lint(_doc()) == []               # quiet_twin: [5, 6]
    d = _doc()
    d["evals"][2]["quiet_twin"] = 5          # was [5, 6]
    out = _lint(d)
    assert any(f.startswith("TWIN_MISSING_CHECKER: A8-2") for f in out), out


def test_a_member_of_a_list_valued_quiet_twin_that_is_no_eval_is_rejected():
    d = _doc()
    d["evals"][2]["quiet_twin"] = [5, 6, 99]
    out = _lint(d)
    assert any(f.startswith("NO_QUIET_TWIN: 8") and "99" in f for f in out), out
    assert not any(f.startswith("TWIN_MISSING_CHECKER") for f in out), out


def test_a_discriminating_assertion_on_an_untwinned_checker_is_rejected():
    d = _doc()
    d["evals"][0]["assertions"][0]["checker"] = "loose"
    out = _lint(d)
    assert any(f.startswith("UNTWINNED_DISCRIMINATING: A5-1") for f in out), out


def test_a_regression_assertion_on_an_untwinned_checker_is_allowed():
    d = _doc()
    a = d["evals"][0]["assertions"][0]
    a["checker"] = "loose"
    a["role"] = "regression"
    a["expected_baseline"] = "pass"
    out = _lint(d)
    assert not any(f.startswith("UNTWINNED_DISCRIMINATING") for f in out), out


def test_a_reader_graded_guard_may_name_its_twin_assertion():
    """Both sides move to the untwinned checker: a reader-graded guard and the
    reader-graded row in its decoy that pins the opposite answer."""
    d = _doc()
    a = d["evals"][0]["assertions"][0]
    a["checker"] = "loose"
    a["twin_assertion"] = "A8-1"
    b = d["evals"][2]["assertions"][0]
    b["checker"] = "loose"
    b["twin_assertion"] = "A5-1"
    assert _lint(d) == []


def test_a_twin_assertion_outside_the_quiet_twin_evals_is_rejected():
    d = _doc()
    a = d["evals"][0]["assertions"][0]
    a["checker"] = "loose"
    a["twin_assertion"] = "A5-1"          # its own eval, not the twin's
    out = _lint(d)
    assert any(f.startswith("TWIN_ASSERTION_MISSING: A5-1") for f in out), out


def test_the_twin_rules_are_skipped_only_when_the_registry_is_unavailable():
    """--checkers-optional accepts any checker name because evals/checkers.py
    need not exist; without the registry the twin relation is unknown, and
    reporting UNTWINNED_DISCRIMINATING for every guard would be a finding about
    the linter's inputs. The skip must be exactly that case and no other."""
    d = _doc()
    assert la.lint(d, scenario_root=EVALS, checkers=CHECKERS, twins={}) == []
    d["evals"][2]["quiet_twin"] = 5
    assert la.lint(d, scenario_root=EVALS, checkers=CHECKERS, twins={}) == []
    assert any(f.startswith("TWIN_MISSING_CHECKER")
               for f in la.lint(d, scenario_root=EVALS, checkers=CHECKERS,
                                twins=TWINS))


@pytest.mark.parametrize("value,expected", [
    (None, []), (7, [7]), ([7], [7]), ([5, 6, 9], [5, 6, 9])])
def test_quiet_twin_reads_the_same_written_either_way(value, expected):
    assert la._declared_twins({"quiet_twin": value}) == expected


# ---- the CLI, as CI runs it -------------------------------------------------

def test_the_real_file_passes_the_script_as_ci_invokes_it():
    """In-process lint() is given extra_assertion_ids by some callers; main()
    is not, which is where a `replaced_by` pointing outside the file fails."""
    import subprocess
    proc = subprocess.run(
        [sys.executable, str(EVALS / "lint_assertions.py")],
        capture_output=True, text=True, cwd=str(REPO))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout == ""
