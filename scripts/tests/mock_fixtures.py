"""A complete, PASSING interview workspace, built on disk.

Every test starts from this quiet case and breaks exactly one thing. A check that fires
on ordinary output therefore fails a test on its first run, which is the only way to
keep the gate from becoming the line everyone learns to skip.

The workspace includes a recorded mode entry against a fake skill root, because a real
session's step 0 is `enter_mode.py` and check_mock requires that record. Building it
here rather than in each test keeps the quiet case genuinely quiet.
"""
import contextlib
import io
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import enter_mode

TRANSCRIPT = """# Mock transcript — round 2
Round type: technical
Market: nl
Family: ml-engineering
Persona: Sanne de Vries, MR reconstruction team lead — direct, asks for numbers

## Q1 — Walk me through the reconstruction pipeline you owned.
**Interviewer:** Walk me through the reconstruction pipeline you owned.
**Candidate:** At the university hospital I owned the offline recon pipeline for a 3T scanner study: raw k-space came off the scanner, I ran coil compression, then a variational-network model, then wrote DICOMs back to the PACS.

## Q2 — What did you change about it, and what happened as a result?
**Interviewer:** What did you change about it, and what happened as a result?
**Candidate:** I replaced the per-slice loop with a batched GPU implementation. It went really well after that.

## Q3 — What did you learn from that, and what would you do differently?
**Interviewer:** What did you learn from that, and what would you do differently?
**Candidate:** I learned to profile before optimising. I would run the profiler first next time and write down the baseline before touching anything.
"""

ASSESSMENT = """# Mock assessment — round 2

Two passes ran on this transcript with deliberately different inputs. Neither saw the
other's output. The blocks below are the assessors' own words, unedited.

MOCK-ASSESSMENT-V1
ROUND: 2
ROUND-TYPE: technical
MARKET: nl
FAMILY: ml-engineering
FINDING: tag=VAGUE-OUTCOME | ref=Q2 | quote=It went really well after that.
BAND: dimension=instance | value=instanced | ref=Q1 | quote=At the university hospital I owned the offline recon pipeline for a 3T scanner study
BAND: dimension=outcome | value=asserted | ref=Q2 | quote=It went really well after that.
BAND: dimension=probe | value=held_under_probe | ref=Q3 | quote=I would run the profiler first next time
BAND: dimension=completeness | value=instanced | ref=Q3 | quote=I learned to profile before optimising.
COVERAGE: status=evidenced | must_have=MRI reconstruction pipelines in a clinical setting
COVERAGE: status=not_asked | must_have=Regulatory documentation (MDR)
SHAPE: status=rehearsed | round_name=technisch gesprek met de vakinhoudelijke manager
SHAPE: status=not_attempted | round_name=gesprek met het team
END-MOCK-ASSESSMENT-V1

MOCK-PROVENANCE-V1
ROUND: 2
FINDINGS: none
END-MOCK-PROVENANCE-V1
"""

QUESTION_LOG = """round: 2
posting_country: NL
questions:
  - id: Q1
    text: Walk me through the reconstruction pipeline you owned.
    source: generated
    asked: true
  - id: Q2
    text: What did you change about it, and what happened as a result?
    source: generated
    asked: true
  - id: Q3
    text: What did you learn from that, and what would you do differently?
    source: generated
    asked: true
rejected:
  - id: R1
    text: "ASML 宣讲会 + 笔试 timeline"
    source: scraped
    source_site: nowcoder
    source_id: "057523b2ca9d"
    source_time: "2026-08-06T11:06:49"
    entity_country: CN
    reason: wrong_country
"""

# The two must-haves the ASSESSMENT block above carries a COVERAGE row for, one each.
# check_mock reads this list rather than counting rows: a bare count pressures the
# assessor to invent a must-have to satisfy it, and naming the uncovered one does not.
POSTING = """role_title: MR Reconstruction Engineer
company: ASML
must_haves:
  - MRI reconstruction pipelines in a clinical setting
  - Regulatory documentation (MDR)
nice_to_haves:
  - PyTorch
"""

OPEN_LOOPS = """# Open loops — round 2

## (i) A fact you have but did not recall
- The before/after timings for the batched GPU rewrite.

## (ii) A genuine gap
- No MDR regulatory documentation experience.

## (iii) A tailoring error
- None this round.
"""

CHEATSHEET = """# Cheatsheet — ASML, MR Reconstruction Engineer

- Story: batched GPU reconstruction on the 3T study (round 2 Q2).
- Honest gap: no MDR regulatory documentation; research-side validation instead.
- Still open: the measured before/after timings.
- Loop: technisch gesprek met de vakinhoudelijke manager, then gesprek met het team.
"""

ASSESSMENT_YAML = """requirements:
  - id: R1
    match: strong
  - id: R2
    match: no_evidence
"""

ANSWER_BANK = """# Answer bank

## Batched GPU reconstruction on the 3T study
- serves: "tell me about an optimisation you made"; round 2 Q2
- source: profile.yaml:experience[0].bullets[2] — "rewrote the recon loop for GPU batching"
- session: 2026-08-09 — applications/asml-mr-recon-engineer-2026-08-09/mock/transcript-2.md#Q2
- S: offline recon for a 3T scanner study at the university hospital
- T: the per-slice loop was the bottleneck in the nightly batch
- A: replaced the per-slice loop with a batched GPU implementation
- R: open loop — the measured change was not stated in the room; see open-loops.md
- R2 (reflectie): profile before optimising, and write the baseline down first
"""

ANSWER_GUIDE = """# Answer guide — round 2

## Q2 — What did you change about it, and what happened as a result?
- row: R1
- basis: evidenced
- source: profile.yaml:experience[0].bullets[2] — "rewrote the recon loop for GPU batching"
- listening for: your own action separated from the team's, and a measured before/after
- S: offline recon for a 3T scanner study
- T: the per-slice loop was the nightly bottleneck
- A: YOUR words — what you personally changed
- R: the measured change; if you no longer hold the number, say so rather than reach
- R2 (reflectie): what you would measure first next time
- fails if: "we" throughout (NO-ACTOR), or an outcome with no object (VAGUE-OUTCOME)

## Q4 — How do you work inside a regulated quality management system?
- row: R2
- basis: honest_gap
- source: fit-assessment.yaml:R2 match=no_evidence — nothing in the profile speaks to this
- honest framing: name the nearest real thing you have done, then how you would come at
  the regulated version. Do not narrate a QMS you have not worked in.
"""

BRIEF = """# Interview-readiness brief

## 1. Be ready to explain (your tailored claims)
- CV says: "Rewrote the offline reconstruction loop for GPU batching."
  Source: profile.yaml:experience[0].bullets[2].
  Be ready to: name the before and after timings and how they were measured.

## 2. Honest gaps — your answer if asked
- No MDR regulatory documentation experience. Honest framing: research-side validation
  work, learning the regulatory side deliberately.
"""

CLAIMS = """- term: GPU batching
  where: tailored-profile.yaml:experience[0].bullets[2]
  source_kind: profile-line
  source_ref: profile.yaml:experience[0].bullets[2]
  session_date: "2026-08-09"
  retracted: null
"""

MODE_FILE = """# Mode: interview

A stand-in for the real modes/interview.md, which Task 6 writes. check_mock only ever
hashes this file; it never reads it, so a stub is honest here and keeps Task 3's tests
independent of Task 6's prose.
"""


def skill_root(workspace):
    """The fake skill root build() created beside the profile tree.

    Tests need a skill root that is NOT the repo, because Task 3 runs before Task 6 and
    the real modes/interview.md does not exist yet.
    """
    return pathlib.Path(workspace).parents[3] / "skill"


def build(tmp_path, *, round_no=2, transcript=None, assessment=None, question_log=None,
          answer_bank=None, brief=None, claims=None, posting=None, open_loops=None,
          cheatsheet=None, answer_guide=None, assessment_yaml=None, enter=True):
    """Write the quiet-case workspace under tmp_path and return the workspace path.

    `enter=False` skips the mode-entry record, for the tests that pin NO_MODE_ENTRY.
    """
    profile = pathlib.Path(tmp_path) / "job-profiles" / "demo"
    workspace = profile / "applications" / "asml-mr-recon-engineer-2026-08-09"
    (workspace / "mock").mkdir(parents=True, exist_ok=True)
    root = pathlib.Path(tmp_path) / "skill"
    (root / "modes").mkdir(parents=True, exist_ok=True)

    def w(path, text):
        path.write_text(text, encoding="utf-8")

    w(root / "modes" / "interview.md", MODE_FILE)
    w(workspace / "mock" / f"transcript-{round_no}.md",
      TRANSCRIPT if transcript is None else transcript)
    w(workspace / "mock" / f"assessment-{round_no}.md",
      ASSESSMENT if assessment is None else assessment)
    w(workspace / "mock" / "question-log.yaml",
      QUESTION_LOG if question_log is None else question_log)
    w(workspace / "interview-brief.md", BRIEF if brief is None else brief)
    w(workspace / "claims.yaml", CLAIMS if claims is None else claims)
    w(workspace / "posting.yaml", POSTING if posting is None else posting)
    w(workspace / "mock" / "open-loops.md",
      OPEN_LOOPS if open_loops is None else open_loops)
    w(workspace / "mock" / "cheatsheet.md",
      CHEATSHEET if cheatsheet is None else cheatsheet)
    w(workspace / "mock" / "answer-guide.md",
      ANSWER_GUIDE if answer_guide is None else answer_guide)
    # The assessment the guide is checked against. Rows deliberately disagree: R1 is
    # evidenced and R2 is not, so a fixture that swapped the two bases would fail.
    w(workspace / "fit-assessment.yaml",
      ASSESSMENT_YAML if assessment_yaml is None else assessment_yaml)
    w(profile / "answer-bank.md", ANSWER_BANK if answer_bank is None else answer_bank)
    if enter:
        # enter_mode.main prints its "now read the file" reminder on stdout. Swallow it
        # here: the tests that assert the gate printed nothing are asserting about the
        # GATE, and a fixture leaking into capsys would make that assertion untestable.
        # Call the real thing rather than hand-writing the record — the record's shape
        # is enter_mode's to define, and a second copy of it here would drift.
        with contextlib.redirect_stdout(io.StringIO()):
            enter_mode.main(["--workspace", str(workspace), "--mode", "interview",
                             "--skill-root", str(root)])
    return workspace


def no_vocab(text, source):
    """Stub for scripts/lint_no_prediction.py (Plan 2): finds nothing, quietly."""
    return []
