#!/usr/bin/env python3
"""Lint evals/assertions.yaml.

NOT a gate (see the plan's Global Constraints): no --workspace, no journal
receipt. exit 0 = clean, exit 1 = findings on stdout one per line each prefixed
with a stable UPPERCASE code, exit 2 = could not run with the reason on stderr
and nothing on stdout.

The finding this file exists for is NON_DISCRIMINATING_BY_CONSTRUCTION: an
assertion whose author expects the baseline to pass it, marked as evidence about
the skill, is not evidence about anything and must not reach a run.
"""
import argparse
import pathlib
import sys

import yaml

# Run either way: as `python3 -m evals.lint_assertions` (repo root already on the
# path) or as `python3 evals/lint_assertions.py`, where sys.path[0] is evals/ and
# the package would otherwise not import at all -- a crash on stderr with exit 1
# is indistinguishable from "one finding", which is the contract this file has to
# keep. The walk is to the repo root, never to a profile directory.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals import schema  # noqa: E402

DEFAULT_FILE = pathlib.Path(__file__).resolve().parent / "assertions.yaml"


def _unknown_keys(record, allowed):
    return sorted(k for k in record if k not in allowed)


def _declared_twins(ev):
    """`quiet_twin` as a list, however it was written.

    One decoy legitimately serves several guards -- eval 12 is the quiet case of
    the login-wall refusal, the refusal floor AND the expiry banner -- so a
    scalar cannot express the set. A scalar stays legal and means a list of one.
    """
    declared = ev.get("quiet_twin")
    if declared is None:
        return []
    return list(declared) if isinstance(declared, list) else [declared]


def lint(doc, *, scenario_root, checkers, twins, extra_assertion_ids=()):
    """Return findings, most structural first. Empty list means clean."""
    findings = []
    scenario_root = pathlib.Path(scenario_root)
    evals = doc.get("evals") or []
    if not evals:
        return ["NO_EVALS: the document declares no evals"]
    for key in _unknown_keys(doc, schema.DOC_KEYS):
        findings.append(f"UNKNOWN_KEY: the document has unknown key {key!r}, "
                        f"not in {schema.DOC_KEYS}")

    by_id = {}
    seen_assertion_ids = set(extra_assertion_ids)
    checker_use = {}          # eval id -> set of checker names

    for ev in evals:
        eid = ev.get("id")
        if eid in by_id:
            findings.append(f"DUP_EVAL_ID: {eid} appears more than once")
        by_id[eid] = ev
        for key in _unknown_keys(ev, schema.EVAL_KEYS):
            findings.append(f"UNKNOWN_KEY: eval {eid} has unknown key {key!r}")
        for key in schema.REQUIRED_EVAL_KEYS:
            if ev.get(key) in (None, "", []):
                findings.append(f"MISSING_KEY: eval {eid} has no {key!r}")
        if ev.get("mode") not in schema.MODES:
            findings.append(f"UNKNOWN_MODE: eval {eid} mode "
                            f"{ev.get('mode')!r} not in {schema.MODES}")
        if ev.get("baseline_kind") not in schema.BASELINE_KINDS:
            findings.append(f"BAD_BASELINE_KIND: eval {eid} "
                            f"{ev.get('baseline_kind')!r} not in "
                            f"{schema.BASELINE_KINDS}")
        scenario = ev.get("scenario")
        if scenario and not (scenario_root / scenario).is_file():
            findings.append(f"SCENARIO_MISSING: {eid} names "
                            f"{scenario!r}, which is not a file")
        checker_use[eid] = set()

    for ev in evals:
        eid = ev.get("id")
        for twin_id in _declared_twins(ev):
            if twin_id not in by_id:
                findings.append(f"NO_QUIET_TWIN: {eid} names quiet_twin "
                                f"{twin_id}, which is not an eval in this "
                                "document")
        for a in ev.get("assertions") or []:
            aid = a.get("id")
            if aid in seen_assertion_ids:
                findings.append(f"DUP_ID: {aid} appears more than once")
            seen_assertion_ids.add(aid)
            for key in _unknown_keys(a, schema.ASSERTION_KEYS):
                findings.append(f"UNKNOWN_KEY: {aid} has unknown key {key!r}")
            for key in schema.REQUIRED_ASSERTION_KEYS:
                if not a.get(key):
                    findings.append(f"MISSING_KEY: {aid} has no {key!r}")
            role = a.get("role")
            if role not in schema.ROLES:
                findings.append(f"BAD_ROLE: {aid} role {role!r} not in "
                                f"{schema.ROLES}")
            expected = a.get("expected_baseline")
            if expected not in schema.EXPECTED_BASELINE:
                findings.append(f"BAD_EXPECTED_BASELINE: {aid} {expected!r} not "
                                f"in {schema.EXPECTED_BASELINE}")
            arms = a.get("arms") or list(schema.ARMS)
            for arm in arms:
                if arm not in schema.ARMS:
                    findings.append(f"BAD_ARM: {aid} names arm {arm!r}")

            # `not_exercised` is rejected alongside `pass`, and for the same
            # reason: "not exercised" is not "fail". An author declaring that
            # the baseline never reaches the branch has declared the assertion
            # cannot compare the arms. Twelve of the iteration-2 pilot's 26
            # guards came back not-exercised and the lint had no way to say so
            # in advance.
            if role == "discriminating" and expected != "fail":
                cure = ("make the scenario force the branch, or re-role it as "
                        "regression with a written reason")
                if expected == "not_exercised":
                    cure = ("point the checker at a surface BOTH arms produce, "
                            "or set role: regression with arms: [with_skill] — "
                            "an assertion only one arm can reach is an audit of "
                            "that arm, not a comparison")
                findings.append(
                    f"NON_DISCRIMINATING_BY_CONSTRUCTION: {aid} is marked "
                    f"discriminating but its author expects the baseline to "
                    f"{expected!r} it. Then passing it says nothing about the "
                    f"skill. Either {cure}.")
            if (role == "regression" and expected != "pass"
                    and arms != ["with_skill"]):
                findings.append(
                    f"REGRESSION_BASELINE_MISMATCH: {aid} is regression but does "
                    f"not expect the baseline to pass ({expected!r}). A "
                    "regression assertion both arms cannot pass belongs to the "
                    "with_skill arm only — set arms: [with_skill] — or it is a "
                    "discriminating assertion wearing the wrong label.")

            # `not_exercised` removes a comparison. The reason belongs beside
            # the assertion, not in a commit message that never reaches the
            # reader of this file.
            if expected == "not_exercised" and \
                    len(str(a.get("note") or "").strip()) < schema.MIN_FALSIFIER_CHARS:
                findings.append(
                    f"UNEXPLAINED_SCOPING: {aid} expects the baseline not to "
                    f"reach it, which removes a comparison, and carries no "
                    f"`note` saying why. Write what the baseline would have to "
                    f"produce for this to be gradable.")

            falsifier = (a.get("falsifier") or "").strip()
            if len(falsifier) < schema.MIN_FALSIFIER_CHARS:
                findings.append(
                    f"NO_FALSIFIER: {aid} has no usable falsifier. Write what an "
                    "output that FAILS this assertion looks like; if you cannot, "
                    "the assertion is a restatement of the skill's own summary.")
            elif falsifier.strip().lower() == (a.get("text") or "").strip().lower():
                findings.append(f"FALSIFIER_RESTATES: {aid} falsifier is the "
                                "assertion text again")

            checker = a.get("checker")
            if checker and checker not in checkers:
                findings.append(f"UNKNOWN_CHECKER: {aid} names {checker!r}, "
                                "which is not registered in evals/checkers.py")
            if checker:
                checker_use[eid].add(checker)

    # The twin rule, last, because it needs every eval's checker set.
    #
    # An EMPTY `twins` map means the checker registry was not available at all
    # -- the --checkers-optional path, which accepts any checker name because
    # evals/checkers.py need not exist yet. The twin relation cannot be decided
    # from nothing, and reporting UNTWINNED_DISCRIMINATING for every guard in the
    # document would be a finding about the linter's own inputs rather than about
    # the data. The rules below are therefore skipped, loudly in the sense that
    # the flag is documented as "for testing the linter itself".
    if twins:
        for ev in evals:
            declared = _declared_twins(ev)
            available = set()
            twin_assertion_ids = set()
            for twin_id in declared:
                available |= checker_use.get(twin_id, set())
                twin_assertion_ids |= {
                    x.get("id") for x in
                    (by_id.get(twin_id, {}).get("assertions") or [])}
            for a in ev.get("assertions") or []:
                checker = a.get("checker")
                twin = twins.get(checker)
                if not twin:
                    if a.get("role") != "discriminating":
                        continue
                    named = a.get("twin_assertion")
                    if not named:
                        findings.append(
                            f"UNTWINNED_DISCRIMINATING: {a.get('id')} uses "
                            f"{checker!r}, which has no twin, and names no "
                            "twin_assertion. A discriminating assertion with no "
                            "quiet case cannot tell a working defence from a "
                            "policy of always firing.")
                    elif named not in twin_assertion_ids:
                        findings.append(
                            f"TWIN_ASSERTION_MISSING: {a.get('id')} names "
                            f"twin_assertion {named!r}, which is not an assertion "
                            f"in any of its quiet_twin eval(s) {declared}.")
                    continue
                if twin not in available:
                    findings.append(
                        f"TWIN_MISSING_CHECKER: {a.get('id')} uses {checker!r}, "
                        f"whose twin {twin!r} is used by none of the quiet_twin "
                        f"eval(s) {declared}. A guard with no quiet twin scores "
                        "100% for a policy that always refuses.")

    # ---- coverage: a mode may not quietly lose its last guard ---------------
    #
    # Every remedy the pilot recommends is a REDUCTION -- re-role it, scope it
    # to one arm, retire it. Each is honest alone, and the sequence ends at an
    # eval with nothing left that could fail, which exits 0 for that reason.
    # A mode losing its last comparison has to be a statement someone made.
    #
    # An assertion scoped to arms: [with_skill] is NOT a guard: the baseline is
    # never graded on it, so it audits the skill rather than comparing the arms.
    guarded = {}
    for ev in evals:
        mode = ev.get("mode")
        for a in ev.get("assertions") or []:
            if a.get("role") != "discriminating":
                continue
            if "baseline" not in (a.get("arms") or list(schema.ARMS)):
                continue
            guarded.setdefault(mode, []).append(a.get("id"))

    coverage = doc.get("coverage") or {}
    if not isinstance(coverage, dict):
        # A gate, not a script: reaching .get on a string exits 1 with a
        # traceback, and 1 is this file's code for "findings". A malformed
        # document has to be distinguishable from a failing one.
        findings.append(f"BAD_COVERAGE: `coverage` is {type(coverage).__name__}, "
                        f"expected a mapping with modes_without_a_guard and/or "
                        f"evals_without_a_guard")
        coverage = {}
    declared = coverage.get("modes_without_a_guard") or {}
    if not isinstance(declared, dict):
        findings.append("BAD_COVERAGE: modes_without_a_guard must be a mapping "
                        "of mode -> reason")
        declared = {}
    for mode in sorted(declared):
        if mode not in schema.MODES:
            findings.append(
                f"UNKNOWN_MODE: coverage.modes_without_a_guard names {mode!r}, "
                f"not in {schema.MODES}. A typo here exempts nothing while "
                f"looking exactly like an exemption that works.")
            continue
        reason = str(declared.get(mode) or "").strip()
        if len(reason) < schema.MIN_FALSIFIER_CHARS:
            findings.append(
                f"THIN_COVERAGE_REASON: coverage.modes_without_a_guard[{mode!r}] "
                f"says {reason!r}. A mode measuring nothing about the skill "
                f"needs a reason a reader can check, not a shrug.")
        if guarded.get(mode):
            findings.append(
                f"STALE_COVERAGE_DECLARATION: {mode!r} is listed as having no "
                f"guard, but {', '.join(sorted(guarded[mode]))} discriminate(s) "
                f"on it. The note claims the eval is weaker than it is, and the "
                f"next reader re-roles the real guard away without a red line.")

    # Same rule one level down: an eval that hosts no guard is not a defect --
    # decoys exist on purpose -- but it must be a statement someone made, or a
    # guard eval quietly becomes a regression eval and nobody sees it happen.
    guard_evals = {ev["id"] for ev in evals
                   for a in (ev.get("assertions") or [])
                   if a.get("role") == "discriminating"
                   and "baseline" in (a.get("arms") or list(schema.ARMS))}
    declared_evals = coverage.get("evals_without_a_guard") or {}
    if not isinstance(declared_evals, dict):
        findings.append("BAD_COVERAGE: evals_without_a_guard must be a mapping "
                        "of eval id -> reason")
        declared_evals = {}
    known = {ev["id"] for ev in evals}
    for eid in sorted(declared_evals, key=str):
        if eid not in known:
            findings.append(f"UNKNOWN_EVAL: coverage.evals_without_a_guard "
                            f"names {eid!r}, which is not an eval in this file")
            continue
        reason = str(declared_evals.get(eid) or "").strip()
        if len(reason) < schema.MIN_FALSIFIER_CHARS:
            findings.append(
                f"THIN_COVERAGE_REASON: coverage.evals_without_a_guard[{eid!r}] "
                f"says {reason!r}, which a reader cannot check.")
        if eid in guard_evals:
            findings.append(
                f"STALE_COVERAGE_DECLARATION: eval {eid} is listed as hosting no "
                f"guard and it hosts one. Remove the declaration, or the next "
                f"reader re-roles the real guard away without a red line.")
    for ev in evals:
        if ev["id"] in guard_evals or ev["id"] in declared_evals:
            continue
        findings.append(
            f"EVAL_HAS_NO_GUARD: eval {ev['id']} ({ev.get('name')!r}) hosts no "
            f"discriminating assertion that compares the arms. Decoys are "
            f"supposed to look like this -- declare it in "
            f"coverage.evals_without_a_guard with the reason.")

    for mode in sorted({ev.get("mode") for ev in evals} & set(schema.MODES)):
        if not guarded.get(mode) and mode not in declared:
            findings.append(
                f"MODE_HAS_NO_GUARD: no discriminating assertion compares the "
                f"arms in {mode!r} mode, so this iteration measures nothing "
                f"about the skill there. Point a checker at a surface both arms "
                f"produce, or declare it in coverage.modes_without_a_guard with "
                f"the reason.")

    for r in doc.get("retired") or []:
        rid = r.get("id")
        for key in _unknown_keys(r, schema.RETIRED_KEYS):
            findings.append(f"UNKNOWN_KEY: retired {rid} has unknown key {key!r}")
        if not (r.get("reason") or "").strip():
            findings.append(f"RETIRED_NO_REASON: {rid} was retired with no "
                            "written reason")
        replacement = r.get("replaced_by")
        if replacement and replacement not in seen_assertion_ids:
            findings.append(f"RETIRED_REPLACEMENT_MISSING: {rid} says it was "
                            f"replaced by {replacement}, which does not exist")
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=str(DEFAULT_FILE))
    parser.add_argument("--checkers-optional", action="store_true",
                        help="accept any checker name; for testing the linter "
                             "itself before evals/checkers.py exists")
    args = parser.parse_args(argv)

    path = pathlib.Path(args.file)
    if not path.is_file():
        print(f"cannot run: {path} does not exist", file=sys.stderr)
        return 2
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        print(f"cannot run: {path} is not valid YAML: {exc}", file=sys.stderr)
        return 2

    if args.checkers_optional:
        names = {a.get("checker")
                 for ev in doc.get("evals") or []
                 for a in ev.get("assertions") or []}
        checkers = {n: None for n in names if n}
        twins = {}
    else:
        try:
            from evals import checkers as ck
        except ImportError as exc:
            print(f"cannot run: evals/checkers.py is not importable: {exc}",
                  file=sys.stderr)
            return 2
        checkers, twins = ck.CHECKERS, ck.TWINS

    findings = lint(doc, scenario_root=path.parent, checkers=checkers,
                    twins=twins)
    for f in findings:
        print(f)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
