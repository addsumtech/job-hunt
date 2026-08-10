export const meta = {
  name: 'job-hunt-final-fix',
  description: 'Fix the blocking defects the re-audits found, then run the final cross-plan check',
  phases: [
    { title: 'Fix', detail: 'targeted blocking-defect fixes, one agent per plan' },
    { title: 'Final', detail: 'cross-plan consistency confirmation' },
  ],
}

const REPO = '/Users/donghanglyu/code_project/job-hunt'
const PLANDIR = REPO + '/docs/superpowers/plans'
const SPEC = REPO + '/docs/superpowers/specs/2026-08-09-job-hunt-skill-design.md'
const RES = REPO + '/docs/superpowers/research/2026-08-09'
const SCRATCH = '/private/tmp/claude-501/-Users-donghanglyu/d1ca171b-6798-42dc-9582-87e4635be401/scratchpad'

const SHARED = `
# CROSS-PLAN FACTS — established by executing the code, not by reading it. Do not relitigate.

## F1. paths.mode_file is the ONLY way to locate a mode file
There is NO enter_mode.mode_file. Plan 1 states this in so many words:
  "There is no enter_mode.mode_file: the mode-file path comes from paths.mode_file(mode, root),
   so enter_mode and check_apply cannot disagree about where a mode file lives."
The real signature is  paths.mode_file(mode: str, root=None) -> pathlib.Path  — MODE FIRST, root second.
Plans 2, 3 and 4 all call enter_mode.mode_file(skill_root, MODE): wrong module, wrong argument order.
Measured effect in Plan 3: AttributeError on every check_shortlist.main() call, 47 of 123 tests red.
Every plan that calls it must "import paths" and call paths.mode_file(MODE, skill_root), and must fix
its Interfaces "Consumes" line to name paths.mode_file(mode, root) -> pathlib.Path (Plan 1).

## F2. The shipped SKILL.md has a "## Modes" TABLE, not a "not yet built" sentence
Plan 1's revision replaced the prose sentence with a purpose-built "## Modes" table in the shipped
SKILL.md (Plan 1 lines ~5677-5683). The string "discover, assess and interview are not yet built in
this repo" now appears only inside Plan 1's own internal inventory table — it is NOT in the artifact.
So Plans 3 and 4's retraction steps target a string that will not be there. Each of Plans 2, 3 and 4
must instead EDIT ITS OWN ROW of the shipped "## Modes" table, and must name the correct test.
Read Plan 1's Task 20 to see the exact table shape before writing the edit.

## F3. Plans 2, 3 and 4 each edit the SAME skip-set line in test_skill_structure.py
Plan 1 creates the skip set. Each later plan appends its own library-only modules. Written as a
whole-line replacement, whichever plan runs last deletes the earlier plans' entries. Each plan must
express its edit as an APPEND to the existing tuple, quoting the state it expects to find (Plan 2
adds nothing library-only; Plan 3 adds opencli_meta.py; Plan 4 adds mock_vocab.py and mock_blocks.py),
and must state in the step that the earlier plans' entries are expected to be present already.

## F4. Bilingual output is a first-class path
count_coverage.py has --lang {zh,en} and check_assessment already carries bilingual DISCLAIMER_ANCHORS
and VERDICT_MARKERS. Any new constant that matches on Chinese-only text will cry wolf on a correct
English document. The spec's own discipline: a check that cries wolf on ordinary output is worse than
no check, because the reader learns to skip the line.

## F5. Git rules
Stage NAMED PATHS only. Never "git add -A", never "git add .". NEVER push. No "-c user.name/email".
`

const HOW = `
# HOW TO WORK

Fix ONLY the defects listed for you. This is a targeted pass, not another full revision — the
re-audit already confirmed, by executing the extracted code, that everything else in your plan works.
Do not restructure, do not re-word what is already correct, do not "improve" neighbouring text.

For each defect:
  1. Read the cited lines to confirm the claim. If it does not reproduce, say so and skip it.
  2. Apply the fix exactly as specified.
  3. Where a fix changes an expected count or an expected string, recompute the true value by
     measuring, not by estimating.
  4. Grep the whole plan for the same mistake elsewhere — these defects travel in pairs.

Use Edit for surgical changes. These files are 5,000-6,300 lines; do NOT rewrite them wholesale.
A lost task is a worse defect than the one you fixed.

You may create throwaway verification files under ${SCRATCH}/finalfix/ to check your work by running
it. Do NOT create anything under the skill tree itself (no scripts/, modes/, references/) — you are
editing a plan, not executing it.

Return a terse report: each defect with FIXED / DID-NOT-REPRODUCE, anything you found while grepping
for siblings, and the plan's final line count.
`

const PLANS = [
  {
    n: 1,
    file: PLANDIR + '/2026-08-09-1-migration-and-p0-fixes.md',
    audit: SCRATCH + '/reaudit-1.md',
    defects: `
Your re-audit ran your extracted code: 264 passed, 0 failed, and all 16 earlier defects are confirmed
fixed. Only these remain. NEW-1 and NEW-2 are blocking; the rest are cheap.

NEW-1 (BLOCKING) — Task 20 Step 8 cannot exit 0, and its recovery instruction is wrong.
  Measured against the live baseline: 10 substantive SKILL.md lines are covered by neither Step 5's
  move ranges nor Step 6's inventory.
    - SKILL.md:4-9 — the six description lines. Fixing old-defect 13 made the description NEW PROSE,
      so those six lines exist nowhere in the new tree. (Lines 10-12 do survive inside the new
      description; 4-9 do not.)
    - SKILL.md:16 ("# Job Application Orchestrator", 28 chars), :18 (the "experienced career coach and
      recruiter" paragraph), :24 ("**The review loop is non-negotiable.** ... each a fresh subagent —
      must all decide the package passes."), :26 ("**Read references as you go.** ... do not work from
      memory or assumption.") — none is in 152-195 or any other cited range.
    - SKILL.md:20 ("## The load-bearing rule — read first", 32 chars) survives only if the implementer
      reuses the exact heading; the inventory cites only :22.
  Line 5867 says "If a line is reported lost, it was condensed rather than moved — put it back", which
  for 4-9 means restoring the one-mode description this pass deliberately replaced. Task 21 Step 6 then
  says "If any line from SKILL.md appears, stop: Task 20 lost content and no waiver is appropriate" —
  so an obedient executor halts at Task 21.
  FIX: (a) add inventory rows for SKILL.md:18, :24, :26 and state the new H1 and heading text
  explicitly; (b) insert a Step 8a waiving exactly the six description-line hashes, in the shape of
  Task 21 Step 6, with its own written reason ("the frontmatter description is new trigger text
  covering four modes; the baseline description named one mode and no skill name"); (c) reword L5867
  so "put it back" applies to body rules only.

NEW-2 (BLOCKING) — Task 21's waiver count is 12, not 9, and one reason describes lines it does not cover.
  Measured on the live README with check_skill_lossless.normalize: besides the nine Skill-flow lines
  (35, 37-44), three more deletions sit at or above the 25-char floor:
    README.md:83  "│   ├── cv/template.tex ... # LaTeX CV template"      -> 33 chars (deleted by Step 4)
    README.md:84  "│   └── letter/template.tex ... # LaTeX letter template" -> 41 chars (Step 4)
    README.md:104 "Expected: 41 tests, all passing."                      -> 29 chars (Step 5)
  The Step 6 regex waives all twelve, so the script prints "waived 12 README lines" while Step 7 and
  Task 23 Step 6 say 9 — three Expected strings are wrong. Worse, the single REASON records the two
  Layout lines and the test-count line as "README's duplicated 8-step pipeline list", which is false
  and defeats the "a decision someone made rather than a casualty" property.
  FIX: change all four expectations to 12, and split REASON into three by line number: the nine
  pipeline lines; the two Layout lines ("names a .tex template deleted in Task 2"); the test-count
  line ("a count nothing updates — replaced by make check").

NEW-3 (moderate) — L5619-5627: the posting-field prose is inserted INSIDE the Task 20 inventory table.
  The table starts at L5603; L5618 is blank and L5619-5627 is prose, so L5628 through L5646 render as
  loose text, not table rows — nineteen inventory rows including Gates and Self-check.
  FIX: move the twelve-name block and its paragraph to after L5646.

NEW-4 (moderate) — L5989: Task 21 Step 4 is the only content change in the plan not written out.
  "Replace the ## Layout code block's contents with the real tree" gives constraints, not text, while
  test_the_layout_matches_the_repo pins four script names and NEW-2's arithmetic depends on exactly
  which layout lines change.
  FIX: write the replacement tree literally, including modes/apply.md, Makefile,
  .github/workflows/checks.yml and each new script.

NEW-5 (minor) — the refusal label is spelled two ways: vocab.VERDICT_ZH[REFUSAL] is the unspaced form
  per R1, but L5710 and L5532 use a spaced form, hard-typed into the assertion at L5462.
  FIX: keep the unspaced form everywhere; change L5462 to
  assert vocab.VERDICT_ZH[vocab.REFUSAL] in text

NEW-6 (minor) — L6296: the smoke test creates the workspace it says does not exist. Verified: every
  gate except check_apply mkdirs via journal.append, so a typo'd --workspace silently materialises a
  workspace — the exact harm paths.py's own docstring names.
  FIX: give every gate the "if not ws.is_dir(): print...; return 2" guard check_apply already has
  (this matches R2's plain reading), and point Step 5's smoke test at a directory it creates and removes.

NEW-7 (minor) — L1539 and the docstring at L1624-1627 justify the once-per-profile guard with "a
  --format all run", but render_cv.main has --format choices=["md","docx","pdf"] — there is no "all".
  FIX: say "an md + docx + pdf run — three invocations, or three direct calls from one process".

ALSO, from F2/F3: your Task 20 writes the shipped "## Modes" table and Plan 1 owns the skip set.
Add one sentence to each so Plans 2/3/4 know what to edit: state that a later plan flips its own row
of the Modes table (not a prose sentence), and that the skip set is APPENDED to, never replaced.
`,
  },
  {
    n: 2,
    file: PLANDIR + '/2026-08-09-2-assess-mode.md',
    audit: SCRATCH + '/reaudit-2.md',
    defects: `
Your re-audit ran your extracted code: 147 passed and 8 failed, and the 8 failures are RED BY DESIGN
(test_market_tables.py cannot pass until Tasks 7-11 create the YAML tables) — that is the correct TDD
red phase, confirmed. All 17 earlier defects are genuinely fixed. Only these remain.

N1 (HIGH, reproduced) — the three new checks are Chinese-only and fire on a correct English assessment.
  L5118 DISQUALIFIER_HEADING = "## 硬性阻断项" and L5125 ACCEPTANCE_COLUMNS = ("验收标准", "输出物").
  English is a first-class path in this very plan (count_coverage.py --lang {zh,en}; render_block emits
  "apply verdict:"; check_assessment already has bilingual DISCLAIMER_ANCHORS and VERDICT_MARKERS).
  Reproduced on a clean English card with one knockout gap:
      NO_DISQUALIFIER_SECTION: 1 knockout requirement(s) are not met and there is no '## 硬性阻断项' section
      NO_ACCEPTANCE_COLUMN: verdict is blocked and the '验收标准' column is missing
      NO_ACCEPTANCE_COLUMN: verdict is blocked and the '输出物' column is missing
  This re-creates the exact cry-wolf class that fix #4 was written to remove. The quiet tests miss it
  because the base ASSESSMENT fixture has R2 screening: weighted, so the disqualifier branch is never
  exercised on a non-Chinese document.
  FIX: make both bilingual, mirroring the two constants directly above them —
    DISQUALIFIER_HEADINGS = ("## 硬性阻断项", "## Hard blockers")     (try each in _section_lines)
    ACCEPTANCE_COLUMNS = (("验收标准", "Acceptance criterion"), ("输出物", "Deliverable"))  (one of each pair)
  State both spellings in modes/assess.md section 4 and section 10. Add one quiet test: knockout gap +
  English heading + English column names -> no finding.

N2 (HIGH, cross-plan) — Task 14 edits SKILL.md for a line Plan 1 moves to modes/apply.md, and misses
  the copy that IS in SKILL.md.
  Step 2 (5458-5463) targets baseline SKILL.md:84, but Plan 1 Task 20 Step 5 moves baseline
  SKILL.md:78-89 into modes/apply.md, and Plan 1's SKILL.md inventory has no row sourced from :84.
  Meanwhile Plan 1's inventory DOES carry references/gap-analysis.md:249-276 into SKILL.md verbatim —
  a second copy of the very disclaimer Step 1 rewrites — which Task 14 never touches. Consequences:
  Step 2's target string is not in SKILL.md so the edit no-ops; Step 3 re-points the anchor to
  "not a forecast of the outcome" but Plan 1's test_every_layer1_rule_is_inline_in_skill_md asserts
  anchors are in SKILL.read_text(), so that test goes RED; SKILL.md keeps shipping the percentage
  disclaimer; and Step 5's "exactly two waived" cannot hold.
  FIX: Task 14 must (a) apply the same rewrite to SKILL.md's verbatim copy of the disclaimer,
  (b) change the parenthetical in modes/apply.md rather than SKILL.md, (c) stage
  references/gap-analysis.md SKILL.md modes/apply.md scripts/tests/required_inline.json
  scripts/lossless-allowlist.json at L5501, and (d) re-measure the waived count against Plan 1's final
  SKILL.md rather than asserting "two".

N3 (LOW) — L5633's "Done means" self-check fails on correct code: grep -c 'return 2' scripts/*.py
  matches the number of cannot_run( call sites. Measured: 'return 2' = 1 per script (inside cannot_run),
  'cannot_run(' = 3-4 per script.
  FIX: grep -c 'return cannot_run(' scripts/*.py equals the exit-2 paths, and each gate has exactly one
  bare 'return 2', inside cannot_run.

N4 (LOW) — count_coverage.py's docstring (2100-2113) omits R2's workspace-absent exception that the
  other six carry.
  FIX: append before L2113: Exit 2 still writes a receipt, verdict "could_not_run", unless the
  workspace directory itself is absent -- there is nothing to append to.

N5 (LOW) — L5396 expects test_skill_structure.py red "with one failure per script this plan added plus
  one for modes/assess.md". Plan 1's test_the_self_check_names_every_script and ..._every_mode_file each
  loop INSIDE one test function, so it is 2 failing tests, not 8.
  FIX: "two failures — test_the_self_check_names_every_script and test_the_self_check_names_every_mode_file".

N6 (LOW) — NO_STRATEGY_SECTION checks no section, and the mode file says it does. modes/assess.md
  section 10 says "counts how many of the five appear in the section"; the implementation does
  "name in markdown" over the whole file. So a natural rendering that mentions two strategy names in a
  contrast sentence trips STRATEGY_NOT_UNIQUE.
  FIX: scope both to _section_lines(lines, "## 那该怎么办") — the helper already exists and this is what
  the finding names claim — or change the mode file's wording and say a token may be written once only.

N7 (LOW) — L4138's enforcement table maps the disqualifier section to DISQUALIFIER_AFTER_VERDICT and
  NO_DISQUALIFIER_SECTION, omitting DISQUALIFIER_NOT_NAMED, the only finding enforcing the id-list half.
  Same omission at L4278.
  FIX: add DISQUALIFIER_NOT_NAMED to both.

N8 (LOW) — two stale Interfaces claims: L2288 says check_conventions.SKILL_ROOT is "the repo root,
  resolved once here" and that check_assessment imports it; the code is SKILL_ROOT = paths.SKILL_ROOT
  (an alias) and check_assessment uses paths.SKILL_ROOT directly, importing only CONVENTIONS_DIR.
  FIX: L2288 -> "SKILL_ROOT = paths.SKILL_ROOT — re-exported for readability; paths.py owns the value";
  drop check_conventions.SKILL_ROOT from L4533.

PLUS the cross-plan items:
- F1: fix your paths.mode_file call and its Interfaces line (yours is at approximately L5171).
- F2: your "retract the not-yet-built sentence" step must instead edit YOUR ROW of the shipped
  "## Modes" table, and name the correct test.
- F3: express your skip-set edit as an APPEND that expects Plan 1's entries to be present.
`,
  },
  {
    n: 3,
    file: PLANDIR + '/2026-08-09-3-discover-mode.md',
    audit: SCRATCH + '/reaudit-3.md',
    defects: `
Your re-audit ran your extracted code: 47 failed / 76 passed AS WRITTEN, but every one of the 47
failures has a single cause (N1 below). With a one-line shim the plan's own numbers reproduce exactly:
16/12/19/26/4/10/10/19/3/4 = 123 passed. All 11 earlier defects are genuinely fixed, several confirmed
by mutation testing. So N1 is the whole ballgame; read your re-audit for N2 onward.

N1 (BLOCKING) — enter_mode.mode_file does not exist, and the argument order is reversed.
  Plan lines 4232 and 4399. See CROSS-PLAN FACT F1 above. Effect: AttributeError on every
  check_shortlist.main() call — 47 of 123 tests red, and Task 9 Step 7's live check_shortlist exits on
  a traceback instead of 0.
  FIX, in the Task 8 Step 4 blocks:
      import paths       # noqa: E402  (Plan 1)   — keep the enter_mode import too
      ...
          mode_path = paths.mode_file(MODE, skill_root)
  and change L4232's Interfaces line to  paths.mode_file(mode, root) -> pathlib.Path  (Plan 1).

N2 (BLOCKING for Task 10) — Step 6 retracts a sentence the shipped SKILL.md does not contain.
  See CROSS-PLAN FACT F2. Plan lines 4953-4966 and Step 8's "Expected: PASS" at 4985. Read Plan 1's
  Task 20 for the shipped "## Modes" table shape, edit YOUR ROW of it, and correct the Expected.

Then work through the remaining NEW defects in your re-audit file (${SCRATCH}/reaudit-3.md, section 3,
N3 onward) — read them there in full and fix each one.

PLUS: F3 — express your skip-set edit (adding opencli_meta.py) as an APPEND that expects Plan 1's
entries to already be present, so Plan 4's later edit cannot delete yours and yours cannot delete
Plan 1's.
`,
  },
  {
    n: 4,
    file: PLANDIR + '/2026-08-09-4-interview-mode.md',
    audit: SCRATCH + '/reaudit-4.md',
    defects: `
Read your re-audit in full at ${SCRATCH}/reaudit-4.md and fix every defect in its "NEW defects"
section, N1 through N6. N1 and N2 are blocking.

N1 (BLOCKING) — enter_mode.mode_file does not exist. See CROSS-PLAN FACT F1. Your call is at
  approximately L2122. Use paths.mode_file(MODE, skill_root), mode first, and fix the Interfaces line.

N2 (BLOCKING) — Task 9 Step 5 retracts a sentence that is not in SKILL.md, in the wrong table shape,
  and names the wrong test. See CROSS-PLAN FACT F2. Read Plan 1's Task 20 for the shipped "## Modes"
  table, edit YOUR ROW, and name the test that actually exists.

N3 (medium) — Task 9's skip-set edit deletes Plan 3's entry. See CROSS-PLAN FACT F3: express it as an
  APPEND of mock_vocab.py and mock_blocks.py that expects Plan 1's entries AND Plan 3's opencli_meta.py
  to be present already.

N4, N5, N6 — as written in your re-audit file.
`,
  },
]

const fixed = parallel(PLANS.map((p) => () => agent(SHARED + '\n' + HOW + `

You are doing the FINAL targeted fix pass on PLAN ${p.n}.

Plan file:   ${p.file}
Re-audit:    ${p.audit}   (read it — it contains measurements you need)
Spec:        ${SPEC}
Plan 1 (for the shipped SKILL.md shape, the Modes table, paths.py and the skip set):
             ${PLANDIR}/2026-08-09-1-migration-and-p0-fixes.md

${p.defects}
`, { label: 'fix:plan-' + p.n, phase: 'Fix' })))

phase('Final')

const reports = await fixed

const final = await agent(SHARED + `

FINAL cross-plan consistency confirmation. Five implementation plans have been through two rounds of
individual audit and fixing; this is the last gate before execution begins.

Plans (execution order 1 -> 2 -> 3 -> 4 -> 5):
  1 ${PLANDIR}/2026-08-09-1-migration-and-p0-fixes.md
  2 ${PLANDIR}/2026-08-09-2-assess-mode.md
  3 ${PLANDIR}/2026-08-09-3-discover-mode.md
  4 ${PLANDIR}/2026-08-09-4-interview-mode.md
  5 ${PLANDIR}/2026-08-09-5-eval-rebuild.md
Spec: ${SPEC}
The first cross-check and its 28 ordered edits: ${RES}/cross.md
The four re-audits: ${SCRATCH}/reaudit-1.md through reaudit-4.md
What the fixers just reported doing:
${reports.filter(Boolean).map((r, i) => '--- plan ' + (i + 1) + ' ---\n' + r).join('\n\n')}

Verify by reading the plans, not by trusting the reports. Report tersely — this is a confirmation
pass, so do not restate what is correct:

1. CROSS-PLAN FACTS F1-F4: is each now honoured in every plan that was affected? Quote the fixed line.
   F1 in particular: grep all five plans for "enter_mode.mode_file" — it must appear ZERO times except
   possibly in prose explaining that it does not exist.
2. Any remaining name, signature, enum, filename, exit-code or schema collision across the five plans.
3. Any Interfaces "Consumes" entry with no matching "Produces" anywhere, and any ordering violation.
4. Any of the first cross-check's 28 edits still unresolved.
5. Spec requirements with no owning task, walking section 1 through section 12 of the spec.
6. THE EXECUTION QUESTION, which matters more than the rest: if an engineer with no context started
   at Plan 1 Task 1 and worked straight through, where would they FIRST get stuck? Name the task, the
   step, and what stops them. If the answer is "nowhere", say that plainly.

End with a verdict line: READY-TO-EXECUTE or BLOCKED. If blocked, give the ordered list of remaining
edits, each assigned to one plan and one task.`,
  { label: 'final-cross-check', phase: 'Final' })

return { final, reports: reports.filter(Boolean) }
