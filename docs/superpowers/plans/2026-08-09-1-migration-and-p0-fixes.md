# Migration and P0 Defect Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the `job-application` skill into the `job-hunt` repo with its git history intact, fix every defect that has been measured live in it, and put the layer-1 / layer-1.5 / layer-2 / layer-3 structure in place — so that after this plan `job-hunt` does everything `job-application` does today, with a deterministic gate behind each rule a program can decide.

**Architecture:** The repo root *is* the skill. `SKILL.md` (layer 1) holds every rule whose omission nothing would report; `modes/apply.md` (layer 1.5) holds the apply pipeline and is loaded unconditionally on mode entry, with its content hash written to `journal.jsonl` as the backstop; `references/*.md` (layer 2) hold branch-specific craft detail; `scripts/*.py` (layer 3) hold everything a program can decide. Every gate script shares one CLI contract, imports `scripts/journal.py`, and leaves a receipt in the workspace journal — so "the gate passed" and "the gate never ran" stop looking identical.

**Tech Stack:** Python 3 (stdlib + PyYAML + python-docx only), pytest, git, LaTeX (tectonic) for PDF output.

## Global Constraints

- Repo root: `/Users/donghanglyu/code_project/job-hunt`. The repo root IS the skill. Git is already initialised; the design spec is committed at `docs/superpowers/specs/2026-08-09-job-hunt-skill-design.md`.
- Python 3, stdlib + PyYAML + python-docx only (already in `requirements.txt`). pytest for tests.
- Run the suite with: `python3 -m pytest scripts/tests -q` (from the repo root). Verified: this command works from the repo root after the migration.
- Every gate script obeys this CLI contract, no exceptions:
  `python3 scripts/<name>.py --workspace <path> [script-specific args]`
  `exit 0` = gate passed. `exit 1` = gate failed (findings printed to stdout, one per line, each prefixed with a stable UPPERCASE code, e.g. `UNSOURCED: ...`, `STALE: ...`, `NO_SOURCE_ID: ...`). `exit 2` = could not run (missing input file); message to stderr.
- Every gate appends **exactly one** receipt line to `<workspace>/journal.jsonl` before exiting — **on every exit path, including exit 2.** A gate that dies without a receipt is indistinguishable from a gate that was never run, which is risk-register entry #12.
- Every gate exposes `main(argv=None) -> int` and ends with `if __name__ == "__main__": sys.exit(main())`, so tests can call `main([...])` directly.
- The ONE verdict vocabulary (spec D3), these exact strings, everywhere:
  `"strong_apply" | "worth_applying" | "stretch" | "likely_screen_out" | "blocked"`
  Orthogonal refusal state (NOT a sixth level): `"insufficient_evidence"`.
  Human-facing zh labels: 强烈建议投 / 值得投 / 可以冲刺 / 大概率被筛掉 / 硬性阻断 / 证据不足—不出结论.
  discover-stage verdicts carry `provisional: true` and MUST NOT be copied into an assessment.
- Requirement-row enums (spec 5.2 step 6), these exact strings:
  `level: "required" | "preferred" | "unclear"`; `screening: "knockout" | "weighted" | "nice_to_have"`; `match: "strong" | "partial" | "gap" | "no_evidence"`; `recency: "current" | "recent" | "dated" | "undated"`; `effort: "quick" | "evening" | "multi_day" | "not_closable"`.
- Mock-interview bands (spec 5.4), deliberately unnumbered so they cannot be averaged:
  `"not_present" | "asserted" | "instanced" | "held_under_probe"`. Non-band flag: `"contradicted"`. Defect tags (closed set): `"UNSOURCED-FACT" | "OVER-CLAIM" | "CONTRADICTED" | "PROBE-COLLAPSE"`.
- Evidence block ids: `"CV-%03d"` and `"JD-%03d"`. Chunking: max 900 chars per block, max 80 blocks per source, split on blank lines or a newline preceding a bullet/number/CJK numeral, over-long paragraphs sentence-split on `[。.!?]`, drop chunks under 8 chars.
- `claims.yaml` row schema (append-only): `term` (str), `where` (str, e.g. `"tailored-profile.yaml:skills.infra"`), `source_kind` (`"profile-line" | "session-answer" | "fetched-artifact"`), `source_ref` (str), `session_date` (str, `YYYY-MM-DD`), `retracted` (str | null — null, or `"walk-back-YYYY-MM-DD"`).
- `JobListingEvidence` row schema (shortlist.yaml rows): `id, title, company, location, salary, url, source_site, source_id, extraction_method, retrieved_at, quality, verification, raw_text, why_matched, verdict, provisional`.
- Today is **2026-08-09**. Use it for filenames and any dated example. Never call an unstamped date helper in an example; show the literal date.
- **Git rules (the repo owner's standing instructions — violating these is a plan defect):** stage NAMED PATHS only; never `git add -A`, never `git add .`. **NEVER push** — commit locally only, no `git push` in any step. Do not pass `-c user.name` / `-c user.email`; the repo's config is already correct.
- **Testing discipline (spec §7).** Every check's tests must pin the QUIET case as hard as the firing case. A check that cries wolf on ordinary output is worse than no check, because readers learn to skip that line. A test that only imports a module proves the button exists, not that pressing it does anything — that is exactly how 51/51 green tests hid a renderer that could not produce a single letter PDF.
- **What `check_skill_lossless.py` does NOT prove (spec §12).** It measures whether the bytes still exist, not whether the content reaches context at the moment it is needed. A refactor can score a perfect lossless result and still degrade the skill, because the regression is in *when* content arrives, not *whether* it survives. Content preservation is necessary and nowhere near sufficient. The only real test of the layering change in Task 17 is re-running the end-to-end evals afterwards and reading what the outputs are missing. Never quote a size number or a lossless score as evidence of quality.

---

## File Structure

Everything created or modified by this plan. One responsibility per file.

**Migrated verbatim from `job-application` (Task 2), not otherwise touched:**

| Path | Responsibility |
|---|---|
| `README.md` | Repo-level orientation (migrated as-is). |
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
| `scripts/journal.py` | Append-only run journal + gate receipts. Imported by every gate. |
| `scripts/paths.py` | Every filesystem location the skill uses. The one place the workspace path shape is defined. |
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
| `scripts/enter_mode.py` | Writes the mode-entry record (mode file content hash) to `journal.jsonl`. The layer-1.5 backstop. |
| `scripts/check_apply.py` | Gate: composes all of the above plus the honest-stop classification and the interview brief. |
| `SKILL.md` | **Rewritten in Task 17.** Layer 1: everything whose omission nothing reports, carried verbatim, plus the self-check list. |
| `modes/apply.md` | **New in Task 17.** Layer 1.5: the apply pipeline (old Steps 0–7.5) and the `honest-stop.yaml` schema. |
| `scripts/tests/test_*.py` | One test module per script above. |

---

### Task 1: Preserve the uncommitted work in the `job-application` repo

`/Users/donghanglyu/.claude/skills/job-application` has ~1500 lines uncommitted since 2026-06-04. Migrating a dirty tree would either lose that work or fold it into one shapeless commit. Commit it there first, in coherent groups, staging named paths only.

**Files:**
- Modify (commit only, no content edits): `/Users/donghanglyu/.claude/skills/job-application/**` as listed below
- Test: `/Users/donghanglyu/.claude/skills/job-application/scripts` (existing suite, must be green before and after)

**Interfaces:**
- Consumes: nothing.
- Produces: a clean `git status` in the `job-application` repo, with `main` at a new tip that contains every file Task 2 will migrate.

- [ ] **Step 1: Confirm the suite is green before touching anything**
    Run: `cd /Users/donghanglyu/.claude/skills/job-application/scripts && python3 -m pytest tests -q`
    Expected: PASS — `51 passed`. If it is not 51 passed, STOP and report; do not commit a red tree.

- [ ] **Step 2: Confirm the working tree is exactly the expected set**
    Run: `cd /Users/donghanglyu/.claude/skills/job-application && git status --short`
    Expected output, exactly these 21 lines (order may vary):
    ```
     M README.md
     M SKILL.md
     M agents/ats-screener.md
     M agents/hiring-manager.md
     M assets/profile.example.yaml
     M references/cv-craft.md
     M references/gap-analysis.md
     M references/job-posting-extraction.md
     M references/motivation-letter.md
     M scripts/render_cv.py
     M scripts/render_letter.py
     M scripts/tests/test_render_cv.py
     M scripts/tests/test_render_letter.py
    ?? agents/recruiter-screener.md
    ?? references/candidate-situations.md
    ?? references/interview-prep.md
    ?? references/rirekisho.md
    ?? references/role-families.md
    ?? references/structured-applications.md
    ?? scripts/render_rirekisho.py
    ?? scripts/tests/test_render_rirekisho.py
    ```
    If anything else appears, STOP and report it — an unexpected path means someone else edited this tree and you would be committing their work blind.

- [ ] **Step 3: Commit group 1 — renderers and their tests**
    ```bash
    cd /Users/donghanglyu/.claude/skills/job-application
    git add scripts/render_cv.py scripts/render_letter.py \
            scripts/tests/test_render_cv.py scripts/tests/test_render_letter.py \
            assets/profile.example.yaml
    git commit -m "feat(render): section ordering, CJK preamble, links, personal-data interlock, exec sections

Adds meta.section_order/meta.headings resolution, the xeCJK preamble with a
cross-platform font fallback, friendly link labels in all three renderers, the
Cluster-1 personal-data suppression, and native achievements/board sections.
Uncommitted since 2026-06-04; landed here so the history survives migration."
    ```

- [ ] **Step 4: Commit group 2 — the Japan rirekisho fork**
    ```bash
    cd /Users/donghanglyu/.claude/skills/job-application
    git add scripts/render_rirekisho.py scripts/tests/test_render_rirekisho.py references/rirekisho.md
    git commit -m "feat(rirekisho): Japanese 履歴書 renderer, reference and tests

The rirekisho is a form, not a CV: personal-data block, 学歴・職歴 table,
免許・資格 table, 志望の動機 box. docx only — the authentic form is exported to
PDF from Word/LibreOffice rather than routed through LaTeX."
    ```

- [ ] **Step 5: Commit group 3 — the three judge personas**
    ```bash
    cd /Users/donghanglyu/.claude/skills/job-application
    git add agents/ats-screener.md agents/recruiter-screener.md agents/hiring-manager.md
    git commit -m "feat(judges): add the recruiter/HR screener as the third judge

Three lenses, deliberately distinct: ATS = literal findability, Recruiter =
fast/broad/logistics, Hiring Manager = deep fit. The recruiter's must_have_fit
>= 3 vs the hiring manager's >= 4 asymmetry is what makes 'honest stretch'
statable at all."
    ```

- [ ] **Step 6: Commit group 4 — the craft references**
    ```bash
    cd /Users/donghanglyu/.claude/skills/job-application
    git add references/candidate-situations.md references/cv-craft.md \
            references/gap-analysis.md references/interview-prep.md \
            references/job-posting-extraction.md references/motivation-letter.md \
            references/role-families.md references/structured-applications.md
    git commit -m "docs(references): candidate situations, role families, structured applications, interview prep

Plus the cv-craft/gap-analysis/job-posting-extraction/motivation-letter updates:
the quantification ladder, the qualitative-evidence rule, the NOT-ALLOWED table,
the disqualifier wall, the FIT SNAPSHOT template and its required disclaimer."
    ```

- [ ] **Step 7: Commit group 5 — the orchestrator and README**
    ```bash
    cd /Users/donghanglyu/.claude/skills/job-application
    git add SKILL.md README.md
    git commit -m "docs(skill): three-judge loop, workspace convention, fast path, Step 7.5 brief

SKILL.md's diff spans every group above, so it lands last and whole rather than
being split with an interactive add (not available in this environment)."
    ```

- [ ] **Step 8: Verify the tree is clean and still green**
    Run:
    ```bash
    cd /Users/donghanglyu/.claude/skills/job-application && git status --short && \
      git log --oneline -6 && cd scripts && python3 -m pytest tests -q
    ```
    Expected: `git status --short` prints nothing; the log shows the five new commits on top of `141bef6`; pytest reports `51 passed`.
    Do **not** push. This repo has no remote and must not gain one.

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
    import os
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


    def receipt(workspace, gate: str, input_hashes: dict, verdict: str,
                findings=None) -> dict:
        """Build, journal and return one gate receipt.

        `mode` comes from the JOB_HUNT_MODE environment variable (default "apply")
        because the gate signature is fixed by the shared contract and does not
        carry it; mode entry sets it. It is recorded rather than derived so a
        receipt read months later still says which mode was running.
        """
        record = {
            "ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "mode": os.environ.get("JOB_HUNT_MODE", "apply"),
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
            if not isinstance(rec, dict) or rec.get("action") != "gate":
                continue
            if gate is None or rec.get("gate") == gate:
                out.append(rec)
        return out
    ```

- [ ] **Step 4: Run test to verify it passes**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_journal.py -q`
    Expected: PASS — `8 passed`

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
  - `slugify(text: str) -> str`
  - `profile_dir(name: str) -> pathlib.Path`
  - `master_profile(name: str) -> pathlib.Path` (`<profile_dir>/profile.yaml`)
  - `search_prefs(name: str) -> pathlib.Path` (`<profile_dir>/search-preferences.yaml`)
  - `answer_bank(name: str) -> pathlib.Path` (`<profile_dir>/answer-bank.md`)
  - `search_dir(name: str, slug: str) -> pathlib.Path` (`<profile_dir>/searches/<slug>`)
  - `workspace(name: str, company: str, role: str, date: str) -> pathlib.Path` (`<profile_dir>/applications/<company>-<role>-<YYYY-MM-DD>`)

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
    ```

- [ ] **Step 4: Run test to verify it passes**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests/test_paths.py -q`
    Expected: PASS — `12 passed`

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

### Task 5: `scripts/check_skill_lossless.py` — prove the migration moved content instead of deleting it

**Read this before writing it, and carry the warning into the docstring:** this check measures whether the bytes still exist, not whether the content reaches context at the moment it is needed. A refactor can score a perfect lossless result and still degrade the skill, because the regression is in *when* content arrives. The only real test of Task 17's layering change is re-running the end-to-end evals and reading what the outputs are missing.

**Files:**
- Create: `scripts/check_skill_lossless.py`
- Modify: `scripts/lossless-allowlist.json` (created in Task 2; unchanged content, now consumed)
- Test: `scripts/tests/test_check_skill_lossless.py`

**Interfaces:**
- Consumes: tag `job-application-baseline` from Task 2; `scripts/lossless-allowlist.json`.
- Produces:
  - `normalize(text: str) -> str`
  - `line_key(normalized: str) -> str` (16-hex-char sha1 prefix)
  - `baseline_docs(spec: str, repo: pathlib.Path) -> dict[str, str]` (relpath → text)
  - `build_corpus(skill_dir: pathlib.Path) -> tuple[str, list[pathlib.Path]]`
  - `main(argv=None) -> int`
  - CI command: `python3 scripts/check_skill_lossless.py --baseline job-application-baseline`

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
        not something a skill trigger can reach."""
        base = _tree(tmp_path / "base", {"SKILL.md": f"{LINE}\n"})
        new = _tree(tmp_path / "new", {"SKILL.md": "# New\n",
                                       "docs/superpowers/specs/design.md": LINE})
        assert csl.main(["--baseline", str(base), "--skill-dir", str(new)]) == 1
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
        python3 scripts/check_skill_lossless.py --baseline job-application-baseline

        # against a tree on disk
        python3 scripts/check_skill_lossless.py --baseline /Users/x/.claude/skills/job-application

    Exit 0 = every baseline line accounted for. Exit 1 = content was lost, or the
    allowlist names a file that is still present.

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
    from pathlib import Path

    # Lines shorter than this once normalized are structural noise — bare list
    # markers, `---` rules, lone code fences, one-word headings. They carry no rule
    # that can be lost, and checking them fails every time a heading is renamed.
    DEFAULT_MIN_CHARS = 25

    CORPUS_SUFFIXES = (".md", ".yaml")
    # Everything a skill trigger can eventually reach. `docs/` is deliberately out:
    # a line that survives only in the design doc has not survived.
    CORPUS_DIRS = (".", "modes", "references", "agents", "assets")

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


    def baseline_docs(spec: str, repo: Path) -> dict:
        """{relpath: text} for the baseline tree. `spec` is a git ref or a directory."""
        p = Path(spec)
        if p.is_dir():
            out = {}
            for sub in CORPUS_DIRS:
                d = p / sub if sub != "." else p
                if not d.is_dir():
                    continue
                for f in sorted(d.rglob("*")):
                    if f.is_file() and f.suffix in CORPUS_SUFFIXES:
                        out[str(f.relative_to(p))] = f.read_text(encoding="utf-8", errors="replace")
            return out
        listing = subprocess.run(["git", "ls-tree", "-r", "--name-only", spec],
                                 cwd=repo, capture_output=True, text=True)
        if listing.returncode != 0:
            sys.exit(f"cannot read baseline {spec!r}: {listing.stderr.strip()}")
        out = {}
        for rel in listing.stdout.split("\n"):
            rel = rel.strip()
            if not rel or not rel.endswith(CORPUS_SUFFIXES) or rel.startswith("docs/"):
                continue
            blob = subprocess.run(["git", "show", f"{spec}:{rel}"],
                                  cwd=repo, capture_output=True, text=True)
            if blob.returncode == 0:
                out[rel] = blob.stdout
        return out


    def build_corpus(skill_dir: Path) -> tuple:
        files = []
        for sub in CORPUS_DIRS:
            d = skill_dir / sub if sub != "." else skill_dir
            if not d.is_dir():
                continue
            files.extend(sorted(f for f in d.rglob("*")
                                if f.is_file() and f.suffix in CORPUS_SUFFIXES))
        files = sorted(set(files))
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

        skill_dir = Path(args.skill_dir).resolve() if args.skill_dir \
            else Path(__file__).resolve().parent.parent
        repo = Path(args.repo).resolve() if args.repo else (
            _find_repo(Path(__file__).resolve().parent) or skill_dir)
        allow_path = Path(args.allow) if args.allow else skill_dir / "scripts" / "lossless-allowlist.json"

        allow, deleted_files = {}, {}
        if allow_path.exists():
            data = json.loads(allow_path.read_text(encoding="utf-8"))
            allow = data.get("waived") or {}
            deleted_files = data.get("deleted_files") or {}

        docs = baseline_docs(args.baseline, repo)
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
    Expected: PASS — `10 passed`

- [ ] **Step 5: Run it for real against the migration**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 scripts/check_skill_lossless.py --baseline job-application-baseline`
    Expected: exit 0 and a line starting `LOSSLESS:` — right now the tree is byte-identical to the baseline apart from the two `.tex` files, which are not in `CORPUS_SUFFIXES` and are covered by `deleted_files`. If it reports `CONTENT LOST` at this point, the merge in Task 2 lost something; stop and investigate rather than waiving.

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

### Task 6: Fix the LaTeX engine bug with one shared `_engine_cmd()`

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
    Replace `test_letter_pdf_degrades_without_engine` in `scripts/tests/test_render_letter.py` — keep it, and add the regression the suite was missing:
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
    Expected: PASS — `51 passed` plus the 6 new tests (`57 passed`).

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

### Task 7: Fix the Cluster-1 personal-data interlock and make it audible

**The live defect.** `references/cv-craft.md:121` claims the renderer makes a leak physically impossible. It does not: `_is_cluster1` does an exact lowercase token lookup, and DOB renders through for `United States of America`, `US (Boston)`, `Los Angeles, CA`, `U.K.` and `remote (US)` — all measured today. The eval-0 scenario input literally reads `TARGET MARKET: United States (Los Angeles, CA)`.

**Two changes, and the second matters as much as the first.** Normalising the match closes the five known spellings. But an unknown market with personal data present must also stop being silent — and it must not cry wolf on the many perfectly ordinary EU/Asia markets where a photo is a convention. So the resolver returns a cluster (1, 2 or 3) or `None`, and only `None` warns.

**Files:**
- Modify: `scripts/render_cv.py` (replace `_CLUSTER1_MARKETS` and `_is_cluster1` at lines 346–360; add the warning in `personal_items` / `photo_path`)
- Test: `scripts/tests/test_render_cv.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `render_cv.resolve_cluster(market) -> int | None` — 1 = US/CA/UK/IE/AU/NZ, 2 = EU/EEA, 3 = East & SE Asia, None = not recognised.
  - `render_cv._is_cluster1(profile) -> bool` (kept, now `resolve_cluster(...) == 1`).
  - `render_cv.protected_fields(profile) -> list[str]` — names of the protected fields actually present, e.g. `["contact.personal.date_of_birth", "meta.photo"]`.

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


    def _warn_unknown_market(profile):
        """Loud when the market is unrecognised AND protected data is present.

        cv-craft.md claims a mis-tailored profile 'physically cannot leak protected
        data onto a US/UK CV'. It could, for five measured spellings. The matcher
        above closes those; this closes the class — an unrecognised market is not
        evidence that rendering a DOB is safe, and silence there is what made the
        original claim false.
        """
        if resolve_cluster((profile.get("meta") or {}).get("target_market")) is not None:
            return
        fields = protected_fields(profile)
        if not fields:
            return
        market = (profile.get("meta") or {}).get("target_market")
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
    Add `import unicodedata` to `render_cv.py`'s module imports if absent. Then call the warning once per render entry point — in `personal_items`, immediately before the `_is_cluster1` check:
    ```python
    def personal_items(profile):
        ...docstring unchanged...
        _warn_unknown_market(profile)
        if _is_cluster1(profile):
            return
    ```

- [ ] **Step 4: Run test to verify it passes**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests -q`
    Expected: PASS — all previous tests plus the new parametrized ones (`18 + 16 + 5 + 2` new cases).

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

### Task 8: `scripts/check_personal_data.py` — the interlock as a gate with a receipt

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
        assert len(receipts) == 1 and receipts[0]["verdict"] == "error"
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
        path = pathlib.Path(args.profile) if args.profile else ws / "tailored-profile.yaml"
        if not path.exists():
            journal.receipt(ws, GATE, {}, "error", [f"MISSING_INPUT: {path}"])
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

### Task 9: `scripts/rounds.py` and `scripts/parse_verdicts.py` — the parser all three agents already assume

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
    ```python
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
        assert len(receipts) == 2 and receipts[-1]["verdict"] == "error"
    ```

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
        paths = {"ats": pathlib.Path(args.ats),
                 "recruiter": pathlib.Path(args.recruiter),
                 "hiring_manager": pathlib.Path(args.hiring_manager)}
        for name, p in paths.items():
            if not p.exists():
                journal.receipt(ws, GATE, {}, "error", [f"MISSING_INPUT: {p}"])
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

### Task 10: `scripts/check_render_freshness.py` — void a round judged on stale files

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


    def test_each_run_leaves_exactly_one_receipt(tmp_path):
        ws = _ws(tmp_path)
        crf.main(["--workspace", str(ws), "--round", "1", "--record", str(ws / "cv.md")])
        crf.main(["--workspace", str(ws), "--round", "1"])
        verdicts = [r["verdict"] for r in journal.read_receipts(ws, "check_render_freshness")]
        assert verdicts == ["recorded", "pass"]
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

        if args.record is not None:
            hashes = {}
            for raw in args.record:
                p = pathlib.Path(raw)
                if not p.exists():
                    journal.receipt(ws, GATE, {}, "error", [f"MISSING_INPUT: {p}"])
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
            journal.receipt(ws, GATE, {}, "error",
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

### Task 11: `scripts/check_claims.py` — every new term traces to a source, and the master was not touched

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


    def test_each_run_leaves_exactly_one_receipt(tmp_path):
        ws, _ = _setup(tmp_path, MASTER)
        check_claims.main(["--workspace", str(ws)])
        verdicts = [r["verdict"] for r in journal.read_receipts(ws, "check_claims")]
        assert verdicts == ["recorded", "pass"]
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
    CLAIM_KEYS = ("term", "where", "source_kind", "source_ref", "session_date")
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
                if not str(row.get(key) or "").strip():
                    findings.append(f"BAD_CLAIM_ROW: claims.yaml[{i}] is missing required "
                                    f"key {key!r}")
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
        fp_path = ws / FINGERPRINT

        if args.record:
            if not args.master or not pathlib.Path(args.master).exists():
                journal.receipt(ws, GATE, {}, "error",
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
            journal.receipt(ws, GATE, {}, "error", [f"{code}: {ws / missing}"])
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
    Expected: PASS — `10 passed`

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

### Task 12: `scripts/lint_cv.py` — the mechanically decidable slice of the quality pass

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
    - Led the migration of 40 clinical protocols onto the new solver.
    - Led a two-person team through the vendor integration with Philips.
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
        ordinary writing does not trip it."""
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


    def test_each_run_leaves_exactly_one_receipt(tmp_path):
        ws = _cv(tmp_path)
        lint_cv.main(["--workspace", str(ws)])
        assert [r["verdict"] for r in journal.read_receipts(ws, "lint_cv")] == ["pass"]
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
        path = pathlib.Path(args.cv) if args.cv else ws / "cv.md"
        if not path.exists():
            journal.receipt(ws, GATE, {}, "error", [f"MISSING_INPUT: {path}"])
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

### Task 13: `scripts/check_letter.py` — the letter constraints the renderer will not enforce

`render_letter.py` passes each `body` string straight into Markdown, docx and LaTeX with no stripping, so `**bold**` prints four asterisks on the PDF and a sender name in `closing` prints twice. This is the same failure class as a format string rendered raw onto a slide: a formatting contract documented only in prose, whose violation is rendered literally.

**A note on `posting.yaml`.** The extraction schema has no `company` field today, so the letter's recipient cannot be verified against anything. This gate therefore *requires* one and reports `NO_COMPANY_IN_POSTING` when it is absent, rather than skipping the check quietly. Task 17 adds `company` to the extraction field table in SKILL.md.

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


    def _letter(body=None, **over):
        d = {"sender": {"name": "Test User", "email": "t@x.com", "location": "Delft"},
             "recipient": {"name": "Hiring Team", "company": "Acme Medical Systems B.V.",
                           "location": "Eindhoven"},
             "date": "2026-08-09",
             "salutation": "Geachte heer/mevrouw,",
             "body": body if body is not None else [
                 PARA + "I am applying for the Senior Reconstruction Engineer role.",
                 PARA, PARA],
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
        body[2] = "- MRI reconstruction\n- GPU solvers"
        ws = _ws(tmp_path, _letter(body=body))
        assert check_letter.main(["--workspace", str(ws)]) == 1
        assert "MARKDOWN_IN_BODY: body[2]" in capsys.readouterr().out


    def test_word_count_below_the_floor_is_caught(tmp_path, capsys):
        ws = _ws(tmp_path, _letter(body=["Short.", "Also short.", "Still short."]))
        assert check_letter.main(["--workspace", str(ws)]) == 1
        out = capsys.readouterr().out
        assert "WORD_COUNT" in out and "250" in out and "400" in out


    def test_word_count_above_the_ceiling_is_caught(tmp_path, capsys):
        ws = _ws(tmp_path, _letter(body=[PARA * 3, PARA * 3, PARA * 3]))
        assert check_letter.main(["--workspace", str(ws)]) == 1
        assert "WORD_COUNT" in capsys.readouterr().out


    def test_paragraph_count_outside_three_to_five_is_caught(tmp_path, capsys):
        ws = _ws(tmp_path, _letter(body=[PARA * 2, PARA * 2]))
        assert check_letter.main(["--workspace", str(ws)]) == 1
        assert "PARA_COUNT" in capsys.readouterr().out


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
        ws = _ws(tmp_path, _letter(body=[PARA, PARA, PARA]))
        assert check_letter.main(["--workspace", str(ws)]) == 1
        out = capsys.readouterr().out
        assert "ROLE_NOT_NAMED" in out and "Senior Reconstruction Engineer" in out


    def test_a_posting_without_a_company_field_fails_loudly(tmp_path, capsys):
        ws = _ws(tmp_path, _letter(), posting={"role_title": "Senior Reconstruction Engineer"})
        assert check_letter.main(["--workspace", str(ws)]) == 1
        assert "NO_COMPANY_IN_POSTING" in capsys.readouterr().out


    def test_a_missing_posting_is_exit_2(tmp_path, capsys):
        ws = _ws(tmp_path, _letter(), posting=None)
        assert check_letter.main(["--workspace", str(ws)]) == 2
        assert "posting.yaml" in capsys.readouterr().err


    def test_each_run_leaves_exactly_one_receipt(tmp_path):
        ws = _ws(tmp_path, _letter())
        check_letter.main(["--workspace", str(ws)])
        assert [r["verdict"] for r in journal.read_receipts(ws, "check_letter")] == ["pass"]
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
    WORD_MIN, WORD_MAX = 250, 400
    PARA_MIN, PARA_MAX = 3, 5

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
                       f"{PARA_MIN}–{PARA_MAX} is the range")

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
        lp = pathlib.Path(args.letter) if args.letter else ws / "letter.yaml"
        pp = pathlib.Path(args.posting) if args.posting else ws / "posting.yaml"
        for p in (lp, pp):
            if not p.exists():
                journal.receipt(ws, GATE, {}, "error", [f"MISSING_INPUT: {p}"])
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

### Task 14: `render_cv.py` — warn on unknown `meta.headings` / `meta.section_order` keys

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

### Task 15: `render_rirekisho.py` — an unparseable date must not render as a blank cell

Measured: `_ym('Sep 2023')`, `_ym('September 2023')` and `_ym('03/2021')` all return `('', '')`, so those rows render with blank 年 and 月 — a structurally invalid 履歴書 that renders, saves and passes pytest. The rirekisho is explicitly routed away from all three judges, so nothing else looks at it.

**Files:**
- Modify: `scripts/render_rirekisho.py` (`gakureki_shokureki_rows`, `licenses_rows`, `main`)
- Test: `scripts/tests/test_render_rirekisho.py`

**Interfaces:**
- Consumes: `render_cv.load_profile`, `render_cv._is_current` (existing).
- Produces:
  - `gakureki_shokureki_rows(profile, problems=None)` and `licenses_rows(profile, problems=None)` — unchanged return value; when `problems` is a list, unparseable dates are appended to it as strings.
  - `date_problems(profile) -> tuple[list[str], list[str]]` — `(fatal, warnings)`; fatal = 学歴・職歴 dates, warnings = 免許・資格 dates.
  - `main` gains `--allow-blank-dates`.

- [ ] **Step 1: Write the failing test**
    Append to `scripts/tests/test_render_rirekisho.py`:
    ```python
    ACCEPTED = ["2023-09", "2021", "2023年9月", "2023/09"]
    REJECTED = ["Sep 2023", "September 2023", "03/2021", "", None]


    @pytest.mark.parametrize("value", ACCEPTED)
    def test_accepted_date_formats_produce_no_problem(jp_profile, value):
        p = dict(jp_profile)
        p["education"] = [{"institution": "○○大学", "degree": "修士",
                           "start": value, "end": "2023-03"}]
        fatal, warnings = rr.date_problems(p)
        assert fatal == [] and warnings == []


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
        fatal, warnings = rr.date_problems(jp_profile)
        assert fatal == [] and warnings == []


    def test_an_undated_certification_warns_but_is_not_fatal(jp_profile):
        p = dict(jp_profile)
        p["certifications"] = ["基本情報技術者試験 合格 (2021)"]
        fatal, warnings = rr.date_problems(p)
        assert fatal == []
        assert len(warnings) == 1 and "基本情報技術者試験" in warnings[0]


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
        import yaml
        src = tmp_path / "profile.yaml"
        src.write_text(yaml.safe_dump(jp_profile, allow_unicode=True), encoding="utf-8")
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
    (the `end` read for a current entry stays unchecked — 現在に至る legitimately has no year, and flagging it would fire on every employed candidate). Change `licenses_rows(profile)` to `licenses_rows(profile, problems=None)` and use `_checked_ym(cert, f"免許・資格 {cert}", problems)`. Then add:
    ```python
    def date_problems(profile):
        """(fatal, warnings). 学歴・職歴 rows must carry a year — the table is the
        form. A certification without one is a common and tolerable omission, so it
        warns instead."""
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
    Expected: PASS — the whole suite. The existing rirekisho fixtures use `2020-04` / `2023-04` / `present`, so they stay silent.

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

### Task 16: `scripts/enter_mode.py` and `scripts/check_apply.py` — the composing gate

`check_apply.py` is where the mode's completion claim becomes checkable. It requires every upstream gate's receipt (a skipped script produces no output, which looks exactly like a clean one), the round's combined verdict *or* an honest-stop record classified as **poorly built** vs **honest stretch** (both emit the identical machine signal, and a stretch candidate told "failed" abandons an application they should have sent), the interview brief, and the mode-entry record that makes `modes/apply.md` a layer-1.5 file rather than an optional one.

**Files:**
- Create: `scripts/enter_mode.py`, `scripts/check_apply.py`
- Test: `scripts/tests/test_check_apply.py`

**Interfaces:**
- Consumes: `journal.append`, `journal.receipt`, `journal.read_receipts`, `journal.sha256_file`; `rounds.load_round`, `rounds.round_path`.
- Produces:
  - `enter_mode.mode_file(skill_root, mode) -> pathlib.Path` (`<skill_root>/modes/<mode>.md`)
  - `enter_mode.latest_mode_entry(workspace, mode) -> dict | None`
  - `enter_mode.main(argv=None) -> int`. CLI: `python3 scripts/enter_mode.py --workspace W --mode apply [--skill-root PATH]`. Writes `{"ts","action":"mode_entry","mode","mode_file","mode_file_sha256"}`.
  - `check_apply.main(argv=None) -> int`. CLI: `python3 scripts/check_apply.py --workspace W [--skill-root PATH]`. Gate name: `check_apply`. Finding codes: `NO_MODE_ENTRY`, `MODE_FILE_CHANGED`, `MISSING_RECEIPT`, `UPSTREAM_FAILED`, `NO_ROUND`, `NO_PASS_NO_STOP`, `BAD_STOP_CLASSIFICATION`, `BAD_STOP_VERDICT`, `INCOMPLETE_STOP`, `NO_BRIEF`.
  - The `honest-stop.yaml` schema this gate requires (defined in `modes/apply.md`, Task 17): `classification` ∈ `poorly_built | honest_stretch`; `verdict` ∈ the five-verdict vocabulary; `reason` (non-empty string); `evidence` (non-empty list of strings — the judge findings the classification rests on).

- [ ] **Step 1: Write the failing test**
    Create `scripts/tests/test_check_apply.py`:
    ```python
    import pathlib
    import sys

    import yaml

    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    import check_apply
    import enter_mode
    import journal
    import rounds

    REQUIRED = ("check_personal_data", "check_claims", "check_render_freshness", "lint_cv")


    def _skill_root(tmp_path, body="# Apply mode\n\nartifact: honest-stop.yaml\n"):
        root = tmp_path / "skill"
        (root / "modes").mkdir(parents=True, exist_ok=True)
        (root / "modes" / "apply.md").write_text(body, encoding="utf-8")
        return root


    def _good_workspace(tmp_path, root):
        ws = tmp_path / "acme-engineer-2026-08-09"
        ws.mkdir(parents=True, exist_ok=True)
        enter_mode.main(["--workspace", str(ws), "--mode", "apply", "--skill-root", str(root)])
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


    def test_it_leaves_exactly_one_receipt(tmp_path):
        root = _skill_root(tmp_path)
        ws = _good_workspace(tmp_path, root)
        check_apply.main(_argv(ws, root))
        assert [r["verdict"] for r in journal.read_receipts(ws, "check_apply")] == ["pass"]
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

    MODES = ("discover", "assess", "apply", "interview")


    def mode_file(skill_root, mode: str) -> pathlib.Path:
        return pathlib.Path(skill_root) / "modes" / f"{mode}.md"


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
        root = pathlib.Path(args.skill_root) if args.skill_root \
            else pathlib.Path(__file__).resolve().parent.parent
        path = mode_file(root, args.mode)
        if not path.exists():
            print(f"cannot enter mode {args.mode}: {path} does not exist", file=sys.stderr)
            return 2
        journal.append(pathlib.Path(args.workspace), {
            "ts": datetime.datetime.now(datetime.timezone.utc)
                          .strftime("%Y-%m-%dT%H:%M:%SZ"),
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

    Exit 0 = the package may be delivered. Exit 1 = findings. Exit 2 = no workspace.
    """
    from __future__ import annotations

    import argparse
    import pathlib
    import sys

    import yaml

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import enter_mode
    import journal
    import rounds

    GATE = "check_apply"
    REQUIRED_GATES = ("check_personal_data", "check_claims", "check_render_freshness",
                      "lint_cv")
    CLASSIFICATIONS = ("poorly_built", "honest_stretch")
    VERDICTS = ("strong_apply", "worth_applying", "stretch", "likely_screen_out", "blocked")
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
        root = pathlib.Path(args.skill_root) if args.skill_root \
            else pathlib.Path(__file__).resolve().parent.parent
        if not ws.is_dir():
            journal.receipt(ws, GATE, {}, "error", [f"MISSING_INPUT: {ws}"])
            print(f"cannot run {GATE}: workspace {ws} does not exist", file=sys.stderr)
            return 2

        findings = []

        # ── the layer-1.5 backstop ────────────────────────────────────────────
        entry = enter_mode.latest_mode_entry(ws, "apply")
        mode_path = enter_mode.mode_file(root, "apply")
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
                findings.append(f"MISSING_RECEIPT: no journal.jsonl receipt for {gate} — "
                                f"the gate was never run, and a skipped gate looks exactly "
                                f"like a clean one")
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
    Expected: PASS — `16 passed`

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

### Task 17: Restructure into `SKILL.md` (layer 1) + `modes/apply.md` (layer 1.5)

**The discipline for this task, and it is the whole task: moving a line is allowed, changing it is not.** Decide the boundaries first, then move the lines byte-for-byte. "Split it into references" quietly becomes "rewrite and condense": the file shrinks, the commit says zero information loss, and operational rules are gone — invisible in review, because the diff is thousands of lines and every removed line plausibly landed somewhere. This skill has already shipped one such condensation defect: `SKILL.md:71`'s extraction field list silently dropped `salary_range` and `application_type`, and `application_type: structured` is the *only* signal that routes to the supporting-statement branch.

**What layer 1 must hold, and why.** Not "is this needed every time" but "if the model skips this, does anything report it?" For every item below the answer is *nothing*. Three of them have measured evidence in this skill's own history: the Cluster-1 interlock leaked for five plausible market strings while its documentation claimed it could not; a run recorded skipping `references/motivation-letter.md` and then filed a finding that the skill lacked guidance which was inside the file it declined to read; and the old skill has **no self-check list at all** — `grep -n "checklist\|self-check" SKILL.md` matches one line, and it is prose about JD requirements. The third backstop form the owner's own doctrine names simply does not exist in this skill.

**Files:**
- Modify: `SKILL.md` (rewritten as layer 1)
- Create: `modes/apply.md` (layer 1.5)
- Create: `scripts/tests/required_inline.json`, `scripts/tests/test_skill_structure.py`

**Interfaces:**
- Consumes: `enter_mode.MODES`; `check_apply.CLASSIFICATIONS`, `check_apply.VERDICTS` (the `honest-stop.yaml` field values `modes/apply.md` must define).
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
        section = _self_check_section()
        skip = {"journal.py", "paths.py", "rounds.py"}      # imported, never invoked
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


    def test_every_mode_named_in_skill_md_has_a_file_or_is_marked_unbuilt():
        text = SKILL.read_text(encoding="utf-8")
        for mode in enter_mode.MODES:
            if (ROOT / "modes" / f"{mode}.md").exists():
                continue
            assert re.search(rf"{mode}.{{0,80}}not yet", text, re.I | re.S), \
                f"SKILL.md names the {mode} mode but there is no modes/{mode}.md and no " \
                f"'not yet' marker — a mode that does not exist must not read as available"
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
    ## On entering this mode

    Record the entry before doing anything else — `check_apply.py` requires it, and the
    hash is what proves the file you read is the file on disk:

    ```bash
    python3 scripts/enter_mode.py --workspace <workspace> --mode apply
    python3 scripts/check_claims.py --workspace <workspace> \
        --master ~/.claude/job-profiles/<name>/profile.yaml --record
    ```

    ## Gate commands, in the order they run

    ```bash
    # after tailoring, before dispatching the judges
    python3 scripts/check_personal_data.py --workspace <ws>
    python3 scripts/check_claims.py --workspace <ws>
    python3 scripts/lint_cv.py --workspace <ws>
    python3 scripts/check_letter.py --workspace <ws>          # only if letter.yaml exists
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
    | frontmatter | `name: job-hunt`; description carried from the baseline with the name changed | `SKILL.md:1-14` |
    | The load-bearing rule | HONEST REFRAMING ONLY, whole paragraph | `SKILL.md:22` |
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
    | Extraction field table | the **complete** table including `salary_range` and `application_type` — **plus a new `company` row** (the exact public employer name; `check_letter.py` verifies the letter's recipient against it and the workspace directory is named from it) | `references/job-posting-extraction.md:20-33` |
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
    | **Gates** (new) | the table below | new |
    | **Self-check** (new) | the list below | new |

    The gate table:

    | Gate | Script | Fires on |
    |---|---|---|
    | Personal data | `scripts/check_personal_data.py` | protected fields on a Cluster-1 target, or an unrecognised market |
    | Claim provenance | `scripts/check_claims.py` | a term with no source; a mutated master profile |
    | Verdict parsing | `scripts/parse_verdicts.py` | anything that is not exactly PASS/REJECT; a non-unanimous round |
    | Render freshness | `scripts/check_render_freshness.py` | a judge that read a file the disk no longer has |
    | CV lint | `scripts/lint_cv.py` | clichés, weak openers, over-long bullets, repeated verbs |
    | Letter | `scripts/check_letter.py` | markdown in a body string, length, duplicated name, wrong company/role |
    | Apply completion | `scripts/check_apply.py` | a missing receipt, an unclassified stop, a missing brief |
    | Migration losslessness | `scripts/check_skill_lossless.py` | a baseline line that exists nowhere in this tree |

    **No mode may claim success while `journal.jsonl` lacks a receipt for its gates.** A skipped script produces no output, and no output is exactly what a clean run looks like.

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

    Ran, with a receipt in `journal.jsonl`:
    - [ ] `scripts/enter_mode.py` (mode entry recorded)
    - [ ] `scripts/render_cv.py` — and `scripts/render_letter.py` / `scripts/render_rirekisho.py`
          if applicable
    - [ ] `scripts/check_personal_data.py`
    - [ ] `scripts/check_claims.py`
    - [ ] `scripts/check_render_freshness.py` (recorded before dispatch, verified after)
    - [ ] `scripts/parse_verdicts.py`
    - [ ] `scripts/lint_cv.py`
    - [ ] `scripts/check_letter.py` (if a letter was produced)
    - [ ] `scripts/check_apply.py`
    - [ ] `scripts/check_skill_lossless.py` (only when this skill's own files changed)

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
    Expected: PASS — 34 anchor cases plus 9 structural cases.

- [ ] **Step 8: Prove the restructure lost nothing**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 scripts/check_skill_lossless.py --baseline job-application-baseline`
    Expected: exit 0, `LOSSLESS: …`. If a line is reported lost, it was condensed rather than moved — put it back. Add an allowlist waiver only for a line you can write a reason for, and remember the FIT SNAPSHOT disclaimer's percentage wording is **not** rewritten in this plan: it is carried verbatim here and revised in the assess-mode plan, in a separate small commit, so this diff never contains a rewrite.

- [ ] **Step 9: Run the whole suite**
    Run: `cd /Users/donghanglyu/code_project/job-hunt && python3 -m pytest scripts/tests -q`
    Expected: PASS — everything.

- [ ] **Step 10: Commit**
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add SKILL.md modes/apply.md scripts/tests/required_inline.json \
            scripts/tests/test_skill_structure.py
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
letter's recipient against it and the workspace directory is named from it."
    ```

---

### Task 18: Install into both runtimes and smoke-test them

One repo, two symlinks — the same shape as `slide-maker`, which is already symlinked into `~/.claude/skills` from `~/code_project/slides_maker`. One copy of the doctrine, so it cannot drift between runtimes. The old `job-application` directory stays on disk as an archive but is **not** symlinked: two skills whose descriptions overlap fight for the trigger, and the user then has to know which one to invoke.

**Files:**
- Create: `~/.claude/skills/job-hunt` → `/Users/donghanglyu/code_project/job-hunt` (symlink)
- Create: `~/.codex/skills/job-hunt` → `/Users/donghanglyu/code_project/job-hunt` (symlink)
- Test: `scripts/tests/test_install.py`

**Interfaces:**
- Consumes: `SKILL.md`, `modes/apply.md`, `scripts/*.py` from Task 17.
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
    python3 ~/.claude/skills/job-hunt/scripts/check_apply.py --workspace /tmp/jh-smoke-does-not-exist; echo "exit=$?"
    python3 ~/.codex/skills/job-hunt/scripts/lint_cv.py --workspace /tmp/jh-smoke-does-not-exist; echo "exit=$?"
    ```
    Expected: both `head` calls print `---` / `name: job-hunt` / `description: >-`; both scripts print a `cannot run …` message to stderr and `exit=2` — which proves the module imports resolved through the symlink (an unresolvable import would be a traceback, not an orderly exit 2).

- [ ] **Step 6: Full suite and a final losslessness check**
    Run:
    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    python3 -m pytest scripts/tests -q
    python3 scripts/check_skill_lossless.py --baseline job-application-baseline
    git status --short
    ```
    Expected: all tests pass; `LOSSLESS: …` with exit 0; `git status --short` shows only `scripts/tests/test_install.py` as untracked.

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

- **The `discover`, `assess` and `interview` modes.** SKILL.md names them and says they are not yet built; `modes/` holds only `apply.md`.
- **The §12 flagged rewrite.** The FIT SNAPSHOT's required disclaimer talks about keyword-coverage *percentages*, and the new assess mode stops emitting those. Carrying it verbatim here is correct — this plan's job is that `job-hunt` does everything `job-application` does. The rewrite belongs to the assess-mode plan, as a separate small readable commit, recorded in the lossless allowlist by name so it is a decision rather than a casualty.
- **The remaining P1/P2 checks** named in the spec: `consistency.py`, `check_mock.py`, `check_shortlist.py`, `check_conventions.py`, `check_evidence_refs.py`, `lint_no_prediction.py`, `check_no_write.py`, `check_opencli_result.py`, `count_coverage.py`, `check_pages.py`, `check_word_limits.py`.
- **The eval rebuild.** The existing baseline at `~/.claude/skills/job-application-workspace/iteration-1/` has one run per configuration despite metadata claiming three, a baseline arm on only two of five evals, and one assertion logged as non-discriminating. Re-running it as `iteration-2` against `job-hunt` is the only real test of Task 17's layering change — `check_skill_lossless.py` proves bytes survived, not that they arrive when needed.

