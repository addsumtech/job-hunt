## DEFECTS

I reconstructed every file the plan creates (de-denting the 4 spaces as instructed), stubbed `journal.py` to the shared contract, and ran the plan's own suite: **93 passed, 1 failed** across 8 modules. The findings below are what that run plus a close read turned up. **No placeholders were found** — no TBD/TODO/"implement later"/"similar to Task N"; every task shows complete file contents, every referenced symbol is defined in some task's Produces block, and there is no `git add -A`, `git add .`, `git push`, or `-c user.email` anywhere except the prohibition at line 31.

---

1. **Line 2553 / 2797–2798 — Task 5's test fails as written; "Expected: PASS (9 passed)" (line 2809) is actually `1 failed, 8 passed`.** The assertion
   > `assert "about to call an adapter other than the four" in text`

   is checked against a SKILL.md block whose trigger sentence is line-wrapped mid-phrase:
   > ```
   > **READ `references/discovery-sources.md` when you are in discover mode and about to
   > call an adapter other than the four in the table above** (upwork, nowcoder,
   > ```

   The substring does not exist — it is `about to\ncall an adapter…`. **Verified**: `test_skill_md_carries_the_discovery_trigger` fails with `AssertionError`. Fix: rewrap the SKILL.md block so the phrase survives on one line —
   `…when you are in discover mode and` / `about to call an adapter other than the four in the table above** (upwork,` / `nowcoder, 1point3acres, maimai, or any site added later).` The same sentence is wrapped differently again at lines 2576–2577 of `references/discovery-sources.md`; fix both so the evaluable trigger reads identically in the two places that carry it.

2. **Lines 3172–3179 — `test_the_no_fabrication_rule_is_restated_at_why_matched` is vacuous; spec §8's three-place fence loses its only backstop.**
   > `index = body.find("why_matched")` … `window = body[index:index + 2600]` … `assert "绝不" in window or "never" in window.lower()`

   `find` returns the **first** occurrence, which is Step 0's "Write how, per row, in `why_matched`." (line 3278), not the Step 6 definition. The 2600-char window is then satisfied by the unrelated "**Never pad the count.**" in the `brief.yaml` paragraph. **Verified**: deleting the entire Step-6 fence paragraph (`**\`why_matched\` is one of exactly three places…绝不 write a reason that the card does not support…**`) from `modes/discover.md` leaves the module at **14 passed**. Spec §8 requires this restatement in exactly three places and this test is the backstop for one of them. Fix: anchor on the definition, e.g. `index = body.index("**\`why_matched\` is one of exactly three places")` and additionally `assert "write a reason that the card does not support" in body`.

3. **Lines 611–612 vs 99 and 2731–2733 — risk-control signals are matched against the extracted `error.message`, not stderr, so the absolute stop rule can silently miss.** The code searches `message` (the output of `_error_message`, which returns only `error.message` when stderr parses as a YAML mapping), while both the data file and the catalogue state the rule as
   > `# matched ONLY against the stderr of an invocation that exited non-zero.`

   **Verified**: a failure whose YAML carries `message: 'boss request failed'` and `body: '请完成安全验证后重试'` classifies as `transport`, `signal_id: None` — the mode continues instead of stopping. Fix: search `f"{message}\n{stderr_text or ''}"` in the signal loop, and add a test whose signal string sits outside `error.message` (its quiet twin — the same string inside a job row on an exit-0 call — already exists at line 327).

4. **Spec §6 (spec line 303) has no task: the platform-limit stop rule never reaches layer 1.** Spec lists under "SKILL.md 里不能离开的内容（layer 1）": *平台限制停止规则（停、不重试、不改参数、不绕过、输出方向级降级、填披露表）*, with the reason *每平台的触发串是数据；这条教条不是*. The plan's marked block (lines 2780–2803) carries the command pairs, the exit-code rule, the write ban and the discovery-sources trigger — not the stop rule, which lives only in `modes/discover.md` (line 3380) and `references/source-policy.md`. Plan 1 rewrites SKILL.md from migrated `job-application` content, which contains no opencli material, so nothing else supplies it. Fix: add the six-clause rule to the marked block and pin it in `test_skill_md_states_the_exit_code_rule_and_the_write_ban` (line 2558), e.g. `assert "do not retry, do not change parameters and retry, do not route around it" in text`.

5. **Spec §5.1 "条数守恒" (count conservation) has no task.** `sources[].rows_returned`, `invocations` and `identity_field_empty_rows` are written into `shortlist.yaml` (lines 1415–1417, 3481–3483, 3817–3818) but `_check_sources` (line 2269) compares only site / command / classification / `raw_files` — even though the wrapper already journals `row_count` and `empty_identity_rows` for every call. Nothing bounds `len(rows)` by what was retrieved, and there is no duplicate-`source_id` check, so one raw row can legally become three shortlist rows. Fix: in `_check_sources` add `SOURCE_REPORT_COUNT_MISMATCH` (entry `rows_returned` vs the summed `row_count` of matching `adapter_call`s; `identity_field_empty_rows` vs `len(empty_identity_rows)`) and a `DUPLICATE_SOURCE_ID` finding in `check_rows`, plus a quiet test — the existing fixture already satisfies both.

6. **Line 3718 — Task 8 has no run-and-watch-it-fail step.**
   > `Expected: PASS immediately if Tasks 1-4 are complete.`

   Nothing proves the three subprocess assertions bind; a typo in `assert sum(...) == 3` or a wrong stream would be indistinguishable from a real pass. Fix: add a negative control before Step 3 — `mv scripts/check_shortlist.py scripts/check_shortlist.py.off`, run the module, confirm `test_the_whole_chain_passes_on_a_real_capture` fails on the subprocess return code, then restore. (Alternatively write and run the e2e module at the end of Task 3, when `check_run` does not yet exist.)

7. **Line 3902 — the Definition-of-done grep is false against the plan's own output.**
   > `…returns only the lines that *forbid* those commands — never one that instructs running them.`

   **Verified** against the reconstruction: it returns five source lines that neither forbid nor instruct — `scripts/tests/test_check_no_write.py` (`"command_line": "opencli boss greet --job-id abc --text 'hello'"`, `assert "opencli boss batchgreet" in …`, the `parse_command_line` edge case), `scripts/tests/test_check_opencli_result.py` (`assert "opencli 1point3acres login" in r["remedy"]`), and the `check_no_write.parse_command_line` docstring — plus `__pycache__` binaries. An executor taking the criterion literally either deletes load-bearing fixtures or waves the gate through. Fix: `grep -rn --exclude-dir=__pycache__ --exclude-dir=tests … SKILL.md modes references scripts` and reword to allow the parser docstring.

8. **Line 760 — wrong expected count.**
   > `Expected: PASS (17 passed)`

   The module defines 15 tests; **verified** `15 passed`. (All other counts are exact: 11 / 15 / 33 / 9 / 14.) Fix: `PASS (15 passed)`.

9. **Lines 77 and 89 — Task 1 Step 1 writes a file into a directory it creates afterwards.** Step 1 says "If it does not exist, create it with exactly this content" (`scripts/tests/conftest.py`), and only then
   > `Then: `mkdir -p scripts/tests references``

   Fix: move `mkdir -p scripts/tests references` to the first line of the step.

10. **Lines 2567 and 2935 — two "Expected: FAIL" descriptions are wrong in kind.**
    > `Expected: FAIL — every test errors with `FileNotFoundError: .../references/discovery-sources.md``

    `test_skill_md_carries_the_discovery_trigger` and `test_skill_md_states_the_exit_code_rule_and_the_write_ban` read `SKILL.md`, which Plan 1 has already created, so they fail with `AssertionError`. Likewise at 2935, `test_there_is_exactly_one_source_policy_file` fails `AssertionError: [] == ['source-policy.md']`. Fix: state both failure modes so a mixed red phase is not read as a broken bootstrap.

11. **Lines 2251–2253 — the partial-missing disclosure branch is unpinned.** The plan tests all-labels-missing (`DEGRADED_WITHOUT_DISCLOSURE`) and blank-answer (`DISCLOSURE_INCOMPLETE`), never some-present-some-missing, which is the branch that emits `DISCLOSURE_INCOMPLETE: the disclosure block is missing these lines: …`. **Verified** the branch works; it just has no test in either direction. Fix: add one test dropping two labels from `DISCLOSURE_OK` and asserting both names appear in the finding.

---

**Verdict: NEEDS-WORK** — #1 makes Task 5 red on execution, and #2–#5 each remove or weaken a backstop the spec explicitly requires; the rest are mechanical.
