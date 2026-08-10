# Re-audit — `2026-08-09-2-assess-mode.md`

## 1. Sandbox run

Every fenced block extracted verbatim (4- and 5-backtick fences handled) into
`/private/tmp/claude-501/-Users-donghanglyu/d1ca171b-6798-42dc-9582-87e4635be401/scratchpad/reverify-2/sandbox/`.
`journal.py`, `paths.py`, `vocab.py` and `enter_mode.py` were taken **verbatim from Plan 1** (not stubbed), so interface drift would show.

| Module | Result | Plan's "Expected" | Match |
|---|---|---|---|
| `test_evidence_blocks.py` | **13 passed** | line 545: `13 passed` | ✅ |
| `test_check_evidence_refs.py` | **13 passed** | line 914: `13 passed` | ✅ |
| `test_lint_no_prediction.py` | **20 passed** | line 1405: `20 passed` | ✅ |
| `test_consistency.py` | **22 passed** | line 1890: `22 passed` | ✅ |
| `test_count_coverage.py` | **17 passed** | line 2264: `17 passed` | ✅ |
| `test_check_conventions.py` | **27 passed** | line 3000: `27 passed` | ✅ |
| `test_check_assessment.py` | **35 passed** | line 5390: `35 passed` | ✅ |
| `test_market_tables.py` | **8 failed** (6× `FileNotFoundError: cn.yaml`, 1 assert, 1 `us.yaml`) | line 3092: `FAIL — 8 failed`; line 4103: `8 passed` after Task 11 | ✅ red-by-design confirmed |

`147 passed, 8 failed` total — exactly the fixer's claim. Every `Produces:` symbol in every Interfaces block exists (checked by `hasattr` across all seven modules; zero missing).

Beyond the suites I also ran the pipeline end-to-end on output the mode file *mandates*:
- `blocked` verdict + `## 30/60/90 计划` heading + strategy + both column headers → `check_assessment.check` = `[]`, CLI rc 0, `lint_no_prediction` rc 0. **Old defects #1 and #2 are genuinely dead, not just unit-tested.**
- Task 12 Step 2's anchor script run against the extracted `modes/assess.md`: all 28 needles present, `language: en` absent.
- Task 7 Step 1 header + Step 2 entry 1 assembled into `cn.yaml` and linted: **rc 0**.
- Task 14's two waiver hashes recomputed from the real baseline at `~/.claude/skills/job-application` using Plan 1's `normalize`/`line_key`: `d6da8347c791420b` ✅ and `903ea1e8ad127567` ✅ — both correct, not fabricated.
- `test_a_delta_of_exactly_three_does_not_warn`: measured zh 3 / en 0 → **delta exactly 3**, ratio 0.237 inside the 0.20–0.60 band. Real boundary test.

## 2. Old defects

| # | Old defect | Status |
|---|---|---|
| 1 | 30/60/90 fails the gate | **FIXED** — `ROADMAP_HORIZON` (L1190-block), 2 tests incl. a narrowness pin (`8/11` on the same line still fires) |
| 2 | Expired `review_by` hard-fails at runtime | **FIXED** — `WARN_EXPIRED_REVIEW_BY` + `MISSING_STALE_BANNER`; the wrong-behaviour test replaced by three |
| 3 | `CONVENTION_PARAPHRASED` on verbatim output | **FIXED** — `_squeeze()` both sides; fixture `text_zh` now carries a hard newline the md reflows out |
| 4 | `DISQUALIFIER_AFTER_VERDICT` cries wolf | **FIXED** — keyed on `## 硬性阻断项` + row **ids**; quiet test uses a genuine Chinese paraphrase with no smuggled English |
| 5 | Layer-1.5 backstop missing | **FIXED** — step 0 of `modes/assess.md`; `NO_MODE_ENTRY` + `MODE_FILE_CHANGED`; 1 quiet + 2 firing tests |
| 6 | Task 13 enforces none of Task 12's "other half" | **FIXED** — `NO_STRATEGY_SECTION`, `STRATEGY_NOT_UNIQUE`, `NO_ACCEPTANCE_COLUMN` with quiet+firing tests |
| 7 | No receipt on exit 2 | **FIXED** — `cannot_run()` in all 7, called from every `return`-2 site; 7× exit-2-receipt test + 7× workspace-absent test |
| 8 | Live-violations test makes a correct build impossible | **FIXED** — scoped to `cck.PROSE_FIELDS`, with the reason written into the test |
| 9 | Task 9 row 6 instructs a lint-failing edit | **FIXED** — line 3737-3742 names `source.title`/`source.quote` explicitly |
| 10 | No red phase on Tasks 7–12 | **FIXED** — `test_market_tables.py` moved to Task 6 Step 7 (verified 8 red); Task 12 Step 2 anchor script runs pre-file |
| 11 | Task 7 Step 1 not a 2–5-min step | **FIXED** — one checkbox per entry across all five tables, each ending in `lint_<key>` |
| 12 | `/private/tmp` dependency | **FIXED** — reads the committed `docs/superpowers/research/2026-08-09/`; no `/private/tmp` path anywhere |
| 13 | False `--check-only` claim | **FIXED** — line 573 now "the form `check_assessment.py` reproduces in-process" |
| 14 | Two wrong pass counts | **FIXED** — all eight counts now match measurement |
| 15 | `INVALID_KIND` undocumented/untested | **FIXED** — lines 1921–1922 + `test_an_out_of_enum_kind_is_reported` |
| 16 | Nothing asserts `<key>.yaml` declares `market: <key>` | **FIXED** — `test_every_table_declares_the_market_its_filename_claims` |
| 17 | `\|delta\| >= 3` hits a shipped entry | **FIXED** — `> MODAL_DELTA`, boundary test verified at delta 3 |

**17/17 fixed, 0 rejected.** Contract compliance also clean: vocab imported not redeclared (with a mechanical test at `test_the_market_keys_are_the_shared_ones_and_the_root_is_resolved_once`), all receipt verdicts inside `pass|fail|could_not_run|recorded`, `paths.py` actually used (`paths.mode_file`, `paths.SKILL_ROOT`), R6's twelve names byte-identical to Plan 1's, Task 15 present (R8) with the retraction (R9), no `git add -A`/`git add .`/`git push`/`-c user.`, no `TBD`/`TODO`/"similar to Task N".

## 3. New defects introduced by the fixes

**N1 (HIGH, reproduced) — the three new checks are Chinese-only, and fire on a correct English assessment.**
Lines 5118 `DISQUALIFIER_HEADING = "## 硬性阻断项"` and 5125 `ACCEPTANCE_COLUMNS = ("验收标准", "输出物")`. English output is a first-class path in this very plan: `count_coverage.py` has `--lang {zh,en}` (line 2129), `render_block` emits `apply verdict:`, and `check_assessment` already carries bilingual `DISCLAIMER_ANCHORS` (5116) and `VERDICT_MARKERS` (5117). The two new constants do not. Reproduced on an otherwise-clean English card with one knockout gap:
```
NO_DISQUALIFIER_SECTION: 1 knockout requirement(s) are not met and there is no '## 硬性阻断项' section
NO_ACCEPTANCE_COLUMN: verdict is blocked and the '验收标准' column is missing
NO_ACCEPTANCE_COLUMN: verdict is blocked and the '输出物' column is missing
```
This is the same "cries wolf on ordinary output" class as old #4, reintroduced by its fix. The quiet tests miss it because the base `ASSESSMENT` fixture has `R2: screening: weighted`, so the disqualifier branch is never exercised on a non-Chinese document.
**Fix:** make both bilingual, mirroring the two constants directly above them —
`DISQUALIFIER_HEADINGS = ("## 硬性阻断项", "## Hard blockers")` (try each in `_section_lines`), `ACCEPTANCE_COLUMNS = (("验收标准", "Acceptance criterion"), ("输出物", "Deliverable"))` (require one of each pair). State both spellings in `modes/assess.md` §4 (line 4278 area) and §10 (line 4396–4408). Add one quiet test: knockout gap + English heading + English column names → no finding.

**N2 (HIGH, cross-plan) — Task 14 edits `SKILL.md` for a line Plan 1 moves to `modes/apply.md`, and misses the copy that is actually in `SKILL.md`.**
Step 2 (5458–5463) says SKILL.md's FIT SNAPSHOT bullet ends `Include the required disclaimer (keyword proxy, not an ATS prediction).` That is baseline `SKILL.md:84`, and Plan 1 Task 20 Step 5 moves baseline `SKILL.md:78–89` into `modes/apply.md ## Step 3 — Gap analysis`; Plan 1's Step 6 SKILL.md inventory has **no row sourced from `SKILL.md:84`**. Task 14's own waiver text at 5484 admits it: *"the rest of the line moved to modes/apply.md unchanged."* Meanwhile Plan 1's inventory **does** carry `references/gap-analysis.md:249-276` into SKILL.md *verbatim* — i.e. a second copy of the very disclaimer Step 1 rewrites — which Task 14 never touches. Consequences, all mechanical:
- Step 2's target string is not in `SKILL.md`; the edit no-ops or is applied to the wrong file.
- Step 3 re-points the anchor to `"not a forecast of the outcome"`, but Plan 1's `test_every_layer1_rule_is_inline_in_skill_md` asserts anchors are `in SKILL.read_text()` — that phrase never reaches SKILL.md, so the test goes **red**.
- SKILL.md keeps shipping the `8/10 … 10/10` percentage disclaimer, defeating the task's stated purpose.
- Step 5's `Expected: exactly two waived` (5493) cannot hold: the gap-analysis line still exists in SKILL.md's copy, so it is not "missing" → 0 waived, and the plan's Expected misdiagnoses that as "a waiver key is wrong" (the keys are correct — I recomputed both).
**Fix:** Task 14 must (a) apply the same rewrite to SKILL.md's verbatim copy of the disclaimer, (b) change the parenthetical in `modes/apply.md`, not `SKILL.md`, and (c) stage `references/gap-analysis.md SKILL.md modes/apply.md scripts/tests/required_inline.json scripts/lossless-allowlist.json` at line 5501. Re-verify the waived count against Plan 1's final SKILL.md before committing to "two".

**N3 (LOW) — the "Done means" self-check fails on correct code.** Line 5633: `grep -c 'return 2' scripts/*.py` matches the number of `cannot_run(` call sites. Measured: `return 2` = 1 per script (the one inside `cannot_run`), `cannot_run(` = 3–4 per script. **Fix:** `grep -c 'return cannot_run(' scripts/*.py` equals the exit-2 paths, and each gate has exactly one bare `return 2`, inside `cannot_run`.

**N4 (LOW) — R2's docstring requirement missed on one of seven.** Six modules' docstrings state the workspace-absent exception; `count_coverage.py`'s (2100–2113) does not, and neither does its `cannot_run` docstring. **Fix:** append before line 2113 the sentence the other six carry: `Exit 2 still writes a receipt, verdict "could_not_run", unless the workspace directory itself is absent -- there is nothing to append to.`

**N5 (LOW) — wrong failure shape at Task 13 Step 5.** Line 5396 expects `test_skill_structure.py` red "with one failure per script this plan added plus one for `modes/assess.md`". Plan 1's `test_the_self_check_names_every_script` and `..._every_mode_file` each loop *inside one test function*, so it is **2 failing tests**, not 8. An executor reading "8" will think something else broke. **Fix:** "two failures — `test_the_self_check_names_every_script` and `test_the_self_check_names_every_mode_file`".

**N6 (LOW) — `NO_STRATEGY_SECTION` checks no section, and the mode file says it does.** `modes/assess.md` §10 (plan 4406–4407): "counts how many of the five appear **in the section**". The implementation (5300 area) does `name in markdown` over the whole file, and nothing requires a `## 那该怎么办` heading at all. So "不是 `apply_anyway`，而是 `skill_sprint`" — a natural rendering — trips `STRATEGY_NOT_UNIQUE`. **Fix:** scope both to `_section_lines(lines, "## 那该怎么办")` (the helper already exists, and this is what the finding names claim), or change §10's wording to "anywhere in `fit-assessment.md`" and say a token may be written once only.

**N7 (LOW) — the enforcement table has the blank it exists to expose.** Line 4138 maps "the `## 硬性阻断项` section **and its `R<n>` id list**" to `DISQUALIFIER_AFTER_VERDICT`, `NO_DISQUALIFIER_SECTION` — omitting `DISQUALIFIER_NOT_NAMED`, which is the only finding that enforces the id-list half. Same omission at 4278 in the mode file. **Fix:** add `DISQUALIFIER_NOT_NAMED` to both.

**N8 (LOW) — two stale Interfaces claims about `SKILL_ROOT`.** Line 2288 still says `check_conventions.SKILL_ROOT` is "the repo root, resolved **once** here" and that `check_assessment.py` imports it; the code is `SKILL_ROOT = paths.SKILL_ROOT` (an alias — `paths.py` owns it, per Global Constraints 46–48), and `check_assessment` uses `paths.SKILL_ROOT` directly, importing only `CONVENTIONS_DIR`. Line 4533 correspondingly lists `check_conventions.SKILL_ROOT` as a Consume that does not exist. **Fix:** 2288 → "`SKILL_ROOT = paths.SKILL_ROOT` — re-exported for readability; `paths.py` owns the value"; drop `check_conventions.SKILL_ROOT` from 4533.

## VERDICT: NEEDS-WORK

The 17 audited defects are all genuinely fixed and verified by execution, not by claim — this is a strong fix pass. But two of the fixes introduced new problems: **N1** re-creates the exact cry-wolf failure that fix #4 was written to remove (reproduced against a correct English card, which this plan's own `--lang en` flag makes a supported output), and **N2** makes the newly-added Task 14 non-executable as written and leaves `SKILL.md`'s copy of the rewritten disclaimer untouched, turning Plan 1's anchor test red. N3–N8 are small and can ride along.
