# Plan Audit — `2026-08-09-1-migration-and-p0-fixes.md`

Verified against the live tree: `job-application` is at `141bef6` with exactly the 21 dirty paths the plan lists; `python3 -m pytest tests -q` → **51 passed**; all 34 `required_inline.json` anchors exist **verbatim** in their named source files; every cited line range (`render_cv.py:118-121/324-327/346-360/992-996`, `render_letter.py:100-105`, and all 14 reference ranges in Task 17 Step 6) is accurate; `assets/{cv,letter}/template.tex` exist and `grep -rn template scripts/*.py` returns exactly the two prose strings the plan predicts. Placeholder scan: **zero** occurrences of TBD/TODO/"implement later"/"add validation"/"similar to Task N". Git rules: **clean** (the only match for `git add -A|git add \.|git push|-c user\.` is the constraint line itself, L34). Every task carries the full write-test → **run-and-see-it-fail** → implement → run-and-see-it-pass → commit cycle.

The defects below are real, and several are the exact failure class the plan writes rules against.

## DEFECTS

1. **L875 + L938 — `build_corpus` includes `docs/`, so the migration's headline safeguard is inert.**
   `CORPUS_DIRS = (".", "modes", "references", "agents", "assets")` combined with `files.extend(sorted(f for f in d.rglob("*") ...))`. With `sub == "."`, `d = skill_dir` and `rglob` is recursive. Simulated: corpus for a tree containing `SKILL.md` + `docs/superpowers/specs/design.md` returns **both files**. This breaks `test_docs_are_not_part_of_the_corpus` (L802–808, asserts `== 1`, gets `0`) and its own docstring at L873–874 (*"`docs/` is deliberately out: a line that survives only in the design doc has not survived"*). Worse in production: Task 5 Step 5 and Task 17 Step 8 run against the repo root, where `docs/superpowers/plans/2026-08-09-1-migration-and-p0-fixes.md` quotes SKILL.md verbatim — a condensed SKILL.md would still report `LOSSLESS` because the plan file is in the corpus.
   **Fix:** in `build_corpus`, use `skill_dir.glob("*")` (non-recursive) for the `"."` entry, or filter `if "docs" not in f.relative_to(skill_dir).parts`. `baseline_docs`'s directory branch (L909–918) has the identical bug — apply the same filter there.

2. **L3019–3035 + L3184 — the "well-formed letter" fixture is 210 words against the gate's own 250 floor, so the quiet-case tests fail.**
   `PARA` is 67 words (measured); the default body is `[PARA + "I am applying…" (76), PARA (67), PARA (67)]` = **210**, and `WORD_MIN, WORD_MAX = 250, 400`. `findings_for` emits `WORD_COUNT`, so `test_a_well_formed_letter_passes_silently` (L3052, asserts `== 0` and empty stdout) and `test_a_shorter_but_matching_company_name_is_accepted` (L3113) both fail. This is precisely the cry-wolf failure L35 forbids.
   **Fix:** make the default body four paragraphs — `[PARA + "I am applying for the Senior Reconstruction Engineer role.", PARA, PARA, PARA]` = 277 words, 4 paragraphs, inside both bands.

3. **L3520 + L3409/3419/3437/3483 — the 免許・資格 date warning fires on every ordinary certification, and three tests assert it doesn't.**
   `licenses_rows` is told to use `_checked_ym(cert, …, problems)`. The real `_ym` is `re.match(r"\s*(\d{4})…")` — **anchored** — so any cert not *starting* with a year yields `('','')` and a warning. The existing `jp_profile` fixture's `certifications: ["基本情報技術者試験 合格"]` triggers it. Therefore `test_accepted_date_formats_produce_no_problem` (×4 params, L3419 `assert fatal == [] and warnings == []`), `test_a_current_role_needs_no_end_date` (L3438) and `test_a_fully_dated_profile_writes_and_is_silent` (L3483 `assert "WARNING" not in err`) all fail. Every realistic Japanese cert string (`"基本情報技術者試験 合格 (2021)"`) also fails to parse, so the warning is a guaranteed cry-wolf.
   **Fix:** gate the licenses check on the string actually containing a date — only call `_checked_ym` when `re.search(r"\d{4}", str(cert))` — and change those three tests to assert `fatal == []` only.

4. **L4358 + L4397 vs L16–20 — `check_skill_lossless.py` is listed as a gate but violates the gate contract in three ways.**
   The gate table (L4358) and the self-check block "Ran, **with a receipt in `journal.jsonl`**" (L4397) both name `scripts/check_skill_lossless.py`, but the implementation (L958–1031) takes no `--workspace`, never imports `journal`, and writes no receipt — so the checklist promises evidence that can never exist, the "nothing reports a skipped gate" doctrine is broken at exactly the file that enforces it, and `test_the_self_check_names_every_script` (L4188) locks the false claim in. Additionally L922 `sys.exit(f"cannot read baseline {spec!r}: …")` exits **1**, not the contract's **2** for "could not run".
   **Fix:** either (a) exempt it explicitly in Global Constraints as a repo-level CI check, move it out of the "Ran, with a receipt" block into its own "CI" line, and change L922 to print to stderr and `return 2`; or (b) give it `--workspace` + `journal.receipt` like every other gate.

5. **L1119 + L1184 — contradictory instruction and wrong arithmetic in Task 6.**
   *"Replace `test_letter_pdf_degrades_without_engine` in `scripts/tests/test_render_letter.py` — keep it, and add the regression the suite was missing"* — replace or keep? And Step 4 expects *"`51 passed` plus the 6 new tests (`57 passed`)"*, but Step 1 adds **5** tests to `test_render_cv.py` and **2** to `test_render_letter.py` = 7 → **58**.
   **Fix:** say "Keep `test_letter_pdf_degrades_without_engine` unchanged and append the two tests below", and correct the expectation to `58 passed`.

6. **L2806–2809 — the `REPEATED_VERB` quiet case passes for the wrong reason and pins nothing.**
   `test_two_bullets_opening_with_the_same_verb_is_not_flagged` relies on the two `- Led …` bullets. But `if first and len(first.group(0)) >= 4` (L2938) excludes `"Led"` (3 chars). Executed the real `findings_for` against `CLEAN`: the openers map is `{'built': [6], 'advised': [9], 'python': [12]}` — `led` is never tracked, so the threshold of 3 is never exercised. Under the plan's own discipline (L35) this is a test that proves the button exists, not that it works.
   **Fix:** change the two bullets to a ≥4-char verb (e.g. `- Drove the migration of 40 clinical protocols…` / `- Drove a two-person team through…`) so the fixture genuinely holds two bullets at the same tracked opener.

7. **L1701 / L1713 / L1723 — the Task 9 code block is broken by nested fences.**
   The block opens ` ```python ` at L1701; `ATS_PASS` embeds bare ` ``` ` at L1713 and L1723 at the same indent, which closes the fence. Everything from L1714 onward renders as prose, not code. Task 17 Step 5 already uses ` ````markdown ` for exactly this reason (L4254).
   **Fix:** open and close the Task 9 block with four backticks.

8. **L3895–3896 — `check_apply` does not require a `parse_verdicts` receipt, contradicting the rule it is enforcing.**
   `REQUIRED_GATES = ("check_personal_data", "check_claims", "check_render_freshness", "lint_cv")`. But the new SKILL.md rule at L4360 is *"No mode may claim success while `journal.jsonl` lacks a receipt for its gates"*, and the self-check lists `scripts/parse_verdicts.py` (L4393). As written, a hand-written `judge-round-1.json` containing `combined_verdict: PASS` passes `check_apply` with no evidence the parser ever ran — the exact substitution the gate exists to prevent.
   **Fix:** add `"parse_verdicts"` to `REQUIRED_GATES`, have `_good_workspace` (L3604) write that receipt, and add a test that deleting it yields `MISSING_RECEIPT: parse_verdicts`.

9. **L1221 vs L1450–1456 — two named insertion points for the unknown-market warning, only one shown; and it lands inside a generator.**
   Files says *"add the warning in `personal_items` / `photo_path`"*; Step 3 patches only `personal_items`. Verified in source: `personal_items` is a **generator** (`yield` at `render_cv.py:379`), so `_warn_unknown_market` fires on iteration, and it is consumed at three sites (`render_cv.py:462`, `:607`, `:873`) — a md+docx+pdf run prints the identical warning three times, which is how a warning gets trained away.
   **Fix:** name one insertion point. Put `_warn_unknown_market` in a non-generator entry (e.g. first line of `render_markdown`, `render_docx` and `build_latex`) with a module-level `_warned` guard keyed on `id(profile)` or the market string, and delete the `personal_items` mention from the Files block.

10. **L653 — wrong expected count for Task 4.** `Expected: PASS — 12 passed`. The file defines 1 + 5 (parametrized `test_slugify`) + 5 = **11** test cases.
    **Fix:** `11 passed`.

11. **Spec §6 coverage — six layer-1 bullets have no task and are not declared as deferred.**
    Spec §6 (L302, L303, L304, L305, L306, L317, L318) requires in SKILL.md: 只读保证 + `access: read` allow-list + the four search/detail command pairs + `--window background` / `-f json` / exit-code-before-stdout / the indeed empty-`title` defect; 平台限制停止规则; 禁用输出词表 + the employer-published-scale exception; 反教唆四条规则 + 绊线; 模拟面试会话机制; and 接地契约摘要 (the §8 three-mechanism diagram). None appear in Task 17 Step 6's inventory (L4315–4345), and "Not in this plan" (L4536–4543) never mentions them — so a reader finishes this plan believing SKILL.md is §6-complete.
    **Fix:** add a bullet to "Not in this plan": "Six §6 layer-1 items that belong to the unbuilt modes — the read-only guarantee and opencli command surface, the platform-limit stop rule, the banned-vocabulary list, the four anti-coaching rules, the mock-session mechanics, and the §8 grounding-contract summary — land with their modes."

12. **L4542 — "Not in this plan" mislabels six **P0** checks as "P1/P2", and omits two scripts entirely.**
    *"The remaining P1/P2 checks named in the spec: consistency.py, check_mock.py, check_shortlist.py, check_conventions.py, check_evidence_refs.py, lint_no_prediction.py, check_no_write.py, check_opencli_result.py, count_coverage.py, check_pages.py, check_word_limits.py."* Spec §7 lists `check_shortlist.py`, `check_conventions.py`, `check_evidence_refs.py`, `lint_no_prediction.py`, `check_no_write.py` and `check_opencli_result.py` under **P0** — in a plan titled "migration and P0 fixes" this understates what ships. Also absent from the list: `evidence_blocks.py` (spec 5.2 step 5) and `check_assessment.py` (spec 5.2 gates).
    **Fix:** relabel as "the remaining P0 checks that belong to the unbuilt discover/assess modes, plus the P1/P2 checks", and add `evidence_blocks.py` and `check_assessment.py`.

13. **L4317 — the frontmatter instruction is under-specified and, followed literally, ships a wrong description.**
    *"`name: job-hunt`; description carried from the baseline with the name changed"*. The baseline description (verified, `SKILL.md:3-13`) contains no skill name — it describes applying to one job. Carried "with the name changed" it would never mention discover/assess/interview, and `test_the_frontmatter_name_matches_the_skill_directory` (L4221) only checks `name:`, so nothing reports it.
    **Fix:** write the intended `description:` verbatim in the plan (it is new prose, not a move), and add an assertion that the description names the four modes and marks three as not yet built.

14. **L3185 — `check_letter.PARA_MAX = 5` contradicts the rule it enforces.** `references/motivation-letter.md:121` reads *"3–4 paragraphs total. Never a single monolithic block. Never more than 4 unless a specific structure requires it (rare)."* The gate silently permits 5.
    **Fix:** `PARA_MIN, PARA_MAX = 3, 4`, and update `test_paragraph_count_outside_three_to_five_is_caught`'s name and the message at L3221.

15. **L4520 — Task 18's `git status --short` expectation is wrong today.** `docs/superpowers/plans/` is currently **untracked** in `job-hunt` (verified), so status will show it alongside `test_install.py`.
    **Fix:** either commit the plans directory in Task 2 Step 6 (named path) or change the expectation to "only `scripts/tests/test_install.py` and `docs/superpowers/plans/` untracked".

16. **L3841–3843 — `enter_mode.py`'s exit-2 path writes nothing to the journal.** `if not path.exists(): print(...); return 2` — a failed mode entry leaves no trace at all, which is risk-register #12 in the one place the plan calls "the layer-1.5 backstop".
    **Fix:** `journal.append(ws, {"ts": …, "action": "mode_entry_failed", "mode": args.mode, "mode_file": …})` before returning 2, and assert it in a test.

**Verdict: NEEDS-WORK** — defects 1–4 each break a test or silently disable a gate the plan is built around; 5–16 are correctness and coverage fixes that are cheap to apply.
