export const meta = {
  name: 'job-hunt-plan-fixes',
  description: 'Apply audit and cross-check fixes to the four plans, author the eval plan, then re-verify',
  phases: [
    { title: 'Fix', detail: 'one agent per plan applies its audit + assigned cross-check edits' },
    { title: 'Reverify', detail: 're-run the extracted code and re-audit each fixed plan' },
    { title: 'Final', detail: 'cross-plan consistency re-check' },
  ],
}

const REPO = '/Users/donghanglyu/code_project/job-hunt'
const PLANDIR = REPO + '/docs/superpowers/plans'
const SPEC = REPO + '/docs/superpowers/specs/2026-08-09-job-hunt-skill-design.md'
const RES = REPO + '/docs/superpowers/research/2026-08-09'
const SCRATCH = '/private/tmp/claude-501/-Users-donghanglyu/d1ca171b-6798-42dc-9582-87e4635be401/scratchpad'

const RECONCILED = `
# RECONCILED CONTRACT — authoritative. These resolve collisions the cross-check found between the
# four plans. Where this contradicts the plan you are editing, THIS WINS and you change the plan.

## R1. scripts/vocab.py — NEW shared module, created in Plan 1, imported by every later plan
No closed set may be spelled out twice. Plan 1 creates it; Plans 2, 3 and 4 import from it and MUST NOT
re-declare these constants locally.

    # scripts/vocab.py
    VERDICTS = ("strong_apply", "worth_applying", "stretch", "likely_screen_out", "blocked")
    REFUSAL = "insufficient_evidence"          # orthogonal refusal state, NOT a sixth verdict
    VERDICT_ZH = {
        "strong_apply": "强烈建议投", "worth_applying": "值得投", "stretch": "可以冲刺",
        "likely_screen_out": "大概率被筛掉", "blocked": "硬性阻断",
        "insufficient_evidence": "证据不足—不出结论",
    }
    MARKET_KEYS = ("cn", "nl", "de", "uk", "us")
    NO_MARKET = "other"                        # the sixth token, everywhere; NEVER "none"
    LEVELS = ("required", "preferred", "unclear")
    SCREENING = ("knockout", "weighted", "nice_to_have")
    MATCH = ("strong", "partial", "gap", "no_evidence")
    RECENCY = ("current", "recent", "dated", "undated")
    EFFORT = ("quick", "evening", "multi_day", "not_closable")
    BANDS = ("not_present", "asserted", "instanced", "held_under_probe")
    CONTRADICTED = "contradicted"
    DEFECT_TAGS = ("UNSOURCED-FACT", "OVER-CLAIM", "CONTRADICTED", "PROBE-COLLAPSE")

Plan 1 writes it with a test asserting every constant is a tuple/dict of the exact expected members.
Plan 4 renames its local MARKET_KEYS out of existence and imports vocab.MARKET_KEYS (its own
mock-specific extension, if still needed, becomes MOCK_MARKET_KEYS and is documented as a superset).

## R2. Exit-2 discipline — identical in all four plans
Every gate, on the "could not run" path: write EXACTLY ONE receipt with verdict "could_not_run"
(never "error"), print the reason to stderr, return 2. If the workspace directory itself does not
exist there is nothing to append to — in that single case print to stderr and return 2 with no
receipt, and say so in the script docstring. Every gate gets a test asserting the exit-2 receipt exists.
Plan 1 changes "error" -> "could_not_run". Plan 2 adds the missing receipts on all six gates.

## R3. Receipt verdict vocabulary — closed
"pass" | "fail" | "could_not_run" | "recorded"
"recorded" is for a script that reports rather than gates (check_evidence_refs, count_coverage,
consistency). Plan 2 must drop "reported" and "produced" and use "recorded" for both, consistently
— the same state must never produce two different verdicts.
check_apply.PASSING_VERDICTS = ("pass", "recorded").

## R4. paths.py is actually used
Every script that resolves a profile, workspace, search dir, answer bank or search-preferences path
imports scripts/paths.py and calls it. No script re-derives a path with .parents[n] or string joins.
Plan 4's _answer_bank_default becomes paths.answer_bank(...). Plan 1 audits its own scripts for this too.

## R5. enter_mode for ALL four modes — this is half of the layer-1.5 backstop
Plan 1 already produces scripts/enter_mode.py. Each of Plans 2, 3 and 4 MUST:
  (a) make "python3 scripts/enter_mode.py --workspace <ws> --mode <mode>" the FIRST step of its mode file;
  (b) mirror check_apply's NO_MODE_ENTRY and MODE_FILE_CHANGED findings into its own gate;
  (c) add a quiet test (entry present, hash matches -> no finding) and two firing tests.
enter_mode.py sets the mode for subsequent receipts. Plan 1 changes journal.receipt so "mode" is read
from the most recent mode_entry record in the journal, falling back to "unknown" — NOT from an
environment variable nothing sets, and NOT defaulting to "apply".

## R6. posting.yaml field list — ONE list, in both places, identical
role_title, company, seniority, location, must_haves, nice_to_haves, responsibilities, keywords,
company_values_tone, red_flags, salary_range, application_type
"company" is the exact public employer name — check_letter.py hard-fails without it.
"location" is a scalar string (the posting's own location text), NOT a mapping — Plan 2 changes.
"language" is NOT in the list — Plan 2 drops it (the CV language lives in meta.language on the profile).
Plan 1's SKILL.md table and Plan 2's modes/assess.md section 3 must be byte-identical on these twelve names.

## R7. claims.yaml required keys
("term", "where", "source_kind", "source_ref", "session_date", "retracted")
"retracted" is a PRESENCE check — the value may be null. Plan 1 adds it to CLAIM_KEYS.

## R8. The self-check and gate table are extended by every plan
Plan 1 writes SKILL.md's "## Self-check" section and gate table, plus tests asserting every
scripts/*.py (minus a skip set for library-only modules), every references/*.md, every agents/*.md
and every modes/*.md is named there. Those tests are CORRECT and stay. Therefore Plans 2, 3 and 4 EACH
need a final task that appends their own scripts, references, agents and mode file to both the
self-check and the gate table, and extends the skip set for library-only modules
(opencli_meta.py, mock_vocab.py, mock_blocks.py, vocab.py, journal.py, paths.py, rounds.py).
Without this the suite is red from Plan 2 onward.

## R9. "Not yet built" must self-retract — convert a coordination hope into a mechanism
Plan 1's SKILL.md says discover/assess/interview are not yet built. Plan 1 MUST also write a test that
normalises the SKILL.md text (strip backticks and collapse whitespace) and then, for each of discover,
assess and interview, asserts that if modes/<mode>.md exists the phrase "<mode> is not yet built" is
absent from the normalised text. The suite then goes red the moment a later plan lands a mode file
without retracting the sentence. Each of Plans 2/3/4 retracts its own sentence in its final task.

## R10. Ownership of the previously-unassigned items
  Plan 1: check_pages.py; check_word_limits.py; CI wiring (a Makefile target AND a
          .github/workflows/checks.yml running pytest + check_skill_lossless.py +
          check_conventions.py --all); apply-mode entry conditions restated against the five verdicts
          (stretch and likely_screen_out do NOT block entry; blocked prompts once then proceeds);
          delete README.md's duplicated 8-step list and point at SKILL.md; add cv-source.txt,
          coverage.json and master-fingerprint.json to the documented workspace layout.
  Plan 2: the spec section 12 flagged FIT SNAPSHOT rewrite, as its own small separate commit, plus its
          scripts/lossless-allowlist.json entry naming it.
  Plan 3: writes search-preferences.yaml (discover owns it per spec section 4.3), including its schema
          and the interview that populates it on first run.
  Plan 5: the eval rebuild (a separate new plan; do not add it to Plans 1-4).

## R11. markets.json is now IN THE REPO — no scratchpad dependency
${RES}/markets.json  (plus adapters.json, preserve.json, brief.md, interview.md, marketfit.md,
committee.md, cross.md, audit-1..4.md — all committed at ac404fb).
Plan 2 Task 6 Step 1 changes from "copy from /private/tmp" to "read from the repo path above".
No plan may reference /private/tmp or a session scratchpad for anything.

## R12. Shortlist rows may carry effort
JobListingEvidence's base fields are fixed, but the shortlist row is our own schema and already adds
verdict and provisional. It also carries "effort" (one of vocab.EFFORT) so that D3's within-band
ordering by effort-to-close is implementable. Plan 3 adds it to the row schema and to check_shortlist.

## R13. insufficient_evidence is never a shortlist row
A refusal state is not a listing. Plan 3 removes the "insufficient_evidence row" instruction from
modes/discover.md Step 7: a card that cannot support any level is dropped from the shortlist and
counted in the shortfall reason instead.

## R14. check_opencli_result.py is an explicitly named exception to the gate contract
It is a wrapper, not a gate: exit 0 = classified, exit 2 = could not classify, no exit 1, and it writes
an action:"adapter_call" record rather than a gate receipt. Plan 3 keeps this and states it as a named
exception in its Global Constraints. No other script may deviate.

## R15. Git rules, unchanged and non-negotiable
Stage NAMED PATHS only. Never "git add -A", never "git add .". NEVER "git push" in any step.
Never pass "-c user.name" / "-c user.email".
`

const HOWTOFIX = `
# HOW TO APPLY THE FIXES

Use the Edit tool for surgical changes. The plan files are thousands of lines and you MUST NOT
truncate, summarise or rewrite them wholesale — a lost task is a worse defect than the one you fixed.
Only use Write if you are replacing one complete task section and you have its full new text.

For every defect:
  1. Read the cited line(s) in the plan file to confirm the audit's claim before changing anything.
     An audit finding you cannot reproduce in the file is a finding you do NOT apply — say so instead.
  2. Apply the fix the audit proposes, unless the RECONCILED CONTRACT dictates otherwise.
  3. Where the fix changes a test's expected count, recount and write the true number.
  4. Where the fix changes code, check every other place in the plan that shows the same code.

When a defect says a test fails, actually verify it: extract the code block into a temp file under
${SCRATCH}/fixcheck/ and run it. Do not take the audit on faith and do not take your own fix on faith.

Do NOT create any file under the skill tree itself (no scripts/, no modes/, no references/). You are
editing a PLAN, not implementing it. The only files you write are the plan document and throwaway
verification files in the scratchpad path above.

Preserve the plan's structure: header, Global Constraints, File Structure, then tasks with
Files / Interfaces / checkbox steps. Every step stays one action of 2-5 minutes with real code.
`

const FIXES = [
  {
    n: 1,
    file: PLANDIR + '/2026-08-09-1-migration-and-p0-fixes.md',
    audit: RES + '/audit-1.md',
    assigned: `
YOUR CROSS-CHECK EDITS (in addition to every defect in your audit file):

- Cross #3  — exit-2 receipt verdict "error" -> "could_not_run" in check_personal_data.py,
              parse_verdicts.py, check_render_freshness.py, check_claims.py and their tests. (R2)
- Cross #4  — add "retracted" to check_claims.CLAIM_KEYS as a presence check. (R7)
- Cross #5  — CREATE scripts/vocab.py exactly as R1 specifies, as a new early task (before any
              script that needs a closed set), with its test. Then make check_apply.py import
              VERDICTS from it instead of declaring its own.
- Cross #6  — add to SKILL.md layer 1, all four currently missing: (a) the apply-verdict block
              template + its required disclaimer; (b) the skill-wide banned-output vocabulary + the
              published-employer-rubric exception; (c) the spec section 8 three-mechanism
              grounding-contract summary (the ASCII diagram plus the three numbered paragraphs);
              (d) NOT the platform-limit stop rule — that is Plan 3's, but add an explicit line to
              "Not in this plan" saying Plan 3 carries it into the same block.
- Cross #21 — add tasks for check_pages.py (PDF page count vs the market's target length) and
              check_word_limits.py (per-criterion supporting-statement word counts). (R10)
- Cross #22 — add a CI task: a Makefile target and .github/workflows/checks.yml running pytest,
              check_skill_lossless.py, and check_conventions.py --all. Spec section 12 requires the
              lossless check to run in CI and no plan wires it. (R10)
- Cross #25 — restate apply-mode entry conditions against the five verdicts in modes/apply.md:
              stretch and likely_screen_out do NOT block entry (a well-built application to a reach
              role is not a defect); blocked prompts exactly once then proceeds if the user says yes. (R10)
- Cross #28 — delete README.md's duplicated 8-step process list (it already omits Step 7.5) and point
              at SKILL.md; add cv-source.txt, coverage.json and master-fingerprint.json to the
              documented workspace layout. (R10)
- Section 1.6 — journal.receipt must read "mode" from the latest mode_entry record in the journal,
              falling back to "unknown". Delete the JOB_HUNT_MODE environment-variable default of
              "apply" — nothing sets it, so every later plan's receipts would be mislabelled. (R5)
- Section 1.7 / R4 — make your own scripts import scripts/paths.py wherever they resolve a path.
- R9        — add the self-retracting "not yet built" test exactly as R9 specifies. This is the
              mechanism that stops that sentence going stale once a later plan lands a mode file.
- R8        — leave your self-check tests as they are; they are correct. But add a line to "Not in
              this plan" stating that Plans 2/3/4 must each extend the self-check and gate table, and
              that the suite is red until they do.
`,
  },
  {
    n: 2,
    file: PLANDIR + '/2026-08-09-2-assess-mode.md',
    audit: RES + '/audit-2.md',
    assigned: `
!! READ THIS FIRST — THIS PLAN IS ALREADY PARTIALLY FIXED !!
An earlier fix run died mid-way (session limit) after editing this file. Commit 7738020 already
applied, correctly, in the Global Constraints / File Structure / Task 1 / Task 2 region ONLY:
  R1 (vocab.py referenced, local closed sets to be deleted), R2 (exit-2 receipts, "could_not_run"),
  R3 (receipt verdict set, "reported"/"produced" retired), R4 (paths.py), R11 (markets.json read
  from the repo, /private/tmp purged), Cross #13 (conftest create-if-absent), and NO_MARKET "other".
Do NOT re-apply those in that region — verify them and move on. They are NOT yet applied inside
Tasks 3 through 13, which is where most of the remaining work is.
**Line numbers in audit-2.md are now stale by roughly +73 lines. Locate every finding by its quoted
content, never by its line number.** Re-read the file to get current positions before editing.

YOUR CROSS-CHECK EDITS (in addition to every defect in your audit file):

- Cross #1  — posting.yaml field list: adopt R6 exactly. Add "company". Make "location" a scalar
              string, not a mapping. Drop "language". The twelve names must be byte-identical to
              Plan 1's SKILL.md table. Without "company", every apply run after an assess run fails
              check_letter.py with NO_COMPANY_IN_POSTING.
- Cross #2  — all six gates write exactly one receipt on the exit-2 path with verdict
              "could_not_run", and each gets a test asserting it. (R2)
- Cross #7  — YOU own the spec section 12 flagged FIT SNAPSHOT rewrite. The old disclaimer is about
              keyword coverage PERCENTAGES, which this skill no longer emits; carried verbatim it
              ships an incoherent paragraph. Add a task that performs it as its own small separate
              commit and records it by name in scripts/lossless-allowlist.json. (R10)
- Cross #8  — markets.json is now in the repo. Change Task 6 Step 1 from copying out of
              /private/tmp to reading ${RES}/markets.json. Purge every /private/tmp reference. (R11)
- Cross #9  — add the quote=-field exemption to lint_no_prediction.py for text inside a MOCK-*-V1
              block, with a test. Plan 4 needs it: an honest transcript where the candidate says
              "40%" out loud would otherwise fail the gate, and Plan 4's fixture currently dodges it
              by writing "40 percent", which its own author called a dodge, not a fix.
- Cross #10 — EXPIRED_REVIEW_BY becomes a WARN_-prefixed finding inside check_assessment (CI keeps it
              hard via check_conventions --all). Spec section 10 is explicit: expiry fails CI but at
              runtime renders a stale-review banner rather than refusing. Your test currently pins the
              wrong behaviour — rewrite it as two tests: expired table alone -> gate passes; expired
              table with no banner -> MISSING_STALE_BANNER.
- Cross #11 — add NO_STRATEGY_SECTION / NO_ACCEPTANCE_COLUMN findings firing when the verdict is
              likely_screen_out or blocked and the strategy, the 30/60/90 acceptance-criteria column,
              or the roadmap deliverable column is absent. Spec section 5.2 step 10 says those two
              columns are the whole value.
- Cross #12 — check_assessment declares journal.read_receipts under Consumes and never calls it.
              Either require the upstream receipts or drop the claim. Prefer requiring them.
- Cross #13 — conftest.py step becomes create-if-absent, matching Plan 3's wording.
- R1        — import every closed set from scripts/vocab.py. Delete FIVE_LEVELS, VERDICT_ZH,
              MARKET_KEYS and VERDICT_LABELS local declarations. Use vocab.NO_MARKET ("other"),
              never "none".
- R3        — receipt verdicts: replace "reported" and "produced" with "recorded", consistently.
              check_evidence_refs must not write "pass" on one clean path and "reported" on another.
- R5 / Cross #15 — enter_mode as step 0 of modes/assess.md, plus NO_MODE_ENTRY and MODE_FILE_CHANGED
              in check_assessment, with one quiet and two firing tests. This is the missing half of
              the layer-1.5 backstop and your own Task 12 already claims it exists.
- R8 / Cross #14 — new final task: append your scripts, references and modes/assess.md to SKILL.md's
              self-check AND gate table, and extend test_skill_structure.py's skip set. The suite is
              red from your plan onward without this.
- R9 / Cross #26 — retract SKILL.md's "assess is not yet built" sentence in that same final task.
`,
  },
  {
    n: 3,
    file: PLANDIR + '/2026-08-09-3-discover-mode.md',
    audit: RES + '/audit-3.md',
    assigned: `
YOUR CROSS-CHECK EDITS (in addition to every defect in your audit file):

- Cross #16 / R13 — remove the "insufficient_evidence row" instruction from modes/discover.md Step 7.
              A refusal state is not a shortlist row, and check_shortlist.VERDICTS rightly rejects it,
              so the mode file currently instructs an output its own gate refuses. A card that cannot
              support any level is DROPPED and counted in the shortfall reason.
- Cross #17 — carry the platform-limit stop rule into the SKILL.md discover-inserts block, all six
              clauses (stop / no retry / no parameter change and retry / no routing around it /
              emit the direction-level degradation / fill the disclosure table). Plan 1 explicitly
              hands it to you. Pin it with an assertion in the SKILL.md structure test.
- Cross #18 — give references/source-policy.md an evaluable SKILL.md trigger (one a model can judge
              WITHOUT having read the file) and a named backstop, or record it as a documented
              residual risk in the plan's handover notes. Prefer giving it a real trigger.
- Cross #24 / R10 — YOU write search-preferences.yaml: its schema, the first-run interview that
              populates it, and where it is read. Spec section 4.3 makes it part of the shared spine
              and no plan currently creates it, while modes/assess.md already branches on its contents.
- Cross #27 — enforce the card-based-provisional stamp in shortlist.md, not only provisional: true in
              shortlist.yaml. The spec says a row may not be rendered without the stamp, and only the
              YAML half is checked; the reader-facing half is the one that matters.
- R12       — add "effort" (one of vocab.EFFORT) to the shortlist row schema and to check_shortlist,
              so D3's within-band ordering by effort-to-close is implementable. Today it is specified
              and unimplementable.
- R1        — import VERDICTS and the rest from scripts/vocab.py; delete the local declaration.
- R14       — state check_opencli_result.py's deviation (exit 0/2 only, adapter_call record instead of
              a gate receipt) as a NAMED exception in your Global Constraints, so a future reader does
              not read it as a contract breach.
- R5 / Cross #15 — enter_mode as step 0 of modes/discover.md, plus NO_MODE_ENTRY and MODE_FILE_CHANGED
              in check_shortlist, with one quiet and two firing tests.
- R8 / Cross #14 — new final task: append your scripts, references and modes/discover.md to SKILL.md's
              self-check AND gate table, and extend test_skill_structure.py's skip set (opencli_meta.py
              is library-only).
- R9 / Cross #26 — retract SKILL.md's "discover is not yet built" sentence in that same final task.
`,
  },
  {
    n: 4,
    file: PLANDIR + '/2026-08-09-4-interview-mode.md',
    audit: RES + '/audit-4.md',
    assigned: `
YOUR CROSS-CHECK EDITS (in addition to every defect in your audit file):

- Cross #19 / R1 — delete mock_vocab.MARKET_KEYS and import vocab.MARKET_KEYS from Plan 1's shared
              module. Two modules in one flat scripts/ namespace exporting the same name with
              different contents is a guaranteed drift. If your mock work genuinely needs the extra
              token, name it MOCK_MARKET_KEYS and document it as a superset of vocab.MARKET_KEYS.
              Also import BANDS, DEFECT_TAGS and CONTRADICTED from vocab.
- Cross #20 — add the sys.path.insert guard to check_mock.py for parity with every other gate.
- R4 / audit defect 14 — _answer_bank_default must call paths.answer_bank(...) rather than re-deriving
              the profile directory with workspace.parents[1].
- R2        — exit-2 receipts with verdict "could_not_run"; and audit defect 13 (a journal write
              failure must return 2 with RECEIPT_WRITE_FAILED, never exit 0 with no receipt).
- Cross #9 (consumer side) — Plan 2 is adding the quote=-field exemption to lint_no_prediction.py for
              MOCK-*-V1 blocks. Remove your fixture's "40 percent" dodge and write the honest "40%",
              and state in your Interfaces/Consumes that you depend on Plan 2 shipping that exemption.
- R5 / Cross #15 — enter_mode as step 0 of modes/interview.md, plus NO_MODE_ENTRY and
              MODE_FILE_CHANGED in check_mock, with one quiet and two firing tests.
- R8 / Cross #14 — new final task: append your scripts, references, both agent files and
              modes/interview.md to SKILL.md's self-check AND gate table, and extend
              test_skill_structure.py's skip set (mock_vocab.py and mock_blocks.py are library-only).
- R9 / Cross #26 — retract SKILL.md's "interview is not yet built" sentence in that same final task.
- Your audit's defect 7 (the indentation ambiguity) is the highest-risk one: no single reading of your
  current indentation convention makes the plan work. State ONE rule at the top of the plan and
  re-indent every fixture so it obeys that rule, then verify by actually parsing them.
`,
  },
]

const fixed = pipeline(
  FIXES,
  (p) => agent(RECONCILED + '\n' + HOWTOFIX + `

You are fixing PLAN ${p.n}.

Plan file to edit:  ${p.file}
Its audit:          ${p.audit}
The spec:           ${SPEC}
Cross-plan review:  ${RES}/cross.md   (read the sections that name Plan ${p.n})

${p.assigned}

Read the audit file in full first. Every numbered defect in it is yours to fix unless you can show it
does not reproduce. Then apply the cross-check edits above. Then re-read your own Global Constraints
section and update it for anything the RECONCILED CONTRACT changed.

Return a short report: how many audit defects you fixed, how many you rejected (with the reason for
each rejection), which cross-check edits you applied, the plan's new task count and line count, and
anything you could not fix and why.`,
    { label: 'fix:plan-' + p.n, phase: 'Fix' }),

  (report, p) => agent(RECONCILED + `

Re-audit a plan that has just been revised in response to an earlier audit. Your job is to decide
whether it is now executable, and to catch fixes that introduced new defects — a common failure when
many edits land in one pass.

Plan file: ${p.file}
Its earlier audit (every defect in it was supposed to be fixed): ${p.audit}
The fixer's own report of what it did:
${report}

Method — do not take the fixer's word for anything:
1. Extract EVERY python code block from the plan into a sandbox under
   ${SCRATCH}/reverify-${p.n}/
   (stub scripts/journal.py, scripts/paths.py and scripts/vocab.py to the RECONCILED CONTRACT above
   if this plan does not create them itself) and RUN every test module. Report the pass/fail counts.
2. For each defect in the earlier audit, state FIXED / NOT FIXED / REJECTED-WITH-GOOD-REASON.
3. Check every "Expected: PASS (N passed)" against the real test count you just measured.
4. Placeholder scan: TBD, TODO, implement later, fill in details, add appropriate error handling,
   add validation, handle edge cases, "write tests for the above" without code, "similar to Task N",
   any step without code where code is needed, any symbol referenced but never defined in a
   Produces block.
5. Git rules: any "git add -A", "git add .", "git push", "-c user.".
6. RECONCILED CONTRACT compliance: vocab.py imported rather than redeclared; exit-2 receipts with
   verdict "could_not_run"; receipt verdicts inside the closed set; paths.py actually used;
   enter_mode wired for this mode; the self-check/gate-table extension task present (Plans 2-4);
   the "not yet built" retraction present (Plans 2-4); no /private/tmp references.
7. NEW defects introduced by the fixes.

Return markdown: the sandbox run results first (module by module, pass/fail), then a table of the old
defects with their status, then any NEW defects with line numbers and concrete fixes, then a verdict
line READY or NEEDS-WORK. Do not invent defects to look thorough — if it is clean, say READY briefly.`,
    { label: 'reverify:plan-' + p.n, phase: 'Reverify' }).then((audit) => ({ n: p.n, file: p.file, report, audit })),
)

const evalPlan = agent(RECONCILED + `

Write a FIFTH implementation plan: the evaluation rebuild. Spec section 10's last row assigns it to
this implementation and none of the four existing plans picks it up — the cross-check flagged it as an
unowned spec requirement.

Write to EXACTLY: ${PLANDIR}/2026-08-09-5-eval-rebuild.md
Title: "Evaluation Rebuild Implementation Plan"

Read first:
  - ${SPEC}  (section 10 last row, section 7 testing discipline, section 11 the whole risk register)
  - ${RES}/preserve.json  — its eval_harness object records what the CURRENT harness measures, how to
    re-run it, and the recorded baseline verbatim
  - the existing harness: /Users/donghanglyu/.claude/skills/job-application-workspace/iteration-1/
    (benchmark.json, evals.json, review.html, scenario-inputs/, eval-0..4 each with eval_metadata.json,
    old_skill/ and with_skill/)
  - the four plans in ${PLANDIR}/ so your scenarios exercise what they actually build

Known problems with the existing baseline, from the research — design around them, do not inherit them:
  - one run per configuration although the metadata claims three
  - only two of five evals have a baseline arm
  - one baseline assertion is logged as non-discriminating (it cannot tell the arms apart, so it
    measures nothing)

The plan must cover:
1. What iteration-2 measures, and the honest limits of what an eval like this can show. An eval that
   cannot distinguish the arms is not evidence.
2. Scenarios for the NEW failure modes the four plans introduce, at minimum:
   - discover: a blocked adapter (exit 1, empty stdout, YAML on stderr) — does the run correctly refuse
     to say "no matching jobs"?
   - discover: rows with a blank identifying field (the measured indeed defect) — are they recovered
     or reported, never read as absence?
   - discover: zero results vs 403 — are they distinguished?
   - discover: a fabricated shortlist row whose source_id is absent from raw/ — is it caught?
   - assess: a login-wall page returned as 200 OK — does it refuse rather than extract must-haves?
   - assess: inputs too thin to support a verdict — does insufficient_evidence fire?
   - assess: an expired market convention — banner at runtime, hard failure in CI?
   - apply: TARGET MARKET "United States (Los Angeles, CA)" with personal data present — the measured
     Cluster-1 leak
   - apply: an ATS REJECT for a keyword the candidate genuinely lacks — does the honest-gap early stop
     fire instead of an ungrounded insert?
   - interview: a candidate who drifts into an unsourced fact — is it tagged with its quote, and does
     the walk-back section become mandatory?
3. How the arms are defined (baseline vs with-skill), how many runs per configuration, and how a
   non-discriminating assertion is detected and rejected BEFORE it enters the benchmark.
4. Scoring that follows the spec's own discipline: no fabricated numbers, and every assertion pins the
   quiet case as hard as the firing case.
5. How to re-run the whole thing, and where results live.

Use the same required plan header as the other four (the "For agentic workers" line, Goal,
Architecture, Tech Stack, Global Constraints), the same File Structure section, and the same
bite-sized task shape: Files / Interfaces (Consumes + Produces) / checkbox steps of one action each,
following write-failing-test -> run-and-watch-it-fail -> minimal-implementation -> run-and-watch-it-pass
-> commit. No placeholders of any kind. Real code in every code step. Named-path commits. Never push.

Return a short report: the path you wrote, the task count, the line count, the scenario count, and any
judgement call the spec did not settle.`,
  { label: 'author:plan-5', phase: 'Fix' })

phase('Final')

const results = await fixed
const plan5 = await evalPlan

const final = await agent(RECONCILED + `

Five implementation plans now exist. Four were just revised in response to individual audits and a
cross-plan consistency review; the fifth is new. Do the FINAL cross-plan consistency pass.

Plans:
  1 ${PLANDIR}/2026-08-09-1-migration-and-p0-fixes.md
  2 ${PLANDIR}/2026-08-09-2-assess-mode.md
  3 ${PLANDIR}/2026-08-09-3-discover-mode.md
  4 ${PLANDIR}/2026-08-09-4-interview-mode.md
  5 ${PLANDIR}/2026-08-09-5-eval-rebuild.md
Spec: ${SPEC}
The previous cross-check (every "ordered list of edits" item should now be resolved): ${RES}/cross.md

Report, tersely — this is a confirmation pass, so do not restate what is now correct:

1. Which of the previous cross-check's 28 ordered edits are STILL unresolved. Quote the plan line that
   shows it is unresolved. This is the most important section.
2. Any NEW name, signature, enum, filename, exit-code or schema collision introduced by the fixes.
3. Any Consumes entry with no matching Produces anywhere, and any ordering violation (execution order
   is 1 -> 2 -> 3 -> 4 -> 5).
4. Spec requirements still with no owning task, walking section 1 through section 12.
5. RECONCILED CONTRACT violations, rule by rule (R1 through R15).

End with a verdict line: CONSISTENT or INCONSISTENT. If inconsistent, give the ordered list of
remaining edits, each assigned to one plan.`,
  { label: 'final-cross-check', phase: 'Final' })

return {
  final,
  plan5,
  plans: results.filter(Boolean).map((r) => ({ n: r.n, report: r.report, audit: r.audit })),
}
