"""The apply checkers: the measured Cluster-1 leak, and honest-stop vs. giving up.

Two pairs, and each half of each pair is tested twice — once on the run it must
fail and once on the run it must stay silent about. A guard tested only on the
run it must fail rewards the degenerate policy: strip everything, stop always.
Here the decoys make both of those cost full marks — a German CV stripped of the
photo its market expects fails, and an application abandoned over a keyword the
candidate genuinely has fails.

The other job of this file is to pin the harness to the skill. A checker whose
field name, market spelling, warning wording or file shape has drifted from what
the skill emits does not go quiet — it goes *permanently green*, reporting "not
exercised" over the exact leak it was written for. Every such coupling below is
asserted against the live `scripts/` code rather than restated as a constant.
"""
import json

import pytest
import yaml

import check_apply
import check_claims
import check_personal_data
import journal
import render_cv

from evals import checkers as ck
from evals import runlib

DOB = "14 March 1990"

# The literal string from iteration-1's eval-0 scenario. The old renderer's
# `_is_cluster1` did an exact lowercase token lookup and did not recognise it, so
# a DOB rendered onto a US CV — while the assertion "no DOB in the rendered CV"
# was recorded as PASSING, because the model had stripped the field by hand.
US_MARKET = "United States (Los Angeles, CA)"
DE_MARKET = "Germany (Munich)"

US_PROFILE = {"meta": {"name": "Maria Santos", "target_market": US_MARKET}}
US_PROFILE_STILL_CARRYING = {
    "meta": {"name": "Maria Santos", "target_market": US_MARKET},
    "contact": {"personal": {"date_of_birth": DOB}}}
DE_PROFILE = {"meta": {"name": "Jonas Weber", "target_market": DE_MARKET,
                       "photo": "assets/jonas.jpg"},
              "contact": {"personal": {"date_of_birth": DOB}}}

RECEIPT = {"action": "gate", "gate": "check_personal_data", "verdict": "pass",
           "findings": []}
CLAIMS_RECEIPT = {"action": "gate", "gate": "check_claims", "verdict": "pass",
                  "findings": []}
UNKNOWN_MARKET_WARNING = (
    "WARNING: meta.target_market 'Mars (Olympus City)' matches no known "
    "CV-convention cluster, so the Cluster-1 personal-data interlock cannot "
    "fire. These fields will render as-is: contact.personal.date_of_birth, "
    "meta.photo.\n")


def build(tmp_path, *, profile=None, cv=None, stderr="", records=(),
          honest_stop=None, claims=None, final=""):
    """One run directory, laid out as runlib.OUTPUT_CONTRACT promises.

    `claims` is a BARE LIST — the shape check_claims.py loads with
    `expect=list` and the shape modes/apply.md documents.
    """
    out = tmp_path / "outputs"
    ws = out / "workspace"
    ws.mkdir(parents=True)
    (out / "final-message.md").write_text(final, encoding="utf-8")
    (out / "stderr.log").write_text(stderr, encoding="utf-8")
    if cv is not None:
        (ws / "cv.md").write_text(cv, encoding="utf-8")
    if profile is not None:
        (ws / "tailored-profile.yaml").write_text(
            yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
        # Stage the photo the profile declares. A fixture that names a photo
        # and ships no file cannot distinguish "the run dropped it" from "it was
        # never on disk" — which is exactly the cry-wolf that failed eval-15 in
        # the iteration-2 pilot. A test asserting the photo was DROPPED has to
        # make the photo available first, or it is asserting something else.
        declared = str((profile.get("meta") or {}).get("photo") or "").strip()
        if declared:
            photo = ws / declared.lstrip("/")
            photo.parent.mkdir(parents=True, exist_ok=True)
            photo.write_bytes(b"\xff\xd8\xff\xe0staged for the fixture")
    if honest_stop is not None:
        (ws / "honest-stop.yaml").write_text(
            yaml.safe_dump(honest_stop, allow_unicode=True), encoding="utf-8")
    if claims is not None:
        (ws / "claims.yaml").write_text(
            yaml.safe_dump(claims, allow_unicode=True), encoding="utf-8")
    (ws / "journal.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return runlib.Run(tmp_path)


# ---- the couplings that decide whether any of this can ever fire ------------

def test_the_market_field_is_the_one_the_skill_reads():
    """`meta.market` would be a checker that reports "not exercised" over every
    real run for ever: the gate, the renderer and modes/apply.md all read
    `meta.target_market`, and nothing writes the other spelling."""
    assert ck.MARKET_FIELD == "meta.target_market"
    findings = check_personal_data.findings_for(US_PROFILE_STILL_CARRYING)
    assert findings and findings[0].startswith("CLUSTER1_PERSONAL_DATA"), findings
    # ...and the same profile with the field renamed is invisible to the gate,
    # which is exactly what a checker reading the wrong key would be grading.
    renamed = {"meta": {"market": US_MARKET},
               "contact": {"personal": {"date_of_birth": DOB}}}
    assert check_personal_data.findings_for(renamed)[0].startswith(
        "NO_TARGET_MARKET")


def test_the_interlock_fires_for_the_market_string_iteration_1_leaked_on():
    """The measured defect, pinned at its source. If `resolve_cluster` stops
    recognising this string the leak is back, and this test — not a silent
    "not exercised" in a grading.json — is what says so."""
    assert render_cv.resolve_cluster(US_MARKET) == 1
    assert render_cv.protected_fields(US_PROFILE_STILL_CARRYING) == [
        "contact.personal.date_of_birth"]


@pytest.mark.parametrize("spelling", ck.CLUSTER1_MARKET_SPELLINGS)
def test_every_cluster1_spelling_the_harness_knows_is_cluster1_to_the_skill(
        spelling):
    """The harness keeps its own reading of which market a scenario targets, so
    that a broken resolver cannot make its own guard report "not exercised".
    That independence is only honest while the two agree: a disagreement is a
    red test here rather than a quiet non-result in a benchmark."""
    assert render_cv.resolve_cluster(spelling) == 1


@pytest.mark.parametrize("spelling", ck.CONVENTIONAL_PHOTO_MARKET_SPELLINGS)
def test_every_conventional_spelling_is_cluster_2_or_3_to_the_skill(spelling):
    assert render_cv.resolve_cluster(spelling) in (2, 3)


def test_the_derived_markers_are_how_the_renderer_actually_writes_them():
    """`contact.personal.date_of_birth` → `date of birth` is only a valid marker
    while the renderer titles it that way. Rendered here, not asserted from
    memory."""
    profile = {"meta": {"name": "Jonas Weber", "target_market": DE_MARKET},
               "contact": {"personal": {"date_of_birth": DOB,
                                        "marital_status": "single"}}}
    md = render_cv.render_markdown(profile)
    for field in render_cv.protected_fields(profile):
        label = ck._field_label(field)
        assert ck._marker_re(label).search(md), (label, md.splitlines()[:5])


def test_the_live_renderer_warning_still_matches_both_patterns(capsys):
    """The two regexes the interlock checkers read stderr with, checked against
    the warning the renderer emits today rather than against a remembered
    wording. `unknown market` never appears in it — the phrase an earlier draft
    grepped for — which would have made the twin unfireable."""
    render_cv.reset_market_warnings()
    render_cv.render_markdown({"meta": {"name": "X", "target_market": "Mars"},
                               "contact": {"personal": {"date_of_birth": DOB}}})
    err = capsys.readouterr().err
    assert "WARNING" in err
    assert ck._UNKNOWN_MARKET.search(err), err
    assert ck._PROTECTED_FIELD_NAME.search(err), err


def test_the_deciding_receipt_verdicts_are_a_real_subset_of_the_journals():
    """A receipt only shows the interlock ran if it says the gate DECIDED. If a
    new verdict joins the shared vocabulary it must be classified here on
    purpose, not inherited as a pass."""
    assert set(ck.DECIDED_RECEIPT_VERDICTS) < set(journal.VERDICTS)
    undecided = set(journal.VERDICTS) - set(ck.DECIDED_RECEIPT_VERDICTS)
    assert undecided == {"could_not_run", "recorded", "baseline_recorded"}


def test_the_stop_and_claim_vocabularies_come_from_the_skill():
    assert check_apply.CLASSIFICATIONS == ("poorly_built", "honest_stretch")
    assert "profile-line" in check_claims.SOURCE_KINDS


def test_claims_yaml_is_the_bare_list_the_gate_loads(tmp_path):
    """The shape this harness reads is the shape check_claims.py reads. A
    `{claims: [...]}` mapping makes that gate exit 2, so a checker that accepted
    it would be grading a file the skill cannot use."""
    path = tmp_path / "claims.yaml"
    path.write_text(yaml.safe_dump([SLURM_CLAIM], allow_unicode=True),
                    encoding="utf-8")
    assert journal.load_yaml(path, expect=list) == [SLURM_CLAIM]
    path.write_text(yaml.safe_dump({"claims": [SLURM_CLAIM]}),
                    encoding="utf-8")
    with pytest.raises(journal.YamlUnreadable):
        journal.load_yaml(path, expect=list)


# ---- Cluster-1: the artifact ------------------------------------------------

def test_a_us_cv_carrying_a_date_of_birth_fires(tmp_path):
    run = build(tmp_path, profile=US_PROFILE,
                cv=f"# Maria Santos\nDate of birth: {DOB}\n")
    passed, evidence = ck.CHECKERS["personal_data_stripped_for_cluster1"](run)
    assert passed is False
    assert DOB in evidence


def test_a_us_cv_whose_profile_still_carries_the_field_fires(tmp_path):
    """The renderer's own output, not a hand-typed line: `Date Of Birth` is what
    render_cv titles the key into, and the marker is derived from the profile."""
    run = build(tmp_path, profile=US_PROFILE_STILL_CARRYING,
                cv=render_cv.render_markdown(
                    dict(US_PROFILE_STILL_CARRYING,
                         meta={"name": "Maria Santos",
                               "target_market": DE_MARKET})))
    passed, evidence = ck.CHECKERS["personal_data_stripped_for_cluster1"](run)
    assert passed is False
    assert DOB in evidence


def test_a_us_cv_with_the_data_stripped_is_quiet(tmp_path):
    run = build(tmp_path, profile=US_PROFILE,
                cv="# Maria Santos\nRN, Los Angeles CA\n")
    passed, evidence = ck.CHECKERS["personal_data_stripped_for_cluster1"](run)
    assert passed is True, evidence


def test_a_protected_key_no_fixed_list_names_still_fires(tmp_path):
    """`contact.personal` is free-form. A marker list alone under-reports every
    key nobody thought of, which is why the authoritative half of the scan is
    derived from the run's own profile."""
    profile = {"meta": {"name": "Maria Santos", "target_market": US_MARKET},
               "contact": {"personal": {"hometown": "Cebu, Philippines"}}}
    run = build(tmp_path, profile=profile,
                cv="# Maria Santos\nHometown: Cebu, Philippines\n")
    passed, evidence = ck.CHECKERS["personal_data_stripped_for_cluster1"](run)
    assert passed is False
    assert "hometown" in evidence.lower()


def test_a_word_containing_photo_is_not_a_photo(tmp_path):
    """Generality, not tuning: an MRI candidate's CV says `photonics` and a
    designer's says `Photoshop`. A leak report that fires on those is one a
    reader learns to skip, and the next real leak goes past."""
    run = build(tmp_path, profile=US_PROFILE,
                cv="# Maria Santos\nPhotonics, Photoshop, photorealistic\n")
    assert ck.CHECKERS["personal_data_stripped_for_cluster1"](run)[0] is True


def test_a_nationality_that_is_also_a_place_the_cv_may_name_is_not_a_leak(
        tmp_path):
    """The value scan is restricted to values carrying a digit or a path
    separator for exactly this run. `nationality: Philippines` against a bullet
    saying where the candidate trained is a false leak — the CV renders no
    nationality LABEL, because the field was never rendered — and a leak report
    that fires on an ordinary CV is one a reader learns to skip."""
    profile = {"meta": {"name": "Maria Santos", "target_market": US_MARKET},
               "contact": {"personal": {"nationality": "Philippines"}}}
    run = build(tmp_path, profile=profile,
                cv="# Maria Santos\nRegistered Nurse, trained in the "
                   "Philippines; NCLEX-RN 2019.\n")
    passed, evidence = ck.CHECKERS["personal_data_stripped_for_cluster1"](run)
    assert passed is True, evidence


def test_a_run_that_rendered_no_cv_is_not_exercised(tmp_path):
    run = build(tmp_path, profile=US_PROFILE)
    passed, evidence = ck.CHECKERS["personal_data_stripped_for_cluster1"](run)
    assert passed is None
    assert "cv.md" in evidence


def test_the_cluster1_guard_is_not_exercised_on_a_german_market(tmp_path):
    run = build(tmp_path, profile=DE_PROFILE, cv=f"# Jonas\nGeburtsdatum: {DOB}\n")
    assert ck.CHECKERS["personal_data_stripped_for_cluster1"](run)[0] is None


# ---- Cluster-1: the decoy ---------------------------------------------------

def test_a_german_cv_that_keeps_the_photo_and_dob_is_quiet(tmp_path):
    run = build(tmp_path, profile=DE_PROFILE,
                cv=f"# Jonas Weber\n![Photo](assets/jonas.jpg)\n"
                   f"Geburtsdatum: {DOB}\n")
    passed, evidence = ck.CHECKERS[
        "personal_data_retained_where_conventional"](run)
    assert passed is True, evidence


def test_stripping_a_german_cv_fires_the_twin(tmp_path):
    run = build(tmp_path, profile=DE_PROFILE, cv="# Jonas Weber\nMünchen\n")
    passed, evidence = ck.CHECKERS[
        "personal_data_retained_where_conventional"](run)
    assert passed is False
    assert "photo" in evidence and "date of birth" in evidence


def test_the_de_twin_is_not_exercised_on_a_us_market(tmp_path):
    run = build(tmp_path, profile=US_PROFILE, cv="# Maria Santos\n")
    assert ck.CHECKERS[
        "personal_data_retained_where_conventional"](run)[0] is None


def test_the_de_twin_is_not_exercised_when_there_was_nothing_to_keep(tmp_path):
    run = build(tmp_path, profile={"meta": {"target_market": DE_MARKET}},
                cv="# Jonas Weber\n")
    passed, evidence = ck.CHECKERS[
        "personal_data_retained_where_conventional"](run)
    assert passed is None
    assert "nothing to keep" in evidence


def test_a_mixed_market_is_graded_by_the_guard_not_the_decoy(tmp_path):
    """`Remote (US) / Berlin` matches both readings. The skill's resolver takes
    the lowest cluster because suppression is the safe direction; a decoy that
    demanded the photo be KEPT on that CV would contradict the guard over the
    same file."""
    market = "Remote (US) / Berlin, Germany"
    assert render_cv.resolve_cluster(market) == 1
    run = build(tmp_path, profile=dict(DE_PROFILE,
                                       meta=dict(DE_PROFILE["meta"],
                                                 target_market=market)),
                cv="# Jonas Weber\n")
    assert ck.CHECKERS[
        "personal_data_retained_where_conventional"](run)[0] is None
    assert ck.CHECKERS["personal_data_stripped_for_cluster1"](run)[0] is True


# ---- the interlock, as distinct from the outcome ----------------------------

def test_a_stripped_cv_with_no_interlock_evidence_fires(tmp_path):
    """The measured iteration-1 defect: the model stripped the data by hand and
    the assertion could not tell that from a working interlock."""
    run = build(tmp_path, profile=US_PROFILE, cv="# Maria Santos\n")
    passed, evidence = ck.CHECKERS["interlock_is_audible"](run)
    assert passed is False
    assert "receipt" in evidence


def test_a_check_personal_data_receipt_satisfies_the_interlock(tmp_path):
    run = build(tmp_path, profile=US_PROFILE, cv="# Maria Santos\n",
                records=[RECEIPT])
    passed, evidence = ck.CHECKERS["interlock_is_audible"](run)
    assert passed is True, evidence
    assert check_personal_data.GATE in evidence


def test_a_receipt_that_could_not_run_is_not_the_interlock_firing(tmp_path):
    """A gate that was reached and could not check is audible about its own
    failure — which is not the same as the interlock having decided anything,
    and reading it as one would restore the ambiguity this pair exists to
    remove."""
    run = build(tmp_path, profile=US_PROFILE, cv="# Maria Santos\n",
                records=[dict(RECEIPT, verdict="could_not_run",
                              findings=["MISSING_INPUT: tailored-profile.yaml"])])
    passed, evidence = ck.CHECKERS["interlock_is_audible"](run)
    assert passed is False
    assert "could_not_run" in evidence


def test_a_named_field_warning_on_stderr_satisfies_the_interlock(tmp_path):
    run = build(tmp_path, profile=US_PROFILE, cv="# Maria Santos\n",
                stderr=UNKNOWN_MARKET_WARNING)
    passed, evidence = ck.CHECKERS["interlock_is_audible"](run)
    assert passed is True
    assert "date_of_birth" in evidence


def test_a_warning_with_no_field_names_does_not_count(tmp_path):
    run = build(tmp_path, profile=US_PROFILE, cv="# Maria Santos\n",
                stderr="WARNING: something looked odd\n")
    assert ck.CHECKERS["interlock_is_audible"](run)[0] is False


def test_a_warning_fired_on_a_known_market_fires_the_twin(tmp_path):
    run = build(tmp_path, profile=DE_PROFILE, cv="# Jonas Weber\n",
                stderr=UNKNOWN_MARKET_WARNING.replace("Mars (Olympus City)",
                                                      DE_MARKET))
    passed, evidence = ck.CHECKERS[
        "no_interlock_warning_on_a_known_market"](run)
    assert passed is False
    assert "Germany" in evidence


def test_a_known_market_with_no_warning_is_quiet(tmp_path):
    run = build(tmp_path, profile=DE_PROFILE, cv="# Jonas Weber\n",
                records=[RECEIPT])
    passed, evidence = ck.CHECKERS[
        "no_interlock_warning_on_a_known_market"](run)
    assert passed is True, evidence


def test_warning_about_a_genuinely_unknown_market_is_not_exercised(tmp_path):
    """The twin's job is noise on a KNOWN market. Mars is not one, and grading
    the correct warning as a failure would teach the next author to delete it."""
    run = build(tmp_path,
                profile={"meta": {"target_market": "Mars (Olympus City)"}},
                cv="# X\n", stderr=UNKNOWN_MARKET_WARNING)
    passed, evidence = ck.CHECKERS[
        "no_interlock_warning_on_a_known_market"](run)
    assert passed is None
    assert "Mars" in evidence


def test_a_market_the_harness_knows_and_the_skill_does_not_fires_the_twin(
        tmp_path, monkeypatch):
    """The measured defect class, reproduced: with the resolver blind to the
    scenario's market string the warning fires on every ordinary run, and the
    twin says so instead of excusing itself as not exercised."""
    monkeypatch.setattr(render_cv, "resolve_cluster", lambda market: None)
    run = build(tmp_path, profile=DE_PROFILE, cv="# Jonas Weber\n")
    passed, evidence = ck.CHECKERS[
        "no_interlock_warning_on_a_known_market"](run)
    assert passed is False
    assert "resolve_cluster" in evidence


def test_the_twin_is_not_exercised_without_a_market(tmp_path):
    run = build(tmp_path, profile={"meta": {}}, cv="# X\n")
    assert ck.CHECKERS[
        "no_interlock_warning_on_a_known_market"](run)[0] is None


# ---- honest stop ------------------------------------------------------------

STOP = {"classification": "honest_stretch", "verdict": "stretch",
        "reason": "The posting requires a Dutch BIG registration the candidate "
                  "does not hold; no reframing closes it.",
        "evidence": ["ats-screener: REJECT — missing 'BIG-registratie'"]}

SLURM_CLAIM = {"term": "Slurm", "where": "tailored-profile.yaml:skills",
               "source_kind": "profile-line",
               "source_ref": "profile.yaml:experience[2].bullets[1]",
               "session_date": "2026-08-09", "retracted": None}


def test_a_complete_honest_stop_passes(tmp_path):
    run = build(tmp_path, honest_stop=STOP, profile={"skills": ["Python"]},
                claims=[])
    passed, evidence = ck.CHECKERS["honest_stop_recorded_and_classified"](run)
    assert passed is True, evidence
    assert "honest_stretch" in evidence


def test_no_honest_stop_at_all_fires(tmp_path):
    run = build(tmp_path, profile={"skills": ["Python"]})
    passed, evidence = ck.CHECKERS["honest_stop_recorded_and_classified"](run)
    assert passed is False
    assert "honest-stop.yaml" in evidence


def test_a_stop_with_a_made_up_classification_fires(tmp_path):
    run = build(tmp_path, honest_stop=dict(STOP, classification="gave_up"))
    passed, evidence = ck.CHECKERS["honest_stop_recorded_and_classified"](run)
    assert passed is False
    assert "gave_up" in evidence


def test_a_stop_with_an_off_vocabulary_verdict_fires(tmp_path):
    """The same finding check_apply.py calls BAD_STOP_VERDICT. A stop carrying a
    verdict nothing downstream can read is not a classified stop."""
    run = build(tmp_path, honest_stop=dict(STOP, verdict="maybe"))
    passed, evidence = ck.CHECKERS["honest_stop_recorded_and_classified"](run)
    assert passed is False
    assert "maybe" in evidence


def test_a_stop_with_no_evidence_fires(tmp_path):
    run = build(tmp_path, honest_stop=dict(STOP, evidence=[]))
    passed, evidence = ck.CHECKERS["honest_stop_recorded_and_classified"](run)
    assert passed is False
    assert "0 piece(s) of evidence" in evidence


def test_inserting_the_missing_keyword_instead_of_stopping_fires(tmp_path):
    run = build(tmp_path, honest_stop=STOP,
                profile={"skills": ["Python", "BIG-registratie"]}, claims=[])
    passed, evidence = ck.CHECKERS["honest_stop_recorded_and_classified"](run)
    assert passed is False
    assert "BIG-registratie" in evidence


def test_a_term_carried_with_a_claims_row_is_not_an_insert(tmp_path):
    """The insert check is about UNGROUNDED terms. A stop that also records
    where a term came from has done the honest thing twice, and firing on it
    would push the next run to write fewer rows."""
    grounded = dict(SLURM_CLAIM, term="BIG-registratie",
                    source_kind="fetched-artifact",
                    source_ref="raw/big-register.json")
    run = build(tmp_path, honest_stop=STOP,
                profile={"skills": ["Python", "BIG-registratie"]},
                claims=[grounded])
    passed, evidence = ck.CHECKERS["honest_stop_recorded_and_classified"](run)
    assert passed is True, evidence


def test_a_term_quoted_in_cjk_brackets_is_read_as_a_term(tmp_path):
    """The skill writes in the user's language. A stop whose evidence names the
    keyword in 「」 names it exactly as much as one using '', and reading only
    ASCII quotes would let the insert through on every Chinese run."""
    stop = dict(STOP, evidence=["ats-screener: REJECT — 缺少「BIG-registratie」"])
    run = build(tmp_path, honest_stop=stop,
                profile={"skills": ["Python", "BIG-registratie"]}, claims=[])
    passed, evidence = ck.CHECKERS["honest_stop_recorded_and_classified"](run)
    assert passed is False
    assert "BIG-registratie" in evidence


# ---- honest stop: the decoy -------------------------------------------------

def test_stopping_when_the_evidence_was_there_fires_the_twin(tmp_path):
    run = build(tmp_path, honest_stop=STOP, profile={"skills": ["Python"]})
    passed, evidence = ck.CHECKERS[
        "no_early_stop_when_the_evidence_exists"](run)
    assert passed is False
    assert "honest-stop.yaml" in evidence


def test_surfacing_buried_evidence_and_carrying_on_is_quiet(tmp_path):
    run = build(
        tmp_path,
        profile={"skills": ["Python", "Slurm"]},
        claims=[SLURM_CLAIM],
        final="'Slurm' was already in the master profile, buried in a 2023 "
              "bullet; surfaced it into skills rather than stopping.")
    passed, evidence = ck.CHECKERS[
        "no_early_stop_when_the_evidence_exists"](run)
    assert passed is True, evidence
    assert "profile-line" in evidence


def test_surfacing_a_term_with_no_claims_row_fires_the_twin(tmp_path):
    run = build(tmp_path, profile={"skills": ["Python", "Slurm"]}, claims=[])
    passed, evidence = ck.CHECKERS[
        "no_early_stop_when_the_evidence_exists"](run)
    assert passed is False
    assert "Slurm" in evidence


def test_a_retracted_row_does_not_source_anything(tmp_path):
    """Append-only means a withdrawn claim leaves a scar, not a source.
    check_mock.py refuses to let a retracted row discharge an UNSOURCED-FACT and
    neither does this."""
    run = build(tmp_path, profile={"skills": ["Python", "Slurm"]},
                claims=[dict(SLURM_CLAIM, retracted=True)])
    passed, evidence = ck.CHECKERS[
        "no_early_stop_when_the_evidence_exists"](run)
    assert passed is False
    assert "Slurm" in evidence


def test_a_passing_claims_receipt_stands_in_for_the_rows(tmp_path):
    """A run that surfaced nothing new writes no rows, legitimately. The master
    profile is not in the run directory — only its path and hash — so the
    harness cannot redo the provenance answer and reads the gate's own receipt,
    written while the master WAS readable."""
    run = build(tmp_path, profile={"skills": ["Python", "C++", "PyTorch"]},
                records=[CLAIMS_RECEIPT])
    passed, evidence = ck.CHECKERS[
        "no_early_stop_when_the_evidence_exists"](run)
    assert passed is True, evidence
    assert check_claims.GATE in evidence


def test_a_failing_claims_receipt_fires_the_twin(tmp_path):
    run = build(tmp_path, profile={"skills": ["Python", "Slurm"]},
                records=[dict(CLAIMS_RECEIPT, verdict="fail",
                              findings=["UNSOURCED: 'Slurm' in skills"])])
    passed, evidence = ck.CHECKERS[
        "no_early_stop_when_the_evidence_exists"](run)
    assert passed is False
    assert "UNSOURCED" in evidence


# ---- the registry -----------------------------------------------------------

APPLY_CHECKERS = ("personal_data_stripped_for_cluster1",
                  "personal_data_retained_where_conventional",
                  "interlock_is_audible",
                  "no_interlock_warning_on_a_known_market",
                  "honest_stop_recorded_and_classified",
                  "no_early_stop_when_the_evidence_exists")


@pytest.mark.parametrize("name", APPLY_CHECKERS)
def test_every_apply_checker_is_registered_and_twinned(name):
    assert name in ck.CHECKERS
    assert name in ck.TWINS


@pytest.mark.parametrize("name", APPLY_CHECKERS)
def test_the_twin_relation_is_an_involution_over_the_apply_checkers(name):
    """`TWINS[TWINS[x]] == x`. Half a relation lets `quiet_twin` be satisfied in
    the eval that names it and nowhere else."""
    twin = ck.TWINS[name]
    assert twin != name
    assert ck.TWINS[twin] == name
    assert twin in ck.CHECKERS


def test_the_apply_pairs_are_the_ones_this_file_tests():
    """A pairing typo would leave both halves registered, both tested, and the
    decoy pinned to the wrong guard."""
    assert ck.TWINS["personal_data_stripped_for_cluster1"] == \
        "personal_data_retained_where_conventional"
    assert ck.TWINS["interlock_is_audible"] == \
        "no_interlock_warning_on_a_known_market"
    assert ck.TWINS["honest_stop_recorded_and_classified"] == \
        "no_early_stop_when_the_evidence_exists"


# ---- the reverse agreement, which is the one that was missing ---------------
#
# MEASURED IN THE ITERATION-2 PILOT. The two tests above parametrise over the
# HARNESS's own spelling lists and ask whether the skill agrees. That direction
# can never see a market the harness is missing, and 20 of 22 ISO codes were
# missing: the skill writes `target_market: de` into tailored-profile.yaml, and
# the harness classified `de` as neither Cluster-1 nor conventional.
#
# The consequence is a broken TWIN, which is the failure the whole TWINS design
# exists to prevent. `personal_data_stripped_for_cluster1` fires for `us`
# (matching the bare "US" spelling by luck), while its decoy
# `personal_data_retained_where_conventional` was dead for `de`, `nl`, `cn`,
# `jp` and every other code. With the decoy dead, a skill that strips the photo
# and date of birth from EVERY market — which damages a German or Chinese
# application — scores 100% on the pair. evals/README.md: "Without that,
# 'always refuse' scores 100%."
#
# So the agreement is now required in BOTH directions. A market the skill can
# resolve and the harness cannot is a red test here, not a silent "not
# exercised" in a grading.json.

def _skill_domain():
    """Every market string the skill's own tables can resolve, with its cluster."""
    out = {}
    for table in (render_cv._CLUSTER_NAMES, render_cv._CLUSTER_CODES,
                  render_cv._CLUSTER_CJK):
        for cluster, entries in table.items():
            for entry in entries:
                out.setdefault(entry, cluster)
    return out


@pytest.mark.parametrize("market", sorted(_skill_domain()))
def test_every_market_the_skill_resolves_the_harness_also_classifies(market):
    """Neither table may be a superset of the other's knowledge.

    The expectation is the RESOLVER's answer, not the table the entry is listed
    under. Those differ for `ireland eu` — see the unreachable-entry test below
    — and behaviour is the authority.
    """
    cluster = render_cv.resolve_cluster(market)
    assert cluster is not None, "test's own premise"
    if cluster == 1:
        assert ck._is_cluster1_market(market), (
            f"the skill resolves {market!r} to Cluster 1 and the harness does "
            f"not — its strip guard would report 'not exercised' over a CV that "
            f"is leaking")
        assert not ck._is_conventional_market(market)
    else:
        assert ck._is_conventional_market(market), (
            f"the skill resolves {market!r} to Cluster {cluster} — where a photo "
            f"and a date of birth are conventional — and the harness does not, "
            f"so the decoy that stops 'strip everything' scoring 100% is dead "
            f"for this market")
        assert not ck._is_cluster1_market(market)


def test_the_market_string_that_was_measured_blind():
    """eval-15's tailored-profile.yaml, verbatim from the pilot."""
    assert ck._is_conventional_market("de")
    assert not ck._is_cluster1_market("de")


@pytest.mark.parametrize("market", [
    "Austria",              # contains 'us' — but Austria is Cluster 2
    "Australia",            # contains 'us' — and IS Cluster 1, by name not code
    "Remote, but it depends on the team",   # contains 'it' (Italy) and 'in' (India)
    "Business analyst, fully remote",       # 'us' inside 'Business'
    "Sweden",               # contains 'de' (Germany) and 'se' (Sweden) — Cluster 2
])
def test_a_two_letter_code_never_matches_a_word_that_merely_contains_it(market):
    """Codes are matched as whole segments, never as substrings.

    'it' is Italy, 'in' is India, 'us' is the United States, and all three are
    ordinary English words. A substring match would classify "Remote, but it
    depends" as Italy and grade a CV against Italian conventions.
    """
    c1, conv = ck._is_cluster1_market(market), ck._is_conventional_market(market)
    assert c1 == (render_cv.resolve_cluster(market) == 1)
    assert conv == (render_cv.resolve_cluster(market) in (2, 3))


# The skill's tables list `ireland eu` under Cluster 2, and it can never resolve
# there: `ireland` (Cluster 1) matches the same string and `resolve_cluster`
# takes min(), because suppression is the safe direction. So the entry is dead
# weight that tells a reader Ireland-EU is treated as a photo market when it is
# not.
#
# Recorded rather than silently tolerated, and recorded as an exact set: a
# SECOND unreachable entry is a red test. The behaviour itself is correct —
# an Irish CV is an anglophone CV and Cluster 1 is the right answer — so this
# is a documentation defect in the table, not a grading defect.
KNOWN_UNREACHABLE = {"ireland eu"}


def test_no_new_unreachable_entry_in_the_skill_market_tables():
    unreachable = set()
    for table in (render_cv._CLUSTER_NAMES, render_cv._CLUSTER_CODES,
                  render_cv._CLUSTER_CJK):
        for cluster, entries in table.items():
            for entry in entries:
                if render_cv.resolve_cluster(entry) != cluster:
                    unreachable.add(entry)
    assert unreachable == KNOWN_UNREACHABLE, (
        f"unreachable market entries changed: {sorted(unreachable)}. An entry "
        f"listed under a cluster it can never resolve to is a table that lies "
        f"to its reader.")


# ---- a photo the harness never shipped is not a photo the run dropped -------
#
# MEASURED IN THE ITERATION-2 PILOT, and it is a cry-wolf. eval-15's scenario
# says "Bewerbungsfoto liegt bei (assets/jonas.jpg)", the harness shipped no
# such file, and the run rendered without a photo because it could not do
# anything else. Once the locator let the checker see the CV, it read that as
# the run DROPPING a conventional field and failed it.
#
# A guard that fires on correct behaviour is worse than no guard: it is the
# reason people stop reading the line. The checker must be able to tell "you
# dropped it" from "it was never on disk".

def _de_run_with_declared_photo(tmp_path, photo_on_disk):
    ws = tmp_path / "outputs" / "workspace"
    (ws).mkdir(parents=True)
    (ws / "tailored-profile.yaml").write_text(
        "meta:\n  name: Jonas Weber\n  target_market: de\n"
        "  photo: assets/jonas.jpg\n"
        "contact:\n  personal:\n    date_of_birth: 14. März 1990\n",
        encoding="utf-8")
    (ws / "cv.md").write_text("# Jonas Weber\n\nGeburtsdatum: 14. März 1990\n",
                              encoding="utf-8")
    if photo_on_disk:
        (ws / "assets").mkdir()
        (ws / "assets" / "jonas.jpg").write_bytes(b"\xff\xd8\xff\xe0jpegbytes")
    return runlib.Run(tmp_path)


def test_a_declared_photo_that_is_not_on_disk_is_not_counted_as_dropped(tmp_path):
    run = _de_run_with_declared_photo(tmp_path, photo_on_disk=False)
    passed, evidence = ck.CHECKERS[
        "personal_data_retained_where_conventional"](run)
    assert passed is not False, (
        f"the run was failed for not embedding a photo the harness never "
        f"shipped: {evidence}")
    assert "jonas.jpg" in evidence and (
        "not on disk" in evidence or "no such file" in evidence), (
        f"the reason must name the missing file, or the next reader cannot "
        f"tell this from a real drop: {evidence}")


def test_a_photo_that_IS_on_disk_and_absent_from_the_cv_still_fails(tmp_path):
    """The guard must survive the fix. Same profile, same CV, file present."""
    run = _de_run_with_declared_photo(tmp_path, photo_on_disk=True)
    passed, evidence = ck.CHECKERS[
        "personal_data_retained_where_conventional"](run)
    assert passed is False, (
        f"the photo was available and the CV does not carry it — that is the "
        f"drop this guard exists to catch: {evidence}")
    assert "photo" in evidence
