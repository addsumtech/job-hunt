# Migration and P0 Defect Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the `job-application` skill into the `job-hunt` repo with its git history intact, fix every defect that has been measured live in it, and put the layer-1 / layer-1.5 / layer-2 / layer-3 structure in place — so that after this plan `job-hunt` does everything `job-application` does today, with a deterministic gate behind each rule a program can decide.

**Architecture:** The repo root *is* the skill. `SKILL.md` (layer 1) holds every rule whose omission nothing would report; `modes/apply.md` (layer 1.5) holds the apply pipeline and is loaded unconditionally on mode entry, with its content hash written to `journal.jsonl` as the backstop; `references/*.md` (layer 2) hold branch-specific craft detail; `scripts/*.py` (layer 3) hold everything a program can decide. Every gate script shares one CLI contract, imports `scripts/journal.py`, and leaves a receipt in the workspace journal — so "the gate passed" and "the gate never ran" stop looking identical.

**Tech Stack:** Python 3 (stdlib + PyYAML + python-docx only), pytest, git, LaTeX (tectonic) for PDF output.

## Global Constraints

- Repo root: `/Users/donghanglyu/code_project/job-hunt`. The repo root IS the skill. Git is already initialised; the design spec is committed at `docs/superpowers/specs/2026-08-09-job-hunt-skill-design.md`.
- Python 3, stdlib + PyYAML + python-docx only (already in `requirements.txt`). pytest for tests.
- Run the suite with: `python3 -m pytest scripts/tests -q` (from the repo root). Verified: this command works from the repo root after the migration.
- Every gate script obeys this CLI contract:
  `python3 scripts/<name>.py --workspace <path> [script-specific args]`
  `exit 0` = gate passed. `exit 1` = gate failed (findings printed to stdout, one per line, each prefixed with a stable UPPERCASE code, e.g. `UNSOURCED: ...`, `STALE: ...`, `NO_SOURCE_ID: ...`). `exit 2` = could not run (missing input file); message to stderr.
  **One named exception, and only one in this plan:** `scripts/check_skill_lossless.py` is a repo-level CI check, not a workspace gate. It takes no `--workspace`, imports no `journal`, and writes no receipt; it exits 0 (lossless) / 1 (content lost or a stale deletion entry) / 2 (the baseline could not be read). It is listed in SKILL.md's gate table and self-check under its own **CI** line rather than under "Ran, with a receipt", because a checklist that promises evidence which can never exist teaches the reader that the evidence line is decorative. (Plan 3 declares a second exception for `check_opencli_result.py`; no other script may deviate.)
- Every gate appends **exactly one** receipt line to `<workspace>/journal.jsonl` before exiting — **on every exit path, including exit 2.** A gate that dies without a receipt is indistinguishable from a gate that was never run, which is risk-register entry #12. On the "could not run" path the verdict is **`"could_not_run"`** — never `"error"`, which says that something went wrong without saying whether the gate reached a judgement. The single exception: if the workspace directory itself does not exist there is nothing to append to, so print to stderr and return 2 with no receipt.
- **Every gate opens `main()` with the workspace guard, spelled identically, immediately after `ws = pathlib.Path(args.workspace)`:**
  ```python
      if not ws.is_dir():
          # journal.receipt() would mkdir it, and a gate that creates the
          # workspace it is auditing has manufactured its own evidence.
          print(f"cannot run {GATE}: workspace {ws} does not exist", file=sys.stderr)
          return 2
  ```
  `journal.append()` creates the directory it writes into, so without this guard a typo'd `--workspace` silently materialises an empty workspace — and the resume-in-progress lookup then finds a shell, which is the exact harm `paths.py`'s own docstring names. The comment is part of the guard: it is the only place a reader learns why the one-receipt-per-exit rule yields here. `scripts/enter_mode.py` is the ONE script allowed to create a workspace — it opens the mode, and a brand-new application has no directory yet. `test_no_gate_creates_a_workspace_it_was_pointed_at` (Task 19) holds the eight upstream gates to this, and `test_a_missing_workspace_is_exit_2_and_creates_nothing` covers `check_apply`.
- Receipt verdicts are a closed set: `"pass" | "fail" | "could_not_run" | "recorded"`. `"recorded"` is for a run that reports or records rather than gates (`check_render_freshness --record`, `check_claims --record`). `check_apply.PASSING_VERDICTS = ("pass", "recorded")`, so any verdict outside this set reads as a failure downstream — which is why the set is closed rather than free text.
- Every gate exposes `main(argv=None) -> int` and ends with `if __name__ == "__main__": sys.exit(main())`, so tests can call `main([...])` directly.
- **The closed vocabularies live in `scripts/vocab.py` (Task 5) and are imported, never re-spelled.** A closed set written out twice is a closed set that will drift; the same five verdicts were hard-coded in five modules across the four plans before this module existed. Every later plan imports from it too.
  The ONE verdict vocabulary (spec D3), these exact strings, everywhere:
  `"strong_apply" | "worth_applying" | "stretch" | "likely_screen_out" | "blocked"`
  Orthogonal refusal state (NOT a sixth level): `"insufficient_evidence"`.
  Human-facing zh labels: 强烈建议投 / 值得投 / 可以冲刺 / 大概率被筛掉 / 硬性阻断 / 证据不足—不出结论.
  discover-stage verdicts carry `provisional: true` and MUST NOT be copied into an assessment.
  Market keys: `cn / nl / de / uk / us`, plus the one token for "no market table": **`other`** (never `none`).
- Requirement-row enums (spec 5.2 step 6), these exact strings:
  `level: "required" | "preferred" | "unclear"`; `screening: "knockout" | "weighted" | "nice_to_have"`; `match: "strong" | "partial" | "gap" | "no_evidence"`; `recency: "current" | "recent" | "dated" | "undated"`; `effort: "quick" | "evening" | "multi_day" | "not_closable"`.
- Mock-interview bands (spec 5.4), deliberately unnumbered so they cannot be averaged:
  `"not_present" | "asserted" | "instanced" | "held_under_probe"`. Non-band flag: `"contradicted"`. Defect tags (closed set): `"UNSOURCED-FACT" | "OVER-CLAIM" | "CONTRADICTED" | "PROBE-COLLAPSE"`.
- **`scripts/paths.py` is imported wherever a path is resolved.** No script re-derives a profile, workspace, search, answer-bank, search-preferences, mode-file or skill-root path with `.parents[n]` or a string join. The one place the load-bearing layout is defined is worth nothing if every caller re-derives it — that is how a resume lookup silently stops finding the previous workspace.
- Evidence block ids: `"CV-%03d"` and `"JD-%03d"`. Chunking: max 900 chars per block, max 80 blocks per source, split on blank lines or a newline preceding a bullet/number/CJK numeral, over-long paragraphs sentence-split on `[。.!?]`, drop chunks under 8 chars.
- `claims.yaml` row schema (append-only): `term` (str), `where` (str, e.g. `"tailored-profile.yaml:skills.infra"`), `source_kind` (`"profile-line" | "session-answer" | "fetched-artifact"`), `source_ref` (str), `session_date` (str, `YYYY-MM-DD`), `retracted` (str | null — null, or `"walk-back-YYYY-MM-DD"`).
- `JobListingEvidence` row schema (shortlist.yaml rows): `id, title, company, location, salary, url, source_site, source_id, extraction_method, retrieved_at, quality, verification, raw_text, why_matched, verdict, provisional`.
- Today is **2026-08-09**. Use it for filenames and any dated example. Never call an unstamped date helper in an example; show the literal date.
- **Git rules (the repo owner's standing instructions — violating these is a plan defect):** stage NAMED PATHS only; never `git add -A`, never `git add .`. **NEVER push** — commit locally only, no `git push` in any step. Do not pass `-c user.name` / `-c user.email`; the repo's config is already correct.
- **Testing discipline (spec §7).** Every check's tests must pin the QUIET case as hard as the firing case. A check that cries wolf on ordinary output is worse than no check, because readers learn to skip that line. A test that only imports a module proves the button exists, not that pressing it does anything — that is exactly how 51/51 green tests hid a renderer that could not produce a single letter PDF.
- **What `check_skill_lossless.py` does NOT prove (spec §12).** It measures whether the bytes still exist, not whether the content reaches context at the moment it is needed. A refactor can score a perfect lossless result and still degrade the skill, because the regression is in *when* content arrives, not *whether* it survives. Content preservation is necessary and nowhere near sufficient. The only real test of the layering change in Task 20 is re-running the end-to-end evals afterwards and reading what the outputs are missing. Never quote a size number or a lossless score as evidence of quality.

---

## File Structure

Everything created or modified by this plan. One responsibility per file.

**Migrated verbatim from `job-application` (Task 2), not otherwise touched:**

| Path | Responsibility |
|---|---|
| `references/candidate-situations.md` | The eight non-standard-candidate playbooks. |
| `references/cv-craft.md` | Cluster conventions, ATS mechanics, bullet craft, section ordering. |
| `references/gap-analysis.md` | Gap table, quantification ladder, NOT-ALLOWED table, FIT SNAPSHOT. |
| `references/interview-prep.md` | Interview-readiness brief contract. |
| `references/job-posting-extraction.md` | Posting fetch integrity + the full extraction field table. |
| `references/motivation-letter.md` | Letter skip gate, structure, market calibration, salutations. |
| `references/rirekisho.md` | Japan 履歴書 fork. |
| `references/role-families.md` | Nine role-family recipes. |
| `references/structured-applications.md` | Criterion-scored applications and the review substitution. |
| `agents/ats-screener.md`, `agents/recruiter-screener.md`, `agents/hiring-manager.md` | The three judge personas and their exact output blocks. |
| `assets/profile.example.yaml` | Canonical profile schema. |
| `requirements.txt`, `.gitignore` | Deps and ignores. |

**Deleted in Task 2:** `assets/cv/template.tex`, `assets/letter/template.tex` (dead and drifted; nothing loads them).

**New or modified by this plan:**

| Path | Responsibility |
|---|---|
| `README.md` | Repo-level orientation. **Modified (Task 21):** the duplicated 8-step process list is deleted and points at `SKILL.md`; the layout section is corrected and gains the workspace layout. |
| `scripts/journal.py` | Append-only run journal + gate receipts. Imported by every gate. |
| `scripts/paths.py` | Every filesystem location the skill uses. The one place the workspace path shape is defined. |
| `scripts/vocab.py` | Every closed vocabulary in the skill, in one module. Imported by every gate in this plan and in Plans 2–4. |
| `scripts/rounds.py` | Read/merge `judge-round-<n>.json` without clobbering another writer's keys. |
| `scripts/check_skill_lossless.py` | Asserts every substantive line of the old tree is findable in the new tree. |
| `scripts/lossless-allowlist.json` | Waived lines and deliberately deleted files, each with a written reason. |
| `scripts/render_cv.py` | CV renderer. **Modified:** shared `_engine_cmd()`, normalized market→cluster resolution with a loud unknown-market warning, `meta.headings` / `meta.section_order` unknown-key warnings. |
| `scripts/render_letter.py` | Letter renderer. **Modified:** uses `render_cv._engine_cmd()` (fixes the engine bug), module-level `subprocess` import. |
| `scripts/render_rirekisho.py` | 履歴書 renderer. **Modified:** unparseable dates are collected, reported by field, and fatal for 学歴・職歴. |
| `scripts/check_personal_data.py` | Gate: protected personal data cannot reach a Cluster-1 CV, and an unrecognised market is never silent. |
| `scripts/parse_verdicts.py` | Gate: parses the three judges' VERDICT blocks; fail-closed on anything but exact PASS/REJECT. |
| `scripts/check_render_freshness.py` | Gate: records the sha256 of every file pasted into the judges at dispatch, and voids the round on mismatch. |
| `scripts/check_claims.py` | Gate: every new term in the tailored profile traces to `claims.yaml`; the master profile was not mutated. |
| `scripts/lint_cv.py` | Gate: clichés, weak bullet openers, over-long bullets, repeated opening verbs. |
| `scripts/check_letter.py` | Gate: markdown-in-body, word/paragraph counts, duplicated sender name, company/role vs `posting.yaml`. |
| `scripts/check_pages.py` | Gate: the rendered PDF's page count against the length table in `references/cv-craft.md`, and the letter's one-page rule. |
| `scripts/check_word_limits.py` | Gate: per-criterion word counts in a structured application's supporting statement. |
| `scripts/enter_mode.py` | Writes the mode-entry record (mode file content hash) to `journal.jsonl`. The layer-1.5 backstop. |
| `scripts/check_apply.py` | Gate: composes all of the above plus the honest-stop classification and the interview brief. |
| `SKILL.md` | **Rewritten in Task 20.** Layer 1: everything whose omission nothing reports, carried verbatim, plus the self-check list. |
| `modes/apply.md` | **New in Task 20.** Layer 1.5: the apply pipeline (old Steps 0–7.5), the apply entry conditions and the `honest-stop.yaml` schema. |
| `Makefile`, `.github/workflows/checks.yml` | **New in Task 22.** CI: pytest + `check_skill_lossless.py` + `check_conventions.py --all`, so spec §12's "进 CI" is a file and not an intention. |
| `scripts/tests/test_*.py` | One test module per script above. |

---

### Task 1: Verify the preservation commits already landed in the `job-application` repo

> **This task was already executed on 2026-08-10, before this plan was finalised.** It is kept as a
> *verification* task rather than deleted, because Task 2 migrates that repo's history and will
> silently carry a dirty tree's worth of missing work if this state is not what you think it is.
>
> Background: `/Users/donghanglyu/.claude/skills/job-application` had ~1500 lines uncommitted since
> 2026-06-04. Migrating a dirty tree would either lose that work or fold it into one shapeless
> commit, so it was committed there first, in five coherent groups, staging named paths only.
> **The commit messages differ from the ones an earlier draft of this plan prescribed — that is
> expected and is not a defect.** What matters is that the five commits exist, the tree is clean,
> and the suite is green.

**Files:**
- Read only: `/Users/donghanglyu/.claude/skills/job-application/**`
- Test: `/Users/donghanglyu/.claude/skills/job-application/scripts` (existing suite, must be green)

**Interfaces:**
- Consumes: nothing.
- Produces: a verified-clean `job-application` repo whose tip contains every file Task 2 migrates.

- [ ] **Step 1: Confirm the five preservation commits are present, on top of `141bef6`**
    Run:
    ```bash
    cd /Users/donghanglyu/.claude/skills/job-application && git log --oneline -6
    ```
    Expected — these six lines, in this order (the five preservation commits, then the 2026-06-04 base):
    ```
    864ad7f docs: craft/gap/posting/letter guidance and the orchestrator flow
    6002e49 feat: candidate situations, role families, structured applications, interview brief
    7141315 feat: renderer overhaul — i18n headings, section order, links, CJK, profile schema
    0940f6d feat: Japan rirekisho renderer and its reference
    9404bbe feat: recruiter/HR screener as a third judge in the review loop
    141bef6 docs: consistent 'dual-lens' wording in fast-path note
    ```
    If `141bef6` is the tip — i.e. the five commits are absent — the preservation never happened and
    the ~1500 lines are still uncommitted or, worse, lost. **STOP and report**; do not migrate.

- [ ] **Step 2: Confirm the working tree is clean**
    Run: `cd /Users/donghanglyu/.claude/skills/job-application && git status --short`
    Expected: **no output at all.**
    If anything appears, someone edited this tree after the preservation commits. STOP and report it —
    migrating now would leave that work behind with no error.

- [ ] **Step 3: Confirm the suite is green**
    Run: `cd /Users/donghanglyu/.claude/skills/job-application/scripts && python3 -m pytest tests -q`
    Expected: PASS — `51 passed`. A red tree must not be migrated.

- [ ] **Step 4: Confirm the repo still has no remote**
    Run: `cd /Users/donghanglyu/.claude/skills/job-application && git remote -v`
    Expected: **no output.** This repo has no remote and must not gain one. Nothing in this plan pushes.

There is nothing to commit in this task.

---

### Task 2: Migrate into `job-hunt` with history, delete the dead templates

Copying files would throw away the evidence that lines were *moved* rather than rewritten — which is the whole discipline this migration is held to. Merge the history instead. The paths do not collide (`job-hunt` currently holds only `docs/`), so an unrelated-histories merge lands the old tree at its exact paths. Verified: the merge applies cleanly and `python3 -m pytest scripts/tests -q` passes from the new repo root.

**Files:**
- Modify: `/Users/donghanglyu/code_project/job-hunt` (git history and working tree)
- Delete: `assets/cv/template.tex`, `assets/letter/template.tex`
- Create: `scripts/lossless-allowlist.json`

**Interfaces:**
- Consumes: the clean `job-application` `main` from Task 1.
- Produces: tag `job-application-baseline` (the pre-migration tip of `job-application`, the immutable baseline every later `check_skill_lossless.py` run compares against); `scripts/lossless-allowlist.json` with the shape `{"_comment": str, "waived": {sha1_16: reason}, "deleted_files": {relpath: reason}}`.

- [ ] **Step 1: Fetch the old history into the new repo and tag the baseline**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git remote add job-application /Users/donghanglyu/.claude/skills/job-application
    git fetch job-application 'refs/heads/main:refs/heads/job-application-main'
    git tag job-application-baseline job-application-main
    git remote remove job-application
    ```
    A tag, not a branch, is what `check_skill_lossless.py` points at: branches move, and a baseline that moves stops being a baseline.

- [ ] **Step 2: Merge, keeping both histories**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git merge --allow-unrelated-histories --no-edit -m "merge: absorb the job-application skill with its history

job-hunt's apply mode IS job-application. Merging rather than copying keeps the
evidence that lines were moved and not rewritten — the only mechanical defence
against a 'lossless refactor' that quietly condenses operational rules.
Baseline for scripts/check_skill_lossless.py: tag job-application-baseline." \
      job-application-main
    ```
    Expected: a merge commit, no conflicts. `ls` now shows `SKILL.md README.md agents assets docs references requirements.txt scripts`.

- [ ] **Step 3: Verify the migrated suite is green from the new repo root**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests -q`
    Expected: PASS — `51 passed`.

- [ ] **Step 4: Delete the two dead LaTeX templates**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    grep -rn "template" scripts/*.py || true          # expect: only the two prose strings in render_letter.py's warning
    git rm assets/cv/template.tex assets/letter/template.tex
    ```
    Both files are dead and actively misleading: nothing in `scripts/` loads them, both renderers assemble LaTeX inline (`render_cv.build_latex`, `render_letter.build_latex`), and both templates have drifted from what is actually generated — `assets/cv/template.tex` has no `inputenc`/`fontenc`/`graphicx`, no xeCJK branch, and no photo/personal-data block. Anyone "experimenting with styling" there is editing a file that no longer resembles the output.

- [ ] **Step 5: Create the lossless allowlist with both deletions recorded**
    Create `scripts/lossless-allowlist.json`:
    ```json
    {
      "_comment": "Deliberate losses from the job-application baseline (tag job-application-baseline). 'waived' entries key on a sha1 of the normalized line, so editing the line revokes its waiver and it comes back for review. 'deleted_files' names whole files that were removed on purpose; check_skill_lossless.py asserts each is genuinely absent, so a stale entry here fails the build instead of rotting.",
      "waived": {},
      "deleted_files": {
        "assets/cv/template.tex": "Dead and drifted. Nothing loads it (grep of scripts/*.py matches only two prose strings inside render_letter.py's warning message); render_cv.build_latex assembles the real preamble inline. The file lacks inputenc/fontenc/graphicx, the xeCJK branch and the photo/personal-data block that render_cv actually emits, so its header ('Edit this to experiment with styling') points a reader at a file that cannot affect the output.",
        "assets/letter/template.tex": "Same class. render_letter.build_latex assembles the letter's LaTeX inline; this 14-line placeholder file is loaded by nothing and has drifted from the generated source."
      }
    }
    ```

- [ ] **Step 6: Commit the deletions and the allowlist**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/lossless-allowlist.json
    git commit -m "chore: delete the dead LaTeX templates, open the lossless allowlist

assets/cv/template.tex and assets/letter/template.tex are loaded by nothing and
have drifted from what the renderers emit. Each deletion is recorded in
scripts/lossless-allowlist.json with its reason so it stays a decision someone
made rather than a casualty of the migration."
    ```
    (`git rm` in Step 4 already staged both deletions; only the new file needs adding.)

- [ ] **Step 7: Verify the baseline tag is readable**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && git show job-application-baseline:SKILL.md | head -3 && git log --oneline -3`
    Expected: the old SKILL.md frontmatter (`---`, `name: job-application`, `description: >-`) prints, and the log shows the deletion commit on top of the merge.

---

### Task 3: `scripts/journal.py` — receipts, so a skipped gate stops looking clean

**Files:**
- Create: `scripts/journal.py`
- Test: `scripts/tests/test_journal.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `append(workspace: pathlib.Path, record: dict) -> None`
  - `receipt(workspace: pathlib.Path, gate: str, input_hashes: dict[str, str], verdict: str, findings: list[str] | None = None) -> dict`
  - `sha256_file(path: pathlib.Path) -> str`
  - `read_receipts(workspace: pathlib.Path, gate: str | None = None) -> list[dict]`
  - `current_mode(workspace: pathlib.Path) -> str` — the `mode` of the most recent `mode_entry` record, else `"unknown"`

- [ ] **Step 1: Write the failing test**
    Create `scripts/tests/test_journal.py`:
    ```python
    import json
    import pathlib
    import re
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    import journal


    def test_append_creates_the_file_and_appends_one_line_per_record(tmp_path):
        ws = tmp_path / "acme-engineer-2026-08-09"
        journal.append(ws, {"a": 1})
        journal.append(ws, {"a": 2})
        lines = (ws / "journal.jsonl").read_text(encoding="utf-8").splitlines()
        assert [json.loads(x)["a"] for x in lines] == [1, 2]


    def test_sha256_file_matches_hashlib(tmp_path):
        import hashlib
        p = tmp_path / "cv.md"
        p.write_bytes(b"# Test User\n")
        assert journal.sha256_file(p) == hashlib.sha256(b"# Test User\n").hexdigest()


    def test_receipt_has_the_contract_fields_and_lands_in_the_journal(tmp_path):
        ws = tmp_path / "ws"
        rec = journal.receipt(ws, "check_claims", {"tailored-profile.yaml": "ab" * 32},
                              "pass", ["UNSOURCED: nothing"])
        assert set(rec) == {"ts", "mode", "action", "gate", "input_hashes",
                            "verdict", "findings", "receipt_hash"}
        assert rec["action"] == "gate"
        assert rec["gate"] == "check_claims"
        assert rec["verdict"] == "pass"
        assert rec["findings"] == ["UNSOURCED: nothing"]
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", rec["ts"])
        assert re.fullmatch(r"[0-9a-f]{64}", rec["receipt_hash"])
        on_disk = json.loads((ws / "journal.jsonl").read_text(encoding="utf-8").splitlines()[0])
        assert on_disk == rec


    def test_receipt_hash_covers_the_other_fields(tmp_path):
        a = journal.receipt(tmp_path / "a", "g", {}, "pass")
        b = journal.receipt(tmp_path / "b", "g", {}, "fail")
        assert a["receipt_hash"] != b["receipt_hash"]


    def test_findings_defaults_to_an_empty_list_not_none(tmp_path):
        rec = journal.receipt(tmp_path / "ws", "g", {}, "pass")
        assert rec["findings"] == []


    def test_read_receipts_filters_by_gate_and_ignores_non_gate_records(tmp_path):
        ws = tmp_path / "ws"
        journal.receipt(ws, "lint_cv", {}, "pass")
        journal.receipt(ws, "check_claims", {}, "fail")
        journal.append(ws, {"action": "mode_entry", "mode": "apply"})
        assert [r["gate"] for r in journal.read_receipts(ws)] == ["lint_cv", "check_claims"]
        assert [r["verdict"] for r in journal.read_receipts(ws, "check_claims")] == ["fail"]


    def test_read_receipts_survives_a_half_written_line(tmp_path):
        """A truncated line must not blind the reader — the whole point of the
        journal is that a later gate can see whether an earlier one ran."""
        ws = tmp_path / "ws"
        journal.receipt(ws, "lint_cv", {}, "pass")
        with open(ws / "journal.jsonl", "a", encoding="utf-8") as fh:
            fh.write('{"action": "gate", "ga\n')
        journal.receipt(ws, "check_claims", {}, "pass")
        assert [r["gate"] for r in journal.read_receipts(ws)] == ["lint_cv", "check_claims"]


    def test_read_receipts_on_a_workspace_with_no_journal_is_empty(tmp_path):
        assert journal.read_receipts(tmp_path / "never-used") == []


    def test_the_receipt_mode_comes_from_the_latest_mode_entry_not_a_default(tmp_path):
        """`mode` is read from the journal, not guessed. An environment-variable
        default of "apply" is worse than "unknown": nothing in any mode sets the
        variable, so every receipt written by discover, assess and interview would
        be stamped `apply` and a journal read months later would lie confidently."""
        ws = tmp_path / "ws"
        assert journal.current_mode(ws) == "unknown"
        assert journal.receipt(ws, "g", {}, "pass")["mode"] == "unknown"
        journal.append(ws, {"action": "mode_entry", "mode": "discover"})
        assert journal.current_mode(ws) == "discover"
        assert journal.receipt(ws, "g", {}, "pass")["mode"] == "discover"
        journal.append(ws, {"action": "mode_entry", "mode": "apply"})
        assert journal.receipt(ws, "g", {}, "pass")["mode"] == "apply"
    ```

- [ ] **Step 2: Run test to verify it fails**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_journal.py -q`
    Expected: FAIL with `ModuleNotFoundError: No module named 'journal'`

- [ ] **Step 3: Write minimal implementation**
    Create `scripts/journal.py`:
    ```python
    #!/usr/bin/env python3
    """The append-only run journal, and the receipt every gate leaves in it.

    Risk-register #12: a gate that was skipped produces no output, and no output
    looks exactly like a clean run. So each gate writes one receipt here before it
    exits — on every exit path, including the "could not run" one — and a mode may
    not claim success without quoting its receipts. The receipt carries the hashes
    of what the gate actually read, so "the gate passed" is a claim about specific
    bytes rather than about a moment in time.
    """
    from __future__ import annotations

    import datetime
    import hashlib
    import json
    import pathlib


    def append(workspace, record: dict) -> None:
        """Append one JSON record as a line to <workspace>/journal.jsonl."""
        workspace = pathlib.Path(workspace)
        workspace.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        with open(workspace / "journal.jsonl", "a", encoding="utf-8") as fh:
            fh.write(line + "\n")


    def sha256_file(path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()


    def _records(workspace):
        """Every parseable JSON record in the journal, oldest first."""
        path = pathlib.Path(workspace) / "journal.jsonl"
        if not path.exists():
            return []
        out = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue          # a half-written line must not blind the reader
            if isinstance(rec, dict):
                out.append(rec)
        return out


    def current_mode(workspace) -> str:
        """The mode of the most recent mode_entry record, or "unknown".

        Read from the journal, never guessed. The obvious alternative — an
        environment variable with a default — is worse than useless here: nothing
        in any mode sets it, so every receipt written by discover, assess and
        interview would be stamped with the default and a journal read months later
        would be confidently wrong about which mode produced which evidence.
        "unknown" is the honest answer when nothing recorded an entry, and it is
        also the shape check_apply's NO_MODE_ENTRY finding exists to catch.
        """
        mode = "unknown"
        for rec in _records(workspace):
            if rec.get("action") == "mode_entry" and rec.get("mode"):
                mode = str(rec["mode"])
        return mode


    def receipt(workspace, gate: str, input_hashes: dict, verdict: str,
                findings=None) -> dict:
        """Build, journal and return one gate receipt.

        `verdict` is one of "pass" | "fail" | "could_not_run" | "recorded". `mode`
        is read from the latest mode_entry record in this workspace's journal
        (see current_mode) rather than passed in, because the gate signature is
        fixed by the shared contract and does not carry it.
        """
        record = {
            "ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "mode": current_mode(workspace),
            "action": "gate",
            "gate": gate,
            "input_hashes": dict(input_hashes or {}),
            "verdict": verdict,
            "findings": list(findings or []),
        }
        payload = json.dumps(record, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"))
        record["receipt_hash"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        append(workspace, record)
        return record


    def read_receipts(workspace, gate: str | None = None) -> list:
        """Every gate receipt in the journal, oldest first, optionally one gate."""
        return [rec for rec in _records(workspace)
                if rec.get("action") == "gate"
                and (gate is None or rec.get("gate") == gate)]
    ```

- [ ] **Step 4: Run test to verify it passes**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_journal.py -q`
    Expected: PASS — `9 passed`

- [ ] **Step 5: Commit**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/journal.py scripts/tests/test_journal.py
    git commit -m "feat(journal): gate receipts in journal.jsonl

A skipped gate and a clean gate emit the same silence. Every gate now writes one
receipt — gate name, the sha256 of what it read, verdict, findings — so a mode
cannot claim success without evidence a downstream gate can check."
    ```

---

### Task 4: `scripts/paths.py` — one definition of the workspace shape

The `<company>-<role>-<YYYY-MM-DD>` directory shape is load-bearing: the "resume an interrupted application" lookup finds a workspace by that shape, so a run that invents its own layout breaks resumption silently. One module owns it.

**Files:**
- Create: `scripts/paths.py`
- Test: `scripts/tests/test_paths.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `PROFILES_ROOT: pathlib.Path` (`~/.claude/job-profiles`)
  - `SKILL_ROOT: pathlib.Path` (the repo root — `scripts/`'s parent)
  - `slugify(text: str) -> str`
  - `profile_dir(name: str) -> pathlib.Path`
  - `master_profile(name: str) -> pathlib.Path` (`<profile_dir>/profile.yaml`)
  - `search_prefs(name: str) -> pathlib.Path` (`<profile_dir>/search-preferences.yaml`)
  - `answer_bank(name: str) -> pathlib.Path` (`<profile_dir>/answer-bank.md`)
  - `search_dir(name: str, slug: str) -> pathlib.Path` (`<profile_dir>/searches/<slug>`)
  - `workspace(name: str, company: str, role: str, date: str) -> pathlib.Path` (`<profile_dir>/applications/<company>-<role>-<YYYY-MM-DD>`)
  - `mode_file(mode: str, root=None) -> pathlib.Path` (`<root or SKILL_ROOT>/modes/<mode>.md`)
  - `lossless_allowlist(root=None) -> pathlib.Path` (`<root or SKILL_ROOT>/scripts/lossless-allowlist.json`)

- [ ] **Step 1: Write the failing test**
    Create `scripts/tests/test_paths.py`:
    ```python
    import pathlib
    import sys

    import pytest

    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    import paths


    def test_profiles_root_is_under_the_claude_dir():
        assert paths.PROFILES_ROOT == pathlib.Path.home() / ".claude" / "job-profiles"


    def test_skill_root_is_the_repo_root_and_holds_this_test():
        """Every script that needs the skill root asks paths for it. A script that
        re-derives it with .parent.parent works until someone moves the file."""
        assert paths.SKILL_ROOT == pathlib.Path(__file__).resolve().parent.parent.parent
        assert (paths.SKILL_ROOT / "scripts" / "paths.py").is_file()


    def test_mode_file_and_allowlist_resolve_under_an_explicit_root(tmp_path):
        assert paths.mode_file("apply", tmp_path) == tmp_path / "modes" / "apply.md"
        assert paths.mode_file("apply") == paths.SKILL_ROOT / "modes" / "apply.md"
        assert paths.lossless_allowlist(tmp_path) == \
            tmp_path / "scripts" / "lossless-allowlist.json"


    @pytest.mark.parametrize("raw,expected", [
        ("Acme Corp.", "acme-corp"),
        ("Senior ML Engineer", "senior-ml-engineer"),
        ("  Donghang  ", "donghang"),
        ("R&D / Imaging", "r-d-imaging"),
        ("ASML Netherlands B.V.", "asml-netherlands-b-v"),
    ])
    def test_slugify(raw, expected):
        assert paths.slugify(raw) == expected


    def test_slugify_keeps_cjk_so_a_chinese_employer_does_not_become_an_empty_name():
        assert paths.slugify("字节跳动") == "字节跳动"
        assert paths.slugify("北京 字节跳动") == "北京-字节跳动"


    def test_workspace_shape_is_company_role_date(tmp_path, monkeypatch):
        monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path)
        ws = paths.workspace("Donghang", "Acme Corp.", "Senior ML Engineer", "2026-08-09")
        assert ws == tmp_path / "donghang" / "applications" / "acme-corp-senior-ml-engineer-2026-08-09"


    def test_workspace_rejects_a_date_that_is_not_iso(tmp_path, monkeypatch):
        """A bad date must not silently produce a directory the resume lookup
        will never find again."""
        monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path)
        with pytest.raises(ValueError):
            paths.workspace("Donghang", "Acme", "Engineer", "Aug 9 2026")


    def test_the_shared_spine_paths(tmp_path, monkeypatch):
        monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path)
        d = tmp_path / "donghang"
        assert paths.profile_dir("Donghang") == d
        assert paths.master_profile("Donghang") == d / "profile.yaml"
        assert paths.search_prefs("Donghang") == d / "search-preferences.yaml"
        assert paths.answer_bank("Donghang") == d / "answer-bank.md"
        assert paths.search_dir("Donghang", "2026-08-09-MRI recon NL") == \
            d / "searches" / "2026-08-09-mri-recon-nl"


    def test_no_path_helper_creates_anything_on_disk(tmp_path, monkeypatch):
        """These are pure path builders. A helper that mkdir'd would create an
        empty workspace on a typo and make the resume lookup find a shell."""
        monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path)
        paths.workspace("Donghang", "Acme", "Engineer", "2026-08-09")
        paths.search_dir("Donghang", "slug")
        assert list(tmp_path.iterdir()) == []
    ```

- [ ] **Step 2: Run test to verify it fails**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_paths.py -q`
    Expected: FAIL with `ModuleNotFoundError: No module named 'paths'`

- [ ] **Step 3: Write minimal implementation**
    Create `scripts/paths.py`:
    ```python
    #!/usr/bin/env python3
    """Every filesystem location job-hunt uses, in one module.

    The <company>-<role>-<YYYY-MM-DD> workspace shape is load-bearing: the
    "resume an in-progress application" lookup finds a prior run by that shape, so
    a mode that invents its own layout orphans the previous workspace and
    re-interviews the user from scratch with no error anywhere. Changing
    `workspace()` changes that behaviour for every mode at once — which is the
    point of it living here rather than in four mode files.

    These are pure path builders: nothing here touches the disk. A helper that
    created directories would materialise an empty workspace on a typo, and the
    resume lookup would then find a shell and offer to continue from it.
    """
    from __future__ import annotations

    import pathlib
    import re
    import unicodedata

    PROFILES_ROOT = pathlib.Path.home() / ".claude" / "job-profiles"
    # The repo root IS the skill. Every script that needs it asks here rather than
    # writing `.parent.parent` again: a hand-derived root is correct until someone
    # moves one file, and then it is wrong in a way that only shows up at runtime.
    SKILL_ROOT = pathlib.Path(__file__).resolve().parent.parent

    # Keep ASCII alphanumerics and CJK/kana/hangul; everything else becomes a
    # separator. Dropping CJK would turn a Chinese employer name into an empty
    # slug and collapse two different companies onto the same directory.
    _KEEP = re.compile(
        r"[^0-9a-z"
        r"぀-ヿ"      # kana
        r"㐀-䶿"      # CJK ext A
        r"一-鿿"      # CJK unified
        r"가-힯"      # hangul
        r"]+"
    )
    _ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


    def slugify(text: str) -> str:
        s = unicodedata.normalize("NFKC", str(text or "")).lower()
        return _KEEP.sub("-", s).strip("-")


    def profile_dir(name: str) -> pathlib.Path:
        return PROFILES_ROOT / slugify(name)


    def master_profile(name: str) -> pathlib.Path:
        return profile_dir(name) / "profile.yaml"


    def search_prefs(name: str) -> pathlib.Path:
        return profile_dir(name) / "search-preferences.yaml"


    def answer_bank(name: str) -> pathlib.Path:
        return profile_dir(name) / "answer-bank.md"


    def search_dir(name: str, slug: str) -> pathlib.Path:
        return profile_dir(name) / "searches" / slugify(slug)


    def workspace(name: str, company: str, role: str, date: str) -> pathlib.Path:
        """<profile_dir>/applications/<company>-<role>-<YYYY-MM-DD>.

        `date` is validated rather than slugified: it is the only part of the name
        another run parses back out, and an unparseable one is a workspace nobody
        finds again.
        """
        if not _ISO_DATE.match(str(date)):
            raise ValueError(f"date must be YYYY-MM-DD, got {date!r}")
        stem = f"{slugify(company)}-{slugify(role)}-{date}"
        return profile_dir(name) / "applications" / stem


    def mode_file(mode: str, root=None) -> pathlib.Path:
        """<skill root>/modes/<mode>.md — the layer-1.5 file for a mode."""
        return (pathlib.Path(root) if root else SKILL_ROOT) / "modes" / f"{mode}.md"


    def lossless_allowlist(root=None) -> pathlib.Path:
        return (pathlib.Path(root) if root else SKILL_ROOT) / "scripts" / \
            "lossless-allowlist.json"
    ```

- [ ] **Step 4: Run test to verify it passes**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_paths.py -q`
    Expected: PASS — `13 passed` (6 plain tests + 5 parametrized `test_slugify` cases + the 2 new ones).

- [ ] **Step 5: Commit**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/paths.py scripts/tests/test_paths.py
    git commit -m "feat(paths): one definition of the profile and workspace layout

The <company>-<role>-<YYYY-MM-DD> workspace shape is what the resume-in-progress
lookup searches for; a mode that invents its own layout breaks resumption with no
error. Pure path builders — nothing here creates a directory."
    ```

---

### Task 5: `scripts/vocab.py` — one definition of every closed set

The design says the verdict words are "these exact strings, everywhere". Everywhere is the problem: a closed set spelled out in two modules is a closed set that will drift, and the drift is silent because both copies are individually valid Python. Before this module the five verdicts were about to be hard-coded in five places across the four mode plans, `MARKET_KEYS` was declared twice with different contents (`us` five keys vs six), and the "no market table" token was `none` in one plan and `other` in two others. All three are the same defect. One module, imported by every gate in this plan and in Plans 2–4.

**Files:**
- Create: `scripts/vocab.py`
- Test: `scripts/tests/test_vocab.py`

**Interfaces:**
- Consumes: nothing (stdlib-free constants only — anything importable must be importable from a gate's exit-2 path).
- Produces: `VERDICTS`, `REFUSAL`, `VERDICT_ZH`, `MARKET_KEYS`, `NO_MARKET`, `LEVELS`, `SCREENING`, `MATCH`, `RECENCY`, `EFFORT`, `BANDS`, `CONTRADICTED`, `DEFECT_TAGS`.

- [ ] **Step 1: Write the failing test**
    Create `scripts/tests/test_vocab.py`:
    ```python
    import pathlib
    import re
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    import vocab

    SCRIPTS = pathlib.Path(__file__).resolve().parent.parent


    def test_the_five_verdicts_are_exactly_these_in_this_order():
        assert vocab.VERDICTS == ("strong_apply", "worth_applying", "stretch",
                                  "likely_screen_out", "blocked")


    def test_the_refusal_is_not_a_sixth_verdict():
        """A refusal is orthogonal to the scale. Folding it in would let a caller
        sort it, average it, or read 'cannot tell' as a weak recommendation."""
        assert vocab.REFUSAL == "insufficient_evidence"
        assert vocab.REFUSAL not in vocab.VERDICTS


    def test_every_verdict_and_the_refusal_have_a_zh_label():
        assert set(vocab.VERDICT_ZH) == set(vocab.VERDICTS) | {vocab.REFUSAL}
        assert vocab.VERDICT_ZH["blocked"] == "硬性阻断"
        assert vocab.VERDICT_ZH[vocab.REFUSAL] == "证据不足—不出结论"


    def test_market_keys_and_the_no_table_token():
        assert vocab.MARKET_KEYS == ("cn", "nl", "de", "uk", "us")
        assert vocab.NO_MARKET == "other"
        assert vocab.NO_MARKET not in vocab.MARKET_KEYS


    def test_requirement_row_enums():
        assert vocab.LEVELS == ("required", "preferred", "unclear")
        assert vocab.SCREENING == ("knockout", "weighted", "nice_to_have")
        assert vocab.MATCH == ("strong", "partial", "gap", "no_evidence")
        assert vocab.RECENCY == ("current", "recent", "dated", "undated")
        assert vocab.EFFORT == ("quick", "evening", "multi_day", "not_closable")


    def test_mock_bands_are_unnumbered_and_contradicted_is_not_one_of_them():
        assert vocab.BANDS == ("not_present", "asserted", "instanced", "held_under_probe")
        assert vocab.CONTRADICTED == "contradicted"
        assert vocab.CONTRADICTED not in vocab.BANDS
        assert vocab.DEFECT_TAGS == ("UNSOURCED-FACT", "OVER-CLAIM", "CONTRADICTED",
                                     "PROBE-COLLAPSE")


    def test_every_closed_set_is_an_immutable_tuple():
        """A list would let a caller append to the shared vocabulary at import
        time, and the drift this module exists to stop would come back invisible."""
        for name in ("VERDICTS", "MARKET_KEYS", "LEVELS", "SCREENING", "MATCH",
                     "RECENCY", "EFFORT", "BANDS", "DEFECT_TAGS"):
            assert isinstance(getattr(vocab, name), tuple), f"{name} must be a tuple"
        assert isinstance(vocab.VERDICT_ZH, dict)


    def test_no_other_script_redeclares_a_closed_set():
        """The whole point. A second copy fails on the day it is written rather
        than on the day the two copies disagree. `MOCK_MARKET_KEYS` (Plan 4's
        documented superset) is deliberately still allowed — the anchored regex
        only rejects a bare re-declaration."""
        for f in sorted(SCRIPTS.glob("*.py")):
            if f.name == "vocab.py":
                continue
            text = f.read_text(encoding="utf-8")
            assert "strong_apply" not in text, \
                f"{f.name} spells out a verdict — import it from vocab.py"
            assert not re.search(r"^\s*MARKET_KEYS\s*=", text, re.M), \
                f"{f.name} re-declares MARKET_KEYS — import it from vocab.py"
            assert not re.search(r"^\s*DEFECT_TAGS\s*=", text, re.M), \
                f"{f.name} re-declares DEFECT_TAGS — import it from vocab.py"
    ```

- [ ] **Step 2: Run test to verify it fails**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_vocab.py -q`
    Expected: FAIL with `ModuleNotFoundError: No module named 'vocab'`

- [ ] **Step 3: Write minimal implementation**
    Create `scripts/vocab.py`:
    ```python
    #!/usr/bin/env python3
    """Every closed vocabulary in job-hunt, in one module.

    A closed set spelled out twice is a closed set that will drift, and the drift
    is silent because both copies are individually valid Python. Before this
    module existed the five verdicts were hard-coded in five places across the
    four mode plans, `MARKET_KEYS` was declared twice with different contents, and
    the "no market table" token was `none` in one plan and `other` in two others —
    three separate ways for two modules to disagree about a set the design calls
    "these exact strings, everywhere".

    Import from here. Do not re-declare. If a set genuinely needs to grow, it grows
    in this file, and test_vocab.py is what tells you which callers you changed.
    """
    from __future__ import annotations

    # ── advice levels (spec D3, §10) ──────────────────────────────────────────
    # Ordinal, in order. Deliberately unnumbered everywhere downstream: a number
    # invites an average, and averaging "worth_applying" with "blocked" is
    # arithmetic performed on words.
    VERDICTS = ("strong_apply", "worth_applying", "stretch", "likely_screen_out",
                "blocked")

    # A refusal is not a sixth level. "The input does not support a conclusion" is
    # not a point on the scale from apply to blocked, so it is kept orthogonal —
    # otherwise a run that could not read the posting sorts as a weak recommendation.
    REFUSAL = "insufficient_evidence"

    VERDICT_ZH = {
        "strong_apply": "强烈建议投",
        "worth_applying": "值得投",
        "stretch": "可以冲刺",
        "likely_screen_out": "大概率被筛掉",
        "blocked": "硬性阻断",
        "insufficient_evidence": "证据不足—不出结论",
    }

    # ── markets (spec §10) ────────────────────────────────────────────────────
    MARKET_KEYS = ("cn", "nl", "de", "uk", "us")
    # The ONE token for "this market has no convention table". Never "none": in
    # YAML an unquoted `none` is easy to read back as a null, and the row then
    # silently becomes untyped instead of explicitly out of scope.
    NO_MARKET = "other"

    # ── requirement rows (spec 5.2 step 6) ────────────────────────────────────
    LEVELS = ("required", "preferred", "unclear")
    SCREENING = ("knockout", "weighted", "nice_to_have")
    MATCH = ("strong", "partial", "gap", "no_evidence")
    RECENCY = ("current", "recent", "dated", "undated")
    EFFORT = ("quick", "evening", "multi_day", "not_closable")

    # ── mock-interview bands (spec 5.4) ───────────────────────────────────────
    # "held_under_probe" is the ceiling on purpose: a higher band would require
    # knowing what this level's expectations are, and this skill does not.
    BANDS = ("not_present", "asserted", "instanced", "held_under_probe")
    CONTRADICTED = "contradicted"
    DEFECT_TAGS = ("UNSOURCED-FACT", "OVER-CLAIM", "CONTRADICTED", "PROBE-COLLAPSE")
    ```

- [ ] **Step 4: Run test to verify it passes**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_vocab.py -q`
    Expected: PASS — `8 passed`

- [ ] **Step 5: Commit**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/vocab.py scripts/tests/test_vocab.py
    git commit -m "feat(vocab): one definition of every closed set

The design says 'these exact strings, everywhere' — and everywhere was about to
mean five hard-coded copies of the five verdicts, two different MARKET_KEYS and
two different tokens for 'no market table'. One module, imported by every gate.
test_vocab.py fails the day a second copy is written, not the day the two
copies disagree."
    ```

---

### Task 6: `scripts/check_skill_lossless.py` — prove the migration moved content instead of deleting it

**Read this before writing it, and carry the warning into the docstring:** this check measures whether the bytes still exist, not whether the content reaches context at the moment it is needed. A refactor can score a perfect lossless result and still degrade the skill, because the regression is in *when* content arrives. The only real test of Task 20's layering change is re-running the end-to-end evals and reading what the outputs are missing.

**This is the plan's one named exception to the gate contract** (see Global Constraints): a repo-level CI check, no `--workspace`, no `journal` import, no receipt. Exit 0 = lossless, 1 = content lost or a stale deletion entry, 2 = the baseline could not be read. It appears in SKILL.md's gate table and self-check on its own **CI** line, not under "Ran, with a receipt" — promising a receipt that can never exist is how a checklist teaches its reader that one of its lines is decorative.

**Files:**
- Create: `scripts/check_skill_lossless.py`
- Modify: `scripts/lossless-allowlist.json` (created in Task 2; unchanged content, now consumed)
- Test: `scripts/tests/test_check_skill_lossless.py`

**Interfaces:**
- Consumes: tag `job-application-baseline` from Task 2; `paths.SKILL_ROOT`, `paths.lossless_allowlist()`.
- Produces:
  - `normalize(text: str) -> str`
  - `line_key(normalized: str) -> str` (16-hex-char sha1 prefix)
  - `in_corpus(rel) -> bool` — the ONE membership rule, used by both sides of the comparison
  - `BaselineUnavailable(Exception)`
  - `baseline_docs(spec: str, repo: pathlib.Path) -> dict[str, str]` (relpath → text; raises `BaselineUnavailable`)
  - `build_corpus(skill_dir: pathlib.Path) -> tuple[str, list[pathlib.Path]]`
  - `main(argv=None) -> int`
  - CI command: `python3 scripts/check_skill_lossless.py --baseline 864ad7f`

> **Why the raw SHA and not the `job-application-baseline` tag.** A tag created locally lives in one
> clone. `job-hunt` has no `origin`, nothing here pushes, and CI checks out a fresh copy — so a tag
> baseline resolves to `BaselineUnavailable`, exit 2, on every machine but this one, and a check that
> cannot run looks exactly like a check that passed. `864ad7f` needs no such distribution: Task 2
> merged `job-application`'s history in, so that commit is an ancestor of `HEAD` and is present in any
> clone by construction (`git merge-base --is-ancestor 864ad7f HEAD` succeeds; verified 2026-08-10).
> The tag is still created in Task 2 and is still fine to type by hand locally — it is a readable
> alias for this SHA, not the thing anything depends on.

- [ ] **Step 1: Write the failing test**
    Create `scripts/tests/test_check_skill_lossless.py`:
    ```python
    import json
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    import check_skill_lossless as csl

    LINE = ("Never fabricate experience, skills, titles, dates, or credentials — "
            "this rule overrides every other instinct in this skill.")


    def _tree(root, files):
        for rel, text in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        return root


    def test_normalize_folds_form_but_not_words():
        assert csl.normalize("**Honest** reframing — only!") == csl.normalize("honest reframing only")
        assert csl.normalize("- Honest reframing") == csl.normalize("Honest reframing")
        assert csl.normalize("诚实 改写") == "诚实 改写"
        assert csl.normalize("honest reframing") != csl.normalize("honest")


    def test_lossless_when_the_line_merely_moved_to_another_file(tmp_path, capsys):
        base = _tree(tmp_path / "base", {"SKILL.md": f"# Old\n\n{LINE}\n"})
        new = _tree(tmp_path / "new", {"SKILL.md": "# New\n",
                                       "references/honesty.md": f"## Honesty\n\n{LINE}\n"})
        rc = csl.main(["--baseline", str(base), "--skill-dir", str(new)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "LOSSLESS" in out


    def test_lossless_when_the_line_was_only_re_wrapped(tmp_path, capsys):
        """Reflowing a paragraph must stay quiet — a check that fires on ordinary
        editing is a check everyone learns to skip."""
        base = _tree(tmp_path / "base", {"SKILL.md": f"{LINE}\n"})
        wrapped = LINE.replace("— ", "—\n")
        new = _tree(tmp_path / "new", {"SKILL.md": f"{wrapped}\n"})
        assert csl.main(["--baseline", str(base), "--skill-dir", str(new)]) == 0
        assert "LOSSLESS" in capsys.readouterr().out


    def test_content_lost_when_the_line_is_gone(tmp_path, capsys):
        base = _tree(tmp_path / "base", {"SKILL.md": f"# Old\n\n{LINE}\n"})
        new = _tree(tmp_path / "new", {"SKILL.md": "# New\n"})
        rc = csl.main(["--baseline", str(base), "--skill-dir", str(new)])
        out = capsys.readouterr().out
        assert rc == 1
        assert "CONTENT LOST" in out
        assert "Never fabricate experience" in out


    def test_content_lost_when_the_line_was_condensed(tmp_path, capsys):
        """The failure this exists for: 'split into references' quietly becoming
        'rewrite and condense'."""
        base = _tree(tmp_path / "base", {"SKILL.md": f"{LINE}\n"})
        new = _tree(tmp_path / "new", {"SKILL.md": "Never fabricate experience.\n"})
        assert csl.main(["--baseline", str(base), "--skill-dir", str(new)]) == 1
        assert "CONTENT LOST" in capsys.readouterr().out


    def test_an_allowlisted_line_stops_failing_the_build(tmp_path, capsys):
        base = _tree(tmp_path / "base", {"SKILL.md": f"{LINE}\n"})
        new = _tree(tmp_path / "new", {"SKILL.md": "# New\n"})
        allow = tmp_path / "allow.json"
        allow.write_text(json.dumps({
            "waived": {csl.line_key(csl.normalize(LINE)): "superseded by lint_no_prediction.py"},
            "deleted_files": {},
        }), encoding="utf-8")
        rc = csl.main(["--baseline", str(base), "--skill-dir", str(new), "--allow", str(allow)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "1 waived" in out


    def test_editing_a_waived_line_revokes_its_waiver(tmp_path, capsys):
        base = _tree(tmp_path / "base", {"SKILL.md": f"{LINE} And a new clause.\n"})
        new = _tree(tmp_path / "new", {"SKILL.md": "# New\n"})
        allow = tmp_path / "allow.json"
        allow.write_text(json.dumps({
            "waived": {csl.line_key(csl.normalize(LINE)): "reason"},
            "deleted_files": {},
        }), encoding="utf-8")
        assert csl.main(["--baseline", str(base), "--skill-dir", str(new), "--allow", str(allow)]) == 1


    def test_a_stale_deleted_files_entry_fails_instead_of_rotting(tmp_path, capsys):
        base = _tree(tmp_path / "base", {"SKILL.md": "# Old\n"})
        new = _tree(tmp_path / "new", {"SKILL.md": "# Old\n",
                                       "assets/cv/template.tex": "\\documentclass{article}\n"})
        allow = tmp_path / "allow.json"
        allow.write_text(json.dumps({
            "waived": {},
            "deleted_files": {"assets/cv/template.tex": "dead and drifted"},
        }), encoding="utf-8")
        rc = csl.main(["--baseline", str(base), "--skill-dir", str(new), "--allow", str(allow)])
        assert rc == 1
        assert "NOT_DELETED: assets/cv/template.tex" in capsys.readouterr().out


    def test_short_structural_lines_are_not_checked(tmp_path, capsys):
        """`---`, bare bullets and one-word headings carry no rule and would fail
        every time a heading is renamed."""
        base = _tree(tmp_path / "base", {"SKILL.md": "---\n# Steps\n- one\n"})
        new = _tree(tmp_path / "new", {"SKILL.md": "# Pipeline\n"})
        assert csl.main(["--baseline", str(base), "--skill-dir", str(new)]) == 0


    def test_docs_are_not_part_of_the_corpus(tmp_path, capsys):
        """A line that survives only in docs/ has not survived: the design doc is
        not something a skill trigger can reach. It matters in production too —
        this plan file quotes SKILL.md verbatim and lives under docs/, so a
        recursive corpus would let a condensed SKILL.md report LOSSLESS."""
        base = _tree(tmp_path / "base", {"SKILL.md": f"{LINE}\n"})
        new = _tree(tmp_path / "new", {"SKILL.md": "# New\n",
                                       "docs/superpowers/specs/design.md": LINE})
        assert csl.main(["--baseline", str(base), "--skill-dir", str(new)]) == 1


    def test_test_fixtures_are_outside_the_corpus_on_both_sides(tmp_path, capsys):
        """Both sides of the comparison must use the SAME membership rule. When the
        git-ref baseline read `scripts/tests/fixtures/*.yaml` and the on-disk corpus
        did not, a byte-identical tree reported 26 lines lost — a check that cries
        wolf on the very run it was written for."""
        base = _tree(tmp_path / "base", {
            "SKILL.md": "# Old\n",
            "scripts/tests/fixtures/full_profile.yaml":
                "summary: a long enough line of prose to be checked\n"})
        new = _tree(tmp_path / "new", {"SKILL.md": "# Old\n"})
        assert csl.main(["--baseline", str(base), "--skill-dir", str(new)]) == 0
        assert "LOSSLESS" in capsys.readouterr().out


    def test_an_unreadable_baseline_ref_is_exit_2_not_a_crash(tmp_path, capsys):
        """`could not run` is exit 2 with a message, not sys.exit(str) — which
        exits 1 and makes 'the baseline is unreachable' indistinguishable from
        'content was lost'."""
        new = _tree(tmp_path / "new", {"SKILL.md": "# New\n"})
        rc = csl.main(["--baseline", "no-such-ref", "--repo", str(tmp_path),
                       "--skill-dir", str(new)])
        assert rc == 2
        assert "no-such-ref" in capsys.readouterr().err
    ```

- [ ] **Step 2: Run test to verify it fails**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_check_skill_lossless.py -q`
    Expected: FAIL with `ModuleNotFoundError: No module named 'check_skill_lossless'`

- [ ] **Step 3: Write minimal implementation**
    Create `scripts/check_skill_lossless.py`:
    ```python
    #!/usr/bin/env python3
    """Guard the job-application → job-hunt migration: prove it MOVED content, not deleted it.

    "Split it into references" quietly becomes "rewrite and condense": the file
    shrinks, the commit says zero information loss, and operational rules are gone.
    That regression is invisible in review — the diff is thousands of lines and every
    removed line *looks* like it landed somewhere. So make it mechanical. Every
    substantive line of the baseline tree must still be findable, verbatim, somewhere
    a skill trigger can reach.

        # in CI, against the tag created during the migration
        python3 scripts/check_skill_lossless.py --baseline 864ad7f

        # against a tree on disk
        python3 scripts/check_skill_lossless.py --baseline /Users/x/.claude/skills/job-application

    Exit 0 = every baseline line accounted for. Exit 1 = content was lost, or the
    allowlist names a file that is still present. Exit 2 = the baseline could not be
    read at all — which is NOT the same answer as "content was lost", and must not
    share an exit code with it.

    This script is the one deliberate exception to job-hunt's gate contract: it is a
    repo-level CI check, takes no --workspace, imports no journal and writes no
    receipt. SKILL.md's self-check lists it under CI for that reason.

    WHAT THIS DOES NOT PROVE — read before quoting a score. It measures whether the
    bytes still exist, not whether they reach the context at the moment they are
    needed. A refactor can score a perfect result and still degrade the skill,
    because the regression is in *when* content arrives, not *whether* it survives.
    Content preservation is necessary and nowhere near sufficient; the only real test
    of a layering change is running the skill end-to-end afterwards and looking at
    what the output is missing.

    Matching is deliberately forgiving about FORM and strict about SUBSTANCE. Text is
    NFKC-folded, dashes and smart quotes unified, punctuation dropped, case ignored,
    and the whole corpus joined into one string before matching — so a line may be
    re-wrapped, re-indented, moved to another file, or have its bullet marker changed
    and still pass. What it may not do is lose a word.

    Deliberate deletions are legitimate. Record them in the allowlist with a reason:
    `waived` for individual lines (keyed on a hash of the normalized line, so editing
    the line revokes its waiver), `deleted_files` for whole files. Adapted from
    slides_maker's scripts/check_skill_lossless.py.
    """
    from __future__ import annotations

    import argparse
    import hashlib
    import json
    import re
    import subprocess
    import sys
    import unicodedata
    from pathlib import Path, PurePosixPath

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import paths

    # Lines shorter than this once normalized are structural noise — bare list
    # markers, `---` rules, lone code fences, one-word headings. They carry no rule
    # that can be lost, and checking them fails every time a heading is renamed.
    DEFAULT_MIN_CHARS = 25

    CORPUS_SUFFIXES = (".md", ".yaml")
    # Everything a skill trigger can eventually reach, keyed on the TOP-LEVEL
    # directory. `docs/` is deliberately out: a line that survives only in the
    # design doc has not survived — and in this repo the plan files under docs/
    # quote SKILL.md verbatim, so a recursive corpus would let a condensed SKILL.md
    # report LOSSLESS against itself. `scripts/` is out for the same reason in
    # reverse: test fixtures are not skill content.
    CORPUS_DIRS = (".", "modes", "references", "agents", "assets")


    class BaselineUnavailable(Exception):
        """The baseline tree could not be read — a different answer from 'lost'."""

    _DASHES = dict.fromkeys(map(ord, "—–‒―−"), "-")
    _QUOTES = {0x2019: "'", 0x2018: "'", 0x201C: '"', 0x201D: '"', ord("`"): "'"}

    # Keep alphanumerics and CJK/kana/hangul; everything else becomes a separator.
    # Dropping CJK would blind the check on the Chinese passages this skill carries.
    _DROP = re.compile(
        r"[^0-9a-z"
        r"぀-ヿ"      # kana
        r"㐀-䶿"      # CJK ext A
        r"一-鿿"      # CJK unified
        r"가-힯"      # hangul
        r"豈-﫿"      # CJK compatibility ideographs
        r"]+"
    )


    def normalize(text: str) -> str:
        """Fold away formatting so only word content is compared."""
        text = unicodedata.normalize("NFKC", text)
        text = text.translate(_DASHES).translate(_QUOTES)
        text = text.lower()
        text = _DROP.sub(" ", text)
        return " ".join(text.split())


    def line_key(normalized: str) -> str:
        return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


    def in_corpus(rel) -> bool:
        """Is this relpath part of the corpus a skill trigger can reach?

        ONE rule, used by BOTH sides of the comparison. When the two sides used
        different rules the check reported losses that never happened: the git-ref
        baseline read `scripts/tests/fixtures/*.yaml` (26 substantive lines, measured)
        and the on-disk corpus never scanned `scripts/`, so a byte-identical tree
        reported CONTENT LOST. A check that cries wolf on the very migration it was
        written for is a check nobody runs twice.
        """
        rel = str(rel).replace("\\", "/")
        if not rel.endswith(CORPUS_SUFFIXES):
            return False
        parts = PurePosixPath(rel).parts
        top = parts[0] if len(parts) > 1 else "."
        return top in CORPUS_DIRS


    def baseline_docs(spec: str, repo: Path) -> dict:
        """{relpath: text} for the baseline tree. `spec` is a git ref or a directory."""
        p = Path(spec)
        if p.is_dir():
            out = {}
            for f in sorted(p.rglob("*")):
                rel = f.relative_to(p)
                if f.is_file() and in_corpus(rel):
                    out[str(rel)] = f.read_text(encoding="utf-8", errors="replace")
            return out
        listing = subprocess.run(["git", "ls-tree", "-r", "--name-only", spec],
                                 cwd=repo, capture_output=True, text=True)
        if listing.returncode != 0:
            raise BaselineUnavailable(
                f"cannot read baseline {spec!r}: {listing.stderr.strip()}")
        out = {}
        for rel in listing.stdout.split("\n"):
            rel = rel.strip()
            if not rel or not in_corpus(rel):
                continue
            blob = subprocess.run(["git", "show", f"{spec}:{rel}"],
                                  cwd=repo, capture_output=True, text=True)
            if blob.returncode == 0:
                out[rel] = blob.stdout
        return out


    def build_corpus(skill_dir: Path) -> tuple:
        files = sorted(f for f in skill_dir.rglob("*")
                       if f.is_file() and in_corpus(f.relative_to(skill_dir)))
        joined = "\n".join(f.read_text(encoding="utf-8", errors="replace") for f in files)
        return normalize(joined), files


    def _find_repo(start: Path):
        p = start.resolve()
        while True:
            if (p / ".git").exists():
                return p
            if p == p.parent:
                return None
            p = p.parent


    def main(argv=None) -> int:
        ap = argparse.ArgumentParser(
            description="Verify a skill refactor moved content instead of deleting it.")
        ap.add_argument("--baseline", required=True,
                        help="a git ref (e.g. job-application-baseline) or a directory path")
        ap.add_argument("--skill-dir", default=None,
                        help="skill root (default: this script's parent directory's parent)")
        ap.add_argument("--repo", default=None, help="git repo for a ref baseline")
        ap.add_argument("--allow", default=None, help="JSON allowlist (default: scripts/lossless-allowlist.json)")
        ap.add_argument("--min-chars", type=int, default=DEFAULT_MIN_CHARS)
        ap.add_argument("--report", default=None, help="write the full missing-line report here")
        args = ap.parse_args(argv)

        skill_dir = Path(args.skill_dir).resolve() if args.skill_dir else paths.SKILL_ROOT
        repo = Path(args.repo).resolve() if args.repo else (
            _find_repo(Path(__file__).resolve().parent) or skill_dir)
        allow_path = Path(args.allow) if args.allow else paths.lossless_allowlist(skill_dir)

        allow, deleted_files = {}, {}
        if allow_path.exists():
            data = json.loads(allow_path.read_text(encoding="utf-8"))
            allow = data.get("waived") or {}
            deleted_files = data.get("deleted_files") or {}

        try:
            docs = baseline_docs(args.baseline, repo)
        except BaselineUnavailable as exc:
            print(str(exc), file=sys.stderr)
            return 2
        corpus, files = build_corpus(skill_dir)

        checked, waived = 0, 0
        missing = []          # (relpath, lineno, raw, normalized)
        for rel, text in sorted(docs.items()):
            for n, raw in enumerate(text.split("\n"), 1):
                norm = normalize(raw)
                if len(norm) < args.min_chars:
                    continue
                checked += 1
                if norm in corpus:
                    continue
                if line_key(norm) in allow:
                    waived += 1
                    continue
                missing.append((rel, n, raw.strip(), norm))

        stale = [rel for rel in sorted(deleted_files) if (skill_dir / rel).exists()]

        for rel, n, raw, _ in missing[:40]:
            print(f"LOST: {rel}:{n}: {raw[:150]}")
        if len(missing) > 40:
            print(f"LOST: … and {len(missing) - 40} more"
                  + (f" (full list: {args.report})" if args.report else " (use --report for all)"))
        for rel in stale:
            print(f"NOT_DELETED: {rel} is listed in {allow_path.name} as deliberately deleted "
                  f"but still exists — remove the entry or the file")

        if args.report:
            with open(args.report, "w", encoding="utf-8") as fh:
                fh.write(f"# Lost content report\n\nBaseline: `{args.baseline}`\n\n")
                for rel, n, raw, nrm in missing:
                    fh.write(f"- **{rel}:{n}** `{line_key(nrm)}`\n  > {raw}\n")

        ok = not missing and not stale
        verdict = "LOSSLESS" if ok else "CONTENT LOST"
        print(f"{verdict}: {checked - len(missing)}/{checked} baseline lines accounted for "
              f"across {len(files)} files"
              + (f", {waived} waived" if waived else "")
              + (f", {len(stale)} stale deletion entr(ies)" if stale else ""))
        if not ok:
            print("Moving these into SKILL.md, modes/ or references/ fixes it. If a line is "
                  "genuinely meant to go, add it to the allowlist and write down why.")
        return 0 if ok else 1


    if __name__ == "__main__":
        sys.exit(main())
    ```

- [ ] **Step 4: Run test to verify it passes**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_check_skill_lossless.py -q`
    Expected: PASS — `12 passed`

- [ ] **Step 5: Run it for real against the migration**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 scripts/check_skill_lossless.py --baseline 864ad7f`
    Expected: exit 0 and a line reading `LOSSLESS: 1317/1317 baseline lines accounted for across 15 files` (measured against the post-Task-1 baseline tree). The two `.tex` files are not in `CORPUS_SUFFIXES` and are covered by `deleted_files`. If it reports `CONTENT LOST` at this point, the merge in Task 2 lost something; stop and investigate rather than waiving. If it reports a number of files other than 15, `in_corpus` is picking up something it should not.

- [ ] **Step 6: Commit**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/check_skill_lossless.py scripts/tests/test_check_skill_lossless.py
    git commit -m "feat(lossless): assert the migration moved content instead of condensing it

Every substantive line of the job-application baseline (tag
job-application-baseline) must still be findable in SKILL.md, modes/,
references/, agents/ or assets/. docs/ is deliberately outside the corpus: a line
that survives only in the design doc has not survived.

The docstring carries the warning this check cannot enforce — it proves bytes
exist, not that they reach context when needed. The real test is the evals."
    ```

---

### Task 7: Fix the LaTeX engine bug with one shared `_engine_cmd()`

**The live defect, reproduced on this machine today.** `render_cv.find_latex_engine()` returns `/opt/homebrew/bin/tectonic`. `render_cv.py:992` compares `pathlib.Path(engine).name == "tectonic"` and takes the tectonic argv. `render_letter.py:101` compares the bare string `engine == "tectonic"`, which is False for an absolute path, so it builds a `pdflatex`-shaped argv and hands it to tectonic. Result in one run, one machine, one engine: `cv.pdf` builds (19,820 bytes), `letter.pdf` fails with "LaTeX compile failed", and all 51 tests stay green — because `test_letter_pdf_degrades_without_engine` monkeypatches the engine to `None` and never reaches the tectonic branch. The contract that would have prevented it ("Callers detect the engine *type* from the basename, so a returned absolute path works the same as a bare name") lives only in `find_latex_engine`'s docstring. Two call sites cannot drift if there is only one.

**Files:**
- Modify: `scripts/render_cv.py` (add `_engine_cmd`; `render_pdf` uses it, replacing lines 992–996)
- Modify: `scripts/render_letter.py` (hoist `import subprocess` to module level; `render_pdf` uses `render_cv._engine_cmd`, replacing lines 100–105)
- Test: `scripts/tests/test_render_cv.py`, `scripts/tests/test_render_letter.py`

**Interfaces:**
- Consumes: `render_cv.find_latex_engine(cjk=False) -> str | None` (existing).
- Produces: `render_cv._engine_cmd(engine: str, tex_path, out_dir) -> list[str]` — the argv for compiling `tex_path` into `out_dir`. Used by `render_cv.render_pdf` and `render_letter.render_pdf`.

- [ ] **Step 1: Write the failing tests**
    Append to `scripts/tests/test_render_cv.py`:
    ```python
    # ── engine argv: one helper, two renderers ────────────────────────────────

    def test_engine_cmd_dispatches_on_the_basename_not_the_whole_path():
        """find_latex_engine returns an ABSOLUTE path (measured:
        '/opt/homebrew/bin/tectonic'). Comparing the whole string to 'tectonic'
        silently selects the pdflatex argv and the compile fails."""
        assert render_cv._engine_cmd("/opt/homebrew/bin/tectonic", "/w/cv.tex", "/w") == \
            ["/opt/homebrew/bin/tectonic", "/w/cv.tex", "--outdir", "/w"]


    def test_engine_cmd_bare_tectonic_name_is_unchanged():
        assert render_cv._engine_cmd("tectonic", "/w/cv.tex", "/w") == \
            ["tectonic", "/w/cv.tex", "--outdir", "/w"]


    def test_engine_cmd_non_tectonic_engines_get_the_latex_argv():
        for engine in ("/usr/bin/pdflatex", "pdflatex", "/Library/TeX/texbin/xelatex"):
            assert render_cv._engine_cmd(engine, "/w/cv.tex", "/w") == \
                [engine, "-interaction=nonstopmode", "-output-directory", "/w", "/w/cv.tex"]


    def test_engine_cmd_accepts_path_objects():
        cmd = render_cv._engine_cmd(pathlib.Path("/opt/homebrew/bin/tectonic"),
                                    pathlib.Path("/w/cv.tex"), pathlib.Path("/w"))
        assert all(isinstance(x, str) for x in cmd)
        assert cmd[2] == "--outdir"


    def test_cv_pdf_invokes_tectonic_with_the_tectonic_argv(tmp_path, monkeypatch):
        engine = "/opt/homebrew/bin/tectonic"
        monkeypatch.setattr(render_cv, "find_latex_engine", lambda cjk=False: engine)
        seen = {}

        def fake_run(cmd, **kw):
            seen["cmd"] = cmd
            class R:
                returncode = 0
            return R()

        monkeypatch.setattr(render_cv.subprocess, "run", fake_run)
        out = tmp_path / "cv.pdf"
        render_cv.render_pdf({"meta": {"name": "Z"}}, out)
        assert seen["cmd"] == [engine, str(tmp_path / "cv.tex"), "--outdir", str(tmp_path)]
    ```
    Leave `test_letter_pdf_degrades_without_engine` in `scripts/tests/test_render_letter.py` **unchanged** — it pins the no-engine degradation, which is still correct behaviour — and append the two tests below, which are the regression the suite was missing:
    ```python
    def test_letter_pdf_uses_the_tectonic_argv_for_an_absolute_engine_path(tmp_path, monkeypatch):
        """The bug this file shipped with: render_letter compared the engine to the
        bare string 'tectonic' while find_latex_engine returns an absolute path, so
        every letter PDF was compiled with pdflatex flags and failed — in the same
        run where cv.pdf built fine, with all 51 tests green."""
        engine = "/opt/homebrew/bin/tectonic"
        monkeypatch.setattr(render_letter.render_cv, "find_latex_engine", lambda: engine)
        seen = {}

        def fake_run(cmd, **kw):
            seen["cmd"] = cmd
            class R:
                returncode = 0
            return R()

        monkeypatch.setattr(render_letter.subprocess, "run", fake_run)
        data = render_letter.load(FIXTURES / "sample_letter.yaml")
        out = tmp_path / "letter.pdf"
        assert render_letter.render_pdf(data, out) is True
        assert seen["cmd"] == [engine, str(tmp_path / "letter.tex"), "--outdir", str(tmp_path)]


    def test_letter_and_cv_build_the_same_argv_for_the_same_engine():
        """The two renderers cannot drift again: there is one helper."""
        import render_cv
        assert render_letter.render_cv._engine_cmd is render_cv._engine_cmd
    ```

- [ ] **Step 2: Run tests to verify they fail**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_render_cv.py scripts/tests/test_render_letter.py -q`
    Expected: FAIL with `AttributeError: module 'render_cv' has no attribute '_engine_cmd'` (and `AttributeError: module 'render_letter' has no attribute 'subprocess'`).

- [ ] **Step 3: Write the implementation**
    In `scripts/render_cv.py`, add immediately after `find_latex_engine`:
    ```python
    def _engine_cmd(engine, tex_path, out_dir):
        """argv to compile `tex_path` into `out_dir` with `engine`.

        Dispatch on the BASENAME, never on the whole string: find_latex_engine
        returns an absolute path when the engine is not on PATH (measured on this
        machine: '/opt/homebrew/bin/tectonic'), and `engine == "tectonic"` is False
        for it. That comparison shipped in render_letter.py and produced a
        pdflatex-shaped argv handed to tectonic — every letter PDF failed while
        cv.pdf built in the same run, with the whole test suite green.

        One helper, both renderers. Two call sites cannot drift if there is one.
        """
        engine, tex_path, out_dir = str(engine), str(tex_path), str(out_dir)
        if pathlib.Path(engine).stem == "tectonic":
            return [engine, tex_path, "--outdir", out_dir]
        return [engine, "-interaction=nonstopmode", "-output-directory", out_dir, tex_path]
    ```
    In `render_cv.render_pdf`, replace lines 992–996 (`if pathlib.Path(engine).name == "tectonic": … str(tex_path)]`) with:
    ```python
        cmd = _engine_cmd(engine, tex_path, out_path.parent)
    ```
    In `scripts/render_letter.py`, add `import subprocess` to the module-level imports (alphabetically before `import sys`), and in `render_letter.render_pdf` replace lines 100–105 (`import subprocess` through `str(tex_path)]`) with:
    ```python
        cmd = render_cv._engine_cmd(engine, tex_path, out_path.parent)
    ```

- [ ] **Step 4: Run tests to verify they pass**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests -q`
    Expected: PASS — the migrated `51 passed`, plus the 5 new cases in `test_render_cv.py` and the 2 in `test_render_letter.py` (`58 passed`), plus everything Tasks 3–6 added (`9 + 13 + 8 + 12 = 42`), i.e. **`100 passed`**. If the total is 57, one of the two appended letter tests was dropped.

- [ ] **Step 5: Prove it end-to-end, since the unit suite is exactly what missed it**
    Run:
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt/scripts
    python3 render_letter.py tests/fixtures/sample_letter.yaml --format pdf --out /tmp/jh-letter.pdf
    ls -l /tmp/jh-letter.pdf
    ```
    Expected: `Wrote /tmp/jh-letter.pdf` on stdout, no "LaTeX compile failed" warning, and a non-zero-byte PDF. Before this task, this exact command printed `WARNING: LaTeX compile failed.` and produced no PDF.

- [ ] **Step 6: Commit**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/render_cv.py scripts/render_letter.py \
            scripts/tests/test_render_cv.py scripts/tests/test_render_letter.py
    git commit -m "fix(render): one _engine_cmd() for both renderers

render_letter compared the engine to the bare string 'tectonic' while
find_latex_engine returns '/opt/homebrew/bin/tectonic', so it built a
pdflatex-shaped argv and every letter PDF failed — in the same run where cv.pdf
built, with 51/51 tests green, because the only letter-PDF test monkeypatched the
engine to None and never reached that branch.

Adds the regression test that does reach it, and hoists argv construction into
one helper so the two renderers cannot drift again."
    ```

---

### Task 8: Fix the Cluster-1 personal-data interlock and make it audible

**The live defect.** `references/cv-craft.md:121` claims the renderer makes a leak physically impossible. It does not: `_is_cluster1` does an exact lowercase token lookup, and DOB renders through for `United States of America`, `US (Boston)`, `Los Angeles, CA`, `U.K.` and `remote (US)` — all measured today. The eval-0 scenario input literally reads `TARGET MARKET: United States (Los Angeles, CA)`.

**Two changes, and the second matters as much as the first.** Normalising the match closes the five known spellings. But an unknown market with personal data present must also stop being silent — and it must not cry wolf on the many perfectly ordinary EU/Asia markets where a photo is a convention. So the resolver returns a cluster (1, 2 or 3) or `None`, and only `None` warns.

**Files:**
- Modify: `scripts/render_cv.py` (replace `_CLUSTER1_MARKETS` and `_is_cluster1` at lines 346–360; call `_warn_unknown_market` as the first statement of the three render entry points — `render_markdown`, `render_docx`, `build_latex` — and nowhere else)
- Test: `scripts/tests/test_render_cv.py`

**One insertion point, named once.** The warning does **not** go in `personal_items`: that function is a generator (`yield` at `render_cv.py:379`) consumed at three sites (`:462`, `:607`, `:873`), so an md + docx + pdf run — three invocations, or three direct calls from one process — would print the identical warning three times. (`main` has `--format choices=["md","docx","pdf"]`; there is no `all`, so one CLI invocation renders one format and the repetition comes from repeating the run.) Three identical warnings is precisely how a warning gets trained away. It goes at the top of each render entry point instead, guarded so that one profile warns once no matter how many formats are rendered from it.

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `render_cv.resolve_cluster(market) -> int | None` — 1 = US/CA/UK/IE/AU/NZ, 2 = EU/EEA, 3 = East & SE Asia, None = not recognised.
  - `render_cv._is_cluster1(profile) -> bool` (kept, now `resolve_cluster(...) == 1`).
  - `render_cv.protected_fields(profile) -> list[str]` — names of the protected fields actually present, e.g. `["contact.personal.date_of_birth", "meta.photo"]`.
  - `render_cv.reset_market_warnings() -> None` — forget which profiles have warned; called at the top of `main()`.

- [ ] **Step 1: Write the failing test**
    Replace `test_personal_data_and_photo_stripped_for_cluster1` in `scripts/tests/test_render_cv.py` and add its neighbours:
    ```python
    # Realistic spellings, drawn from the eval scenario inputs and from what a
    # returning user actually types. Every one must either suppress or warn — never
    # render protected data silently.
    CLUSTER1_SPELLINGS = [
        "us", "USA", "U.S.", "United States", "United States of America",
        "United States (Los Angeles, CA)", "US (Boston)", "Los Angeles, CA",
        "remote (US)", "uk", "U.K.", "United Kingdom", "London, United Kingdom",
        "Canada", "Toronto, Canada", "Ireland", "australia", "New Zealand",
    ]
    KNOWN_NON_CLUSTER1_SPELLINGS = [
        "nl", "Netherlands", "Amsterdam, Netherlands", "Eindhoven, NL (hybrid)",
        "Germany", "Munich, Germany", "Remote — EU", "Austria", "Switzerland",
        "cn", "China", "中国", "Japan", "Tokyo, Japan", "South Korea", "Singapore",
    ]
    UNRECOGNIZED_SPELLINGS = ["Brazil", "Dubai, UAE", "Mars", "", "somewhere nice"]


    @pytest.mark.parametrize("market", CLUSTER1_SPELLINGS)
    def test_cluster1_spellings_suppress_personal_data(tmp_path, market):
        img = tmp_path / "p.png"; img.write_bytes(b"\x89PNG\r\n\x1a\n")
        profile = {
            "meta": {"name": "Z", "target_market": market, "photo": str(img)},
            "contact": {"email": "z@x.com", "personal": {"date_of_birth": "1992"}},
        }
        assert render_cv.resolve_cluster(market) == 1
        md = render_cv.render_markdown(profile)
        assert "1992" not in md and "Photo" not in md, f"{market!r} leaked personal data"
        assert "includegraphics" not in render_cv.build_latex(profile)


    @pytest.mark.parametrize("market", KNOWN_NON_CLUSTER1_SPELLINGS)
    def test_known_non_cluster1_markets_render_quietly(tmp_path, capsys, market):
        """The quiet case, pinned as hard as the firing one: a photo on a Dutch or
        Chinese CV is a convention, not a defect. A warning here would be a warning
        everyone learns to ignore."""
        img = tmp_path / "p.png"; img.write_bytes(b"\x89PNG\r\n\x1a\n")
        profile = {
            "meta": {"name": "Z", "target_market": market, "photo": str(img)},
            "contact": {"email": "z@x.com", "personal": {"date_of_birth": "1992"}},
        }
        assert render_cv.resolve_cluster(market) in (2, 3)
        md = render_cv.render_markdown(profile)
        assert "1992" in md
        assert capsys.readouterr().err == ""


    @pytest.mark.parametrize("market", UNRECOGNIZED_SPELLINGS)
    def test_unrecognized_market_with_personal_data_warns_and_names_the_fields(tmp_path, capsys, market):
        img = tmp_path / "p.png"; img.write_bytes(b"\x89PNG\r\n\x1a\n")
        profile = {
            "meta": {"name": "Z", "target_market": market, "photo": str(img)},
            "contact": {"email": "z@x.com", "personal": {"date_of_birth": "1992"}},
        }
        assert render_cv.resolve_cluster(market) is None
        render_cv.render_markdown(profile)
        err = capsys.readouterr().err
        assert "WARNING" in err
        assert "contact.personal.date_of_birth" in err
        assert "meta.photo" in err
        assert repr(market) in err or f"{market!r}" in err


    def test_unrecognized_market_without_personal_data_is_silent(tmp_path, capsys):
        """No protected data, nothing to warn about."""
        profile = {"meta": {"name": "Z", "target_market": "Brazil"},
                   "contact": {"email": "z@x.com"}}
        render_cv.render_markdown(profile)
        assert capsys.readouterr().err == ""


    def test_the_unknown_market_warning_prints_once_per_profile_not_once_per_format(
            tmp_path, capsys):
        """An md + docx + pdf run — three invocations, or three direct calls from
        one process — renders from the SAME profile. Three identical warnings is
        how a warning gets trained away, and it is why this does not live in
        personal_items (a generator consumed at three separate sites)."""
        img = tmp_path / "p.png"; img.write_bytes(b"\x89PNG\r\n\x1a\n")
        profile = {"meta": {"name": "Z", "target_market": "Dubai, UAE", "photo": str(img)},
                   "contact": {"email": "z@x.com",
                               "personal": {"date_of_birth": "1992"}}}
        render_cv.render_markdown(profile)
        render_cv.build_latex(profile)
        render_cv.render_docx(profile, tmp_path / "cv.docx")
        assert capsys.readouterr().err.count("WARNING") == 1


    def test_resetting_lets_a_second_run_warn_again(tmp_path, capsys):
        """The guard is per-run, not per-process: main() clears it, so a second
        CLI invocation in the same process is not silently exempted."""
        profile = {"meta": {"name": "Z", "target_market": "Mars"},
                   "contact": {"personal": {"nationality": "NL"}}}
        render_cv.render_markdown(profile)
        render_cv.reset_market_warnings()
        render_cv.render_markdown(profile)
        assert capsys.readouterr().err.count("WARNING") == 2


    def test_protected_fields_names_exactly_what_is_present():
        profile = {"meta": {"name": "Z", "photo": "/tmp/p.png"},
                   "contact": {"personal": {"date_of_birth": "1992", "nationality": "NL",
                                            "marital_status": None}}}
        assert render_cv.protected_fields(profile) == [
            "contact.personal.date_of_birth", "contact.personal.nationality", "meta.photo"]
    ```

- [ ] **Step 2: Run test to verify it fails**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_render_cv.py -q -k "cluster or market or protected"`
    Expected: FAIL — `AttributeError: module 'render_cv' has no attribute 'resolve_cluster'`, and (once that exists) `'United States of America' leaked personal data`.

- [ ] **Step 3: Write the implementation**
    In `scripts/render_cv.py`, replace lines 346–360 (`# Markets where a photo …` through the end of `_is_cluster1`) with:
    ```python
    # Which regional CV convention a `meta.target_market` string belongs to.
    #   1 = US/CA/UK/IE/AU/NZ — a photo/DOB/nationality is a liability there; many
    #       employers route such CVs straight to rejection because considering that
    #       data exposes them to discrimination-law claims.
    #   2 = EU/EEA, 3 = East & SE Asia — the same fields are a normal convention.
    #   None = not recognised, which is NOT the same as "safe".
    #
    # Full names are matched as whole-word phrases anywhere in a segment, so
    # "United States of America" and "London, United Kingdom" both resolve. Two-letter
    # codes are matched only when they are the WHOLE segment: otherwise "Remote in
    # Berlin" would resolve to India via "in", and a false resolution is worse than
    # none — it silences the warning.
    _CLUSTER_NAMES = {
        1: ["united states of america", "united states", "u s a", "america", "canada",
            "united kingdom", "great britain", "britain", "england", "scotland", "wales",
            "northern ireland", "republic of ireland", "ireland", "australia",
            "new zealand", "u k", "u s"],
        2: ["the netherlands", "netherlands", "holland", "germany", "deutschland",
            "france", "belgium", "spain", "italy", "portugal", "austria", "switzerland",
            "sweden", "norway", "denmark", "finland", "poland", "czechia",
            "czech republic", "luxembourg", "greece", "romania", "hungary", "ireland eu",
            "european union", "eea"],
        3: ["mainland china", "china", "hong kong", "taiwan", "japan", "south korea",
            "republic of korea", "korea", "singapore", "malaysia", "thailand", "vietnam",
            "indonesia", "philippines", "india"],
    }
    _CLUSTER_CODES = {
        1: ["us", "usa", "ca", "can", "uk", "gb", "ie", "irl", "au", "aus", "nz"],
        2: ["nl", "de", "fr", "be", "es", "it", "pt", "at", "ch", "se", "no", "dk",
            "fi", "pl", "cz", "lu", "gr", "ro", "hu", "eu"],
        3: ["cn", "prc", "hk", "tw", "jp", "kr", "sg", "my", "th", "vn", "id", "ph", "in"],
    }
    # CJK market names have no word boundaries to split on, so they are matched by
    # substring. Without these a Chinese-language profile resolves to None and the
    # unknown-market warning fires on a perfectly ordinary Chinese CV.
    _CLUSTER_CJK = {
        1: ["美国", "英国", "加拿大", "澳大利亚", "新西兰", "爱尔兰"],
        2: ["荷兰", "德国", "法国", "比利时", "西班牙", "意大利", "瑞士", "瑞典", "欧盟"],
        3: ["中国", "中国大陆", "香港", "台湾", "日本", "韩国", "新加坡", "马来西亚", "泰国", "印度"],
    }

    _NAME_CLUSTER, _CODE_CLUSTER, _CJK_CLUSTER = {}, {}, {}
    for _c, _names in _CLUSTER_NAMES.items():
        for _n in _names:
            _NAME_CLUSTER.setdefault(_n, _c)
    for _c, _codes in _CLUSTER_CODES.items():
        for _n in _codes:
            _CODE_CLUSTER.setdefault(_n, _c)
    for _c, _names in _CLUSTER_CJK.items():
        for _n in _names:
            _CJK_CLUSTER.setdefault(_n, _c)
    _MAX_NAME_WORDS = max(len(_n.split()) for _n in _NAME_CLUSTER)

    _MARKET_SEP = re.compile(r"[,()\[\]/|;·–—-]+")
    _MARKET_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)

    # The protected fields, in the order they are reported. `contact.personal` is a
    # free-form dict, so any key in it is treated as protected — the risk is the
    # category, not a fixed list of key names.
    _PHOTO_FIELD = "meta.photo"


    def _market_segments(market):
        text = unicodedata.normalize("NFKC", str(market or "")).lower()
        for seg in _MARKET_SEP.split(text):
            seg = " ".join(_MARKET_PUNCT.sub(" ", seg).split())
            if seg:
                yield seg


    def resolve_cluster(market):
        """1, 2, 3 — or None when the string names no market we know.

        When several clusters match (e.g. 'remote (US) / hybrid Berlin') the lowest
        wins: suppression is the safe direction, because the cost of stripping a
        photo from an EU CV is cosmetic and the cost of leaving a DOB on a US CV is
        an automatic rejection at best.
        """
        text = unicodedata.normalize("NFKC", str(market or "")).lower()
        found = {c for alias, c in _CJK_CLUSTER.items() if alias in text}
        for seg in _market_segments(market):
            if seg in _CODE_CLUSTER:
                found.add(_CODE_CLUSTER[seg])
            words = seg.split()
            for n in range(_MAX_NAME_WORDS, 0, -1):
                for i in range(len(words) - n + 1):
                    phrase = " ".join(words[i:i + n])
                    if phrase in _NAME_CLUSTER:
                        found.add(_NAME_CLUSTER[phrase])
        return min(found) if found else None


    def protected_fields(profile):
        """Names of the protected personal-data fields actually present."""
        out = []
        personal = (profile.get("contact") or {}).get("personal") or {}
        if isinstance(personal, dict):
            out += [f"contact.personal.{k}" for k, v in personal.items()
                    if v not in (None, "")]
        if (profile.get("meta") or {}).get("photo"):
            out.append(_PHOTO_FIELD)
        return out


    # One warning per (profile object, market), not per render call. An md + docx
    # + pdf run — three invocations, or three direct calls from one process —
    # renders from the SAME profile dict, and printing the identical warning three
    # times is how a warning gets trained away. (main() takes one --format per
    # invocation: md, docx or pdf. There is no `all`.) The profile OBJECT is held
    # rather than its id(): an id can be
    # reused after garbage collection, and a silently-suppressed leak warning is
    # exactly the failure this interlock exists to prevent.
    _MARKET_WARNED = []


    def reset_market_warnings():
        """Forget which profiles have already warned. main() calls this at the top
        of every CLI run so the guard is per-run, not per-process."""
        _MARKET_WARNED.clear()


    def _warn_unknown_market(profile):
        """Loud when the market is unrecognised AND protected data is present.

        cv-craft.md claims a mis-tailored profile 'physically cannot leak protected
        data onto a US/UK CV'. It could, for five measured spellings. The matcher
        above closes those; this closes the class — an unrecognised market is not
        evidence that rendering a DOB is safe, and silence there is what made the
        original claim false.
        """
        market = (profile.get("meta") or {}).get("target_market")
        if resolve_cluster(market) is not None:
            return
        fields = protected_fields(profile)
        if not fields:
            return
        if any(p is profile and m == market for p, m in _MARKET_WARNED):
            return
        _MARKET_WARNED.append((profile, market))
        print(f"WARNING: meta.target_market {market!r} matches no known CV-convention "
              f"cluster, so the Cluster-1 personal-data interlock cannot fire. These "
              f"fields will render as-is: {', '.join(fields)}. If this is a "
              f"US/Canada/UK/Ireland/Australia/NZ target, set meta.target_market to a "
              f"recognised country name and re-render — protected personal data on "
              f"such a CV is a discrimination-law liability and a common auto-reject.",
              file=sys.stderr)


    def _is_cluster1(profile):
        return resolve_cluster((profile.get("meta") or {}).get("target_market")) == 1
    ```
    Add `import unicodedata` to `render_cv.py`'s module imports if absent. Then call the warning as the **first statement** of each of the three render entry points — and nowhere else:
    ```python
    def render_markdown(profile):
        _warn_unknown_market(profile)
        ...rest unchanged...

    def render_docx(profile, out_path):
        _warn_unknown_market(profile)
        ...rest unchanged...

    def build_latex(profile, cjk=None):
        _warn_unknown_market(profile)
        ...rest unchanged...
    ```
    and add `reset_market_warnings()` as the first statement of `main()`. Do **not** touch `personal_items` or `photo_path`: they are the suppression, not the warning, and `personal_items` is a generator consumed at three sites.

- [ ] **Step 4: Run test to verify it passes**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests -q`
    Expected: PASS — all previous tests plus `18 + 16 + 5 + 4` = 43 new cases (the 18 Cluster-1 spellings, the 16 quiet non-Cluster-1 ones, the 5 unrecognised ones, and the four singletons: no-personal-data-is-silent, protected_fields, warn-once-per-profile, reset-lets-it-warn-again).

- [ ] **Step 5: Commit**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/render_cv.py scripts/tests/test_render_cv.py
    git commit -m "fix(render): normalize market matching, warn on an unknown market

Measured leaks through the exact-token matcher: 'United States of America',
'US (Boston)', 'Los Angeles, CA', 'U.K.', 'remote (US)' — and the eval-0 scenario
input literally reads 'United States (Los Angeles, CA)'. resolve_cluster()
segments the string, matches full names as whole-word phrases and ISO codes only
as whole segments (so 'Remote in Berlin' does not resolve to India), and adds CJK
aliases.

An unrecognised market with personal data present now warns to stderr naming the
fields, instead of rendering silently. Known EU/Asia markets stay quiet, and the
tests pin that as hard as the firing case."
    ```

---

### Task 9: `scripts/check_personal_data.py` — the interlock as a gate with a receipt

The renderer now suppresses and warns, but the renderer is the *last* line. `cv-craft.md` requires the tailoring step to strip these fields from the tailored profile itself, because a profile that still carries a DOB leaks the moment someone re-renders it against a different market. This gate checks the tailored profile, not the rendered output, and leaves the receipt `check_apply.py` requires.

**Files:**
- Create: `scripts/check_personal_data.py`
- Test: `scripts/tests/test_check_personal_data.py`

**Interfaces:**
- Consumes: `journal.receipt`, `journal.sha256_file`; `render_cv.resolve_cluster`, `render_cv.protected_fields`.
- Produces: `main(argv=None) -> int`. CLI: `python3 scripts/check_personal_data.py --workspace W [--profile PATH]` (default profile: `<W>/tailored-profile.yaml`). Gate name in the journal: `check_personal_data`. Finding codes: `CLUSTER1_PERSONAL_DATA`, `MARKET_UNRECOGNIZED`, `NO_TARGET_MARKET`.

- [ ] **Step 1: Write the failing test**
    Create `scripts/tests/test_check_personal_data.py`:
    ```python
    import pathlib
    import sys

    import yaml

    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    import check_personal_data
    import journal


    def _ws(tmp_path, profile):
        ws = tmp_path / "acme-engineer-2026-08-09"
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "tailored-profile.yaml").write_text(
            yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
        return ws


    def test_clean_cluster1_profile_passes_quietly(tmp_path, capsys):
        ws = _ws(tmp_path, {"meta": {"name": "Z", "target_market": "United States (Boston, MA)"},
                            "contact": {"email": "z@x.com"}})
        assert check_personal_data.main(["--workspace", str(ws)]) == 0
        assert capsys.readouterr().out.strip() == ""


    def test_eu_profile_with_photo_and_dob_passes_quietly(tmp_path, capsys):
        """A photo on a Dutch CV is a convention. Firing here would train the reader
        to ignore this gate."""
        ws = _ws(tmp_path, {"meta": {"name": "Z", "target_market": "Amsterdam, Netherlands",
                                     "photo": "/tmp/p.png"},
                            "contact": {"personal": {"date_of_birth": "1992-04-01"}}})
        assert check_personal_data.main(["--workspace", str(ws)]) == 0
        assert capsys.readouterr().out.strip() == ""


    def test_cluster1_profile_still_carrying_a_dob_fails_and_names_the_field(tmp_path, capsys):
        ws = _ws(tmp_path, {"meta": {"name": "Z", "target_market": "United States of America"},
                            "contact": {"personal": {"date_of_birth": "1992-04-01"}}})
        assert check_personal_data.main(["--workspace", str(ws)]) == 1
        out = capsys.readouterr().out
        assert "CLUSTER1_PERSONAL_DATA" in out
        assert "contact.personal.date_of_birth" in out


    def test_unrecognized_market_with_personal_data_fails(tmp_path, capsys):
        ws = _ws(tmp_path, {"meta": {"name": "Z", "target_market": "Dubai, UAE",
                                     "photo": "/tmp/p.png"},
                            "contact": {"personal": {"nationality": "CN"}}})
        assert check_personal_data.main(["--workspace", str(ws)]) == 1
        out = capsys.readouterr().out
        assert "MARKET_UNRECOGNIZED" in out
        assert "meta.photo" in out and "contact.personal.nationality" in out


    def test_missing_target_market_with_personal_data_fails(tmp_path, capsys):
        ws = _ws(tmp_path, {"meta": {"name": "Z"},
                            "contact": {"personal": {"date_of_birth": "1992"}}})
        assert check_personal_data.main(["--workspace", str(ws)]) == 1
        assert "NO_TARGET_MARKET" in capsys.readouterr().out


    def test_missing_profile_is_exit_2_not_a_pass(tmp_path, capsys):
        ws = tmp_path / "empty"; ws.mkdir()
        assert check_personal_data.main(["--workspace", str(ws)]) == 2
        assert "tailored-profile.yaml" in capsys.readouterr().err


    def test_every_exit_path_leaves_exactly_one_receipt(tmp_path):
        for profile, expected in (
            ({"meta": {"target_market": "us"}}, "pass"),
            ({"meta": {"target_market": "us"}, "contact": {"personal": {"date_of_birth": "1"}}}, "fail"),
        ):
            ws = _ws(tmp_path / expected, profile)
            check_personal_data.main(["--workspace", str(ws)])
            receipts = journal.read_receipts(ws, "check_personal_data")
            assert len(receipts) == 1
            assert receipts[0]["verdict"] == expected
        ws = tmp_path / "gone"; ws.mkdir()
        check_personal_data.main(["--workspace", str(ws)])
        receipts = journal.read_receipts(ws, "check_personal_data")
        assert len(receipts) == 1 and receipts[0]["verdict"] == "could_not_run"
    ```

- [ ] **Step 2: Run test to verify it fails**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_check_personal_data.py -q`
    Expected: FAIL with `ModuleNotFoundError: No module named 'check_personal_data'`

- [ ] **Step 3: Write minimal implementation**
    Create `scripts/check_personal_data.py`:
    ```python
    #!/usr/bin/env python3
    """Gate: protected personal data must not survive into a Cluster-1 application.

    The renderer suppresses these fields for a Cluster-1 target, but the renderer is
    the last line, not the rule. cv-craft requires the *tailoring* step to strip
    them, because a tailored profile that still carries a DOB leaks the moment
    anyone re-renders it against a different market string — and the market string
    is the one field a returning user changes.

    Exit 0 = clean. Exit 1 = findings. Exit 2 = no tailored profile to check.
    """
    from __future__ import annotations

    import argparse
    import pathlib
    import sys

    import yaml

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import journal
    import render_cv

    GATE = "check_personal_data"


    def findings_for(profile) -> list:
        market = (profile.get("meta") or {}).get("target_market")
        fields = render_cv.protected_fields(profile)
        if not fields:
            return []
        named = ", ".join(fields)
        if not str(market or "").strip():
            return [f"NO_TARGET_MARKET: the tailored profile carries {named} but sets no "
                    f"meta.target_market, so no CV-convention rule can be applied to it"]
        cluster = render_cv.resolve_cluster(market)
        if cluster is None:
            return [f"MARKET_UNRECOGNIZED: meta.target_market {market!r} matches no known "
                    f"CV-convention cluster while the profile carries {named}; set a "
                    f"recognised country name so the interlock can decide"]
        if cluster == 1:
            return [f"CLUSTER1_PERSONAL_DATA: {named} are present in the tailored profile "
                    f"for a Cluster-1 target ({market!r}); strip them at the tailoring "
                    f"step and tell the user you did and why — the renderer's suppression "
                    f"is defence in depth, not the rule"]
        return []


    def main(argv=None) -> int:
        ap = argparse.ArgumentParser()
        ap.add_argument("--workspace", required=True)
        ap.add_argument("--profile", default=None,
                        help="default: <workspace>/tailored-profile.yaml")
        args = ap.parse_args(argv)

        ws = pathlib.Path(args.workspace)
        if not ws.is_dir():
            # journal.receipt() would mkdir it, and a gate that creates the
            # workspace it is auditing has manufactured its own evidence.
            print(f"cannot run {GATE}: workspace {ws} does not exist", file=sys.stderr)
            return 2
        path = pathlib.Path(args.profile) if args.profile else ws / "tailored-profile.yaml"
        if not path.exists():
            journal.receipt(ws, GATE, {}, "could_not_run", [f"MISSING_INPUT: {path}"])
            print(f"cannot run {GATE}: {path} does not exist", file=sys.stderr)
            return 2

        profile = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        findings = findings_for(profile)
        for f in findings:
            print(f)
        journal.receipt(ws, GATE, {path.name: journal.sha256_file(path)},
                        "fail" if findings else "pass", findings)
        return 1 if findings else 0


    if __name__ == "__main__":
        sys.exit(main())
    ```

- [ ] **Step 4: Run test to verify it passes**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_check_personal_data.py -q`
    Expected: PASS — `7 passed`

- [ ] **Step 5: Commit**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/check_personal_data.py scripts/tests/test_check_personal_data.py
    git commit -m "feat(gate): check_personal_data — the interlock with a receipt

Checks the tailored profile, not the render: a profile that still carries a DOB
leaks the moment someone re-renders it against a different market. An
unrecognised market with protected data present fails rather than passing
quietly; recognised EU/Asia markets stay silent, and the tests pin that."
    ```

---

### Task 10: `scripts/rounds.py` and `scripts/parse_verdicts.py` — the parser all three agents already assume

All three agent files end with *"The orchestrator parses this block programmatically — formatting must be exact"*, and no such program exists: the orchestrator is a model reading prose. A model that charitably reads `VERDICT: PASS (with reservations)` as a pass ships a package that looks fully reviewed. Fail-closed goes in code.

**Files:**
- Create: `scripts/rounds.py`, `scripts/parse_verdicts.py`
- Test: `scripts/tests/test_parse_verdicts.py`

**Interfaces:**
- Consumes: `journal.receipt`, `journal.sha256_file`.
- Produces:
  - `rounds.round_path(workspace, n) -> pathlib.Path` (`<workspace>/judge-round-<n>.json`)
  - `rounds.load_round(workspace, n) -> dict` (`{}` when absent)
  - `rounds.merge_round(workspace, n, updates: dict) -> dict` (top-level key merge; never clobbers another writer's keys)
  - `parse_verdicts.parse_judge(text: str) -> dict` — keys: `verdict` (`"PASS" | "REJECT" | "AMBIGUOUS"`), `verdict_line` (raw str or None), plus any of `coverage`, `screen_note`, `leveling`, `standout_signal` (str), `scores` (dict), `missing_or_weak`, `format_issues`, `top_feedback`, `supplementary_questions_for_candidate` (list of str)
  - `parse_verdicts.combine(judges: dict) -> str`
  - `parse_verdicts.main(argv=None) -> int`. CLI: `python3 scripts/parse_verdicts.py --workspace W --round N --ats FILE --recruiter FILE --hiring-manager FILE`. Gate name: `parse_verdicts`. Finding codes: `AMBIGUOUS`, `NO_VERDICT`, `REJECT`.

- [ ] **Step 1: Write the failing test**
    Create `scripts/tests/test_parse_verdicts.py`:
    ````python
    import json
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    import journal
    import parse_verdicts as pv
    import rounds

    ATS_PASS = """I reviewed the CV against the posting.

    ```
    VERDICT: PASS
    COVERAGE: 89% (7 present, 2 partial of 9 must-haves)
    MISSING_OR_WEAK:
      - real-time processing — partial [Prose] (appears in one experience bullet)
      - Spark — partial [Prose] (mentioned in a project bullet)
    FORMAT_ISSUES:
      - none
    TOP_FEEDBACK:
      - Move 'Apache Spark' into the Skills section if truthful
    ```
    """

    REC_PASS = """
    VERDICT: PASS
    SCORES:
      must_have_fit: 4/5 — solid overlap
      readability: 5/5 — skims well
      communication: 4/5 — clear
      logistics: 5/5 — no blockers
      targeting: 4/5 — on target
    SCREEN_NOTE: Clears the screen easily — advance to the hiring manager
    TOP_FEEDBACK:
      - Lead the summary with the recon work
    SUPPLEMENTARY_QUESTIONS_FOR_CANDIDATE:
      - none
    """

    HM_PASS = """
    VERDICT: PASS
    SCORES:
      requirement_match: 4/5 — real overlap
      evidence: 4/5 — concrete
      clarity: 4/5 — readable
      credibility: 5/5 — consistent
      letter_fit: n/a — no letter provided
    LEVELING: correctly leveled — senior IC scope matches the posting
    STANDOUT_SIGNAL: Core maintainer of a widely-used recon library — surfaced well
    TOP_FEEDBACK:
      - Name the scanner vendors in the first bullet
    SUPPLEMENTARY_QUESTIONS_FOR_CANDIDATE:
      - Did the Philips collaboration involve direct clinical deployment?
    """


    def _files(tmp_path, ats=ATS_PASS, rec=REC_PASS, hm=HM_PASS):
        ws = tmp_path / "acme-engineer-2026-08-09"
        ws.mkdir(parents=True, exist_ok=True)
        for name, text in (("ats.txt", ats), ("rec.txt", rec), ("hm.txt", hm)):
            (ws / name).write_text(text, encoding="utf-8")
        return ws, ["--workspace", str(ws), "--round", "1",
                    "--ats", str(ws / "ats.txt"),
                    "--recruiter", str(ws / "rec.txt"),
                    "--hiring-manager", str(ws / "hm.txt")]


    def test_three_clean_passes_are_a_pass_and_print_nothing(tmp_path, capsys):
        ws, argv = _files(tmp_path)
        assert pv.main(argv) == 0
        assert capsys.readouterr().out.strip() == ""
        data = rounds.load_round(ws, 1)
        assert data["combined_verdict"] == "PASS"
        assert data["round"] == 1
        assert set(data["judges"]) == {"ats", "recruiter", "hiring_manager"}


    def test_one_reject_makes_the_round_a_reject(tmp_path, capsys):
        ws, argv = _files(tmp_path, hm=HM_PASS.replace("VERDICT: PASS", "VERDICT: REJECT"))
        assert pv.main(argv) == 1
        assert "REJECT: hiring_manager" in capsys.readouterr().out
        assert rounds.load_round(ws, 1)["combined_verdict"] == "REJECT"


    def test_a_hedged_verdict_is_ambiguous_not_a_pass(tmp_path, capsys):
        """The whole reason this program exists: a model reading prose treats
        'PASS (with reservations)' as a pass and ships a package that looks fully
        reviewed."""
        ws, argv = _files(tmp_path, ats=ATS_PASS.replace(
            "VERDICT: PASS", "VERDICT: PASS (with reservations)"))
        assert pv.main(argv) == 1
        out = capsys.readouterr().out
        assert "AMBIGUOUS: ats" in out and "re-dispatch" in out
        data = rounds.load_round(ws, 1)
        assert data["combined_verdict"] == "AMBIGUOUS"
        assert data["redispatch"] == ["ats"]


    def test_a_missing_verdict_line_is_ambiguous(tmp_path, capsys):
        ws, argv = _files(tmp_path, rec="I think this CV is quite good overall.\n")
        assert pv.main(argv) == 1
        assert "NO_VERDICT: recruiter" in capsys.readouterr().out
        assert rounds.load_round(ws, 1)["combined_verdict"] == "AMBIGUOUS"


    def test_lowercase_verdict_is_accepted(tmp_path):
        ws, argv = _files(tmp_path, ats=ATS_PASS.replace("VERDICT: PASS", "verdict: pass"))
        assert pv.main(argv) == 0


    def test_the_last_verdict_line_wins(tmp_path):
        """A judge pasted its own agent file echoes the template block
        ('VERDICT: PASS | REJECT') and two worked examples. The contract says the
        real block is last."""
        echoed = "VERDICT: PASS | REJECT\nCOVERAGE: <NN>%\n\n" + ATS_PASS
        ws, argv = _files(tmp_path, ats=echoed)
        assert pv.main(argv) == 0


    def test_coverage_is_kept_verbatim_including_n_a(tmp_path):
        ws, argv = _files(tmp_path, ats=ATS_PASS.replace(
            "COVERAGE: 89% (7 present, 2 partial of 9 must-haves)",
            "COVERAGE: n/a (rirekisho form — not ATS-screened)"))
        pv.main(argv)
        assert rounds.load_round(ws, 1)["judges"]["ats"]["coverage"] == \
            "n/a (rirekisho form — not ATS-screened)"


    def test_a_single_none_bullet_becomes_an_empty_list(tmp_path):
        ws, argv = _files(tmp_path)
        pv.main(argv)
        judges = rounds.load_round(ws, 1)["judges"]
        assert judges["ats"]["format_issues"] == []
        assert judges["recruiter"]["supplementary_questions_for_candidate"] == []
        assert judges["hiring_manager"]["supplementary_questions_for_candidate"] == [
            "Did the Philips collaboration involve direct clinical deployment?"]


    def test_advisory_and_score_fields_are_extracted(tmp_path):
        ws, argv = _files(tmp_path)
        pv.main(argv)
        hm = rounds.load_round(ws, 1)["judges"]["hiring_manager"]
        assert hm["leveling"].startswith("correctly leveled")
        assert hm["standout_signal"].startswith("Core maintainer")
        assert hm["scores"]["credibility"] == "5/5 — consistent"
        assert hm["scores"]["letter_fit"] == "n/a — no letter provided"
        rec = rounds.load_round(ws, 1)["judges"]["recruiter"]
        assert rec["screen_note"].startswith("Clears the screen easily")
        assert rec["scores"]["must_have_fit"] == "4/5 — solid overlap"


    def test_merge_round_does_not_clobber_another_writer(tmp_path):
        ws, argv = _files(tmp_path)
        rounds.merge_round(ws, 1, {"dispatch": {"input_hashes": {"cv.md": "ab"}}})
        pv.main(argv)
        data = rounds.load_round(ws, 1)
        assert data["dispatch"]["input_hashes"] == {"cv.md": "ab"}
        assert data["combined_verdict"] == "PASS"


    def test_a_missing_transcript_is_exit_2(tmp_path, capsys):
        ws, argv = _files(tmp_path)
        (ws / "rec.txt").unlink()
        assert pv.main(argv) == 2
        assert "rec.txt" in capsys.readouterr().err


    def test_every_exit_path_leaves_exactly_one_receipt(tmp_path):
        ws, argv = _files(tmp_path)
        pv.main(argv)
        assert len(journal.read_receipts(ws, "parse_verdicts")) == 1
        (ws / "rec.txt").unlink()
        pv.main(argv)
        receipts = journal.read_receipts(ws, "parse_verdicts")
        assert len(receipts) == 2 and receipts[-1]["verdict"] == "could_not_run"
    ````

- [ ] **Step 2: Run test to verify it fails**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_parse_verdicts.py -q`
    Expected: FAIL with `ModuleNotFoundError: No module named 'parse_verdicts'`

- [ ] **Step 3a: Write `scripts/rounds.py`**
    ```python
    #!/usr/bin/env python3
    """judge-round-<n>.json: read and merge, never blind-overwrite.

    Two programs write this file — check_render_freshness records the dispatch
    hashes before the judges run, parse_verdicts writes the verdicts after — and a
    plain write from either would erase the other's evidence. Merging at the top
    level keeps both, which is the only reason the freshness check can be verified
    against the same round it was recorded for.
    """
    from __future__ import annotations

    import json
    import pathlib


    def round_path(workspace, n: int) -> pathlib.Path:
        return pathlib.Path(workspace) / f"judge-round-{int(n)}.json"


    def load_round(workspace, n: int) -> dict:
        path = round_path(workspace, n)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}


    def merge_round(workspace, n: int, updates: dict) -> dict:
        path = round_path(workspace, n)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = load_round(workspace, n)
        data.update(updates)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                        encoding="utf-8")
        return data
    ```

- [ ] **Step 3b: Write `scripts/parse_verdicts.py`**
    ```python
    #!/usr/bin/env python3
    """Parse the three judges' VERDICT blocks into judge-round-<n>.json.

    Every agent file ends with "The orchestrator parses this block programmatically
    — formatting must be exact", and until now no such program existed: the
    orchestrator was a model reading prose. Three things move into code here, and
    each of them is a place where a charitable read produces a package that looks
    fully reviewed and is not:

      * anything other than exactly PASS or REJECT is AMBIGUOUS, and AMBIGUOUS means
        re-dispatch that judge — fail-closed, never "close enough to a pass";
      * combined PASS requires all three, because each agent file states only its own
        bar and none of them knows it is being ANDed;
      * LEVELING and STANDOUT_SIGNAL are extracted but do not touch the verdict —
        treating them as gates stalls a package that should pass, ignoring them drops
        the highest-value tailoring instruction the loop produces.

    Exit 0 = all three returned exactly PASS. Exit 1 = REJECT or AMBIGUOUS (i.e. the
    round needs another pass; findings on stdout). Exit 2 = a transcript is missing.
    """
    from __future__ import annotations

    import argparse
    import datetime
    import pathlib
    import re
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import journal
    import rounds

    GATE = "parse_verdicts"
    JUDGES = ("ats", "recruiter", "hiring_manager")

    SINGLE_LINE_FIELDS = ("VERDICT", "COVERAGE", "SCREEN_NOTE", "LEVELING", "STANDOUT_SIGNAL")
    LIST_FIELDS = ("MISSING_OR_WEAK", "FORMAT_ISSUES", "TOP_FEEDBACK",
                   "SUPPLEMENTARY_QUESTIONS_FOR_CANDIDATE")
    BLOCK_FIELDS = ("SCORES",)

    _KEY_RE = re.compile(r"^\s{0,3}(?P<key>[A-Za-z][A-Za-z_]{2,})\s*:\s*(?P<rest>.*)$")
    _BULLET_RE = re.compile(r"^\s*[-*]\s+(?P<text>.*?)\s*$")
    _SCORE_RE = re.compile(r"^\s+(?P<name>[A-Za-z_]+)\s*:\s*(?P<value>.*?)\s*$")
    _ALL_KEYS = set(SINGLE_LINE_FIELDS) | set(LIST_FIELDS) | set(BLOCK_FIELDS)


    def _key_at(line):
        m = _KEY_RE.match(line)
        if not m:
            return None, None
        key = m.group("key").upper()
        return (key, m.group("rest").strip()) if key in _ALL_KEYS else (None, None)


    def _key_positions(lines):
        """{KEY: index of its LAST occurrence}.

        Last, not first: a judge that was pasted its own agent file echoes the
        template block and two worked examples, each containing a literal VERDICT
        line. The output contract says the real block is the last thing in the reply.
        """
        pos = {}
        for i, line in enumerate(lines):
            key, _ = _key_at(line)
            if key:
                pos[key] = i
        return pos


    def _stop(line):
        """True at the end of a field's body."""
        if _key_at(line)[0]:
            return True
        stripped = line.strip()
        return bool(stripped) and not stripped.startswith("```") \
            and not _BULLET_RE.match(line)


    def _collect_bullets(lines, start):
        out = []
        for line in lines[start + 1:]:
            if _stop(line):
                break
            m = _BULLET_RE.match(line)
            if m and m.group("text").strip():
                out.append(m.group("text").strip())
        if len(out) == 1 and out[0].lower() == "none":
            return []
        return out


    def _collect_scores(lines, start):
        out = {}
        for line in lines[start + 1:]:
            if _key_at(line)[0]:
                break
            m = _SCORE_RE.match(line)
            if m:
                out[m.group("name")] = m.group("value")
            elif line.strip() and not line.strip().startswith("```"):
                break
        return out


    def parse_judge(text: str) -> dict:
        lines = text.replace("\r\n", "\n").split("\n")
        pos = _key_positions(lines)
        fields = {}
        for key in SINGLE_LINE_FIELDS:
            if key in pos:
                fields[key.lower()] = _key_at(lines[pos[key]])[1]
        for key in LIST_FIELDS:
            if key in pos:
                fields[key.lower()] = _collect_bullets(lines, pos[key])
        for key in BLOCK_FIELDS:
            if key in pos:
                fields[key.lower()] = _collect_scores(lines, pos[key])
        raw = fields.pop("verdict", None)
        token = (raw or "").strip().upper()
        fields["verdict_line"] = raw
        fields["verdict"] = token if token in ("PASS", "REJECT") else "AMBIGUOUS"
        return fields


    def combine(judges: dict) -> str:
        verdicts = [judges[j]["verdict"] for j in JUDGES]
        if all(v == "PASS" for v in verdicts):
            return "PASS"
        if any(v == "AMBIGUOUS" for v in verdicts):
            return "AMBIGUOUS"
        return "REJECT"


    def main(argv=None) -> int:
        ap = argparse.ArgumentParser()
        ap.add_argument("--workspace", required=True)
        ap.add_argument("--round", type=int, required=True)
        ap.add_argument("--ats", required=True)
        ap.add_argument("--recruiter", required=True)
        ap.add_argument("--hiring-manager", dest="hiring_manager", required=True)
        args = ap.parse_args(argv)

        ws = pathlib.Path(args.workspace)
        if not ws.is_dir():
            # journal.receipt() would mkdir it, and a gate that creates the
            # workspace it is auditing has manufactured its own evidence.
            print(f"cannot run {GATE}: workspace {ws} does not exist", file=sys.stderr)
            return 2
        paths = {"ats": pathlib.Path(args.ats),
                 "recruiter": pathlib.Path(args.recruiter),
                 "hiring_manager": pathlib.Path(args.hiring_manager)}
        for name, p in paths.items():
            if not p.exists():
                journal.receipt(ws, GATE, {}, "could_not_run", [f"MISSING_INPUT: {p}"])
                print(f"cannot run {GATE}: {name} transcript {p} does not exist",
                      file=sys.stderr)
                return 2

        judges = {n: parse_judge(p.read_text(encoding="utf-8")) for n, p in paths.items()}
        combined = combine(judges)
        redispatch = [n for n in JUDGES if judges[n]["verdict"] == "AMBIGUOUS"]

        findings = []
        for name in JUDGES:
            j = judges[name]
            if j["verdict"] == "AMBIGUOUS":
                if j["verdict_line"] is None:
                    findings.append(f"NO_VERDICT: {name} emitted no VERDICT: line — "
                                    f"re-dispatch this judge")
                else:
                    findings.append(f"AMBIGUOUS: {name} returned {j['verdict_line']!r}, "
                                    f"which is not exactly PASS or REJECT — re-dispatch "
                                    f"this judge")
            elif j["verdict"] == "REJECT":
                findings.append(f"REJECT: {name} returned REJECT")

        rounds.merge_round(ws, args.round, {
            "round": args.round,
            "parsed_at": datetime.datetime.now(datetime.timezone.utc)
                                 .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "judges": judges,
            "combined_verdict": combined,
            "redispatch": redispatch,
        })
        for f in findings:
            print(f)
        journal.receipt(ws, GATE,
                        {n: journal.sha256_file(p) for n, p in paths.items()},
                        "pass" if combined == "PASS" else "fail", findings)
        return 0 if combined == "PASS" else 1


    if __name__ == "__main__":
        sys.exit(main())
    ```

- [ ] **Step 4: Run test to verify it passes**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_parse_verdicts.py -q`
    Expected: PASS — `12 passed`

- [ ] **Step 5: Commit**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/rounds.py scripts/parse_verdicts.py scripts/tests/test_parse_verdicts.py
    git commit -m "feat(gate): parse_verdicts — the parser all three agent files assume exists

Every agent file says the orchestrator parses its block programmatically; no such
program existed. Anything other than exactly PASS/REJECT is now AMBIGUOUS and the
judge is re-dispatched, combined PASS requires all three, and the round becomes a
durable artifact (judge-round-<n>.json) that also gives the loop its round
counter. LEVELING/STANDOUT_SIGNAL are extracted but never touch the verdict."
    ```

---

### Task 11: `scripts/check_render_freshness.py` — void a round judged on stale files

Re-judging a stale `cv.md` produces a perfectly valid *and self-confirming* verdict block: the judges return the same feedback that was supposedly just addressed. Nothing else in the system ties a verdict to the file version it judged.

**Files:**
- Create: `scripts/check_render_freshness.py`
- Test: `scripts/tests/test_check_render_freshness.py`

**Interfaces:**
- Consumes: `journal.receipt`, `journal.sha256_file`, `rounds.merge_round`, `rounds.load_round`.
- Produces: `main(argv=None) -> int`. Two modes:
  `python3 scripts/check_render_freshness.py --workspace W --round N --record FILE [FILE ...]` (at dispatch)
  `python3 scripts/check_render_freshness.py --workspace W --round N` (after the verdicts arrive)
  Gate name: `check_render_freshness`. Finding codes: `STALE`, `MISSING_FILE`, `NO_DISPATCH_RECORD`.

- [ ] **Step 1: Write the failing test**
    Create `scripts/tests/test_check_render_freshness.py`:
    ```python
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    import check_render_freshness as crf
    import journal
    import rounds


    def _ws(tmp_path):
        ws = tmp_path / "acme-engineer-2026-08-09"
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "cv.md").write_text("# Test User\n\n## Experience\n", encoding="utf-8")
        (ws / "letter.md").write_text("Dear Hiring Team,\n", encoding="utf-8")
        return ws


    def test_record_then_verify_unchanged_is_quiet(tmp_path, capsys):
        ws = _ws(tmp_path)
        assert crf.main(["--workspace", str(ws), "--round", "1",
                         "--record", str(ws / "cv.md"), str(ws / "letter.md")]) == 0
        capsys.readouterr()
        assert crf.main(["--workspace", str(ws), "--round", "1"]) == 0
        assert capsys.readouterr().out.strip() == ""


    def test_record_writes_the_hashes_into_the_round_file(tmp_path):
        ws = _ws(tmp_path)
        crf.main(["--workspace", str(ws), "--round", "2", "--record", str(ws / "cv.md")])
        dispatch = rounds.load_round(ws, 2)["dispatch"]
        assert dispatch["input_hashes"]["cv.md"] == journal.sha256_file(ws / "cv.md")
        assert dispatch["ts"].endswith("Z")


    def test_an_edited_file_voids_the_round(tmp_path, capsys):
        ws = _ws(tmp_path)
        crf.main(["--workspace", str(ws), "--round", "1", "--record", str(ws / "cv.md")])
        capsys.readouterr()
        (ws / "cv.md").write_text("# Test User\n\n## Skills\n", encoding="utf-8")
        assert crf.main(["--workspace", str(ws), "--round", "1"]) == 1
        out = capsys.readouterr().out
        assert out.startswith("STALE: cv.md")
        assert "this round is void" in out


    def test_a_deleted_file_is_reported_not_ignored(tmp_path, capsys):
        ws = _ws(tmp_path)
        crf.main(["--workspace", str(ws), "--round", "1", "--record", str(ws / "letter.md")])
        capsys.readouterr()
        (ws / "letter.md").unlink()
        assert crf.main(["--workspace", str(ws), "--round", "1"]) == 1
        assert "MISSING_FILE: letter.md" in capsys.readouterr().out


    def test_verifying_a_round_that_was_never_recorded_is_exit_2(tmp_path, capsys):
        """Not a pass: an unrecorded round is one nobody can vouch for."""
        ws = _ws(tmp_path)
        assert crf.main(["--workspace", str(ws), "--round", "1"]) == 2
        assert "NO_DISPATCH_RECORD" in capsys.readouterr().err


    def test_recording_a_file_that_does_not_exist_is_exit_2(tmp_path, capsys):
        ws = _ws(tmp_path)
        assert crf.main(["--workspace", str(ws), "--round", "1",
                         "--record", str(ws / "nope.md")]) == 2
        assert "nope.md" in capsys.readouterr().err


    def test_recording_does_not_clobber_the_verdicts(tmp_path):
        ws = _ws(tmp_path)
        rounds.merge_round(ws, 1, {"combined_verdict": "PASS"})
        crf.main(["--workspace", str(ws), "--round", "1", "--record", str(ws / "cv.md")])
        assert rounds.load_round(ws, 1)["combined_verdict"] == "PASS"


    def test_each_run_leaves_exactly_one_receipt_including_the_exit_2_paths(tmp_path):
        """An exit-2 run must leave a receipt too: 'the gate could not run' and
        'the gate was never run' produce the same silence otherwise."""
        ws = _ws(tmp_path)
        crf.main(["--workspace", str(ws), "--round", "1", "--record", str(ws / "cv.md")])
        crf.main(["--workspace", str(ws), "--round", "1"])
        crf.main(["--workspace", str(ws), "--round", "9"])                     # never recorded
        crf.main(["--workspace", str(ws), "--round", "3", "--record", str(ws / "nope.md")])
        verdicts = [r["verdict"] for r in journal.read_receipts(ws, "check_render_freshness")]
        assert verdicts == ["recorded", "pass", "could_not_run", "could_not_run"]
    ```

- [ ] **Step 2: Run test to verify it fails**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_check_render_freshness.py -q`
    Expected: FAIL with `ModuleNotFoundError: No module named 'check_render_freshness'`

- [ ] **Step 3: Write minimal implementation**
    Create `scripts/check_render_freshness.py`:
    ```python
    #!/usr/bin/env python3
    """Gate: the judges must have read the files that are on disk now.

    Re-judging a stale cv.md produces a verdict block that is completely valid and
    *self-confirming* — the judges hand back the same feedback that was supposedly
    just addressed, so the loop looks like it is working while nothing changes. No
    timestamp, hash or artifact tied a verdict to the file version it judged, which
    is why the per-round order (edit → re-render → re-judge) had no backstop at all.

    Two modes, in this order:
      --record FILE...  at dispatch, before the judges are spawned
      (no --record)     after the verdicts arrive; a mismatch voids the round

    Exit 0 = fresh / recorded. Exit 1 = stale. Exit 2 = nothing to check.
    """
    from __future__ import annotations

    import argparse
    import datetime
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import journal
    import rounds

    GATE = "check_render_freshness"


    def _rel(ws: pathlib.Path, p: pathlib.Path) -> str:
        try:
            return str(p.resolve().relative_to(ws.resolve()))
        except ValueError:
            return str(p.resolve())


    def main(argv=None) -> int:
        ap = argparse.ArgumentParser()
        ap.add_argument("--workspace", required=True)
        ap.add_argument("--round", type=int, required=True)
        ap.add_argument("--record", nargs="+", default=None, metavar="FILE",
                        help="hash these files now, before dispatching the judges")
        args = ap.parse_args(argv)
        ws = pathlib.Path(args.workspace)
        if not ws.is_dir():
            # journal.receipt() would mkdir it, and a gate that creates the
            # workspace it is auditing has manufactured its own evidence.
            print(f"cannot run {GATE}: workspace {ws} does not exist", file=sys.stderr)
            return 2

        if args.record is not None:
            hashes = {}
            for raw in args.record:
                p = pathlib.Path(raw)
                if not p.exists():
                    journal.receipt(ws, GATE, {}, "could_not_run", [f"MISSING_INPUT: {p}"])
                    print(f"cannot run {GATE}: {p} does not exist", file=sys.stderr)
                    return 2
                hashes[_rel(ws, p)] = journal.sha256_file(p)
            rounds.merge_round(ws, args.round, {"dispatch": {
                "ts": datetime.datetime.now(datetime.timezone.utc)
                              .strftime("%Y-%m-%dT%H:%M:%SZ"),
                "input_hashes": hashes,
            }})
            journal.receipt(ws, GATE, hashes, "recorded", [])
            return 0

        dispatch = (rounds.load_round(ws, args.round) or {}).get("dispatch") or {}
        recorded = dispatch.get("input_hashes") or {}
        if not recorded:
            journal.receipt(ws, GATE, {}, "could_not_run",
                            [f"NO_DISPATCH_RECORD: round {args.round}"])
            print(f"cannot run {GATE}: NO_DISPATCH_RECORD — judge-round-{args.round}.json "
                  f"has no dispatch hashes, so nothing vouches for what the judges read. "
                  f"Re-render, re-record with --record, and re-dispatch.", file=sys.stderr)
            return 2

        findings, now = [], {}
        for rel, was in sorted(recorded.items()):
            p = pathlib.Path(rel)
            if not p.is_absolute():
                p = ws / rel
            if not p.exists():
                findings.append(f"MISSING_FILE: {rel} was hashed at dispatch but is gone "
                                f"from disk — this round is void")
                continue
            now[rel] = journal.sha256_file(p)
            if now[rel] != was:
                findings.append(f"STALE: {rel} hashed {was[:12]}… at dispatch != "
                                f"{now[rel][:12]}… on disk — this round is void; "
                                f"re-render, re-record and re-dispatch all three judges")
        for f in findings:
            print(f)
        journal.receipt(ws, GATE, now, "fail" if findings else "pass", findings)
        return 1 if findings else 0


    if __name__ == "__main__":
        sys.exit(main())
    ```

- [ ] **Step 4: Run test to verify it passes**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_check_render_freshness.py -q`
    Expected: PASS — `8 passed`

- [ ] **Step 5: Commit**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/check_render_freshness.py scripts/tests/test_check_render_freshness.py
    git commit -m "feat(gate): check_render_freshness — void a round judged on stale files

Hash every file at dispatch into judge-round-<n>.json; compare against disk when
the verdicts arrive. A stale re-judge otherwise produces a valid, self-confirming
verdict block in which the judges re-report the problem that was just fixed."
    ```

---

### Task 12: `scripts/check_claims.py` — every new term traces to a source, and the master was not touched

The claim-provenance checkpoint is the skill's highest-value silent rule: it produces no artifact, no citation column, and no diff, so a run can skip it entirely and every downstream gate still passes. `claims.yaml` makes it diffable; this gate makes it decidable.

**Scope, chosen deliberately.** The gate compares a *closed set* of short atomic fields — `skills.*` leaves, `certifications[]`, `experience[].title`, `education[].degree` — because those are exactly where the NOT-ALLOWED table's fabrication classes land (an invented skill/tool, a claimed credential, an inflated title, a degree not held) and each is a string that can be compared exactly. Free prose (bullets, summary) is deliberately out of scope: rewording prose *is* the skill's job, so diffing it would fire on every honest run, and a gate that fires on every run is a gate nobody reads.

**Files:**
- Create: `scripts/check_claims.py`
- Test: `scripts/tests/test_check_claims.py`

**Interfaces:**
- Consumes: `journal.receipt`, `journal.sha256_file`.
- Produces: `main(argv=None) -> int`; `tailored_terms(profile) -> list[tuple[str, str]]` (term, where); `normalize_term(s) -> str`. CLI:
  `python3 scripts/check_claims.py --workspace W --master PATH --record` (at apply-mode entry, fingerprints the master)
  `python3 scripts/check_claims.py --workspace W` (verify)
  Gate name: `check_claims`. Finding codes: `UNSOURCED`, `RETRACTED_CLAIM`, `BAD_CLAIM_ROW`, `MASTER_MUTATED`, `MASTER_TOUCHED`, `NO_MASTER_FINGERPRINT`.

- [ ] **Step 1: Write the failing test**
    Create `scripts/tests/test_check_claims.py`:
    ```python
    import pathlib
    import sys

    import yaml

    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    import check_claims
    import journal

    MASTER = {
        "meta": {"name": "Test User"},
        "skills": {"languages": ["Python", "C++"], "infra": ["Docker"]},
        "experience": [{"title": "Research Engineer", "org": "Acme",
                        "bullets": ["Built a PyTorch reconstruction pipeline on a GPU cluster."]}],
        "education": [{"degree": "MSc Computer Science", "institution": "TU Delft"}],
        "certifications": ["AWS Certified Cloud Practitioner (2024)"],
    }


    def _setup(tmp_path, tailored, claims=None):
        ws = tmp_path / "acme-engineer-2026-08-09"
        ws.mkdir(parents=True, exist_ok=True)
        master = tmp_path / "profile.yaml"
        master.write_text(yaml.safe_dump(MASTER, allow_unicode=True), encoding="utf-8")
        (ws / "tailored-profile.yaml").write_text(
            yaml.safe_dump(tailored, allow_unicode=True), encoding="utf-8")
        if claims is not None:
            (ws / "claims.yaml").write_text(
                yaml.safe_dump(claims, allow_unicode=True), encoding="utf-8")
        check_claims.main(["--workspace", str(ws), "--master", str(master), "--record"])
        return ws, master


    def test_an_unchanged_tailoring_passes_quietly(tmp_path, capsys):
        ws, _ = _setup(tmp_path, MASTER)
        capsys.readouterr()
        assert check_claims.main(["--workspace", str(ws)]) == 0
        assert capsys.readouterr().out.strip() == ""


    def test_a_term_the_master_mentions_only_in_a_bullet_is_sourced(tmp_path, capsys):
        """The cry-wolf case. 'PyTorch' appears in a master bullet but not in the
        master's skills list; surfacing it into Skills is honest reframing, which is
        the whole point of the skill. Firing here would make the gate unusable."""
        tailored = {**MASTER, "skills": {"languages": ["Python", "C++"],
                                         "ml": ["PyTorch"], "infra": ["Docker"]}}
        ws, _ = _setup(tmp_path, tailored)
        capsys.readouterr()
        assert check_claims.main(["--workspace", str(ws)]) == 0
        assert capsys.readouterr().out.strip() == ""


    def test_a_new_term_with_no_claims_row_fails(tmp_path, capsys):
        tailored = {**MASTER, "skills": {"languages": ["Python"], "infra": ["Docker", "Kubernetes"]}}
        ws, _ = _setup(tmp_path, tailored)
        capsys.readouterr()
        assert check_claims.main(["--workspace", str(ws)]) == 1
        out = capsys.readouterr().out
        assert out.startswith("UNSOURCED:")
        assert '"Kubernetes"' in out
        assert "skills.infra" in out
        assert "claims.yaml" in out


    def test_a_new_term_with_a_claims_row_passes(tmp_path, capsys):
        tailored = {**MASTER, "skills": {"languages": ["Python"], "infra": ["Docker", "Kubernetes"]}}
        claims = [{"term": "Kubernetes", "where": "tailored-profile.yaml:skills.infra",
                   "source_kind": "session-answer",
                   "source_ref": "user confirmed 2 years of k8s at Acme, 2026-08-09",
                   "session_date": "2026-08-09", "retracted": None}]
        ws, _ = _setup(tmp_path, tailored, claims)
        capsys.readouterr()
        assert check_claims.main(["--workspace", str(ws)]) == 0
        assert capsys.readouterr().out.strip() == ""


    def test_the_retracted_key_is_required_but_null_is_its_normal_value(tmp_path, capsys):
        """`retracted: null` is what a live claim looks like — requiring a
        non-empty string would invalidate every honest row. The KEY must still be
        present: in a schema where "absent" and "not retracted" look identical, a
        withdrawn claim leaves no scar, and a scar is the whole point of the field.
        Plan 4's check_mock.py requires the same six keys."""
        tailored = {**MASTER, "skills": {"infra": ["Kubernetes"]}}
        row = {"term": "Kubernetes", "where": "tailored-profile.yaml:skills.infra",
               "source_kind": "session-answer", "source_ref": "x",
               "session_date": "2026-08-09", "retracted": None}
        ws, _ = _setup(tmp_path / "null-is-fine", tailored, [row])
        capsys.readouterr()
        assert check_claims.main(["--workspace", str(ws)]) == 0
        assert capsys.readouterr().out.strip() == ""

        absent = {k: v for k, v in row.items() if k != "retracted"}
        ws2, _ = _setup(tmp_path / "key-absent", tailored, [absent])
        capsys.readouterr()
        assert check_claims.main(["--workspace", str(ws2)]) == 1
        assert "BAD_CLAIM_ROW" in capsys.readouterr().out


    def test_a_retracted_row_does_not_source_the_claim(tmp_path, capsys):
        tailored = {**MASTER, "skills": {"infra": ["Kubernetes"]}}
        claims = [{"term": "Kubernetes", "where": "tailored-profile.yaml:skills.infra",
                   "source_kind": "session-answer", "source_ref": "x",
                   "session_date": "2026-08-09", "retracted": "walk-back-2026-08-09"}]
        ws, _ = _setup(tmp_path, tailored, claims)
        capsys.readouterr()
        assert check_claims.main(["--workspace", str(ws)]) == 1
        assert "RETRACTED_CLAIM" in capsys.readouterr().out


    def test_an_inflated_title_is_caught(tmp_path, capsys):
        tailored = {**MASTER, "experience": [{"title": "Head of Reconstruction", "org": "Acme",
                                              "bullets": ["Built a PyTorch pipeline."]}]}
        ws, _ = _setup(tmp_path, tailored)
        capsys.readouterr()
        assert check_claims.main(["--workspace", str(ws)]) == 1
        out = capsys.readouterr().out
        assert "UNSOURCED" in out and "experience[0].title" in out


    def test_bad_claim_rows_are_reported_individually(tmp_path, capsys):
        claims = [
            {"term": "K8s", "where": "x", "source_kind": "guesswork",
             "source_ref": "y", "session_date": "2026-08-09", "retracted": None},
            {"term": "Rust", "where": "x", "source_kind": "profile-line",
             "source_ref": "y", "session_date": "9 Aug 2026", "retracted": None},
            {"term": "Go", "source_kind": "profile-line", "source_ref": "y",
             "session_date": "2026-08-09", "retracted": None},
        ]
        ws, _ = _setup(tmp_path, MASTER, claims)
        capsys.readouterr()
        assert check_claims.main(["--workspace", str(ws)]) == 1
        out = capsys.readouterr().out
        assert "BAD_CLAIM_ROW: claims.yaml[0]" in out and "guesswork" in out
        assert "BAD_CLAIM_ROW: claims.yaml[1]" in out and "9 Aug 2026" in out
        assert "BAD_CLAIM_ROW: claims.yaml[2]" in out and "where" in out


    def test_a_mutated_master_fails_the_gate(tmp_path, capsys):
        ws, master = _setup(tmp_path, MASTER)
        capsys.readouterr()
        narrowed = {**MASTER, "skills": {"languages": ["Python"]}}
        master.write_text(yaml.safe_dump(narrowed, allow_unicode=True), encoding="utf-8")
        assert check_claims.main(["--workspace", str(ws)]) == 1
        out = capsys.readouterr().out
        assert "MASTER_MUTATED" in out
        assert "never mutated by tailoring" in out


    def test_verifying_without_a_recorded_fingerprint_is_exit_2(tmp_path, capsys):
        ws = tmp_path / "ws"; ws.mkdir()
        (ws / "tailored-profile.yaml").write_text("meta: {}\n", encoding="utf-8")
        assert check_claims.main(["--workspace", str(ws)]) == 2
        assert "NO_MASTER_FINGERPRINT" in capsys.readouterr().err


    def test_each_run_leaves_exactly_one_receipt_including_the_exit_2_path(tmp_path):
        ws, _ = _setup(tmp_path, MASTER)
        check_claims.main(["--workspace", str(ws)])
        (ws / check_claims.FINGERPRINT).unlink()
        assert check_claims.main(["--workspace", str(ws)]) == 2
        verdicts = [r["verdict"] for r in journal.read_receipts(ws, "check_claims")]
        assert verdicts == ["recorded", "pass", "could_not_run"]
    ```

- [ ] **Step 2: Run test to verify it fails**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_check_claims.py -q`
    Expected: FAIL with `ModuleNotFoundError: No module named 'check_claims'`

- [ ] **Step 3: Write minimal implementation**
    Create `scripts/check_claims.py`:
    ```python
    #!/usr/bin/env python3
    """Gate: every claim the tailoring added traces to a permitted source.

    The claim-provenance checkpoint is the skill's highest-value rule and, until
    claims.yaml existed, its most silent one: no provenance file, no citation column
    in any required output, no script diffing the tailored CV against the master. A
    run could skip it entirely and every downstream gate still passed — while every
    automated signal in the system (an ATS REJECT on a missing keyword) rewarded the
    dishonest edit.

    Scope is a closed set of short atomic fields — skills leaves, certifications,
    experience titles, education degrees — because that is where the four named
    fabrication classes land and each is a string that compares exactly. Free prose
    is deliberately out: rewording prose IS the skill's job, and a gate that fires on
    every honest run is a gate people learn to skip.

    Also fails if profile.yaml changed during the run. Overwriting the master is
    destructive and unrecoverable, and the damage only surfaces on the NEXT
    application, when the "master" has already been narrowed to the previous job.

    Exit 0 = clean. Exit 1 = findings. Exit 2 = nothing recorded to check against.
    """
    from __future__ import annotations

    import argparse
    import json
    import pathlib
    import re
    import sys
    import unicodedata

    import yaml

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import journal

    GATE = "check_claims"
    FINGERPRINT = "master-fingerprint.json"
    SOURCE_KINDS = ("profile-line", "session-answer", "fetched-artifact")
    CLAIM_KEYS = ("term", "where", "source_kind", "source_ref", "session_date",
                  "retracted")
    # `retracted` is a PRESENCE check, not a non-empty check: null is what a live
    # claim looks like, and demanding a value would make every honest row invalid.
    # It is still required to be there — in a schema where "absent" and "not
    # retracted" are indistinguishable, a withdrawn claim leaves no scar, and the
    # scar is the entire reason the field exists. Plan 4's check_mock.py requires
    # the same six keys; a row that satisfied one and failed the other would make
    # the two gates disagree about a shared artifact.
    PRESENCE_ONLY_KEYS = ("retracted",)
    _DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    _PUNCT = re.compile(r"[^\w\s+#./-]", re.UNICODE)


    def normalize_term(s) -> str:
        s = unicodedata.normalize("NFKC", str(s or "")).lower()
        return " ".join(_PUNCT.sub(" ", s).split())


    def _as_list(v):
        if isinstance(v, str):
            return [v]
        if isinstance(v, list):
            return v
        return []


    def _flat(v):
        if isinstance(v, dict):
            return " ".join(str(x) for x in v.values())
        return str(v)


    def tailored_terms(profile) -> list:
        """[(term, where)] over the closed set of fabrication-prone fields."""
        out = []
        skills = profile.get("skills") or {}
        if isinstance(skills, dict):
            for group, items in skills.items():
                for item in _as_list(items):
                    out.append((_flat(item), f"skills.{group}"))
        else:
            for item in _as_list(skills):
                out.append((_flat(item), "skills"))
        for i, cert in enumerate(profile.get("certifications") or []):
            out.append((_flat(cert), f"certifications[{i}]"))
        for i, ex in enumerate(profile.get("experience") or []):
            if isinstance(ex, dict) and ex.get("title"):
                out.append((str(ex["title"]), f"experience[{i}].title"))
        for i, ed in enumerate(profile.get("education") or []):
            if isinstance(ed, dict) and ed.get("degree"):
                out.append((str(ed["degree"]), f"education[{i}].degree"))
        return out


    def _claim_index(claims):
        """{normalized term: row} for live rows, plus findings for malformed ones."""
        live, retracted, findings = {}, {}, []
        for i, row in enumerate(claims or []):
            if not isinstance(row, dict):
                findings.append(f"BAD_CLAIM_ROW: claims.yaml[{i}] is not a mapping")
                continue
            for key in CLAIM_KEYS:
                if key not in row:
                    findings.append(f"BAD_CLAIM_ROW: claims.yaml[{i}] is missing required "
                                    f"key {key!r}")
                elif key not in PRESENCE_ONLY_KEYS and not str(row.get(key) or "").strip():
                    findings.append(f"BAD_CLAIM_ROW: claims.yaml[{i}] has an empty "
                                    f"required key {key!r}")
            if row.get("source_kind") and row["source_kind"] not in SOURCE_KINDS:
                findings.append(f"BAD_CLAIM_ROW: claims.yaml[{i}] source_kind "
                                f"{row['source_kind']!r} is not one of "
                                f"{', '.join(SOURCE_KINDS)} — there is no fourth source")
            if row.get("session_date") and not _DATE_RE.match(str(row["session_date"])):
                findings.append(f"BAD_CLAIM_ROW: claims.yaml[{i}] session_date "
                                f"{row['session_date']!r} is not YYYY-MM-DD")
            key = normalize_term(row.get("term"))
            if not key:
                continue
            (retracted if row.get("retracted") else live)[key] = row
        return live, retracted, findings


    def main(argv=None) -> int:
        ap = argparse.ArgumentParser()
        ap.add_argument("--workspace", required=True)
        ap.add_argument("--master", default=None)
        ap.add_argument("--record", action="store_true",
                        help="fingerprint the master profile at apply-mode entry")
        args = ap.parse_args(argv)
        ws = pathlib.Path(args.workspace)
        if not ws.is_dir():
            # journal.receipt() would mkdir it, and a gate that creates the
            # workspace it is auditing has manufactured its own evidence.
            print(f"cannot run {GATE}: workspace {ws} does not exist", file=sys.stderr)
            return 2
        fp_path = ws / FINGERPRINT

        if args.record:
            if not args.master or not pathlib.Path(args.master).exists():
                journal.receipt(ws, GATE, {}, "could_not_run",
                                [f"MISSING_INPUT: master {args.master}"])
                print(f"cannot run {GATE}: --master must point at an existing profile.yaml",
                      file=sys.stderr)
                return 2
            master = pathlib.Path(args.master).resolve()
            digest = journal.sha256_file(master)
            ws.mkdir(parents=True, exist_ok=True)
            fp_path.write_text(json.dumps({
                "path": str(master), "sha256": digest,
                "mtime_ns": master.stat().st_mtime_ns}, indent=2) + "\n", encoding="utf-8")
            journal.receipt(ws, GATE, {"profile.yaml": digest}, "recorded", [])
            return 0

        tailored_path = ws / "tailored-profile.yaml"
        if not fp_path.exists() or not tailored_path.exists():
            missing = FINGERPRINT if not fp_path.exists() else "tailored-profile.yaml"
            code = "NO_MASTER_FINGERPRINT" if missing == FINGERPRINT else "MISSING_INPUT"
            journal.receipt(ws, GATE, {}, "could_not_run", [f"{code}: {ws / missing}"])
            print(f"cannot run {GATE}: {code} — {ws / missing} does not exist; run with "
                  f"--record --master <profile.yaml> at apply-mode entry", file=sys.stderr)
            return 2

        fp = json.loads(fp_path.read_text(encoding="utf-8"))
        master = pathlib.Path(fp["path"])
        findings = []
        if not master.exists():
            findings.append(f"MASTER_MUTATED: {master} no longer exists — the master "
                            f"profile is never mutated by tailoring")
            master_text = ""
        else:
            now = journal.sha256_file(master)
            master_text = normalize_term(master.read_text(encoding="utf-8"))
            if now != fp["sha256"]:
                findings.append(f"MASTER_MUTATED: profile.yaml content changed during this "
                                f"run ({fp['sha256'][:12]}… → {now[:12]}…) — the master "
                                f"profile is never mutated by tailoring; tailoring works on "
                                f"the workspace copy")
            elif master.stat().st_mtime_ns != fp.get("mtime_ns"):
                findings.append(f"MASTER_TOUCHED: profile.yaml's mtime changed during this "
                                f"run though its content is identical — something wrote to "
                                f"the master; confirm nothing is editing it")

        tailored = yaml.safe_load(tailored_path.read_text(encoding="utf-8")) or {}
        claims_path = ws / "claims.yaml"
        claims = []
        if claims_path.exists():
            claims = yaml.safe_load(claims_path.read_text(encoding="utf-8")) or []
        live, retracted, claim_findings = _claim_index(claims)
        findings += claim_findings

        for term, where in tailored_terms(tailored):
            key = normalize_term(term)
            if len(key) < 2 or key in master_text:
                continue
            if key in live:
                continue
            if key in retracted:
                findings.append(f'RETRACTED_CLAIM: "{term}" at '
                                f'tailored-profile.yaml:{where} is backed only by a '
                                f'claims.yaml row marked retracted: '
                                f'{retracted[key]["retracted"]} — remove the claim or '
                                f're-source it')
                continue
            findings.append(f'UNSOURCED: "{term}" appears in '
                            f'tailored-profile.yaml:{where}, is absent from profile.yaml, '
                            f'and has no claims.yaml row. A keyword that appears in the job '
                            f'description is not evidence the candidate has it — source it '
                            f'or move it to HONEST-GAPS')

        for f in findings:
            print(f)
        journal.receipt(ws, GATE,
                        {"tailored-profile.yaml": journal.sha256_file(tailored_path)},
                        "fail" if findings else "pass", findings)
        return 1 if findings else 0


    if __name__ == "__main__":
        sys.exit(main())
    ```

- [ ] **Step 4: Run test to verify it passes**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_check_claims.py -q`
    Expected: PASS — `11 passed`

- [ ] **Step 5: Commit**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/check_claims.py scripts/tests/test_check_claims.py
    git commit -m "feat(gate): check_claims — provenance for every added claim

Every term the tailoring introduced into skills, certifications, a job title or a
degree must either already appear in profile.yaml or carry a claims.yaml row.
Free prose is deliberately out of scope: rewording is the skill's job, and a gate
that fires on every honest run is a gate people skip.

Also fingerprints profile.yaml at mode entry and fails if it changed — overwriting
the master is unrecoverable and only surfaces on the NEXT application."
    ```

---

### Task 13: `scripts/lint_cv.py` — the mechanically decidable slice of the quality pass

Clichés, weak openers, bullet length and repeated opening verbs are enumerated in prose today and scanned by eye. Dimension 1 of the AI-uniformity check ("verb variety") is countable; dimensions 3 and 4 (voice, specificity) are not and stay inline in SKILL.md.

**Files:**
- Create: `scripts/lint_cv.py`
- Test: `scripts/tests/test_lint_cv.py`

**Interfaces:**
- Consumes: `journal.receipt`, `journal.sha256_file`.
- Produces: `main(argv=None) -> int`; `findings_for(text: str) -> list[str]`. CLI: `python3 scripts/lint_cv.py --workspace W [--cv PATH]` (default `<W>/cv.md`). Gate name: `lint_cv`. Finding codes: `CLICHE`, `WEAK_OPENER`, `LONG_BULLET`, `REPEATED_VERB`.

- [ ] **Step 1: Write the failing test**
    Create `scripts/tests/test_lint_cv.py`:
    ```python
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    import journal
    import lint_cv

    CLEAN = """# Test User

    ## Experience

    ### Research Engineer — Acme (2022–present)
    - Built a GPU reconstruction pipeline that cut scan time from 12 to 7 minutes.
    - Drove the migration of 40 clinical protocols onto the new solver.
    - Drove a two-person team through the vendor integration with Philips.
    - Advised the finance team on a leveraged buyout of the imaging division.

    ## Skills
    - Python, C++, PyTorch
    """


    def _cv(tmp_path, text=CLEAN):
        ws = tmp_path / "acme-engineer-2026-08-09"
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "cv.md").write_text(text, encoding="utf-8")
        return ws


    def test_a_clean_cv_passes_silently(tmp_path, capsys):
        ws = _cv(tmp_path)
        assert lint_cv.main(["--workspace", str(ws)]) == 0
        assert capsys.readouterr().out.strip() == ""


    def test_leveraged_buyout_is_not_a_cliche(tmp_path):
        """A finance CV legitimately says 'leveraged buyout'. Firing on it would
        teach the reader to skip every CLICHE line."""
        assert lint_cv.findings_for("- Advised on a leveraged buyout of the division.") == []


    def test_two_bullets_opening_with_the_same_verb_is_not_flagged(tmp_path):
        """Two is variation; three is a template. The threshold has to sit where
        ordinary writing does not trip it.

        The fixture opens two bullets with 'Drove' rather than 'Led' on purpose:
        `findings_for` only tracks openers of 4+ characters, so a three-letter verb
        is never counted and a test built on it would pass without the threshold
        ever being reached — proving the button exists, not that pressing it does
        anything. Measured on CLEAN: openers == {'built': [6], 'drove': [7, 8],
        'advised': [9], 'python': [12]}."""
        assert [f for f in lint_cv.findings_for(CLEAN) if f.startswith("REPEATED_VERB")] == []


    def test_cliche_is_reported_with_its_line_number(tmp_path, capsys):
        ws = _cv(tmp_path, CLEAN + "\n- A results-driven engineer with a proven track record.\n")
        assert lint_cv.main(["--workspace", str(ws)]) == 1
        out = capsys.readouterr().out
        assert "CLICHE: cv.md:" in out
        assert "results-driven" in out and "proven track record" in out


    def test_weak_openers_are_reported(tmp_path, capsys):
        ws = _cv(tmp_path, "# X\n- Responsible for the reconstruction pipeline and its tests.\n")
        assert lint_cv.main(["--workspace", str(ws)]) == 1
        out = capsys.readouterr().out
        assert "WEAK_OPENER: cv.md:2" in out and "Responsible for" in out


    def test_an_over_long_bullet_is_reported_with_its_length(tmp_path, capsys):
        long_bullet = "- " + ("Rebuilt the acquisition pipeline end to end " * 8).strip() + "."
        ws = _cv(tmp_path, "# X\n" + long_bullet + "\n")
        assert lint_cv.main(["--workspace", str(ws)]) == 1
        out = capsys.readouterr().out
        assert "LONG_BULLET: cv.md:2" in out and "characters" in out


    def test_three_bullets_with_the_same_opening_verb_are_reported(tmp_path, capsys):
        text = ("# X\n"
                "- Spearheaded the solver rewrite across two teams.\n"
                "- Spearheaded the vendor migration for 40 protocols.\n"
                "- Spearheaded the clinical rollout at three sites.\n")
        ws = _cv(tmp_path, text)
        assert lint_cv.main(["--workspace", str(ws)]) == 1
        out = capsys.readouterr().out
        assert "REPEATED_VERB" in out and "spearheaded" in out
        assert "2, 3, 4" in out


    def test_missing_cv_is_exit_2(tmp_path, capsys):
        ws = tmp_path / "empty"; ws.mkdir()
        assert lint_cv.main(["--workspace", str(ws)]) == 2
        assert "cv.md" in capsys.readouterr().err


    def test_each_run_leaves_exactly_one_receipt_including_the_exit_2_path(tmp_path):
        ws = _cv(tmp_path)
        lint_cv.main(["--workspace", str(ws)])
        (ws / "cv.md").unlink()
        assert lint_cv.main(["--workspace", str(ws)]) == 2
        assert [r["verdict"] for r in journal.read_receipts(ws, "lint_cv")] == \
            ["pass", "could_not_run"]
    ```

- [ ] **Step 2: Run test to verify it fails**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_lint_cv.py -q`
    Expected: FAIL with `ModuleNotFoundError: No module named 'lint_cv'`

- [ ] **Step 3: Write minimal implementation**
    Create `scripts/lint_cv.py`:
    ```python
    #!/usr/bin/env python3
    """Gate: the mechanically decidable half of the CV quality pass.

    Nothing downstream scores voice — the ATS judge is a literal text matcher, the
    recruiter judge scores readability not phrasing — so a grammatical,
    keyword-complete, utterly templated CV passes all three judges and loses at the
    real human recruiter, outside every loop this skill can observe. What a program
    can decide goes here; dimensions 3 and 4 of the AI-uniformity check (voice,
    specificity) cannot be decided by a program and stay inline in SKILL.md.

    Exit 0 = clean. Exit 1 = findings. Exit 2 = no cv.md.
    """
    from __future__ import annotations

    import argparse
    import pathlib
    import re
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import journal

    GATE = "lint_cv"

    # Multi-word clichés are unambiguous. "leveraged" is not: a finance CV
    # legitimately says "leveraged buyout", so that one collocation is carved out
    # rather than teaching the reader to ignore the whole CLICHE class.
    CLICHES = [
        ("results-driven", re.compile(r"\bresults[- ]driven\b", re.I)),
        ("proven track record", re.compile(r"\bproven track record\b", re.I)),
        ("synergy", re.compile(r"\bsynerg(y|ies|istic)\b", re.I)),
        ("leveraged", re.compile(r"\bleverag(e|ed|es|ing)\b(?!\s+buyout)", re.I)),
        ("excellent communicator", re.compile(r"\bexcellent communicator\b", re.I)),
        ("team player", re.compile(r"\bteam player\b", re.I)),
        ("passionate about technology", re.compile(r"\bpassionate about technology\b", re.I)),
        ("references available on request",
         re.compile(r"\breferences available (up)?on request\b", re.I)),
    ]
    WEAK_OPENERS = ("responsible for", "worked on", "helped with", "assisted in",
                    "was involved in")
    # ~120 characters is one rendered line at CV widths; two is the stated ceiling.
    MAX_BULLET_CHARS = 240
    # Two bullets sharing an opening verb is variation; three is a template.
    REPEAT_VERB_THRESHOLD = 3

    _BULLET_RE = re.compile(r"^\s*[-*]\s+(?P<text>.+?)\s*$")
    _WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")


    def findings_for(text: str, name: str = "cv.md") -> list:
        out, openers = [], {}
        for n, line in enumerate(text.split("\n"), 1):
            m = _BULLET_RE.match(line)
            if not m:
                continue
            body = m.group("text")
            hits = [label for label, rx in CLICHES if rx.search(body)]
            if hits:
                out.append(f"CLICHE: {name}:{n} contains {', '.join(repr(h) for h in hits)} "
                           f"— say the specific thing instead")
            low = body.lower()
            for opener in WEAK_OPENERS:
                if low.startswith(opener):
                    out.append(f"WEAK_OPENER: {name}:{n} opens with "
                               f"{body[:len(opener)]!r} — open with an action verb and "
                               f"the result")
                    break
            if len(body) > MAX_BULLET_CHARS:
                out.append(f"LONG_BULLET: {name}:{n} is {len(body)} characters "
                           f"(limit {MAX_BULLET_CHARS} ≈ two rendered lines) — it is "
                           f"either two bullets or it is padded")
            first = _WORD_RE.match(body)
            if first and len(first.group(0)) >= 4:
                openers.setdefault(first.group(0).lower(), []).append(n)
        for verb, lines in sorted(openers.items()):
            if len(lines) >= REPEAT_VERB_THRESHOLD:
                out.append(f"REPEATED_VERB: {verb!r} opens {len(lines)} bullets (lines "
                           f"{', '.join(str(x) for x in lines)}) — vary the verb; "
                           f"repetition is the first thing that reads as generated")
        return out


    def main(argv=None) -> int:
        ap = argparse.ArgumentParser()
        ap.add_argument("--workspace", required=True)
        ap.add_argument("--cv", default=None, help="default: <workspace>/cv.md")
        args = ap.parse_args(argv)
        ws = pathlib.Path(args.workspace)
        if not ws.is_dir():
            # journal.receipt() would mkdir it, and a gate that creates the
            # workspace it is auditing has manufactured its own evidence.
            print(f"cannot run {GATE}: workspace {ws} does not exist", file=sys.stderr)
            return 2
        path = pathlib.Path(args.cv) if args.cv else ws / "cv.md"
        if not path.exists():
            journal.receipt(ws, GATE, {}, "could_not_run", [f"MISSING_INPUT: {path}"])
            print(f"cannot run {GATE}: {path} does not exist", file=sys.stderr)
            return 2
        findings = findings_for(path.read_text(encoding="utf-8"), path.name)
        for f in findings:
            print(f)
        journal.receipt(ws, GATE, {path.name: journal.sha256_file(path)},
                        "fail" if findings else "pass", findings)
        return 1 if findings else 0


    if __name__ == "__main__":
        sys.exit(main())
    ```

- [ ] **Step 4: Run test to verify it passes**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_lint_cv.py -q`
    Expected: PASS — `9 passed`

- [ ] **Step 5: Commit**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/lint_cv.py scripts/tests/test_lint_cv.py
    git commit -m "feat(gate): lint_cv — clichés, weak openers, bullet length, repeated verbs

The decidable half of the quality pass. Nothing downstream scores voice, so a
templated CV clears all three judges and loses at the real recruiter. 'leveraged
buyout' is carved out of the cliché rule and two bullets sharing a verb is not
flagged — a check that cries wolf is one people learn to skip."
    ```

---

### Task 14: `scripts/check_letter.py` — the letter constraints the renderer will not enforce

`render_letter.py` passes each `body` string straight into Markdown, docx and LaTeX with no stripping, so `**bold**` prints four asterisks on the PDF and a sender name in `closing` prints twice. This is the same failure class as a format string rendered raw onto a slide: a formatting contract documented only in prose, whose violation is rendered literally.

**A note on `posting.yaml`.** The extraction schema has no `company` field today, so the letter's recipient cannot be verified against anything. This gate therefore *requires* one and reports `NO_COMPANY_IN_POSTING` when it is absent, rather than skipping the check quietly. Task 20 adds `company` to the extraction field table in SKILL.md.

**Files:**
- Create: `scripts/check_letter.py`
- Test: `scripts/tests/test_check_letter.py`

**Interfaces:**
- Consumes: `journal.receipt`, `journal.sha256_file`.
- Produces: `main(argv=None) -> int`; `findings_for(letter: dict, posting: dict) -> list[str]`. CLI: `python3 scripts/check_letter.py --workspace W [--letter PATH] [--posting PATH]` (defaults `<W>/letter.yaml`, `<W>/posting.yaml`). Gate name: `check_letter`. Finding codes: `MARKDOWN_IN_BODY`, `WORD_COUNT`, `PARA_COUNT`, `NAME_DUPLICATED`, `COMPANY_MISMATCH`, `ROLE_NOT_NAMED`, `NO_COMPANY_IN_POSTING`.

- [ ] **Step 1: Write the failing test**
    Create `scripts/tests/test_check_letter.py`:
    ```python
    import pathlib
    import sys

    import yaml

    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    import check_letter
    import journal

    POSTING = {"company": "Acme Medical Systems B.V.",
               "role_title": "Senior Reconstruction Engineer",
               "must_haves": ["MRI reconstruction"]}

    PARA = ("I have spent four years building GPU reconstruction pipelines for clinical "
            "MRI, and the work your team published on motion-resolved cine recon is the "
            "closest thing I have seen to the problem I want to keep solving. At Acme I "
            "rebuilt the solver that cut a twelve-minute scan to seven, working directly "
            "with radiographers to keep the protocol changes clinically safe and "
            "auditable across three hospital sites. ")


    # PARA is 67 words (measured). The default body is FOUR paragraphs — 277 words,
    # inside both the 250–400 word band and the 3–4 paragraph band. Three paragraphs
    # would be 210 words, which trips the gate's own floor: every "passes silently"
    # test would then fail, and the fixture would be teaching the reader that this
    # gate cries wolf.
    def _letter(body=None, **over):
        d = {"sender": {"name": "Test User", "email": "t@x.com", "location": "Delft"},
             "recipient": {"name": "Hiring Team", "company": "Acme Medical Systems B.V.",
                           "location": "Eindhoven"},
             "date": "2026-08-09",
             "salutation": "Geachte heer/mevrouw,",
             "body": body if body is not None else [
                 PARA + "I am applying for the Senior Reconstruction Engineer role.",
                 PARA, PARA, PARA],
             "closing": "Met vriendelijke groet,"}
        d.update(over)
        return d


    def _ws(tmp_path, letter, posting=POSTING):
        ws = tmp_path / "acme-engineer-2026-08-09"
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "letter.yaml").write_text(yaml.safe_dump(letter, allow_unicode=True),
                                        encoding="utf-8")
        if posting is not None:
            (ws / "posting.yaml").write_text(yaml.safe_dump(posting, allow_unicode=True),
                                             encoding="utf-8")
        return ws


    def test_a_well_formed_letter_passes_silently(tmp_path, capsys):
        ws = _ws(tmp_path, _letter())
        assert check_letter.main(["--workspace", str(ws)]) == 0
        assert capsys.readouterr().out.strip() == ""


    def test_markdown_in_a_body_string_is_caught(tmp_path, capsys):
        """render_letter passes body strings through untouched, so '**bold**' prints
        four asterisks on the PDF."""
        body = _letter()["body"]
        body[1] = "I **rebuilt** the solver. " + PARA
        ws = _ws(tmp_path, _letter(body=body))
        assert check_letter.main(["--workspace", str(ws)]) == 1
        out = capsys.readouterr().out
        assert "MARKDOWN_IN_BODY: body[1]" in out and "**" in out


    def test_a_bulleted_body_paragraph_is_caught(tmp_path, capsys):
        body = _letter()["body"]
        body[2] = "- MRI reconstruction\n- GPU solvers\n" + PARA   # stays in the word band
        ws = _ws(tmp_path, _letter(body=body))
        assert check_letter.main(["--workspace", str(ws)]) == 1
        out = capsys.readouterr().out
        assert "MARKDOWN_IN_BODY: body[2]" in out
        assert "WORD_COUNT" not in out and "PARA_COUNT" not in out


    def test_word_count_below_the_floor_is_caught(tmp_path, capsys):
        ws = _ws(tmp_path, _letter(body=["Short.", "Also short.", "Still short."]))
        assert check_letter.main(["--workspace", str(ws)]) == 1
        out = capsys.readouterr().out
        assert "WORD_COUNT" in out and "250" in out and "400" in out


    def test_word_count_above_the_ceiling_is_caught(tmp_path, capsys):
        ws = _ws(tmp_path, _letter(body=[PARA * 3, PARA * 3, PARA * 3]))
        assert check_letter.main(["--workspace", str(ws)]) == 1
        assert "WORD_COUNT" in capsys.readouterr().out


    def test_paragraph_count_outside_three_to_four_is_caught(tmp_path, capsys):
        """`motivation-letter.md:121`: "3–4 paragraphs total. Never a single
        monolithic block. Never more than 4 unless a specific structure requires it
        (rare)." A gate that silently permitted 5 would be enforcing a rule the
        reference does not contain."""
        ws = _ws(tmp_path, _letter(body=[PARA * 2, PARA * 2]))
        assert check_letter.main(["--workspace", str(ws)]) == 1
        assert "PARA_COUNT" in capsys.readouterr().out
        ws = _ws(tmp_path / "five", _letter(body=[PARA] * 5))
        assert check_letter.main(["--workspace", str(ws)]) == 1
        out = capsys.readouterr().out
        assert "PARA_COUNT" in out and "5 paragraphs" in out


    def test_sender_name_in_the_closing_prints_twice(tmp_path, capsys):
        """render_letter appends sender.name after the closing automatically."""
        ws = _ws(tmp_path, _letter(closing="Met vriendelijke groet,\nTest User"))
        assert check_letter.main(["--workspace", str(ws)]) == 1
        out = capsys.readouterr().out
        assert "NAME_DUPLICATED" in out and "Test User" in out


    def test_a_wrong_company_is_caught(tmp_path, capsys):
        letter = _letter()
        letter["recipient"]["company"] = "Acme Manufacturing"
        ws = _ws(tmp_path, letter)
        assert check_letter.main(["--workspace", str(ws)]) == 1
        out = capsys.readouterr().out
        assert "COMPANY_MISMATCH" in out and "Acme Medical Systems B.V." in out


    def test_a_shorter_but_matching_company_name_is_accepted(tmp_path, capsys):
        """'Acme Medical Systems' addressed to 'Acme Medical Systems B.V.' is
        correct in a letter; only a genuinely different name is an error."""
        letter = _letter()
        letter["recipient"]["company"] = "Acme Medical Systems"
        ws = _ws(tmp_path, letter)
        assert check_letter.main(["--workspace", str(ws)]) == 0
        assert capsys.readouterr().out.strip() == ""


    def test_a_letter_that_never_names_the_role_is_caught(tmp_path, capsys):
        ws = _ws(tmp_path, _letter(body=[PARA, PARA, PARA, PARA]))
        assert check_letter.main(["--workspace", str(ws)]) == 1
        out = capsys.readouterr().out
        assert "ROLE_NOT_NAMED" in out and "Senior Reconstruction Engineer" in out
        assert "WORD_COUNT" not in out and "PARA_COUNT" not in out   # one finding, not three


    def test_a_posting_without_a_company_field_fails_loudly(tmp_path, capsys):
        ws = _ws(tmp_path, _letter(), posting={"role_title": "Senior Reconstruction Engineer"})
        assert check_letter.main(["--workspace", str(ws)]) == 1
        assert "NO_COMPANY_IN_POSTING" in capsys.readouterr().out


    def test_a_missing_posting_is_exit_2(tmp_path, capsys):
        ws = _ws(tmp_path, _letter(), posting=None)
        assert check_letter.main(["--workspace", str(ws)]) == 2
        assert "posting.yaml" in capsys.readouterr().err


    def test_each_run_leaves_exactly_one_receipt_including_the_exit_2_path(tmp_path):
        ws = _ws(tmp_path, _letter())
        check_letter.main(["--workspace", str(ws)])
        (ws / "posting.yaml").unlink()
        assert check_letter.main(["--workspace", str(ws)]) == 2
        assert [r["verdict"] for r in journal.read_receipts(ws, "check_letter")] == \
            ["pass", "could_not_run"]
    ```

- [ ] **Step 2: Run test to verify it fails**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_check_letter.py -q`
    Expected: FAIL with `ModuleNotFoundError: No module named 'check_letter'`

- [ ] **Step 3: Write minimal implementation**
    Create `scripts/check_letter.py`:
    ```python
    #!/usr/bin/env python3
    """Gate: the letter constraints render_letter.py will not enforce.

    render_letter passes each body string straight into Markdown, docx and LaTeX
    with no stripping, so '**bold**' prints four asterisks on the PDF and a sender
    name written into `closing` prints twice — the renderer appends it already.
    These are exact string and count checks documented only in prose today, which is
    the same failure class as a format string rendered raw onto a slide.

    Misspelling the company or role is called disqualifying in the reference and is
    checked by reading. posting.yaml is a required artifact, so it can be checked by
    comparing.

    Exit 0 = clean. Exit 1 = findings. Exit 2 = missing letter.yaml or posting.yaml.
    """
    from __future__ import annotations

    import argparse
    import pathlib
    import re
    import sys
    import unicodedata

    import yaml

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import journal

    GATE = "check_letter"
    # motivation-letter.md:119 — "250–350 words optimal for the body … 400 words is
    # the hard ceiling". :121 — "3–4 paragraphs total … Never more than 4 unless a
    # specific structure requires it (rare)." A gate that permitted 5 would be
    # enforcing a rule the reference it cites does not contain.
    WORD_MIN, WORD_MAX = 250, 400
    PARA_MIN, PARA_MAX = 3, 4

    MARKUP = [
        ("**", re.compile(r"\*\*")),
        ("__", re.compile(r"__")),
        ("`", re.compile(r"`")),
        ("a leading bullet", re.compile(r"(^|\n)\s*[-*+]\s+")),
        ("a leading heading", re.compile(r"(^|\n)\s*#{1,6}\s+")),
    ]
    _PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


    def _norm(s) -> str:
        s = unicodedata.normalize("NFKC", str(s or "")).lower()
        return " ".join(_PUNCT.sub(" ", s).split())


    def findings_for(letter: dict, posting: dict) -> list:
        out = []
        body = letter.get("body") or []
        if isinstance(body, str):
            body = [body]

        for i, para in enumerate(body):
            hits = [label for label, rx in MARKUP if rx.search(str(para))]
            if hits:
                out.append(f"MARKDOWN_IN_BODY: body[{i}] contains "
                           f"{', '.join(repr(h) for h in hits)} — render_letter prints "
                           f"body strings verbatim, so this renders literally "
                           f"(**bold** prints four asterisks)")

        words = sum(len(str(p).split()) for p in body)
        if not (WORD_MIN <= words <= WORD_MAX):
            out.append(f"WORD_COUNT: the body is {words} words; the target is "
                       f"{WORD_MIN}–350 with {WORD_MAX} as the hard ceiling")
        if not (PARA_MIN <= len(body) <= PARA_MAX):
            out.append(f"PARA_COUNT: the body has {len(body)} paragraphs; "
                       f"{PARA_MIN}–{PARA_MAX} is the range (motivation-letter.md: "
                       f"never a single monolithic block, never more than 4)")

        sender = str((letter.get("sender") or {}).get("name") or "").strip()
        closing = str(letter.get("closing") or "")
        if sender and _norm(sender) and _norm(sender) in _norm(closing):
            out.append(f"NAME_DUPLICATED: closing contains the sender name {sender!r}; "
                       f"render_letter appends it automatically, so it prints twice")

        posted_company = str(posting.get("company") or "").strip()
        letter_company = str((letter.get("recipient") or {}).get("company") or "").strip()
        if not posted_company:
            out.append("NO_COMPANY_IN_POSTING: posting.yaml has no `company` field, so the "
                       "letter's recipient cannot be verified — add it to the extracted "
                       "posting (misspelling the employer is disqualifying)")
        elif not letter_company:
            out.append(f"COMPANY_MISMATCH: letter.yaml has no recipient.company; the "
                       f"posting names {posted_company!r}")
        else:
            a, b = _norm(letter_company), _norm(posted_company)
            if a not in b and b not in a:
                out.append(f"COMPANY_MISMATCH: recipient.company {letter_company!r} does "
                           f"not match the posting's company {posted_company!r}")

        role = str(posting.get("role_title") or "").strip()
        if role and _norm(role) not in _norm(" ".join(str(p) for p in body)):
            out.append(f"ROLE_NOT_NAMED: the body never names the role {role!r} as the "
                       f"posting writes it — name it exactly once, early")
        return out


    def main(argv=None) -> int:
        ap = argparse.ArgumentParser()
        ap.add_argument("--workspace", required=True)
        ap.add_argument("--letter", default=None, help="default: <workspace>/letter.yaml")
        ap.add_argument("--posting", default=None, help="default: <workspace>/posting.yaml")
        args = ap.parse_args(argv)
        ws = pathlib.Path(args.workspace)
        if not ws.is_dir():
            # journal.receipt() would mkdir it, and a gate that creates the
            # workspace it is auditing has manufactured its own evidence.
            print(f"cannot run {GATE}: workspace {ws} does not exist", file=sys.stderr)
            return 2
        lp = pathlib.Path(args.letter) if args.letter else ws / "letter.yaml"
        pp = pathlib.Path(args.posting) if args.posting else ws / "posting.yaml"
        for p in (lp, pp):
            if not p.exists():
                journal.receipt(ws, GATE, {}, "could_not_run", [f"MISSING_INPUT: {p}"])
                print(f"cannot run {GATE}: {p} does not exist", file=sys.stderr)
                return 2
        letter = yaml.safe_load(lp.read_text(encoding="utf-8")) or {}
        posting = yaml.safe_load(pp.read_text(encoding="utf-8")) or {}
        findings = findings_for(letter, posting)
        for f in findings:
            print(f)
        journal.receipt(ws, GATE,
                        {lp.name: journal.sha256_file(lp), pp.name: journal.sha256_file(pp)},
                        "fail" if findings else "pass", findings)
        return 1 if findings else 0


    if __name__ == "__main__":
        sys.exit(main())
    ```

- [ ] **Step 4: Run test to verify it passes**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_check_letter.py -q`
    Expected: PASS — `13 passed`

- [ ] **Step 5: Commit**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/check_letter.py scripts/tests/test_check_letter.py
    git commit -m "feat(gate): check_letter — markup, length, duplicated name, company and role

render_letter prints body strings verbatim, so **bold** renders as four asterisks
and a name in `closing` prints twice. A wrong company or an unnamed role is called
disqualifying in the reference and was checked by reading; posting.yaml is a
required artifact, so it can be checked by comparing — and a posting with no
`company` field fails loudly rather than skipping the check."
    ```

---

### Task 15: `render_cv.py` — warn on unknown `meta.headings` / `meta.section_order` keys

Measured: `meta.headings: {selected_matters: "Selected Matters"}` produces no warning and no relabel — the key is filtered out at `render_cv.py:120`. `role-families.md` hands out recipes that depend on those keys being exactly right, so a legal CV built from the recipe silently loses its "Selected Matters" heading on a typo, and the CV renders perfectly.

**Files:**
- Modify: `scripts/render_cv.py` (`headings()` around line 118–121, `section_order()` around line 324–327)
- Test: `scripts/tests/test_render_cv.py`

**Interfaces:**
- Consumes: `render_cv.HEADINGS`, `render_cv._ALL_SECTIONS` (existing).
- Produces: no new public function; `headings()` and `section_order()` keep their signatures and now write to stderr.

- [ ] **Step 1: Write the failing test**
    Append to `scripts/tests/test_render_cv.py`:
    ```python
    def test_unknown_headings_key_warns_and_names_the_valid_set(full_profile, capsys):
        """Measured silent failure: role-families.md's legal recipe relabels a
        section via meta.headings, and a key outside the built-in set is dropped
        with no warning — so the CV renders perfectly and loses its heading."""
        p = copy.deepcopy(full_profile)
        p["meta"]["headings"] = {"selected_matters": "Selected Matters",
                                 "experience": "Clinical Experience"}
        md = render_cv.render_markdown(p)
        err = capsys.readouterr().err
        assert "WARNING" in err
        assert "'selected_matters'" in err
        assert "certifications" in err and "publications" in err   # the valid set is listed
        assert "## Clinical Experience" in md                      # the valid key still works


    def test_unknown_section_order_entry_warns(full_profile, capsys):
        p = copy.deepcopy(full_profile)
        p["meta"]["section_order"] = ["summary", "selected_matters", "experience"]
        render_cv.render_markdown(p)
        err = capsys.readouterr().err
        assert "WARNING" in err and "'selected_matters'" in err


    def test_valid_headings_and_section_order_are_silent(full_profile, capsys):
        """The quiet case: headings() runs on every render of every CV. A warning
        here would appear on every clean run and be trained away."""
        p = copy.deepcopy(full_profile)
        p["meta"]["headings"] = {"experience": "Clinical Experience"}
        p["meta"]["section_order"] = ["education", "skills", "experience"]
        render_cv.render_markdown(p)
        assert capsys.readouterr().err == ""
    ```

- [ ] **Step 2: Run test to verify it fails**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_render_cv.py -q -k "headings_key or section_order_entry or are_silent"`
    Expected: FAIL — `assert 'WARNING' in ''`

- [ ] **Step 3: Write the implementation**
    In `render_cv.headings()`, replace the `if isinstance(override, dict):` block with:
    ```python
        if isinstance(override, dict):
            unknown = sorted(k for k in override if k not in base)
            if unknown:
                print(f"WARNING: meta.headings key(s) "
                      f"{', '.join(repr(k) for k in unknown)} are not section keys and "
                      f"were ignored — the section keeps its default label. Valid keys: "
                      f"{', '.join(sorted(base))}.", file=sys.stderr)
            base.update({k: v for k, v in override.items() if k in base and v})
    ```
    In `render_cv.section_order()`, immediately after the scalar-tolerance line (`explicit = [explicit]`), add:
    ```python
        unknown = [s for s in explicit if s not in _ALL_SECTIONS]
        if unknown:
            print(f"WARNING: meta.section_order entr(ies) "
                  f"{', '.join(repr(s) for s in unknown)} are not section keys and were "
                  f"ignored. Valid keys: {', '.join(_ALL_SECTIONS)}.", file=sys.stderr)
    ```

- [ ] **Step 4: Run test to verify it passes**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests -q`
    Expected: PASS — the whole suite, including the pre-existing heading/order tests which all use valid keys.

- [ ] **Step 5: Commit**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/render_cv.py scripts/tests/test_render_cv.py
    git commit -m "fix(render): warn on unknown meta.headings / meta.section_order keys

Verified silent today: {selected_matters: 'Selected Matters'} produced no output
and no relabel, so a legal CV built from the role-families recipe loses its
'Selected Matters' heading on a typo and still renders perfectly. Both call sites
now name the bad key and print the valid set. Valid keys stay silent."
    ```

---

### Task 16: `render_rirekisho.py` — an unparseable date must not render as a blank cell

Measured: `_ym('Sep 2023')`, `_ym('September 2023')` and `_ym('03/2021')` all return `('', '')`, so those rows render with blank 年 and 月 — a structurally invalid 履歴書 that renders, saves and passes pytest. The rirekisho is explicitly routed away from all three judges, so nothing else looks at it.

**Files:**
- Modify: `scripts/render_rirekisho.py` (`gakureki_shokureki_rows`, `licenses_rows`, `main`)
- Test: `scripts/tests/test_render_rirekisho.py`

**Two date fields, two parsers, and that is deliberate.** `_ym` is anchored (`re.match`), which is right for `education[].start` and `experience[].end`: those are structured fields, and `'Sep 2023'` there is a data error the form cannot show. It is *wrong* for `certifications[]`, which is free-form prose — the most ordinary real entry is `"基本情報技術者試験 合格 (2021)"`, and an anchored match returns `('', '')` for it, so the year is right there in the string and the 年 cell renders blank while a warning fires. Feeding the licenses table through `_checked_ym` would therefore cry wolf on almost every real Japanese CV, and three of this task's own tests assert it stays quiet. So certifications get `_cert_ym`, which searches for a plausible year (`19xx`/`20xx`, not preceded or followed by a digit — so `"ISO 27001"` and `"CCNA 200-301"` do not resolve to a year) anywhere in the string, and warns only when there is no year at all.

**Interfaces:**
- Consumes: `render_cv.load_profile`, `render_cv._is_current` (existing).
- Produces:
  - `gakureki_shokureki_rows(profile, problems=None)` and `licenses_rows(profile, problems=None)` — unchanged return value; when `problems` is a list, unreadable dates are appended to it as strings.
  - `_cert_ym(cert) -> tuple[str, str]` — a year/month searched anywhere in a free-form certification string.
  - `date_problems(profile) -> tuple[list[str], list[str]]` — `(fatal, warnings)`; fatal = 学歴・職歴 dates, warnings = 免許・資格 entries with no year at all.
  - `main` gains `--allow-blank-dates`.

- [ ] **Step 1: Write the failing test**
    Append to `scripts/tests/test_render_rirekisho.py`:
    ```python
    ACCEPTED = ["2023-09", "2021", "2023年9月", "2023/09"]
    REJECTED = ["Sep 2023", "September 2023", "03/2021", "", None]


    @pytest.mark.parametrize("value", ACCEPTED)
    def test_accepted_date_formats_produce_no_fatal_problem(jp_profile, value):
        """`warnings` is not asserted empty here: the jp_profile fixture's
        certification is genuinely undated (`"基本情報技術者試験 合格"`), and an
        undated certification is a warning by design."""
        p = dict(jp_profile)
        p["education"] = [{"institution": "○○大学", "degree": "修士",
                           "start": value, "end": "2023-03"}]
        fatal, _ = rr.date_problems(p)
        assert fatal == []


    @pytest.mark.parametrize("value", REJECTED)
    def test_unparseable_education_date_is_fatal_and_names_the_entry(jp_profile, value):
        p = dict(jp_profile)
        p["education"] = [{"institution": "○○大学", "degree": "修士",
                           "start": value, "end": "2023-03"}]
        fatal, _ = rr.date_problems(p)
        assert len(fatal) == 1
        assert "○○大学" in fatal[0]
        assert "start" in fatal[0]
        assert repr(value) in fatal[0] or "''" in fatal[0]


    def test_a_current_role_needs_no_end_date(jp_profile):
        """現在に至る legitimately has no year. Flagging it would fire on every
        employed candidate."""
        fatal, _ = rr.date_problems(jp_profile)
        assert fatal == []


    def test_an_undated_certification_warns_but_is_not_fatal(jp_profile):
        p = dict(jp_profile)
        p["certifications"] = ["基本情報技術者試験 合格"]
        fatal, warnings = rr.date_problems(p)
        assert fatal == []
        assert len(warnings) == 1 and "基本情報技術者試験" in warnings[0]


    @pytest.mark.parametrize("cert,year,month", [
        ("基本情報技術者試験 合格 (2021)", "2021", ""),
        ("AWS Certified Cloud Practitioner (2024)", "2024", ""),
        ("普通自動車第一種運転免許 (2015-04)", "2015", "4"),
        ("2023年9月 応用情報技術者", "2023", "9"),
    ])
    def test_a_certification_carrying_its_year_anywhere_is_read_and_silent(cert, year, month):
        """The most ordinary real entry puts the year in parentheses at the end.
        The anchored `_ym` returns ('', '') for it, which would blank the 年 cell
        AND fire a warning on a perfectly good line — a check that cries wolf on
        the common case is a check its reader stops seeing."""
        rows = rr.licenses_rows({"certifications": [cert]})
        assert (rows[0]["y"], rows[0]["m"]) == (year, month)
        fatal, warnings = rr.date_problems({"certifications": [cert]})
        assert fatal == [] and warnings == []


    @pytest.mark.parametrize("cert", ["ISO 27001 Lead Auditor", "CCNA 200-301",
                                      "TOEIC 990"])
    def test_a_digit_string_that_is_not_a_year_does_not_become_one(cert):
        """A false year printed into the 年 cell is worse than a blank one: it is
        a fabricated date on a legal-ish form, and it looks exactly like a real one."""
        rows = rr.licenses_rows({"certifications": [cert]})
        assert rows[0]["y"] == ""
        fatal, warnings = rr.date_problems({"certifications": [cert]})
        assert fatal == [] and len(warnings) == 1


    def test_main_refuses_to_write_a_form_with_blank_year_cells(jp_profile, tmp_path, capsys):
        import yaml
        p = dict(jp_profile)
        p["education"] = [{"institution": "○○大学", "degree": "修士",
                           "start": "Sep 2023", "end": "2025-03"}]
        src = tmp_path / "profile.yaml"
        src.write_text(yaml.safe_dump(p, allow_unicode=True), encoding="utf-8")
        out = tmp_path / "rirekisho.md"
        assert rr.main([str(src), "--format", "md", "--out", str(out)]) == 1
        err = capsys.readouterr().err
        assert "WARNING" in err and "Sep 2023" in err
        assert not out.exists()


    def test_allow_blank_dates_is_an_explicit_opt_in(jp_profile, tmp_path, capsys):
        import yaml
        p = dict(jp_profile)
        p["education"] = [{"institution": "○○大学", "degree": "修士",
                           "start": "Sep 2023", "end": "2025-03"}]
        src = tmp_path / "profile.yaml"
        src.write_text(yaml.safe_dump(p, allow_unicode=True), encoding="utf-8")
        out = tmp_path / "rirekisho.md"
        assert rr.main([str(src), "--format", "md", "--out", str(out),
                        "--allow-blank-dates"]) == 0
        assert out.exists()
        assert "WARNING" in capsys.readouterr().err     # still says so, just doesn't refuse


    def test_a_fully_dated_profile_writes_and_is_silent(jp_profile, tmp_path, capsys):
        """The quiet case, pinned as hard as the firing one — including the
        certification, which is given its year here so that a silent run is a real
        claim about the whole form rather than about the tables we happened to fix."""
        import yaml
        p = dict(jp_profile)
        p["certifications"] = ["基本情報技術者試験 合格 (2021)"]
        src = tmp_path / "profile.yaml"
        src.write_text(yaml.safe_dump(p, allow_unicode=True), encoding="utf-8")
        out = tmp_path / "rirekisho.md"
        assert rr.main([str(src), "--format", "md", "--out", str(out)]) == 0
        assert "WARNING" not in capsys.readouterr().err
    ```

- [ ] **Step 2: Run test to verify it fails**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_render_rirekisho.py -q`
    Expected: FAIL with `AttributeError: module 'render_rirekisho' has no attribute 'date_problems'`

- [ ] **Step 3: Write the implementation**
    In `scripts/render_rirekisho.py`, add after `_sortable`:
    ```python
    def _checked_ym(value, what, problems):
        """(year, month) plus a recorded problem when there is no parseable year.

        _ym returns ('', '') for anything it cannot read — 'Sep 2023',
        'September 2023' and '03/2021' all do — and the row then renders with blank
        年 and 月 cells. That is a structurally invalid 履歴書 that renders, saves and
        passes pytest, and the rirekisho is deliberately routed away from all three
        judges, so no other reader exists.
        """
        y, mo = _ym(value)
        if not y and problems is not None:
            problems.append(f"{what}: could not read a year from {value!r} — accepted "
                            f"forms are '2023-09', '2023/09', '2021', '2023年9月'")
        return y, mo
    ```
    In `gakureki_shokureki_rows(profile)`, change the signature to `gakureki_shokureki_rows(profile, problems=None)` and replace each date read with the checked form:
    ```python
        # education
        y, mo = _checked_ym(ed.get("start"), f"学歴 {name} 入学 (start)", problems)
        ...
        ey, emo = _checked_ym(ed.get("end"), f"学歴 {name} 卒業 (end)", problems) \
            if not render_cv._is_current(ed) else _ym(ed.get("end"))
        # experience
        y, mo = _checked_ym(ex.get("start"), f"職歴 {org} 入社 (start)", problems)
        ...
        ey, emo = _checked_ym(ex.get("end"), f"職歴 {org} 退社 (end)", problems)
    ```
    (the `end` read for a current entry stays unchecked — 現在に至る legitimately has no year, and flagging it would fire on every employed candidate). Next, add the free-form certification parser next to `_ym`:
    ```python
    # certifications[] is free-form prose, not a structured date field. The most
    # ordinary real entry is "基本情報技術者試験 合格 (2021)", and the anchored _ym
    # returns ('', '') for it — blanking the 年 cell while the year sits in plain
    # sight, and firing a warning on a perfectly good line. So search instead of
    # anchoring, and require a plausible year shape (19xx/20xx, not adjacent to
    # another digit) so that "ISO 27001" and "CCNA 200-301" do not silently print
    # a fabricated date into the form.
    _CERT_YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)(?:\s*[-/.年]\s*(\d{1,2})(?!\d))?")


    def _cert_ym(value):
        m = _CERT_YEAR.search(str(value or ""))
        if not m:
            return "", ""
        return m.group(1), (str(int(m.group(2))) if m.group(2) else "")
    ```
    Change `licenses_rows(profile)` to `licenses_rows(profile, problems=None)`, replace its `_ym(cert)` with `_cert_ym(cert)`, and record a problem only when no year was found at all:
    ```python
    def licenses_rows(profile, problems=None):
        rows = []
        for cert in (profile.get("certifications") or []):
            y, mo = _cert_ym(cert)
            if not y and problems is not None:
                problems.append(f"免許・資格 {cert}: no year found — the 年 cell will be "
                                f"blank; add one, e.g. '基本情報技術者試験 合格 (2021)'")
            rows.append({"y": y, "m": mo, "text": cert})
        if not rows:
            rows.append({"y": "", "m": "", "text": "特になし"})
        return rows
    ```
    Then add:
    ```python
    def date_problems(profile):
        """(fatal, warnings). 学歴・職歴 rows must carry a year — the table IS the
        form, and a blank 年 cell makes it structurally invalid. A certification
        with no year at all is a common and tolerable omission, so it warns; a
        certification that carries its year in prose is read and stays silent."""
        fatal, warnings = [], []
        gakureki_shokureki_rows(profile, fatal)
        licenses_rows(profile, warnings)
        return fatal, warnings
    ```
    Finally, in `main()`, add `ap.add_argument("--allow-blank-dates", action="store_true", help="write the form anyway; the 年/月 cells will be blank")`, and after loading the profile:
    ```python
        fatal, warnings = date_problems(profile)
        for problem in fatal + warnings:
            print(f"WARNING: {problem}", file=sys.stderr)
        if fatal and not args.allow_blank_dates:
            print("Refusing to write a 履歴書 with blank 年/月 cells in 学歴・職歴 — the "
                  "table is the form. Fix the dates, or pass --allow-blank-dates.",
                  file=sys.stderr)
            return 1
    ```
    and make `main` return `0` on the success path (it currently falls off the end, which is `None`; `sys.exit(None)` is 0, but the tests compare to `0`).

- [ ] **Step 4: Run test to verify it passes**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests -q`
    Expected: PASS — the whole suite. The existing rirekisho fixtures use `2020-04` / `2023-04` / `present` for 学歴・職歴, so nothing there is fatal; the fixture's undated certification warns, which is why the three `date_problems` tests assert `fatal == []` and not `warnings == []`.

- [ ] **Step 5: Commit**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/render_rirekisho.py scripts/tests/test_render_rirekisho.py
    git commit -m "fix(rirekisho): fail loudly on a date the form cannot show

_ym('Sep 2023') returns ('', ''), so the row rendered with blank 年/月 cells — a
structurally invalid form that renders, saves and passes pytest, reviewed by
nobody because the rirekisho is routed away from all three judges. 学歴・職歴 dates
are now fatal unless --allow-blank-dates; certifications warn. A current role
still needs no end date."
    ```

---

### Task 17: `scripts/check_pages.py` — the artifact that is actually submitted is the one nobody measures

`references/cv-craft.md:224-228` states a hard length table (0-2 years: 1 page; 3-7: 1-2; 8-15: 2; 15+: 2, three only when the senior roles are genuinely distinct; academic: no limit) and `references/motivation-letter.md:122` says the letter is "One page, always". No program has ever checked either. The three judges read `cv.md`, not `cv.pdf`; `render_cv.render_pdf` reports success on any compile that returns 0. So a three-page CV for a five-year candidate renders perfectly, passes every gate this plan has built so far, and is a common silent screen-out — and a truncated PDF that no reader can open passes identically.

**Files:**
- Create: `scripts/check_pages.py`
- Test: `scripts/tests/test_check_pages.py`

**Interfaces:**
- Consumes: `journal.receipt`, `journal.sha256_file`.
- Produces: `page_count(path) -> int | None`; `years_of_experience(profile, today_year) -> int`; `max_pages(profile, today_year) -> int | None`; `findings_for(cv_pdf, profile, today_year, letter_pdf=None) -> list[str]`; `main(argv=None) -> int`. CLI: `python3 scripts/check_pages.py --workspace W [--cv PATH] [--letter PATH] [--profile PATH] [--today YYYY-MM-DD]`. Gate name: `check_pages`. Finding codes: `CV_TOO_LONG`, `LETTER_TOO_LONG`, `UNREADABLE_PDF`.

**Measured, and it decides the implementation:** tectonic on this machine writes PDF 1.5 with compressed object streams. A real `cv.pdf` (19,820 bytes, rendered from `tests/fixtures/full_profile.yaml`) contains **zero** literal `/Type /Page` bytes; inflating its FlateDecode streams yields 29,003 bytes containing exactly one. A page counter that only scanned the raw file would report 0 pages for every CV this skill produces.

- [ ] **Step 1: Write the failing test**
    Create `scripts/tests/test_check_pages.py`:
    ```python
    import pathlib
    import sys
    import zlib

    import yaml

    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    import check_pages
    import journal

    JUNIOR = {"meta": {"name": "Z"}, "experience": [{"org": "A", "start": "2025-01"}]}
    MID = {"meta": {"name": "Z"}, "experience": [{"org": "A", "start": "2018-03"}]}


    def _pdf(path, pages, compress=False):
        """A minimal PDF with `pages` page objects. Uncompressed by default; the
        compressed variant exercises the object-stream path tectonic actually emits."""
        body = b"".join(b"%d 0 obj\n<< /Type /Page /Parent 1 0 R >>\nendobj\n" % (i + 2)
                        for i in range(pages))
        if compress:
            blob = zlib.compress(body)
            body = (b"1 0 obj\n<< /Type /ObjStm /Filter /FlateDecode /Length %d >>\nstream\n"
                    % len(blob)) + blob + b"\nendstream\nendobj\n"
        path.write_bytes(b"%PDF-1.5\n" + body + b"trailer\n<< >>\n%%EOF\n")
        return path


    def _ws(tmp_path, profile=MID, cv_pages=2, letter_pages=None, compress=False):
        ws = tmp_path / "acme-engineer-2026-08-09"
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "tailored-profile.yaml").write_text(
            yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
        _pdf(ws / "cv.pdf", cv_pages, compress)
        if letter_pages is not None:
            _pdf(ws / "letter.pdf", letter_pages, compress)
        return ws


    def test_page_count_reads_a_compressed_object_stream(tmp_path):
        """tectonic writes PDF 1.5 with compressed object streams — measured on this
        machine, a real one-page cv.pdf contains zero literal '/Type /Page' bytes. A
        counter that only scanned the raw file would report 0 pages for every CV."""
        assert check_pages.page_count(_pdf(tmp_path / "a.pdf", 3, compress=True)) == 3
        assert check_pages.page_count(_pdf(tmp_path / "b.pdf", 1)) == 1


    def test_a_two_page_cv_for_a_mid_career_candidate_is_silent(tmp_path, capsys):
        """The quiet case. Two pages at eight years is exactly what cv-craft.md's
        table prescribes; firing here would teach the reader to skip this gate."""
        ws = _ws(tmp_path, MID, cv_pages=2)
        assert check_pages.main(["--workspace", str(ws), "--today", "2026-08-09"]) == 0
        assert capsys.readouterr().out.strip() == ""


    def test_a_two_page_cv_for_a_junior_candidate_is_caught(tmp_path, capsys):
        ws = _ws(tmp_path, JUNIOR, cv_pages=2)
        assert check_pages.main(["--workspace", str(ws), "--today", "2026-08-09"]) == 1
        out = capsys.readouterr().out
        assert "CV_TOO_LONG" in out and "2 pages" in out and "allows 1" in out


    def test_a_three_page_cv_is_caught_unless_max_pages_says_otherwise(tmp_path, capsys):
        ws = _ws(tmp_path, MID, cv_pages=3)
        assert check_pages.main(["--workspace", str(ws), "--today", "2026-08-09"]) == 1
        assert "CV_TOO_LONG" in capsys.readouterr().out
        allowed = {**MID, "meta": {"name": "Z", "max_pages": 3}}
        ws2 = _ws(tmp_path / "override", allowed, cv_pages=3)
        assert check_pages.main(["--workspace", str(ws2), "--today", "2026-08-09"]) == 0
        assert capsys.readouterr().out.strip() == ""


    def test_an_academic_cv_has_no_page_limit(tmp_path, capsys):
        """cv-craft.md:228 — 'Academic / research CV: No page limit; list all
        publications, grants, talks.'"""
        academic = {**MID, "meta": {"name": "Z", "cv_type": "academic"}}
        ws = _ws(tmp_path, academic, cv_pages=7)
        assert check_pages.main(["--workspace", str(ws), "--today", "2026-08-09"]) == 0
        assert capsys.readouterr().out.strip() == ""


    def test_a_two_page_letter_is_caught_and_a_one_page_letter_is_not(tmp_path, capsys):
        ws = _ws(tmp_path, MID, cv_pages=2, letter_pages=1)
        assert check_pages.main(["--workspace", str(ws), "--today", "2026-08-09"]) == 0
        capsys.readouterr()
        ws2 = _ws(tmp_path / "long", MID, cv_pages=2, letter_pages=2)
        assert check_pages.main(["--workspace", str(ws2), "--today", "2026-08-09"]) == 1
        assert "LETTER_TOO_LONG" in capsys.readouterr().out


    def test_a_pdf_with_no_readable_page_tree_is_reported_not_ignored(tmp_path, capsys):
        ws = _ws(tmp_path, MID, cv_pages=2)
        (ws / "cv.pdf").write_bytes(b"%PDF-1.5\ntruncated\n")
        assert check_pages.main(["--workspace", str(ws), "--today", "2026-08-09"]) == 1
        assert "UNREADABLE_PDF" in capsys.readouterr().out


    def test_no_pdf_is_exit_2_not_a_pass(tmp_path, capsys):
        """A markdown-only run has no PDF to measure. That is 'could not run', not
        'within budget' — check_apply only requires this receipt when cv.pdf exists."""
        ws = _ws(tmp_path, MID, cv_pages=2)
        (ws / "cv.pdf").unlink()
        assert check_pages.main(["--workspace", str(ws)]) == 2
        assert "cv.pdf" in capsys.readouterr().err


    def test_each_run_leaves_exactly_one_receipt_including_the_exit_2_path(tmp_path):
        ws = _ws(tmp_path, MID, cv_pages=2)
        check_pages.main(["--workspace", str(ws), "--today", "2026-08-09"])
        (ws / "cv.pdf").unlink()
        check_pages.main(["--workspace", str(ws), "--today", "2026-08-09"])
        assert [r["verdict"] for r in journal.read_receipts(ws, "check_pages")] == \
            ["pass", "could_not_run"]
    ```

- [ ] **Step 2: Run test to verify it fails**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_check_pages.py -q`
    Expected: FAIL with `ModuleNotFoundError: No module named 'check_pages'`

- [ ] **Step 3: Write minimal implementation**
    Create `scripts/check_pages.py`:
    ```python
    #!/usr/bin/env python3
    """Gate: the rendered PDF is as long as the market says it may be.

    Nothing else in the pipeline measures the artifact that is actually submitted.
    The three judges read `cv.md`; `render_cv.py` reports success on any compile that
    returns 0; and `references/cv-craft.md:224-228` states a hard length table that no
    program has ever checked. A three-page CV for a five-year candidate renders
    perfectly, passes every existing gate, and is a common silent screen-out.

    Exit 0 = within budget. Exit 1 = findings. Exit 2 = no PDF to measure.
    """
    from __future__ import annotations

    import argparse
    import datetime
    import pathlib
    import re
    import sys
    import zlib

    import yaml

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import journal

    GATE = "check_pages"
    _PAGE = re.compile(rb"/Type\s*/Page(?![sA-Za-z])")
    _PAGES_COUNT = re.compile(rb"/Type\s*/Pages\b[^>]{0,200}?/Count\s+(\d+)", re.S)
    _YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
    ACADEMIC = ("academic", "research")


    def _haystack(data: bytes) -> bytes:
        """Raw bytes plus every inflated FlateDecode stream.

        Measured: tectonic writes PDF 1.5 with compressed object streams, so the page
        objects are not in the raw bytes at all — a plain `/Type /Page` scan reports
        0 pages for a perfectly good one-page CV, which would make this gate fire on
        every single run.
        """
        parts = [data]
        for m in re.finditer(rb"stream\r?\n", data):
            start = m.end()
            end = data.find(b"endstream", start)
            if end < 0:
                continue
            try:
                parts.append(zlib.decompress(data[start:end]))
            except zlib.error:
                pass
        return b"\n".join(parts)


    def page_count(path):
        """Number of pages, or None when the file cannot be read as a PDF."""
        hay = _haystack(pathlib.Path(path).read_bytes())
        n = len(_PAGE.findall(hay))
        if n:
            return n
        counts = [int(c) for c in _PAGES_COUNT.findall(hay)]
        return max(counts) if counts else None


    def years_of_experience(profile, today_year: int) -> int:
        years = []
        for ex in profile.get("experience") or []:
            if not isinstance(ex, dict):
                continue
            m = _YEAR.search(str(ex.get("start") or ""))
            if m:
                years.append(int(m.group(1)))
        return max(0, today_year - min(years)) if years else 0


    def max_pages(profile, today_year: int):
        """The page budget, or None when there is none.

        cv-craft.md:224-228 — 0-2 years: 1 page; 3-7: 1-2; 8-15: 2; 15+: 2, "3 only if
        roles are very distinct and all relevant"; academic/research CVs: no limit.
        The 15+/3-page case is an explicit judgement call, so it is an explicit opt-in
        (`meta.max_pages: 3`) rather than a band the gate guesses at.
        """
        meta = profile.get("meta") or {}
        if str(meta.get("cv_type") or "").strip().lower() in ACADEMIC:
            return None
        override = meta.get("max_pages")
        if isinstance(override, int) and not isinstance(override, bool) and override > 0:
            return override
        return 1 if years_of_experience(profile, today_year) < 3 else 2


    def findings_for(cv_pdf, profile, today_year: int, letter_pdf=None) -> list:
        out = []
        pages = page_count(cv_pdf)
        if pages is None:
            out.append(f"UNREADABLE_PDF: {pathlib.Path(cv_pdf).name} has no readable page "
                       f"tree — the compile reported success but produced a file no "
                       f"reader can open; re-render before sending it")
        else:
            budget = max_pages(profile, today_year)
            if budget is not None and pages > budget:
                out.append(f"CV_TOO_LONG: {pathlib.Path(cv_pdf).name} is {pages} pages; "
                           f"the length table in references/cv-craft.md allows {budget} "
                           f"for {years_of_experience(profile, today_year)} years of "
                           f"experience. Cut, or set meta.max_pages with a reason")
        if letter_pdf and pathlib.Path(letter_pdf).exists():
            lp = page_count(letter_pdf)
            if lp is None:
                out.append(f"UNREADABLE_PDF: {pathlib.Path(letter_pdf).name} has no "
                           f"readable page tree")
            elif lp > 1:
                out.append(f"LETTER_TOO_LONG: {pathlib.Path(letter_pdf).name} is {lp} "
                           f"pages; motivation-letter.md says one page, always")
        return out


    def main(argv=None) -> int:
        ap = argparse.ArgumentParser()
        ap.add_argument("--workspace", required=True)
        ap.add_argument("--cv", default=None, help="default: <workspace>/cv.pdf")
        ap.add_argument("--letter", default=None, help="default: <workspace>/letter.pdf")
        ap.add_argument("--profile", default=None,
                        help="default: <workspace>/tailored-profile.yaml")
        ap.add_argument("--today", default=None, help="YYYY-MM-DD; default: today")
        args = ap.parse_args(argv)

        ws = pathlib.Path(args.workspace)
        if not ws.is_dir():
            # journal.receipt() would mkdir it, and a gate that creates the
            # workspace it is auditing has manufactured its own evidence.
            print(f"cannot run {GATE}: workspace {ws} does not exist", file=sys.stderr)
            return 2
        cv = pathlib.Path(args.cv) if args.cv else ws / "cv.pdf"
        letter = pathlib.Path(args.letter) if args.letter else ws / "letter.pdf"
        prof = pathlib.Path(args.profile) if args.profile else ws / "tailored-profile.yaml"
        for p in (cv, prof):
            if not p.exists():
                journal.receipt(ws, GATE, {}, "could_not_run", [f"MISSING_INPUT: {p}"])
                print(f"cannot run {GATE}: {p} does not exist", file=sys.stderr)
                return 2

        today_year = int((args.today or
                          datetime.date.today().isoformat())[:4])
        profile = yaml.safe_load(prof.read_text(encoding="utf-8")) or {}
        findings = findings_for(cv, profile, today_year, letter)
        for f in findings:
            print(f)
        journal.receipt(ws, GATE, {cv.name: journal.sha256_file(cv)},
                        "fail" if findings else "pass", findings)
        return 1 if findings else 0


    if __name__ == "__main__":
        sys.exit(main())
    ```

- [ ] **Step 4: Run test to verify it passes**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_check_pages.py -q`
    Expected: PASS — `9 passed`

- [ ] **Step 5: Run it against a real tectonic PDF, since a synthetic one is exactly what could hide the bug**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    mkdir -p /tmp/jh-pages && python3 scripts/render_cv.py \
        scripts/tests/fixtures/full_profile.yaml --format pdf --out /tmp/jh-pages/cv.pdf
    cp scripts/tests/fixtures/full_profile.yaml /tmp/jh-pages/tailored-profile.yaml
    python3 scripts/check_pages.py --workspace /tmp/jh-pages --today 2026-08-09; echo "exit=$?"
    python3 -c "import sys; sys.path.insert(0,'scripts'); import check_pages; print(check_pages.page_count('/tmp/jh-pages/cv.pdf'))"
    ```
    Expected: `page_count` prints `1`, not `None` and not `0`. If it prints `None`, the inflate path is not reaching the object stream and every CV would be reported unreadable.

- [ ] **Step 6: Commit**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/check_pages.py scripts/tests/test_check_pages.py
    git commit -m "feat(gate): check_pages — measure the PDF, not the markdown

cv-craft.md states a page table and motivation-letter.md says one page always;
nothing checked either, because the three judges read cv.md and render_pdf calls
any exit-0 compile a success. Counts pages through tectonic's compressed object
streams (a real cv.pdf contains zero literal /Type /Page bytes), exempts academic
CVs, and treats the 15+/three-page case as an explicit meta.max_pages opt-in
rather than a band to guess at."
    ```

---

### Task 18: `scripts/check_word_limits.py` — the only scored artifact had no reader

`references/structured-applications.md:52` routes a structured application **away** from all three CV judges — "review the supporting statement against the framework instead" — and `:25` says "respect the limit exactly: over-limit statements are cut or penalised". Put together, the one document that actually gets marked is the one document nothing in this skill reads. This gate reads it.

**The limit lives in the criterion heading**, in the employer's own number — `### Making Effective Decisions (250 words)` — because that is where a human writing the statement is already looking, and because a limit recorded anywhere else is a limit that drifts from the heading it applies to. When the posting states none, the file must say so once (`<!-- word-limits: none stated in the posting -->`): "the posting gave no limit" and "nobody recorded the limit" are the same silence otherwise, and only one of them is safe.

**Files:**
- Create: `scripts/check_word_limits.py`
- Test: `scripts/tests/test_check_word_limits.py`

**Interfaces:**
- Consumes: `journal.receipt`, `journal.sha256_file`; `posting.yaml`'s `application_type`.
- Produces: `sections(text) -> list[tuple[str, int | None, int]]`; `findings_for(text, posting) -> list[str]`; `main(argv=None) -> int`. CLI: `python3 scripts/check_word_limits.py --workspace W [--statement PATH] [--posting PATH]` (defaults `<W>/supporting-statement.md`, `<W>/posting.yaml`). Gate name: `check_word_limits`. Finding codes: `OVER_LIMIT`, `EMPTY_CRITERION`, `NO_LIMIT_DECLARED`, `NO_CRITERIA`.

- [ ] **Step 1: Write the failing test**
    Create `scripts/tests/test_check_word_limits.py`:
    ```python
    import pathlib
    import sys

    import yaml

    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    import check_word_limits as cwl
    import journal

    POSTING = {"company": "NHS Trust", "role_title": "Clinical Scientist",
               "application_type": "structured"}
    STAR = ("At the trust I owned the migration of the reporting pipeline. The task was "
            "to cut a four-hour nightly batch without losing any audit trail. I profiled "
            "the job, rewrote the two slowest stages, and agreed a rollback plan with the "
            "data protection officer before touching production. The batch now finishes "
            "in forty minutes and no audit record has been lost since. ")

    GOOD = ("# Supporting statement — Clinical Scientist, NHS Trust\n\n"
            "## Essential criteria\n\n"
            "### Making Effective Decisions (250 words)\n" + STAR + "\n\n"
            "### Communicating and Influencing (max 250 words)\n" + STAR + "\n")


    def _ws(tmp_path, text=GOOD, posting=POSTING):
        ws = tmp_path / "nhs-clinical-scientist-2026-08-09"
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "supporting-statement.md").write_text(text, encoding="utf-8")
        if posting is not None:
            (ws / "posting.yaml").write_text(yaml.safe_dump(posting, allow_unicode=True),
                                             encoding="utf-8")
        return ws


    def test_a_statement_inside_its_limits_passes_silently(tmp_path, capsys):
        ws = _ws(tmp_path)
        assert cwl.main(["--workspace", str(ws)]) == 0
        assert capsys.readouterr().out.strip() == ""


    def test_both_limit_spellings_are_read(tmp_path):
        rows = cwl.sections(GOOD)
        assert [r[1] for r in rows] == [250, 250]
        assert all(0 < r[2] < 250 for r in rows)


    def test_an_over_limit_criterion_is_caught_with_both_numbers(tmp_path, capsys):
        ws = _ws(tmp_path, GOOD.replace("(250 words)", "(40 words)"))
        assert cwl.main(["--workspace", str(ws)]) == 1
        out = capsys.readouterr().out
        assert "OVER_LIMIT" in out and "Making Effective Decisions" in out and "40" in out
        assert out.count("OVER_LIMIT") == 1        # the 250-word criterion stays quiet


    def test_an_unaddressed_criterion_is_caught(tmp_path, capsys):
        text = GOOD + "\n### Delivering at Pace (250 words)\n\n"
        ws = _ws(tmp_path, text)
        assert cwl.main(["--workspace", str(ws)]) == 1
        assert "EMPTY_CRITERION" in capsys.readouterr().out


    def test_a_structured_posting_with_no_limits_anywhere_must_say_so(tmp_path, capsys):
        bare = GOOD.replace(" (250 words)", "").replace(" (max 250 words)", "")
        ws = _ws(tmp_path, bare)
        assert cwl.main(["--workspace", str(ws)]) == 1
        assert "NO_LIMIT_DECLARED" in capsys.readouterr().out
        ws2 = _ws(tmp_path / "declared",
                  "<!-- word-limits: none stated in the posting -->\n" + bare)
        assert cwl.main(["--workspace", str(ws2)]) == 0
        assert capsys.readouterr().out.strip() == ""


    def test_an_unstructured_posting_is_not_policed(tmp_path, capsys):
        """A free-CV application has no scored criteria. Firing here would make this
        gate noise on the common case."""
        bare = GOOD.replace(" (250 words)", "").replace(" (max 250 words)", "")
        ws = _ws(tmp_path, bare, posting={"company": "Acme", "application_type": "cv"})
        assert cwl.main(["--workspace", str(ws)]) == 0
        assert capsys.readouterr().out.strip() == ""


    def test_a_structured_posting_with_no_criteria_headings_is_caught(tmp_path, capsys):
        ws = _ws(tmp_path, "# Supporting statement\n\n" + STAR)
        assert cwl.main(["--workspace", str(ws)]) == 1
        assert "NO_CRITERIA" in capsys.readouterr().out


    def test_cjk_is_counted_by_character_not_as_one_giant_word(tmp_path):
        """A criterion answered in Chinese is a real case (the skill is bilingual).
        Splitting on whitespace would score a 600-character answer as three words."""
        rows = cwl.sections("### 沟通与影响 (200 words)\n" + "我负责该项目的交付与验收。" * 20 + "\n")
        assert rows[0][1] == 200 and rows[0][2] > 200


    def test_a_missing_statement_is_exit_2_and_leaves_a_receipt(tmp_path, capsys):
        ws = _ws(tmp_path)
        (ws / "supporting-statement.md").unlink()
        assert cwl.main(["--workspace", str(ws)]) == 2
        assert "supporting-statement.md" in capsys.readouterr().err
        assert [r["verdict"] for r in journal.read_receipts(ws, "check_word_limits")] == \
            ["could_not_run"]


    def test_each_run_leaves_exactly_one_receipt(tmp_path):
        ws = _ws(tmp_path)
        cwl.main(["--workspace", str(ws)])
        assert [r["verdict"] for r in journal.read_receipts(ws, "check_word_limits")] == \
            ["pass"]
    ```

- [ ] **Step 2: Run test to verify it fails**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_check_word_limits.py -q`
    Expected: FAIL with `ModuleNotFoundError: No module named 'check_word_limits'`

- [ ] **Step 3: Write minimal implementation**
    Create `scripts/check_word_limits.py`:
    ```python
    #!/usr/bin/env python3
    """Gate: a scored supporting statement stays inside its stated word limits.

    `references/structured-applications.md:25` — "respect the limit exactly:
    over-limit statements are cut or penalised", and ":52" makes the statement, not
    the CV, the thing that gets scored. Nothing checked it: the three CV judges are
    routed away from a structured application by design, so the one artifact that is
    actually marked had no reader at all.

    The limit is written into the criterion heading, in the employer's own number:

        ### Making Effective Decisions (250 words)
        ### Communicating and Influencing (max 250 words)

    When the posting states no limit, say so once, at the top of the file:

        <!-- word-limits: none stated in the posting -->

    That marker is required rather than optional because "the posting gave no limit"
    and "nobody recorded the limit" are the same silence otherwise, and only one of
    them is safe.

    Exit 0 = clean. Exit 1 = findings. Exit 2 = no supporting statement to check.
    """
    from __future__ import annotations

    import argparse
    import pathlib
    import re
    import sys

    import yaml

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import journal

    GATE = "check_word_limits"
    NO_LIMIT_MARKER = re.compile(r"<!--\s*word-limits:\s*none stated", re.I)
    _HEADING = re.compile(r"^###\s+(?P<title>.+?)\s*$", re.M)
    _LIMIT = re.compile(r"\(?\s*(?:max\.?\s*|word limit:?\s*|up to\s*)?"
                        r"(?P<n>\d{2,4})\s*(?:words?|字)\s*\)?", re.I)
    _WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


    def _words(text: str) -> int:
        """Latin words plus CJK characters — a criterion answered in Chinese or
        Japanese must be counted, not measured as one enormous word."""
        n = 0
        for token in _WORD.findall(text):
            cjk = sum(1 for ch in token if "぀" <= ch <= "鿿")
            n += cjk if cjk else 1
        return n


    def sections(text: str) -> list:
        """[(title, declared_limit|None, body_word_count)] for each `###` heading."""
        out, marks = [], list(_HEADING.finditer(text))
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            title = m.group("title")
            lim = _LIMIT.search(title)
            out.append((title, int(lim.group("n")) if lim else None,
                        _words(text[m.end():end])))
        return out


    def findings_for(text: str, posting: dict) -> list:
        out = []
        structured = str(posting.get("application_type") or "").strip().lower() == "structured"
        rows = sections(text)
        if not rows:
            if structured:
                out.append("NO_CRITERIA: application_type is 'structured' but the "
                           "supporting statement has no `### <criterion>` headings — the "
                           "form is scored criterion by criterion, so an unlabelled essay "
                           "cannot be marked against it")
            return out
        for title, limit, words in rows:
            if words == 0:
                out.append(f"EMPTY_CRITERION: {title!r} has no body — an unaddressed "
                           f"Essential criterion is usually an auto-reject")
            elif limit is not None and words > limit:
                out.append(f"OVER_LIMIT: {title!r} is {words} words against its stated "
                           f"limit of {limit} — over-limit statements are cut or "
                           f"penalised, so the tail you wrote may simply not be read")
        if structured and not any(l is not None for _, l, _ in rows) \
                and not NO_LIMIT_MARKER.search(text):
            out.append("NO_LIMIT_DECLARED: no criterion heading carries a word limit and "
                       "the file does not say the posting stated none. Add the employer's "
                       "number to each heading, e.g. '### Making Effective Decisions "
                       "(250 words)', or record '<!-- word-limits: none stated in the "
                       "posting -->' — otherwise 'no limit given' and 'nobody checked' "
                       "look identical")
        return out


    def main(argv=None) -> int:
        ap = argparse.ArgumentParser()
        ap.add_argument("--workspace", required=True)
        ap.add_argument("--statement", default=None,
                        help="default: <workspace>/supporting-statement.md")
        ap.add_argument("--posting", default=None, help="default: <workspace>/posting.yaml")
        args = ap.parse_args(argv)
        ws = pathlib.Path(args.workspace)
        if not ws.is_dir():
            # journal.receipt() would mkdir it, and a gate that creates the
            # workspace it is auditing has manufactured its own evidence.
            print(f"cannot run {GATE}: workspace {ws} does not exist", file=sys.stderr)
            return 2
        sp = pathlib.Path(args.statement) if args.statement else ws / "supporting-statement.md"
        pp = pathlib.Path(args.posting) if args.posting else ws / "posting.yaml"
        for p in (sp, pp):
            if not p.exists():
                journal.receipt(ws, GATE, {}, "could_not_run", [f"MISSING_INPUT: {p}"])
                print(f"cannot run {GATE}: {p} does not exist", file=sys.stderr)
                return 2
        posting = yaml.safe_load(pp.read_text(encoding="utf-8")) or {}
        findings = findings_for(sp.read_text(encoding="utf-8"), posting)
        for f in findings:
            print(f)
        journal.receipt(ws, GATE, {sp.name: journal.sha256_file(sp)},
                        "fail" if findings else "pass", findings)
        return 1 if findings else 0


    if __name__ == "__main__":
        sys.exit(main())
    ```

- [ ] **Step 4: Run test to verify it passes**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_check_word_limits.py -q`
    Expected: PASS — `10 passed`

- [ ] **Step 5: Commit**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/check_word_limits.py scripts/tests/test_check_word_limits.py
    git commit -m "feat(gate): check_word_limits — read the document that is scored

structured-applications.md routes a criterion-scored form away from all three CV
judges, which left the only marked artifact with no reader at all. Counts each
criterion against the limit written in its own heading, counts CJK by character,
and requires the run to record when the posting stated no limit — otherwise 'no
limit given' and 'nobody checked' are the same silence."
    ```

---

### Task 19: `scripts/enter_mode.py` and `scripts/check_apply.py` — the composing gate

`check_apply.py` is where the mode's completion claim becomes checkable. It requires every upstream gate's receipt (a skipped script produces no output, which looks exactly like a clean one), the round's combined verdict *or* an honest-stop record classified as **poorly built** vs **honest stretch** (both emit the identical machine signal, and a stretch candidate told "failed" abandons an application they should have sent), the interview brief, and the mode-entry record that makes `modes/apply.md` a layer-1.5 file rather than an optional one.

**Files:**
- Create: `scripts/enter_mode.py`, `scripts/check_apply.py`
- Test: `scripts/tests/test_check_apply.py`

**Interfaces:**
- Consumes: `journal.append`, `journal.receipt`, `journal.read_receipts`, `journal.sha256_file`; `paths.SKILL_ROOT`, `paths.mode_file`; `vocab.VERDICTS`; `rounds.load_round`, `rounds.round_path`. The test module additionally imports all eight upstream gates by name (Tasks 9–18) to hold them to the Global Constraints workspace guard, so this task must run after them.
- Produces:
  - `enter_mode.latest_mode_entry(workspace, mode) -> dict | None`
  - `enter_mode.main(argv=None) -> int`. CLI: `python3 scripts/enter_mode.py --workspace W --mode apply [--skill-root PATH]`. Writes `{"ts","action":"mode_entry","mode","mode_file","mode_file_sha256"}` on success and `{"ts","action":"mode_entry_failed","mode","mode_file","reason"}` on exit 2.
  - `check_apply.main(argv=None) -> int`. CLI: `python3 scripts/check_apply.py --workspace W [--skill-root PATH]`. Gate name: `check_apply`. Finding codes: `NO_MODE_ENTRY`, `MODE_FILE_CHANGED`, `MISSING_RECEIPT`, `UPSTREAM_FAILED`, `NO_ROUND`, `NO_PASS_NO_STOP`, `BAD_STOP_CLASSIFICATION`, `BAD_STOP_VERDICT`, `INCOMPLETE_STOP`, `NO_BRIEF`.
  - There is no `enter_mode.mode_file`: the mode-file path comes from `paths.mode_file(mode, root)`, so `enter_mode` and `check_apply` cannot disagree about where a mode file lives.
  - The `honest-stop.yaml` schema this gate requires (defined in `modes/apply.md`, Task 20): `classification` ∈ `poorly_built | honest_stretch`; `verdict` ∈ the five-verdict vocabulary; `reason` (non-empty string); `evidence` (non-empty list of strings — the judge findings the classification rests on).

- [ ] **Step 1: Write the failing test**
    Create `scripts/tests/test_check_apply.py`:
    ```python
    import contextlib
    import importlib
    import io
    import json
    import pathlib
    import sys

    import pytest
    import yaml

    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    import check_apply
    import enter_mode
    import journal
    import rounds

    REQUIRED = ("check_personal_data", "check_claims", "check_render_freshness",
                "parse_verdicts", "lint_cv")

    # Every upstream workspace gate, with the extra arguments argparse demands
    # before main() can reach its workspace guard. check_apply has its own case
    # below (test_a_missing_workspace_is_exit_2_and_creates_nothing).
    GATE_ARGS = {
        "check_personal_data": [],
        "check_claims": [],
        "check_render_freshness": ["--round", "1"],
        "parse_verdicts": ["--round", "1", "--ats", "a.txt",
                           "--recruiter", "r.txt", "--hiring-manager", "h.txt"],
        "lint_cv": [],
        "check_letter": [],
        "check_pages": [],
        "check_word_limits": [],
    }


    def _skill_root(tmp_path, body="# Apply mode\n\nartifact: honest-stop.yaml\n"):
        root = tmp_path / "skill"
        (root / "modes").mkdir(parents=True, exist_ok=True)
        (root / "modes" / "apply.md").write_text(body, encoding="utf-8")
        return root


    def _good_workspace(tmp_path, root):
        ws = tmp_path / "acme-engineer-2026-08-09"
        ws.mkdir(parents=True, exist_ok=True)
        # enter_mode prints "entered mode apply; read …" — setup noise. Left in the
        # capture it lands in every "passes silently" assertion below and makes them
        # fail for a reason that has nothing to do with the gate under test.
        with contextlib.redirect_stdout(io.StringIO()):
            enter_mode.main(["--workspace", str(ws), "--mode", "apply",
                             "--skill-root", str(root)])
        for gate in REQUIRED:
            journal.receipt(ws, gate, {}, "pass")
        rounds.merge_round(ws, 1, {"round": 1, "combined_verdict": "PASS"})
        (ws / "interview-brief.md").write_text("# Interview brief\n", encoding="utf-8")
        return ws


    def _argv(ws, root):
        return ["--workspace", str(ws), "--skill-root", str(root)]


    def test_a_complete_apply_run_passes_silently(tmp_path, capsys):
        root = _skill_root(tmp_path)
        ws = _good_workspace(tmp_path, root)
        assert check_apply.main(_argv(ws, root)) == 0
        assert capsys.readouterr().out.strip() == ""


    def test_a_missing_upstream_receipt_is_reported_by_name(tmp_path, capsys):
        root = _skill_root(tmp_path)
        ws = _good_workspace(tmp_path, root)
        (ws / "journal.jsonl").write_text(
            "\n".join(l for l in (ws / "journal.jsonl").read_text(encoding="utf-8")
                      .splitlines() if "check_claims" not in l) + "\n", encoding="utf-8")
        assert check_apply.main(_argv(ws, root)) == 1
        out = capsys.readouterr().out
        assert "MISSING_RECEIPT: check_claims" in out
        assert "never run" in out


    def test_a_hand_written_round_file_without_a_parse_verdicts_receipt_fails(tmp_path, capsys):
        """judge-round-1.json is a plain JSON file. Without this, anyone (or any
        model) can write `combined_verdict: PASS` into it and check_apply agrees —
        with no evidence the parser ever ran, which is the exact substitution
        parse_verdicts.py exists to prevent."""
        root = _skill_root(tmp_path)
        ws = _good_workspace(tmp_path, root)
        (ws / "journal.jsonl").write_text(
            "\n".join(l for l in (ws / "journal.jsonl").read_text(encoding="utf-8")
                      .splitlines() if "parse_verdicts" not in l) + "\n", encoding="utf-8")
        assert check_apply.main(_argv(ws, root)) == 1
        assert "MISSING_RECEIPT: parse_verdicts" in capsys.readouterr().out


    def test_a_failed_upstream_gate_is_reported(tmp_path, capsys):
        root = _skill_root(tmp_path)
        ws = _good_workspace(tmp_path, root)
        journal.receipt(ws, "lint_cv", {}, "fail", ["CLICHE: cv.md:4 contains 'synergy'"])
        assert check_apply.main(_argv(ws, root)) == 1
        assert "UPSTREAM_FAILED: lint_cv" in capsys.readouterr().out


    def test_the_latest_receipt_wins_so_a_rerun_can_clear_a_failure(tmp_path, capsys):
        root = _skill_root(tmp_path)
        ws = _good_workspace(tmp_path, root)
        journal.receipt(ws, "lint_cv", {}, "fail", ["CLICHE"])
        journal.receipt(ws, "lint_cv", {}, "pass")
        assert check_apply.main(_argv(ws, root)) == 0


    def test_check_letter_is_required_only_when_a_letter_exists(tmp_path, capsys):
        root = _skill_root(tmp_path)
        ws = _good_workspace(tmp_path, root)
        assert check_apply.main(_argv(ws, root)) == 0
        (ws / "letter.yaml").write_text("sender: {}\n", encoding="utf-8")
        capsys.readouterr()
        assert check_apply.main(_argv(ws, root)) == 1
        assert "MISSING_RECEIPT: check_letter" in capsys.readouterr().out


    def test_a_rejected_round_without_an_honest_stop_fails(tmp_path, capsys):
        root = _skill_root(tmp_path)
        ws = _good_workspace(tmp_path, root)
        rounds.merge_round(ws, 1, {"combined_verdict": "REJECT"})
        assert check_apply.main(_argv(ws, root)) == 1
        out = capsys.readouterr().out
        assert "NO_PASS_NO_STOP" in out
        assert "poorly_built" in out and "honest_stretch" in out


    def test_a_rejected_round_with_a_complete_honest_stop_passes(tmp_path, capsys):
        root = _skill_root(tmp_path)
        ws = _good_workspace(tmp_path, root)
        rounds.merge_round(ws, 1, {"combined_verdict": "REJECT"})
        (ws / "honest-stop.yaml").write_text(yaml.safe_dump({
            "classification": "honest_stretch",
            "verdict": "stretch",
            "reason": ("The package is as strong as it can truthfully be; the only "
                       "unmet must-have is 5 years of clinical PACS integration, "
                       "which the candidate genuinely lacks."),
            "evidence": ["hiring_manager requirement_match: 3/5 — no clinical PACS work"],
        }, allow_unicode=True), encoding="utf-8")
        assert check_apply.main(_argv(ws, root)) == 0
        assert capsys.readouterr().out.strip() == ""


    def test_an_honest_stop_with_a_made_up_classification_fails(tmp_path, capsys):
        root = _skill_root(tmp_path)
        ws = _good_workspace(tmp_path, root)
        rounds.merge_round(ws, 1, {"combined_verdict": "REJECT"})
        (ws / "honest-stop.yaml").write_text(yaml.safe_dump({
            "classification": "needs_work", "verdict": "stretch",
            "reason": "x", "evidence": ["y"]}), encoding="utf-8")
        assert check_apply.main(_argv(ws, root)) == 1
        assert "BAD_STOP_CLASSIFICATION" in capsys.readouterr().out


    def test_an_honest_stop_with_an_off_vocabulary_verdict_fails(tmp_path, capsys):
        root = _skill_root(tmp_path)
        ws = _good_workspace(tmp_path, root)
        rounds.merge_round(ws, 1, {"combined_verdict": "REJECT"})
        (ws / "honest-stop.yaml").write_text(yaml.safe_dump({
            "classification": "honest_stretch", "verdict": "maybe",
            "reason": "x", "evidence": ["y"]}), encoding="utf-8")
        assert check_apply.main(_argv(ws, root)) == 1
        out = capsys.readouterr().out
        assert "BAD_STOP_VERDICT" in out and "worth_applying" in out


    def test_an_honest_stop_with_no_evidence_fails(tmp_path, capsys):
        root = _skill_root(tmp_path)
        ws = _good_workspace(tmp_path, root)
        rounds.merge_round(ws, 1, {"combined_verdict": "REJECT"})
        (ws / "honest-stop.yaml").write_text(yaml.safe_dump({
            "classification": "poorly_built", "verdict": "worth_applying",
            "reason": "x", "evidence": []}), encoding="utf-8")
        assert check_apply.main(_argv(ws, root)) == 1
        assert "INCOMPLETE_STOP" in capsys.readouterr().out


    def test_a_missing_interview_brief_fails(tmp_path, capsys):
        root = _skill_root(tmp_path)
        ws = _good_workspace(tmp_path, root)
        (ws / "interview-brief.md").unlink()
        assert check_apply.main(_argv(ws, root)) == 1
        assert "NO_BRIEF" in capsys.readouterr().out


    def test_no_mode_entry_fails(tmp_path, capsys):
        """The layer-1.5 backstop: modes/apply.md is not optional, and the journal
        is what proves it was loaded."""
        root = _skill_root(tmp_path)
        ws = tmp_path / "no-entry"
        ws.mkdir()
        for gate in REQUIRED:
            journal.receipt(ws, gate, {}, "pass")
        rounds.merge_round(ws, 1, {"combined_verdict": "PASS"})
        (ws / "interview-brief.md").write_text("x\n", encoding="utf-8")
        assert check_apply.main(_argv(ws, root)) == 1
        assert "NO_MODE_ENTRY" in capsys.readouterr().out


    def test_an_edited_mode_file_invalidates_the_entry(tmp_path, capsys):
        root = _skill_root(tmp_path)
        ws = _good_workspace(tmp_path, root)
        (root / "modes" / "apply.md").write_text("# Apply mode\n\nrewritten\n",
                                                 encoding="utf-8")
        assert check_apply.main(_argv(ws, root)) == 1
        assert "MODE_FILE_CHANGED" in capsys.readouterr().out


    def test_no_round_at_all_fails(tmp_path, capsys):
        root = _skill_root(tmp_path)
        ws = _good_workspace(tmp_path, root)
        rounds.round_path(ws, 1).unlink()
        assert check_apply.main(_argv(ws, root)) == 1
        assert "NO_ROUND" in capsys.readouterr().out


    def test_the_highest_numbered_round_is_the_one_that_counts(tmp_path, capsys):
        root = _skill_root(tmp_path)
        ws = _good_workspace(tmp_path, root)
        rounds.merge_round(ws, 1, {"combined_verdict": "REJECT"})
        rounds.merge_round(ws, 2, {"round": 2, "combined_verdict": "PASS"})
        assert check_apply.main(_argv(ws, root)) == 0


    def test_a_failed_mode_entry_leaves_a_trace_in_the_journal(tmp_path):
        """The layer-1.5 backstop's own failure must not be the one silent thing in
        the system. An exit-2 mode entry that wrote nothing would be
        indistinguishable from a mode entry nobody attempted — risk-register #12,
        in the exact place this plan calls the backstop."""
        root = tmp_path / "skill"
        (root / "modes").mkdir(parents=True)
        ws = tmp_path / "ws"
        assert enter_mode.main(["--workspace", str(ws), "--mode", "apply",
                                "--skill-root", str(root)]) == 2
        recs = [json.loads(l) for l in
                (ws / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
        assert [r["action"] for r in recs] == ["mode_entry_failed"]
        assert recs[0]["mode"] == "apply" and "apply.md" in recs[0]["mode_file"]
        assert enter_mode.latest_mode_entry(ws, "apply") is None


    def test_a_missing_workspace_is_exit_2_and_creates_nothing(tmp_path, capsys):
        """The single place the one-receipt-per-exit rule yields: there is no
        journal to append to. A gate that mkdir'd the workspace it was told does
        not exist would manufacture the evidence directory it is checking."""
        root = _skill_root(tmp_path)
        ws = tmp_path / "never-created"
        assert check_apply.main(_argv(ws, root)) == 2
        assert "does not exist" in capsys.readouterr().err
        assert not ws.exists()


    def test_it_leaves_exactly_one_receipt(tmp_path):
        root = _skill_root(tmp_path)
        ws = _good_workspace(tmp_path, root)
        check_apply.main(_argv(ws, root))
        assert [r["verdict"] for r in journal.read_receipts(ws, "check_apply")] == ["pass"]


    @pytest.mark.parametrize("gate", sorted(GATE_ARGS))
    def test_no_gate_creates_a_workspace_it_was_pointed_at(gate, tmp_path, capsys):
        """journal.receipt() mkdirs, so before the guard existed a typo'd
        --workspace silently materialised an empty workspace and the
        resume-in-progress lookup then found a shell — measured on lint_cv, and
        true of every gate except check_apply. This is the whole set, held to the
        one rule; scripts/enter_mode.py is the only script allowed to create a
        workspace, because it opens the mode."""
        ws = tmp_path / "typo-workspace"
        mod = importlib.import_module(gate)
        assert mod.main(["--workspace", str(ws)] + GATE_ARGS[gate]) == 2
        assert "does not exist" in capsys.readouterr().err
        assert not ws.exists()
    ```

- [ ] **Step 2: Run test to verify it fails**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_check_apply.py -q`
    Expected: FAIL with `ModuleNotFoundError: No module named 'check_apply'`

- [ ] **Step 3a: Write `scripts/enter_mode.py`**
    ```python
    #!/usr/bin/env python3
    """Record entering a mode, and the exact bytes of the mode file that was loaded.

    modes/*.md is layer 1.5: loaded unconditionally on entering the mode, not "if
    relevant". That distinction is only real if something reports its absence — a
    reference file skipped is a silent deletion, which is the failure this whole
    layering exists to avoid. So the mode's own gate requires this record, and
    requires the hash to still match the file on disk.

    Exit 0 = entered. Exit 2 = the mode file does not exist; a `mode_entry_failed`
    record is written first, because a failed entry that left no trace looks exactly
    like an entry nobody attempted — the same silence the record exists to break.

    Usage: python3 scripts/enter_mode.py --workspace W --mode apply
    """
    from __future__ import annotations

    import argparse
    import datetime
    import json
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import journal
    import paths

    MODES = ("discover", "assess", "apply", "interview")


    def _now() -> str:
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


    def latest_mode_entry(workspace, mode: str):
        path = pathlib.Path(workspace) / "journal.jsonl"
        if not path.exists():
            return None
        found = None
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict) and rec.get("action") == "mode_entry" \
                    and rec.get("mode") == mode:
                found = rec
        return found


    def main(argv=None) -> int:
        ap = argparse.ArgumentParser()
        ap.add_argument("--workspace", required=True)
        ap.add_argument("--mode", required=True, choices=MODES)
        ap.add_argument("--skill-root", default=None)
        args = ap.parse_args(argv)
        root = pathlib.Path(args.skill_root) if args.skill_root else paths.SKILL_ROOT
        path = paths.mode_file(args.mode, root)
        ws = pathlib.Path(args.workspace)
        if not path.exists():
            journal.append(ws, {
                "ts": _now(),
                "action": "mode_entry_failed",
                "mode": args.mode,
                "mode_file": f"modes/{args.mode}.md",
                "reason": f"{path} does not exist",
            })
            print(f"cannot enter mode {args.mode}: {path} does not exist", file=sys.stderr)
            return 2
        journal.append(ws, {
            "ts": _now(),
            "action": "mode_entry",
            "mode": args.mode,
            "mode_file": f"modes/{args.mode}.md",
            "mode_file_sha256": journal.sha256_file(path),
        })
        print(f"entered mode {args.mode}; read {path} in full before doing anything else")
        return 0


    if __name__ == "__main__":
        sys.exit(main())
    ```

- [ ] **Step 3b: Write `scripts/check_apply.py`**
    ```python
    #!/usr/bin/env python3
    """Gate: apply mode may not claim success without evidence for each claim.

    Composition, not new judgement. Each upstream gate already decided one thing;
    this asserts that each of them actually ran, on this workspace, and passed —
    because a skipped script produces no output and no output is exactly what a
    clean run looks like.

    Two things it adds. First, the round must have PASSed or the run must record an
    honest stop that is classified: **poorly built** (a fixable tailoring miss) or
    **honest stretch** (as strong as it can truthfully be, and the candidate is
    genuinely a notch off the role). Both outcomes emit the identical machine signal
    — three verdicts, at least one REJECT — so nothing distinguishes them, and a
    stretch candidate told "failed" abandons an application they should have sent.
    Second, the mode-entry record: modes/apply.md is loaded unconditionally, and
    this is what reports it if it was not.

    Exit 0 = the package may be delivered. Exit 1 = findings. Exit 2 = no workspace —
    and this is the one exit path in the skill that writes NO receipt, because there
    is no journal to append to and a gate that created the workspace it was told does
    not exist would manufacture the evidence directory it is checking.
    """
    from __future__ import annotations

    import argparse
    import pathlib
    import sys

    import yaml

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import enter_mode
    import journal
    import paths
    import rounds
    import vocab

    GATE = "check_apply"
    # parse_verdicts is in this list for a reason that is easy to miss:
    # judge-round-<n>.json is a plain JSON file, so without its receipt a
    # hand-written `combined_verdict: PASS` passes this gate with no evidence the
    # parser ever ran — the exact substitution parse_verdicts.py exists to prevent.
    REQUIRED_GATES = ("check_personal_data", "check_claims", "check_render_freshness",
                      "parse_verdicts", "lint_cv")
    CLASSIFICATIONS = ("poorly_built", "honest_stretch")
    VERDICTS = vocab.VERDICTS
    PASSING_VERDICTS = ("pass", "recorded")


    def _latest_round(ws: pathlib.Path):
        numbers = []
        for p in ws.glob("judge-round-*.json"):
            stem = p.stem.rsplit("-", 1)[-1]
            if stem.isdigit():
                numbers.append(int(stem))
        return max(numbers) if numbers else None


    def main(argv=None) -> int:
        ap = argparse.ArgumentParser()
        ap.add_argument("--workspace", required=True)
        ap.add_argument("--skill-root", default=None)
        args = ap.parse_args(argv)
        ws = pathlib.Path(args.workspace)
        root = pathlib.Path(args.skill_root) if args.skill_root else paths.SKILL_ROOT
        if not ws.is_dir():
            # No receipt here, deliberately: journal.append() would mkdir the
            # workspace, and a gate that creates the directory it is auditing has
            # manufactured its own evidence. Documented in the docstring.
            print(f"cannot run {GATE}: workspace {ws} does not exist", file=sys.stderr)
            return 2

        findings = []

        # ── the layer-1.5 backstop ────────────────────────────────────────────
        entry = enter_mode.latest_mode_entry(ws, "apply")
        mode_path = paths.mode_file("apply", root)
        if entry is None:
            findings.append("NO_MODE_ENTRY: journal.jsonl has no mode_entry for apply — "
                            "modes/apply.md is loaded unconditionally on entering the "
                            "mode; run scripts/enter_mode.py --mode apply and read it")
        elif mode_path.exists() and entry.get("mode_file_sha256") != journal.sha256_file(mode_path):
            findings.append("MODE_FILE_CHANGED: modes/apply.md changed after this run "
                            "entered the mode, so what was read is not what is on disk — "
                            "re-enter the mode and re-read it")

        # ── every upstream gate ran, on this workspace, and passed ────────────
        required = list(REQUIRED_GATES)
        if (ws / "letter.yaml").exists():
            required.append("check_letter")
        for gate in required:
            receipts = journal.read_receipts(ws, gate)
            if not receipts:
                # `CODE: subject` — the subject comes first so a reader (and a test)
                # can grep `MISSING_RECEIPT: check_claims` the way every other
                # finding in this skill is greppable.
                findings.append(f"MISSING_RECEIPT: {gate} has no receipt in "
                                f"journal.jsonl — the gate was never run, and a "
                                f"skipped gate looks exactly like a clean one")
                continue
            last = receipts[-1]
            if last.get("verdict") not in PASSING_VERDICTS:
                detail = "; ".join(last.get("findings") or []) or "no findings recorded"
                findings.append(f"UPSTREAM_FAILED: {gate} verdict={last.get('verdict')} "
                                f"({detail})")

        # ── the round passed, or the stop is classified ───────────────────────
        n = _latest_round(ws)
        combined = rounds.load_round(ws, n).get("combined_verdict") if n else None
        if n is None:
            findings.append("NO_ROUND: no judge-round-<n>.json in the workspace — the "
                            "three-judge review loop is non-negotiable and leaves an "
                            "artifact")
        elif combined != "PASS":
            stop_path = ws / "honest-stop.yaml"
            if not stop_path.exists():
                findings.append(f"NO_PASS_NO_STOP: round {n} is {combined} and there is no "
                                f"honest-stop.yaml. Write one and classify it: "
                                f"poorly_built (a fixable tailoring miss) or honest_stretch "
                                f"(a well-built application for a reach role). The two emit "
                                f"the same machine signal and mean opposite things to the "
                                f"user")
            else:
                stop = yaml.safe_load(stop_path.read_text(encoding="utf-8")) or {}
                if stop.get("classification") not in CLASSIFICATIONS:
                    findings.append(f"BAD_STOP_CLASSIFICATION: honest-stop.yaml "
                                    f"classification {stop.get('classification')!r} is not "
                                    f"one of {', '.join(CLASSIFICATIONS)}")
                if stop.get("verdict") not in VERDICTS:
                    findings.append(f"BAD_STOP_VERDICT: honest-stop.yaml verdict "
                                    f"{stop.get('verdict')!r} is not one of "
                                    f"{', '.join(VERDICTS)}")
                if not str(stop.get("reason") or "").strip():
                    findings.append("INCOMPLETE_STOP: honest-stop.yaml has no reason")
                if not (stop.get("evidence") or []):
                    findings.append("INCOMPLETE_STOP: honest-stop.yaml has no evidence — "
                                    "name the judge findings the classification rests on")

        if not (ws / "interview-brief.md").exists():
            findings.append("NO_BRIEF: interview-brief.md is missing — it is the last "
                            "honesty checkpoint and the only one that can still walk a "
                            "claim back after every gate has already fired")

        for f in findings:
            print(f)
        journal.receipt(ws, GATE, {}, "fail" if findings else "pass", findings)
        return 1 if findings else 0


    if __name__ == "__main__":
        sys.exit(main())
    ```

- [ ] **Step 4: Run test to verify it passes**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_check_apply.py -q`
    Expected: PASS — `27 passed` (19 check_apply cases plus the 8 parametrized workspace-guard cases, one per upstream gate). Measured: if it is 19, the eight guards from Global Constraints were not added to the gate scripts in Tasks 9–18.

- [ ] **Step 5: Commit**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/enter_mode.py scripts/check_apply.py scripts/tests/test_check_apply.py
    git commit -m "feat(gate): check_apply composes the apply-mode evidence

Requires every upstream gate's receipt (a skipped script and a clean one look
identical), the round's PASS or a classified honest stop, the interview brief, and
the mode-entry record whose hash must still match modes/apply.md — the backstop
that makes layer 1.5 unconditional rather than optional.

poorly_built vs honest_stretch is a required field precisely because both emit the
same machine signal and mean opposite things to the user."
    ```

---

### Task 20: Restructure into `SKILL.md` (layer 1) + `modes/apply.md` (layer 1.5)

**The discipline for this task, and it is the whole task: moving a line is allowed, changing it is not.** Decide the boundaries first, then move the lines byte-for-byte. "Split it into references" quietly becomes "rewrite and condense": the file shrinks, the commit says zero information loss, and operational rules are gone — invisible in review, because the diff is thousands of lines and every removed line plausibly landed somewhere. This skill has already shipped one such condensation defect: `SKILL.md:71`'s extraction field list silently dropped `salary_range` and `application_type`, and `application_type: structured` is the *only* signal that routes to the supporting-statement branch.

**What layer 1 must hold, and why.** Not "is this needed every time" but "if the model skips this, does anything report it?" For every item below the answer is *nothing*. Three of them have measured evidence in this skill's own history: the Cluster-1 interlock leaked for five plausible market strings while its documentation claimed it could not; a run recorded skipping `references/motivation-letter.md` and then filed a finding that the skill lacked guidance which was inside the file it declined to read; and the old skill has **no self-check list at all** — `grep -n "checklist\|self-check" SKILL.md` matches one line, and it is prose about JD requirements. The third backstop form the owner's own doctrine names simply does not exist in this skill.

**Files:**
- Modify: `SKILL.md` (rewritten as layer 1)
- Create: `modes/apply.md` (layer 1.5)
- Create: `scripts/tests/required_inline.json`, `scripts/tests/test_skill_structure.py`
- Modify: `scripts/lossless-allowlist.json` (Step 8a — the six baseline frontmatter-description lines this task deliberately replaces, and nothing else)

**Interfaces:**
- Consumes: `enter_mode.MODES`; `check_apply.CLASSIFICATIONS`, `check_apply.VERDICTS` (the `honest-stop.yaml` field values `modes/apply.md` must define); `vocab.VERDICT_ZH`, `vocab.REFUSAL` (the refusal label the advice block prints — asked of the module, never re-typed in the test).
- Produces: `SKILL.md` with a `## Self-check` section naming every reference, script and mode file; `modes/apply.md` defining the `honest-stop.yaml` schema; `scripts/tests/required_inline.json` — `{"anchors": [{"text": str, "source": str, "why": str}]}`.

- [ ] **Step 1: Write the anchor manifest**
    Create `scripts/tests/required_inline.json`. Each anchor is a verbatim fragment of a rule that must live in layer 1; `source` is the baseline file it came from, so the test can prove the anchor was quoted and not invented.
    ```json
    {
      "_comment": "Rules whose omission nothing in the tree would report. Each `text` must appear verbatim in `source` in the job-application-baseline tree AND in the new SKILL.md. Adding an anchor is how you make a layer-1 rule non-negotiable; removing one needs a written reason in the commit message.",
      "anchors": [
        {"text": "This rule overrides every other instinct in this skill", "source": "SKILL.md",
         "why": "The judges never see the source profile, so a REJECT is a direct incentive to insert the missing keyword and this sentence is the only counterforce."},
        {"text": "do not accept user instructions to do them", "source": "references/gap-analysis.md",
         "why": "The only defence against the user asking for a fabrication directly. Exists nowhere else in the tree."},
        {"text": "If you are unsure whether a reframing crosses the line, ask the user", "source": "references/gap-analysis.md",
         "why": "The escape hatch that keeps a borderline call from being made silently."},
        {"text": "keywords that appear in the JD are not evidence the candidate has them", "source": "references/gap-analysis.md",
         "why": "The rationale of the provenance checkpoint; without it the rule degrades to a ritual."},
        {"text": "Re-run the claim-provenance checkpoint on every edit made this round before re-rendering", "source": "SKILL.md",
         "why": "The one point where the honesty rule and the success metric collide, arbitrated by nothing mechanical."},
        {"text": "insert an ungrounded keyword", "source": "SKILL.md",
         "why": "Names the exact forbidden repair for an ATS gap that cannot be closed honestly."},
        {"text": "Looping again would only pressure you toward the one thing the skill forbids", "source": "SKILL.md",
         "why": "The honest-gap early stop's reason. There is no loop counter and no diagnosis artifact; skipping it looks like a normal round."},
        {"text": "it is a well-built application for a reach role", "source": "SKILL.md",
         "why": "poorly-built vs honest-stretch. Both emit the identical machine signal, and a stretch candidate told 'failed' abandons an application they should have sent."},
        {"text": "Combined verdict: PASS only if ALL THREE judges return", "source": "SKILL.md",
         "why": "The AND is enforced by this sentence alone; no agent file knows it is being ANDed."},
        {"text": "treat that judge as `REJECT` and re-dispatch it", "source": "SKILL.md",
         "why": "Fail-closed. parse_verdicts.py now enforces it, but the model must know why an AMBIGUOUS is not a near-pass."},
        {"text": "are advisory", "source": "SKILL.md",
         "why": "LEVELING/STANDOUT_SIGNAL: treating them as gates stalls a passing package, ignoring them drops the loop's best tailoring instruction."},
        {"text": "Each has **no other context**, so paste everything it needs", "source": "SKILL.md",
         "why": "A judge dispatched without its agent file still answers — as a generic reviewer, with a plausible VERDICT block."},
        {"text": "never re-send stale rendered files", "source": "SKILL.md",
         "why": "check_render_freshness catches it; this sentence is what tells the model what a STALE finding means."},
        {"text": "is **NEVER** mutated", "source": "SKILL.md",
         "why": "Overwriting the master is unrecoverable and only surfaces on the next application."},
        {"text": "resume from where it stopped", "source": "SKILL.md",
         "why": "Skipping the check is indistinguishable from a first run; this is what makes a returning user's second application cheap."},
        {"text": "this only collapses the *confirmation* round-trips, never the analysis or the judges", "source": "SKILL.md",
         "why": "The fast path's bound. Read as a general speed licence it authorises skipping the judges."},
        {"text": "not an ATS pass prediction", "source": "references/gap-analysis.md",
         "why": "The FIT SNAPSHOT disclaimer. The snapshot is spoken, never written, so no artifact and no script can check it."},
        {"text": "do not merge them into one", "source": "references/gap-analysis.md",
         "why": "Two formulas over the same must-have list always disagree; conflating them produces a self-consistent wrong report."},
        {"text": "Honest ≠ timid", "source": "references/gap-analysis.md",
         "why": "The counterweight to the honesty rule, with no gate at all. Under-claiming is invisible to every judge and every test."},
        {"text": "No reframing closes a legal barrier", "source": "references/gap-analysis.md",
         "why": "A hard disqualifier is a wall. A fake mitigation counts as 'addressed' to the recruiter judge."},
        {"text": "Level 5 is a last resort", "source": "references/gap-analysis.md",
         "why": "The quantification ladder is the entire middle ground between a vague bullet and an invented number."},
        {"text": "manufacture a soft metric", "source": "references/gap-analysis.md",
         "why": "The fabrication that makes a CV look better against a naive reading of the quantify-everything rule."},
        {"text": "reads as rusty to a human", "source": "references/gap-analysis.md",
         "why": "Recency downgrade. Counting stale evidence as strong inflates the verdict for a role the candidate will be screened out of."},
        {"text": "Coverage is necessary, not sufficient", "source": "references/gap-analysis.md",
         "why": "LEAD-WITH placement. No renderer measures page position and no test checks bullet order."},
        {"text": "Flawless-but-voiceless prose signals AI generation", "source": "references/gap-analysis.md",
         "why": "The AI-uniformity scan list; its harm lands entirely on the real human recruiter, outside every loop this skill observes."},
        {"text": "Restricted access is the only reason to ask the user", "source": "references/gap-analysis.md",
         "why": "Enrichment from the candidate's own papers/repos, including the honest-attribution half — misreading it produces a fabrication with a real citation behind it."},
        {"text": "strip photo, date of birth, age, marital status, and nationality from the tailored profile", "source": "references/cv-craft.md",
         "why": "The Cluster-1 interlock. Highest legal consequence in the skill, and the backstop its own documentation claimed was false for five measured spellings."},
        {"text": "A `200 OK` is not proof you have the posting", "source": "references/job-posting-extraction.md",
         "why": "The garbage-in root of the whole pipeline. Requirements invented off a login wall are internally consistent and entirely wrong."},
        {"text": "application_type", "source": "references/job-posting-extraction.md",
         "why": "The ONLY signal routing to the supporting-statement branch, and already dropped once by a condensed field list."},
        {"text": "salary_range", "source": "references/job-posting-extraction.md",
         "why": "Dropped by the same condensation. A band mismatch is a common silent screen-out."},
        {"text": "review the **supporting statement** against the framework instead", "source": "references/structured-applications.md",
         "why": "It silently overrides SKILL.md's 'non-negotiable' judge loop; a model holding only layer 1 runs CV-calibrated judges on a scored form."},
        {"text": "No Markdown formatting inside the strings", "source": "references/motivation-letter.md",
         "why": "check_letter.py catches it now, but the rule belongs where the string is written."},
        {"text": "To Whom It May Concern", "source": "references/motivation-letter.md",
         "why": "Salutation rules: rendered perfectly, read by no gate, instantly noticed by the real employer."},
        {"text": "never invented or inferred", "source": "references/rirekisho.md",
         "why": "Rirekisho personal data. An invented DOB prints identically to a real one and the form is routed away from all three judges."}
      ]
    }
    ```

- [ ] **Step 2: Verify every anchor is a real quote from the baseline, not an invention**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    python3 - <<'PY'
    import json, subprocess, sys
    data = json.load(open("scripts/tests/required_inline.json", encoding="utf-8"))
    bad = []
    for a in data["anchors"]:
        text = subprocess.run(["git", "show", f"job-application-baseline:{a['source']}"],
                              capture_output=True, text=True).stdout
        if a["text"] not in text:
            bad.append((a["source"], a["text"]))
    print(f"{len(data['anchors']) - len(bad)}/{len(data['anchors'])} anchors verified")
    for src, t in bad:
        print(f"NOT FOUND in {src}: {t}")
    sys.exit(1 if bad else 0)
    PY
    ```
    Expected: `34/34 anchors verified`, exit 0. If an anchor is not found, **fix the anchor text to match the baseline byte-for-byte** — do not reword the source to match the anchor. That would be exactly the rewrite this task forbids.

- [ ] **Step 3: Write the failing structural test**
    Create `scripts/tests/test_skill_structure.py`:
    ```python
    import json
    import pathlib
    import re
    import sys

    import pytest

    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    import enter_mode
    import vocab

    ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
    SKILL = ROOT / "SKILL.md"
    ANCHORS = json.loads((pathlib.Path(__file__).parent / "required_inline.json")
                         .read_text(encoding="utf-8"))["anchors"]


    def _self_check_section() -> str:
        text = SKILL.read_text(encoding="utf-8")
        m = re.search(r"^## Self-check.*?(?=^## |\Z)", text, re.M | re.S)
        assert m, "SKILL.md has no '## Self-check' section"
        return m.group(0)


    @pytest.mark.parametrize("anchor", ANCHORS, ids=lambda a: a["text"][:40])
    def test_every_layer1_rule_is_inline_in_skill_md(anchor):
        """Each of these fails SILENTLY if skipped — no lint, no artifact, no test
        reports it. `why` on each anchor records what goes wrong without it."""
        assert anchor["text"] in SKILL.read_text(encoding="utf-8"), \
            f"missing from SKILL.md: {anchor['text']!r} — {anchor['why']}"


    def test_the_self_check_names_every_reference_file():
        section = _self_check_section()
        for f in sorted((ROOT / "references").glob("*.md")):
            assert f"references/{f.name}" in section, f"self-check does not name {f.name}"


    def test_the_self_check_names_every_agent_file():
        section = _self_check_section()
        for f in sorted((ROOT / "agents").glob("*.md")):
            assert f"agents/{f.name}" in section


    def test_the_self_check_names_every_mode_file():
        section = _self_check_section()
        for f in sorted((ROOT / "modes").glob("*.md")):
            assert f"modes/{f.name}" in section


    def test_the_self_check_names_every_script():
        # Library-only modules: imported by gates, never invoked as a step, so a
        # checklist line for them would be a line the reader can never tick. Every
        # later plan extends this set for its own libraries and — more importantly —
        # adds its own gates to the self-check, or this test goes red.
        #
        # PLANS 2, 3 AND 4: this set is APPENDED TO, never replaced. Plan 1 owns the
        # four names below; Plan 3 adds "opencli_meta.py"; Plan 4 adds "mock_vocab.py"
        # and "mock_blocks.py"; Plan 2 adds nothing (it has no library-only module).
        # Written as a whole-line replacement instead of an append, whichever plan
        # lands last silently deletes the earlier plans' entries and the deletion
        # shows up as an unrelated red test in someone else's task.
        skip = {"journal.py", "paths.py", "rounds.py", "vocab.py"}
        section = _self_check_section()
        for f in sorted((ROOT / "scripts").glob("*.py")):
            if f.name in skip:
                continue
            assert f"scripts/{f.name}" in section, f"self-check does not name {f.name}"


    def test_every_path_the_self_check_names_exists():
        """The other direction: a checklist that names a file nobody wrote sends the
        model to read nothing and report it as done."""
        for rel in re.findall(r"`((?:references|agents|modes|scripts|assets)/[\w./-]+)`",
                              _self_check_section()):
            assert (ROOT / rel).exists(), f"self-check names a missing path: {rel}"


    def test_the_apply_mode_file_defines_the_honest_stop_schema():
        """modes/apply.md is layer 1.5 because it defines an artifact field
        check_apply.py requires. If this stops being true the mode file becomes an
        ordinary reference and loses its backstop."""
        text = (ROOT / "modes" / "apply.md").read_text(encoding="utf-8")
        assert "honest-stop.yaml" in text
        for token in ("poorly_built", "honest_stretch", "classification", "evidence"):
            assert token in text, f"modes/apply.md does not define {token}"


    def test_skill_md_tells_the_run_to_record_mode_entry():
        text = SKILL.read_text(encoding="utf-8")
        assert "scripts/enter_mode.py" in text
        assert "journal.jsonl" in text


    def test_the_frontmatter_name_matches_the_skill_directory():
        head = SKILL.read_text(encoding="utf-8").split("---")[1]
        assert re.search(r"^name:\s*job-hunt\s*$", head, re.M)


    def test_the_description_names_all_four_modes():
        """The description is trigger text. Carried over from the baseline "with the
        name changed" it would describe applying to one job and nothing else, so a
        "find me roles" request would never reach the file that says discover is not
        built yet — and nothing would report it, because the name check above passes
        either way."""
        head = SKILL.read_text(encoding="utf-8").split("---")[1].lower()
        for mode in enter_mode.MODES:
            assert mode in head, f"the frontmatter description never mentions {mode}"
        assert "honest reframing only" in head
        assert "probability" in head          # the D2 promise is in the trigger text


    def test_every_mode_named_in_skill_md_has_a_file_or_is_marked_unbuilt():
        text = SKILL.read_text(encoding="utf-8")
        for mode in enter_mode.MODES:
            if (ROOT / "modes" / f"{mode}.md").exists():
                continue
            assert re.search(rf"{mode}.{{0,80}}not yet", text, re.I | re.S), \
                f"SKILL.md names the {mode} mode but there is no modes/{mode}.md and no " \
                f"'not yet' marker — a mode that does not exist must not read as available"


    def test_a_mode_that_exists_is_not_still_described_as_not_yet_built():
        """The other direction, and it is the one that rots. This plan ships SKILL.md
        saying discover, assess and interview are not yet built; Plans 2, 3 and 4 each
        land one of those mode files. The guard above only fires when a file is
        ABSENT, so once the file exists the stale sentence passes every check and
        layer 1 tells the model to refuse a mode that works. This turns that
        coordination hope into a red suite."""
        text = re.sub(r"\s+", " ",
                      SKILL.read_text(encoding="utf-8").replace("`", "")).lower()
        for mode in ("discover", "assess", "interview"):
            if (ROOT / "modes" / f"{mode}.md").exists():
                assert f"{mode} is not yet built" not in text, (
                    f"modes/{mode}.md exists — delete '{mode} is not yet built in this "
                    f"repo' from SKILL.md's Modes table and give the row its real status")


    def test_skill_md_carries_the_apply_verdict_block_and_its_disclaimer():
        """spec §6: the block template AND the disclaimer, because the disclaimer is
        the only thing standing between a count and a prediction. New prose, so it
        cannot be an anchor in required_inline.json (those must quote the baseline)."""
        text = SKILL.read_text(encoding="utf-8")
        for token in ("投递建议：", "强烈建议投", "硬性阻断",
                      "不是对面试或录用概率的预测"):
            assert token in text, f"SKILL.md is missing {token!r} from the advice block"
        # Asked of vocab.py rather than typed, because a closed-vocabulary label
        # spelled a second way in prose is the exact drift vocab.py exists to stop
        # — and prose is the one place no other test compares against the module.
        assert vocab.VERDICT_ZH[vocab.REFUSAL] in text, (
            f"SKILL.md does not carry {vocab.VERDICT_ZH[vocab.REFUSAL]!r} verbatim; "
            f"the refusal label is spelled by vocab.py, never re-typed")


    def test_skill_md_carries_the_banned_vocabulary_and_its_one_exception():
        text = SKILL.read_text(encoding="utf-8")
        for token in ("likely to be hired", "strong candidate", "would pass",
                      "Success Profiles", "Quoting the employer's scale is reporting"):
            assert token in text, f"SKILL.md is missing {token!r} from the banned list"


    def test_skill_md_lists_every_posting_field_including_company():
        """The condensation defect that already shipped: SKILL.md:71's table dropped
        salary_range and application_type, and `application_type: structured` is the
        ONLY signal that routes to the supporting-statement branch. `company` is new
        and load-bearing — check_letter.py hard-fails without it."""
        text = SKILL.read_text(encoding="utf-8")
        for field in ("role_title", "company", "seniority", "location", "must_haves",
                      "nice_to_haves", "responsibilities", "keywords",
                      "company_values_tone", "red_flags", "salary_range",
                      "application_type"):
            assert field in text, f"the extraction field table is missing {field}"


    def test_skill_md_carries_the_grounding_contract_summary():
        """spec §8's three mechanisms. Without the summary in layer 1 the model has
        three separate rules and no account of why none of them substitutes for
        another — which is exactly when one gets treated as covering for a missing
        other."""
        text = SKILL.read_text(encoding="utf-8")
        for token in ("check_evidence_refs.py", "claims.yaml", "check_conventions.py",
                      "a floor on credibility, not a proof",
                      "restated in exactly three places"):
            assert token in text, f"SKILL.md is missing {token!r} from §8's summary"
    ```

- [ ] **Step 4: Run the test to verify it fails**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_skill_structure.py -q`
    Expected: FAIL — `AssertionError: SKILL.md has no '## Self-check' section`, plus a failure per anchor.

- [ ] **Step 5: Write `modes/apply.md` by MOVING the pipeline out of the old SKILL.md**
    Extract, byte-for-byte, from `git show job-application-baseline:SKILL.md`:
    - lines 32–39 → `## Step 0 — Interview the user`
    - lines 43–60 → `## Step 1 — CV acquisition → profile.yaml`
    - lines 64–74 → `## Step 2 — Job posting → structured requirements`
    - lines 78–89 → `## Step 3 — Gap analysis`
    - lines 93–124 → `## Step 4 — Tailor the CV`
    - lines 128–146 → `## Step 5 — Motivation letter (if requested)`
    - lines 150–195 → `## Step 6 — Hiring-pipeline review loop (non-negotiable)`
    - lines 199–210 → `## Step 7 — Finalize` and `### Step 7.5 — Interview-readiness brief`
    - lines 214–217 → `## Toolchain note`
    Anything from those ranges that is also an anchor in `required_inline.json` is **duplicated**, not moved — it appears in both SKILL.md and here. Duplication is the cheap direction; a rule that appears twice costs tokens, a rule that appears zero times costs correctness.
    Then add these new sections, which are what make this file layer 1.5:

    ````markdown
    ## Entry conditions

    An assessment should exist. Its verdict decides how this mode opens, and only one
    of the five stops it:

    - `强烈建议投` / `值得投` — enter.
    - `可以冲刺` (stretch) and `大概率被筛掉` (likely_screen_out) — **enter.** These do
      not block: building a solid application for a role the candidate is reaching for
      is not a defect, and refusing here would systematically underserve exactly the
      people this skill is for — stretch candidates and career switchers. Say the
      verdict out loud, then do the work well.
    - `硬性阻断` (blocked) — **ask once**: "this is a legal-level barrier, not a
      phrasing problem — still want to apply?" If the user says yes, proceed and do the
      work properly. Ask once, not every step; a second ask is nagging, and a silent
      refusal is deciding for them.
    - `证据不足—不出结论` — this is a refusal, not a level. Say what could not be read
      (the posting, the CV, an illegible region of an image source) and get that first.

    No assessment at all is not a blocker either: run apply, and say plainly that no
    fit assessment was made.

    ## On entering this mode

    Record the entry before doing anything else — `check_apply.py` requires it, and the
    hash is what proves the file you read is the file on disk:

    ```bash
    python3 scripts/enter_mode.py --workspace <workspace> --mode apply
    # the master profile path comes from scripts/paths.py, never hand-built:
    #   python3 -c "import sys;sys.path.insert(0,'scripts');import paths;print(paths.master_profile('<name>'))"
    python3 scripts/check_claims.py --workspace <workspace> \
        --master "$(python3 -c "import sys;sys.path.insert(0,'scripts');import paths;print(paths.master_profile('<name>'))")" \
        --record
    ```

    ## Gate commands, in the order they run

    ```bash
    # after tailoring, before dispatching the judges
    python3 scripts/check_personal_data.py --workspace <ws>
    python3 scripts/check_claims.py --workspace <ws>
    python3 scripts/lint_cv.py --workspace <ws>
    python3 scripts/check_letter.py --workspace <ws>          # only if letter.yaml exists
    python3 scripts/check_pages.py --workspace <ws>           # only if cv.pdf was produced
    python3 scripts/check_word_limits.py --workspace <ws>     # only if application_type: structured
    python3 scripts/check_render_freshness.py --workspace <ws> --round <n> \
        --record <ws>/cv.md <ws>/posting.yaml <ws>/letter.md  # letter.md only if produced

    # ... dispatch all three judges in parallel, save each reply verbatim ...

    python3 scripts/parse_verdicts.py --workspace <ws> --round <n> \
        --ats <ws>/judge-<n>-ats.txt --recruiter <ws>/judge-<n>-recruiter.txt \
        --hiring-manager <ws>/judge-<n>-hiring-manager.txt
    python3 scripts/check_render_freshness.py --workspace <ws> --round <n>
    # ... at the end of the mode ...
    python3 scripts/check_apply.py --workspace <ws>
    ```

    ## `honest-stop.yaml` — required whenever the loop ends without a PASS

    The three-judge loop ending un-passed means one of two opposite things, and they emit
    the identical machine signal. Writing this file is how the run says which:

    ```yaml
    classification: honest_stretch     # honest_stretch | poorly_built
    verdict: stretch                   # strong_apply | worth_applying | stretch |
                                       # likely_screen_out | blocked
    reason: >-
      The package is as strong as it can truthfully be. The only unmet must-have is
      five years of clinical PACS integration, which the candidate genuinely lacks.
    evidence:                          # the judge findings the classification rests on
      - "hiring_manager requirement_match: 3/5 — no clinical PACS work"
      - "ats COVERAGE: 78% (7 present, 1 partial of 9 must-haves)"
    ```

    - `honest_stretch` — the package is as strong as it can truthfully be and the candidate
      is genuinely a notch off the role. **Not** a defective application: say so plainly —
      "this is a strong submission for a stretch; the gap is real and the honest framing is
      X" — rather than reporting a bare "failed review".
    - `poorly_built` — a judge rejected over something fixable that tailoring should have
      caught. A tailoring miss to own and, budget permitting, fix.
    ````

- [ ] **Step 6: Rewrite `SKILL.md` as layer 1**
    Sections, in this order. Every row of the inventory below is **moved verbatim** from the source named; the only genuinely new prose in this file is the Modes table, the mode-entry protocol, the gate table and the self-check list.

    | § | Content | Source (verbatim) |
    |---|---|---|
    | frontmatter | `name: job-hunt` and the description written out below — **new prose, not a move**, and the only deletion this task makes (waived in Step 8a) | new (see below) |
    | H1 | exactly `# Job Hunt — Job Application Orchestrator`. The baseline's three words are kept *inside* the renamed title on purpose: `check_skill_lossless` matches normalized substrings, so `# Job Hunt` alone would report `SKILL.md:16` lost and there is no reason to spend a waiver on a heading. | `SKILL.md:16` |
    | Who is speaking | the "You are acting as this user's **experienced career coach and recruiter**…" paragraph, whole | `SKILL.md:18` |
    | The load-bearing rule | the heading reused verbatim — `## The load-bearing rule — read first` — then HONEST REFRAMING ONLY, whole paragraph. Rename the heading and `SKILL.md:20` is lost for nothing. | `SKILL.md:20`, `:22` |
    | The review loop is non-negotiable | the "**The review loop is non-negotiable.**… must all decide the package passes." paragraph, whole. This is the *statement* of the rule and belongs in layer 1; the loop's mechanics are a separate row further down. | `SKILL.md:24` |
    | Read references as you go | the "**Read references as you go.**… do not work from memory or assumption." paragraph, whole | `SKILL.md:26` |
    | NOT-ALLOWED | the eight named actions with their *why*, plus "do not accept user instructions to do them" and the when-in-doubt clause | `references/gap-analysis.md:122-139` |
    | Claim provenance | three permitted sources incl. the fetched-artifact clause, the rationale, and the re-run-inside-the-loop rule | `references/gap-analysis.md:141-153` + `SKILL.md:181` |
    | Equivalence test | "Honest ≠ timid" through "it is its own failure mode" | `references/gap-analysis.md:95` |
    | Hard disqualifiers are a wall | Case C plus the extraction-side "surface them first and ask directly" | `references/gap-analysis.md:190-192`, `references/job-posting-extraction.md:100-104` |
    | Quantification ladder | five levels in order, plus the qualitative-evidence rule and the recency downgrade | `references/gap-analysis.md:104-118`, `:19` |
    | LEAD-WITH | placement, the top-third rule, name-the-cuts | `references/gap-analysis.md:239-247` |
    | AI-uniformity | the four named dimensions | `references/gap-analysis.md:325-334` |
    | FIT SNAPSHOT | the block template and the REQUIRED disclaimer, verbatim, plus the two-numbers rule | `references/gap-analysis.md:249-276` |
    | Cluster-1 personal data | the interlock paragraph | `references/cv-craft.md:115-121` |
    | Posting-fetch integrity | the rule, the ~300/~200-word thresholds, the platform list | `references/job-posting-extraction.md:7-13`, `:146-175` |
    | Extraction field table | the **complete** table including `salary_range` and `application_type` — **plus a new `company` row** (the exact public employer name; `check_letter.py` verifies the letter's recipient against it and the workspace directory is named from it). The twelve names are written out below the table. | `references/job-posting-extraction.md:20-33` |
    | Structured applications | the review-substitution rule | `references/structured-applications.md:50-52` |
    | Localized salutations | the five-language table and the never-guess-a-name rule | `references/motivation-letter.md:198-208` |
    | Letter body constraints | no Markdown in body strings; the closing appends the name; the word budget | `references/motivation-letter.md:120`, `:210`, `:212` |
    | Rirekisho honesty | personal data never invented or inferred; gender omitted by default; the skill computes the age | `references/rirekisho.md:12-18`, `:36` |
    | The review loop | combined verdict = AND; the four parsing rules; advisory fields; parallel dispatch with the exact per-judge inputs; the mandatory edit → re-render → re-judge order; never fake a pass | `SKILL.md:152-195` |
    | Judge lanes | the three lenses and the deliberate `>=3` / `>=4` asymmetry | `SKILL.md:160`, `SKILL.md:152`, `agents/recruiter-screener.md:52`, `agents/hiring-manager.md:78` |
    | Honest-gap early stop | the rule with its rationale | `SKILL.md:185-187` |
    | Poorly built vs honest stretch | both paragraphs | `SKILL.md:189-193` |
    | Immutability + workspace | master never mutated; the workspace path convention; resume-in-progress; reuse an existing master | `SKILL.md:45`, `:47`, `:60`, `:95-103` |
    | Fast path | the bounded permission | `SKILL.md:28` |
    | Enrichment from own papers/repos | fetch before you ask, plus the honest-attribution half | `references/gap-analysis.md:59-66` |
    | Interview brief | the content contract and the over-reach signal | `references/interview-prep.md:11-23`, `:35-39` |
    | **Modes** (new) | the four-mode map. `apply` is live. `discover`, `assess` and `interview` are **not yet built in this repo** — say so and stop rather than improvising them. | new |
    | **Mode entry** (new) | on entering a mode, run `python3 scripts/enter_mode.py --workspace <ws> --mode <mode>`, then read `modes/<mode>.md` in full. The entry writes the mode file's content hash to `journal.jsonl`; `check_apply.py` fails if it is absent or stale. | new |
    | **Apply-verdict block** (new, spec §6) | the block template below, with its REQUIRED disclaimer | new (spec 5.2 step 7, §6) |
    | **Banned output vocabulary** (new, spec §6) | the list below and its single exception | new (spec §6, 5.4) |
    | **Grounding contract** (new, spec §6) | the §8 three-mechanism diagram and its three paragraphs | new (spec §8) |
    | **Gates** (new) | the table below | new |
    | **Self-check** (new) | the list below | new |

    **The `posting.yaml` field list, and it is exactly these twelve names in this order** — `modes/assess.md` §3 (Plan 2) carries the same list and the two copies must be identical, because assess writes the file and apply reads it:

    ```
    role_title, company, seniority, location, must_haves, nice_to_haves,
    responsibilities, keywords, company_values_tone, red_flags, salary_range,
    application_type
    ```

    `company` is the exact public employer name — `check_letter.py` hard-fails with `NO_COMPANY_IN_POSTING` without it, so a posting extracted without it breaks every downstream apply run. `location` is a **scalar string**, the posting's own location text, not a `{city, country, arrangement}` mapping. There is no `language` field: the CV's language follows the market and lives in `meta.language` on the profile. The old `SKILL.md:71` table silently dropped `salary_range` and `application_type`, and `application_type: structured` is the only signal routing to the supporting-statement branch — that condensation defect already shipped once.

    **The frontmatter, verbatim.** The baseline description (`SKILL.md:3-13`, verified) contains no skill name and describes applying to one job, so "carry it with the name changed" would ship a description that never mentions discover, assess or interview — and `test_the_frontmatter_name_matches_the_skill_directory` only checks `name:`, so nothing would report it. Write this instead:

    ```yaml
    ---
    name: job-hunt
    description: >-
      Help a user find, judge, apply for and rehearse for jobs. Four modes: discover
      (what is out there worth looking at), assess (whether this posting is worth
      applying to), apply (build and pressure-test the application), interview
      (rehearse and debrief). Use whenever the user wants to search for roles, judge
      their fit for a posting, tailor or optimize their CV/resume to a job, build a
      resume from scratch, write a cover/motivation letter, check whether an
      application is strong enough, or practise an interview — e.g. "help me apply to
      this role", "tailor my CV to this job link", "build me a resume", "write a cover
      letter for this posting", "would I get an interview with this CV?", "is this job
      worth applying to?", "find me MRI reconstruction roles in the Netherlands", "run
      a mock interview for this posting". Outputs Markdown, PDF (LaTeX), and .docx.
      Never fabricates experience — honest reframing only — and never predicts an
      interview or offer probability.
    ---
    ```

    The description advertises all four modes even though three are unbuilt, deliberately: it is trigger text, and a "find me roles" request that never reaches this file also never reaches the row telling the user discover is not built. Build status lives in the **Modes** table below, where the self-retracting test can police it.

    **The Modes section, verbatim** — the phrasing matters, because a test greps it:

    ```markdown
    ## Modes

    | Mode | Question it answers | Status |
    |---|---|---|
    | `discover` | what is out there worth looking at | `discover` is not yet built in this repo |
    | `assess` | is this posting worth applying to | `assess` is not yet built in this repo |
    | `apply` | how do I build and pressure-test the application | live — `modes/apply.md` |
    | `interview` | how do I answer, and what did I get wrong | `interview` is not yet built in this repo |

    For an unbuilt mode: say so and stop. Do not improvise it. An improvised discover
    run produces a shortlist with no source ids, which is indistinguishable from a real
    one and is the first row of the risk register.
    ```

    **For Plans 2, 3 and 4: this table is the retraction point, and it is a TABLE ROW, not a sentence.** There is no prose sentence anywhere in the shipped `SKILL.md` saying "discover, assess and interview are not yet built in this repo" — that phrasing exists only per-row in the Status column above. A later plan that lands its mode file edits **its own row's Status cell** to `live — modes/<mode>.md` and leaves the other rows alone. `test_a_mode_that_exists_is_not_still_described_as_not_yet_built` is what makes this non-optional: it greps whitespace-collapsed, backtick-stripped text for `<mode> is not yet built`, so the row must change, and only that row.

    **The apply-verdict block, verbatim** (spec 5.2 step 7 + §6 — the disclaimer is what stops a count being read as a prediction):

    ```markdown
    ## The advice block, and the disclaimer that is not optional

    Whenever this skill states how good a fit a posting is, it states it in exactly this
    shape — counted facts, then one word, then the disclaimer:

        must-have 强证据：   X of N   （partial P，gap G，无证据 U）
        核心职责已证实：     M of K
        职级匹配：           <上跳 | 平级 | 下沉 | 不明>
        可补缺口所需投入：   <当天 | 一晚 | 数日 | 补不上>
        投递建议：           <强烈建议投 | 值得投 | 可以冲刺 | 大概率被筛掉 | 硬性阻断>

        这是对「已写下来的证据」的清点，不是对面试或录用概率的预测。
        每一项都附了它的证据引用，分母可以逐条复核；不同意某一行就直接说。

    Every item inside N and K is printed with its evidence reference, so the denominator
    is auditable. `强证据` counts only `strong`; `partial` and `gap` are never folded into
    a "covered" number; evidence that is only `dated` counts as `partial`, never `strong`.
    When the input cannot support a conclusion at all, the whole block is replaced by
    `证据不足—不出结论` and the reason — that is a refusal, not a sixth level, and it is
    never softened into `可以冲刺`.
    ```

    **The banned output vocabulary, verbatim** (spec §6, §5.4 — one exception, and it is narrow):

    ```markdown
    ## Words this skill does not put in its output

    No percentages of fit. No self-invented scales (`7/10`, `B+`, "score: 82"). No
    probability language at all: `概率`, `chance`, `odds`, `likely to be hired`,
    `likely to be interviewed`, `strong candidate`, `would pass`. There is no data
    behind any of them — "interview probability 45–65%" is a number someone made up,
    and a weighted total is the same fabrication with arithmetic on top. The advice is
    one word from the five, and the counts beside it are counts of evidence.

    **The one exception, and its shape.** When the employer has published its own rubric
    — a UK Civil Service Success Profiles level named in the advert, an NHS values
    framework, a university person specification — this skill may walk the candidate
    through **that** scale, in the employer's own wording, with the source named, framed
    as "what the panel is asked to look at". Quoting the employer's scale is reporting.
    Using it as a conclusion is fabrication. Never assert a score on it.
    ```

    **The grounding contract summary, verbatim** (spec §8 — three mechanisms, three different jobs, none substituting for another):

    ````markdown
    ## The grounding contract

    ```
      原始来源文本                    skill 说了什么              谁在检查
      ─────────────                  ──────────────             ────────
      posting-source.txt  ──切块──► JD-001…JD-080  ──被引用──► 需求表行
      cv.md / profile     ──切块──► CV-001…CV-080                  │
                                                                    ▼
                                                        check_evidence_refs.py
                                                        （解析得到，或丢弃）

      profile.yaml 某行  ─┐
      本次会话的回答     ─┼────► claims.yaml ──被要求──► 每个 REFRAME /
      已读取的本人产物   ─┘                              KEYWORD-INSERT 词条
                                                                    │
                                                                    ▼
                                                             check_claims.py

      一个人，在一次提交里 ────► market-conventions/<key>.yaml
                                        │  id 白名单 · 逐字渲染
                                        │  绝不经模型转述
                                        ▼
                                 check_conventions.py
    ```

    1. **Evidence blocks tie the analysis to the source text.** The model may only cite
       blocks that exist; a reference that will not resolve is **dropped, not fatal**. An
       empty evidence list is not an error — rejecting it would punish the honest shape,
       and a *fabricated* reference lands in that same empty array and passes anyway.
       Carry the honest boundary into the skill's own output: **this is a floor on
       credibility, not a proof — it guarantees a claim points at something that really
       exists, not that the claim follows from it.**
    2. **Claim provenance ties the output to source facts.** Three permitted sources,
       and there is no fourth. `claims.yaml` is the first thing that makes it a diffable
       artifact instead of a habit.
    3. **Market tables tie down the one class of claim with no citable source.** In this
       whole skill exactly one kind of statement cannot be traced to text the user gave
       us: what this market screens for that the posting does not say. So it is written
       by a person, dated, with its source kind, whitelisted by id, and **rendered
       verbatim** — the model may not strengthen "usually" into "must", may not attach a
       number to it, and may not invent a row.

    **Restate the fence next to the field that tempts the violation.** A rule at the top
    of fifty instructions is not where the model is standing when it writes the dangerous
    field. The no-fabrication rule is restated in exactly three places: the KEYWORD-INSERT
    step, mock-interview question generation (a question premise the CV does not support is
    a fabrication the candidate then repeats back), and the shortlist's `why_matched` field.
    ````

    The gate table:

    | Gate | Script | Fires on |
    |---|---|---|
    | Personal data | `scripts/check_personal_data.py` | protected fields on a Cluster-1 target, or an unrecognised market |
    | Claim provenance | `scripts/check_claims.py` | a term with no source; a mutated master profile |
    | Verdict parsing | `scripts/parse_verdicts.py` | anything that is not exactly PASS/REJECT; a non-unanimous round |
    | Render freshness | `scripts/check_render_freshness.py` | a judge that read a file the disk no longer has |
    | CV lint | `scripts/lint_cv.py` | clichés, weak openers, over-long bullets, repeated verbs |
    | Letter | `scripts/check_letter.py` | markdown in a body string, length, duplicated name, wrong company/role |
    | Page count | `scripts/check_pages.py` | a PDF longer than the market's table allows; a letter over one page; an unreadable PDF |
    | Word limits | `scripts/check_word_limits.py` | a supporting-statement criterion over its stated limit, empty, or with no limit recorded |
    | Apply completion | `scripts/check_apply.py` | a missing receipt, an unclassified stop, a missing brief |
    | Migration losslessness (CI only) | `scripts/check_skill_lossless.py` | a baseline line that exists nowhere in this tree |

    **No mode may claim success while `journal.jsonl` lacks a receipt for its gates.** A skipped script produces no output, and no output is exactly what a clean run looks like. `scripts/check_skill_lossless.py` is the one exception and is marked as such: it is a repo-level CI check with no workspace and no receipt, so requiring one would be requiring evidence that cannot exist.

    The self-check list (this is the third backstop form, and the old skill had none of it):

    ```markdown
    ## Self-check — run through this before reporting the package as done

    Read-when:
    - [ ] Not a software/research/engineering role? Read `references/role-families.md`.
    - [ ] Employment gap >6 months, career switch, re-entry, over/under-levelled, thin
          experience, executive, military transition or international credentials?
          Read `references/candidate-situations.md`.
    - [ ] Essential/Desirable criteria, behaviours or a scored supporting statement?
          Read `references/structured-applications.md` — it REPLACES the CV judge loop.
    - [ ] Writing a letter? Read `references/motivation-letter.md` (skip gate first).
    - [ ] Japan + traditional/domestic employer? Read `references/rirekisho.md`.
    - [ ] Building or reordering the CV? `references/cv-craft.md`.
    - [ ] Doing gap analysis or tailoring? `references/gap-analysis.md`.
    - [ ] Extracting a posting? `references/job-posting-extraction.md`.
    - [ ] Writing the brief? `references/interview-prep.md`.
    - [ ] In apply mode? `modes/apply.md`, loaded on entry, not on demand.

    Dispatched:
    - [ ] `agents/ats-screener.md`, `agents/recruiter-screener.md` and
          `agents/hiring-manager.md` were each pasted IN FULL into their own judge.

    Ran, with a receipt in `journal.jsonl` — `scripts/check_apply.py` requires each of these:
    - [ ] `scripts/check_personal_data.py`
    - [ ] `scripts/check_claims.py`
    - [ ] `scripts/check_render_freshness.py` (recorded before dispatch, verified after)
    - [ ] `scripts/parse_verdicts.py`
    - [ ] `scripts/lint_cv.py`
    - [ ] `scripts/check_letter.py` (if a letter was produced)
    - [ ] `scripts/check_pages.py` (if a PDF was produced)
    - [ ] `scripts/check_word_limits.py` (if `application_type: structured`)
    - [ ] `scripts/check_apply.py`

    Ran, leaving a `mode_entry` record rather than a gate receipt:
    - [ ] `scripts/enter_mode.py` — and its recorded hash still matches `modes/apply.md`.

    Ran, leaving nothing in the journal (they render; they do not judge):
    - [ ] `scripts/render_cv.py`, plus `scripts/render_letter.py` /
          `scripts/render_rirekisho.py` if applicable.

    In CI, not in a workspace (no receipt exists for these, by design):
    - [ ] `scripts/check_skill_lossless.py` — only when this skill's own files changed.

    Every line above says what evidence it leaves, and the three headings differ for a
    reason: a checklist that promises a receipt where none can exist teaches its reader
    that one of its lines is decorative, and the reader cannot tell which one.

    Told the user:
    - [ ] All three verdicts and the ATS coverage line, verbatim, each round.
    - [ ] The FIT SNAPSHOT with its required disclaimer, before and after.
    - [ ] Which market and language the CV was calibrated for.
    - [ ] Any remaining honest gaps, and — if the loop ended un-passed — whether this is
          POORLY BUILT or an HONEST STRETCH.
    - [ ] The workspace path and every output file, including the `.tex`.
    ```

- [ ] **Step 7: Run the structural test to verify it passes**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_skill_structure.py -q`
    Expected: PASS — `49 passed` (34 anchor cases plus 15 structural ones).

- [ ] **Step 8: Find out exactly what the restructure dropped**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    python3 scripts/check_skill_lossless.py --baseline 864ad7f \
        --report /tmp/jh-skill-lost.md ; echo "exit=$?"
    cat /tmp/jh-skill-lost.md
    ```
    Expected: **exit 1**, and the report lists **exactly six lines — `SKILL.md:4` through `SKILL.md:9` — and nothing else.** Those six are the baseline frontmatter description, which Step 6 deliberately replaces with new trigger text; they are waived in Step 8a. Measured against the live baseline: baseline `SKILL.md:10-12` (the example prompts, and the outputs/honesty sentence) survive verbatim *inside* the new description, and `:13` normalizes to 14 characters, under the 25-character floor — so 4–9 are the whole loss.

    **Any other line in that report is a condensation, not a deletion: put it back, byte-for-byte, and do not waive it.** Every body line of the baseline `SKILL.md` is either inside one of Step 5's move ranges or named by a row of Step 6's inventory — including `:16` (the H1 words), `:18`, `:20` (the heading), `:22`, `:24`, `:26` and `:28` — so a body line reported lost means a row was condensed rather than moved, which is the one failure this whole task is written to prevent. A waiver is only ever for a line this plan *decided* to delete.

    The FIT SNAPSHOT disclaimer's percentage wording is **not** rewritten in this plan: it is carried verbatim here and revised by **Plan 2 (assess mode), which owns that rewrite and its `scripts/lossless-allowlist.json` entry**, in a separate small commit — so this diff never contains a rewrite.

- [ ] **Step 8a: Waive the six description lines, and only those**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    python3 - <<'PY'
    import json, pathlib, re
    REASON = ("job-application's frontmatter description (baseline SKILL.md:4-9), "
              "replaced 2026-08-09 by Task 20 Step 6. The new description is new "
              "trigger text: it names the skill and all four modes and carries the "
              "never-predict-a-probability promise, where the baseline description "
              "named one mode and no skill name — so a 'find me roles' request would "
              "never have reached the file that says discover is not built yet. "
              "Baseline lines 10-12 are carried verbatim inside the new description "
              "and are deliberately NOT waived.")
    report = pathlib.Path("/tmp/jh-skill-lost.md").read_text(encoding="utf-8")
    keys = re.findall(r"^- \*\*SKILL\.md:([4-9])\*\* `([0-9a-f]{16})`", report, re.M)
    others = [l for l in report.splitlines()
              if l.startswith("- **") and not re.match(r"^- \*\*SKILL\.md:[4-9]\*\*", l)]
    assert not others, "unexpected lost lines — restore these, do not waive them:\n" + "\n".join(others)
    assert len(keys) == 6, f"expected SKILL.md:4-9, got {[n for n, _ in keys]}"
    allow = json.loads(pathlib.Path("scripts/lossless-allowlist.json").read_text(encoding="utf-8"))
    for _, key in keys:
        allow["waived"][key] = REASON
    pathlib.Path("scripts/lossless-allowlist.json").write_text(
        json.dumps(allow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"waived {len(keys)} description lines")
    PY
    python3 scripts/check_skill_lossless.py --baseline 864ad7f ; echo "exit=$?"
    ```
    Expected: `waived 6 description lines`, then `LOSSLESS: … , 6 waived` and `exit=0`. The keys are computed from the report rather than typed, and each waiver keys on a hash of the normalized line — so if anyone later edits one of those six baseline lines the waiver is revoked and the line comes back for review. The `others` assertion is the shape of Task 21 Step 6's "stop" rule, applied one task earlier: a script that waived whatever it found would turn a condensation into a rubber stamp.

- [ ] **Step 9: Run the whole suite**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests -q`
    Expected: PASS — everything.

- [ ] **Step 10: Commit**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add SKILL.md modes/apply.md scripts/tests/required_inline.json \
            scripts/tests/test_skill_structure.py scripts/lossless-allowlist.json
    git commit -m "refactor(skill): SKILL.md as layer 1, modes/apply.md as layer 1.5

Boundaries decided first, lines moved byte-for-byte. What stays inline is chosen by
one test — if the model skips it, does anything report it? — and for every item in
required_inline.json the answer is no. Three have measured evidence in this skill's
own history: the Cluster-1 interlock leaked while its docs claimed it could not, a
run skipped references/motivation-letter.md and then filed a finding about guidance
inside the file it declined to read, and this skill had NO self-check list at all.

modes/apply.md is layer 1.5, not a reference: it defines the honest-stop.yaml
schema check_apply.py requires, and its content hash goes into journal.jsonl on
entry. test_skill_structure.py turns 'did you carry it' into a lint.

Adds `company` to the extraction field table — check_letter.py verifies the
letter's recipient against it and the workspace directory is named from it.

One deliberate deletion: the baseline frontmatter description (SKILL.md:4-9),
waived by hash in scripts/lossless-allowlist.json with its reason. It named one
mode and no skill name; the replacement is trigger text for all four."
    ```

---

### Task 21: `README.md` — delete the duplicated pipeline, document the workspace

Spec §9 asks for this and the migration carried the file over untouched. Three problems, all of the same kind — a second copy of something that has moved on:

1. **The 8-step process list is a stale duplicate.** It already omits Step 7.5 (the interview-readiness brief), which the real pipeline has, so a reader who trusts the README believes the run ends at "Finalize". Duplication is legitimate under this skill's layering doctrine only when a rule needs to be *where the model is standing*; a README is not that place, and a second copy of the pipeline is a second copy that drifts.
2. **The layout section lists `assets/cv/template.tex` and `assets/letter/template.tex`**, which Task 2 deleted, and does not list `modes/`, or any of the gates this plan added.
3. **"Expected: 41 tests, all passing"** was already wrong before the migration (the suite is 51) and is now wrong by more than a hundred.

It also has no record of the workspace layout — so `cv-source.txt`, `coverage.json` and `master-fingerprint.json`, all of which this plan or Plan 2 writes into a workspace, exist nowhere in the repo's own documentation.

**Files:**
- Modify: `README.md`
- Modify: `scripts/lossless-allowlist.json` (twelve waivers in three groups — the nine pipeline lines, the two `.tex` Layout lines, the test-count line — each group with the reason that describes it)
- Test: `scripts/tests/test_readme.py`

**Interfaces:**
- Consumes: `check_skill_lossless.main` (to find exactly which lines the edit dropped).
- Produces: no Python interfaces.

- [ ] **Step 1: Write the failing test**
    Create `scripts/tests/test_readme.py`:
    ```python
    import pathlib
    import re

    ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
    README = ROOT / "README.md"


    def _text():
        return README.read_text(encoding="utf-8")


    def test_the_pipeline_is_not_duplicated_here():
        """Spec §9. The copy that lived here already omitted Step 7.5, so a reader
        who trusted it believed the run ended at 'Finalize'. One pipeline, in the
        file the model actually loads."""
        text = _text()
        assert "The skill executes these 8 steps" not in text
        assert not re.search(r"^\s*4\.\s+\*\*Gap analysis\*\*", text, re.M)
        assert "SKILL.md" in text and "modes/apply.md" in text


    def test_the_layout_matches_the_repo():
        """A layout that names a deleted file sends a reader to look for it, and a
        layout that omits modes/ hides the one directory layer 1.5 lives in."""
        text = _text()
        assert "cv/template.tex" not in text and "letter/template.tex" not in text
        assert "modes/" in text
        for script in ("check_apply.py", "check_claims.py", "enter_mode.py",
                       "check_skill_lossless.py"):
            assert script in text, f"the layout does not mention {script}"


    def test_the_workspace_layout_is_documented_including_the_derived_files():
        """cv-source.txt, coverage.json and master-fingerprint.json are written into
        a workspace by this skill and appear in no design document. An undocumented
        artifact is one a later reader deletes as junk."""
        text = _text()
        for name in ("applications/<company>-<role>-<YYYY-MM-DD>", "journal.jsonl",
                     "claims.yaml", "master-fingerprint.json", "cv-source.txt",
                     "coverage.json", "posting-source.txt", "judge-round-<n>.json"):
            assert name in text, f"the workspace layout does not mention {name}"


    def test_no_stale_test_count_claim():
        """'Expected: 41 tests' was wrong before the migration and is wrong by more
        than a hundred now. A number that nothing updates is a number that lies."""
        assert not re.search(r"\b\d+\s+tests?,\s+all passing", _text())
    ```

- [ ] **Step 2: Run test to verify it fails**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_readme.py -q`
    Expected: FAIL — `assert 'The skill executes these 8 steps' not in text`, plus the layout and workspace failures.

- [ ] **Step 3: Replace the "Skill flow" section with a pointer**
    In `README.md`, replace the whole `## Skill flow` section (the intro line and the eight numbered items) with:
    ```markdown
    ## How it runs

    One pipeline, in one place. `SKILL.md` holds the rules that must be in context on
    every run — the honesty rule, the NOT-ALLOWED table, the claim-provenance
    checkpoint, the gate table, the self-check. `modes/apply.md` holds the apply
    pipeline itself and is loaded unconditionally on entering the mode, with its
    content hash written to the workspace journal so that "it was loaded" is a fact
    rather than a hope.

    A second copy of the pipeline was here until 2026-08-09 and had already drifted —
    it listed eight steps and omitted the interview-readiness brief. Read `SKILL.md`.
    ```

- [ ] **Step 4: Correct the layout section and add the workspace layout**
    Replace the contents of the `## Layout` code block with exactly this:
    ```
    job-hunt/
    ├── SKILL.md                        # Orchestrator instructions — layer 1, always in context
    ├── README.md
    ├── requirements.txt
    ├── Makefile                        # make check = tests + losslessness + conventions
    ├── .github/workflows/checks.yml    # the same three checks, for whenever this repo gains a remote
    ├── modes/
    │   └── apply.md                    # Layer 1.5 — the apply pipeline, loaded on mode entry
    ├── references/
    │   ├── cv-craft.md                 # CV writing conventions (markets, links, bullets, ordering)
    │   ├── gap-analysis.md             # Gap analysis + tailoring methodology
    │   ├── job-posting-extraction.md   # How to parse a posting (+ fetch sanity, application type)
    │   ├── candidate-situations.md     # Non-standard candidates (gap, switch, exec, military, intl)
    │   ├── role-families.md            # Non-tech / regulated role conventions (clinical, sales, legal…)
    │   ├── structured-applications.md  # Competency-form applications (NHS, Civil Service)
    │   ├── motivation-letter.md        # Letter craft guide
    │   ├── interview-prep.md           # Interview-readiness brief
    │   └── rirekisho.md                # Japanese 履歴書 form guide
    ├── agents/                         # Three review judges (hiring funnel)
    │   ├── ats-screener.md             # Judge 1 of 3 — machine lens (keyword coverage)
    │   ├── recruiter-screener.md       # Judge 2 of 3 — fast human screen (skim/logistics)
    │   └── hiring-manager.md           # Judge 3 of 3 — deep human lens (fit/credibility)
    ├── assets/
    │   └── profile.example.yaml        # Canonical profile schema
    ├── docs/                           # spec, plans, research — outside the skill corpus
    └── scripts/
        ├── journal.py                  # gate receipts in journal.jsonl (library)
        ├── paths.py                    # the one definition of the workspace shape (library)
        ├── vocab.py                    # every closed vocabulary in the skill (library)
        ├── rounds.py                   # judge-round-<n>.json read/merge (library)
        ├── enter_mode.py               # mode entry + the mode file's content hash
        ├── check_personal_data.py      # Cluster-1 interlock
        ├── check_claims.py             # claim provenance + master-profile immutability
        ├── check_render_freshness.py   # the judges read the files still on disk
        ├── parse_verdicts.py           # PASS/REJECT parsing, fail-closed on AMBIGUOUS
        ├── lint_cv.py                  # clichés, weak openers, bullet length, repeated verbs
        ├── check_letter.py             # letter body constraints
        ├── check_pages.py              # page count of the artifact actually submitted
        ├── check_word_limits.py        # supporting-statement per-criterion word limits
        ├── check_apply.py              # the composing gate: every receipt present
        ├── check_skill_lossless.py     # CI only — the migration moved content, not deleted it
        ├── lossless-allowlist.json     # deliberate deletions, each with a written reason
        ├── render_cv.py
        ├── render_letter.py
        ├── render_rirekisho.py         # Japanese 履歴書 form renderer
        └── tests/
            ├── fixtures/
            ├── required_inline.json    # layer-1 rules that must stay inline, each with its why
            └── test_*.py               # one module per script above
    ```
    Three things about that tree are deliberate, not cosmetic. **The comments on the carried-over lines are byte-identical to the baseline's** — `# Orchestrator instructions`, `# CV writing conventions (markets, links, bullets, ordering)`, `# Japanese 履歴書 form renderer` and the rest — because `check_skill_lossless.py` matches normalized substrings and rewording any of them turns a layout line into a lost line that then needs a waiver it does not deserve. `SKILL.md`'s comment gains `— layer 1, always in context` *after* the baseline words for the same reason: appended text still contains the original substring, replaced text does not. **`Makefile` and `.github/workflows/checks.yml` are written by Task 22**, one task later; naming them here makes the layout correct at the end of the plan rather than correct for exactly one commit. And `assets/cv/template.tex` / `assets/letter/template.tex` are gone — those two lines are the second waiver group in Step 6.

    Then append, after the code block:
    ````markdown
    ### A workspace

    Everything a single application produces lives in one directory whose **shape is
    load-bearing**: the "resume an unfinished application" lookup finds a prior run by
    that shape, so a run that invents its own layout orphans the previous workspace and
    silently re-interviews the user from scratch. `scripts/paths.py` is the only place
    it is defined.

    ```
    ~/.claude/job-profiles/<name>/
      profile.yaml                 master profile · never mutated by any mode
      search-preferences.yaml      target market/city/level/languages (written by discover)
      answer-bank.md               the one artifact that accumulates across applications

      applications/<company>-<role>-<YYYY-MM-DD>/
        posting.yaml               extracted requirements
        posting-source.txt         raw capture · never edited
        cv-source.txt              raw CV text the assessment was cut from (assess mode)
        evidence-blocks.json       derived · never hand-edited
        fit-assessment.{yaml,md}
        coverage.json              the single counting path (assess mode)
        claims.yaml                append-only · a withdrawal is marked `retracted`, not deleted
        master-fingerprint.json    sha256 + mtime of profile.yaml at mode entry, so a
                                   mutated master is detectable rather than discovered
                                   on the NEXT application
        tailored-profile.yaml
        cv.{md,docx,pdf,tex} · letter.* · supporting-statement.md
        judge-round-<n>.json       dispatch hashes + the three parsed verdicts
        interview-brief.md
        mock/                      transcripts, assessments, question log (interview mode)
        journal.jsonl              every gate receipt · the evidence a gate actually ran
    ```
    ````

- [ ] **Step 5: Drop the stale test-count claim**
    Replace `Expected: 41 tests, all passing.` with:
    ```markdown
    Everything must pass. `make check` additionally runs the migration losslessness
    check and the market-convention lint.
    ```

- [ ] **Step 6: Find exactly which lines the edit dropped, and waive those and only those**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    python3 scripts/check_skill_lossless.py --baseline 864ad7f \
        --report /tmp/jh-readme-lost.md ; echo "exit=$?"
    cat /tmp/jh-readme-lost.md
    ```
    Expected: exit 1, and the report lists **exactly twelve `README.md` lines and nothing else**. Measured against the live README with `check_skill_lossless.normalize`, they are:

    | Lines | What they are | Deleted by |
    |---|---|---|
    | `README.md:35`, `:37`–`:44` | the "The skill executes these 8 steps" intro plus the eight numbered steps | Step 3 |
    | `README.md:83`, `:84` | the two `.tex` template lines in the Layout tree (33 and 41 normalized chars) | Step 4 |
    | `README.md:104` | `Expected: 41 tests, all passing.` (29 normalized chars) | Step 5 |

    `## Skill flow` itself (`README.md:33`) normalizes to 10 characters, under the 25-character floor, so it is not reported and needs no waiver — and every other Layout line survives verbatim in Step 4's tree, which is why that tree keeps the baseline's comments byte-for-byte. If any line from `SKILL.md`, `modes/`, `references/` or `agents/` appears, stop: Task 20 lost content and no waiver is appropriate. (Task 20 Step 8a already waived the six baseline frontmatter-description lines, so those will not appear here.)

    Then add exactly those keys, computed from the report rather than typed, **with the reason that actually describes each group** — a single blanket reason would record the two Layout lines and the test-count line as "the duplicated 8-step pipeline list", which is false, and an allowlist entry whose reason does not describe its line is a casualty wearing a decision's clothes:
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    python3 - <<'PY'
    import json, pathlib, re
    PIPELINE = ("README's duplicated 8-step pipeline list, deleted 2026-08-09. It was a "
                "second copy of SKILL.md's flow and had already drifted — it omitted Step "
                "7.5, the interview-readiness brief. Spec §9 asks for the duplication to "
                "go; the pipeline now exists once, in SKILL.md and modes/apply.md.")
    TEMPLATES = ("README's Layout tree named assets/cv/template.tex and "
                 "assets/letter/template.tex, both deleted in Task 2 as dead and drifted "
                 "files that nothing loads. A layout line for a file that no longer exists "
                 "sends a reader to look for it. The deletions themselves are recorded "
                 "under deleted_files in this same allowlist.")
    TESTCOUNT = ("README's 'Expected: 41 tests, all passing.' — a count nothing updates. It "
                 "was already wrong before the migration (the suite was 51) and is wrong by "
                 "more than a hundred now. Replaced by `make check`, which has no number in "
                 "it to rot.")
    GROUPS = {PIPELINE: {35, 37, 38, 39, 40, 41, 42, 43, 44},
              TEMPLATES: {83, 84},
              TESTCOUNT: {104}}

    def reason_for(lineno: int) -> str:
        for reason, lines in GROUPS.items():
            if lineno in lines:
                return reason
        raise SystemExit(f"README.md:{lineno} was not expected to be deleted — read the "
                         f"line and fix the edit; do not waive it under someone else's reason")

    report = pathlib.Path("/tmp/jh-readme-lost.md").read_text(encoding="utf-8")
    hits = re.findall(r"^- \*\*README\.md:(\d+)\*\* `([0-9a-f]{16})`", report, re.M)
    others = [l for l in report.splitlines()
              if l.startswith("- **") and not l.startswith("- **README.md:")]
    assert not others, "non-README losses — restore these, do not waive them:\n" + "\n".join(others)
    allow = json.loads(pathlib.Path("scripts/lossless-allowlist.json").read_text(encoding="utf-8"))
    for lineno, key in hits:
        allow["waived"][key] = reason_for(int(lineno))
    pathlib.Path("scripts/lossless-allowlist.json").write_text(
        json.dumps(allow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"waived {len(hits)} README lines in {len({reason_for(int(n)) for n, _ in hits})} groups")
    PY
    ```
    Expected: `waived 12 README lines in 3 groups`. Every waiver keys on a hash of the normalized line, so editing any of those lines later revokes its waiver and brings it back for review.

- [ ] **Step 7: Verify losslessness and the whole suite**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    python3 scripts/check_skill_lossless.py --baseline 864ad7f
    python3 -m pytest scripts/tests -q
    ```
    Expected: `LOSSLESS: … , 18 waived` and exit 0; the whole suite passes, including the four new `test_readme.py` cases. Eighteen, not twelve: the script prints the running total for the whole allowlist, and Task 20 Step 8a already waived the six baseline frontmatter-description lines. If it says 12, Task 20's waivers were dropped when this step rewrote the file.

- [ ] **Step 8: Commit**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add README.md scripts/lossless-allowlist.json scripts/tests/test_readme.py
    git commit -m "docs(readme): one pipeline, a correct layout, and the workspace shape

The duplicated 8-step list had already drifted — it omitted Step 7.5 — which is
the failure mode a second copy always has. Deleted. Twelve dropped lines are
waived by hash in three groups, each with the reason that describes it: the nine
pipeline lines, the two .tex Layout lines, and the stale test count. Editing any
of them revokes its waiver.

Also drops the two deleted .tex templates from the layout, adds modes/ and the
gates, documents the workspace directory including cv-source.txt, coverage.json
and master-fingerprint.json, and removes a test-count claim that was wrong before
the migration and is wrong by more than a hundred now."
    ```

---

### Task 22: CI — `make check` and a workflow, so spec §12's "进 CI" is a file

Spec §12 requires `check_skill_lossless.py` to run in CI, and §7's P0 table requires `check_conventions.py --all` to fail the build on an expired market table. No plan wired either. A check that exists but is never invoked is a check that is not there — the same class of defect as a gate with no receipt, one level up.

**Files:**
- Create: `Makefile`, `.github/workflows/checks.yml`
- Test: `scripts/tests/test_ci.py`

**Interfaces:**
- Consumes: `scripts/check_skill_lossless.py`; `scripts/check_conventions.py` when Plan 2 lands it.
- Produces: `make test`, `make lossless`, `make conventions`, `make check`.

**About the conventions guard.** `check_conventions.py` is Plan 2's. Until it exists both CI entry points guard it with a file test — and both carry a self-retracting test, so the moment Plan 2 lands the script the suite goes red until the guard is removed. A step that skips silently after the script exists is a step that is not running.

- [ ] **Step 1: Write the failing test**
    Create `scripts/tests/test_ci.py`:
    ```python
    import pathlib

    ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
    MAKEFILE = ROOT / "Makefile"
    WORKFLOW = ROOT / ".github" / "workflows" / "checks.yml"


    def test_both_entry_points_exist():
        assert MAKEFILE.is_file() and WORKFLOW.is_file()


    def test_the_makefile_and_the_workflow_run_the_same_three_checks():
        """Two entry points that run different things is worse than one: the local
        one passes, the remote one fails, and nobody knows which is authoritative."""
        mk, wf = MAKEFILE.read_text(encoding="utf-8"), WORKFLOW.read_text(encoding="utf-8")
        for needle in ("pytest scripts/tests", "check_skill_lossless.py",
                       "check_conventions.py"):
            assert needle in mk, f"Makefile does not run {needle}"
            assert needle in wf, f"checks.yml does not run {needle}"


    def test_ci_fetches_enough_history_for_the_lossless_baseline():
        """check_skill_lossless resolves a git TAG. A default shallow checkout has no
        tags, so the check exits 2 — 'could not read the baseline', which is exactly
        why that is a different exit code from 'content was lost'."""
        assert "fetch-depth: 0" in WORKFLOW.read_text(encoding="utf-8")


    def test_the_conventions_guard_disappears_when_the_script_lands():
        """Plan 2 ships check_conventions.py. This test is red from that moment until
        both entry points stop guarding it — because a CI step that keeps skipping is
        a CI step that is not there, and spec §10 requires an expired market table to
        fail the build."""
        if not (ROOT / "scripts" / "check_conventions.py").exists():
            return
        for f in (MAKEFILE, WORKFLOW):
            assert "-f scripts/check_conventions.py" not in f.read_text(encoding="utf-8"), (
                f"{f.name} still guards check_conventions.py behind a file test — the "
                f"script exists now; run it unconditionally")
    ```

- [ ] **Step 2: Run test to verify it fails**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_ci.py -q`
    Expected: FAIL — `assert MAKEFILE.is_file() and WORKFLOW.is_file()`

- [ ] **Step 3: Write the Makefile**
    Create `Makefile` (tabs, not spaces, in the recipe lines):
    ```make
    # The checks this repo is held to. `make check` is what actually runs today —
    # the workflow file below it is the same three commands for whenever this repo
    # gains a remote. Two entry points that run different things would be worse than
    # one, so scripts/tests/test_ci.py asserts they stay in step.
    .PHONY: test lossless conventions check
    PY ?= python3
    BASELINE ?= job-application-baseline

    test:
    	$(PY) -m pytest scripts/tests -q

    lossless:
    	$(PY) scripts/check_skill_lossless.py --baseline $(BASELINE)

    conventions:
    	@if [ -f scripts/check_conventions.py ]; then \
    	  $(PY) scripts/check_conventions.py --all; \
    	else \
    	  echo "check_conventions.py is not in this repo yet (Plan 2 lands it) — skipped"; \
    	fi

    check: test lossless conventions
    ```

- [ ] **Step 4: Write the workflow**
    Create `.github/workflows/checks.yml`:
    ```yaml
    name: checks

    on:
      push:
      pull_request:

    jobs:
      checks:
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v4
            with:
              # check_skill_lossless.py resolves the job-application-baseline TAG.
              # A shallow checkout has no tags, and the check would exit 2.
              fetch-depth: 0
          - uses: actions/setup-python@v5
            with:
              python-version: '3.11'
          - run: pip install -r requirements.txt pytest
          - run: python3 -m pytest scripts/tests -q
          - run: python3 scripts/check_skill_lossless.py --baseline 864ad7f
          - name: market conventions
            run: |
              if [ -f scripts/check_conventions.py ]; then
                python3 scripts/check_conventions.py --all
              else
                echo "check_conventions.py is not in this repo yet (Plan 2 lands it)"
              fi
    ```

- [ ] **Step 5: Run test to verify it passes, then run the target for real**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    python3 -m pytest scripts/tests/test_ci.py -q
    make check
    ```
    Expected: `4 passed`; `make check` runs the suite green, prints `LOSSLESS: …`, and prints the conventions skip line. If `make` reports `missing separator`, the recipe lines are indented with spaces instead of a tab.

- [ ] **Step 6: Commit**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add Makefile .github/workflows/checks.yml scripts/tests/test_ci.py
    git commit -m "ci: run pytest, the losslessness check and the conventions lint

Spec §12 puts check_skill_lossless.py in CI and §7 puts check_conventions.py --all
there; nothing invoked either. A check that exists and is never run is a check that
is not there. The conventions step is guarded until Plan 2 lands the script, and
test_ci.py goes red the moment it does so the guard cannot outlive its reason."
    ```

---

### Task 23: Install into both runtimes and smoke-test them

One repo, two symlinks — the same shape as `slide-maker`, which is already symlinked into `~/.claude/skills` from `~/code_project/slides_maker`. One copy of the doctrine, so it cannot drift between runtimes. The old `job-application` directory stays on disk as an archive but is **not** symlinked: two skills whose descriptions overlap fight for the trigger, and the user then has to know which one to invoke.

**Files:**
- Create: `~/.claude/skills/job-hunt` → `/Users/donghanglyu/code_project/job-hunt` (symlink)
- Create: `~/.codex/skills/job-hunt` → `/Users/donghanglyu/code_project/job-hunt` (symlink)
- Test: `scripts/tests/test_install.py`

**Interfaces:**
- Consumes: `SKILL.md`, `modes/apply.md`, `scripts/*.py` from Task 20.
- Produces: two resolvable skill directories. No new Python interfaces.

- [ ] **Step 1: Write the failing test**
    Create `scripts/tests/test_install.py`:
    ```python
    import pathlib

    import pytest

    ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
    LINKS = [pathlib.Path.home() / ".claude" / "skills" / "job-hunt",
             pathlib.Path.home() / ".codex" / "skills" / "job-hunt"]


    @pytest.mark.parametrize("link", LINKS, ids=lambda p: p.parent.parent.name)
    def test_the_runtime_resolves_the_skill(link):
        if not link.parent.is_dir():
            pytest.skip(f"{link.parent} does not exist on this machine")
        assert link.is_symlink(), f"{link} is not a symlink — a copy would drift"
        assert link.resolve() == ROOT
        assert (link / "SKILL.md").is_file()
        assert (link / "modes" / "apply.md").is_file()
        assert (link / "scripts" / "check_apply.py").is_file()


    def test_the_old_skill_is_archived_but_not_symlinked():
        """Two skills with overlapping descriptions fight for the trigger and the
        user has to know which to invoke."""
        old = pathlib.Path.home() / ".claude" / "skills" / "job-application"
        assert old.is_dir(), "the archive was removed; it is the migration's baseline"
        assert not old.is_symlink()
    ```

- [ ] **Step 2: Run test to verify it fails**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_install.py -q`
    Expected: FAIL with `AssertionError: /Users/donghanglyu/.claude/skills/job-hunt is not a symlink`

- [ ] **Step 3: Create the symlinks**
    ```bash
    ln -s /Users/donghanglyu/code_project/job-hunt /Users/donghanglyu/.claude/skills/job-hunt
    ln -s /Users/donghanglyu/code_project/job-hunt /Users/donghanglyu/.codex/skills/job-hunt
    ls -l /Users/donghanglyu/.claude/skills/job-hunt /Users/donghanglyu/.codex/skills/job-hunt
    ```

- [ ] **Step 4: Run test to verify it passes**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_install.py -q`
    Expected: PASS — `3 passed`

- [ ] **Step 5: Smoke-test that both runtimes execute the skill's code through the link**
    ```bash
    head -3 ~/.claude/skills/job-hunt/SKILL.md
    head -3 ~/.codex/skills/job-hunt/SKILL.md
    SMOKE="/tmp/jh-smoke-$$"          # a path that does not exist, and must not exist after
    python3 ~/.claude/skills/job-hunt/scripts/check_apply.py --workspace "$SMOKE"; echo "exit=$?"
    python3 ~/.codex/skills/job-hunt/scripts/lint_cv.py --workspace "$SMOKE"; echo "exit=$?"
    if [ -e "$SMOKE" ]; then echo "CREATED — the workspace guard is missing"; else echo "not created: ok"; fi
    rm -rf "$SMOKE"
    ```
    Expected: both `head` calls print `---` / `name: job-hunt` / `description: >-`; both scripts print `cannot run <gate>: workspace /tmp/jh-smoke-<pid> does not exist` to stderr and `exit=2`; then `not created: ok`. The orderly exit 2 proves the module imports resolved through the symlink (an unresolvable import would be a traceback, not an exit 2). The `not created` line proves the Global Constraints workspace guard is really in every gate: measured before it was added, `lint_cv.py --workspace <a path that does not exist>` printed the right message, exited 2 **and left a `journal.jsonl` behind**, because `journal.receipt()` mkdirs — so a typo'd `--workspace` silently manufactured the empty workspace the resume lookup would later find. `rm -rf "$SMOKE"` is a belt-and-braces cleanup for the day that regresses.

- [ ] **Step 6: Full suite and a final losslessness check**
    Run:
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    make check
    git status --short -- ':!docs'
    ```
    Expected: `make check` runs the whole suite green and prints `LOSSLESS: … , 18 waived` with exit 0 (6 from Task 20 Step 8a + 12 from Task 21 Step 6). `git status --short -- ':!docs'` shows **only** `?? scripts/tests/test_install.py`.
    `docs/` is excluded from that listing deliberately, not to hide anything: it is tracked, it is outside the skill corpus, and executing this plan legitimately leaves plan/research edits there. Anything else appearing under the skill tree itself — `SKILL.md`, `modes/`, `references/`, `agents/`, `assets/`, `scripts/`, `Makefile`, `.github/` — means a task's commit step was skipped; find it before finishing.

- [ ] **Step 7: Commit**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/tests/test_install.py
    git commit -m "chore(install): symlink job-hunt into both runtimes, assert it resolves

One repo, two symlinks — the doctrine cannot drift between Claude Code and Codex.
job-application stays on disk as the migration baseline and is deliberately NOT
symlinked: two skills with overlapping descriptions fight for the trigger."
    ```
    Do **not** push. Report what is unpushed at the end of the run.

---

## Not in this plan

State these when reporting completion, so nobody assumes they landed:

- **The `discover`, `assess` and `interview` modes.** SKILL.md names them and says, per mode and in those exact words, that each `is not yet built in this repo`; `modes/` holds only `apply.md`. Those words are the **Status cell of that mode's row in SKILL.md's `## Modes` table** — there is no prose sentence to find. `test_a_mode_that_exists_is_not_still_described_as_not_yet_built` turns each row into a self-retracting one: the suite goes red the moment a later plan lands the mode file without editing its own row's Status to `live — modes/<mode>.md`.
- **The self-check list and the gate table are extended by every later plan, and the suite is RED until they are.** `test_the_self_check_names_every_script` / `..._every_reference_file` / `..._every_agent_file` / `..._every_mode_file` are deliberately exhaustive. Plans 2, 3 and 4 together add fourteen scripts, three mode files, three reference files and two agent files, so each of them needs a final task that appends its own entries to SKILL.md's `## Self-check` section **and** its gate table, and **appends to** the `skip` set for its library-only modules (`opencli_meta.py` from Plan 3, `mock_vocab.py` and `mock_blocks.py` from Plan 4, joining `journal.py`, `paths.py`, `rounds.py`, `vocab.py`; Plan 2 has no library-only module and adds nothing). Appends, not replacements: three plans editing the same line as a whole-line replacement means whichever lands last deletes the other two's entries. This plan cannot do it — it runs first — and the red suite is the mechanism, not an accident.
- **The CI conventions guard is Plan 2's to remove, and it is a FIFTH red.** Task 22 ships `make conventions` and the workflow's market-conventions step behind an `if [ -f scripts/check_conventions.py ]` file test, because the script does not exist yet and a CI step that references a missing file fails for the wrong reason. `test_the_conventions_guard_disappears_when_the_script_lands` returns early while the script is absent and goes **red the moment Plan 2 Task 6 creates it** — a CI step that keeps skipping is a CI step that is not there, and spec §10 requires an expired market table to fail the build. **Plan 2 must delete the guard from both `Makefile` and `.github/workflows/checks.yml` in the same task that creates the script**, and stage both files in that task's commit. Until it does, this test is red alongside the four self-check tests above, and any later plan's "the whole suite is green" step is unreachable.
- **The mode-entry step for the other three modes.** `scripts/enter_mode.py` handles all four modes and `check_apply.py` requires the record for `apply`. Plans 2, 3 and 4 must each make `enter_mode.py --mode <theirs>` the first step of their mode file and mirror the `NO_MODE_ENTRY` / `MODE_FILE_CHANGED` findings into their own gate; without that, half of the layer-1.5 backstop exists for one mode out of four.
- **The §12 flagged rewrite.** The FIT SNAPSHOT's required disclaimer talks about keyword-coverage *percentages*, and the new assess mode stops emitting those. Carrying it verbatim here is correct — this plan's job is that `job-hunt` does everything `job-application` does. **Plan 2 owns the rewrite**, as a separate small readable commit with its own `scripts/lossless-allowlist.json` entry naming it, so it is a decision rather than a casualty.
- **Six layer-1 items from spec §6 that belong to the unbuilt modes**, listed so nobody finishes this plan believing SKILL.md is §6-complete. Landing here: the apply-verdict block and its disclaimer, the skill-wide banned-output vocabulary and its published-employer-rubric exception, and the §8 grounding-contract summary (Task 20). Landing with their modes: the read-only guarantee plus the `access: read` allow-list and the four opencli command pairs (**Plan 3**); the **platform-limit stop rule** — stop, no retry, no parameter change, no bypass, direction-level degradation, fill the disclosure table — which **Plan 3 carries into the same SKILL.md block** as the read-only guarantee; the four anti-coaching rules and their tripwire, and the mock-interview session mechanics (**Plan 4**).
- **The remaining spec §7 scripts.** Six of them are **P0**, not P1/P2, which matters in a plan titled "migration and P0 fixes": `check_shortlist.py`, `check_conventions.py`, `check_evidence_refs.py`, `lint_no_prediction.py`, `check_no_write.py`, `check_opencli_result.py`. Then the P1/P2 remainder: `consistency.py`, `check_mock.py`, `count_coverage.py`. And two the spec names outside those tables: `evidence_blocks.py` (spec 5.2 step 5) and `check_assessment.py` (spec 5.2 gates). `check_pages.py` and `check_word_limits.py` are **no longer on this list** — Tasks 17 and 18 build them.
- **The eval rebuild.** The existing baseline at `~/.claude/skills/job-application-workspace/iteration-1/` has one run per configuration despite metadata claiming three, a baseline arm on only two of five evals, and one assertion logged as non-discriminating. Re-running it as `iteration-2` against `job-hunt` is the only real test of Task 20's layering change — `check_skill_lossless.py` proves bytes survived, not that they arrive when needed. Spec §10 assigns it to this implementation; it is **Plan 5**, a separate plan.

