# Plan audit — `2026-08-09-2-assess-mode.md`

**Method:** extracted all 16 code blocks verbatim from the plan into a sandbox, added Plan 1's `journal.py`, and ran every test suite. **All 8 suites pass as written** (`12+11+15+20+13+24+20` = 115 tests green; `test_market_tables` needs the tables). Placeholder scan is clean — no `TBD`/`TODO`/`similar to Task N`/"handle edge cases". Git-rule scan is clean — no `git add -A`, no `git add .`, no `git push`, no `-c user.email`. Every symbol referenced in a test is defined in some Produces block.

The defects below are things the passing tests **don't** catch. Seven are reproduced, not inferred.

---

## DEFECTS

**1. (CRITICAL, reproduced) The 30/60/90 table that `modes/assess.md` mandates fails the assess gate.**
Line 3217: `**(b) A 30/60/90 table** with exactly these columns:`. Line 999: `_SCORE = re.compile(r"\b\d+\s*/\s*\d+\b")`. `check_assessment` runs `prediction.scan_text` over `fit-assessment.md` and treats the result as a hard finding. Reproduced end-to-end on a `likely_screen_out` fixture:
```
SCORE_PATTERN: fit-assessment.md:31: '30/60' in '## 30/60/90 计划'
main exit: 1
```
The gate fires on exactly the two verdicts (`大概率被筛掉`/`硬性阻断`) where §10 makes the table compulsory — and the plan already knows the table renders there (line 474 mentions "the 30/60/90 table's prose cells"). No test in `test_lint_no_prediction.py` covers it. **Fix:** mask the roadmap-horizon token in `mask_exempt_spans` (`re.compile(r"\b30\s*/\s*60\s*/\s*90\b")`, same length-preserving substitution as the URL mask), and add both halves to the tests: `assert lint.scan_text("## 30/60/90 计划", "x") == []` and keep `test_a_slash_score_fires` proving `8/11` still fires.

**2. (HIGH, reproduced) An expired `review_by` fails the assess gate at runtime — the spec forbids exactly this.**
Spec §7 P0: 「`review_by` 已过期 → CI 失败，**运行时改为在卡片上打「已过复核期」横幅而不拒绝渲染**」. The plan's own README (2027–2029) and `modes/assess.md` §9 (3192–3193) repeat it. But line 3748 is `findings += conventions.check_file(table, today)`, so `EXPIRED_REVIEW_BY` becomes a hard finding of the assess gate, and line 3586 `test_a_broken_market_table_fails_the_assessment` **pins the wrong behaviour**. Reproduced: `main exit: 1`. A date passing with no code change stops the skill working. **Fix:** in `check_assessment.check`, re-prefix any `EXPIRED_REVIEW_BY` from `check_file` as `WARN_EXPIRED_REVIEW_BY`, and add a real check that the 「已过复核期」 banner appears in `fit-assessment.md` when a rendered entry is expired. Rewrite the test as two: expired table alone → gate passes; expired table with no banner → `MISSING_STALE_BANNER`.

**3. (HIGH, reproduced) `CONVENTION_PARAPHRASED` fires on a card rendered character-for-character.**
Lines 3756–3761 compare `str(entry[field]).strip() in markdown`. Real tables use YAML block scalars with hard line breaks (Task 7, lines 2606–2615), so the check demands the model reproduce the YAML's wrap points. Reproduced with a two-line `text_zh` reflowed to one line:
```
CONVENTION_PARAPHRASED: nl-recognised-sponsor-gate was listed as rendered but ne...
```
The test never catches it because the `MARKET` fixture (3344–3346) uses a single-line Python string. **Fix:** compare `re.sub(r"\s+", "", …)` on both sides (whitespace is not the claim), and change the fixture's `text_zh` to a multi-line string so the test would have failed.

**4. (HIGH, reproduced) `DISQUALIFIER_AFTER_VERDICT` fires on ordinary correct output.**
Lines 3732–3738 require the row's `text` — the posting's own words — to appear verbatim above the verdict line. `modes/assess.md` §4 only says "surface these before anything else and ask". Reproduced: a Chinese-language 硬性阻断项 section that names the barrier correctly but paraphrases it still fires. The quiet-case test (3484–3490) passes only because the fixture smuggles the English string into a Chinese sentence: `该岗位要求你已经持有欧盟工作许可（Kubernetes in production 另见下表）` (3406). This is precisely the "cries wolf on ordinary output" failure the plan's own line 50 forbids. **Fix:** key the check on a required `## 硬性阻断项` section that lists the row **ids** (`R2`), state that mechanical requirement in `modes/assess.md` §4, and add a quiet test whose disqualifier section is a genuine paraphrase.

**5. (HIGH) The layer-1.5 backstop Task 12 claims does not exist in any task.**
Line 3007: "It has two backstops at once: `check_assessment.py` requires artifact fields that only this file defines, and **`journal.jsonl` records its content hash**." Nothing in this plan records it. Plan 1 already built the mechanism (`scripts/enter_mode.py`, `enter_mode.latest_mode_entry`, and `check_apply`'s `NO_MODE_ENTRY` + stale-hash finding); `check_assessment` lists `journal.read_receipts` in Consumes (line 3302) and never calls it, and `modes/assess.md` §11's gate list omits `enter_mode.py` entirely. This is the exact silent-layering regression spec §4.2 exists to prevent. **Fix:** add `python3 scripts/enter_mode.py --workspace <ws> --mode assess` as step 0 of §11; mirror `check_apply`'s `NO_MODE_ENTRY` / stale-hash block into `check_assessment.check`; add a quiet test (entry present, hash matches → no finding) and two firing tests (no entry; hash stale).

**6. (MEDIUM) Task 12 says Task 13 enforces the "other half"; Task 13 enforces none of it.**
Lines 3004–3005 list as Produces "the closed strategy set `apply_anyway | … | change_track`" and "the 30/60/90 column names 目标 | 行动 | 验收标准 and the roadmap's 输出物 column", prefaced (3000) by "these are the definitions **Task 13 enforces** and nothing else supplies". `check_assessment.py` contains no check for exactly-one-strategy, for either column, or for the mirroring into `actions:`. Spec §5.2 step 10: 「`验收标准` 和 `输出物` 这两列就是全部价值所在」. **Fix:** add `MISSING_OTHER_HALF` (verdict in `likely_screen_out|blocked` ⇒ `fit-assessment.md` contains `验收标准` and `输出物`) and `STRATEGY_NOT_UNIQUE` (exactly one token from the closed set), with quiet+firing tests — or delete the claim from line 3000 and record the absent backstop honestly.

**7. (MEDIUM, reproduced) No gate writes a receipt on the exit-2 path.**
Line 25 of this plan: "Every gate appends **exactly one** receipt line to `<workspace>/journal.jsonl` **before exiting**." Plan 1's `journal.py` docstring: "on every exit path, including the 'could not run' one." All seven scripts `return 2` before `journal.receipt` (e.g. 414, 722–723, 1073, 1524, 1836, 2502, 3781–3783). Reproduced: `exit-2 rc: 2  journal exists: False`. "Could not run" is the case where silence most looks like a clean run — the risk the journal exists to close. **Fix:** call `journal.receipt(workspace, "<gate>", {}, "could_not_run", [f"NO_INPUT: {path}"])` before each `return 2`, and extend each `test_*_exits_two` to assert the receipt line exists with that verdict.

**8. (MEDIUM, reproduced against the research) `test_the_three_live_violations_the_reviewer_found_are_gone` makes a correct build impossible.**
Lines 2961–2967 grep the whole non-comment body of `cn.yaml` for `51job` and of `nl.yaml` for `2023/970`. Checked against `markets.json`: `cn-campus-track-is-cohort-gated-and-early.source_detail` cites *"the 51job.com homepage, fetched by curl on 2026-08-09"*, and `nl-weu-pay-range-not-pay-history.source_detail` carries the EUR-Lex title *"Directive (EU) 2023/970 of the European Parliament and of the Council of 10 May 2023…"*. Step 5 of every table task requires restructuring `source_detail` into `source:`. Every landing place loses: `publisher`/`note` → `DIGIT_IN_PROSE` (verified), `title`/`quote`/`url` → this test. The only escape is dropping the citation — the exact outcome the README's exemption paragraph (1992–1994) was written to prevent. **Fix:** scope the test to the prose fields, e.g. iterate `cck.load_market_file(...)["conventions"]` and assert the needle is absent from `text_en`/`text_zh`/`applies_when`/`why` only.

**9. (LOW, reproduced) Task 9 row 6 instructs an edit the lint hard-fails.**
Line 2771: "In `source`, name § 16 Abs. 2 **TV-L** for the BAG case and **state that** the BVA catalogue covers the **federal** agreement". `SOURCE_PROSE_FIELDS = ("publisher", "note")` are digit-scanned; reproduced `DIGIT_IN_PROSE: …source.note`. **Fix:** say explicitly that the § number goes in `source.title` or `source.quote` (both exempt), never in `note`.

**10. (MEDIUM) Tasks 7–12 have no "run it and watch it fail" step.**
Tasks 7/8/9/10 are Write-file → run lint → verify count → commit. Task 11 writes `us.yaml` **then** writes `test_market_tables.py`, so that regression never has a red phase. Task 12 writes `modes/assess.md` then greps it. **Fix:** move `scripts/tests/test_market_tables.py` to Task 6 Step 3½ (before any table exists) and run it red — it then goes green one table at a time across 7–11; in Task 12, run the Step-2 anchor script first and record the expected `AssertionError: 不是对结果的预判`.

**11. (LOW) Task 7 Step 1 is not a 2–5-minute step.** Lines 2576–2578: "Create `references/market-conventions/cn.yaml`. The first entry, written out in full, is the pattern for the other nine… Then add the remaining nine entries." Each entry is a splice from a 20k-character review with its own `source:` restructuring. **Fix:** one checkbox per disposition-table row, each ending in the `--market-file` lint run.

**12. (LOW) Task 6 Step 1 hard-depends on a session-scoped temp path.** Line 1906 hardcodes `/private/tmp/claude-501/…/d1ca171b-…/scratchpad`. I confirmed `markets.json` is present today and the copy script would run correctly (keys `market`/`review`/`entry.conventions` all match). But 5 of 13 tasks die if `/private/tmp` is reaped between planning and execution, and the plan's own guard says so. **Fix:** perform the copy and commit `docs/superpowers/research/2026-08-09-market-conventions/` now, before executing, and reduce Task 6 Step 1 to a verification.

**13. (LOW) A false statement about the code the plan itself shows.** Line 472: "`--check-only` … **that is what `check_assessment.py` calls**". It does not — lines 3664–3666 import `drop_unresolvable_refs` / `strip_block_ids` and run them on a deep copy. **Fix:** "…that is the form `check_assessment.py` reproduces in-process."

**14. (LOW, verified by running) Two wrong expected pass counts.** Line 444 "Expected: PASS (11 passed)" — `test_evidence_blocks.py` has 12 tests. Line 1100 "Expected: PASS (14 passed)" — `test_lint_no_prediction.py` has 15. **Fix:** 12 and 15.

**15. (LOW) `INVALID_KIND` is emitted, undocumented and untested.** Line 1797 emits it; the counting-rules prose (1575) names only `INVALID_MATCH`/`INVALID_RECENCY`, and no test covers a row with a bad `kind`. **Fix:** name it in the Task 5 rules and add `test_an_out_of_enum_kind_is_reported`.

**16. (LOW) Nothing asserts `<key>.yaml` declares `market: <key>`.** `check_file` only checks membership in `MARKET_KEYS`; `check_assessment` selects the table by filename, so a mis-declared `market:` is invisible — the "wrong market card reads exactly like a right one" failure. **Fix:** add to `test_market_tables.py`: `assert cck.load_market_file(ROOT / f"{key}.yaml")["market"] == key`.

**17. (LOW) One calibration threshold touches the distribution it claims to sit outside.** Line 1900: "the modal-marker delta runs −1 to +3. The thresholds below (… `|delta| >= 3`) **sit outside the body of the distribution**." I recomputed over all 40 source entries: ratio 0.258–0.424 and delta −1..+3 are **exactly right** (good), but `abs(delta) >= 3` fires on `nl-weu-language-requirement-must-be-justified`, a shipped entry. It is only a `WARN_`, so nothing breaks. **Fix:** `MODAL_DELTA` comparison to `> 3`, or note the known hit in `nl.yaml`'s `# NEXT REVIEW` block.

---

## VERDICT: NEEDS-WORK — defects 1–5 must be fixed before execution (three of them make the gate fail on output the plan's own mode file mandates; two contradict the spec).
