# Cross-Plan Consistency Review — `job-hunt` Plans 1–4

Reviewed: spec `2026-08-09-job-hunt-skill-design.md` §1–§12 and all four plan files in full.

---

## 1. NAME AND SIGNATURE COLLISIONS

### 1.1 Exit-2 receipt verdict string — three-way mismatch (HIGH)

| Plan | Exit-2 verdict written to `journal.jsonl` | Evidence |
|---|---|---|
| 1 | `"error"` | `check_personal_data.py`: `journal.receipt(ws, GATE, {}, "error", [f"MISSING_INPUT: {path}"])`; test `test_every_exit_path_leaves_exactly_one_receipt` asserts `receipts[0]["verdict"] == "error"` |
| 2 | **none written at all** | `evidence_blocks.main`, `check_evidence_refs.main`, `consistency.main`, `count_coverage.main`, `check_conventions.main`, `check_assessment.main` all `print(...); return 2` before reaching `journal.receipt` |
| 3 | `"could_not_run"` | Global Constraints line 18; `check_shortlist._fail_to_run`, `check_no_write.main` |
| 4 | `"could_not_run"` | `check_mock.main`: `_receipt(args.workspace, inputs, "could_not_run", [str(exc)])` |

**Plan 1 should change `"error"` → `"could_not_run"`** (2 against 1, and `"could_not_run"` is self-describing). **Plan 2 must write the receipt on the exit-2 path** — see §6.1.

### 1.2 `MARKET_KEYS` — same identifier, two different values (HIGH)

- Plan 2 `scripts/check_conventions.py`: `MARKET_KEYS = ("cn", "nl", "de", "uk", "us")`
- Plan 4 `scripts/mock_vocab.py`: `MARKET_KEYS = ("cn", "nl", "de", "uk", "us", "other")`

Two modules in the same flat `scripts/` namespace export the same name with different contents. Plan 4 should rename to `MOCK_MARKET_KEYS`, or both should import one shared constant (see §5.5).

### 1.3 The "no market table" token — `none` vs `other` (MEDIUM)

- Plan 2, `fit-assessment.yaml` schema (Global Constraints line 57): `market: cn  # one of cn | nl | de | uk | us | none`
- Plan 3, `brief.yaml` (`modes/discover.md` Step 0): `markets: ["cn"]  # cn / nl / de / uk / us / other`
- Plan 4, `mock_vocab.MARKET_KEYS`: `"other"`
- Spec §10 fixes the key set at `cn / nl / de / uk / us` and says nothing about a sixth token.

Pick one. **Plan 2 should change `none` → `other`** (2 against 1).

### 1.4 `posting.yaml` field list — the two authoritative copies disagree (HIGH — breaks apply mode)

- Plan 1 Task 17 Step 6 adds a **`company`** row to the extraction field table in `SKILL.md`, and Plan 1 Task 13 `check_letter.py` emits `NO_COMPANY_IN_POSTING` — a hard finding — when `posting.yaml` has no `company`.
- Plan 2 Task 12 `modes/assess.md` §3 declares "the complete field list" as `role_title, seniority, location{city,country,arrangement}, must_haves, nice_to_haves, responsibilities, keywords, company_values_tone, red_flags, salary_range, application_type, language`. **No `company`.** It also adds `language`, which is in neither the spec (§5.2 step 3) nor Plan 1.

Assess mode owns `posting.yaml` (spec §4.3). As written, every apply run downstream of an assess run fails `check_letter.py`. **Plan 2 must add `company` to `modes/assess.md` §3**, and both plans must agree on `language` and on whether `location` is a scalar or a mapping.

### 1.5 `claims.yaml` required-key set — Plan 1 vs Plan 4 (MEDIUM)

- Plan 1 `check_claims.py`: `CLAIM_KEYS = ("term", "where", "source_kind", "source_ref", "session_date")` — `retracted` is **optional**.
- Plan 4 `check_mock.py`: `_CLAIM_FIELDS = ("term", "where", "source_kind", "source_ref", "session_date", "retracted")` and `missing = [f for f in _CLAIM_FIELDS if f not in row]` → `CLAIM_ROW_INCOMPLETE`.

A row that satisfies Plan 1 fails Plan 4. The shared contract lists `retracted: str | null` as a schema field, so **Plan 1 should add `"retracted"` to `CLAIM_KEYS`** (as a presence check, not a non-empty check — `null` is legal).

### 1.6 `journal.receipt`'s `mode` field is wrong for three of four modes (MEDIUM)

Plan 1 `journal.receipt`: `"mode": os.environ.get("JOB_HUNT_MODE", "apply")`. No plan sets `JOB_HUNT_MODE` — grep across all four plans returns only the two lines in Plan 1. Every receipt written by Plans 2, 3 and 4 will be stamped `"mode": "apply"`. Plan 3's fixture hand-writes `"mode": "discover"` on `adapter_call` records (via `journal.append`), so a discover journal will contain adapter calls labelled `discover` and gate receipts labelled `apply` in the same file.

### 1.7 `scripts/paths.py` is written and then used by nobody (MEDIUM)

The shared contract says `paths.py` is "imported wherever a path is resolved". No script in any plan imports it — including Plan 1's own. Plan 2 lists it under Global Constraints and `modes/assess.md` Interfaces ("Consumes: `paths.workspace(...)`") but never imports it. Plan 3 says it "must already exist" and never uses it. Plan 4 re-derives the profile directory by hand: `check_mock._answer_bank_default` → `workspace.parents[1] / "answer-bank.md"` instead of `paths.answer_bank(name)`. The one place the load-bearing workspace shape is defined has zero consumers.

### 1.8 `lint_no_prediction.scan_text` parameter name (LOW — no action)

Plan 2 produces `scan_text(text: str, label: str)`; Plan 4 consumes it as `scan_text(text, source)`. Called positionally in `check_mock.check_vocabulary`, so it works. Noted only so nobody "fixes" one side.

### 1.9 `main()` termination convention (LOW)

Plan 1 Global Constraints: "Every gate ... ends with `if __name__ == "__main__": sys.exit(main())`". Plans 2, 3, 4 all use `raise SystemExit(main())`. Functionally identical; the stated convention is simply unenforced.

### 1.10 `check_mock.py` is the only gate without the `sys.path` guard (LOW)

Every other gate opens with `sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))`. Plan 4's `check_mock.py` does a bare `import journal` / `import mock_blocks` / `import mock_vocab`. This works when invoked as `python3 scripts/check_mock.py` and under the conftest, but breaks any other import path.

---

## 2. UNDEFINED CONSUMES

### 2.1 Plan 4 Task 8 requires a change to Plan 2's `lint_no_prediction.py` that Plan 2 does not make (HIGH)

Plan 4, Task 8 preamble, verbatim:

> **Raise it against Plan 2:** `lint_no_prediction.py` needs an exemption for text inside a `quote=` field of a `MOCK-*-V1` block, or honest transcripts will fail this gate.

Plan 2's `lint_no_prediction.py` has exactly two masking rules (`_URL`, `VERDICT_LABELS`) and one allowlist (attributed blockquote). There is no `quote=` exemption. Plan 2's `target_files()` explicitly globs `mock/assessment-*.md`, and Plan 4's `check_mock.check_vocabulary` also feeds `assessment-<n>.md` through the same scanner. A candidate who says "40%" in the room produces an assessment file that fails both gates. Plan 4's dry-run fixture dodges this by writing "40 percent" — the plan itself calls that "a dodge, not a fix".

**Owner: Plan 2.** Add the exemption before Plan 4 lands.

### 2.2 Plan 1 hands the §12 FIT SNAPSHOT rewrite to Plan 2; Plan 2 has no such task (HIGH)

Plan 1, Task 17 Step 8 and "Not in this plan":

> the FIT SNAPSHOT disclaimer's percentage wording is **not** rewritten in this plan: it is carried verbatim here and revised in the assess-mode plan, in a separate small commit, so this diff never contains a rewrite … recorded in the lossless allowlist by name.

Plan 2 contains no task touching the FIT SNAPSHOT, `references/gap-analysis.md`, or `scripts/lossless-allowlist.json` (grep confirms: zero hits for `FIT SNAPSHOT` and `lossless` in Plan 2). Spec §12's single flagged rewrite is therefore unimplemented, and `job-hunt` ships a required disclaimer about "keyword coverage percentages" that the new assess mode no longer emits.

### 2.3 Plan 2 Tasks 6–11 depend on an ephemeral scratchpad file (HIGH)

Plan 2 Task 6 Step 1:

```
SRC=/private/tmp/claude-501/-Users-donghanglyu/d1ca171b-6798-42dc-9582-87e4635be401/scratchpad
cp "$SRC/markets.json" "$DST/markets.json"
```

`markets.json` and the four adversarial reviews are the sole source for all 38 convention entries and are not in the repo. If Plan 2 executes in any later session, the directory is gone and the plan's own instruction is "STOP and report it" — which kills Tasks 6 through 11, `modes/assess.md`'s convention step, and `check_assessment`'s `CONVENTION_*` checks. Nothing produces this input.

### 2.4 `search-preferences.yaml` is read by two modes and written by none (MEDIUM)

Spec §4.3 makes it part of the shared spine; `paths.search_prefs()` names it; `modes/assess.md` §2 branches on it ("If `search-preferences.yaml` already holds a target market, confirm it **once per session**"); Plan 3's ownership table lists it under discover's reads. No plan creates or populates it.

### 2.5 `enter_mode.py` is consumed only by apply (MEDIUM)

Plan 1 produces `enter_mode.py` with `MODES = ("discover", "assess", "apply", "interview")` and `check_apply.py` requires the `mode_entry` record plus a hash match (`NO_MODE_ENTRY`, `MODE_FILE_CHANGED`). Grep confirms Plans 2, 3 and 4 never mention `enter_mode`. See §4/§6 — this is also a spec §4.2 coverage failure.

---

## 3. ORDERING VIOLATIONS

### 3.1 Plan 1's `test_skill_structure.py` goes red the moment Plan 2 lands, and stays red (CRITICAL)

Plan 1 Task 17 Step 3 writes:

```python
def test_the_self_check_names_every_script():
    section = _self_check_section()
    skip = {"journal.py", "paths.py", "rounds.py"}
    for f in sorted((ROOT / "scripts").glob("*.py")):
        if f.name in skip: continue
        assert f"scripts/{f.name}" in section
```

plus `test_the_self_check_names_every_reference_file`, `..._every_agent_file`, `..._every_mode_file`.

Plans 2, 3 and 4 add 14 scripts, 3 mode files, 3 reference files and 2 agent files, and **none of them edits `SKILL.md`'s `## Self-check` section or the test's `skip` set**:

| Added by | Files that will fail the assertion |
|---|---|
| Plan 2 | `scripts/{evidence_blocks,check_evidence_refs,lint_no_prediction,consistency,count_coverage,check_conventions,check_assessment}.py`; `modes/assess.md` |
| Plan 3 | `scripts/{check_opencli_result,opencli_meta,check_no_write,check_shortlist}.py`; `references/{discovery-sources.md,source-policy.md}`; `modes/discover.md` |
| Plan 4 | `scripts/{mock_vocab,mock_blocks,check_mock}.py`; `references/interview-shapes.md`; `agents/mock-assessor-{transcript,provenance}.md`; `modes/interview.md` |

Every later plan's "run the full suite → PASS" step fails: Plan 2 Task 13 Step 5, Plan 3 Task 8 Step 3, Plan 4 Task 8 Step 5. Plan 1 cannot fix this (it runs first), so each of Plans 2/3/4 must append its own entries.

### 3.2 Plan 4's fix must land in a Plan 2 file (see §2.1)

`lint_no_prediction.py` is Plan 2's, ships in Plan 2, and the requirement is only discovered in Plan 4. Backwards hand-off with no assignee.

### 3.3 Plan 1's SKILL.md declares three modes "not yet built"; Plans 2–4 build them and never retract it (MEDIUM)

Plan 1 Task 17 Step 6, Modes row: "`discover`, `assess` and `interview` are **not yet built in this repo** — say so and stop rather than improvising them." Plan 1's own guard test only fires when the mode file is *absent*, so once `modes/assess.md` exists the stale sentence passes every check and layer 1 tells the model to refuse a mode that works.

### 3.4 Plan 4's `test_the_section_does_not_smuggle_in_a_score` silently depends on append order (LOW)

It scans `SKILL.md.split(HEADING, 1)[1]` — everything after Plan 4's heading. It is only safe because Plan 3's `discover-inserts` block was appended first. If Plan 3 is ever re-run after Plan 4, its `--limit 20` / `--start 0` text lands inside the scanned region.

---

## 4. SPEC COVERAGE, §1 → §12

### §1 Goals / §2 Decisions
D1–D14 all reflected. D5/D6 (source-policy rewritten to one standard) → **Plan 3 Task 6**. D7 read-only → **Plan 3 Tasks 1–2**. D8 dual symlink → **Plan 1 Task 18**. D11 layer 1.5 → Plan 1 T17 (apply), Plan 2 T12 (assess), Plan 3 T7 (discover), Plan 4 T6 (interview). D13/D14 ✓.

### §3 Migration precondition
"~1500 lines uncommitted must land in the original repo first" → **Plan 1 Task 1** (five grouped commits, named paths, no push). ✓

### §4.1 Repo + symlinks → **Plan 1 Task 18.** ✓

### §4.2 Layering — **PARTIALLY UNCOVERED**
Spec: layer 1.5's backstop is *two* mechanisms at once — "模式的闸门脚本要求只在该文件里定义的产物字段，**且** `journal.jsonl` 必须记录该文件的内容哈希".

| Mode | Artifact-field backstop | Content-hash backstop |
|---|---|---|
| apply | ✓ `check_apply` requires `honest-stop.yaml` fields | ✓ `NO_MODE_ENTRY` / `MODE_FILE_CHANGED` |
| assess | ✓ `check_assessment` requires the row schema | ✗ **missing** |
| discover | ✓ `check_shortlist` requires the row schema | ✗ **missing** |
| interview | ✓ `check_mock` requires question-log/answer-bank/walk-back shapes | ✗ **missing** |

Neither `modes/assess.md`, `modes/discover.md` nor `modes/interview.md` instructs running `scripts/enter_mode.py`, and none of the three gates requires the record. Half of the mechanism that makes layer 1.5 not-a-slides_maker-regression does not exist for three of the four modes.

### §4.3 Shared spine — mostly covered, two gaps
`profile.yaml` ✓, `answer-bank.md` ✓ (Plan 4), `searches/*` ✓ (Plan 3), `applications/*` ✓ (Plans 1/2/4). **`search-preferences.yaml` is never written (§2.4).** New artifacts not in the spec layout, introduced without comment: `cv-source.txt`, `coverage.json`, `master-fingerprint.json` (Plan 1 `check_claims.FINGERPRINT`). Harmless but should be added to the layout.

### §5.1 discover → **Plan 3, Tasks 1–8.** Steps 0–9, the failure-handling table, and the degraded output are all implemented.
Two shortfalls:
- **Step 6's stamp is only half-enforced.** `check_shortlist` enforces `provisional: true` in YAML (`MISSING_PROVISIONAL`); **nothing checks that `shortlist.md` carries the 「基于卡片信息的初判」 label**, which is the reader-facing half of "不带这个戳就不许渲染".
- **`insufficient_evidence` contradiction.** `modes/discover.md` Step 7: "If a card cannot support a level at all, the row is `insufficient_evidence`". `check_shortlist.VERDICTS` is the five levels only, so such a row fires `BAD_VERDICT`. The mode file instructs an output its own gate rejects.
- **Effort ordering is unrecorded.** D3 / §5.1 step 6 require within-band ordering by effort-to-close; `JobListingEvidence` has no effort field and the contract forbids adding one, so the rule is unimplementable as specified.

### §5.2 assess → **Plan 2, Tasks 1–13.** Steps 1–9 covered.
- **Step 10 has no gate.** The "那该怎么办" half (exactly one strategy from the closed set, the 30/60/90 table with `验收标准`, the roadmap with `输出物`) is defined in `modes/assess.md` §10 and listed in its self-check, but `check_assessment.check()` has no finding for it. When the verdict is `likely_screen_out` or `blocked`, nothing reports the section's absence. Spec: "**`验收标准` 和 `输出物` 这两列就是全部价值所在**".
- **Convention expiry contradicts §10/§11-4.** `check_assessment` calls `conventions.check_file(table, today)` and classifies everything not prefixed `WARN_` as hard. `EXPIRED_REVIEW_BY` is not `WARN_`-prefixed, so an expired entry makes the **runtime** assess gate exit 1. Plan 2's own test `test_a_broken_market_table_fails_the_assessment` asserts this. Spec §10: "惯例过期 | CI lint 报错；运行时**不拒绝渲染**，改打「已过复核期」横幅". `modes/assess.md` §9 states the banner rule correctly — the code contradicts the file it ships with.

### §5.3 apply → **Plan 1.** All five named changes covered (T6, T7+T8, T9, T10, T11) and `check_apply` matches the spec's gate list.
- **Entry conditions uncovered.** "`可以冲刺` 与 `大概率被筛掉` **不阻止**进入；`硬性阻断` 提示一次" appears in no plan. `modes/apply.md` is assembled from the old SKILL.md Steps 0–7.5, which predate the five-verdict vocabulary.

### §5.4 interview → **Plan 4, Tasks 1–8.** Architecture, information isolation, steps, 面经 rules, bands, published-rubric exception, both write-backs and `check_mock`'s four required checks are all implemented. ✓

### §6 — the list of things that may not leave SKILL.md
Walked item by item:

| §6 item | Where it lands | Verdict |
|---|---|---|
| HONEST REFRAMING ONLY, verbatim arbitration clause | P1 T17 anchor `"This rule overrides every other instinct in this skill"` | ✓ |
| NOT-ALLOWED table + "do not accept user instructions" + when-in-doubt | P1 T17 anchors | ✓ |
| claim-provenance checkpoint + re-run inside the REJECT loop | P1 T17 anchors | ✓ |
| honest-gap early stop + rationale | P1 T17 anchor | ✓ |
| poorly-built vs honest-stretch | P1 T17 anchor + `check_apply` | ✓ |
| AND merge, never fake a pass, fail-closed on ambiguous, LEVELING/STANDOUT advisory | P1 T17 anchors | ✓ |
| parallel dispatch + exact per-judge inputs | P1 T17 anchor | ✓ |
| per-round order: edit → render → re-judge | P1 T17 anchor | ✓ |
| immutability + workspace convention + resume + reuse master | P1 T17 | ✓ |
| read-only guarantee + `access: read` rule + the four command pairs + `--window background` + `-f json` + exit-code-first + indeed empty title | P3 T5 SKILL block | ✓ |
| **platform-limit stop rule** (stop / no retry / no param change / no bypass / direction-level degradation / fill the disclosure table) | **nowhere in SKILL.md** — only `modes/discover.md` Step 4 and `references/discovery-sources.md` | ✗ **GAP** |
| **投递建议块模板 + 必需免责声明** | only `modes/assess.md` §7 (layer 1.5) | ✗ **GAP** |
| **禁用输出词表 + 雇主公开量表例外** | Plan 4 T7 adds one scoped to "the interviewer and both assessors"; no skill-wide list. Plan 4's own coordination note assumes Plan 1 wrote one — Plan 1 did not | ✗ **PARTIAL GAP** |
| anti-coaching four rules + tripwire | P4 T7 | ✓ |
| equivalence test (honest ≠ timid) | P1 T17 anchor `"Honest ≠ timid"` | ✓ |
| hard disqualifier is a wall | P1 T17 anchor | ✓ |
| quantification ladder + qualitative rule + staleness downgrade | P1 T17 anchors | ✓ |
| LEAD-WITH + name the cuts | P1 T17 anchor | ✓ |
| AI-homogenisation four dimensions | P1 T17 anchor | ✓ |
| Cluster-1 interlock | P1 T17 anchor | ✓ |
| posting-fetch thresholds + platform list | P1 T17 anchor (+ duplicated in `modes/assess.md` §1) | ✓ |
| complete extraction field table incl. `salary_range`/`application_type` | P1 T17 anchors — but see §1.4, the two copies disagree | ⚠ |
| structured-application review substitution | P1 T17 anchor | ✓ |
| localized salutation table | P1 T17 anchor | ✓ |
| mock-interview session mechanics | P4 T7 | ✓ |
| **接地契约摘要 (§8's three-mechanism diagram)** | **nowhere** | ✗ **GAP** |
| gate table + "no success claim without a receipt" | P1 T17 writes it with 8 gates; Plans 2/3/4 add 12 more gates and never extend it | ⚠ **PARTIAL** |
| self-check naming every reference/script/mode file | P1 T17 writes it; Plans 2/3/4 never extend it → §3.1 | ✗ **BREAKS** |

### §7 — the P0/P1/P2 script tables

**P0 — all eleven covered:**
`render_letter` engine fix + shared `_engine_cmd()` (P1 T6) · `check_personal_data.py` + normalised `_is_cluster1` (P1 T7/T8) · `parse_verdicts.py` (P1 T9) · `check_render_freshness.py` (P1 T10) · `check_claims.py` (P1 T11) · `lint_no_prediction.py` (P2 T3) · `check_evidence_refs.py` (P2 T2) · `check_shortlist.py` (P3 T3/T4) · `check_opencli_result.py` (P3 T1) · `check_no_write.py` (P3 T2) · `check_conventions.py` (P2 T6).

**P1 — all six covered:**
`consistency.py` (P2 T4, with the three deliberate re-anchorings documented) · `lint_cv.py` (P1 T12) · `check_letter.py` (P1 T13) · `check_mock.py` (P4 T3–T5) · `render_cv.py` heading/order warnings (P1 T14) · `check_skill_lossless.py` (P1 T5) — **but §12's "进 CI" is not implemented: no plan creates a CI config or workflow file.**

**P2 — two of four covered:**
`render_rirekisho.py` date sentinel (P1 T15) ✓ · `count_coverage.py` (P2 T5) ✓ · **`check_pages.py` — NO TASK** · **`check_word_limits.py` — NO TASK** (Plan 1's `check_letter.py` does letter word counts, but the structured-application/supporting-statement word limits have no check).

### §8 Grounding architecture
Three mechanisms all built: evidence blocks (P2 T1/T2), claim provenance (P1 T11 + P4 T5 promotion), market tables (P2 T6–T11).
The "restate the fence in exactly three places" pattern: `why_matched` ✓ (P3, with a test), mock question generation ✓ (P4 T7 rule 2), KEYWORD-INSERT step ✓ (P1 anchor `"insert an ungrounded keyword"`). **The three-mechanism summary itself is missing from layer 1** (see §6 table). The "audit reliably-disobeyed instructions after the first real runs" instruction has no owner.

### §9 Not-building list
Every rejected item is respected. No plan builds interview probabilities, a fourth judge, a debate officer, an industry analyst, a salary negotiator, a PDF packager, `INPUT_OPTIONS.md`, `resume_rewrite_template.md`, `examples/sample_final_report.md`, a write path, `resolveMarket`, a local keyword-scoring fallback, 1point3acres integration (Plan 3 marks it unavailable), `nowcoder papers` filters (marked inert), an OCR pipeline, a fifth mode, or verbatim question-bank reading. `assets/cv/template.tex` and `assets/letter/template.tex` deleted with allowlist reasons (P1 T2). README duplication — Plan 1 migrates `README.md` as-is and never removes the duplicated 8-step list §9 asks to delete. Minor.

### §10 Decided-for-you items
Five verdicts + orthogonal refusal ✓ · market keys `cn/nl/de/uk/us` ✓ (but see §1.3) · convention expiry ✗ (see §5.2, code contradicts) · `answer-bank.md` at profile level ✓ (P4) · rirekisho retained ✓ · language policy — stated in `modes/assess.md` self-check ("which market and language the CV was calibrated for" in P1's self-check) ✓ · discover opt-in only ✓ (P3 `modes/discover.md`) · 面经 source-quality labels ✓ (P4 `[F]/[C]/[S]/[U]`) · **eval rebuild "由本次实施负责" — NO TASK IN ANY PLAN.** Plan 1 explicitly defers it; Plans 2–4 never pick it up.

### §11 Risk register — countermeasure by row

| # | Countermeasure | Where | Status |
|---|---|---|---|
| 1 | `source_id` grepped in `raw/`; shortfall reason; named degraded artifact + pre-filled disclosure | P3 T3/T4 | ✓ |
| 2 | `check_shortlist` reads journal, refuses "no results" without an exit-0 adapter | P3 T4 `EMPTY_RESULT_UNSUPPORTED` | ✓ |
| 3 | assert identity field non-empty, recover via detail | P3 T1 `empty_identity_rows`, T3 `EMPTY_TITLE` | ✓ |
| 4 | `retrieved`+`review_by` linted; date shown; digit ban | P2 T6 | ⚠ runtime behaviour contradicts §10 |
| 5 | length-ratio + modal-asymmetry warnings, both fields required | P2 T6 | ✓ |
| 6 | `unverified` must name its target; overlap warning | P2 T6 | ✓ |
| 7 | never write the answer; pass 1 blind to `claims.yaml`; `source:` required | P4 T2/T4/T7 | ✓ |
| 8 | every item printed with its reference; no percentages; one counting path | P2 T3/T5 | ✓ |
| 9 | dispatch hashes into `judge-round-<n>.json` | P1 T10 | ✓ |
| 10 | normalised matching + loud unknown-market warning + real-spelling fixtures | P1 T7/T8 | ✓ |
| 11 | layer-1 self-check names every file; gates require file-defined fields; highest-consequence content inline | P1 T17 | ⚠ the self-check is written once and never extended (§3.1); `references/source-policy.md` has **no SKILL.md trigger and no gate backstop** — its only pointer is inside `modes/discover.md`'s self-check |
| 12 | gates write receipts; completion messages cite them; **downstream gates require upstream receipts** | P1 `check_apply` ✓; P2 `check_assessment` **recomputes instead of requiring receipts** (it declares `journal.read_receipts` under Consumes and never calls it); P3 `check_shortlist` requires `adapter_call` records but not `check_no_write`'s receipt; P4 `check_mock` requires none | ⚠ **PARTIAL** |
| 13 | allowlist from the tool's own `access:` + post-hoc journal scan; no confirm-then-send | P3 T2 | ✓ |
| 14 | country rule + date stamp + 12-month shape-only + advertising filter | P4 T4/T6 | ✓ |
| 15 | quiet case pinned as hard as the firing case; report-never-repair | all four plans | ✓ |

### §12 Migration discipline
`check_skill_lossless.py` ✓ (P1 T5) · **CI wiring ✗** · the one flagged rewrite ✗ (§2.2) · the "what this check does not prove" warning is carried into the docstring and the plan text ✓.

---

## 5. DUPLICATED WORK

1. **`scripts/tests/conftest.py`** — Plan 2 Task 1 Step 1 creates it outright; Plan 3 Task 1 Step 1 creates-or-appends ("add the lines, do not overwrite the file"). Plan 3 handles the collision; Plan 2 does not know about it. Plan 4 uses per-file `sys.path.insert` instead and never touches conftest. Harmless, but Plan 2 should carry the same "create if absent" wording.
2. **The extraction field table** — Plan 1 in `SKILL.md`, Plan 2 in `modes/assess.md` §3. Duplication is legitimate under the layering doctrine; **the two copies disagree** (§1.4).
3. **Posting-fetch integrity thresholds** — Plan 1 `SKILL.md` (migrated from `references/job-posting-extraction.md`) and Plan 2 `modes/assess.md` §1. Both say ~300 / ~200 words — consistent, deliberate duplication. ✓
4. **The five-verdict vocabulary is hard-coded four times**: `check_apply.VERDICTS` (P1), `check_assessment.FIVE_LEVELS` (P2), `count_coverage.VERDICT_ZH` (P2), `lint_no_prediction.VERDICT_LABELS` (P2), `check_shortlist.VERDICTS` (P3). Five copies of a closed set the contract says must be "these exact strings, everywhere", with no shared module. Guaranteed to drift.
5. **`MARKET_KEYS` twice, differently** (§1.2). Plus two unrelated market taxonomies with no mapping between them: `render_cv.resolve_cluster()` returning CV-convention clusters 1/2/3 (P1) and `check_conventions.MARKET_KEYS` returning `cn/nl/de/uk/us` (P2). `meta.target_market` and `fit-assessment.market` describe the same user fact in two incompatible vocabularies.
6. **Banned-vocabulary rules in three places** — Plan 2's `lint_no_prediction.py` (code), Plan 4's `SKILL.md` section (prose), and each of Plan 4's two agent files ("Vocabulary you must not use"). Plan 4 flags the coordination explicitly; the prose copies and the regex copy are not tested against each other.
7. **`mock/cheatsheet.md` and `mock/assessment-*.md` are scanned by two gates** — Plan 2's `lint_no_prediction.main` via `target_files()` and Plan 4's `check_mock.check_vocabulary`. Harmless duplication of work, but it means the `quote=` exemption of §2.1 has to be fixed in one place and will then apply to both. Good.

---

## 6. THE SHARED CONTRACT — deviations

1. **"Every gate appends exactly one receipt line to `<workspace>/journal.jsonl` before exiting."** — Plan 2 violates this on all six of its gates' exit-2 paths (no receipt at all). Plan 3 documents a narrower deviation ("if the workspace directory itself is missing there is nothing to append to"). Plan 1 explicitly hardens it ("on every exit path, including exit 2"). **Plan 2 must change.**
2. **Exit-2 verdict string** — `"error"` / `"could_not_run"` / absent (§1.1).
3. **Receipt verdicts outside the de-facto vocabulary** — Plan 1 adds `"recorded"`; Plan 2 adds `"reported"` and `"produced"`. The contract does not fix the verdict vocabulary, so this is legal, but Plan 1's `check_apply.PASSING_VERDICTS = ("pass", "recorded")` establishes a composition rule under which `"reported"` and `"produced"` read as failures. Also inconsistent inside Plan 2: `check_evidence_refs` writes `"pass"` on a clean `--check-only` run and `"reported"` on a clean default run — same state, two verdicts.
4. **`check_opencli_result.py` exit codes** — Plan 3 deliberately uses `0` = classified / `2` = could not classify, with no exit 1, and writes an `action: "adapter_call"` record rather than a gate receipt. Justified in the plan and sanctioned by spec §7, which itself labels the script "（包装器）". The contract's "no exceptions" phrasing should be amended to name this exception rather than leaving the deviation unrecorded.
5. **`paths.py` "imported wherever a path is resolved"** — violated by every plan including Plan 1 (§1.7).
6. **`JobListingEvidence` "Do not add or rename fields"** — Plan 3 honours it exactly. Consequence: the D3 within-band ordering by effort has nowhere to live (§4, §5.1).
7. **`claims.yaml` row schema** — `retracted` required by Plan 4, optional in Plan 1 (§1.5).
8. **The ONE verdict vocabulary** — the strings are right everywhere; the *sixth token* for "no market" is not (`none` vs `other`, §1.3), and the set is duplicated five times (§5.4).
9. **Defect tags "closed set"** — Plan 4 keeps `DEFECT_TAGS` at exactly four ✓ but adds a second closed set `SHAPE_TAGS` (11 tags) and gates against `ALL_TAGS = DEFECT_TAGS + SHAPE_TAGS`. The plan argues the case explicitly ("Two closed vocabularies, and why there are two") and keeps the walk-back trigger on the contract's four. Acceptable, documented extension — but the contract text should be amended to name it, or a future reader will read `ALL_TAGS` as a contract breach.
10. **Requirement-row enums, evidence-block ids and chunking parameters, mock bands, `2026-08-09` dating** — exact in every plan. ✓
11. **Git rules** — all four stage named paths, never `git add -A`/`.`, never push, never `-c user.name`. ✓ One borderline case: Plan 2 Task 6 Step 7 stages the directory `docs/superpowers/research/2026-08-09-market-conventions` rather than its files. Still a named path; flagging only for completeness.

---

## VERDICT: **INCONSISTENT**

### Ordered list of edits to reconcile

**Before Plan 2 runs**

1. **Plan 2 Task 12** — add `company` to the `posting.yaml` field list in `modes/assess.md` §3 (the exact public employer name), and reconcile `language` and the `location` shape with Plan 1's SKILL.md table. Without this, every apply run after an assess run fails `check_letter.py` with `NO_COMPANY_IN_POSTING`. *(§1.4)*
2. **Plan 2, all six gates** — write exactly one receipt on the exit-2 path, with verdict `"could_not_run"`. *(§6.1)*
3. **Plan 1** — change the exit-2 receipt verdict from `"error"` to `"could_not_run"` in `check_personal_data.py`, `parse_verdicts.py`, `check_render_freshness.py`, `check_claims.py` and their tests. *(§1.1)*
4. **Plan 1** — add `"retracted"` to `check_claims.CLAIM_KEYS` as a presence check. *(§1.5)*
5. **New shared module** (write it in Plan 1, e.g. `scripts/vocab.py`) — one definition of the five verdicts, `insufficient_evidence`, the zh labels, the market keys and the "no table" token; import it from `check_apply`, `check_assessment`, `count_coverage`, `lint_no_prediction`, `check_shortlist`, `mock_vocab`. Choose `"other"` for the no-table token. *(§1.2, §1.3, §5.4, §5.5)*
6. **Plan 1** — add to `SKILL.md` layer 1: the apply-verdict block template + its required disclaimer, the skill-wide banned-output vocabulary + the published-employer-rubric exception, the §8 three-mechanism grounding summary, and the platform-limit stop rule (or explicitly hand the last one to Plan 3 Task 5). *(§4 §6 table)*
7. **Plan 1 / Plan 2** — decide who performs the §12 flagged FIT SNAPSHOT rewrite and its `scripts/lossless-allowlist.json` entry, and write the task. *(§2.2)*
8. **Plan 2 Task 6 Step 1** — commit `markets.json` and the four reviews into the repo *now*, as a Plan-1 prerequisite, instead of copying from a session scratchpad at execution time. *(§2.3)*

**Inside Plan 2**

9. **Plan 2 Task 3** — add the `quote=`-field exemption to `lint_no_prediction.py` for text inside a `MOCK-*-V1` block, with a test. *(§2.1)*
10. **Plan 2 Task 13** — treat `EXPIRED_REVIEW_BY` as a `WARN_` finding inside `check_assessment` (CI keeps it hard via `check_conventions --all`), matching spec §10 and `modes/assess.md` §9. *(§5.2)*
11. **Plan 2 Task 13** — add a `NO_STRATEGY_SECTION` / `NO_ACCEPTANCE_COLUMN` check that fires when the verdict is `likely_screen_out` or `blocked` and the strategy / 30-60-90 `验收标准` / roadmap `输出物` are absent. *(§5.2 step 10)*
12. **Plan 2 Task 13** — either call `journal.read_receipts` (as its Interfaces claim) to require upstream receipts, or drop the claim. *(§4 §11-12)*
13. **Plan 2 Task 1** — make the `conftest.py` step create-if-absent, matching Plan 3's wording. *(§5.1)*

**In each of Plans 2, 3, 4 (a new final task in each)**

14. Append the plan's scripts, mode file, reference files and agent files to `SKILL.md`'s `## Self-check` section and its gate table, and extend `scripts/tests/test_skill_structure.py`'s `skip` set for the new library-only modules (`opencli_meta.py`, `mock_vocab.py`, `mock_blocks.py`). **Without this the suite is red from Plan 2 onward.** *(§3.1)*
15. Add a mode-entry step: `python3 scripts/enter_mode.py --workspace <ws> --mode assess|discover|interview` in the mode file, and a `NO_MODE_ENTRY` / `MODE_FILE_CHANGED` check in `check_assessment` / `check_shortlist` / `check_mock`. Set `JOB_HUNT_MODE` there so receipts stop being mislabelled `apply`. *(§1.6, §2.5, §4.2)*

**Inside Plan 3**

16. Reconcile `modes/discover.md` Step 7's `insufficient_evidence` row with `check_shortlist.VERDICTS` — either drop the row entirely (recommended: a refusal state is not a shortlist row) or teach the gate about it. *(§5.1)*
17. Add the platform-limit stop rule to the `discover-inserts` SKILL.md block if Plan 1 does not carry it (edit 6). *(§6 table)*
18. Give `references/source-policy.md` an evaluable SKILL.md trigger and a named backstop, or accept it as a documented residual risk. *(§11-11)*

**Inside Plan 4**

19. Rename `mock_vocab.MARKET_KEYS` (or import the shared constant from edit 5). *(§1.2)*
20. Add the `sys.path.insert` guard to `check_mock.py` for parity with every other gate. *(§1.10)*

**Unassigned spec requirements — give each one an owner or an explicit written deferral**

21. `check_pages.py` and `check_word_limits.py` (§7 P2).
22. CI wiring for `check_skill_lossless.py` and `check_conventions.py --all` (§7 P1, §12).
23. The eval rebuild as iteration-2 (§10, last row — the spec says this implementation owns it, and no plan does).
24. Who writes `search-preferences.yaml` (§4.3).
25. Apply-mode entry conditions against the five-verdict vocabulary (§5.3).
26. Retract SKILL.md's "discover, assess and interview are not yet built in this repo" once they are (§3.3).
27. Enforce the 「基于卡片信息的初判」 stamp in `shortlist.md`, not only `provisional: true` in `shortlist.yaml` (§5.1 step 6).
28. Delete README.md's duplicated 8-step process list (§9) and add `cv-source.txt`, `coverage.json`, `master-fingerprint.json` to the §4.3 workspace layout.
