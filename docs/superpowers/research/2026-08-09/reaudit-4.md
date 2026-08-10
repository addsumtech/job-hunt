# Re-audit — `docs/superpowers/plans/2026-08-09-4-interview-mode.md`

## 1. Sandbox run

Sandbox: `/private/tmp/claude-501/-Users-donghanglyu/d1ca171b-6798-42dc-9582-87e4635be401/scratchpad/reverify-4/pkg`
All 64 fenced blocks extracted with a **strict** 4-space dedent (any line at column 0 inside a block aborts extraction). Plan-1 modules (`vocab.py`, `journal.py`, `paths.py`, `enter_mode.py`) stubbed to the RECONCILED CONTRACT; `check_mock.py` assembled by applying Task 3 → Task 4 → Task 5 edits in order.

| Module | Result |
|---|---|
| `test_check_mock_core.py` | **43 passed** |
| `test_check_mock_sources.py` | **32 passed** |
| `test_check_mock_walkback.py` | **18 passed** |
| `test_interview_shapes_doc.py` | **10 passed** |
| `test_mock_assessor_agents.py` | **9 passed** |
| `test_mock_blocks.py` | **17 passed** |
| `test_mock_dryrun.py` | **9 passed, 1 skipped** (Plan-2 composition test; **10 passed** with a `lint_no_prediction` stub) |
| `test_mode_interview_doc.py` | **22 passed** |
| `test_paths.py` | **4 passed** (1 Plan-1 stub + the 3 appended) |
| `test_skill_md_interview_blocks.py` | **4 passed** |
| **Total** | **168 passed, 1 skipped** (169 passed, 0 skipped with the Plan-2 stub) |

Also executed and confirmed:

- **Indentation:** 64 blocks scanned, **0 violations**. The four YAML-in-Python parse checks print exactly `NL`, `1`, `4`, `2`.
- **Incremental sub-steps** (I replayed each partial document, not just the finished one):

| Step | selector | plan says | measured |
|---|---|---|---|
| 1/4a | `neighbours` | 1 passed | 1 passed ✓ |
| 1/4b | `source_label` | FAIL `…no '## Role-family shapes' section` | that exact message ✓ |
| 1/4c | `source_label or populated` | 2 passed | 2 passed ✓ |
| 1/4d | `band_table or ceiling or flag_is_not` | 3 passed | 3 passed ✓ |
| 1/4e | `tag_table` | 2 passed | 2 passed ✓ |
| 6/3a | `mode_entry` | 1 passed | 1 passed ✓ |
| 6/3b | `question_log or country_rule or twelve_month` | 3 passed | 3 passed ✓ |
| 6/3c | `transcript_example or assessment_example or pack_split` | 3 passed | 3 passed ✓ |
| 6/3d | `answer_bank or walkback` | 2 passed | 2 passed ✓ |
| 8/5 | whole dry-run file | 10 passed, 0 skipped | 10 passed ✓ |

- **Red phases:** Task 4 Step 2 → 23 failed / 9 passed; Task 5 Step 2 → 11 failed (incl. `test_a_probe_collapse_demands_the_walkback_section`); Task 8 Step 2 → `FileNotFoundError` on the fixture dir.
- **Definition of done CLI**, run for real: without Plan 2 → exit **2**, stderr `scripts/lint_no_prediction.py (Plan 2) is not importable`. With a Plan-2 stub carrying the `quote=` exemption → exit **1**, first line `WALKBACK_MISSING: OVER-CLAIM, PROBE-COLLAPSE fired…`. Both branches are exactly as the plan documents them.
- Row counts behind defect 3's guard: Market shapes **29** (≥25), Role-family **8** (≥8).

## 2. Old defects

| # | Defect | Status | Evidence |
|---|---|---|---|
| 1 | `PROMOTED` term not a substring of the quote | **FIXED** | L3064 `- term: PACS`; inverse test L3184 `test_a_promotion_row_whose_term_is_not_in_the_quote_does_not_resolve_it`; both pass |
| 2 | ceiling assertion vs backticks | **FIXED** | L199 asserts `` "`held_under_probe` is the ceiling" `` |
| 3 | shape-row label test fails on every row | **FIXED** | `LABEL` = `[F\|C\|S\|U]` L151, `.strip("\`")` L223, `_shape_rows` drops `Source` L215, vacuity guard L229; 29/8 rows measured |
| 4 | `"may set SHAPE"` absent from the doc | **FIXED** | L246-247 assert the doc's real sentences; §10 `[S]`/`[U]` bar added L236-243 |
| 5 | 10 of 18 `REQUIRED` phrases lost to the hard wrap | **FIXED** | `_normalised()` L4047, comparison L4073; 3 case mismatches corrected in the list not the prose |
| 6 | `"one round per dispatch"` case | **FIXED** | L3483 `"One round per dispatch"` |
| 7 | ambiguous indentation, no reading works | **FIXED** | one rule L11-24; **64/64 blocks pass a strict 4-space dedent**; all 4 parse checks print the stated values |
| 8 | Task 8 has no real red phase | **FIXED** | reordered: test → red → fixture → fix files → green |
| 9 | DoD exits 2, not 1 | **FIXED** | L4765-4770 restates both branches; verified empirically |
| 10 | renamed Plan-2 fn crashes | **FIXED** | `getattr(..., "scan_text", None)` L2318 + `test_a_renamed_scan_function_is_exit_2_not_a_traceback` L2759 |
| 11 | 7 finding codes untested | **FIXED** | firing tests at L1966 / L1996 / L2621 / L2607+2615 / L2681 / L3206 / L2010, plus the `cannot_simulate` quiet guard L2018 |
| 12 | `UNKNOWN_REF` self-disables silently | **FIXED** | `NO_QUESTION_HEADINGS` emitted once L2269-2277; firing L1911 + quiet L1920; mode file §3 states the rule L3749-3752 |
| 13 | journal write failure reports success | **FIXED** | `ReceiptFailed` L2094, raised L2337, → exit 2 L2437; tests L1746 (no-workspace exception) and L1758 |
| 14 | `paths.py` bypassed | **FIXED** | `paths.answer_bank_of` L2353; Task 3 Steps 1b-1d add it with red/green; 3 tests |
| 15 | step granularity | **FIXED** | Task 1 Step 4 → 4a-4f, Task 6 Step 3 → 3a-3e, every `-k` count verified above |

15/15 fixed, 0 rejected. The one defect the fixer says it found itself (`_AB_SOURCE` `\s` → `[ \t]`) is real and correctly fixed — L2906-2910 carries both the regex and the rationale, and `test_an_empty_source_line_fails` passes.

## 3. New defects

### N1 (blocking) — `enter_mode.mode_file` does not exist. Plan 1 says so in those words.

`check_mock.py` L2122 (Task 3 Step 4) and the Consumes list at L1324:

```python
mode_path = enter_mode.mode_file(skill_root, MODE)
```

Plan 1, `2026-08-09-1-migration-and-p0-fixes.md:4689`, under `enter_mode`'s **Produces**:

> There is no `enter_mode.mode_file`: the mode-file path comes from `paths.mode_file(mode, root)`, so `enter_mode` and `check_apply` cannot disagree about where a mode file lives.

Plan 1's signature is `paths.mode_file(mode: str, root=None)` — **mode first**, root second — so Plan 4 has both the wrong module and the arguments reversed. Plan 1's own `check_apply` mirror (`:5111-5112`) reads `paths.mode_file("apply", root)`.

Measured: with my stub matching Plan 1's real API, `check_mode_entry` raises `AttributeError: module 'enter_mode' has no attribute 'mode_file'` on **every** invocation — **98 failed, 71 passed**. Changing that one line to `paths.mode_file(MODE, skill_root)` restores **169 passed**. This is also an R4 violation (path resolution outside `paths.py`).

**Fix:** L2122 → `mode_path = paths.mode_file(MODE, skill_root)`. L1324 → drop `mode_file` from the `enter_mode` Consumes line and add `paths.mode_file(mode, root)` to the `paths.py` Consumes line (L1323). Introduced in this pass — `enter_mode` appears **zero** times in the pre-fix plan (`ac404fb`), so the whole R5 backstop is new and this shipped with it.

### N2 (blocking) — Task 9 Step 5 retracts a sentence that is not in `SKILL.md`, in the wrong table shape, and names the wrong test

Step 5 (L4722-4728) quotes the row it says Plan 1 wrote:

> "`apply` is live. `discover`, `assess` and `interview` are **not yet built in this repo** — say so and stop rather than improvising them."

That sentence lives in Plan 1's *change-summary* table (`plan 1:5640`), not in `SKILL.md`. The real Modes table Plan 1 writes verbatim (`plan 1:5675-5682`) is:

```
| Mode | Question it answers | Status |
|---|---|---|
| `apply` | how do I build and pressure-test the application | live — `modes/apply.md` |
| `interview` | how do I answer, and what did I get wrong | `interview` is not yet built in this repo |
```

Three consequences: there is no list to "remove `interview` from"; Plan 4's replacement row `| `interview` | live | `modes/interview.md` — … |` puts `live` under **Question it answers**; and "give it a live row of its own" appends a *second* `interview` row while the original's stale cell survives, so `test_a_mode_that_exists_is_not_still_described_as_not_yet_built` (`plan 1:5440-5453`) stays red and Step 5's "Expected: PASS" is false.

Compounding it, Step 1 (L4668) and Step 5 (L4734-4736) both name `test_every_mode_named_in_skill_md_has_a_file_or_is_marked_unbuilt` as the failing/passing test. That test `continue`s the moment `modes/<mode>.md` exists (`plan 1:5430-5437`), so it can never be the red one here. The R9 backstop is the *other* test, which the plan never names.

**Fix:** Step 5 → "Rewrite the third cell of the existing `interview` row of `SKILL.md`'s Modes table (`| Mode | Question it answers | Status |`) so it reads:

```markdown
| `interview` | how do I answer, and what did I get wrong | live — `modes/interview.md`, gated by `scripts/check_mock.py` |
```

Do not add a row; the row already exists." Replace the test name in Steps 1 and 5 with `test_a_mode_that_exists_is_not_still_described_as_not_yet_built`.

### N3 (medium) — Task 9's skip-set edit deletes Plan 3's entry

L4678-4681 says "Change the one line" to `{"journal.py", "paths.py", "rounds.py", "vocab.py", "mock_vocab.py", "mock_blocks.py"}`. Plan 3 Step 7 (`plan 3:4973-4975`) sets that same line to `{…, "opencli_meta.py"}`. If Plan 3 lands first — the natural order — Plan 4's literal replacement drops `opencli_meta.py` and `test_the_self_check_names_every_script` goes red on it. The step already defends the `vocab.py` case with a parenthetical but not this one.

**Fix:** make it additive — "**add** `mock_vocab.py` and `mock_blocks.py` to whatever the set already holds; if Plan 3 has landed it also contains `opencli_meta.py`, which stays."

### N4 (minor) — `_skill_root_default()` re-derives what `paths.py` owns

L2369-2370: `return pathlib.Path(__file__).resolve().parent.parent`. Plan 1 exports `paths.SKILL_ROOT` for exactly this (`plan 1:543, 665`), and its own `check_apply` uses it (`plan 1:5100`). R4 wants one place. **Fix:** `return paths.SKILL_ROOT` and delete the helper, or keep the helper as a one-line `return paths.SKILL_ROOT`.

### N5 (minor) — Task 3 says "change nothing existing", Step 1c changes something

L87 and L1316 promise `paths.py` is "additive only; nothing existing changes", while Step 1c (L1593) says "Replace the body of `answer_bank()`". Behaviour is identical (`profile_dir(name) / "answer-bank.md"` → `profile_dir(name) / ANSWER_BANK_NAME`), but the two statements contradict. **Fix:** L87/L1316 → "additive, plus a behaviour-preserving refactor of `answer_bank()` onto the new `ANSWER_BANK_NAME` constant."

### N6 (minor, pre-existing — also in `ac404fb:2219`, missed by audit-4)

Task 4 Step 2 (L2796) predicts `AttributeError: module 'check_mock' has no attribute 'check_question_log'`. No test in `test_check_mock_sources.py` touches that name; measured, the red phase is 23 assertion failures whose first is `test_a_missing_question_log_is_a_finding_not_an_exit_2` — which the parenthetical already names. **Fix:** drop the `AttributeError` clause and promote the parenthetical.

## 4. Everything else, clean

- **Placeholders:** zero hits for TBD/TODO/implement later/fill in details/handle edge cases/add validation/similar to Task N/"write tests for the above". Every step that needs code shows code.
- **Symbols:** every `check_mock.*`, `mock_blocks.*`, `mock_vocab.*`, `mock_fixtures.*` and `paths.*` name referenced by a test is defined in a Produces block. Cross-plan: `journal.append/receipt/sha256_file/read_receipts`, `enter_mode.latest_mode_entry/main` (incl. `--skill-root` and `"interview"` in `MODES`), `paths.profile_dir/workspace/answer_bank`, and Plan 2's `lint_no_prediction.scan_text(text, label)` with the `MOCK-*-V1` `quote=` exemption (`plan 2:938, 951`) all check out. **`enter_mode.mode_file` is the sole exception — N1.**
- **Git:** all 10 `git add` lines stage named paths; no `git add -A`, no `git add .`, no `git push`, no `-c user.`.
- **Contract:** R1 ✓ (`mock_vocab` re-exports, `MOCK_MARKET_KEYS`, `assert not hasattr(V, "MARKET_KEYS")`), R2 ✓ (`could_not_run` + the documented no-workspace exception + `RECEIPT_WRITE_FAILED`, all three tested), R3 ✓ (closed to pass/fail/could_not_run, stated at L36), R4 ✓ except N1/N4, R5 ✓ (§0 entry, mirrored findings, 1 quiet + 2 firing + dry-run + the `mode`-stamp backstop on Plan 1), R8 ✓ (Task 9 exists) except N3, R9 ✓ (retraction present) except N2, R11 ✓ (no `/private/tmp`; the only `/tmp` is `Path("/tmp/somewhere")` as a synthetic non-workspace argument), R15 ✓.

---

**Verdict: NEEDS-WORK** — the 15 audited defects are genuinely fixed and the suite runs green end to end, but the new R5 mode-entry backstop calls `enter_mode.mode_file`, a symbol Plan 1 explicitly declares does not exist (98/169 tests fail against Plan 1's real API; one line fixes it), and the new Task 9 Step 5 retracts a sentence that is not in `SKILL.md`, in a row shape that does not match, while naming a test that cannot fail. N1 and N2 are both small, mechanical edits.
