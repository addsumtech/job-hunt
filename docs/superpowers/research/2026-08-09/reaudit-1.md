# Re-audit — `2026-08-09-1-migration-and-p0-fixes.md`

## 1. Sandbox run

Sandbox: `/private/tmp/claude-501/-Users-donghanglyu/d1ca171b-6798-42dc-9582-87e4635be401/scratchpad/reverify-1/`. All 32 whole-module Python blocks extracted; the real `render_cv.py` / `render_letter.py` / `render_rirekisho.py` / `tests/fixtures/` copied from `~/.claude/skills/job-application`; Tasks 7, 8, 15 and 16's diffs applied to them by hand. Every extracted module `ast.parse`s clean.

| Module | Result | Plan says |
|---|---|---|
| `test_journal.py` | **9 passed** | 9 ✓ |
| `test_paths.py` | **13 passed** | 13 ✓ |
| `test_vocab.py` | **8 passed** | 8 ✓ |
| `test_check_skill_lossless.py` | **12 passed** | 12 ✓ |
| `test_render_cv.py` (after Tasks 7+8+15) | **90 passed** | 45→87→90 ✓ |
| `test_render_letter.py` (after Task 7) | **7 passed** | 5+2 ✓ |
| `test_render_rirekisho.py` (after Task 16) | **27 passed** | — |
| `test_check_personal_data.py` | **7 passed** | 7 ✓ |
| `test_parse_verdicts.py` | **12 passed** | 12 ✓ |
| `test_check_render_freshness.py` | **8 passed** | 8 ✓ |
| `test_check_claims.py` | **11 passed** | 11 ✓ |
| `test_lint_cv.py` | **9 passed** | 9 ✓ |
| `test_check_letter.py` | **13 passed** | 13 ✓ |
| `test_check_pages.py` | **9 passed** | 9 ✓ |
| `test_check_word_limits.py` | **10 passed** | 10 ✓ |
| `test_check_apply.py` | **19 passed** | 19 ✓ |
| **total** | **264 passed, 0 failed** | — |
| `test_skill_structure.py` | not runnable (needs Task 20's `SKILL.md`); **collects 34+15 = 49** | 49 ✓ |
| `test_readme.py` / `test_ci.py` / `test_install.py` | not runnable (need Tasks 21–23 artifacts); **4 / 4 / 3** cases | 4 / 4 / 3 ✓ |

Task 7 Step 4's cumulative `100 passed` reproduces exactly: 51 baseline → 58 after the two appends, plus 9+13+8+12=42.

Live (not read, run):
- `check_skill_lossless` against the real tree, **both** the directory baseline and the git-ref baseline: `LOSSLESS: 1317/1317 baseline lines accounted for across 15 files` — Task 6 Step 5's string verbatim. Bad ref → stderr message, exit 2, no traceback.
- tectonic: `cv.pdf` = 19,820 bytes, **0** raw `/Type /Page`, inflated payload 29,003 bytes, `check_pages.page_count` → `1`. Task 17's measurement is exact.
- `render_letter.py --format pdf` now produces a 6,770-byte PDF through the shared `_engine_cmd` (Task 7 Step 5's claim holds end-to-end).
- `Makefile` recipe lines are real tabs; `make conventions` prints the guard line; `make lossless` exits 2 cleanly.
- `git status --short -- ':!docs'` prints nothing in `job-hunt` today.
- 34/34 `required_inline.json` anchors found verbatim in the baseline tree.
- `lint_cv.py` opener map on `CLEAN` = `{'built':[6], 'drove':[7,8], 'advised':[9], 'python':[12]}` — the test's own comment, measured.

Placeholder scan: **zero** hits for TBD/TODO/"implement later"/"add validation"/"handle edge cases"/"similar to Task N"/"as needed"/"if relevant". Git rules: **clean** (only the constraint line at L39 matches). No `/private/tmp` or scratchpad reference anywhere.

Contract compliance: `vocab.py` matches R1 byte-for-byte and `test_vocab.py` fails any script that re-spells a closed set; receipt verdicts across all scripts are exactly `pass|fail|could_not_run|recorded` (10/9/9/2 occurrences, no `error`/`reported`/`produced`); all eight workspace gates write a `could_not_run` receipt and have a test for it; `paths.py` is imported by everything that resolves a load-bearing path and no script uses `.parents[n]`; `CLAIM_KEYS` carries `retracted` with `PRESENCE_ONLY_KEYS`; `enter_mode` is step 1 of `modes/apply.md`; R8/R9 tests are present and correct; R10's six previously-unassigned items are all owned.

## 2. Old defects

| # | Status | Evidence |
|---|---|---|
| 1 `build_corpus`/`baseline_docs` include `docs/` | **FIXED** | one shared `in_corpus()`; live run 1317/1317 across 15 files from *both* baselines |
| 2 letter fixture 210 words | **FIXED** | 4 paragraphs, 277 words; `test_a_well_formed_letter_passes_silently` passes |
| 3 免許・資格 cry-wolf | **FIXED** | `_cert_ym` searching parser; 27/27 rirekisho tests pass incl. the four "carries its year anywhere" and three "not a year" cases |
| 4 `check_skill_lossless` gate-contract violation | **FIXED** | named exception in Global Constraints L19 + docstring + own CI line in the self-check; `BaselineUnavailable` → stderr, exit 2 (run) |
| 5 keep-vs-replace + 57/58 | **FIXED** | L1434 "**unchanged** … append"; 58 and 100 both measured correct |
| 6 `Led` never tracked | **FIXED** | fixture uses `Drove`; measured openers include `'drove': [7, 8]` |
| 7 Task 9 nested fence | **FIXED** | block now `````python` … ````` (L2071–2247); all 107 fences balance |
| 8 `parse_verdicts` not required | **FIXED** | in `REQUIRED_GATES` + `test_a_hand_written_round_file_without_a_parse_verdicts_receipt_fails` |
| 9 warning in a generator / two insertion points | **FIXED** | three entry points, `_MARKET_WARNED` guard, `reset_market_warnings()`; warn-once and reset tests pass |
| 10 Task 4 count | **FIXED** | 13 collected, breakdown at L731 correct |
| 11 §6 coverage undeclared | **FIXED** | L6332 |
| 12 P0 mislabelled + 2 scripts missing | **FIXED** | L6333 |
| 13 frontmatter under-specified | **FIXED** (but see NEW-1) | description written verbatim L5650–5668 + `test_the_description_names_all_four_modes` |
| 14 `PARA_MAX = 5` | **FIXED** | `PARA_MIN, PARA_MAX = 3, 4` |
| 15 Task 18 `git status` | **REJECTED-WITH-GOOD-REASON** | `docs/` is tracked at `ac404fb`; replaced with `git status --short -- ':!docs'`, verified to print nothing |
| 16 `enter_mode` exit-2 silent | **FIXED** | `mode_entry_failed` record + `test_a_failed_mode_entry_leaves_a_trace_in_the_journal` |

## 3. New defects

**NEW-1 (blocking) — L5866–5867: Task 20 Step 8 cannot exit 0, and its recovery instruction is wrong for the lines that will fail.**
Measured against the live baseline: **10 substantive `SKILL.md` lines are covered by neither Step 5's move ranges nor Step 6's inventory**, and one more is at risk.
- `SKILL.md:4–9` — the six description lines. The fix for old-defect 13 made the description *new prose*, so those six lines (76–81 normalized chars each) exist nowhere in the new tree. Lines 10–12 do survive inside the new description; 4–9 do not.
- `SKILL.md:16` (`# Job Application Orchestrator`, 28 chars), `:18` (the "experienced career coach and recruiter" paragraph), `:24` ("**The review loop is non-negotiable.** … each a fresh subagent — must all decide the package passes."), `:26` ("**Read references as you go.** … do not work from memory or assumption."). None is in `152–195` or any other cited range.
- `SKILL.md:20` (`## The load-bearing rule — read first`, 32 chars) survives only if the implementer reuses the exact heading; the inventory cites only `:22`.

L5867 says "If a line is reported lost, it was condensed rather than moved — **put it back**", which for 4–9 means restoring the one-mode description this pass deliberately replaced. Worse, Task 21 Step 6 (L6039) then reads *"If any line from `SKILL.md` … appears, **stop**: Task 20 lost content and no waiver is appropriate"* — so an obedient executor halts at Task 21.
**Fix:** (a) add inventory rows for `SKILL.md:18`, `:24`, `:26` and state the new H1/heading text explicitly; (b) insert a Step 8a that waives exactly the six description-line hashes with the shape of Task 21 Step 6 and its own reason ("the frontmatter description is new trigger text covering four modes; the baseline description named one mode and no skill name"); (c) reword L5867 so "put it back" applies to body rules only.

**NEW-2 (blocking) — L6039 / L6060 / L6068 / L6307: Task 21's waiver count is 12, not 9, and one reason is attached to three lines it does not describe.**
Measured on the live README with `check_skill_lossless.normalize`: the nine Skill-flow lines (35, 37–44) are joined by three more deletions at or above the 25-char floor —
- `README.md:83` `│   ├── cv/template.tex … # LaTeX CV template` → 33 chars (deleted by Step 4),
- `README.md:84` `│   └── letter/template.tex … # LaTeX letter template` → 41 chars (Step 4),
- `README.md:104` `Expected: 41 tests, all passing.` → 29 chars (Step 5).

The Step 6 regex `^- \*\*(README\.md):\d+\*\*` waives all twelve, so the script prints `waived 12 README lines` and Step 7/Task 23 Step 6 print `12 waived` — three "Expected" strings are wrong. More importantly the single `REASON` then records the two Layout lines and the test-count line as *"README's duplicated 8-step pipeline list"*, which is false, defeating the "a decision someone made rather than a casualty" property the allowlist exists for.
**Fix:** change all four expectations to 12, and split `REASON` into three by line number: the nine pipeline lines; the two Layout lines ("names a `.tex` template deleted in Task 2"); the test-count line ("a count nothing updates — replaced by `make check`").

**NEW-3 (moderate) — L5619–5627: the posting-field prose is inserted *inside* the Task 20 inventory table, breaking it.**
The table starts at L5603; L5618 is blank and L5619–5627 is prose; L5628 (`| Structured applications | … |`) through L5646 then render as loose text, not table rows, in every markdown viewer. Nineteen inventory rows — including **Gates** and **Self-check** — sit in that broken tail.
**Fix:** move the twelve-name block and its paragraph to after L5646 (or directly above the frontmatter block at L5648).

**NEW-4 (moderate) — L5989: Task 21 Step 4 is the only content change in the plan not written out.**
"Replace the `## Layout` code block's contents with the real tree" gives constraints, not text, while `test_the_layout_matches_the_repo` (L5946–5948) pins four script names and NEW-2's arithmetic depends on exactly which layout lines change. Every other edit in this plan is verbatim.
**Fix:** write the replacement tree literally, including `modes/apply.md`, `Makefile`, `.github/workflows/checks.yml` and each new script.

**NEW-5 (minor) — the refusal label is spelled two ways.** `vocab.VERDICT_ZH[REFUSAL] == "证据不足—不出结论"` (per R1, in the Task 5 block) versus `证据不足 — 不出结论` at L5710 (SKILL.md advice block) and L5532 (`modes/apply.md` entry conditions), with the spaced form hard-typed into `test_skill_md_carries_the_apply_verdict_block_and_its_disclaimer` (L5462). Two spellings of one closed-vocabulary label is exactly the drift `vocab.py` exists to prevent, and nothing compares the prose to the module.
**Fix:** keep R1's unspaced form everywhere and change L5462's literal to `assert vocab.VERDICT_ZH[vocab.REFUSAL] in text`.

**NEW-6 (minor) — L6296: the smoke test creates the workspace it says does not exist.** Verified: `python3 scripts/lint_cv.py --workspace /tmp/jh-smoke-does-not-exist` exits 2 with the promised message *and* leaves `/tmp/jh-smoke-does-not-exist/journal.jsonl` behind, because `journal.append` mkdirs. Every gate except `check_apply` behaves this way, so a typo'd `--workspace` silently materialises a workspace — the harm `paths.py`'s own docstring names ("a helper that created directories would materialise an empty workspace on a typo, and the resume lookup would then find a shell") and the one `check_apply`'s docstring is written to avoid.
**Fix:** either give every gate the `if not ws.is_dir(): print…; return 2` guard `check_apply` already has (matching R2's plain reading), or state in Global Constraints that only `check_apply` declines to create the workspace, and point Step 5's smoke test at a directory it creates and removes.

**NEW-7 (minor) — L1539 and the docstring at L1624–1627 justify the once-per-profile guard with "a `--format all` run", but `render_cv.main` has `--format choices=["md","docx","pdf"]`** — there is no `all`, and one invocation renders one format. The guard is still correct (three entry points), but a reader who checks the rationale will find it does not exist.
**Fix:** say "an md + docx + pdf run — three invocations, or three direct calls from one process".

---

**VERDICT: NEEDS-WORK** — NEW-1 and NEW-2 each make a step's stated expectation unreachable, and NEW-1 trips Task 21 Step 6's own "stop" instruction; NEW-3 and NEW-4 are cheap and mechanical. Everything the earlier audit raised is genuinely fixed, and every executable claim in the plan that I could run reproduces exactly.
