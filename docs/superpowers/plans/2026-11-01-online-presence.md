# Online Presence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ask each candidate once for their GitHub, Google Scholar and personal website, check them when stale, diff against the last snapshot, and write user-confirmed findings into the master profile.

**Architecture:** One new script, `scripts/online_presence.py`, owns the per-person record (`<profile_dir>/online-presence.yaml`), snapshots, diffing, confirmation and write-back, with subcommands the agent calls at mode entry. GitHub is fetched by the script; Scholar and website pages arrive as raw captures made by the agent through existing tools and are only ingested. `check_claims.py` learns to recognise a journaled write-back; the mode docs gain one entry step.

**Tech Stack:** Python 3.10+, standard library (`urllib.request`, `json`, `difflib`), PyYAML; pytest.

**Spec:** `docs/superpowers/specs/2026-11-01-online-presence-design.md`

## Global Constraints

- Sources are GitHub, Google Scholar and a personal website only. No LinkedIn, no page that needs a login.
- Re-check a source only when its last check is older than **14 days**, unless the run passes `--force`.
- Show at most **4** findings per run; the rest stay `pending` and are never folded into the baseline.
- Ask status values: `given`, `none`, `declined`. Finding status values: `pending`, `confirmed`, `ignored`, `confirmed_unwritten`. Check outcomes: `ok`, `refused`, `failed`, `not_checked`.
- Stars, forks and release numbers are never written into a master.
- The master is written only through `scripts/save_profile.py` (dated backup).
- A 403/429/captcha/login wall is `refused`: no retry, no alternate route, never reported as "no updates".
- Scripts run as `python3 scripts/<x>.py`, exit 0 ok / 1 findings / 2 could-not-run, print one finding per line, and refuse a workspace inside the skill (existing `cli_io`/`paths` behaviour).
- Every new test must fail on the pre-change code; `make check` stays green.

## Review Focus

- **GitHub rate limit or 403 when unauthenticated** → outcome `refused` with the response saved; no findings computed from a partial listing. (Task 2)
- **A source that exists but is empty** (no public repositories, no papers) → outcome `ok`, zero findings, not an error. (Task 2, Task 4)
- **A mistyped username or URL (404)** → outcome `failed` with the status code; the ask status stays `given`, and `status` reports `BROKEN_LINK` so the agent can offer a correction instead of asking from scratch. (Task 1, Task 2)
- **An unreadable or hand-damaged `online-presence.yaml`** → exit 2 naming the file; the record is never overwritten and the user is never re-asked because of it. (Task 1)
- **A finding the master already mentions** (repository URL or name in `projects`, paper title in `publications`, case- and punctuation-insensitive) → not proposed. (Task 4)

---

### Task 1: Record, status and the ask-once rule

**Files:**
- Modify: `scripts/paths.py` (add two functions beside `answer_bank`)
- Create: `scripts/online_presence.py`
- Test: `scripts/tests/test_online_presence_record.py`

**Interfaces:**
- Produces:
  - `paths.online_presence(name: str) -> pathlib.Path` → `profile_dir(name) / "online-presence.yaml"`
  - `paths.online_presence_dir(name: str) -> pathlib.Path` → `profile_dir(name) / "online-presence"`
  - `online_presence.load_record(path: Path) -> dict` (empty record `{"sources": {}, "checks": {}, "findings": [], "writebacks": []}` when absent; raises `journal.YamlUnreadable` when unreadable)
  - `online_presence.save_record(path: Path, record: dict) -> None` (atomic write)
  - `online_presence.status(name: str, today: date) -> dict` → `{"to_ask": [sources], "stale": [sources], "broken": [sources], "shared_with": str|None}`
  - `online_presence.record_answer(name: str, source: str, status: str, value: str|None, words: str, extra: list[str]|None = None) -> None`
  - CLI: `online_presence.py status --name N [--today YYYY-MM-DD] [--workspace WS]` (with `--workspace`, journals `{"action": "online_presence_status", ...}` there), `online_presence.py record --name N --source {github,scholar,website} --status {given,none,declined} [--value V] [--extra org-or-repo ...] --words "<user's words>"`

- [ ] **Step 1: Write the failing tests**

```python
def test_absent_record_asks_all_three(tmp_store): assert status("Jane Doe", D)["to_ask"] == ["github", "scholar", "website"]
def test_declined_and_none_are_never_asked_again(tmp_store):  # record none/declined -> to_ask == []
def test_master_links_seed_the_record_without_asking(tmp_store):  # master contact.links.scholar -> scholar not in to_ask, record has status given
def test_stale_after_14_days(tmp_store):  # last check 2026-10-17 ok, today 2026-11-01 -> stale; 2026-10-19 -> not stale
def test_failed_404_is_broken_not_reasked(tmp_store):  # checks.github.outcome failed, code 404 -> broken == ["github"], to_ask == []
def test_unreadable_record_exits_2_and_is_untouched(tmp_store):  # garbage YAML -> CLI status exit 2, bytes unchanged
def test_record_requires_users_words(tmp_store):  # CLI record without --words -> exit 2
def test_status_with_workspace_journals_the_step(tmp_store, ws):  # journal has action online_presence_status
```

- [ ] **Step 2: Run** `python -m pytest scripts/tests/test_online_presence_record.py -q` — Expected: FAIL (module missing)
- [ ] **Step 3: Implement** the interfaces above. Seeding reads every master from `paths.master_profiles(name)`, keys `github`/`scholar`/`website` in `contact.links`, and records them with `words: "from master contact.links"`.
- [ ] **Step 4: Run** the same command — Expected: PASS
- [ ] **Step 5: Commit** `git add scripts/paths.py scripts/online_presence.py scripts/tests/test_online_presence_record.py && git commit -m "Record public profiles once per person"`

### Task 2: GitHub fetch and snapshot

**Files:**
- Modify: `scripts/online_presence.py`
- Test: `scripts/tests/test_online_presence_github.py`, fixtures under `scripts/tests/fixtures/online_presence/github/`

**Interfaces:**
- Consumes: Task 1 record functions, `journal.append(workspace, record)`
- Produces:
  - `online_presence.fetch_github(username: str, extra: list[str], get: Callable[[str], tuple[int, bytes]]) -> dict` → `{"outcome": str, "code": int|None, "repos": [{"full_name", "html_url", "description", "created_at", "pushed_at", "stars", "forks", "latest_release", "topics", "role"}], "raw": [(url, status, bytes)]}`; `role` is `owner`, `contributor` or excluded.
  - `online_presence.http_get(url: str) -> tuple[int, bytes]` (urllib, 20 s timeout, `Accept: application/vnd.github+json`, no auth unless `GITHUB_TOKEN` is set in the environment)
  - `online_presence.write_snapshot(name: str, source: str, snapshot: dict, today: date) -> Path` → `<online_presence_dir>/snapshots/<date>-<source>.json`; raw bodies under `<online_presence_dir>/raw/<date>-<source>-<n>.json`

- [ ] **Step 1: Write the failing tests** (fixtures replay recorded API JSON through a fake `get`)

```python
def test_forks_archived_and_no_commit_repos_are_left_out():  # fixture: 1 fork, 1 archived, 1 org repo with zero user commits -> none in repos
def test_extra_org_repo_is_included_with_contributor_role():  # extra ["addsumtech/slides_maker"], contributors fixture lists user -> role "contributor" or "owner"
def test_rate_limit_403_is_refused_and_has_no_repos():  # get returns 403 with "rate limit" body -> outcome "refused", repos == []
def test_404_user_is_failed_with_code():  # -> outcome "failed", code 404
def test_empty_account_is_ok_with_no_repos():  # [] -> outcome "ok", repos == []
def test_snapshot_and_raw_are_written_and_journaled(tmp_store, ws):  # files exist; journal has action "online_presence_fetch" with source and outcome
```

- [ ] **Step 2: Run** `python -m pytest scripts/tests/test_online_presence_github.py -q` — Expected: FAIL
- [ ] **Step 3: Implement.** User repos from `/users/{u}/repos?per_page=100&type=owner`; each `extra` entry that is `org/repo` is read directly, a bare `org` from `/orgs/{org}/repos`; contributor membership from `/repos/{full}/contributors?per_page=100`; latest release from `/repos/{full}/releases/latest` (404 → `None`). Any 403/429 anywhere makes the whole fetch `refused`.
- [ ] **Step 4: Run** — Expected: PASS
- [ ] **Step 5: Commit** `git commit -m "Fetch and snapshot a candidate's GitHub repositories"` (named paths only)

### Task 3: Ingest Scholar and website captures

**Files:**
- Modify: `scripts/online_presence.py`
- Test: `scripts/tests/test_online_presence_ingest.py`, fixtures `scripts/tests/fixtures/online_presence/{scholar,website}/`

**Interfaces:**
- Consumes: browser snapshot JSON as written by `scripts/browser_cdp.mjs` / `record_browser_capture.py` (`text`, `url`, `http_status`, `blocked`)
- Produces:
  - `online_presence.ingest_scholar(capture: Path) -> dict` → `{"outcome", "papers": [{"title", "venue", "year", "authors"}]}`
  - `online_presence.ingest_website(capture: Path) -> dict` → `{"outcome", "url", "text"}`
  - CLI: `online_presence.py ingest --name N --source {scholar,website} --capture PATH --workspace WS`

- [ ] **Step 1: Write the failing tests**

```python
def test_scholar_rows_parse_title_venue_year_authors():  # fixture page text -> 3 papers with exact titles
def test_scholar_captcha_capture_is_refused():  # text contains "unusual traffic" / blocked true -> outcome "refused", papers == []
def test_website_text_is_kept_verbatim():  # outcome ok, text equals capture text
def test_http_404_capture_is_failed():  # http_status 404 -> outcome "failed"
def test_ingest_without_capture_file_exits_2(tmp_path):
```

- [ ] **Step 2–4:** run (FAIL), implement (refusal detection reuses `references/risk-control-signals.yaml` patterns through the existing loader in `check_opencli_result.py`), run (PASS)
- [ ] **Step 5: Commit** `git commit -m "Ingest Scholar and website captures into snapshots"`

### Task 4: Diff, findings and the `check` command

**Files:**
- Modify: `scripts/online_presence.py`
- Test: `scripts/tests/test_online_presence_diff.py`

**Interfaces:**
- Consumes: snapshots from Tasks 2–3, record from Task 1
- Produces:
  - `online_presence.diff(source: str, previous: dict|None, current: dict, master: dict) -> list[dict]`; a finding is `{"id": "<source>:<key>", "source", "kind": "new_repo"|"new_release"|"new_paper"|"page_changed"|"repo_changed", "summary", "evidence_url", "evidence_file", "rank": float}`
  - `online_presence.check(name: str, workspace: Path, today: date, force: bool, get=http_get) -> dict` → `{"checked": {source: outcome}, "shown": [finding], "pending_count": int}`; appends new findings as `pending`, keeps old `pending` ones, shows at most 4 ordered by `rank`
  - CLI: `online_presence.py check --name N --workspace WS [--force]` prints the shown findings and `PENDING: <n> more`

- [ ] **Step 1: Write the failing tests**

```python
def test_first_check_proposes_only_what_master_lacks():  # master projects mention slides_maker by URL -> no new_repo for it
def test_master_match_ignores_case_and_punctuation():  # "Slides Maker" vs "slides_maker" -> treated as mentioned
def test_new_release_is_a_finding_but_star_change_is_not_written():  # finding kind new_release; star delta only in summary
def test_more_than_four_findings_keeps_the_rest_pending():  # 6 findings -> shown 4, pending_count 2, all 6 in record
def test_ignored_finding_returns_only_when_it_changes():  # ignored new_repo X; next check same X -> not shown; X gets release -> shown as new_release
def test_fresh_source_is_not_refetched(): # last check 3 days ago -> get never called unless force
def test_refused_source_yields_no_findings_and_reports_it():  # checked == {"github": "refused"}
def test_empty_paper_list_is_ok_with_zero_findings():
```

- [ ] **Step 2–4:** run (FAIL), implement (rank = recency of `pushed_at`/year, then owner over contributor, then stars), run (PASS)
- [ ] **Step 5: Commit** `git commit -m "Diff online-presence snapshots into findings the user confirms"`

### Task 5: Confirmation and write-back

**Files:**
- Modify: `scripts/online_presence.py`
- Test: `scripts/tests/test_online_presence_writeback.py`

**Interfaces:**
- Consumes: findings from Task 4; `save_profile.main(["--name", N, "--profile", tmpfile])`
- Produces:
  - `online_presence.confirm(name: str, finding_id: str, decision: "confirmed"|"ignored", words: str, correction: dict|None = None) -> None`
  - `online_presence.writeback(name: str, language: str, workspace: Path|None) -> list[str]` → finding ids written; appends `{"master": path, "before_sha256", "after_sha256", "finding_ids", "date"}` to `record["writebacks"]` and, when given, journals `{"action": "master_writeback", ...}` in the workspace
  - CLI: `online_presence.py confirm --name N --finding ID --decision {confirmed,ignored} --words "..." [--role ROLE]`, `online_presence.py writeback --name N --language en [--workspace WS]`

- [ ] **Step 1: Write the failing tests**

```python
def test_confirmed_repo_becomes_a_project_without_star_counts(tmp_store):  # master projects gains name/description/role/link; no digits from stars/forks
def test_confirmed_paper_becomes_a_publication(tmp_store):
def test_writeback_backs_up_and_logs_shas(tmp_store):  # .bak-<date> exists; writebacks[-1] before/after sha match files
def test_no_master_leaves_confirmed_unwritten(tmp_store):  # status confirmed_unwritten; later writeback after a master exists writes it
def test_unconfirmed_findings_are_never_written(tmp_store):
def test_user_text_in_existing_entry_is_not_edited(tmp_store):  # existing project entry for the repo stays byte-identical
def test_other_language_master_is_offered_not_rewritten(tmp_store):  # writeback en; status for zh lists the finding as pending_for_master
```

- [ ] **Step 2–4:** run (FAIL), implement, run (PASS)
- [ ] **Step 5: Commit** `git commit -m "Write confirmed online findings into the master through save_profile"`

### Task 6: Recognise a recorded write-back in check_claims

**Files:**
- Modify: `scripts/check_claims.py` (the `MASTER_MUTATED` branch, ~line 1217)
- Test: `scripts/tests/test_check_claims_writeback.py`

**Interfaces:**
- Consumes: `record["writebacks"]` from Task 5 via `online_presence.load_record(paths.online_presence_of(workspace))` — add `paths.online_presence_of(workspace) -> Path` using `profile_dir_of`
- Produces: finding `MASTER_WRITEBACK: <master> gained <n> confirmed online-presence item(s) on <date> (<ids>); tell the user, then re-run check_claims.py --record` — still blocking; any change not covered by a write-back stays `MASTER_MUTATED`

- [ ] **Step 1: Write the failing tests**

```python
def test_writeback_chain_reports_master_writeback_not_mutated(ws):  # fingerprint sha == writeback before_sha, current == after_sha
def test_unrecorded_edit_after_writeback_is_still_mutated(ws):  # after_sha != current -> MASTER_MUTATED
def test_rerecord_clears_the_finding(ws):  # --record then gate -> no MASTER_* finding
```

- [ ] **Step 2–4:** run (FAIL), implement, run (PASS)
- [ ] **Step 5: Commit** `git commit -m "Tell a recorded master write-back apart from a mutation"`

### Task 7: Split profile directories

**Files:**
- Modify: `scripts/online_presence.py`
- Test: `scripts/tests/test_online_presence_link.py`

**Interfaces:**
- Produces: `status(...)["other_records"]: list[str]` (slugs of other profile dirs that have a record); `online_presence.link(name: str, other: str, words: str) -> None` writes `shared_with: <other-slug>` and makes `load_record`/`status` follow it; CLI `online_presence.py link --name N --with OTHER --words "..."`

- [ ] **Step 1: Write the failing tests**

```python
def test_status_lists_other_directories_with_a_record(tmp_store):
def test_linked_directory_is_not_asked_again(tmp_store):  # link -> to_ask == [] and sources come from the other record
def test_link_to_missing_directory_exits_2(tmp_store):
```

- [ ] **Step 2–4:** run (FAIL), implement, run (PASS)
- [ ] **Step 5: Commit** `git commit -m "Share one online-presence record across a person's profile directories"`

### Task 8: Mode wiring, gate notices and documentation

**Files:**
- Create: `references/online-presence.md` (the agent procedure: when to run, how to ask once, Scholar/website capture commands, refusal hand-off without blocking the mode, the confirmation message with at most 4 findings, write-back order)
- Modify: `SKILL.md` ("Enter a full mode": one step pointing to the reference), `modes/apply.md` (Step 1, before `check_claims.py --record`), `modes/discover.md` (before `snapshot_profile.py`), `modes/assess.md` (before the profile read; replace "never writes it" with "never writes it except through a confirmed online-presence write-back"), `references/workflow-checklist.md`, `REFERENCE.md` (layout tree), `scripts/check_apply.py`, `scripts/check_shortlist.py`
- Test: `scripts/tests/test_online_presence_wiring.py`

**Interfaces:**
- Consumes: journal actions `online_presence_status` (written by `status --workspace`), `online_presence_fetch`, `master_writeback`
- Produces: `NOTICE_NO_ONLINE_PRESENCE_STEP` on stderr from `check_apply.py` and `check_shortlist.py` when the workspace journal has no `online_presence_status` record; exit codes unchanged

- [ ] **Step 1: Write the failing tests**

```python
def test_three_modes_name_the_step_before_freezing_the_profile():  # in apply.md the step precedes "check_claims.py --record"; discover precedes snapshot_profile; assess precedes the profile read
def test_assess_no_longer_says_never_writes_without_the_exception():
def test_gates_notice_but_do_not_fail_without_the_step(ws):  # exit 0, stderr has NOTICE_NO_ONLINE_PRESENCE_STEP
def test_reference_and_script_are_in_the_layout_tree_and_self_check():
```

- [ ] **Step 2–4:** run (FAIL), edit docs and gates, run (PASS)
- [ ] **Step 5: Full suite** `make check PY=python` — Expected: all pass, `LOSSLESS`, `check_conventions` and `NO_HIDDEN_CHARS` green
- [ ] **Step 6: Commit** `git commit -m "Wire the online-presence step into apply, discover and assess"`
