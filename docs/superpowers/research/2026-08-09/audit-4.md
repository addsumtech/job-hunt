# Plan audit — `docs/superpowers/plans/2026-08-09-4-interview-mode.md`

Read in full (3,893 lines) against spec §§4.3, 5.4, 6, 7 (P1 `check_mock.py`), 10, 11 (risks 7 / 14 / 15), and the shared contract. **No placeholders found** — the `TBD/TODO/implement later/handle edge cases/similar to Task N` scan returns zero hits, every step shows code rather than intent, and no function is referenced that isn't defined in some Produces block. **Git rules are clean** — no `git add -A`, no `git add .`, no `git push`, no `-c user.email`; every commit stages named paths. **Test quality is unusually good** — the quiet case is pinned as hard as the firing case for essentially every check (`test_a_generated_question_needs_no_source_id`, `test_the_same_tag_in_the_dutch_market_is_quiet`, `test_the_same_year_old_post_used_for_shape_is_quiet`, `test_a_post_that_names_the_posting_country_itself_is_quiet`, `test_a_rewrapped_quote_is_quiet`, `test_no_walkback_is_demanded_when_no_walkback_tag_fired`, `test_the_ordinary_claims_file_is_not_flagged`, dry-run stage C).

The failures are all **code reality**: six tests fail against the plan's own artifacts, and one fixture cannot be written at all under the plan's own stated rule. I verified each by executing the test logic against the plan's literal text.

---

## DEFECTS

### 1. `test_promotion_to_claims_resolves_it` fails against the plan's own implementation (L2587–2591)

```python
def test_promotion_to_claims_resolves_it(tmp_path):
    findings = run(F.build(tmp_path, assessment=assessment_with(UNSOURCED), claims=F.CLAIMS + PROMOTED))
    assert not [f for f in findings if f.startswith("UNRESOLVED_FACT:")]
```
`UNSOURCED` (L2460–2462) quotes `then wrote DICOMs back to the PACS`; `PROMOTED` (L2475) has `term: PACS export`. The resolution rule (L2735–2738) is `collapse_ws(row["term"]).lower() in quote.lower()` — i.e. **term must be a substring of the quote**. Executed: `"pacs export" in "then wrote dicoms back to the pacs"` → `False`. The test asserts it resolves; it does not. (The dry-run fixture works only because `term: department cluster` *is* a substring of its quote — so Task 8 passes and Task 5 fails, which is exactly how this survives a casual read.)

**Fix:** change `PROMOTED`'s `term:` to a token that occurs in the quote (`term: PACS`, or `term: DICOMs`), *and* add the inverse test — a promotion row whose term is absent from the quote must **not** resolve it — otherwise the matching rule stays untested in both directions.

### 2. `test_the_ceiling_is_stated_in_words` fails on backticks (L166 vs L398)

```python
assert "held_under_probe is the ceiling" in section
```
The reference doc the same task writes says: `**\`held_under_probe\` is the ceiling, and that is deliberate.**` — with backticks, so the asserted substring is absent. Verified `False`.

**Fix:** assert against the text as written — `"`held_under_probe` is the ceiling"` — or strip backticks from `section` before the membership test.

### 3. `test_every_shape_row_carries_a_source_label` fails on **every** row (L175–183)

Executed against the doc from Step 4: **33 of 34** "Market shapes" rows and **8 of 9** "Role-family shapes" rows fail `LABEL = re.compile(r"^\[(F|C|S)\]$")`. Three independent causes:
- `cells[0]` is `` `[F]` `` (backticked); the regex has no backtick allowance — `_first_col_tokens` strips them but this test uses `cells[0]` raw.
- `## Market shapes` contains **five** H3 sub-tables, so `rows[1:]` still holds four `| Source | Shape fact |` header rows.
- The Germany table has `` | `[U]` | Whether German private-sector hiring… | `` (L366) — `[U]` is defined in the doc's own label table (L302) but excluded from the regex.

**Fix:** in the test, strip backticks (`cells[0].strip("`")`), skip any row whose first cell is `Source`, and extend the regex to `^\[(F|C|S|U)\]$` — then add the assertion that actually carries the spec §10 requirement: a `[S]` or `[U]` row may never appear in the "Verbatim question material" section.

### 4. `test_search_summary_material_is_barred_from_verbatim_questions` fails on its second assert (L188 vs L301)

```python
assert "may set SHAPE" in _section("How to read the source labels")
```
The doc says `**Shape only.** \`[S]\` material may set round count, order, and ritual names.` The literal `may set SHAPE` appears only in the *Python* module comment (L278), not in the doc. Verified `False`.

**Fix:** assert `"may set round count, order, and ritual names"` and `"never be quoted"`, or add the exact sentence to the doc.

### 5. Task 7: 10 of the 18 `REQUIRED` phrases are absent from the SKILL.md text the plan says to append **verbatim** (L3324–3350 vs L3386–3460)

The section is hard-wrapped at ~90 columns; the assertions were written as if it were not. Executed diff:

```
it is fabrication, however plausible, and it stays fabrication after the candidate agrees
Naming a gap is feedback; filling it is ghostwriting a lie.
never build a question on a premise the CV does not support
the three CV judges only read the page and the page does not stammer
"I haven't done X" must survive rehearsal intact
before it may enter the answer bank            <- file says "BEFORE it may enter the answer\nbank"
an answer-bank entry containing an unsourced fact is worse than no answer bank
one round per dispatch                         <- file says "One round per dispatch"
flush the transcript after every answer        <- file says "Flush the transcript after every answer"
the first assessment pass does not see `interview-brief.md` or `claims.yaml`
```
Each is split by a newline + indent, or differs in case. Step 3 says "Append **exactly this**", so the implementer cannot satisfy Step 4 without contradicting Step 3.

**Fix:** make each `REQUIRED` entry a phrase that survives the wrap (shorten to the fragment that fits on one line, e.g. `"filling it is ghostwriting a lie"`, `"must survive rehearsal"`), or normalise before matching — `text = " ".join(SKILL.read_text().split())` and compare normalised phrases. Do not fix it by rewrapping the prose; the wrap will drift again.

### 6. Task 6: `test_the_mode_file_states["one round per dispatch"]` fails (L2862 vs L3071)

`modes/interview.md` contains only `**One round per dispatch.**` (capital O). Verified absent.

**Fix:** assert `"One round per dispatch"`, or lowercase both sides.

### 7. The indentation convention is ambiguous and **no single reading makes the plan work** (L1354–1360, L2008–2019, L2475–2481)

The plan indents fenced code by 4 and warns once (L1354–1360, scoped to `mock_fixtures.py`) that "in the real file they start at column 0". Measured leading whitespace:

| Constant | Body indent in plan | Needs |
|---|---|---|
| `QUESTION_LOG` L1267 | 4 / 6 / 8 (but `rejected:` at **0**, L1282) | dedent by 4 |
| `GOOD` L498 | 4 | dedent by 4 (else `ln.startswith("FINDING:")` filters never match — L584, L592) |
| `PROMOTED` L2475 | `- term:` at 0, `where:` at **6** | dedent by 4 (else `term` col 2 vs `where` col 6 → YAML error) |
| `SCRAPED` L2008 | `- id: Q4` at 2, `text:` at **4** | **no dedent** (dedent puts `text:` at col 0 → `yaml.YAMLError`) |

Dedent everything → `with_scraped()` produces unparseable YAML and ~10 tests in `test_check_mock_sources.py` fail with `QUESTION_LOG_UNPARSEABLE`. Dedent nothing → `PROMOTED`, `QUESTION_LOG` and `GOOD` all break. The `rejected:` line at column 0 inside an otherwise 4-indented literal (L1282) is the same bug in miniature.

**Fix:** state one rule at the top of the plan ("strip exactly 4 leading spaces from every line inside a fenced block"), then re-indent `SCRAPED` to `      - id: Q4` / `        text:` so it obeys it, and re-indent `rejected:` to 4. Extend the Step-1 verification one-liner to cover the sources test too:
`python3 -c "import yaml,sys;sys.path.insert(0,'scripts/tests');import test_check_mock_sources as t;print(len(yaml.safe_load(t.with_scraped())['questions']))"` → must print `4`.

### 8. Task 8 has no real red phase (L3848–3853)

Step 1–2 write the complete fixture; Step 3 writes the test; **Step 4 "Run test to verify it fails"** then says `Expected: FAIL with FileNotFoundError ... (before the fixture is written) or, once written, AssertionError`. By Step 4 the fixture *is* written, so the test should pass. The step that proves the test is real is missing.

**Fix:** reorder — Step 1 write `test_mock_dryrun.py`, Step 2 run it and watch it fail with `FileNotFoundError: fixtures/mock-dryrun`, Step 3 write the fixture + fixes, Step 4 run and watch it pass. That also makes the stated failure message true.

### 9. The Definition-of-Done command exits 2, not 1 (L3872)

```
python3 scripts/check_mock.py --workspace .../asml-mr-recon-engineer-2026-08-09 --round 2 --today 2026-08-09
```
is asserted to "exit 1 and print `WALKBACK_MISSING:`". From the CLI there is no way to inject a scanner, so `_default_scanner()` runs; until Plan 2 lands it returns `None`, `check_vocabulary` raises `MissingDependency`, and `main` returns **2**. The plan's own Global Constraint (L15) says this is the intended behaviour — so the DoD contradicts it.

**Fix:** either add a documented `--skip-vocab` / `--vocab-scanner none` flag (and a test that it is refused unless explicitly passed), or restate the DoD as "exits 2 with `lint_no_prediction` on stderr until Plan 2 lands; exits 1 with `WALKBACK_MISSING:` after".

### 10. A renamed Plan-2 function crashes instead of exiting 2 (L1855–1862)

```python
try:
    import lint_no_prediction
except ImportError:
    return None
return lint_no_prediction.scan_text
```
The plan itself says "If Plan 2 named it differently, change `_default_scanner()`" (L1975). If Plan 2 lands with a different name, `lint_no_prediction.scan_text` raises `AttributeError`, which `main()` does not catch → traceback, exit 1 from Python, no receipt, no stable code. That is precisely the "a check that did not run must not look like a check that passed" failure the module docstring forbids.

**Fix:** `scan = getattr(lint_no_prediction, "scan_text", None)` and `return scan` (so `None` → `MissingDependency` → exit 2), plus a test: `monkeypatch.delattr(lint_no_prediction, "scan_text", raising=False)` → `main()` returns 2 and stderr names the symbol.

### 11. Seven finding codes have no test in either direction

`BAD_ROUND` (L1708), `NO_FAMILY` (L1728), `QUESTION_LOG_EMPTY` (L2262), `UNKNOWN_USE` (L2285), `NO_ANSWER_BANK_ENTRIES` (L2343), `CLAIMS_UNPARSEABLE` (L2717), and the `SHAPE`-status branch of `UNKNOWN_STATUS` (L1844–1849) are emitted by code no test exercises. Spec §7 test discipline — "只 import 模块的测试只能证明按钮存在" — applies: these are buttons with no press.

**Fix:** add one firing test each to `test_check_mock_core.py` / `_sources.py`, breaking exactly one thing from the quiet fixture (e.g. `ROUND: two`, `FAMILY:` empty, `questions: []`, `use: maybe`, an answer bank with no `## `, `claims.yaml: "[unclosed"`, `SHAPE: status=done`).

### 12. `UNKNOWN_REF` silently disables itself on a heading-less transcript (L1745)

```python
if refs and ref not in refs:
```
A transcript with no `## Q<n>` headings yields `refs == set()` and **every** `ref=` passes unchecked — with no finding saying so. The mode file requires those headings (L3008), so their absence is a defect, not a licence.

**Fix:** emit `NO_QUESTION_HEADINGS: mock/transcript-<n>.md has no '## Q<n>' headings — every ref= is unverifiable` when `refs` is empty and the block has records, and pin it with a test plus the quiet counterpart.

### 13. A journal write failure still reports success (L1867–1875)

`_receipt` catches `OSError`, prints a warning to stderr, and `main()` returns 0 anyway — so the gate can exit 0 with **no receipt line**, while the shared contract says "Every gate appends exactly one receipt line before exiting" and `modes/interview.md` §7 tells the model to quote the receipt.

**Fix:** on receipt-write failure return 2 with `RECEIPT_WRITE_FAILED:` on stderr; test with a read-only workspace dir (`chmod 0o500`).

### 14. Minor — `scripts/paths.py` is bypassed (L1880–1884)

The shared contract says `paths.py` is "imported wherever a path is resolved"; `_answer_bank_default` re-derives the profile dir as `workspace.parents[1]`. If `paths.workspace()`'s shape changes, this breaks silently rather than at the one place that owns the layout.

**Fix:** `import paths` and resolve via `paths.answer_bank(workspace.parents[1].name)`, keeping the `--answer-bank` override; the tests already exercise both branches.

### 15. Minor — step granularity on the two prose steps

Task 1 Step 4 (`references/interview-shapes.md`, ~160 lines) and Task 6 Step 3 (`modes/interview.md`, ~360 lines) are single checkboxes that are hours, not 2–5 minutes, and Task 1 writes two production artifacts (Steps 3 and 4) between one red and one green.

**Fix:** split each into per-H2 sub-steps that map to the assertions already written (labels table → market tables → role-family table → bands → tag tables → verbatim material), re-running the doc test after each so the red→green cycle is per-section rather than per-file.

---

**Spec coverage:** complete. Every element of §5.4 (entry conditions, inline-interviewer rationale, the isolation table, all seven pipeline steps, all six 面经 rules including the country rule, the four unnumbered bands with `在追问下站住` as ceiling, the published-rubric exception, both write-backs, and all five `check_mock.py` gate clauses), §4.3's `mock/` layout and append-only transcript, §6's 反教唆四条 + 绊线 + 会话机制, §10's visible source-quality labels, and §11 risks 7/14/15 have owning tasks. The §6 item 等价测试（诚实 ≠ 畏缩） is correctly left to Plan 1's SKILL.md and honestly re-declared as uncloseable in the Handover notes (L3889–3892).

**Verdict: NEEDS-WORK** — six tests fail against the plan's own artifacts (defects 1–6), one fixture is unwritable under the plan's own indentation rule (7), and Task 8's red phase is not real (8).
