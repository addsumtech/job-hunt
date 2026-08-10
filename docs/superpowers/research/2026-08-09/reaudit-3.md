## 1. Sandbox run results

Sandbox: `/private/tmp/claude-501/-Users-donghanglyu/d1ca171b-6798-42dc-9582-87e4635be401/scratchpad/reverify-3/`
All 20 whole-file blocks extracted (4-space de-dent, clean on every block) + all 22 patch blocks applied in task order. Plan 1 stubs written **verbatim from the current Plan 1 text**, not invented: `journal.py`, `paths.py`, `enter_mode.py`, plus `vocab.py` to R1 and a stand-in `test_skill_structure.py` (structural half, Plan 1's skip set + Task 10 Step 7's extension) and a Plan-1-shaped `SKILL.md`.

**As written — 47 failed, 76 passed** (Plan 3's own 10 modules):

| module | as written | with a one-line shim for defect N1 |
|---|---|---|
| `test_check_opencli_result.py` | **16 passed** | 16 passed |
| `test_check_no_write.py` | **12 passed** | 12 passed |
| `test_check_shortlist_rows.py` | **16 failed, 3 passed** | 19 passed |
| `test_check_shortlist_run.py` | **25 failed, 1 passed** | 26 passed |
| `test_check_shortlist_mode_entry.py` | **3 failed, 1 passed** | 4 passed |
| `test_discovery_docs.py` | **10 passed** | 10 passed |
| `test_source_policy.py` | **10 passed** | 10 passed |
| `test_discover_mode_doc.py` | **19 passed** | 19 passed |
| `test_discover_e2e.py` | **3 failed** | 3 passed |
| `test_discover_registration.py` | **4 passed** (after Task 10) | 4 passed |
| **total** | **47 failed / 76 passed** | **123 passed** |

Every failure has one cause: `AttributeError: module 'enter_mode' has no attribute 'mode_file'` (defect N1). With `mode_file` shimmed in, the plan's own numbers reproduce exactly — 16 / 12 / 19 / 26 / 4 / 10 / 10 / 19 / 3 / 4 = **123**.

## 2. Old defects

| # | Status | Evidence |
|---|---|---|
| 1 trigger sentence line-wrap | **FIXED** | phrase on one line in both files (`SKILL.md:95`, `discovery-sources.md:4`); `test_the_trigger_sentence_survives_line_wrapping_in_both_files` added and passes |
| 2 vacuous `why_matched` test | **FIXED** | re-anchored on `"**\`why_matched\` is one of exactly three places"`, window 700. Mutation-tested: deleting the fence paragraph → `1 failed, 18 passed` (old version stayed green) |
| 3 signals matched against `error.message` only | **FIXED** | `haystack = f"{message}\n{stderr_text or ''}"`. Reproduced: `body: '请完成安全验证后重试'` now → `platform_limit` / `security-verification-cn` (was `transport` / `None`) |
| 4 stop rule never reaches layer 1 | **FIXED** | six numbered clauses in the marked block; six asserts in the renamed test |
| 5 条数守恒 has no task | **FIXED** | 4 one-directional `SOURCE_REPORT_COUNT_MISMATCH` checks + `DUPLICATE_SOURCE_ID`. Mutation-tested: removing the block → exactly the 4 new tests fail |
| 6 Task 8 (now 9) had no negative control | **FIXED** | Step 2 reproduced verbatim: `mv …check_shortlist.py.off` → all 3 e2e tests fail with `can't open file … check_shortlist.py`, exactly as the plan states |
| 7 DoD grep false against own output | **FIXED** | grep run against the reconstruction: **exactly 2 lines**, both named and explained in the DoD text |
| 8 `17 passed` | **FIXED** | measured 16 |
| 9 `mkdir -p` after the write | **FIXED** | line 82 is now the first line of Step 1 |
| 10 two "Expected: FAIL" wrong in kind | **FIXED** | Task 5 Step 2 reproduced exactly (7 × `FileNotFoundError` + 3 × `AssertionError`); Task 6 Step 2 now two-shaped (but see N5) |
| 11 partial-disclosure branch unpinned | **FIXED** | `test_a_partially_missing_disclosure_block_names_the_missing_lines` drops two labels, asserts `DISCLOSURE_INCOMPLETE` present, `DEGRADED_WITHOUT_DISCLOSURE` absent, both names printed |

11/11 fixed, 0 rejected. Cross-check items R1, R2, R3, R5, R8, R12, R13, R14 verified in code; no `git add -A` / `git add .` / `git push` / `-c user.`; no `/private/tmp` or scratchpad reference; placeholder scan clean (no TBD/TODO/"similar to Task N"/undefined symbol).

## 3. NEW defects

### N1 — BLOCKING. `enter_mode.mode_file` does not exist; the argument order is also reversed
**Plan lines 4232 and 4399.** `_check_mode_entry` calls `enter_mode.mode_file(skill_root, MODE)`, and the Interfaces block declares `enter_mode.mode_file(skill_root, mode)` as coming from Plan 1. Plan 1 line 4689 says the opposite in so many words:

> There is no `enter_mode.mode_file`: the mode-file path comes from `paths.mode_file(mode, root)`, so `enter_mode` and `check_apply` cannot disagree about where a mode file lives.

Plan 1's real signature is `paths.mode_file(mode: str, root=None)` — **mode first, root second**. Introduced by the new Task 8. Effect: `AttributeError` on every `check_shortlist.main()` call → 47 of 123 tests red, and Task 9 Step 7's live `check_shortlist` exits on a traceback instead of 0.

Fix, in the Task 8 Step 4 blocks:
```python
import paths       # noqa: E402  (Plan 1)   — replaces `import enter_mode` alone; keep both
...
    mode_path = paths.mode_file(MODE, skill_root)
```
and change line 4232 to `paths.mode_file(mode, root) -> pathlib.Path` (Plan 1). (The same call appears in Plan 2 line 5171 and Plan 4 line 2122 — worth fixing there in the same pass.)

### N2 — BLOCKING for Task 10. Step 6 retracts a sentence the shipped `SKILL.md` does not contain
**Plan lines 4953–4966, and Step 8's "Expected: PASS" at 4985.** Step 6 quotes *"`discover`, `assess` and `interview` are **not yet built in this repo**"* and replaces it with an inventory-shaped row `| **Modes** | … | new |`. In the **current** Plan 1 (revised today, uncommitted) that string is a row of Plan 1's *internal §-inventory table*, not of the shipped file. The shipped `SKILL.md` gets a purpose-built `## Modes` table (Plan 1 lines 5677–5683):

```
| `discover` | what is out there worth looking at | `discover` is not yet built in this repo |
```

Reproduced: applying Step 6 exactly as written leaves that row intact → Plan 3's own `test_the_not_yet_built_sentence_retracted_itself` fails **and** Plan 1's `test_a_mode_that_exists_is_not_still_described_as_not_yet_built` (R9's real backstop) stays red, so Step 8's "PASS, no failures" is wrong. The replacement row is also the wrong column shape for that table.

Fix — Step 6 should edit the shipped `## Modes` table row only:
```markdown
| `discover` | what is out there worth looking at | live — `modes/discover.md`; enter with `scripts/enter_mode.py --mode discover` |
```
leaving the `assess` and `interview` rows byte-identical, and drop the quoted-sentence framing.

### N3 — Task 10 Step 4 files the wrapper under a heading that promises a receipt it never writes
**Plan lines 4923–4933.** Step 4 appends `scripts/check_opencli_result.py` to the **"Ran, with a receipt in `journal.jsonl`"** list while the same bullet says it "writes an `adapter_call` record rather than a receipt". Plan 1 states the rule twice (lines 19 and 926) and now builds `SKILL.md` around it with four separate headings — *"Ran, leaving a `mode_entry` record rather than a gate receipt"*, *"Ran, leaving nothing in the journal"*, *"In CI, not in a workspace"* — closing with: *"a checklist that promises a receipt where none can exist teaches its reader that one of its lines is decorative, and the reader cannot tell which one."* Plan 3 re-creates exactly that. (Plan 1's heading has also changed to `Ran, with a receipt in \`journal.jsonl\` — \`scripts/check_apply.py\` requires each of these:`, which `check_opencli_result.py` does not satisfy either.)

Fix — give it its own heading instead of appending to that list:
```markdown
Ran, leaving an `adapter_call` record rather than a gate receipt:
- [ ] `scripts/check_opencli_result.py` — once per adapter invocation, exit 0
      (classified) or 2 (could not classify), never 1.
```
`test_the_self_check_names_every_script` and `test_the_self_check_names_this_plans_files…` both still pass (they search the whole section).

### N4 — Task 8 Step 2's expected failure is wrong in kind, twice
**Plan line 4309:** *"`AttributeError: module 'discover_fixtures' has no attribute 'mode_entry_record'` on three of the four, and `assert 0 == 1` on `test_no_mode_entry_fires`."* Measured on the reverted-Task-8 tree: **2** AttributeErrors, `test_no_mode_entry_fires` raises `TypeError: write_journal() got an unexpected keyword argument 'mode_entry'`, and `test_a_workspace_that_entered_the_mode_is_quiet` **passes**. This is the same defect class as old #10, re-introduced in the new task.

Fix, line 4309: *"FAIL — `test_a_mode_file_changed_after_entry_fires` and `test_the_hash_is_read_from_the_real_mode_file` error with `AttributeError: module 'discover_fixtures' has no attribute 'mode_entry_record'`; `test_no_mode_entry_fires` errors with `TypeError: write_journal() got an unexpected keyword argument 'mode_entry'`; `test_a_workspace_that_entered_the_mode_is_quiet` PASSES — it is the quiet twin and there is nothing yet for it to be quiet about."*

### N5 — Global Constraints line 26 justifies a duplication with two false statements about Plan 1
> "The **skill root** is not a spine path and `paths.py` does not model it, so `check_opencli_result.py` and `check_shortlist.py` derive it from `__file__` exactly as Plan 1's own `enter_mode.py` does"

`paths.py` **does** model it (`paths.SKILL_ROOT`, asserted by Plan 1's `test_mode_file_and_allowlist_resolve_under_an_explicit_root`), and `enter_mode.py` does **not** derive it from `__file__` — it reads `paths.SKILL_ROOT`. So the two `.parent.parent` derivations (line 517 `DEFAULT_SIGNALS_FILE`, line 4421 `--skill-root` default) are R4 violations, not carve-outs.

Fix: delete that sentence; `import paths` in both scripts and use `default=paths.SKILL_ROOT` / `DEFAULT_SIGNALS_FILE = paths.SKILL_ROOT / "references" / "risk-control-signals.yaml"`. Keep both override flags.

### N6 — cosmetic. Task 6 Step 2 undercounts by one
**Plan line 3360:** "Seven tests error with `FileNotFoundError`". Measured: **eight** (`test_source_policy.py` has 10 tests; 8 read the policy file, 2 read only `SKILL.md`). Change "Seven" → "Eight".

## Verdict

**NEEDS-WORK** — N1 makes 47 of 123 tests red on execution and breaks the live dry run; N2 leaves Task 10 unable to reach its own "Expected: PASS". N3–N6 are small and local. The eleven original defects are genuinely fixed — each one I re-derived from the plan's own code rather than from the report — and every per-task count in the plan matches what I measured.
