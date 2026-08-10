# Discover Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `job-hunt` a live, read-only job-discovery mode that runs through `opencli` and cannot deliver a shortlist it did not actually retrieve.

**Architecture:** Three layers. `scripts/check_opencli_result.py` is a wrapper that turns one adapter invocation into a classification (`ok | platform_limit | not_logged_in | no_auth_adapter | transport`) and one `adapter_call` line in `journal.jsonl`; `scripts/check_no_write.py` and `scripts/check_shortlist.py` are gates that read those lines back and refuse a run that ran a write command, fabricated a row, listed more rows than were retrieved, rendered a band without saying it came from a card, or said "no results" when in fact every adapter died. `modes/discover.md` (layer 1.5, loaded unconditionally on entering the mode, entry recorded with its content hash by `scripts/enter_mode.py`) defines the `search-preferences.yaml`, `brief.yaml` and `shortlist.yaml` schemas that the gates require, and `references/{discovery-sources.md,source-policy.md,risk-control-signals.yaml}` carry the per-adapter catalogue, the single source standard, and the machine-readable stop signals. SKILL.md (layer 1) carries only what has to be there when it is needed: the four command pairs, the exit-code rule, the write ban, the platform-limit stop rule, and the two triggers.

**Tech Stack:** Python 3 (stdlib + PyYAML), pytest, `opencli` v1.8.6 (read commands only), Markdown + YAML skill files.

## Global Constraints

- Repo root is `/Users/donghanglyu/code_project/job-hunt`. **Every path in this plan is relative to that root.**
- **Prerequisite: Plan 1 has landed.** `scripts/journal.py`, `scripts/paths.py`, `scripts/vocab.py` and `scripts/enter_mode.py` must already exist. If any does not, stop and run Plan 1 first — do not stub them, do not reimplement them, do not change their signatures.
- Python 3, stdlib + **PyYAML** only in this plan. `python-docx` is not used here. If `python3 -c 'import yaml'` fails, stop — do not vendor a YAML parser.
- Run tests with: `python3 -m pytest scripts/tests -q`
- **Gate CLI contract, one named exception (`check_opencli_result.py`, below).** `python3 scripts/<name>.py --workspace <path> [args]`; exit `0` = passed, exit `1` = failed with findings printed to stdout one per line each prefixed with a stable UPPERCASE code, exit `2` = could not run with the message on stderr. Each gate appends exactly one receipt line to `<workspace>/journal.jsonl` before exiting.
- **Receipt verdict vocabulary, closed:** `"pass"` | `"fail"` | `"could_not_run"` | `"recorded"`. This plan's two gates use only the first three; `"recorded"` belongs to reporting scripts in other plans. **Never `"error"`.**
- **Exit-2 discipline, identical in every gate.** On the "could not run" path write EXACTLY ONE receipt with verdict `"could_not_run"`, print the reason to stderr, return 2. The single exception: if the workspace directory itself does not exist there is nothing to append to, so print to stderr and return 2 **with no receipt** — and say that in the script's own docstring, because a reader who finds no receipt needs to know which of the two cases they are in. Every gate carries a test asserting the exit-2 receipt exists, and a test asserting the missing-workspace path writes none.
- **`scripts/check_opencli_result.py` is a wrapper, NOT a gate — the one named exception to the contract above.** Its exit codes are deliberately different: `0` = classified (the classification is printed to stdout as one JSON object), `2` = could not classify. There is no exit 1. It writes an `action: "adapter_call"` record via `journal.append`, never a gate receipt. Reason: a `not_logged_in` adapter is information the mode acts on, not a failure of the run; giving it exit 1 would make every honest degraded run look like a broken one. **No other script in this plan may deviate**, and this deviation is named here so a later reader does not read it as a contract breach.
- **The five classification strings, exact:** `"ok"` | `"platform_limit"` | `"not_logged_in"` | `"no_auth_adapter"` | `"transport"`.
- **The ONE verdict vocabulary lives in `scripts/vocab.py` (Plan 1) and is never re-spelled here.** `check_shortlist.py` does `from vocab import EFFORT, VERDICTS`; it declares no verdict tuple of its own. For the reader: `vocab.VERDICTS` is `("strong_apply", "worth_applying", "stretch", "likely_screen_out", "blocked")`, ordinal, strongest first; `vocab.REFUSAL` is `"insufficient_evidence"`, an orthogonal refusal state and **not** a sixth level. zh labels live in `vocab.VERDICT_ZH`. **Every discover-stage verdict carries `provisional: true` and MUST NOT be copied into an assessment.**
- **Top three verdict levels** (the only ones a detail page may be fetched for): `VERDICTS[:3]` — `strong_apply`, `worth_applying`, `stretch`. Derived, never re-listed, so a change to the vocabulary cannot leave the cap behind.
- **`JobListingEvidence` base fields, exact and complete:** `id, title, company, location, salary, url, source_site, source_id, extraction_method, retrieved_at, quality, verification, raw_text`. **Do not add or rename a base field.**
- **The shortlist row is this skill's own schema on top of those base fields**, and it adds exactly three: `why_matched`, `verdict`, `provisional`, `effort`. Seventeen fields in total. `effort` is one of `vocab.EFFORT` (`quick` | `evening` | `multi_day` | `not_closable`) and exists so that D3's *within-a-band, order by effort-to-close* rule is implementable rather than merely stated. `check_shortlist.REQUIRED_ROW_FIELDS` is the single enumeration of all seventeen.
- **`scripts/paths.py` is imported wherever a profile, workspace, search directory or `search-preferences.yaml` path is resolved** — `paths.search_prefs(name)`, `paths.search_dir(name, slug)`. No script and no mode file re-derives one of those with `.parents[n]` or a string join. (The gates themselves take `--workspace` as an argument and resolve nothing; the mode file is where the spine paths are named.) The **skill root** is modelled there too, as `paths.SKILL_ROOT`, and `paths.mode_file(mode, root)` resolves `modes/<mode>.md` under it — **mode first, root second**, and there is no `enter_mode.mode_file`. So `check_opencli_result.py` and `check_shortlist.py` `import paths` and use `paths.SKILL_ROOT`; neither re-derives a root with `.parent.parent`. Both still take an explicit override (`--signals-file`, `--skill-root`) so a test never depends on where the module happens to sit.
- **Mode entry is the first thing `modes/discover.md` instructs.** `python3 scripts/enter_mode.py --workspace <ws> --mode discover` writes the `mode_entry` record and the mode file's content hash; `check_shortlist.py` fails with `NO_MODE_ENTRY` / `MODE_FILE_CHANGED` if it is absent or stale. That record is also what makes `journal.receipt` stamp this run's receipts `"mode": "discover"` instead of `"unknown"`.
- **Expect one known-red window.** From Task 1 until Task 10, Plan 1's `scripts/tests/test_skill_structure.py` is FAILING, because it asserts `SKILL.md`'s `## Self-check` section names every `scripts/*.py`, every `references/*.md` and every `modes/*.md` in the tree — and this plan adds files before it registers them. That is why the per-task steps run only their own module and the **full** suite is not run until Task 10, which does the registration. Do not "fix" it by deleting the assertion.
- **READ-ONLY.** No step in this plan may run an `opencli` command whose published `access:` is `write`. No login attempt on any site, ever, including in the dry run. There is no "confirm then send" path (spec D7).
- **No fabricated facts.** Every claim about opencli behaviour written into a doc must be marked either measured (with the date `2026-08-09` and the exact command) or explicitly unverified. Do not invent a risk-control string and present it as observed.
- Today is **2026-08-09**. Use that literal date in filenames and examples; never call an unstamped date helper in an example.
- **Reading this plan's code blocks:** every fenced block inside a step is indented four
  spaces relative to the step. Strip exactly those four spaces when you write the file —
  including inside triple-quoted Python strings and inside the Markdown files, whose
  content is otherwise byte-for-byte what should land on disk.
- **Git:** stage NAMED PATHS only — never `git add -A`, never `git add .`. **NEVER push.** Do not pass `-c user.name` / `-c user.email`.

---

## File Structure

| File | Responsibility |
|---|---|
| `references/risk-control-signals.yaml` | The machine-readable list of platform stop-signal patterns, each tagged `verified: true/false`. Loaded by `check_opencli_result.py`. Matched **only** against the stderr of a non-zero exit. |
| `scripts/check_opencli_result.py` | Classify one adapter invocation. Exit code first, always. Writes the `adapter_call` journal record. Owns reading those records back (`read_journal`, `read_adapter_calls`). |
| `scripts/opencli_meta.py` | Read opencli's **own** `access: read\|write` metadata from `opencli <site> --help -f yaml`, cached on disk. Nothing else in the tree maintains a command allowlist. |
| `scripts/check_no_write.py` | Gate. Fails if any invocation recorded in `journal.jsonl` resolves to `access: write`, or if its access cannot be resolved at all (fail closed). |
| `scripts/check_shortlist.py` | Gate. Per-row provenance (Task 3) and run-level honesty: shortfall, empty-result disambiguation, disclosure block, source report, detail-fetch cap (Task 4). |
| `references/discovery-sources.md` | Layer 2. Per-adapter flags, measured login state, identity field, detail command, caps, risk-control strings, degraded-fallback field list. Trigger + backstop live in SKILL.md and `check_shortlist.py`. |
| `references/source-policy.md` | The ONE source standard (green/yellow/red) that the skill actually obeys. Replaces the retired `job-search-coach` policy. Trigger + backstop live in SKILL.md and `check_shortlist.py`'s cap findings. |
| `modes/discover.md` | Layer 1.5. The mode file: the mode-entry command, entry conditions, the `search-preferences.yaml` schema and the interview that fills it, the auth probe, bilingual queries, the `brief.yaml` and `shortlist.yaml` schemas (defined nowhere else), the provisional stamp rule for BOTH outputs, the platform-limit stop rule, the degraded disclosure block, the self-check list. |
| `SKILL.md` | **Modified twice** — Task 5 appends a marked block carrying the four inlined command pairs, the six-clause platform-limit stop rule and the evaluable trigger for `references/discovery-sources.md`; Task 6 adds the trigger for `references/source-policy.md`; Task 10 registers everything in the `## Self-check` section and the gate table and flips the `discover` row of the `## Modes` table from "not yet built" to live. |
| `scripts/tests/conftest.py` | Puts `scripts/` on `sys.path` so tests can `import check_shortlist`. |
| `scripts/tests/discover_fixtures.py` | Builds a **valid** discover workspace out of the real 2026-08-09 51job capture. Every test mutates exactly one thing away from valid. |
| `scripts/tests/test_*.py` | One test module per deliverable, each pinning the quiet case as hard as the firing case. |

---

### Task 1: opencli result classifier

**Files:**
- Create: `references/risk-control-signals.yaml`
- Create: `scripts/check_opencli_result.py`
- Create: `scripts/tests/conftest.py` (if it does not already exist — see Step 1)
- Test: `scripts/tests/test_check_opencli_result.py`

**Interfaces:**
- Consumes (from Plan 1):
  - `journal.append(workspace: pathlib.Path, record: dict) -> None` (`scripts/journal.py`)
  - `paths.SKILL_ROOT: pathlib.Path` (`scripts/paths.py`) — the repo root, used for `DEFAULT_SIGNALS_FILE`; never re-derived with `.parent.parent`
- Produces (later tasks rely on these exact names):
  - `ADAPTER_CALL_ACTION: str` — the literal `"adapter_call"`
  - `CLASSIFICATIONS: tuple[str, ...]`
  - `IDENTITY_FIELD: dict[str, str]`, `IDENTITY_FIELD_DEFAULT: str`, `DETAIL_COMMAND: dict[str, str]`
  - `load_signals(path: pathlib.Path | None) -> list[dict]`
  - `classify(site: str, command: str, exit_code: int, stdout_text: str, stderr_text: str, auth_rows: list[dict] | None = None, signals=()) -> dict`
  - `read_journal(workspace: pathlib.Path) -> list[dict]` — every line, with `_lineno`; unparsable lines come back as `{"_lineno": n, "_unparsable": raw}`
  - `read_adapter_calls(workspace: pathlib.Path) -> list[dict]` — only records whose `action == ADAPTER_CALL_ACTION`
  - `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Create the test bootstrap**

    First: `mkdir -p scripts/tests references` — the file below lands inside `scripts/tests`, so the directory has to exist before it is written.

    Then, if `scripts/tests/conftest.py` already exists (Plan 1 may have created it), open it and make sure it contains the `sys.path` insert below; **add the lines, do not overwrite the file**. If it does not exist, create it with exactly this content:

    ```python
    """Put scripts/ on sys.path so tests can import the gate modules directly."""
    import pathlib
    import sys

    SCRIPTS = pathlib.Path(__file__).resolve().parent.parent
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    ```

- [ ] **Step 2: Write the signal data file**

    Create `references/risk-control-signals.yaml`:

    ```yaml
    # Platform stop-signals for scripts/check_opencli_result.py.
    #
    # MATCHING RULE (this is the whole anti-cry-wolf design): a pattern here is
    # matched ONLY against the stderr of an invocation that exited non-zero. A
    # successful opencli call has EMPTY stderr, so nothing in this file can fire
    # on ordinary output — a job posting whose title contains "安全验证" or
    # "captcha" is a job about verification, not a verification wall.
    #
    # `verified: true` means the string was captured verbatim from a real run and
    # `observed:` names the date and command. `verified: false` means it is a
    # shape we expect but have NOT seen. The first time a real risk-control body
    # is captured, replace the guessed pattern with the verbatim string and flip
    # the flag. Do not add a `verified: true` entry you did not run.
    #
    # Cost of a false positive here is bounded and conservative: the mode stops
    # that one site for that one round and says so. Cost of a false negative is
    # a retry against a platform that just asked us to stop.

    measured_note: >-
      The only failure body ever captured from this toolset (2026-08-09) is
      exit 1 + EMPTY stdout + a YAML block on stderr even under -f json:
      "ok: false / error: {code: COMMAND_EXEC, message: '1point3acres request
      failed: HTTP 403 Forbidden from https://www.1point3acres.com/bbs/forum-145-1.html',
      exitCode: 1}". That 403 is a LOGIN WALL, and check_opencli_result.py
      resolves it in the login-wall branch against `opencli auth status`, not
      here. No captcha, slider or rate-limit body has ever been observed.

    signals:
      - id: http-429-rate-limited
        site: "*"
        pattern: "HTTP 429"
        verified: false
      - id: verify-human-en
        site: "*"
        pattern: "(?i)verify (that )?you are (a )?human"
        verified: false
      - id: unusual-traffic-en
        site: "*"
        pattern: "(?i)unusual traffic"
        verified: false
      - id: captcha-interstitial
        site: "*"
        pattern: "(?i)captcha"
        verified: false
      - id: slider-verification-cn
        site: "*"
        pattern: "滑块"
        verified: false
      - id: security-verification-cn
        site: "*"
        pattern: "安全验证"
        verified: false
      - id: risk-control-cn
        site: "*"
        pattern: "风控"
        verified: false
      - id: too-frequent-cn
        site: "*"
        pattern: "操作过于频繁"
        verified: false
      - id: access-restricted-cn
        site: "*"
        pattern: "访问受限"
        verified: false
    ```

- [ ] **Step 3: Write the failing test**

    Create `scripts/tests/test_check_opencli_result.py`:

    ```python
    """Tests for scripts/check_opencli_result.py.

    Every payload below is a MEASURED opencli response captured 2026-08-09, not an
    invented one. The quiet cases are pinned as hard as the firing cases: a
    classifier that shouts on an ordinary successful search is worse than none,
    because the reader learns to skip that line.
    """
    import json
    import pathlib

    import check_opencli_result as coc

    REPO = pathlib.Path(__file__).resolve().parents[2]
    SIGNALS_FILE = REPO / "references" / "risk-control-signals.yaml"


    def stderr_403(site, url):
        """The measured failure body: YAML on stderr even under -f json."""
        return (
            "ok: false\n"
            "error:\n"
            "  code: COMMAND_EXEC\n"
            f"  message: '{site} request failed: HTTP 403 Forbidden from {url}'\n"
            "  exitCode: 1\n"
        )


    STDERR_1P3A_403 = stderr_403(
        "1point3acres", "https://www.1point3acres.com/bbs/forum-145-1.html"
    )

    STDOUT_51JOB_OK = json.dumps(
        [
            {"rank": 1, "jobId": "173198362",
             "title": "高级算法工程师（视觉调试智能化、AI方向）", "salary": "3-6万",
             "salaryMin": 30000, "salaryMax": 60000, "city": "西安",
             "district": "高新技术产业开发区", "workYear": "3年及以上", "degree": "博士",
             "company": "比亚迪汽车工业", "issueDate": "2026-08-08 10:23:15",
             "url": "https://jobs.51job.com/xian-gxjs/173198362.html?s=sou_sou_soulb&t=0_0",
             "encCoId": "VDMHY1M0BDgAZ1c9AWVWZA"},
            {"rank": 2, "jobId": "173199597", "title": "高级AI算法工程师(J10032)",
             "salary": "1.7-3.4万·15薪", "salaryMin": 17000, "salaryMax": 34000,
             "city": "海宁", "district": "", "workYear": "3年", "degree": "硕士",
             "company": "拓荆键科（海宁）半导体设备", "issueDate": "2026-08-08 14:34:16",
             "url": "https://jobs.51job.com/haining/173199597.html?s=sou_sou_soulb&t=0_0",
             "encCoId": "UjJQPFY2DzYPaVQyVDI"},
        ],
        ensure_ascii=False,
    )

    STDOUT_INDEED_EMPTY_TITLES = json.dumps(
        [
            {"rank": 1, "id": "152875498075cf99", "title": "", "company": "UF Health",
             "location": "Gainesville, FL 32610", "salary": "", "tags": "",
             "url": "https://www.indeed.com/viewjob?jk=152875498075cf99"},
            {"rank": 2, "id": "35fc226942cc38c0", "title": "", "company": "Orthoindy",
             "location": "Lafayette, IN 47909", "salary": "", "tags": "",
             "url": "https://www.indeed.com/viewjob?jk=35fc226942cc38c0"},
        ]
    )

    # Measured auth rows. Note `logged_in` is an EMPTY STRING on nowcoder, not false.
    AUTH_ROWS = [
        {"site": "boss", "status": "logged_in", "logged_in": True, "checked": "quick"},
        {"site": "linkedin", "status": "logged_in", "logged_in": True, "checked": "quick"},
        {"site": "1point3acres", "status": "not_logged_in", "logged_in": False,
         "checked": "full"},
        {"site": "nowcoder", "status": "unknown", "logged_in": "", "checked": "skipped",
         "error": "quickCheck not implemented; use --full to run whoami"},
    ]


    def test_exit0_json_array_is_ok_and_says_nothing():
        r = coc.classify("51job", "search", 0, STDOUT_51JOB_OK, "", AUTH_ROWS)
        assert r["classification"] == "ok"
        assert r["row_count"] == 2
        assert r["empty_result"] is False
        assert r["empty_identity_rows"] == []
        assert r["needs_detail_recovery"] is False
        assert r["remedy"] is None


    def test_exit0_with_empty_titles_stays_ok_but_demands_detail_recovery():
        r = coc.classify("indeed", "search", 0, STDOUT_INDEED_EMPTY_TITLES, "")
        assert r["classification"] == "ok"          # the rows EXIST
        assert r["row_count"] == 2
        assert r["empty_identity_rows"] == [0, 1]
        assert r["needs_detail_recovery"] is True
        assert r["detail_command"] == "opencli indeed job <id>"
        assert "never read blank fields" in r["remedy"]


    def test_exit1_empty_stdout_yaml_stderr_is_not_logged_in():
        r = coc.classify("1point3acres", "forum", 1, "", STDERR_1P3A_403, AUTH_ROWS)
        assert r["classification"] == "not_logged_in"
        assert r["row_count"] == 0
        assert "HTTP 403 Forbidden" in r["error_message"]
        assert "opencli 1point3acres login" in r["remedy"]
        assert "Do not retry" in r["remedy"]


    def test_exit1_on_a_site_with_no_auth_adapter_is_no_auth_adapter():
        r = coc.classify(
            "indeed", "search", 1, "",
            stderr_403("indeed", "https://www.indeed.com/jobs?q=mri"), AUTH_ROWS,
        )
        assert r["auth_state"] == "absent"
        assert r["classification"] == "no_auth_adapter"
        assert "does not exist" in r["remedy"]


    def test_unknown_auth_status_is_never_collapsed_into_logged_out():
        r = coc.classify(
            "nowcoder", "search", 1, "",
            stderr_403("nowcoder", "https://www.nowcoder.com/search"), AUTH_ROWS,
        )
        assert r["auth_state"] == "unknown"
        assert r["classification"] == "not_logged_in"
        assert "--full" in r["remedy"]


    def test_403_while_auth_says_logged_in_is_a_platform_limit():
        r = coc.classify(
            "boss", "search", 1, "",
            stderr_403("boss", "https://www.zhipin.com/web/geek/job"), AUTH_ROWS,
        )
        assert r["classification"] == "platform_limit"
        assert "Stop this site" in r["remedy"]


    def test_empty_array_on_exit0_is_a_real_zero_result():
        r = coc.classify("51job", "search", 0, "[]", "", AUTH_ROWS)
        assert r["classification"] == "ok"
        assert r["row_count"] == 0
        assert r["empty_result"] is True


    def test_exit_code_wins_over_a_parsable_stdout():
        # The JSON.parse(stdout || '[]') trap. Even when stdout is a perfectly
        # good empty array, a non-zero exit is a failure, not a zero-result.
        r = coc.classify(
            "linkedin", "search", 1, "[]",
            stderr_403("linkedin", "https://www.linkedin.com/jobs/search"), AUTH_ROWS,
        )
        assert r["classification"] != "ok"
        assert r["empty_result"] is False


    def test_boss_identity_field_is_name_not_title():
        rows = json.dumps(
            [{"name": "算法工程师", "salary": "20-30K", "company": "某公司",
              "security_id": "abc123def456", "url": "https://www.zhipin.com/job_detail/x"}],
            ensure_ascii=False,
        )
        r = coc.classify("boss", "search", 0, rows, "", AUTH_ROWS)
        assert r["identity_field"] == "name"
        assert r["empty_identity_rows"] == []   # must NOT cry wolf over a missing `title`
        assert r["needs_detail_recovery"] is False


    def test_signals_never_match_job_rows_only_a_failed_calls_stderr():
        signals = coc.load_signals(SIGNALS_FILE)
        assert signals, "risk-control-signals.yaml produced no patterns"
        rows = json.dumps(
            [{"jobId": "173100001", "title": "安全验证/风控算法工程师 captcha 方向"}],
            ensure_ascii=False,
        )
        quiet = coc.classify("51job", "search", 0, rows, "", AUTH_ROWS, signals)
        assert quiet["classification"] == "ok"
        assert quiet["signal_id"] is None

        loud = coc.classify(
            "51job", "search", 1, "",
            "ok: false\nerror:\n  code: COMMAND_EXEC\n"
            "  message: 'HTTP 429 Too Many Requests'\n  exitCode: 1\n",
            AUTH_ROWS, signals,
        )
        assert loud["classification"] == "platform_limit"
        assert loud["signal_id"] == "http-429-rate-limited"
        assert "do not retry" in loud["remedy"]


    def test_a_signal_outside_error_message_still_fires():
        """The rule is 'matched against the STDERR of a failed call', not 'matched
        against the message field we happened to extract from it'. A body that
        carries the wall while `message` carries only a generic sentence is the
        exact shape a real risk-control page would take, and searching only the
        extracted message would classify it `transport` and let the round continue
        against a platform that just asked us to stop."""
        signals = coc.load_signals(SIGNALS_FILE)
        stderr = (
            "ok: false\n"
            "error:\n"
            "  code: COMMAND_EXEC\n"
            "  message: 'boss request failed'\n"
            "  body: '请完成安全验证后重试'\n"
            "  exitCode: 1\n"
        )
        r = coc.classify("boss", "search", 1, "", stderr, AUTH_ROWS, signals)
        assert r["error_message"] == "boss request failed"   # extraction unchanged
        assert r["classification"] == "platform_limit"
        assert r["signal_id"] == "security-verification-cn"


    def test_transport_is_the_default_for_an_unrecognised_failure():
        r = coc.classify(
            "51job", "search", 1, "",
            "ok: false\nerror:\n  code: COMMAND_EXEC\n"
            "  message: 'connect ECONNREFUSED 127.0.0.1:19825'\n  exitCode: 1\n",
        )
        assert r["classification"] == "transport"
        assert "opencli doctor" in r["remedy"]


    def test_exit0_with_unparsable_stdout_is_transport_not_ok():
        r = coc.classify("51job", "search", 0, "<html>login</html>", "")
        assert r["classification"] == "transport"


    def test_main_writes_exactly_one_adapter_call_record(tmp_path):
        (tmp_path / "raw").mkdir()
        out = tmp_path / "raw" / "51job-1.json"
        out.write_text(STDOUT_51JOB_OK, encoding="utf-8")
        rc = coc.main([
            "--workspace", str(tmp_path),
            "--site", "51job", "--command", "search",
            "--exit-code", "0", "--stdout-file", str(out),
            "--command-line",
            "opencli 51job search 算法工程师 --limit 2 --window background -f json",
        ])
        assert rc == 0
        lines = (tmp_path / "journal.jsonl").read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        rec = json.loads(lines[0])
        assert rec["action"] == "adapter_call"
        assert rec["site"] == "51job" and rec["command"] == "search"
        assert rec["exit_code"] == 0
        assert rec["classification"] == "ok"
        assert rec["row_count"] == 2
        assert rec["command_line"].startswith("opencli 51job search")


    def test_main_exits_2_when_the_stdout_file_is_missing(tmp_path):
        rc = coc.main([
            "--workspace", str(tmp_path), "--site", "51job", "--command", "search",
            "--exit-code", "0", "--stdout-file", str(tmp_path / "nope.json"),
        ])
        assert rc == 2
        assert not (tmp_path / "journal.jsonl").exists()


    def test_read_adapter_calls_skips_receipts_and_surfaces_bad_lines(tmp_path):
        (tmp_path / "journal.jsonl").write_text(
            json.dumps({"action": "adapter_call", "site": "51job",
                        "command": "search", "exit_code": 0}) + "\n"
            + json.dumps({"action": "gate", "gate": "check_shortlist",
                          "verdict": "pass"}) + "\n"
            + "{not json at all}\n",
            encoding="utf-8",
        )
        calls = coc.read_adapter_calls(tmp_path)
        assert [c["site"] for c in calls] == ["51job"]
        assert calls[0]["_lineno"] == 1

        records = coc.read_journal(tmp_path)
        assert len(records) == 3
        assert records[2]["_unparsable"] == "{not json at all}"
        assert records[2]["_lineno"] == 3
    ```

- [ ] **Step 4: Run the test to verify it fails**

    Run: `python3 -m pytest scripts/tests/test_check_opencli_result.py -q`
    Expected: FAIL — collection error `ModuleNotFoundError: No module named 'check_opencli_result'`

- [ ] **Step 5: Write the implementation**

    Create `scripts/check_opencli_result.py`:

    ```python
    #!/usr/bin/env python3
    """Classify one opencli adapter invocation. A wrapper, not a gate.

    Exit codes here are deliberately NOT the gate contract:
      0 = classified; one JSON object printed to stdout
      2 = could not classify (workspace or stdout file missing)
    A `not_logged_in` adapter is information the discover mode acts on, not a
    failure of the run, so it must not exit 1.

    THE ONE RULE: branch on the exit code BEFORE interpreting stdout. A login wall
    gives exit 1, EMPTY stdout and a YAML error body on stderr even under -f json
    (measured 2026-08-09 on 1point3acres), so `JSON.parse(stdout || '[]')` silently
    converts a 403 into a zero-result success.
    """
    from __future__ import annotations

    import argparse
    import datetime as _dt
    import json
    import pathlib
    import re
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

    import yaml  # noqa: E402

    import journal  # noqa: E402  (Plan 1)
    import paths    # noqa: E402  (Plan 1)  — SKILL_ROOT lives here, not in __file__ math

    ADAPTER_CALL_ACTION = "adapter_call"

    CLASSIFICATIONS = ("ok", "platform_limit", "not_logged_in", "no_auth_adapter",
                       "transport")

    # The column that makes a search row self-sufficient. Measured from
    # `opencli <site> --help -f yaml` columns on 2026-08-09: boss calls it `name`,
    # everyone else calls it `title`.
    IDENTITY_FIELD = {"boss": "name"}
    IDENTITY_FIELD_DEFAULT = "title"

    # The documented command that recovers a row whose identity field came back
    # empty. Measured from the same help output.
    DETAIL_COMMAND = {
        "51job": "opencli 51job detail <jobId>",
        "indeed": "opencli indeed job <id>",
        "boss": "opencli boss detail <security_id>",
        "linkedin": "opencli linkedin job-detail <job-url>",
        "upwork": "opencli upwork detail <id>",
        "nowcoder": "opencli nowcoder detail <id>",
        "1point3acres": "opencli 1point3acres thread <tid>",
    }

    # A refusal that means "you are not signed in". Checked BEFORE the risk-control
    # signals so that the measured 403 resolves against `opencli auth status`
    # rather than being swallowed as a generic platform limit.
    LOGIN_WALL_PATTERNS = (
        re.compile(r"HTTP 40[13]\b"),
        re.compile(r"\bForbidden\b", re.I),
        re.compile(r"\bUnauthorized\b", re.I),
        re.compile(r"需要登录"),
        re.compile(r"\blogin required\b", re.I),
        re.compile(r"\bnot logged in\b", re.I),
    )

    DEFAULT_SIGNALS_FILE = paths.SKILL_ROOT / "references" / "risk-control-signals.yaml"


    def load_signals(path):
        """Compile references/risk-control-signals.yaml into matchers."""
        if path is None or not pathlib.Path(path).is_file():
            return []
        data = yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8")) or {}
        out = []
        for entry in data.get("signals") or []:
            pattern = entry.get("pattern")
            if not pattern:
                continue
            out.append({
                "id": entry.get("id") or pattern,
                "site": entry.get("site") or "*",
                "verified": bool(entry.get("verified")),
                "regex": re.compile(pattern),
            })
        return out


    def _auth_state(site, auth_rows):
        """'logged_in' | 'not_logged_in' | 'unknown' | 'absent' | 'unchecked'.

        Never reads row['logged_in']: on an `unknown` row that field is an EMPTY
        STRING, not false, so `if not row['logged_in']` misreads it as logged out.
        """
        if auth_rows is None:
            return "unchecked"
        for row in auth_rows:
            if isinstance(row, dict) and row.get("site") == site:
                status = row.get("status")
                if status in ("logged_in", "not_logged_in", "unknown"):
                    return status
                return "unknown"
        return "absent"


    def _error_message(stderr_text):
        text = (stderr_text or "").strip()
        if not text:
            return ""
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError:
            return text
        if isinstance(parsed, dict):
            err = parsed.get("error")
            if isinstance(err, dict) and err.get("message"):
                return str(err["message"])
        return text


    def classify(site, command, exit_code, stdout_text, stderr_text,
                 auth_rows=None, signals=()):
        """Classify one invocation. Returns a JSON-serialisable dict."""
        result = {
            "site": site,
            "command": command,
            "exit_code": exit_code,
            "classification": None,
            "row_count": 0,
            "empty_result": False,
            "identity_field": IDENTITY_FIELD.get(site, IDENTITY_FIELD_DEFAULT),
            "empty_identity_rows": [],
            "needs_detail_recovery": False,
            "detail_command": DETAIL_COMMAND.get(site),
            "auth_state": _auth_state(site, auth_rows),
            "signal_id": None,
            "error_message": None,
            "remedy": None,
        }

        # ---- exit code first, always -------------------------------------
        if exit_code != 0:
            message = _error_message(stderr_text)
            result["error_message"] = message

            if any(p.search(message) for p in LOGIN_WALL_PATTERNS):
                state = result["auth_state"]
                if state == "absent":
                    result["classification"] = "no_auth_adapter"
                    result["remedy"] = (
                        f"{site} has no auth adapter — it is absent from "
                        f"`opencli auth status` and `opencli {site} login` does not "
                        "exist. This is the platform refusing, not a session "
                        "problem: treat the site as unavailable for this round."
                    )
                elif state == "logged_in":
                    result["classification"] = "platform_limit"
                    result["remedy"] = (
                        "auth status says logged_in and the site still refused. "
                        "Treat it as a platform control. Stop this site for this "
                        "round: do not retry, do not change parameters and retry, "
                        "do not route around it."
                    )
                elif state == "unknown":
                    result["classification"] = "not_logged_in"
                    result["remedy"] = (
                        "auth status returned `unknown` (its logged_in field is an "
                        "EMPTY STRING, not false). Re-probe before concluding "
                        f"anything: opencli auth status --site {site} --full "
                        "--timeout 40 -f json, then classify again."
                    )
                else:
                    result["classification"] = "not_logged_in"
                    result["remedy"] = (
                        f"Hand `opencli {site} login` to the user to run — it is a "
                        "write command and this skill never runs one. Do not retry "
                        "the read: the refusal is deterministic while logged out."
                    )
                    if state == "unchecked":
                        result["remedy"] += (
                            " Auth state was not supplied; run `opencli auth status "
                            f"--site {site} --full -f json` first."
                        )
                return result

            # Matched against the WHOLE stderr of the failed call, not just the
            # message we extracted from it. `references/risk-control-signals.yaml`
            # states the rule that way for a reason: a real risk-control body puts
            # the wall in a `body:`/`detail:` field while `message:` stays generic,
            # and a search over `message` alone would classify that as `transport`
            # and let the round carry on. Searching stderr cannot cry wolf either —
            # a successful call has EMPTY stderr, and we are already inside the
            # `exit_code != 0` branch.
            haystack = f"{message}\n{stderr_text or ''}"
            for signal in signals:
                if signal["site"] in ("*", site) and signal["regex"].search(haystack):
                    result["classification"] = "platform_limit"
                    result["signal_id"] = signal["id"]
                    result["remedy"] = (
                        f"platform stop-signal {signal['id']!r} matched. Stop this "
                        "site for this round: do not retry, do not change "
                        "parameters and retry, do not route around it. Output the "
                        "direction-level degraded shortlist with its disclosure "
                        "block."
                    )
                    return result

            result["classification"] = "transport"
            result["remedy"] = (
                "unrecognised failure. Run `opencli doctor` before concluding this "
                "adapter is broken — a dead browser bridge takes out every "
                "browser:true command on every site at once."
            )
            return result

        # ---- exit 0: only NOW may stdout be interpreted -------------------
        try:
            rows = json.loads(stdout_text)
        except (json.JSONDecodeError, TypeError):
            result["classification"] = "transport"
            result["remedy"] = (
                "exit 0 but stdout is not JSON. Re-run with --trace on and check "
                "`opencli doctor`."
            )
            return result
        if not isinstance(rows, list):
            result["classification"] = "transport"
            result["remedy"] = "exit 0 but stdout was not a JSON array"
            return result

        result["classification"] = "ok"
        result["row_count"] = len(rows)
        result["empty_result"] = not rows

        field = result["identity_field"]
        result["empty_identity_rows"] = [
            index for index, row in enumerate(rows)
            if not isinstance(row, dict) or not str(row.get(field, "")).strip()
        ]
        if result["empty_identity_rows"]:
            result["needs_detail_recovery"] = True
            result["remedy"] = (
                f"{len(result['empty_identity_rows'])} of {len(rows)} rows came back "
                f"with an empty `{field}`. Recover each one with "
                f"`{result['detail_command']}` and report the gap. The rows exist — "
                "never read blank fields as 'this site has no such jobs'."
            )
        return result


    def read_journal(workspace):
        """Every journal line, in order, each carrying `_lineno`.

        An unparsable line comes back as {"_lineno": n, "_unparsable": raw} rather
        than being dropped: a write command hidden in a malformed line must stay
        visible to check_no_write.py.
        """
        path = pathlib.Path(workspace) / "journal.jsonl"
        if not path.is_file():
            return []
        records = []
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, raw in enumerate(text.splitlines(), start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                records.append({"_lineno": lineno, "_unparsable": stripped})
                continue
            if not isinstance(record, dict):
                records.append({"_lineno": lineno, "_unparsable": stripped})
                continue
            record["_lineno"] = lineno
            records.append(record)
        return records


    def read_adapter_calls(workspace):
        return [r for r in read_journal(workspace)
                if r.get("action") == ADAPTER_CALL_ACTION]


    def main(argv=None):
        parser = argparse.ArgumentParser(
            description="Classify one opencli adapter invocation (wrapper, not a gate)."
        )
        parser.add_argument("--workspace", required=True, type=pathlib.Path)
        parser.add_argument("--site", required=True)
        parser.add_argument("--command", required=True)
        parser.add_argument("--exit-code", required=True, type=int)
        parser.add_argument("--stdout-file", required=True, type=pathlib.Path)
        parser.add_argument("--stderr-file", type=pathlib.Path)
        parser.add_argument("--auth-status-file", type=pathlib.Path)
        parser.add_argument("--signals-file", type=pathlib.Path,
                            default=DEFAULT_SIGNALS_FILE)
        parser.add_argument("--command-line", default="")
        args = parser.parse_args(argv)

        if not args.workspace.is_dir():
            print(f"workspace not found: {args.workspace}", file=sys.stderr)
            return 2
        if args.exit_code == 0 and not args.stdout_file.is_file():
            print(f"stdout file not found: {args.stdout_file}", file=sys.stderr)
            return 2

        stdout_text = (args.stdout_file.read_text(encoding="utf-8", errors="replace")
                       if args.stdout_file.is_file() else "")
        stderr_text = ""
        if args.stderr_file and args.stderr_file.is_file():
            stderr_text = args.stderr_file.read_text(encoding="utf-8", errors="replace")

        auth_rows = None
        if args.auth_status_file and args.auth_status_file.is_file():
            try:
                loaded = json.loads(args.auth_status_file.read_text(encoding="utf-8"))
                auth_rows = loaded if isinstance(loaded, list) else None
            except json.JSONDecodeError:
                auth_rows = None

        result = classify(args.site, args.command, args.exit_code, stdout_text,
                          stderr_text, auth_rows, load_signals(args.signals_file))

        record = dict(result)
        record["action"] = ADAPTER_CALL_ACTION
        record["ts"] = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        record["stdout_file"] = str(args.stdout_file)
        record["stderr_file"] = str(args.stderr_file) if args.stderr_file else None
        record["command_line"] = args.command_line
        journal.append(args.workspace, record)

        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0


    if __name__ == "__main__":
        raise SystemExit(main())
    ```

- [ ] **Step 6: Run the test to verify it passes**

    Run: `python3 -m pytest scripts/tests/test_check_opencli_result.py -q`
    Expected: PASS (16 passed)

- [ ] **Step 7: Commit**

    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add references/risk-control-signals.yaml scripts/check_opencli_result.py \
            scripts/tests/conftest.py scripts/tests/test_check_opencli_result.py
    git commit -m "discover: classify one opencli invocation, exit code first

Wraps a single adapter call into {ok, platform_limit, not_logged_in,
no_auth_adapter, transport} and one adapter_call line in journal.jsonl.
A login wall gives exit 1 + EMPTY stdout + a YAML body on stderr even
under -f json, so stdout is never interpreted before the exit code.
Risk-control patterns are matched only against a failed call's stderr,
which is empty on success, so they cannot fire on job rows."
    ```

---

### Task 2: read/write authority from opencli's own metadata

**Files:**
- Create: `scripts/opencli_meta.py`
- Create: `scripts/check_no_write.py`
- Test: `scripts/tests/test_check_no_write.py`

**Interfaces:**
- Consumes:
  - `journal.receipt(workspace, gate, input_hashes, verdict, findings=None) -> dict` (Plan 1)
  - `journal.sha256_file(path) -> str` (Plan 1)
  - `check_opencli_result.read_journal(workspace) -> list[dict]` (Task 1)
  - `check_opencli_result.ADAPTER_CALL_ACTION` (Task 1)
- Produces:
  - `opencli_meta.MetadataUnavailable` (Exception)
  - `opencli_meta.load_site_metadata(site: str, cache_dir=None, allow_fetch=True) -> dict[str, dict]` — keyed by command name **and** every alias
  - `opencli_meta.access_for(site: str, command: str, cache_dir=None, allow_fetch=True) -> str | None`
  - `check_no_write.parse_command_line(text: str) -> tuple[str, str] | None`
  - `check_no_write.resolve_access(site, command, cache_dir, allow_fetch) -> str | None`
  - `check_no_write.scan(records, cache_dir, allow_fetch) -> list[str]`
  - `check_no_write.main(argv=None) -> int`

- [ ] **Step 1: Write the failing test**

    Create `scripts/tests/test_check_no_write.py`:

    ```python
    """Tests for scripts/check_no_write.py.

    The authority for read/write is opencli's OWN published `access:` field, not a
    list we maintain — a maintained list goes stale the day a new command ships and
    the staleness is invisible. These fixtures are trimmed copies of real
    `opencli <site> --help -f yaml` output from 2026-08-09.
    """
    import json

    import check_no_write as cnw

    BOSS_HELP = """site: boss
    command_count: 5
    commands:
      - name: search
        access: read
      - name: detail
        access: read
      - name: greet
        access: write
      - name: batchgreet
        access: write
      - name: login
        access: write
    """

    INDEED_HELP = """site: indeed
    command_count: 2
    commands:
      - name: job
        access: read
        aliases:
          - detail
          - view
      - name: search
        access: read
    """

    JOB51_HELP = """site: 51job
    command_count: 2
    commands:
      - name: search
        access: read
      - name: detail
        access: read
    """


    def build(tmp_path, records):
        cache = tmp_path / "raw" / "opencli-help"
        cache.mkdir(parents=True)
        (cache / "boss.yaml").write_text(BOSS_HELP, encoding="utf-8")
        (cache / "indeed.yaml").write_text(INDEED_HELP, encoding="utf-8")
        (cache / "51job.yaml").write_text(JOB51_HELP, encoding="utf-8")
        with (tmp_path / "journal.jsonl").open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return tmp_path


    def run(tmp_path):
        return cnw.main(["--workspace", str(tmp_path), "--no-fetch"])


    CLEAN = [
        {"action": "adapter_call", "site": "51job", "command": "search",
         "exit_code": 0, "classification": "ok",
         "command_line": "opencli 51job search 算法工程师 --limit 20 -f json"},
        {"action": "adapter_call", "site": "51job", "command": "detail",
         "exit_code": 0, "classification": "ok",
         "command_line": "opencli 51job detail 173199597 -f json"},
        {"action": "adapter_call", "site": "indeed", "command": "detail",
         "exit_code": 0, "classification": "ok",
         "command_line": "opencli indeed detail 152875498075cf99 -f json"},
        {"action": "tool_call",
         "command_line": "opencli auth status --site boss,linkedin -f json"},
        {"action": "tool_call", "command_line": "opencli boss --help -f yaml"},
        {"action": "gate", "gate": "check_shortlist", "verdict": "pass"},
    ]


    def test_a_read_only_journal_is_completely_quiet(tmp_path, capsys):
        build(tmp_path, CLEAN)
        assert run(tmp_path) == 0
        assert capsys.readouterr().out == ""


    def test_alias_resolves_to_its_canonical_read_command(tmp_path):
        # `indeed detail` is an ALIAS of `indeed job`; only the canonical entry
        # carries access:. Resolving via the alias must not fail closed.
        build(tmp_path, CLEAN)
        assert cnw.resolve_access(
            "indeed", "detail", tmp_path / "raw" / "opencli-help", False) == "read"


    def test_greet_recorded_as_an_adapter_call_fails(tmp_path, capsys):
        build(tmp_path, CLEAN + [
            {"action": "adapter_call", "site": "boss", "command": "greet",
             "exit_code": 0, "classification": "ok"},
        ])
        assert run(tmp_path) == 1
        out = capsys.readouterr().out
        assert out.startswith("WRITE_COMMAND:")
        assert "opencli boss greet" in out
        assert "access: write" in out


    def test_greet_hidden_in_a_command_line_only_record_fails(tmp_path, capsys):
        build(tmp_path, CLEAN + [
            {"action": "note",
             "command_line": "opencli boss greet --job-id abc --text 'hello'"},
        ])
        assert run(tmp_path) == 1
        assert "WRITE_COMMAND:" in capsys.readouterr().out


    def test_profile_prefix_does_not_hide_a_write(tmp_path, capsys):
        build(tmp_path, CLEAN + [
            {"action": "note",
             "command_line": "opencli --profile n4drczmg boss batchgreet --limit 5"},
        ])
        assert run(tmp_path) == 1
        assert "opencli boss batchgreet" in capsys.readouterr().out


    def test_an_unknown_site_fails_closed(tmp_path, capsys):
        build(tmp_path, CLEAN + [
            {"action": "adapter_call", "site": "zhilian", "command": "search",
             "exit_code": 0, "classification": "ok"},
        ])
        assert run(tmp_path) == 1
        out = capsys.readouterr().out
        assert "UNKNOWN_ACCESS:" in out
        assert "opencli zhilian search" in out


    def test_auth_refresh_is_not_silently_allowed(tmp_path, capsys):
        # The `auth` namespace publishes NO access: field, so only `auth status`
        # is allow-listed. Anything else in that namespace fails closed.
        build(tmp_path, CLEAN + [
            {"action": "note", "command_line": "opencli auth refresh --all"},
        ])
        assert run(tmp_path) == 1
        assert "UNKNOWN_ACCESS:" in capsys.readouterr().out


    def test_an_unparsable_journal_line_is_reported(tmp_path, capsys):
        build(tmp_path, CLEAN)
        with (tmp_path / "journal.jsonl").open("a", encoding="utf-8") as handle:
            handle.write("{ this is not json\n")
        assert run(tmp_path) == 1
        assert "UNPARSABLE_JOURNAL_LINE:" in capsys.readouterr().out


    def test_missing_journal_exits_2_and_still_leaves_a_receipt(tmp_path, capsys):
        # Exit-2 discipline: the workspace exists, so exactly one receipt is
        # written, with verdict could_not_run. A gate that exits silently is
        # indistinguishable from a gate nobody ran.
        (tmp_path / "raw" / "opencli-help").mkdir(parents=True)
        assert run(tmp_path) == 2
        assert "journal.jsonl" in capsys.readouterr().err
        lines = (tmp_path / "journal.jsonl").read_text(
            encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        receipt = json.loads(lines[0])
        assert receipt["gate"] == "check_no_write"
        assert receipt["verdict"] == "could_not_run"


    def test_a_missing_workspace_directory_exits_2_with_no_receipt(tmp_path, capsys):
        # The ONE case with no receipt: there is no directory to append to. The
        # gate's docstring says so, and this pins it, so the two exit-2 shapes
        # stay distinguishable to whoever reads the journal afterwards.
        missing = tmp_path / "nope"
        assert cnw.main(["--workspace", str(missing), "--no-fetch"]) == 2
        assert "workspace not found" in capsys.readouterr().err
        assert not missing.exists()


    def test_exactly_one_receipt_is_appended(tmp_path):
        build(tmp_path, CLEAN)
        before = len((tmp_path / "journal.jsonl").read_text(
            encoding="utf-8").strip().splitlines())
        assert run(tmp_path) == 0
        lines = (tmp_path / "journal.jsonl").read_text(
            encoding="utf-8").strip().splitlines()
        assert len(lines) == before + 1
        receipt = json.loads(lines[-1])
        assert receipt["action"] == "gate"
        assert receipt["gate"] == "check_no_write"
        assert receipt["verdict"] == "pass"


    def test_parse_command_line_edge_cases():
        assert cnw.parse_command_line(
            "opencli 51job search 算法工程师 --limit 2") == ("51job", "search")
        assert cnw.parse_command_line("opencli boss --help -f yaml") is None
        assert cnw.parse_command_line("opencli auth status -f json") == ("auth", "status")
        assert cnw.parse_command_line("python3 scripts/check_shortlist.py") is None
        assert cnw.parse_command_line("") is None
        assert cnw.parse_command_line(
            "/Users/x/.local/bin/opencli boss greet") == ("boss", "greet")
    ```

- [ ] **Step 2: Run the test to verify it fails**

    Run: `python3 -m pytest scripts/tests/test_check_no_write.py -q`
    Expected: FAIL — collection error `ModuleNotFoundError: No module named 'check_no_write'`

- [ ] **Step 3: Write the metadata reader**

    Create `scripts/opencli_meta.py`:

    ```python
    #!/usr/bin/env python3
    """Read opencli's OWN published command metadata.

    `opencli <site> --help -f yaml` emits, per command: name, access (read|write),
    aliases, columns, options. That `access:` field is the authority this skill
    uses to decide whether a command was a read. A list WE maintain would go stale
    the day a new command ships, and nothing would report the staleness.
    """
    from __future__ import annotations

    import pathlib
    import shutil
    import subprocess

    import yaml


    class MetadataUnavailable(Exception):
        """The tool did not tell us; the caller must fail closed."""


    def _help_yaml(site, cache_dir, allow_fetch, timeout=60):
        if cache_dir is not None:
            cached = pathlib.Path(cache_dir) / f"{site}.yaml"
            if cached.is_file():
                return cached.read_text(encoding="utf-8")
        if not allow_fetch:
            raise MetadataUnavailable(
                f"no cached metadata for {site!r} and fetching is disabled")
        binary = shutil.which("opencli")
        if binary is None:
            raise MetadataUnavailable("opencli is not on PATH")
        try:
            proc = subprocess.run([binary, site, "--help", "-f", "yaml"],
                                  capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.SubprocessError) as exc:
            raise MetadataUnavailable(str(exc)) from exc
        if proc.returncode != 0 or not proc.stdout.strip():
            raise MetadataUnavailable(
                f"`opencli {site} --help -f yaml` exited {proc.returncode}")
        return proc.stdout


    def load_site_metadata(site, cache_dir=None, allow_fetch=True):
        """{command-or-alias: {"name": canonical, "access": "read"|"write"|None}}."""
        text = _help_yaml(site, cache_dir, allow_fetch)
        try:
            doc = yaml.safe_load(text) or {}
        except yaml.YAMLError as exc:
            raise MetadataUnavailable(f"{site}: help yaml did not parse: {exc}") from exc
        table = {}
        for command in doc.get("commands") or []:
            if not isinstance(command, dict):
                continue
            name = command.get("name")
            if not name:
                continue
            entry = {"name": name, "access": command.get("access")}
            table[name] = entry
            for alias in command.get("aliases") or []:
                table[alias] = entry
        if not table:
            raise MetadataUnavailable(f"{site}: help yaml listed no commands")
        return table


    def access_for(site, command, cache_dir=None, allow_fetch=True):
        """"read" | "write" | None. None means the tool did not tell us."""
        try:
            table = load_site_metadata(site, cache_dir, allow_fetch)
        except MetadataUnavailable:
            return None
        entry = table.get(command)
        if entry is None:
            return None
        access = entry.get("access")
        return access if access in ("read", "write") else None
    ```

- [ ] **Step 4: Write the gate**

    Create `scripts/check_no_write.py`:

    ```python
    #!/usr/bin/env python3
    """Gate: no write command was run (spec D7, risk register row 13).

    A greeting that went out cannot be recalled and leaves no local trace, so the
    guard has to be an after-the-fact scan against the tool's own metadata.

    KNOWN BOUND, stated rather than papered over: this gate can only see commands
    that were journaled. It proves nothing about a command nobody recorded. The
    load-bearing half of the guarantee is that no write command appears anywhere in
    this skill's instructions and every command the mode file names is access: read.

    Exit codes: 0 = passed, 1 = findings on stdout, 2 = could not run. On exit 2 one
    receipt with verdict "could_not_run" is appended — EXCEPT when the workspace
    directory itself does not exist, because then there is nothing to append to. If
    you find no receipt at all, that is the case you are in.
    """
    from __future__ import annotations

    import argparse
    import pathlib
    import shlex
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

    import journal  # noqa: E402  (Plan 1)
    import opencli_meta  # noqa: E402
    from check_opencli_result import ADAPTER_CALL_ACTION, read_journal  # noqa: E402

    GATE = "check_no_write"

    # opencli's non-adapter namespaces (`opencli auth --help -f yaml` returns
    # `namespace: auth` and publishes NO access: field). Only the commands this
    # skill actually needs are allow-listed; everything else in those namespaces
    # falls through to UNKNOWN_ACCESS and fails closed. Every genuine write command
    # in the toolset lives on an adapter, where the tool's own metadata governs.
    NON_ADAPTER_READS = {("auth", "status")}

    GLOBAL_VALUE_FLAGS = {"--profile"}


    def parse_command_line(text):
        """('boss', 'greet') from 'opencli boss greet --job-id X'; None otherwise.

        Site and command are the first two positional tokens and always precede any
        flag, so the scan stops at the first token starting with '-'. That means
        `opencli boss --help -f yaml` correctly yields None rather than ('boss',
        'yaml'). A command line that buries the site behind other leading flags will
        not be recognised — which is why the mode records site/command as structured
        fields and this parser is only the backstop.
        """
        if not text:
            return None
        try:
            tokens = shlex.split(text)
        except ValueError:
            tokens = text.split()
        tokens = [t for t in tokens if t]
        if not tokens:
            return None
        if pathlib.PurePath(tokens[0]).name != "opencli":
            return None
        rest = tokens[1:]
        while rest and rest[0] in GLOBAL_VALUE_FLAGS:
            rest = rest[2:]
        positional = []
        for token in rest:
            if token.startswith("-"):
                break
            positional.append(token)
        if len(positional) < 2:
            return None
        return positional[0], positional[1]


    def resolve_access(site, command, cache_dir, allow_fetch):
        if (site, command) in NON_ADAPTER_READS:
            return "read"
        return opencli_meta.access_for(site, command, cache_dir=cache_dir,
                                       allow_fetch=allow_fetch)


    def scan(records, cache_dir, allow_fetch):
        findings = []
        for record in records:
            lineno = record.get("_lineno")
            if "_unparsable" in record:
                findings.append(
                    f"UNPARSABLE_JOURNAL_LINE: journal.jsonl line {lineno} is not "
                    "JSON, so a command hidden in it cannot be checked")
                continue
            pairs = []
            if (record.get("action") == ADAPTER_CALL_ACTION
                    and record.get("site") and record.get("command")):
                pairs.append((str(record["site"]), str(record["command"])))
            parsed = parse_command_line(record.get("command_line") or "")
            if parsed and parsed not in pairs:
                pairs.append(parsed)
            for site, command in pairs:
                access = resolve_access(site, command, cache_dir, allow_fetch)
                if access == "write":
                    findings.append(
                        f"WRITE_COMMAND: journal.jsonl line {lineno} ran `opencli "
                        f"{site} {command}` — `opencli {site} --help -f yaml` "
                        "publishes access: write. This skill is read-only and has "
                        "no confirm-then-send path.")
                elif access is None:
                    findings.append(
                        f"UNKNOWN_ACCESS: journal.jsonl line {lineno} ran `opencli "
                        f"{site} {command}` — no access metadata available, so this "
                        "cannot be shown to be a read. Save `opencli {0} --help -f "
                        "yaml` into the metadata cache and re-run.".format(site))
        return findings


    def main(argv=None):
        parser = argparse.ArgumentParser(
            description="Gate: no opencli write command was run in this workspace.")
        parser.add_argument("--workspace", required=True, type=pathlib.Path)
        parser.add_argument("--metadata-cache", type=pathlib.Path,
                            help="default: <workspace>/raw/opencli-help")
        parser.add_argument("--no-fetch", action="store_true",
                            help="never shell out to opencli; use the cache only")
        args = parser.parse_args(argv)

        workspace = args.workspace
        if not workspace.is_dir():
            print(f"workspace not found: {workspace}", file=sys.stderr)
            return 2
        journal_path = workspace / "journal.jsonl"
        if not journal_path.is_file():
            journal.receipt(workspace, GATE, {}, "could_not_run",
                            [f"missing input: {journal_path}"])
            print(f"missing input: {journal_path}", file=sys.stderr)
            return 2

        cache_dir = args.metadata_cache or (workspace / "raw" / "opencli-help")
        findings = scan(read_journal(workspace), cache_dir, not args.no_fetch)

        input_hashes = {"journal.jsonl": journal.sha256_file(journal_path)}
        journal.receipt(workspace, GATE, input_hashes,
                        "fail" if findings else "pass", findings)
        for line in findings:
            print(line)
        return 1 if findings else 0


    if __name__ == "__main__":
        raise SystemExit(main())
    ```

- [ ] **Step 5: Run the test to verify it passes**

    Run: `python3 -m pytest scripts/tests/test_check_no_write.py -q`
    Expected: PASS (12 passed)

- [ ] **Step 6: Commit**

    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/opencli_meta.py scripts/check_no_write.py \
            scripts/tests/test_check_no_write.py
    git commit -m "discover: prove read-only from opencli's own access: metadata

check_no_write resolves every journaled invocation against
\`opencli <site> --help -f yaml\`, following aliases, and fails closed
when the tool does not publish an access field. The auth namespace
publishes none, so only \`auth status\` is allow-listed by name.
States its own bound: it cannot see a command nobody journaled."
    ```

---

### Task 3: shortlist gate — per-row provenance

**Files:**
- Create: `scripts/tests/discover_fixtures.py`
- Create: `scripts/check_shortlist.py`
- Test: `scripts/tests/test_check_shortlist_rows.py`

**Interfaces:**
- Consumes: `journal.receipt`, `journal.sha256_file` (Plan 1)
- Produces:
  - `check_shortlist.GATE: str` = `"check_shortlist"`
  - `check_shortlist.REQUIRED_ROW_FIELDS: tuple[str, ...]` — all **seventeen** row fields (Task 7's mode-file test imports this)
  - `check_shortlist.VERDICTS` and `check_shortlist.EFFORT` — **re-exported from `scripts/vocab.py`, not declared here**; plus `TOP_THREE` (`VERDICTS[:3]`, derived), `EXTRACTION_METHODS`, `QUALITIES`, `VERIFICATIONS`, `MIN_SOURCE_ID_LEN`
  - `check_shortlist.load_raw_texts(workspace) -> dict[str, dict[str, str]]` — `{site: {filename: text}}`
  - `check_shortlist.check_rows(shortlist: dict, raw_texts: dict) -> list[str]`
  - `check_shortlist.main(argv=None) -> int`
  - `discover_fixtures.build_workspace(root) -> pathlib.Path`, plus `load_shortlist/save_shortlist/load_brief/save_brief/write_md(ws, text)`

- [ ] **Step 1: Write the fixture builder**

    Create `scripts/tests/discover_fixtures.py`. This builds a **valid** workspace out of the real 51job rows captured on 2026-08-09; every test mutates exactly one thing away from valid, so if `build_workspace()` ever stops being clean, every test fails at once.

    ```python
    """A valid discover workspace, built from the real 2026-08-09 51job capture.

    Tests mutate exactly ONE thing away from valid. That makes the quiet case
    structural rather than aspirational: a gate that starts crying wolf on ordinary
    output breaks every test in both shortlist modules at once.
    """
    import json
    import pathlib

    import yaml

    RAW_51JOB_SEARCH = [
        {"rank": 1, "jobId": "173198362",
         "title": "高级算法工程师（视觉调试智能化、AI方向）", "salary": "3-6万",
         "salaryMin": 30000, "salaryMax": 60000, "city": "西安",
         "district": "高新技术产业开发区", "workYear": "3年及以上", "degree": "博士",
         "tags": "3年及以上,博士,c++,人工智能,图像处理,深度学习,opencv",
         "company": "比亚迪汽车工业", "companyFull": "比亚迪汽车工业有限公司",
         "companyType": "民营", "companySize": "10000人以上", "industry": "汽车",
         "hr": "王女士·行政实习生", "issueDate": "2026-08-08 10:23:15",
         "url": "https://jobs.51job.com/xian-gxjs/173198362.html?s=sou_sou_soulb&t=0_0",
         "companyUrl": "https://jobs.51job.com/all/coVDMHY1M0BDgAZ1c9AWVWZA.html",
         "encCoId": "VDMHY1M0BDgAZ1c9AWVWZA"},
        {"rank": 2, "jobId": "173199597", "title": "高级AI算法工程师(J10032)",
         "salary": "1.7-3.4万·15薪", "salaryMin": 17000, "salaryMax": 34000,
         "city": "海宁", "district": "", "workYear": "3年", "degree": "硕士",
         "tags": "3年,硕士,数字孪生,ai模型训练,ai算法,五险一金",
         "company": "拓荆键科（海宁）半导体设备",
         "companyFull": "拓荆键科（海宁）半导体设备有限公司", "companyType": "民营",
         "companySize": "150-500人", "industry": "电子技术/半导体/集成电路",
         "hr": "周女士·人事", "issueDate": "2026-08-08 14:34:16",
         "url": "https://jobs.51job.com/haining/173199597.html?s=sou_sou_soulb&t=0_0",
         "companyUrl": "https://jobs.51job.com/all/coUjJQPFY2DzYPaVQyVDI.html",
         "encCoId": "UjJQPFY2DzYPaVQyVDI"},
    ]

    RAW_51JOB_DETAIL = [
        {"jobId": "173199597", "title": "高级AI算法工程师(J10032)",
         "salary": "1.7-3.4万·15薪", "location": "海宁", "workYear": "3年",
         "degree": "硕士", "category": "算法工程师",
         "address": "浙江省海宁市经济开发区",
         "description": "负责数字孪生方向的 AI 算法研发；熟悉 Python/C++；有半导体设备经验优先。",
         "welfare": "五险一金 带薪年假 年终奖金",
         "company": "拓荆键科（海宁）半导体设备", "companyType": "民营",
         "companySize": "150-500人", "companyIndustry": "电子技术/半导体/集成电路",
         "url": "https://jobs.51job.com/haining/173199597.html"},
    ]

    # A trimmed copy of `opencli 51job --help -f yaml` so check_no_write can run
    # against this workspace without shelling out.
    HELP_51JOB = """site: 51job
    command_count: 4
    commands:
      - name: company
        access: read
      - name: detail
        access: read
      - name: hot
        access: read
      - name: search
        access: read
    """

    BRIEF = {
        "slug": "2026-08-09-suanfa-shanghai",
        "created": "2026-08-09",
        "trigger_reason": (
            "用户要求本轮检索：上一份 JD 被 assess 判为 likely_screen_out（缺 C++ 生产经验），"
            "因此在同方向上找更稳的岗位。本轮候选必须肉眼可见地比它更稳，而不只是标题相似。"),
        "target_titles": ["算法工程师", "algorithm engineer"],
        "markets": ["cn"],
        "locations": ["上海", "西安", "海宁"],
        "seniority": "mid",
        "employment_types": ["full_time"],
        "work_models": ["onsite", "hybrid"],
        "languages": ["Chinese", "English"],
        "must_have_constraints": ["work authorization: 中国公民，无需担保"],
        "nice_to_have": ["计算机视觉", "医疗影像"],
        "avoid": ["外包", "销售导向岗位"],
        "target_count": 2,
        "max_rows_per_round": 25,
        "max_pages_per_site": 2,
        "max_age_days": 30,
    }

    ROWS = [
        {"id": "51job-173198362",
         "title": "高级算法工程师（视觉调试智能化、AI方向）",
         "company": "比亚迪汽车工业",
         "location": "西安 · 高新技术产业开发区",
         "salary": "3-6万",
         "url": "https://jobs.51job.com/xian-gxjs/173198362.html",
         "source_site": "51job",
         "source_id": "173198362",
         "extraction_method": "adapter_search",
         "retrieved_at": "2026-08-09T14:02:11Z",
         "quality": "card_only",
         "verification": "collected_unverified",
         "raw_text": ("高级算法工程师（视觉调试智能化、AI方向） | 比亚迪汽车工业 | 西安 | "
                      "3-6万 | 博士 | 3年及以上 | c++,图像处理,深度学习,opencv"),
         "why_matched": ("brief.target_titles 命中「算法工程师」；raw salaryMin 30000 在 brief "
                         "薪资区间内；raw city 西安 在 brief.locations 内。raw degree 为「博士」，"
                         "档案为硕士，已计入分档。仅卡片信息，未取详情。"),
         "verdict": "worth_applying",
         "provisional": True,
         "effort": "evening"},
        {"id": "51job-173199597",
         "title": "高级AI算法工程师(J10032)",
         "company": "拓荆键科（海宁）半导体设备",
         "location": "海宁",
         "salary": "1.7-3.4万·15薪",
         "url": "https://jobs.51job.com/haining/173199597.html",
         "source_site": "51job",
         "source_id": "173199597",
         "extraction_method": "adapter_detail",
         "retrieved_at": "2026-08-09T14:03:40Z",
         "quality": "complete",
         "verification": "fresh_verified",
         "raw_text": ("高级AI算法工程师(J10032) | 拓荆键科（海宁）半导体设备 | 海宁 | "
                      "1.7-3.4万·15薪 | 硕士 | 3年 | 负责数字孪生方向的 AI 算法研发；"
                      "熟悉 Python/C++"),
         "why_matched": ("brief.target_titles 命中「算法工程师」；详情页 description 点名 "
                         "Python/C++ 与档案主线一致；raw degree 硕士 与档案一致。"),
         "verdict": "strong_apply",
         "provisional": True,
         "effort": "quick"},
    ]

    SHORTLIST = {
        "search_slug": "2026-08-09-suanfa-shanghai",
        "brief": "brief.yaml",
        "shortfall_reason": None,
        "detail_fetch_exceptions": [],
        "sources": [
            {"site": "51job",
             "command": "search",
             "access": "read",
             "login_state": "no_auth_adapter",
             "classification": "ok",
             "invocations": 1,
             "rows_returned": 2,
             "identity_field": "title",
             "identity_field_empty_rows": 0,
             "detail_command": "opencli 51job detail <jobId>",
             "raw_files": ["raw/51job-1.json", "raw/51job-detail-173199597.json"]},
        ],
        "rows": ROWS,
    }

    SHORTLIST_MD = """# Shortlist — 2026-08-09 · 算法工程师 · 上海/西安/海宁

    ## §0 来源与读取质量

    | site | command | access | 登录态 | 调用 | 返回行 | 标识字段 | 空标识行 | 详情命令 | 分类 |
    |---|---|---|---|---|---|---|---|---|---|
    | 51job | search | read | 无 auth adapter | 1 | 2 | `title` | 0 | `opencli 51job detail <jobId>` | ok |

    原始捕获：`raw/51job-1.json`、`raw/51job-detail-173199597.json`。
    每一行的来源终点都在这两个文件里；它们永不编辑。

    ## §0.1 触发原因

    上一份 JD 被 assess 判为 `likely_screen_out`（缺 C++ 生产经验），用户要求在同方向上
    找更稳的岗位。本轮候选必须肉眼可见地比它更稳，而不只是标题相似。

    ## §1 候选（全部为基于卡片信息的初判 · provisional）

    1. **高级AI算法工程师(J10032)** — 拓荆键科（海宁）半导体设备 · 海宁 · 1.7-3.4万·15薪
       — `strong_apply`（初判）
    2. **高级算法工程师（视觉调试智能化、AI方向）** — 比亚迪汽车工业 · 西安 · 3-6万
       — `worth_applying`（初判）· 未取详情
    """

    JOURNAL = [
        {"ts": "2026-08-09T14:02:11Z", "mode": "discover", "action": "adapter_call",
         "site": "51job", "command": "search", "exit_code": 0, "classification": "ok",
         "row_count": 2, "empty_result": False, "identity_field": "title",
         "empty_identity_rows": [], "needs_detail_recovery": False,
         "detail_command": "opencli 51job detail <jobId>", "auth_state": "absent",
         "signal_id": None, "error_message": None, "remedy": None,
         "stdout_file": "raw/51job-1.json", "stderr_file": "raw/51job-1.err",
         "command_line": ("opencli 51job search 算法工程师 --area 上海 --page 1 "
                          "--limit 25 --window background -f json")},
        {"ts": "2026-08-09T14:03:40Z", "mode": "discover", "action": "adapter_call",
         "site": "51job", "command": "detail", "exit_code": 0, "classification": "ok",
         "row_count": 1, "empty_result": False, "identity_field": "title",
         "empty_identity_rows": [], "needs_detail_recovery": False,
         "detail_command": "opencli 51job detail <jobId>", "auth_state": "absent",
         "signal_id": None, "error_message": None, "remedy": None,
         "stdout_file": "raw/51job-detail-173199597.json", "stderr_file": None,
         "command_line": ("opencli 51job detail 173199597 --window background "
                          "-f json")},
    ]


    def _dump_yaml(path, data):
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                        encoding="utf-8")


    def build_workspace(root):
        """Create a VALID search workspace under `root` and return its path."""
        import textwrap
        workspace = pathlib.Path(root) / "2026-08-09-suanfa-shanghai"
        (workspace / "raw" / "opencli-help").mkdir(parents=True)
        (workspace / "raw" / "51job-1.json").write_text(
            json.dumps(RAW_51JOB_SEARCH, ensure_ascii=False, indent=2), encoding="utf-8")
        (workspace / "raw" / "51job-detail-173199597.json").write_text(
            json.dumps(RAW_51JOB_DETAIL, ensure_ascii=False, indent=2), encoding="utf-8")
        (workspace / "raw" / "51job-1.err").write_text("", encoding="utf-8")
        (workspace / "raw" / "opencli-help" / "51job.yaml").write_text(
            textwrap.dedent(HELP_51JOB), encoding="utf-8")
        _dump_yaml(workspace / "brief.yaml", BRIEF)
        _dump_yaml(workspace / "shortlist.yaml", SHORTLIST)
        (workspace / "shortlist.md").write_text(
            textwrap.dedent(SHORTLIST_MD), encoding="utf-8")
        with (workspace / "journal.jsonl").open("w", encoding="utf-8") as handle:
            for record in JOURNAL:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return workspace


    def load_shortlist(workspace):
        return yaml.safe_load((workspace / "shortlist.yaml").read_text(encoding="utf-8"))


    def save_shortlist(workspace, data):
        _dump_yaml(workspace / "shortlist.yaml", data)


    def load_brief(workspace):
        return yaml.safe_load((workspace / "brief.yaml").read_text(encoding="utf-8"))


    def save_brief(workspace, data):
        _dump_yaml(workspace / "brief.yaml", data)


    def write_md(workspace, text):
        (workspace / "shortlist.md").write_text(text, encoding="utf-8")


    def write_journal(workspace, records):
        with (workspace / "journal.jsonl").open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    ```

- [ ] **Step 2: Write the failing test**

    Create `scripts/tests/test_check_shortlist_rows.py`:

    ```python
    """Per-row provenance tests for scripts/check_shortlist.py.

    Risk register row 1: a fabricated shortlist is internally consistent, perfectly
    formatted, and every field has the right shape. The one thing a fabricated row
    cannot do is appear in raw/ — so that is what is checked, verbatim, per row.
    """
    import check_shortlist as cs
    import discover_fixtures as fx


    def run(workspace, capsys):
        code = cs.main(["--workspace", str(workspace)])
        return code, capsys.readouterr()


    def codes(out):
        return sorted({line.split(":", 1)[0] for line in out.strip().splitlines() if line})


    def test_the_valid_workspace_is_completely_quiet(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        code, captured = run(workspace, capsys)
        assert code == 0
        assert captured.out == ""


    def test_source_id_absent_from_raw_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        data = fx.load_shortlist(workspace)
        data["rows"][0]["source_id"] = "999999999"
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "SOURCE_ID_NOT_IN_RAW" in codes(captured.out)
        assert "51job-1.json" in captured.out


    def test_a_short_source_id_is_rejected_before_the_substring_search(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        data = fx.load_shortlist(workspace)
        data["rows"][0]["source_id"] = "17"      # would match almost any capture
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "SUSPICIOUS_SOURCE_ID" in codes(captured.out)


    def test_a_site_with_no_raw_capture_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        data = fx.load_shortlist(workspace)
        row = dict(data["rows"][0])
        row.update({"id": "linkedin-1", "source_site": "linkedin",
                    "source_id": "3812345678",
                    "url": "https://www.linkedin.com/jobs/view/3812345678/"})
        data["rows"].append(row)
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "NO_RAW_CAPTURE_FOR_SITE" in codes(captured.out)
        # Reported once, not twice: no SOURCE_ID_NOT_IN_RAW piled on top.
        assert "SOURCE_ID_NOT_IN_RAW" not in codes(captured.out)


    def test_an_invented_url_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        data = fx.load_shortlist(workspace)
        data["rows"][0]["url"] = "https://jobs.51job.com/shanghai/173198362.html"
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "URL_NOT_FROM_ADAPTER" in codes(captured.out)


    def test_the_full_url_with_tracking_params_is_quiet(tmp_path, capsys):
        # Storing either the trimmed url or the adapter's full one must pass;
        # stripping tracking parameters is not evidence of fabrication.
        workspace = fx.build_workspace(tmp_path)
        data = fx.load_shortlist(workspace)
        data["rows"][0]["url"] = (
            "https://jobs.51job.com/xian-gxjs/173198362.html?s=sou_sou_soulb&t=0_0")
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 0
        assert captured.out == ""


    def test_empty_title_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        data = fx.load_shortlist(workspace)
        data["rows"][0]["title"] = ""
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "EMPTY_TITLE" in codes(captured.out)


    def test_missing_why_matched_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        data = fx.load_shortlist(workspace)
        data["rows"][1]["why_matched"] = "   "
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "NO_WHY_MATCHED" in codes(captured.out)


    def test_missing_retrieved_at_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        data = fx.load_shortlist(workspace)
        del data["rows"][0]["retrieved_at"]
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "NO_RETRIEVED_AT" in codes(captured.out)
        assert "MISSING_FIELD" in codes(captured.out)


    def test_missing_source_site_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        data = fx.load_shortlist(workspace)
        data["rows"][0]["source_site"] = ""
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "NO_SOURCE_SITE" in codes(captured.out)


    def test_a_verdict_outside_the_five_levels_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        data = fx.load_shortlist(workspace)
        data["rows"][0]["verdict"] = "maybe"
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "BAD_VERDICT" in codes(captured.out)
        assert "strong_apply" in captured.out


    def test_a_missing_provisional_stamp_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        data = fx.load_shortlist(workspace)
        data["rows"][0]["provisional"] = False
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "MISSING_PROVISIONAL" in codes(captured.out)
        assert "may not be rendered" in captured.out


    def test_a_bad_enum_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        data = fx.load_shortlist(workspace)
        data["rows"][0]["extraction_method"] = "screenshot"
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "BAD_ENUM" in codes(captured.out)


    def test_a_bad_effort_value_fires(tmp_path, capsys):
        # effort is what makes D3's "within a band, order by effort-to-close"
        # implementable instead of merely stated, so it is enum-checked like the
        # rest rather than left as free text nobody can sort on.
        workspace = fx.build_workspace(tmp_path)
        data = fx.load_shortlist(workspace)
        data["rows"][0]["effort"] = "a weekend maybe"
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "BAD_ENUM" in codes(captured.out)
        assert "not_closable" in captured.out


    def test_a_duplicated_source_id_fires(tmp_path, capsys):
        # Count conservation from the row side: one retrieved posting may not be
        # listed twice to pad the shortlist toward target_count.
        import copy
        workspace = fx.build_workspace(tmp_path)
        data = fx.load_shortlist(workspace)
        clone = copy.deepcopy(data["rows"][0])
        clone["id"] = "51job-173198362-b"
        data["rows"].append(clone)
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "DUPLICATE_SOURCE_ID" in codes(captured.out)


    def test_the_row_vocabulary_is_the_one_in_scripts_vocab(tmp_path):
        # R1: no closed set is spelled out twice. If check_shortlist ever grows its
        # own copy of the verdicts, this fails rather than drifting quietly.
        import vocab
        assert cs.VERDICTS is vocab.VERDICTS
        assert cs.EFFORT is vocab.EFFORT
        assert cs.TOP_THREE == ("strong_apply", "worth_applying", "stretch")
        assert len(cs.REQUIRED_ROW_FIELDS) == 17
        assert "effort" in cs.REQUIRED_ROW_FIELDS


    def test_a_missing_shortlist_exits_2_and_still_leaves_a_receipt(tmp_path, capsys):
        import json
        workspace = fx.build_workspace(tmp_path)
        before = len((workspace / "journal.jsonl").read_text(
            encoding="utf-8").strip().splitlines())
        (workspace / "shortlist.yaml").unlink()
        code, captured = run(workspace, capsys)
        assert code == 2
        assert "shortlist.yaml" in captured.err
        lines = (workspace / "journal.jsonl").read_text(
            encoding="utf-8").strip().splitlines()
        assert len(lines) == before + 1
        receipt = json.loads(lines[-1])
        assert receipt["gate"] == "check_shortlist"
        assert receipt["verdict"] == "could_not_run"


    def test_a_missing_workspace_directory_exits_2_with_no_receipt(tmp_path, capsys):
        missing = tmp_path / "nope"
        assert cs.main(["--workspace", str(missing)]) == 2
        assert "workspace not found" in capsys.readouterr().err
        assert not missing.exists()


    def test_a_receipt_is_written_on_pass_and_on_fail(tmp_path, capsys):
        import json
        workspace = fx.build_workspace(tmp_path)
        assert cs.main(["--workspace", str(workspace)]) == 0
        capsys.readouterr()
        receipt = json.loads((workspace / "journal.jsonl").read_text(
            encoding="utf-8").strip().splitlines()[-1])
        assert receipt["gate"] == "check_shortlist"
        assert receipt["verdict"] == "pass"
        assert "shortlist.yaml" in receipt["input_hashes"]

        data = fx.load_shortlist(workspace)
        data["rows"][0]["source_id"] = "999999999"
        fx.save_shortlist(workspace, data)
        assert cs.main(["--workspace", str(workspace)]) == 1
        capsys.readouterr()
        receipt = json.loads((workspace / "journal.jsonl").read_text(
            encoding="utf-8").strip().splitlines()[-1])
        assert receipt["verdict"] == "fail"
        assert any(f.startswith("SOURCE_ID_NOT_IN_RAW") for f in receipt["findings"])
    ```

- [ ] **Step 3: Run the test to verify it fails**

    Run: `python3 -m pytest scripts/tests/test_check_shortlist_rows.py -q`
    Expected: FAIL — collection error `ModuleNotFoundError: No module named 'check_shortlist'`

- [ ] **Step 4: Write the implementation**

    Create `scripts/check_shortlist.py`:

    ```python
    #!/usr/bin/env python3
    """Gate: is this shortlist real? (spec §5.1, risk register rows 1-3)

    A fabricated shortlist is internally consistent, perfectly formatted, and every
    field has the right shape — so shape is not what gets checked. What gets checked
    is that each row's identifier appears VERBATIM in a raw capture from the site it
    claims, because that is the one thing a fabricated row cannot do.

    Exit codes: 0 = passed, 1 = findings on stdout, 2 = could not run. On exit 2 one
    receipt with verdict "could_not_run" is appended — EXCEPT when the workspace
    directory itself does not exist, because then there is nothing to append to. If
    you find no receipt at all, that is the case you are in.
    """
    from __future__ import annotations

    import argparse
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

    import yaml  # noqa: E402

    import journal  # noqa: E402  (Plan 1)
    from vocab import EFFORT, VERDICTS  # noqa: E402  (Plan 1 — the ONE vocabulary)

    GATE = "check_shortlist"

    # The seventeen fields of a shortlist row: the thirteen JobListingEvidence base
    # fields, plus the four this skill adds on top of them. This tuple is the single
    # enumeration — modes/discover.md documents the same seventeen and the mode-doc
    # test asserts every one of them is findable there.
    REQUIRED_ROW_FIELDS = (
        "id", "title", "company", "location", "salary", "url", "source_site",
        "source_id", "extraction_method", "retrieved_at", "quality",
        "verification", "raw_text", "why_matched", "verdict", "provisional",
        "effort",
    )

    # VERDICTS and EFFORT are imported, never re-spelled: a second copy of a closed
    # set is a second thing to forget to update. VERDICTS is ordinal, strongest
    # first, so the detail-fetch cap is a slice of it rather than a third list that
    # could silently disagree with the other two.
    TOP_THREE = VERDICTS[:3]
    EXTRACTION_METHODS = ("adapter_search", "adapter_detail", "user_paste",
                          "public_page")
    QUALITIES = ("complete", "partial", "card_only")
    VERIFICATIONS = ("fresh_verified", "collected_unverified", "stale_possible")

    # Shorter than this and a verbatim substring search would match almost any
    # capture, which makes the provenance check vacuous rather than strict.
    MIN_SOURCE_ID_LEN = 4


    def load_raw_texts(workspace):
        """{site: {filename: text}} over raw/<site>-*.json. Never parsed as JSON:
        the check is a verbatim substring search over the bytes we captured."""
        out = {}
        raw_dir = pathlib.Path(workspace) / "raw"
        if not raw_dir.is_dir():
            return out
        for path in sorted(raw_dir.glob("*.json")):
            if "-" not in path.name:
                continue
            site = path.name.split("-", 1)[0]
            out.setdefault(site, {})[path.name] = path.read_text(
                encoding="utf-8", errors="replace")
        return out


    def _check_provenance(label, row, site, raw_texts):
        findings = []
        source_id = str(row.get("source_id") or "").strip()
        if not source_id:
            findings.append(f"NO_SOURCE_ID: {label} has no source_id")
            return findings
        if len(source_id) < MIN_SOURCE_ID_LEN:
            findings.append(
                f"SUSPICIOUS_SOURCE_ID: {label} source_id {source_id!r} is shorter "
                f"than {MIN_SOURCE_ID_LEN} characters; a verbatim search for it "
                "would match almost any capture")
            return findings
        if not site:
            return findings
        captures = raw_texts.get(site)
        if not captures:
            findings.append(
                f"NO_RAW_CAPTURE_FOR_SITE: {label} claims source_site {site!r} but "
                f"raw/ holds no {site}-*.json capture")
            return findings
        if not any(source_id in text for text in captures.values()):
            findings.append(
                f"SOURCE_ID_NOT_IN_RAW: {label} source_id {source_id!r} does not "
                f"appear verbatim in any of {', '.join(sorted(captures))}")
        url = str(row.get("url") or "").strip()
        if url:
            stem = url.split("?", 1)[0].split("#", 1)[0]
            if not any(stem in text for text in captures.values()):
                findings.append(
                    f"URL_NOT_FROM_ADAPTER: {label} url {url!r} was not returned by "
                    f"an adapter ({stem!r} appears in no {site}-*.json capture)")
        return findings


    def check_rows(shortlist, raw_texts):
        findings = []
        for index, row in enumerate(shortlist.get("rows") or []):
            if not isinstance(row, dict):
                findings.append(f"BAD_ROW: row {index} is not a mapping")
                continue
            label = f"row {index} (id={row.get('id', '<no id>')!r})"
            for field in REQUIRED_ROW_FIELDS:
                if field not in row:
                    findings.append(f"MISSING_FIELD: {label} has no `{field}`")
            site = str(row.get("source_site") or "").strip()
            if not site:
                findings.append(
                    f"NO_SOURCE_SITE: {label} has no source_site — the row cannot be "
                    "traced back to a capture")
            if not str(row.get("title") or "").strip():
                findings.append(
                    f"EMPTY_TITLE: {label} has an empty title — the identifying "
                    f"field was never recovered (run the detail command for "
                    f"{site or 'this site'})")
            if not str(row.get("why_matched") or "").strip():
                findings.append(f"NO_WHY_MATCHED: {label} has no why_matched")
            if not str(row.get("retrieved_at") or "").strip():
                findings.append(f"NO_RETRIEVED_AT: {label} has no retrieved_at")
            if row.get("verdict") not in VERDICTS:
                findings.append(
                    f"BAD_VERDICT: {label} verdict {row.get('verdict')!r} is not one "
                    f"of {', '.join(VERDICTS)}")
            if row.get("provisional") is not True:
                findings.append(
                    f"MISSING_PROVISIONAL: {label} has no `provisional: true` stamp. "
                    "A discover verdict is based on a card, not on a full JD, so it "
                    "may not be rendered without the stamp and is never carried into "
                    "an assessment — assess always recomputes.")
            for field, allowed in (("extraction_method", EXTRACTION_METHODS),
                                   ("quality", QUALITIES),
                                   ("verification", VERIFICATIONS),
                                   ("effort", EFFORT)):
                if field in row and row.get(field) not in allowed:
                    findings.append(
                        f"BAD_ENUM: {label} {field}={row.get(field)!r} is not one of "
                        f"{', '.join(allowed)}")
            findings.extend(_check_provenance(label, row, site, raw_texts))

        # One retrieved row may not become two shortlist rows. Without this, count
        # conservation is decorative: the source report can honestly say "2 rows
        # returned" while the shortlist below it lists the same posting three times.
        seen = {}
        for index, row in enumerate(shortlist.get("rows") or []):
            if not isinstance(row, dict):
                continue
            key = (str(row.get("source_site") or "").strip(),
                   str(row.get("source_id") or "").strip())
            if not key[1]:
                continue
            if key in seen:
                findings.append(
                    f"DUPLICATE_SOURCE_ID: row {index} (id={row.get('id')!r}) repeats "
                    f"source_id {key[1]!r} from row {seen[key]} on the same site — one "
                    "retrieved row became two shortlist rows")
            else:
                seen[key] = index
        return findings


    def _fail_to_run(workspace, message):
        journal.receipt(workspace, GATE, {}, "could_not_run", [message])
        print(message, file=sys.stderr)
        return 2


    def main(argv=None):
        parser = argparse.ArgumentParser(description="Gate: the shortlist is real.")
        parser.add_argument("--workspace", required=True, type=pathlib.Path)
        args = parser.parse_args(argv)
        workspace = args.workspace

        if not workspace.is_dir():
            print(f"workspace not found: {workspace}", file=sys.stderr)
            return 2
        shortlist_path = workspace / "shortlist.yaml"
        if not shortlist_path.is_file():
            return _fail_to_run(workspace, f"missing input: {shortlist_path}")
        try:
            shortlist = yaml.safe_load(shortlist_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            return _fail_to_run(workspace, f"unparsable shortlist.yaml: {exc}")
        if not isinstance(shortlist, dict):
            return _fail_to_run(
                workspace, "shortlist.yaml must be a mapping with a `rows:` list")

        raw_texts = load_raw_texts(workspace)
        findings = check_rows(shortlist, raw_texts)

        input_hashes = {"shortlist.yaml": journal.sha256_file(shortlist_path)}
        for site in sorted(raw_texts):
            for name in sorted(raw_texts[site]):
                input_hashes[f"raw/{name}"] = journal.sha256_file(
                    workspace / "raw" / name)

        journal.receipt(workspace, GATE, input_hashes,
                        "fail" if findings else "pass", findings)
        for line in findings:
            print(line)
        return 1 if findings else 0


    if __name__ == "__main__":
        raise SystemExit(main())
    ```

- [ ] **Step 5: Run the test to verify it passes**

    Run: `python3 -m pytest scripts/tests/test_check_shortlist_rows.py -q`
    Expected: PASS (19 passed)

- [ ] **Step 6: Commit**

    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/check_shortlist.py scripts/tests/discover_fixtures.py \
            scripts/tests/test_check_shortlist_rows.py
    git commit -m "discover: per-row shortlist provenance against raw captures

Every row's source_id must appear VERBATIM in a raw/<site>-*.json
capture from the site it claims, and its url (minus tracking params)
must have been returned by an adapter. Verdicts are checked against the
one five-level vocabulary — imported from scripts/vocab.py, never
re-spelled, with the detail-fetch cap derived as VERDICTS[:3] so it
cannot drift — and must carry provisional: true. effort joins the row
schema so that ordering a band by effort-to-close is implementable
rather than merely specified. One retrieved posting may not become two
rows (DUPLICATE_SOURCE_ID). Fixtures are the real 2026-08-09 51job rows,
and the valid workspace is asserted silent so the gate cannot start
crying wolf unnoticed."
    ```

---

### Task 4: shortlist gate — run-level honesty

**Files:**
- Modify: `scripts/check_shortlist.py` (add the run-level layer; rewrite `main`)
- Test: `scripts/tests/test_check_shortlist_run.py`

**Interfaces:**
- Consumes: `check_opencli_result.read_adapter_calls(workspace) -> list[dict]` (Task 1); `check_shortlist.check_rows`, `load_raw_texts`, `GATE`, `TOP_THREE`, `_fail_to_run` (Task 3); `journal.receipt`, `journal.sha256_file` (Plan 1)
- Produces:
  - `check_shortlist.EMPTINESS_PHRASES: tuple[str, ...]`
  - `check_shortlist.DISCLOSURE_LABELS: tuple[str, ...]` (Task 7's mode-file test imports this)
  - `check_shortlist.PROVISIONAL_STAMP: str` — `"基于卡片信息的初判"`, the reader-facing half of the stamp
  - `check_shortlist.MAX_ROWS_PER_ROUND_CEILING: int`, `check_shortlist.MAX_PAGES_PER_SITE_CEILING: int` — the enforceable half of `references/source-policy.md`
  - `check_shortlist._check_caps(brief) -> list[str]`
  - `check_shortlist.check_run(workspace, shortlist, brief, md_text, calls) -> list[str]`
  - New finding codes: `SOURCE_REPORT_COUNT_MISMATCH`, `MD_MISSING_PROVISIONAL_STAMP`, `CAP_MISSING`, `CAP_ABOVE_CEILING`

**Why this is a separate task:** per-row provenance answers "is this row real"; the run-level layer answers "is this *run's story* real" — the shortfall, the empty-result disambiguation, the disclosure block, the source report, and the detail-fetch cap. A reviewer can accept one and reject the other.

- [ ] **Step 1: Write the failing test**

    Create `scripts/tests/test_check_shortlist_run.py`:

    ```python
    """Run-level tests for scripts/check_shortlist.py.

    Risk register row 2: all-adapters-died and found-nothing have the identical
    shape. Only the receipts tell them apart, so both branches get a QUIET twin
    here — a gate that fires on an honest zero-result would teach the reader to
    skip the line that matters.
    """
    import copy

    import check_shortlist as cs
    import discover_fixtures as fx


    def run(workspace, capsys):
        code = cs.main(["--workspace", str(workspace)])
        return code, capsys.readouterr()


    def codes(out):
        return sorted({line.split(":", 1)[0] for line in out.strip().splitlines() if line})


    OK_CALL = fx.JOURNAL[0]

    DEAD_CALL = {
        "ts": "2026-08-09T14:02:11Z", "mode": "discover", "action": "adapter_call",
        "site": "51job", "command": "search", "exit_code": 1,
        "classification": "not_logged_in", "row_count": 0, "empty_result": False,
        "identity_field": "title", "empty_identity_rows": [],
        "needs_detail_recovery": False, "auth_state": "not_logged_in",
        "signal_id": None, "remedy": "hand the login command to the user",
        "error_message": "51job request failed: HTTP 403 Forbidden",
        "stdout_file": "raw/51job-1.json", "stderr_file": "raw/51job-1.err",
        "command_line": "opencli 51job search 算法工程师 --limit 25 -f json",
    }

    EMPTY_CALL = dict(OK_CALL, row_count=0, empty_result=True)

    DISCLOSURE_OK = """# Shortlist — 2026-08-09 · 降级输出

    ## §0 来源与读取质量

    本轮所有 adapter 均未返回岗位，见下方披露块。输出为方向级 shortlist。

    ## §0.1 触发原因

    用户要求检索算法工程师岗位。

    ## §0.2 披露

    本次会话已登录：        否
    Adapter 返回：          51job request failed: HTTP 403 Forbidden
    收到限制信号后重试：    否
    绕过任何平台控制：      否
    取得真实岗位：          否
    降级输出类型：          方向级 shortlist

    ## §1 方向级 shortlist

    1. 计算机视觉算法工程师（制造/半导体设备方向）— 检索词「视觉算法 半导体」…
    """


    def make_empty(tmp_path, journal_records, md_text):
        workspace = fx.build_workspace(tmp_path)
        data = fx.load_shortlist(workspace)
        data["rows"] = []
        data["sources"] = []
        data["shortfall_reason"] = "本轮 adapter 未返回可用行，原因见 §0.2 披露块。"
        fx.save_shortlist(workspace, data)
        fx.write_journal(workspace, journal_records)
        fx.write_md(workspace, md_text)
        return workspace


    def test_the_valid_workspace_is_still_completely_quiet(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        code, captured = run(workspace, capsys)
        assert code == 0
        assert captured.out == ""


    def test_no_adapter_receipts_at_all_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        fx.write_journal(workspace, [{"action": "gate", "gate": "check_no_write",
                                      "verdict": "pass"}])
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "NO_ADAPTER_RECEIPTS" in codes(captured.out)


    def test_no_results_wording_when_every_adapter_died_fires(tmp_path, capsys):
        workspace = make_empty(
            tmp_path, [DEAD_CALL],
            "## §0 来源\n\n## §0.1 触发原因\n\n用户要求检索。\n\n本轮没有匹配的岗位。\n")
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "EMPTY_RESULT_UNSUPPORTED" in codes(captured.out)
        assert "没有匹配" in captured.out
        assert "DEGRADED_WITHOUT_DISCLOSURE" in codes(captured.out)


    def test_no_results_wording_with_a_genuine_empty_adapter_result_is_quiet(
            tmp_path, capsys):
        # THE quiet twin: exit 0, a parsed array, zero rows. That IS "no results".
        workspace = make_empty(
            tmp_path, [EMPTY_CALL],
            "## §0 来源\n\n## §0.1 触发原因\n\n用户要求检索。\n\n本轮没有匹配的岗位。\n")
        code, captured = run(workspace, capsys)
        assert code == 0
        assert captured.out == ""


    def test_a_degraded_run_with_a_complete_disclosure_block_is_quiet(tmp_path, capsys):
        workspace = make_empty(tmp_path, [DEAD_CALL], DISCLOSURE_OK)
        code, captured = run(workspace, capsys)
        assert code == 0
        assert captured.out == ""


    def test_a_blank_disclosure_answer_fires(tmp_path, capsys):
        label = "绕过任何平台控制："
        blanked = "\n".join(label if label in line else line
                            for line in DISCLOSURE_OK.splitlines())
        workspace = make_empty(tmp_path, [DEAD_CALL], blanked)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "DISCLOSURE_INCOMPLETE" in codes(captured.out)
        assert "active overwrite" in captured.out


    def test_a_partially_missing_disclosure_block_names_the_missing_lines(
            tmp_path, capsys):
        # The middle branch: some labels present, some absent. All-absent gives
        # DEGRADED_WITHOUT_DISCLOSURE and a blank answer gives DISCLOSURE_INCOMPLETE;
        # this one was the only path with no test in either direction, which is how
        # a half-filled disclosure block would have shipped silently.
        dropped = ("收到限制信号后重试：", "绕过任何平台控制：")
        trimmed = "\n".join(line for line in DISCLOSURE_OK.splitlines()
                            if not any(label in line for label in dropped))
        workspace = make_empty(tmp_path, [DEAD_CALL], trimmed)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "DISCLOSURE_INCOMPLETE" in codes(captured.out)
        assert "DEGRADED_WITHOUT_DISCLOSURE" not in codes(captured.out)
        for label in dropped:
            assert label in captured.out


    def test_the_markdown_must_carry_the_card_based_stamp(tmp_path, capsys):
        # spec §5.1 step 6: 不带这个戳就不许渲染. The YAML half is MISSING_PROVISIONAL;
        # this is the half the reader actually sees.
        workspace = fx.build_workspace(tmp_path)
        text = (workspace / "shortlist.md").read_text(encoding="utf-8")
        fx.write_md(workspace, text.replace("基于卡片信息的初判", "候选"))
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "MD_MISSING_PROVISIONAL_STAMP" in codes(captured.out)


    def test_an_over_reported_rows_returned_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        data = fx.load_shortlist(workspace)
        data["sources"][0]["rows_returned"] = 25
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "SOURCE_REPORT_COUNT_MISMATCH" in codes(captured.out)
        assert "more rows than the adapter returned" in captured.out


    def test_more_shortlist_rows_than_the_site_returned_fires(tmp_path, capsys):
        # The failure this bounds: one raw row becoming three shortlist rows.
        workspace = fx.build_workspace(tmp_path)
        data = fx.load_shortlist(workspace)
        data["sources"][0]["rows_returned"] = 1
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "SOURCE_REPORT_COUNT_MISMATCH" in codes(captured.out)
        assert "De-duplication removes rows" in captured.out


    def test_a_hidden_second_invocation_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        fx.write_journal(workspace, list(fx.JOURNAL) + [dict(fx.JOURNAL[0])])
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "SOURCE_REPORT_COUNT_MISMATCH" in codes(captured.out)
        assert "invocations=1" in captured.out


    def test_an_understated_empty_identity_count_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        records = [dict(fx.JOURNAL[0], empty_identity_rows=[0],
                        needs_detail_recovery=True), fx.JOURNAL[1]]
        fx.write_journal(workspace, records)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "SOURCE_REPORT_COUNT_MISMATCH" in codes(captured.out)
        assert "needs_detail_recovery" in captured.out


    def test_a_brief_missing_the_yellow_caps_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        brief = fx.load_brief(workspace)
        del brief["max_pages_per_site"]
        fx.save_brief(workspace, brief)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "CAP_MISSING" in codes(captured.out)
        assert "references/source-policy.md" in captured.out


    def test_a_cap_above_the_yellow_ceiling_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        brief = fx.load_brief(workspace)
        brief["max_pages_per_site"] = 12
        fx.save_brief(workspace, brief)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "CAP_ABOVE_CEILING" in codes(captured.out)
        assert "references/source-policy.md" in captured.out


    def test_qualified_prose_about_no_matches_with_rows_present_is_quiet(
            tmp_path, capsys):
        # "no matching senior roles in Utrecht" alongside two real rows is a
        # qualified statement, not a claim that the run found nothing.
        workspace = fx.build_workspace(tmp_path)
        text = (workspace / "shortlist.md").read_text(encoding="utf-8")
        fx.write_md(workspace, text + "\n本轮没有匹配到 staff 级别的岗位。\n")
        code, captured = run(workspace, capsys)
        assert code == 0
        assert captured.out == ""


    def test_a_shortfall_without_a_written_reason_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        brief = fx.load_brief(workspace)
        brief["target_count"] = 8
        fx.save_brief(workspace, brief)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "SHORTFALL_NO_REASON" in codes(captured.out)
        assert "never pad" in captured.out


    def test_a_shortfall_with_a_written_reason_is_quiet(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        brief = fx.load_brief(workspace)
        brief["target_count"] = 8
        fx.save_brief(workspace, brief)
        data = fx.load_shortlist(workspace)
        data["shortfall_reason"] = (
            "51job 单轮上限 25 行，去重后只有 2 行同时满足 brief 的城市与薪资约束；"
            "下一轮放宽城市到长三角再检索。")
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 0
        assert captured.out == ""


    def test_a_missing_trigger_reason_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        brief = fx.load_brief(workspace)
        brief["trigger_reason"] = ""
        fx.save_brief(workspace, brief)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "NO_TRIGGER_REASON" in codes(captured.out)


    def test_a_missing_trigger_section_in_the_markdown_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        text = (workspace / "shortlist.md").read_text(encoding="utf-8")
        fx.write_md(workspace, text.replace("§0.1", "§9.9"))
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "NO_TRIGGER_SECTION" in codes(captured.out)


    def test_a_missing_brief_exits_2_and_still_leaves_a_receipt(tmp_path, capsys):
        import json
        workspace = fx.build_workspace(tmp_path)
        (workspace / "brief.yaml").unlink()
        code, captured = run(workspace, capsys)
        assert code == 2
        assert "brief.yaml" in captured.err
        receipt = json.loads((workspace / "journal.jsonl").read_text(
            encoding="utf-8").strip().splitlines()[-1])
        assert receipt["gate"] == "check_shortlist"
        assert receipt["verdict"] == "could_not_run"


    def test_a_used_site_with_no_source_report_entry_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        data = fx.load_shortlist(workspace)
        data["sources"] = []
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "SOURCE_REPORT_MISSING" in codes(captured.out)
        assert "references/discovery-sources.md" in captured.out


    def test_a_source_report_that_contradicts_the_journal_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        fx.write_journal(workspace, [DEAD_CALL])      # journal says it failed
        code, captured = run(workspace, capsys)       # sources still claims ok
        assert code == 1
        assert "SOURCE_REPORT_CONTRADICTS_JOURNAL" in codes(captured.out)


    def test_a_source_report_naming_a_missing_raw_file_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        data = fx.load_shortlist(workspace)
        data["sources"][0]["raw_files"] = ["raw/51job-9.json"]
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "SOURCE_REPORT_MISSING_RAW" in codes(captured.out)


    def test_a_detail_fetch_on_a_screened_out_row_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        data = fx.load_shortlist(workspace)
        data["rows"][1]["verdict"] = "likely_screen_out"   # still quality: complete
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "DETAIL_FETCH_OUT_OF_BAND" in codes(captured.out)
        assert "detail_fetch_exceptions" in captured.out


    def test_a_named_detail_fetch_exception_is_quiet(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        data = fx.load_shortlist(workspace)
        data["rows"][1]["verdict"] = "likely_screen_out"
        data["detail_fetch_exceptions"] = [
            {"id": "51job-173199597", "reason": "用户点名要求补取这一条的详情"}]
        fx.save_shortlist(workspace, data)
        code, captured = run(workspace, capsys)
        assert code == 0
        assert captured.out == ""


    def test_every_top_three_verdict_may_carry_a_detail_fetch(tmp_path, capsys):
        for verdict in cs.TOP_THREE:
            data = copy.deepcopy(fx.SHORTLIST)
            workspace = fx.build_workspace(tmp_path / verdict)
            data["rows"][1]["verdict"] = verdict
            fx.save_shortlist(workspace, data)
            code, captured = run(workspace, capsys)
            assert code == 0, f"{verdict} should be allowed a detail fetch"
            assert captured.out == ""
    ```

- [ ] **Step 2: Run the test to verify it fails**

    Run: `python3 -m pytest scripts/tests/test_check_shortlist_run.py -q`
    Expected: FAIL — several tests fail with `assert 0 == 1` (the run-level findings do not exist yet); `test_a_missing_brief_exits_2_and_still_leaves_a_receipt` fails with `assert 0 == 2`; `test_a_hidden_second_invocation_fires` and `test_an_understated_empty_identity_count_fires` fail on `assert 0 == 1` because `fx.write_journal` exists but nothing reads the counts back yet.

- [ ] **Step 3: Add the run-level layer**

    In `scripts/check_shortlist.py`, add this import next to the existing ones:

    ```python
    from check_opencli_result import read_adapter_calls  # noqa: E402
    ```

    Add these constants directly below `MIN_SOURCE_ID_LEN`:

    ```python
    # Wording that asserts the run found nothing. Only consulted when the shortlist
    # has ZERO rows: with rows present, "没有匹配到 staff 级别的岗位" is a qualified
    # statement about a slice, not a claim that the run came back empty.
    EMPTINESS_PHRASES = ("没有匹配", "没有结果", "未找到", "无匹配", "零结果",
                         "no results", "no matching", "nothing found", "found nothing")

    # The degraded-output disclosure block. The last four answers ship pre-filled as
    # 否, so concealing a retry or a bypass has to be an active overwrite rather than
    # an omission.
    DISCLOSURE_LABELS = ("本次会话已登录：", "Adapter 返回：", "收到限制信号后重试：",
                         "绕过任何平台控制：", "取得真实岗位：", "降级输出类型：")

    # The reader-facing half of the provisional stamp (spec §5.1 step 6: a discover
    # verdict 不带这个戳就不许渲染). `provisional: true` in shortlist.yaml is the
    # machine half, and nobody reading the round ever sees it — shortlist.md is what
    # the user actually reads, so that is where the claim has to be qualified.
    PROVISIONAL_STAMP = "基于卡片信息的初判"

    # The yellow-tier round caps from references/source-policy.md, as numbers,
    # because a cap enforced by a paragraph is not a cap. brief.yaml must carry both
    # and neither may exceed these. This is that reference file's named backstop.
    MAX_ROWS_PER_ROUND_CEILING = 25
    MAX_PAGES_PER_SITE_CEILING = 2
    ```

    Add these functions above `_fail_to_run`:

    ```python
    def _check_disclosure(md_text):
        missing = [label for label in DISCLOSURE_LABELS if label not in md_text]
        if len(missing) == len(DISCLOSURE_LABELS):
            return ["DEGRADED_WITHOUT_DISCLOSURE: no adapter exited 0 and the "
                    "shortlist is empty, so this run is a degraded output. It must "
                    "carry the disclosure block (" + "、".join(DISCLOSURE_LABELS)
                    + ") with every answer filled in."]
        findings = []
        if missing:
            findings.append("DISCLOSURE_INCOMPLETE: the disclosure block is missing "
                            "these lines: " + "、".join(missing))
        for label in DISCLOSURE_LABELS:
            if label in missing:
                continue
            for line in md_text.splitlines():
                if label in line:
                    if not line.split(label, 1)[1].strip():
                        findings.append(
                            f"DISCLOSURE_INCOMPLETE: disclosure line {label!r} has a "
                            "blank answer. The answers ship pre-filled as 否 so that "
                            "concealment has to be an active overwrite, not an "
                            "omission.")
                    break
        return findings


    def _check_sources(workspace, shortlist, rows, calls):
        findings = []
        reported = {str(entry["site"]): entry
                    for entry in (shortlist.get("sources") or [])
                    if isinstance(entry, dict) and entry.get("site")}
        used = {str(row.get("source_site")) for row in rows
                if isinstance(row, dict) and row.get("source_site")}
        for site in sorted(used):
            if site not in reported:
                findings.append(
                    f"SOURCE_REPORT_MISSING: rows cite source_site {site!r} but "
                    "shortlist.yaml `sources:` has no entry for it. That entry needs "
                    "the adapter's identity_field and detail_command — for any site "
                    "outside the four inlined in SKILL.md they come from "
                    "references/discovery-sources.md.")
        for site, entry in sorted(reported.items()):
            command = entry.get("command")
            matching = [c for c in calls if c.get("site") == site
                        and (command is None or c.get("command") == command)]
            if not matching:
                findings.append(
                    f"SOURCE_REPORT_CONTRADICTS_JOURNAL: sources[{site}] reports "
                    f"command {command!r} but journal.jsonl records no adapter_call "
                    "for that site and command")
                continue
            recorded = {c.get("classification") for c in matching}
            if entry.get("classification") not in recorded:
                findings.append(
                    f"SOURCE_REPORT_CONTRADICTS_JOURNAL: sources[{site}] reports "
                    f"classification {entry.get('classification')!r} but "
                    f"journal.jsonl recorded {sorted(x for x in recorded if x)}")

            # ---- 条数守恒 (spec §5.1) --------------------------------------
            # Each of these fires in ONE direction only — the dishonest one. The
            # opposite direction is either impossible or harmless, and a check that
            # also fires on the harmless case is a check people learn to ignore.
            reported_rows = entry.get("rows_returned")
            retrieved = sum(int(c.get("row_count") or 0) for c in matching)
            if isinstance(reported_rows, int) and reported_rows > retrieved:
                findings.append(
                    f"SOURCE_REPORT_COUNT_MISMATCH: sources[{site}] reports "
                    f"rows_returned={reported_rows} but journal.jsonl recorded "
                    f"{retrieved} row(s) across {len(matching)} adapter_call(s). A "
                    "run may not report more rows than the adapter returned.")
            site_rows = [r for r in rows if isinstance(r, dict)
                         and str(r.get("source_site") or "").strip() == site]
            if isinstance(reported_rows, int) and len(site_rows) > reported_rows:
                findings.append(
                    f"SOURCE_REPORT_COUNT_MISMATCH: {len(site_rows)} shortlist rows "
                    f"cite source_site {site!r} but sources[{site}] reports only "
                    f"rows_returned={reported_rows}. De-duplication removes rows; "
                    "nothing adds them.")
            reported_calls = entry.get("invocations")
            if isinstance(reported_calls, int) and reported_calls < len(matching):
                findings.append(
                    f"SOURCE_REPORT_COUNT_MISMATCH: sources[{site}] reports "
                    f"invocations={reported_calls} but journal.jsonl recorded "
                    f"{len(matching)}. Under-reporting invocations is how a retry "
                    "after a stop-signal disappears from the disclosure block.")
            reported_empty = entry.get("identity_field_empty_rows")
            observed_empty = sum(len(c.get("empty_identity_rows") or [])
                                 for c in matching)
            if isinstance(reported_empty, int) and reported_empty < observed_empty:
                findings.append(
                    f"SOURCE_REPORT_COUNT_MISMATCH: sources[{site}] reports "
                    f"identity_field_empty_rows={reported_empty} but journal.jsonl "
                    f"recorded {observed_empty}. Under-reporting a blank identity "
                    "field hides exactly the gap needs_detail_recovery exists to "
                    "surface.")

            for name in entry.get("raw_files") or []:
                if not (workspace / name).is_file():
                    findings.append(
                        f"SOURCE_REPORT_MISSING_RAW: sources[{site}] names "
                        f"{name!r}, which does not exist")
        return findings


    def _check_caps(brief):
        """The yellow-tier caps in references/source-policy.md, as a check.

        This is that reference file's named backstop: its two numbers are the only
        part of the policy a program can decide, and without them the trigger in
        SKILL.md would point at a file nothing reports you for skipping.
        """
        findings = []
        for field, ceiling in (("max_rows_per_round", MAX_ROWS_PER_ROUND_CEILING),
                               ("max_pages_per_site", MAX_PAGES_PER_SITE_CEILING)):
            value = brief.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                findings.append(
                    f"CAP_MISSING: brief.yaml has no positive integer `{field}`. "
                    "The yellow-tier caps are what keep pagination and detail "
                    "fan-out inside references/source-policy.md; a round without "
                    "them is an uncapped one.")
            elif value > ceiling:
                findings.append(
                    f"CAP_ABOVE_CEILING: brief.yaml {field}={value} exceeds the "
                    f"yellow-tier ceiling of {ceiling} in "
                    "references/source-policy.md. Read that file before raising "
                    "it: the cap is the whole difference between two pages a human "
                    "asked for and a crawl.")
        return findings


    def _check_detail_cap(shortlist, rows):
        findings = []
        exempt = {str(entry.get("id"))
                  for entry in (shortlist.get("detail_fetch_exceptions") or [])
                  if isinstance(entry, dict)}
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            fetched = (row.get("quality") == "complete"
                       or row.get("extraction_method") == "adapter_detail")
            if (fetched and row.get("verdict") not in TOP_THREE
                    and str(row.get("id")) not in exempt):
                findings.append(
                    f"DETAIL_FETCH_OUT_OF_BAND: row {index} (id={row.get('id')!r}) "
                    f"carries a detail fetch but verdict {row.get('verdict')!r} is "
                    f"outside the top three ({', '.join(TOP_THREE)}). Detail "
                    "fan-out is the yellow-layer cap. If the user named this row, "
                    "record it in shortlist.yaml `detail_fetch_exceptions` with a "
                    "reason.")
        return findings


    def check_run(workspace, shortlist, brief, md_text, calls):
        findings = []
        rows = shortlist.get("rows") or []
        ok_calls = [c for c in calls
                    if c.get("classification") == "ok" and c.get("exit_code") == 0]

        if not calls:
            findings.append(
                "NO_ADAPTER_RECEIPTS: journal.jsonl records no adapter_call at all, "
                "so nothing in this workspace can be traced to a live retrieval. "
                "Every adapter invocation goes through "
                "scripts/check_opencli_result.py.")

        if not str(brief.get("trigger_reason") or "").strip():
            findings.append(
                "NO_TRIGGER_REASON: brief.yaml has no trigger_reason. The reason for "
                "searching is stated BEFORE the search and written into the brief.")
        if "§0.1" not in md_text:
            findings.append(
                "NO_TRIGGER_SECTION: shortlist.md has no `§0.1` section carrying the "
                "trigger reason")

        target = brief.get("target_count")
        if isinstance(target, int) and len(rows) < target and not str(
                shortlist.get("shortfall_reason") or "").strip():
            findings.append(
                f"SHORTFALL_NO_REASON: brief.target_count is {target} but the "
                f"shortlist has {len(rows)} rows and shortfall_reason is empty. "
                "Write the reason — never pad the count.")

        findings.extend(_check_caps(brief))

        if rows and PROVISIONAL_STAMP not in md_text:
            findings.append(
                "MD_MISSING_PROVISIONAL_STAMP: shortlist.md renders rows without the "
                f"「{PROVISIONAL_STAMP}」 label. `provisional: true` in shortlist.yaml "
                "is the machine half of the stamp and no reader ever sees it; this is "
                "the half they do see, and a discover verdict may not be rendered "
                "without it.")

        if not rows:
            lowered = md_text.lower()
            hit = next((p for p in EMPTINESS_PHRASES
                        if p in md_text or p in lowered), None)
            if hit and not ok_calls:
                findings.append(
                    f"EMPTY_RESULT_UNSUPPORTED: shortlist.md says {hit!r} but "
                    "journal.jsonl records no adapter call that exited 0. "
                    "All-adapters-failed and found-nothing have the identical "
                    "shape; only the receipts tell them apart.")
            if not ok_calls:
                findings.extend(_check_disclosure(md_text))

        findings.extend(_check_sources(workspace, shortlist, rows, calls))
        findings.extend(_check_detail_cap(shortlist, rows))
        return findings
    ```

- [ ] **Step 4: Rewrite `main` to run both layers**

    Replace the body of `main` in `scripts/check_shortlist.py` from the `raw_texts = ...` line to the end of the function with:

    ```python
        brief_path = workspace / "brief.yaml"
        if not brief_path.is_file():
            return _fail_to_run(workspace, f"missing input: {brief_path}")
        try:
            brief = yaml.safe_load(brief_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            return _fail_to_run(workspace, f"unparsable brief.yaml: {exc}")
        if not isinstance(brief, dict):
            return _fail_to_run(workspace, "brief.yaml must be a mapping")

        md_path = workspace / "shortlist.md"
        md_text = (md_path.read_text(encoding="utf-8", errors="replace")
                   if md_path.is_file() else "")
        journal_path = workspace / "journal.jsonl"

        raw_texts = load_raw_texts(workspace)
        findings = check_rows(shortlist, raw_texts)
        findings.extend(check_run(workspace, shortlist, brief, md_text,
                                  read_adapter_calls(workspace)))

        input_hashes = {"shortlist.yaml": journal.sha256_file(shortlist_path),
                        "brief.yaml": journal.sha256_file(brief_path)}
        if md_path.is_file():
            input_hashes["shortlist.md"] = journal.sha256_file(md_path)
        if journal_path.is_file():
            input_hashes["journal.jsonl"] = journal.sha256_file(journal_path)
        for site in sorted(raw_texts):
            for name in sorted(raw_texts[site]):
                input_hashes[f"raw/{name}"] = journal.sha256_file(
                    workspace / "raw" / name)

        journal.receipt(workspace, GATE, input_hashes,
                        "fail" if findings else "pass", findings)
        for line in findings:
            print(line)
        return 1 if findings else 0
    ```

    Note: `journal.jsonl` is hashed **before** the receipt is appended, which is correct — the hash records the input state the gate judged.

- [ ] **Step 5: Run both shortlist test modules to verify they pass**

    Run: `python3 -m pytest scripts/tests/test_check_shortlist_rows.py scripts/tests/test_check_shortlist_run.py -q`
    Expected: PASS (45 passed — 19 from the rows module, 26 from this one)

- [ ] **Step 6: Commit**

    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/check_shortlist.py scripts/tests/test_check_shortlist_run.py
    git commit -m "discover: run-level shortlist honesty, incl. empty-result disambiguation

Reads journal.jsonl and refuses 'no results' wording unless at least one
adapter exited 0 — all-adapters-died and found-nothing are otherwise the
same shape. Also: shortfall needs a written reason, a degraded run needs
its pre-filled disclosure block, the source report may not contradict OR
out-count the receipts (条数守恒, each check firing only in the dishonest
direction), shortlist.md may not render a band without the
「基于卡片信息的初判」 stamp because the YAML flag is not a disclosure
anyone reads, brief.yaml must carry both yellow-tier caps, and a detail
fetch outside the top three verdict levels needs a named exception. Both
empty-result branches and all three disclosure branches have tests."
    ```

---

### Task 5: the per-adapter catalogue and its layer-1 trigger

**Files:**
- Create: `references/discovery-sources.md`
- Modify: `SKILL.md` (append one marked block; create the file with just that block if it does not exist yet)
- Test: `scripts/tests/test_discovery_docs.py`

**Interfaces:**
- Consumes: `references/risk-control-signals.yaml` (Task 1)
- Produces:
  - `references/discovery-sources.md` containing exactly one fenced ` ```yaml ` block whose top-level key is `adapters:`, with one entry per site keyed by site name, each carrying `identity_field`, `detail_command`, `login_state_2026_08_09`, `runtime_verified`, `search_command`, `pagination`, `caps`.
  - `SKILL.md` containing the markers `<!-- BEGIN discover-inserts (plan 3) -->` / `<!-- END discover-inserts (plan 3) -->`, the four command pairs, the six-clause platform-limit stop rule, and the trigger for `references/discovery-sources.md`.

**The trigger and its backstop.** The trigger sentence in SKILL.md is evaluable without having read the reference: *"you are in discover mode and about to call an adapter other than the four in the table above"*. The backstop is `check_shortlist.py`'s `SOURCE_REPORT_MISSING` — `shortlist.yaml`'s `sources:` entry needs that adapter's `identity_field` and `detail_command`, and for a non-inlined adapter those values exist nowhere else in the tree.

**Why the stop rule is in this block and not in a reference.** Spec §6 lists 平台限制停止规则 among the things that may not leave SKILL.md, with the reason stated plainly: *每平台的触发串是数据；这条教条不是*. Plan 1 rewrites SKILL.md out of migrated `job-application` content, which contains no opencli material at all, so if this task does not carry the rule, nothing does — and the one file that would have carried it, `references/discovery-sources.md`, is a file you only open when you are already about to call an unfamiliar adapter. **Keep the sentence one line long wherever it is written.** The trigger is asserted as a substring, so a line break dropped into the middle of it silently deletes the assertion while leaving a paragraph that still reads correctly to a human — which is exactly the class of defect this whole plan is built against.

- [ ] **Step 1: Write the failing test**

    Create `scripts/tests/test_discovery_docs.py`:

    ````python
    """The reference catalogue must stay in sync with the code that depends on it."""
    import pathlib
    import re

    import yaml

    REPO = pathlib.Path(__file__).resolve().parents[2]
    SOURCES = REPO / "references" / "discovery-sources.md"
    SIGNALS = REPO / "references" / "risk-control-signals.yaml"
    SKILL = REPO / "SKILL.md"

    INLINED = ("51job", "indeed", "linkedin", "boss")
    NON_INLINED = ("upwork", "nowcoder", "1point3acres", "maimai")


    def adapters():
        text = SOURCES.read_text(encoding="utf-8")
        match = re.search(r"```yaml\n(.*?)\n```", text, re.S)
        assert match, "discovery-sources.md has no fenced yaml block"
        block = yaml.safe_load(match.group(1))
        return block["adapters"]


    def test_every_adapter_in_the_capability_matrix_is_catalogued():
        table = adapters()
        for site in INLINED + NON_INLINED:
            assert site in table, f"{site} is missing from the adapters block"


    def test_every_adapter_entry_carries_the_fields_the_source_report_needs():
        for site, entry in adapters().items():
            for field in ("identity_field", "detail_command",
                          "login_state_2026_08_09", "runtime_verified",
                          "search_command", "pagination", "caps"):
                assert field in entry, f"{site}.{field} missing"
            assert entry["login_state_2026_08_09"] in (
                "logged_in", "not_logged_in", "unknown", "no_auth_adapter")
            assert isinstance(entry["runtime_verified"], bool)


    def test_boss_identity_field_matches_the_classifier():
        import check_opencli_result as coc
        table = adapters()
        for site, entry in table.items():
            expected = coc.IDENTITY_FIELD.get(site, coc.IDENTITY_FIELD_DEFAULT)
            if entry["identity_field"] != "n/a":
                assert entry["identity_field"] == expected, (
                    f"{site}: catalogue says {entry['identity_field']!r}, "
                    f"check_opencli_result says {expected!r}")


    def test_every_risk_control_signal_string_appears_in_the_catalogue():
        text = SOURCES.read_text(encoding="utf-8")
        data = yaml.safe_load(SIGNALS.read_text(encoding="utf-8"))
        for signal in data["signals"]:
            assert signal["pattern"] in text, (
                f"signal {signal['id']!r} pattern {signal['pattern']!r} is not "
                "documented in references/discovery-sources.md")
            assert signal["id"] in text


    def test_the_catalogue_states_which_adapters_were_never_run():
        table = adapters()
        # Measured 2026-08-09: only 51job, indeed and 1point3acres were executed.
        assert table["51job"]["runtime_verified"] is True
        assert table["indeed"]["runtime_verified"] is True
        assert table["boss"]["runtime_verified"] is False
        assert table["linkedin"]["runtime_verified"] is False


    def test_maimai_is_marked_as_having_no_job_search():
        text = SOURCES.read_text(encoding="utf-8")
        assert "maimai has no job-search capability" in text
        assert adapters()["maimai"]["search_command"] is None


    def test_the_degraded_fallback_field_list_is_present():
        text = SOURCES.read_text(encoding="utf-8")
        for field in ("目标方向", "检索词", "建议筛选条件", "为何比原 JD 更稳",
                      "要避开的标题与信号", "手动收集优先序"):
            assert field in text


    def test_skill_md_carries_the_discovery_trigger():
        text = SKILL.read_text(encoding="utf-8")
        assert "<!-- BEGIN discover-inserts (plan 3) -->" in text
        assert "<!-- END discover-inserts (plan 3) -->" in text
        assert "references/discovery-sources.md" in text
        assert "about to call an adapter other than the four" in text
        for site in INLINED:
            assert site in text


    def test_the_trigger_sentence_survives_line_wrapping_in_both_files():
        # It is one evaluable sentence, and it is load-bearing in two files. A
        # newline dropped into the middle of it deletes the assertion above
        # without deleting the paragraph a reader sees, which is the worst
        # possible failure shape for a layer-2 trigger.
        phrase = "about to call an adapter other than the four"
        assert phrase in SKILL.read_text(encoding="utf-8")
        assert phrase in SOURCES.read_text(encoding="utf-8")


    def test_skill_md_states_the_exit_code_rule_the_write_ban_and_the_stop_rule():
        text = SKILL.read_text(encoding="utf-8")
        assert "branch on the exit code before you read stdout" in text
        assert "access:` is `write" in text
        # spec §6 lists the platform-limit stop rule as layer-1 content: the
        # per-platform trigger strings are data, this dogma is not. All six
        # clauses, because dropping any one of them is how "stop" quietly becomes
        # "stop, then try a smaller limit".
        assert "Stop that site for that round." in text
        assert "Do not retry." in text
        assert "Do not change parameters and retry" in text
        assert "Do not route around it" in text
        assert "direction-level degraded output" in text
        assert "disclosure table" in text
    ````

- [ ] **Step 2: Run the test to verify it fails**

    Run: `python3 -m pytest scripts/tests/test_discovery_docs.py -q`
    Expected: FAIL, in **two different shapes** — do not read the mixture as a broken bootstrap. The seven tests that read `references/discovery-sources.md` error with `FileNotFoundError`; `test_skill_md_carries_the_discovery_trigger` and `test_skill_md_states_the_exit_code_rule_the_write_ban_and_the_stop_rule` fail with plain `AssertionError`, because Plan 1 already created `SKILL.md` and it simply does not carry this block yet. `test_the_trigger_sentence_survives_line_wrapping_in_both_files` fails on the SKILL.md assertion first.

- [ ] **Step 3: Write the catalogue**

    Create `references/discovery-sources.md`:

    ````markdown
    # Discovery sources — the opencli adapter catalogue

    **Read this when you are in discover mode and
    about to call an adapter other than the four in the table above** — the four
    inlined in SKILL.md, which are 51job, indeed, linkedin and boss. You cannot fill in
    `shortlist.yaml`'s `sources:` entry for such an adapter without the
    `identity_field` and `detail_command` below, and `check_shortlist.py` fails the run
    with `SOURCE_REPORT_MISSING` when that entry is absent.

    Everything here was read out of the tool's own introspection
    (`opencli <site> --help -f yaml`, `opencli list -f yaml`, `opencli auth status`) on
    **2026-08-09** with opencli v1.8.6. `runtime_verified: true` means the command was
    actually executed that day; `false` means only the help text was read. Do not
    upgrade a `false` to a `true` without running the command and recording the output.

    ## The machine-readable block

    `scripts/tests/test_discovery_docs.py` parses this block and cross-checks it
    against `check_opencli_result.IDENTITY_FIELD`. Keep it accurate rather than tidy.

    ```yaml
    adapters:
      51job:
        domain: jobs.51job.com
        login_state_2026_08_09: no_auth_adapter
        runtime_verified: true
        identity_field: title
        search_command: 'opencli 51job search "<keyword>" --area <city> --sort 最新 --page 1 --limit 20 --window background -f json'
        detail_command: "opencli 51job detail <jobId>"
        pagination: "--page 1-based (default 1) + --limit (help: 1-50, default 20)"
        caps: {rows_per_round: 25, pages_per_round: 2}
        other_read_commands: [hot, company]
        notes: >-
          The best no-login source of the eight and the only adapter measured to
          return every documented column non-empty. salaryMin/salaryMax are plain
          integers, which makes it the easiest adapter to filter programmatically.
      indeed:
        domain: www.indeed.com
        login_state_2026_08_09: no_auth_adapter
        runtime_verified: true
        identity_field: title
        search_command: 'opencli indeed search "<keyword>" --location "<loc>" --fromage 7 --sort date --start 0 --limit 15 --window background -f json'
        detail_command: "opencli indeed job <id>"
        pagination: "--start 0-based multiple of 10 + --limit (help: 1-25, one page)"
        caps: {rows_per_round: 25, pages_per_round: 2}
        other_read_commands: []
        notes: >-
          MEASURED DEFECT: search returns exit 0 and well-formed JSON with EMPTY
          title, salary and tags while id/company/location/url are populated. The
          rows exist — follow every id with `opencli indeed job <id>` to recover the
          title. `job` has aliases `detail` and `view`.
      linkedin:
        domain: www.linkedin.com
        login_state_2026_08_09: logged_in
        runtime_verified: false
        identity_field: title
        search_command: 'opencli linkedin search "<keyword>" --location "<loc>" --experience-level mid-senior --job-type full-time --date-posted week --start 0 --limit 10 --window background -f json'
        detail_command: "opencli linkedin job-detail <job-url>"
        pagination: "--start offset (default 0) + --limit (help: max 100, default 10)"
        caps: {rows_per_round: 25, pages_per_round: 2}
        other_read_commands: [jobs-preferences, people-search]
        notes: >-
          Filters are comma-separated free text with no `choices` enum, so a
          malformed value will not be rejected by the CLI. `--details` inlines the
          description but the help marks it "(slower)"; prefer job-detail for the
          top three verdict levels only. `people-search` carries a verbatim
          rate-limit warning about LinkedIn's monthly Commercial Use Limit and is
          NOT a job-discovery path — do not call it in discover mode.
      boss:
        domain: www.zhipin.com
        login_state_2026_08_09: logged_in
        runtime_verified: false
        identity_field: name
        search_command: 'opencli boss search "<keyword>" --city <城市> --experience 3-5年 --degree 硕士 --page 1 --limit 15 --window background -f json'
        detail_command: "opencli boss detail <security_id>"
        pagination: "--page 1-based (default 1) + --limit (default 15)"
        caps: {rows_per_round: 25, pages_per_round: 2}
        other_read_commands: [recommend]
        notes: >-
          The identity field is `name`, NOT `title` — asserting non-empty `title`
          here would fire on every healthy row. --city defaults to 北京, so it must
          be set explicitly for any other geography. The positional query is
          OPTIONAL; omitting it returns 为你推荐职位 rather than a keyword search,
          which is a different thing and must not be reported as a keyword result.
          Nine of its sixteen commands are recruiter-side or write; only search,
          detail and recommend belong in discover mode.
      upwork:
        domain: www.upwork.com
        login_state_2026_08_09: not_logged_in
        runtime_verified: false
        identity_field: title
        search_command: 'opencli upwork search "<keyword>" --location "<loc>" --sort recency --page 1 --per_page 10 -f json'
        detail_command: "opencli upwork detail <id>"
        pagination: "--page 1-based + --per_page (help: 10-50). NOTE the underscore: --per_page, not --per-page."
        caps: {rows_per_round: 25, pages_per_round: 2}
        other_read_commands: [feed]
        notes: >-
          Freelance/contract work, not salaried postings — the row carries `budget`
          and `type` instead of a salary band, so a fit verdict built on salary
          constraints does not apply. Login is required and the account was logged
          out on 2026-08-09; expect not_logged_in.
      nowcoder:
        domain: www.nowcoder.com
        login_state_2026_08_09: not_logged_in
        runtime_verified: false
        identity_field: title
        search_command: 'opencli nowcoder search "<company> 面经" --type post --limit 10 -f json'
        detail_command: "opencli nowcoder detail <id>"
        pagination: "`search` takes ONLY --limit (default 10) — there is no --page, so search depth is hard-capped at one page. `experience` takes --page + --limit."
        caps: {rows_per_round: 10, pages_per_round: 1}
        other_read_commands: [experience, papers, companies, jobs, hot, trending]
        notes: >-
          An interview-experience (面经) source, not a job source. search /
          experience / papers / detail are strategy=cookie and need a logged-in
          session. Only companies / jobs / hot / topics / trending / recommend /
          creators are strategy=public. `papers` returns question-SET titles and
          practice counts, not question text, and yields no id to chain onwards.
          Its --company/--job filters were measured INERT elsewhere in this project
          (three different ids returned byte-identical rows), so treat `papers` as a
          company/role index only.
      1point3acres:
        domain: www.1point3acres.com
        login_state_2026_08_09: not_logged_in
        runtime_verified: true
        identity_field: title
        search_command: 'opencli 1point3acres search "<company> 面经" --fid 145 --limit 20 -f json'
        detail_command: "opencli 1point3acres thread <tid> --limit 30 --contentLimit 2000"
        pagination: "`forum` --page + --limit (max 50); `search`/`hot`/`latest`/`digest` take --limit only."
        caps: {rows_per_round: 20, pages_per_round: 1}
        other_read_commands: [forum, forums, thread, hot, latest, digest]
        notes: >-
          MEASURED: `opencli 1point3acres forum 145 --limit 2 -f json` returned exit
          1 and HTTP 403 while logged out, even though that command is
          strategy=public / browser=false. Treat the WHOLE adapter as
          login-required, and never treat `strategy: public` as evidence that no
          login is needed. Raise --contentLimit above its 400-char default or a real
          面经 will come back truncated.
      maimai:
        domain: maimai.cn
        login_state_2026_08_09: not_logged_in
        runtime_verified: false
        identity_field: "n/a"
        search_command: null
        detail_command: null
        pagination: "--page is ZERO-based here (default 0) + --size (default 20)."
        caps: {rows_per_round: 0, pages_per_round: 0}
        other_read_commands: [search-talents]
        notes: >-
          maimai has no job-search capability. Its only read command is
          `search-talents`, recruiter-side candidate sourcing; every output column
          describes a person, not a posting. If the goal is finding jobs, maimai is
          the wrong adapter — say so plainly rather than running it and reporting
          zero jobs.
    ```

    ## Platform stop-signals

    `scripts/check_opencli_result.py` loads `references/risk-control-signals.yaml` and
    matches these patterns **only against the stderr of an invocation that exited
    non-zero**. A successful call has empty stderr, so none of them can fire on a job
    row — a posting whose title contains `安全验证` is a job about verification, not a
    verification wall.

    | id | pattern | verified |
    |---|---|---|
    | `http-429-rate-limited` | `HTTP 429` | no |
    | `verify-human-en` | `(?i)verify (that )?you are (a )?human` | no |
    | `unusual-traffic-en` | `(?i)unusual traffic` | no |
    | `captcha-interstitial` | `(?i)captcha` | no |
    | `slider-verification-cn` | `滑块` | no |
    | `security-verification-cn` | `安全验证` | no |
    | `risk-control-cn` | `风控` | no |
    | `too-frequent-cn` | `操作过于频繁` | no |
    | `access-restricted-cn` | `访问受限` | no |

    **None of these has been observed.** The only failure body ever captured from this
    toolset is the HTTP 403 login wall, which `check_opencli_result.py` resolves in its
    login-wall branch against `opencli auth status`, not here. The first time a real
    risk-control body is captured, save the raw stderr, replace the guessed pattern
    with the verbatim string, and flip `verified` to `true`.

    **When one fires: stop that site for that round.** Do not retry. Do not change
    parameters and retry. Do not route around it. Emit the degraded output below.

    ## Degraded fallback — the direction-level shortlist

    When no real postings can be retrieved, the output is a direction-level shortlist
    with these six fields per direction (3-5 directions), plus the disclosure block
    defined in `modes/discover.md`:

    1. **目标方向** — the role family, not a job title copied from a JD you could not fetch
    2. **检索词** — the exact keywords to search, in both languages of the market
    3. **建议筛选条件** — seniority / work model / language / employment type filters
    4. **为何比原 JD 更稳** — the visible, checkable reason, not "similar title"
    5. **要避开的标题与信号** — the titles and phrases that indicate a worse fit
    6. **手动收集优先序** — which source the user should open first, and why

    A direction-level shortlist has no `rows:`, so it never claims a posting exists.
    That is the whole point: the failure mode being defended against is a model filling
    an empty result with plausible-looking jobs.
    ````

- [ ] **Step 4: Append the SKILL.md block**

    If `SKILL.md` does not exist, create it containing only the block below. If it does exist, append the block to the end — **do not rewrite anything already in the file**, and if the markers are already present, replace only the text between them.

    ```markdown
    <!-- BEGIN discover-inserts (plan 3) -->
    ### opencli: the four command pairs this skill actually uses

    | site | search | detail | login state (2026-08-09) | identity field |
    |---|---|---|---|---|
    | `51job` | `opencli 51job search "<kw>" --area <city> --page 1 --limit 20 --window background -f json` | `opencli 51job detail <jobId>` | no auth adapter | `title` |
    | `indeed` | `opencli indeed search "<kw>" --location "<loc>" --fromage 7 --start 0 --limit 15 --window background -f json` | `opencli indeed job <id>` | no auth adapter | `title` — **measured EMPTY**, recover via detail |
    | `linkedin` | `opencli linkedin search "<kw>" --location "<loc>" --date-posted week --start 0 --limit 10 --window background -f json` | `opencli linkedin job-detail <job-url>` | logged in (cookie session) | `title` |
    | `boss` | `opencli boss search "<kw>" --city <城市> --page 1 --limit 15 --window background -f json` | `opencli boss detail <security_id>` | logged in (cookie session) | `name`, **not** `title` |

    Always `-f json`. Always `--window background`.
    And **always branch on the exit code before you read stdout**:
    a login wall gives exit 1, EMPTY stdout and a YAML error body on stderr even under
    `-f json`, so `JSON.parse(stdout || '[]')` turns a 403 into a zero-result success.
    Never run a command whose published `access:` is `write` —
    `check_no_write.py` reads that field out of the tool itself.

    ### When a platform says stop, stop

    A platform limit is any refusal the platform itself put up: a risk-control or
    captcha body, a rate-limit, or a refusal on a site `opencli auth status` says you
    are logged into. When one appears, all six of these apply at once, and the last
    two are what make the first four checkable:

    1. **Stop that site for that round.**
    2. Do not retry.
    3. Do not change parameters and retry — a smaller `--limit`, a different city or a
       fresh `--window` is still a retry.
    4. Do not route around it — no other adapter, no public mirror, no logged-in
       session standing in for a logged-out one.
    5. Emit the **direction-level degraded output** instead: 3-5 目标方向, no `rows:`,
       so it cannot claim a posting exists.
    6. Fill in the disclosure table, whose answers ship pre-filled as 否 precisely so
       that concealing a retry has to be an active overwrite rather than an omission.

    The per-platform trigger strings are data and live in
    `references/risk-control-signals.yaml`; **this rule is not data and does not live
    in a reference file**, because the moment it needs to be applied is the moment
    nobody is going to go and look it up.

    **READ `references/discovery-sources.md` when you are in discover mode and
    about to call an adapter other than the four in the table above** (upwork,
    nowcoder, 1point3acres, maimai, or any site added later). It carries that
    adapter's flags, its measured login state, its identity field and its detail
    command — and `shortlist.yaml`'s `sources:` entry cannot be filled in without
    them, so `check_shortlist.py` fails the run with `SOURCE_REPORT_MISSING` if you
    skipped it.
    <!-- END discover-inserts (plan 3) -->
    ```

- [ ] **Step 5: Run the test to verify it passes**

    Run: `python3 -m pytest scripts/tests/test_discovery_docs.py -q`
    Expected: PASS (10 passed)

- [ ] **Step 6: Commit**

    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add references/discovery-sources.md SKILL.md scripts/tests/test_discovery_docs.py
    git commit -m "discover: per-adapter catalogue with a trigger you can evaluate unread

SKILL.md inlines the four command pairs actually used, the six-clause
platform-limit stop rule (spec 6: the trigger strings are data, the rule
is not), and says exactly when to open references/discovery-sources.md:
when about to call an adapter other than those four. The trigger sentence
is kept on one line in both files that carry it, because it is asserted
as a substring and a line break would delete the assertion silently.
Backstop is SOURCE_REPORT_MISSING — a
non-inlined adapter's identity_field and detail_command exist nowhere
else. Every runtime claim is tagged runtime_verified true/false; only
51job, indeed and 1point3acres were ever executed."
    ```

---

### Task 6: rewrite the source policy as ONE standard

**Files:**
- Create: `references/source-policy.md`
- Modify: `SKILL.md` (add the source-policy trigger inside the existing `discover-inserts` marker block)
- Test: `scripts/tests/test_source_policy.py`

**Interfaces:**
- Consumes: `check_shortlist.TOP_THREE`, `check_shortlist.EXTRACTION_METHODS`, `check_shortlist.MAX_ROWS_PER_ROUND_CEILING`, `check_shortlist.MAX_PAGES_PER_SITE_CEILING` (Tasks 3-4) — the policy's detail-fetch cap and the gate's `DETAIL_FETCH_OUT_OF_BAND` must name the same three verdicts, the policy's two numeric ceilings must be the numbers `_check_caps` enforces, and the policy's metadata table must list the same extraction methods the gate accepts.
- Produces: `references/source-policy.md` with exactly one `## Green`, one `## Yellow`, one `## Red` section; `SKILL.md` carrying its trigger.

**This file's trigger and its backstop (the thing every layer-2 file needs).** Until now `references/source-policy.md` had neither: its only pointer was inside `modes/discover.md`'s own self-check, which is a pointer you only reach if you already opened the mode file, and nothing anywhere reported skipping it. Both halves are added here.

- **Trigger, evaluable without having read the file:** *read it before the first live retrieval of any run — before the first `opencli` adapter call — and again before agreeing to page further, fetch more detail pages, or work while the user is away.* A model can decide "am I about to make my first live call, or has the user just asked for more pages?" without knowing anything about the file's contents.
- **Backstop:** `check_shortlist.py`'s `CAP_MISSING` and `CAP_ABOVE_CEILING` (Task 4). The two round caps are the only part of the policy a program can decide, and `brief.yaml` cannot satisfy them by accident: a round with no caps, or caps above the yellow ceiling, fails the gate and the finding text names this file.
- **Honest bound, carried into the residual-risk list:** the caps are a backstop for *one* section. Nothing reports a run that quietly did something Red. The load-bearing half there remains that no Red action appears anywhere in this skill's instructions, and `check_no_write.py` covers the one Red line a script can see.

**Why this rewrite exists (spec D5/D6).** The retired `job-search-coach` policy put "auto-scroll or page through large result sets", "automatically opening many detail pages" and "hidden/internal API calls on logged-in job boards" in **Red**. The owner then chose opencli as the primary discovery path, and opencli's cookie-strategy read commands are precisely those three things. Two standards would mean shipping a policy the skill violates on every run, so pagination and detail fetch move to **Yellow with hard caps** and the caps are enforced by `check_shortlist.py` rather than by good intentions. Red keeps everything that is about defeating a control the platform put up on purpose.

- [ ] **Step 1: Write the failing test**

    Create `scripts/tests/test_source_policy.py`:

    ```python
    """The source policy must be ONE standard, and one the skill actually obeys."""
    import pathlib
    import re

    import check_shortlist as cs

    REPO = pathlib.Path(__file__).resolve().parents[2]
    POLICY = REPO / "references" / "source-policy.md"


    def sections():
        text = POLICY.read_text(encoding="utf-8")
        parts = re.split(r"^## ", text, flags=re.M)
        return {p.split("\n", 1)[0].strip(): p.split("\n", 1)[1] for p in parts[1:]}


    def test_there_is_exactly_one_source_policy_file():
        found = sorted(p.name for p in (REPO / "references").glob("*source-polic*"))
        assert found == ["source-policy.md"]


    def test_there_is_exactly_one_tier_section_of_each_colour():
        text = POLICY.read_text(encoding="utf-8")
        for colour in ("Green", "Yellow", "Red"):
            assert len(re.findall(rf"^## {colour}\b", text, flags=re.M)) == 1


    def test_pagination_and_detail_fetch_are_yellow_not_red():
        blocks = sections()
        yellow, red = blocks["Yellow"], blocks["Red"]
        assert "pagination" in yellow.lower()
        assert "detail" in yellow.lower()
        for banned in ("auto-scroll", "page through", "detail page",
                       "hidden/internal API"):
            assert banned.lower() not in red.lower(), (
                f"{banned!r} is still in Red, which the skill itself does on every run")


    def test_red_keeps_every_named_ban():
        red = sections()["Red"].lower()
        for phrase in ("captcha", "risk-control", "fingerprint", "proxy", "stealth",
                       "multi-account rotation", "while the user is not present",
                       "batch apply", "greeting", "auto-chat",
                       "without a fresh source signal",
                       "published `access:` is `write`"):
            assert phrase.lower() in red, f"Red no longer bans {phrase!r}"


    def test_the_policy_says_account_risk_is_not_zero_in_those_words():
        assert "Account risk is not zero." in POLICY.read_text(encoding="utf-8")


    def test_the_yellow_caps_are_the_ones_the_gates_enforce():
        yellow = sections()["Yellow"]
        assert "max_rows_per_round" in yellow
        assert "max_pages_per_site" in yellow
        for verdict in cs.TOP_THREE:
            assert verdict in yellow, (
                f"the detail-fetch cap must name {verdict} exactly as "
                "check_shortlist.DETAIL_FETCH_OUT_OF_BAND does")
        assert "DETAIL_FETCH_OUT_OF_BAND" in yellow
        # The two numbers are the enforceable half of this file. If the prose and
        # the gate ever disagree, the run passes a cap the policy did not set.
        assert str(cs.MAX_ROWS_PER_ROUND_CEILING) in yellow
        assert str(cs.MAX_PAGES_PER_SITE_CEILING) in yellow
        assert "CAP_ABOVE_CEILING" in yellow


    def test_skill_md_carries_this_files_trigger_and_names_its_backstop():
        # Every layer-2 file needs a trigger a model can evaluate WITHOUT having
        # read it, plus something that reports skipping it. This file had neither
        # until now: its only pointer lived inside modes/discover.md's self-check,
        # which you only reach once you have already opened the mode file.
        text = (REPO / "SKILL.md").read_text(encoding="utf-8")
        assert "references/source-policy.md" in text
        assert "before the first live retrieval of any run" in text
        assert "CAP_ABOVE_CEILING" in text


    def test_the_policy_does_not_ban_the_adapters_the_skill_uses():
        red = sections()["Red"]
        for site in ("51job", "indeed", "linkedin", "boss"):
            assert site not in red


    def test_the_changelog_names_what_moved_and_why():
        text = POLICY.read_text(encoding="utf-8")
        assert "## What changed from the retired policy" in text
        assert "job-search-coach" in text
        assert "cookie" in text          # the honest naming of the moved red line


    def test_the_required_metadata_maps_onto_the_real_row_fields():
        text = POLICY.read_text(encoding="utf-8")
        for field in ("source_site", "source_id", "retrieved_at",
                      "extraction_method", "quality", "verification"):
            assert field in text
        # The retired policy's extraction_method values are gone; the live enum wins.
        for value in cs.EXTRACTION_METHODS:
            assert value in text
        assert "visible_capture" not in text
    ```

- [ ] **Step 2: Run the test to verify it fails**

    Run: `python3 -m pytest scripts/tests/test_source_policy.py -q`
    Expected: FAIL, in **two shapes**. Eight tests error with `FileNotFoundError: .../references/source-policy.md` (all ten except the two that never open the policy file); `test_there_is_exactly_one_source_policy_file` fails with a plain `AssertionError: [] == ['source-policy.md']` because the glob finds nothing rather than raising; and `test_skill_md_carries_this_files_trigger_and_names_its_backstop` fails with `AssertionError` against a `SKILL.md` that Plan 1 already created.

- [ ] **Step 3: Write the policy**

    Create `references/source-policy.md`:

    ```markdown
    # Source policy

    This is the **only** source standard in `job-hunt`. It governs every live
    retrieval in every mode. If the skill's own behaviour would violate a line here,
    the line wins and the behaviour changes — a policy the skill violates on every
    run teaches the reader to ignore all of it.

    **Account risk is not zero.** Every yellow action below runs inside the user's own
    logged-in browser session, on the user's own account, against a platform that did
    not agree to it. The caps exist to keep the behaviour closer to note-taking than to
    automation, not to make the risk disappear. The user can stop at any point, and
    discover mode is never triggered as a side effect of another mode — starting it is
    always an explicit act by the user.

    ## Green

    Allowed by default, no disclosure needed:

    - Job descriptions, links, PDFs, screenshots or CSV/JSON exports the **user** pasted.
    - Official or public job APIs with a documented usage path.
    - Public employer career pages reachable without a login and without a bypass.
    - Search-engine results that point at public career pages.
    - `opencli <site> --help -f yaml`, `opencli list`, `opencli doctor`,
      `opencli auth status` — introspection that touches no site.
    - opencli read commands on adapters that have **no login concept at all**
      (`51job`, `indeed`: absent from `opencli auth status` entirely, and exposing no
      `login` command), within the caps below.

    ## Yellow

    Allowed, capped, and disclosed. Say plainly that account risk is not zero.

    - opencli read commands on a **logged-in** adapter (`boss`, `linkedin`) in a session
      the user is present for.
    - **Pagination** within the round cap. `brief.yaml` must carry `max_rows_per_round`
      and `max_pages_per_site`, and these are **ceilings, not defaults**: at most 25
      rows per site per round and at most 2 pages per site. `check_shortlist.py`
      enforces both with `CAP_MISSING` (the brief left one out) and
      `CAP_ABOVE_CEILING` (the brief raised one) — the cap is a check, not a promise.
      Also never above the adapter's own documented `--limit` ceiling — indeed caps at
      25, 51job at 50, linkedin at 100, upwork at 50.
    - **Detail-page fetch**, and only for rows whose provisional verdict is
      `strong_apply`, `worth_applying` or `stretch`. `likely_screen_out` and `blocked`
      rows stay card-level and are labelled 未取详情. The user may name an individual
      row to fetch anyway; that goes in `shortlist.yaml` `detail_fetch_exceptions` with
      a reason. `check_shortlist.py` enforces this with `DETAIL_FETCH_OUT_OF_BAND` —
      the cap is a check, not a promise.
    - Small-volume capture for the user's own analysis, with source, timestamp and
      read-quality retained on every row.
    - **Stop on any risk-control signal**, for that site, for that round. Do not retry.
      Do not change parameters and retry. Do not route around it. Emit the
      direction-level degraded shortlist and its disclosure block.

    ## Red

    Never performed and never designed, whatever the user asks:

    - Captcha, risk-control, fingerprint, proxy or stealth evasion of any kind.
    - Multi-account rotation or cookie switching between identities.
    - Background or unattended operation while the user is not present.
    - Batch apply, batch greeting, auto-chat, auto-reply, or any automated contact with
      a recruiter or hiring manager.
    - Running any opencli command whose published `access:` is `write` — including
      `login`. A login command is handed to the user to run; it is never run here, and
      there is no confirm-then-send path, because a confirmation flow is just a write
      path with a speed bump.
    - Claiming a job is open without a fresh source signal.
    - Presenting a fabricated, inferred or padded listing as retrieved. If the count
      falls short of the target, write the reason; never pad.

    ## What changed from the retired policy

    `~/.codex/skills/job-search-coach/references/source-policy.md` is retired. Three of
    its Red lines moved, and naming them honestly matters more than the move:

    | Retired Red line | Now | Why |
    |---|---|---|
    | "Auto-scroll or page through large result sets" | Yellow, capped by `max_pages_per_site` | Two pages of a keyword search a human asked for is not a scrape; an uncapped crawl is. The cap is the difference, so the cap is enforced by a script. |
    | "Automatically opening many detail pages" | Yellow, capped to the top three verdict levels | "Many" was never defined, so it could not be checked. "Only the rows the user might actually apply to" can be. |
    | "Hidden/internal API calls on logged-in job boards" | Yellow | This is the uncomfortable one, said plainly: opencli's `strategy: cookie` read commands on `boss` and `linkedin` **are** requests to the site's own endpoints carrying the user's session. Calling that Red while building the skill on top of it would be a lie in a file whose only job is to be true. |

    Unchanged: every Red line about defeating a control the platform put up on purpose,
    and every Red line about writing.

    ## Required source metadata

    These are not a separate schema — they are the `JobListingEvidence` fields that
    `check_shortlist.py` already enforces on every row:

    | Metadata | Field | Enforced by |
    |---|---|---|
    | source name | `source_site` | `NO_SOURCE_SITE` |
    | traceable identifier | `source_id`, verbatim in `raw/<site>-*.json` | `SOURCE_ID_NOT_IN_RAW` |
    | collection time | `retrieved_at` | `NO_RETRIEVED_AT` |
    | extraction method | `extraction_method`: `adapter_search` \| `adapter_detail` \| `user_paste` \| `public_page` | `BAD_ENUM` |
    | text quality | `quality`: `complete` \| `partial` \| `card_only` | `BAD_ENUM` |
    | verification status | `verification`: `fresh_verified` \| `collected_unverified` \| `stale_possible` | `BAD_ENUM` |
    | original URL | `url`, verbatim from an adapter response | `URL_NOT_FROM_ADAPTER` |

    The retired policy's screenshot / visible-capture extraction methods are gone:
    there is no OCR pipeline in this skill and there will not be one. A screenshot the
    user pastes is `user_paste`, and if it cannot be read, the honest output is
    `insufficient_evidence`, not a guess.

    ## Source tiers apply to ACTIONS, not to rows

    A row does not carry a tier. The tier describes what was done to obtain it, and
    that is already recorded: `journal.jsonl` holds the site, command and classification
    of every invocation, and `check_no_write.py` resolves each one against opencli's own
    `access:` metadata. A `source_tier` column on a row would be a self-assessment with
    nothing checking it.
    ```

- [ ] **Step 4: Add this file's trigger to SKILL.md**

    Insert these lines into `SKILL.md` **inside** the existing
    `<!-- BEGIN discover-inserts (plan 3) --> … <!-- END discover-inserts (plan 3) -->`
    block, immediately before the `references/discovery-sources.md` trigger paragraph.
    Do not create a second marker block, and do not touch anything outside the markers.

    ```markdown
    **READ `references/source-policy.md` before the first live retrieval of any run**
    — before the first `opencli` adapter call — and again before agreeing to page
    further, to fetch more detail pages, or to work while the user is away. It is the
    ONE source standard: what is green, what is yellow-with-caps, and what is never
    done whatever the user asks. Its two round caps are enforced rather than
    suggested: `brief.yaml` must carry `max_rows_per_round` and `max_pages_per_site`,
    and `check_shortlist.py` fails the run with `CAP_MISSING` or `CAP_ABOVE_CEILING`.
    ```

- [ ] **Step 5: Run the test to verify it passes**

    Run: `python3 -m pytest scripts/tests/test_source_policy.py -q`
    Expected: PASS (10 passed)

- [ ] **Step 6: Commit**

    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add references/source-policy.md SKILL.md scripts/tests/test_source_policy.py
    git commit -m "discover: one source policy, and one the skill actually obeys

Pagination and detail fetch move from Red to Yellow with caps that a
script enforces (max_rows_per_round, max_pages_per_site, detail only for
strong_apply/worth_applying/stretch). Red keeps captcha and fingerprint
evasion, proxies, multi-account rotation, unattended operation, batch
outreach, unsourced openness claims, and every access: write command.
The changelog names the cookie-strategy line honestly instead of quietly
dropping it, and says outright that account risk is not zero.

Also gives the file the two things every layer-2 file needs and this one
had neither of: a SKILL.md trigger you can evaluate before opening it
(before the first live retrieval of any run) and a named backstop
(CAP_MISSING / CAP_ABOVE_CEILING on brief.yaml's two round caps)."
    ```

---

### Task 7: the discover mode file (layer 1.5)

**Files:**
- Create: `modes/discover.md`
- Test: `scripts/tests/test_discover_mode_doc.py`

**Interfaces:**
- Consumes: `check_shortlist.REQUIRED_ROW_FIELDS`, `check_shortlist.VERDICTS`, `check_shortlist.EFFORT`, `check_shortlist.TOP_THREE`, `check_shortlist.DISCLOSURE_LABELS`, `check_shortlist.PROVISIONAL_STAMP`, `check_shortlist.EXTRACTION_METHODS`, `check_shortlist.QUALITIES`, `check_shortlist.VERIFICATIONS` (Tasks 3-4); `check_opencli_result.CLASSIFICATIONS` (Task 1); `scripts/enter_mode.py` and `scripts/paths.py` (Plan 1) as the commands and helpers the file instructs
- Produces: `modes/discover.md` — the **only** definition of the `brief.yaml`, `shortlist.yaml` and `search-preferences.yaml` schemas. Nothing else in the tree defines them, which is what makes the gates' field requirements a backstop for having read this file.

**Three things this task settles that were previously loose ends.** (1) `search-preferences.yaml` is in the spec's shared spine (§4.3) and `modes/assess.md` already branches on its contents, but no plan created it — discover owns it, so it is defined here, with the interview that fills it. (2) The mode-entry command is step zero, which gives layer 1.5 the **second** half of its backstop (spec §4.2: the gate requires a field only this file defines, *and* `journal.jsonl` records this file's hash) — the gate half lands in Task 8. (3) `insufficient_evidence` stops being described as a shortlist row: the gate rejects it, so instructing it would have been instructing an output the run's own gate refuses.

- [ ] **Step 1: Write the failing test**

    Create `scripts/tests/test_discover_mode_doc.py`:

    ```python
    """The mode file is layer 1.5: loaded unconditionally on entering discover.

    These assertions are its backstop. Every row field a gate requires, every verdict
    string, every disclosure label and every script name must be findable here,
    because a mode file that drifts from the gates fails silently — the run just
    produces a shortlist the gate then rejects for a reason the mode never mentioned.
    """
    import pathlib

    import check_opencli_result as coc
    import check_shortlist as cs

    REPO = pathlib.Path(__file__).resolve().parents[2]
    MODE = REPO / "modes" / "discover.md"


    def text():
        return MODE.read_text(encoding="utf-8")


    def test_every_row_field_the_gate_requires_is_defined_here():
        body = text()
        for field in cs.REQUIRED_ROW_FIELDS:
            assert field in body, f"row field {field!r} is defined nowhere"


    def test_every_enum_value_the_gate_accepts_is_listed_here():
        body = text()
        for value in (cs.EXTRACTION_METHODS + cs.QUALITIES + cs.VERIFICATIONS):
            assert value in body, f"enum value {value!r} is listed nowhere"


    def test_all_five_verdicts_and_the_provisional_rule_are_present():
        body = text()
        for verdict in cs.VERDICTS:
            assert verdict in body
        assert "provisional: true" in body
        assert "assess 一律重算" in body


    def test_only_the_top_three_verdicts_may_get_a_detail_fetch():
        body = text()
        for verdict in cs.TOP_THREE:
            assert verdict in body
        assert "未取详情" in body


    def test_the_disclosure_block_ships_prefilled_with_no():
        body = text()
        for label in cs.DISCLOSURE_LABELS:
            assert label in body, f"disclosure label {label!r} missing"
        for label in ("收到限制信号后重试：", "绕过任何平台控制：", "取得真实岗位："):
            line = next(l for l in body.splitlines() if label in l)
            assert line.split(label, 1)[1].strip() == "否", (
                f"{label!r} must ship pre-filled as 否 so concealment is an active "
                "overwrite, not an omission")


    def test_the_three_auth_states_are_distinguished():
        body = text()
        for state in ("logged_in", "not_logged_in", "unknown", "no_auth_adapter"):
            assert state in body
        assert "EMPTY STRING" in body
        assert "--full" in body


    def test_every_classification_the_wrapper_can_return_has_an_action():
        body = text()
        for classification in coc.CLASSIFICATIONS:
            assert classification in body


    def test_bilingual_query_generation_is_required_with_its_reason():
        assert "English-only keywords miss local-language postings" in text()


    def test_the_exit_code_rule_is_restated_here():
        body = text()
        assert "先看 exit code" in body
        assert "JSON.parse(stdout || '[]')" in body


    def test_the_no_fabrication_rule_is_restated_at_why_matched():
        # spec §8: the fence is repeated in exactly three places, and the
        # shortlist's why_matched field is one of them.
        #
        # Anchored on the DEFINITION, not on the first mention of the word. The
        # first mention is Step 0's "Write how, per row, in `why_matched`", and a
        # window measured from there is satisfied by the unrelated "Never pad the
        # count." two paragraphs later — so the earlier version of this test passed
        # with the entire fence paragraph deleted.
        body = text()
        anchor = "**`why_matched` is one of exactly three places"
        index = body.find(anchor)
        assert index != -1, "the why_matched fence paragraph is gone"
        window = body[index:index + 700]
        assert "绝不" in window
        assert "write a reason that the card does not support" in body


    def test_every_script_and_reference_this_mode_uses_is_named():
        body = text()
        for name in ("scripts/enter_mode.py", "scripts/check_opencli_result.py",
                     "scripts/check_no_write.py", "scripts/check_shortlist.py",
                     "scripts/paths.py", "references/discovery-sources.md",
                     "references/source-policy.md",
                     "references/risk-control-signals.yaml"):
            assert name in body, f"{name} is not named in the self-check list"


    def test_the_platform_limit_stop_rule_is_absolute():
        body = text()
        assert "不重试" in body
        assert "不改参数重试" in body
        assert "不绕过" in body


    def test_the_finding_codes_an_operator_must_react_to_are_explained():
        body = text()
        for code in ("SOURCE_ID_NOT_IN_RAW", "EMPTY_RESULT_UNSUPPORTED",
                     "DETAIL_FETCH_OUT_OF_BAND", "DEGRADED_WITHOUT_DISCLOSURE",
                     "WRITE_COMMAND", "UNKNOWN_ACCESS"):
            assert code in body


    def test_the_workspace_path_shape_is_load_bearing_and_stated():
        body = text()
        assert "searches/<YYYY-MM-DD>-<slug>" in body
        assert "raw/<site>-<n>.json" in body
        # R4: the spine paths are resolved through scripts/paths.py, never
        # rebuilt by hand, so the resume-an-unfinished-run lookup keeps working.
        assert "paths.search_dir(" in body
        assert "paths.search_prefs(" in body


    def test_the_mode_entry_command_is_the_first_thing_the_file_asks_for():
        # Layer 1.5's second backstop (spec §4.2): the gate requires a field only
        # this file defines, AND journal.jsonl records this file's content hash.
        # Without the second half, "loaded unconditionally" is a hope.
        body = text()
        assert "scripts/enter_mode.py --workspace <ws> --mode discover" in body
        assert "NO_MODE_ENTRY" in body
        assert "MODE_FILE_CHANGED" in body
        entry = body.index("scripts/enter_mode.py")
        for later in ("## Step 0", "opencli auth status"):
            assert body.index(later) > entry, (
                f"{later!r} comes before the mode-entry command; entry is step zero")


    def test_the_search_preferences_schema_is_defined_here():
        # spec §4.3 puts search-preferences.yaml in the shared spine and §5.2 has
        # assess branch on it. discover owns writing it, so discover defines it —
        # a schema two modes read and no mode defines is a schema that drifts.
        body = text()
        assert "search-preferences.yaml" in body
        for field in ("target_market", "locations", "seniority", "work_models",
                      "languages", "salary_floor", "avoid", "experience_track"):
            assert field in body, f"search-preferences field {field!r} is defined nowhere"
        assert "cn / nl / de / uk / us / other" in body
        assert "asked, never inferred" in body


    def test_the_effort_vocabulary_is_defined_here():
        body = text()
        for value in cs.EFFORT:
            assert value in body, f"effort value {value!r} is listed nowhere"
        assert "order by effort" in body.lower()


    def test_insufficient_evidence_is_never_a_shortlist_row():
        # A refusal state is not a listing. check_shortlist.VERDICTS is the five
        # levels, so a row carrying it fires BAD_VERDICT — a mode file that asks
        # for one would be instructing an output its own gate rejects.
        body = text()
        assert "insufficient_evidence" in body          # it IS named…
        assert "dropped from the shortlist" in body     # …as a drop, not a row
        assert "the row is `insufficient_evidence`" not in body


    def test_the_card_based_stamp_is_required_in_the_rendered_markdown_too():
        body = text()
        assert cs.PROVISIONAL_STAMP in body
        assert "MD_MISSING_PROVISIONAL_STAMP" in body
    ```

- [ ] **Step 2: Run the test to verify it fails**

    Run: `python3 -m pytest scripts/tests/test_discover_mode_doc.py -q`
    Expected: FAIL — every test errors with `FileNotFoundError: .../modes/discover.md`

- [ ] **Step 3: Write the mode file**

    `mkdir -p modes`, then create `modes/discover.md`:

    ````markdown
    # Mode: discover — 找什么

    Loaded unconditionally on entering discover mode. Read it in full before the first
    adapter call.

    **What this mode does:** turn a search intent into a shortlist of real, retrieved
    job listings with a provisional verdict on each. **What it does not do:** it never
    chains into `apply`. Thirty rows do not become thirty CVs; the whole point of
    ranking a shortlist is to let a person choose.

    ## On entering this mode — before anything else

    ```bash
    python3 scripts/enter_mode.py --workspace <ws> --mode discover
    ```

    This writes a `mode_entry` record carrying **this file's content hash** into
    `journal.jsonl`. It is not bookkeeping: it is the half of the layer-1.5 backstop
    that a gate can see. `check_shortlist.py` fails the run with `NO_MODE_ENTRY` when
    the record is absent, and with `MODE_FILE_CHANGED` when the hash no longer matches
    the file on disk — meaning what was read is not what is now here, so re-enter and
    re-read. It is also what makes every receipt in this run stamped
    `"mode": "discover"` instead of `"unknown"`.

    Then read this file in full. Both halves matter: the gate below requires
    `shortlist.yaml` fields that are defined nowhere else, and the hash proves the
    definition you followed is the definition on disk.

    ## Entry conditions (any one)

    1. The user wants to find or compare roles.
    2. `assess` returned `likely_screen_out` or `blocked`.
    3. The honest-gap early-stop fired.
    4. `assess` returned `stretch` and the user has not said they want that specific job.
    5. The user supplied two or more postings (ranking mode).

    Discover is **never** triggered as a side effect of another mode. The user starting
    it is the opt-in. Probing could not confirm whether read commands leave server-side
    traces (whether `linkedin inbox` marks a thread read, for instance), so there are no
    implicit calls.

    ## Ownership

    | Reads | Writes |
    |---|---|
    | `profile.yaml` (never modified by any mode) | `searches/<YYYY-MM-DD>-<slug>/`, plus `search-preferences.yaml` — the one spine file discover owns |

    Discover is the **only** mode that writes `search-preferences.yaml`. `assess` reads
    it and must not create it: a file two modes write is a file whose contents nobody
    can account for.

    Workspace layout — **the path shape is load-bearing**, the resume-an-unfinished-run
    feature finds work by this shape:

    ```text
    ~/.claude/job-profiles/<name>/searches/<YYYY-MM-DD>-<slug>/
      brief.yaml                 this round's reproducible search basis
      shortlist.yaml             the structured shortlist
      shortlist.md               readable: §0 来源与读取质量, §0.1 触发原因, §0.2 披露
      raw/<site>-<n>.json        adapter stdout, VERBATIM, never edited
      raw/<site>-<n>.err         adapter stderr for the same call
      raw/opencli-help/<site>.yaml   the adapter's own metadata for this run
      raw/auth-status.json       the auth probe output
      journal.jsonl              mode_entry + adapter_call records + gate receipts
    ```

    **Resolve both spine paths through `scripts/paths.py`, never by hand:**
    `paths.search_dir(<name>, "<YYYY-MM-DD>-<slug>")` for the workspace above and
    `paths.search_prefs(<name>)` for the preferences file below. One module owns the
    layout, and a run that string-joins its own version orphans the previous workspace
    with no error anywhere.

    `raw/*` is where every downstream claim's provenance chain terminates. Edit it and
    source tracing becomes theatre.

    ## The shared search preferences — asked once, reused, confirmed

    `paths.search_prefs(<name>)` → `~/.claude/job-profiles/<name>/search-preferences.yaml`.
    Discover **owns** this file: it is the only mode that writes it, and `assess` reads
    it to avoid asking for the target market once per posting.

    ```yaml
    updated: "2026-08-09"
    target_market: cn                    # cn / nl / de / uk / us / other
    locations: ["上海", "西安"]           # cities or regions, in the market's own language
    seniority: mid                       # new_grad|junior|mid|senior|unknown
    work_models: ["onsite", "hybrid"]    # remote|hybrid|onsite
    languages: ["Chinese", "English"]    # languages the user can work in
    salary_floor: {currency: CNY, amount: 30000, period: month}   # or null
    avoid: ["外包", "销售导向岗位"]
    experience_track: "medical imaging / MRI reconstruction"
    ```

    **Every field here is asked, never inferred.** Reading a salary floor off a past
    payslip, an avoid-list off a CV, or a target market off the language someone happens
    to be typing in produces a file that looks like the user's preferences and is not —
    and because it is reused across every later round, one wrong inference quietly
    steers months of searching.

    - **First run** (the file does not exist): ask the eight questions above, in the
      user's language, in one pass. `salary_floor: null` is a legitimate answer and the
      only correct one if the user declines — never substitute a market median.
      `target_market: other` is likewise legitimate: markets outside `cn/nl/de/uk/us`
      have no convention data, and saying so beats borrowing a neighbour's.
    - **Later runs:** read it, show the user what it says, and **confirm once per
      session** — not once per posting. Re-ask whenever this round's locations sit in a
      different market than `target_market`.
    - Rewriting it is an explicit act with the user watching. Bump `updated` when you do.
    - `brief.yaml` below is this round's *narrowing* of these preferences, not a copy of
      them: preferences are durable, a brief is one round.

    ## Step 0 — state the trigger reason BEFORE searching

    Say why this search is happening, then write it into `brief.yaml` as
    `trigger_reason` and into `shortlist.md` under `## §0.1 触发原因`. Stating it
    afterwards is a rationalisation; `check_shortlist.py` fires `NO_TRIGGER_REASON` and
    `NO_TRIGGER_SECTION` if either is missing.

    If the original JD was judged unsuitable: **this round's candidates must be visibly
    more solid than it, not merely similarly titled.** Write how, per row, in
    `why_matched`.

    ### brief.yaml — this round's reproducible basis

    ```yaml
    slug: 2026-08-09-suanfa-shanghai       # <YYYY-MM-DD>-<short-slug>
    created: "2026-08-09"
    trigger_reason: "上一份 JD 被 assess 判为 likely_screen_out（缺 C++ 生产经验）…"
    target_titles: ["算法工程师", "algorithm engineer"]
    markets: ["cn"]                        # cn / nl / de / uk / us / other
    locations: ["上海", "西安"]
    seniority: mid                         # new_grad|junior|mid|senior|unknown
    employment_types: ["full_time"]
    work_models: ["onsite", "hybrid"]      # remote|hybrid|onsite
    languages: ["Chinese", "English"]
    must_have_constraints: ["work authorization: …"]
    nice_to_have: ["计算机视觉"]
    avoid: ["外包", "销售导向岗位"]
    target_count: 12                       # how many rows the user wants
    max_rows_per_round: 25                 # yellow-layer cap, per site per round
    max_pages_per_site: 2                  # yellow-layer cap
    max_age_days: 30                       # older than this ⇒ verification: stale_possible
    ```

    `target_count` and `max_rows_per_round` are different things: the first is the goal,
    the second is the politeness cap from `references/source-policy.md`. Falling short of
    `target_count` requires a written `shortfall_reason` in `shortlist.yaml`
    (`SHORTFALL_NO_REASON`). **Never pad the count.**

    ## Step 1 — probe the login state (three states, not two)

    ```bash
    opencli auth status -f json > raw/auth-status.json
    ```

    - `status: "logged_in"` — usable.
    - `status: "not_logged_in"` — usable only for adapters that do not need a session.
    - `status: "unknown"` — **not the same as logged out.** Its `logged_in` field is an
      **EMPTY STRING**, not `false`, so `if (!row.logged_in)` misreads it. Re-probe:
      `opencli auth status --site <sites> --full --timeout 40 -f json`, which runs the
      read-only `whoami` and returns `checked: "full"`.
    - **Site absent from the list entirely** — `no_auth_adapter`. `indeed` and `51job`
      are simply not there (65 rows returned, neither matched) and neither exposes a
      `login` or `whoami` command. This is not an error and not a missing adapter: it
      means the site has no login concept. Never run `opencli 51job login`; it does not
      exist.

    Also save each adapter's own contract before calling it — `check_no_write.py` reads
    it from here:

    ```bash
    mkdir -p raw/opencli-help
    opencli <site> --help -f yaml > raw/opencli-help/<site>.yaml
    ```

    ## Step 2 — choose sources

    Prefer sources that need no login. `51job` is the only adapter measured to return
    every documented column populated. `indeed` also works without login but returns
    empty titles (Step 4). For the four inlined adapters, use the command pairs in
    SKILL.md. For anything else, read `references/discovery-sources.md` first.

    ## Step 3 — generate queries in BOTH languages

    Generate the keyword set in English **and** in the market's local language, and run
    both. **English-only keywords miss local-language postings**, which is not a
    rounding error in NL/DE/CN: a Dutch employer posting "Onderzoeker beeldreconstructie"
    or a Chinese one posting "图像重建算法工程师" is invisible to an English-only query,
    and the resulting empty result looks exactly like "there are no such jobs".

    Record every query string in `brief.yaml.target_titles` so the round is reproducible.

    ## Step 4 — run the search, read the exit code first

    One round per site, capped at `max_rows_per_round`, `-f json`, `--window background`.
    **No detail pages at this stage.** Capture stdout and stderr to separate files, then
    classify:

    ```bash
    set +e
    opencli 51job search "算法工程师" --area 上海 --page 1 --limit 25 \
        --window background -f json > raw/51job-1.json 2> raw/51job-1.err
    RC=$?
    set -e
    python3 scripts/check_opencli_result.py --workspace . --site 51job --command search \
        --exit-code "$RC" --stdout-file raw/51job-1.json --stderr-file raw/51job-1.err \
        --auth-status-file raw/auth-status.json \
        --command-line 'opencli 51job search "算法工程师" --area 上海 --page 1 --limit 25 --window background -f json'
    ```

    **先看 exit code，再解释「空」。** A login wall gives exit 1, EMPTY stdout and a YAML
    error body on stderr *even under `-f json`*, so `JSON.parse(stdout || '[]')` silently
    converts a 403 into a zero-result success. Only `exit == 0` **and** stdout parsed to
    an array is "no results".

    The wrapper returns one of five classifications, each with an action:

    | classification | what happened | what to do |
    |---|---|---|
    | `ok` | exit 0, JSON array parsed | continue to Step 5 |
    | `not_logged_in` | login wall, and auth says the session is absent or unknown | cross-check auth; hand `opencli <site> login` **to the user** — it is a write command. Do not retry: the refusal is deterministic while logged out. **Do not treat `strategy: public` as evidence that no login is needed** — 1point3acres' public-strategy `forum` still 403s. |
    | `no_auth_adapter` | login wall on a site with no login concept | the platform is refusing, not the session. Drop the site for this round and say so. |
    | `platform_limit` | a stop-signal from `references/risk-control-signals.yaml`, or a refusal while auth says logged in | **立即停止。不重试、不改参数重试、不绕过。** Emit the degraded output below. |
    | `transport` | unrecognised failure, or exit 0 with unparsable stdout | run `opencli doctor` — a dead browser bridge takes out every `browser: true` command on every site at once, which distinguishes infrastructure failure from a single-site problem. |

    ## Step 5 — row integrity, before anything else

    Assert the identity field is non-empty on every returned row: `title` for every
    adapter except `boss`, where it is `name`. The wrapper reports this as
    `empty_identity_rows` / `needs_detail_recovery`.

    `indeed` is measured to return exit 0, valid JSON, and empty `title`/`salary`/`tags`
    while `id`/`company`/`location`/`url` are populated. Recover each row with
    `opencli indeed job <id>` and report the gap in `§0`. **绝不** infer "this site has
    no such jobs" from blank fields — the rows existed.

    ## Step 6 — normalise, then de-duplicate

    Every row becomes one `JobListingEvidence` entry plus this skill's four additions
    (`why_matched`, `verdict`, `provisional`, `effort`). This schema is defined here and
    nowhere else; `check_shortlist.py` requires all seventeen fields.

    ```yaml
    - id: 51job-173198362              # <site>-<source_id>, stable within the search
      title: 高级算法工程师（视觉调试智能化、AI方向）   # non-empty, or recover it
      company: 比亚迪汽车工业
      location: 西安 · 高新技术产业开发区
      salary: 3-6万                     # verbatim display string from the adapter
      url: https://jobs.51job.com/xian-gxjs/173198362.html   # tracking params stripped
      source_site: 51job
      source_id: "173198362"           # MUST appear verbatim in raw/51job-*.json
      extraction_method: adapter_search # adapter_search|adapter_detail|user_paste|public_page
      retrieved_at: "2026-08-09T14:02:11Z"
      quality: card_only               # complete|partial|card_only
      verification: collected_unverified # fresh_verified|collected_unverified|stale_possible
      raw_text: "…the card text the evaluator actually saw…"
      why_matched: "…"                 # see the rule below
      verdict: worth_applying          # the five levels, nothing else
      provisional: true                # always true in discover
      effort: evening                  # quick|evening|multi_day|not_closable
    ```

    - `quality`: `card_only` = search row only; `partial` = search row with fields
      recovered by a detail call; `complete` = the detail page was fetched.
    - `effort`: how much work the row's *closable* gaps would take, from the card you
      actually have — `quick` (rewording and reordering what is already true),
      `evening` (one focused session: a small demo, a short write-up),
      `multi_day`, `not_closable` (the gap is a hard disqualifier or years of
      experience). It is what makes the within-band ordering in Step 7 a rule rather
      than a sentiment, so it is a closed vocabulary the gate checks (`BAD_ENUM`), not
      free text. Estimate it from the card and say so; do not pretend a card told you
      more than it did.
    - `verification`: `fresh_verified` only when a detail call in **this** session
      returned the posting; `collected_unverified` for a card; `stale_possible` when the
      source's own posting date is older than `brief.max_age_days`.
    - De-duplicate across platforms on company + normalised title + location; keep the
      row with the higher `quality`.

    **`why_matched` is one of exactly three places where the no-fabrication fence is
    restated, and this is that restatement.** Cite the brief field and the raw field
    that made the match — "brief.target_titles 命中「算法工程师」；raw salaryMin 30000
    在 brief 区间内". **绝不** write a reason that the card does not support, and 绝不
    borrow a requirement from a JD you have not fetched. An invented `why_matched` is
    the most persuasive part of a fabricated row.

    ## Step 7 — provisional verdicts

    First scan for hard disqualifiers (work authorisation, licence, mandatory language,
    hard location) — a hit is `blocked` immediately. Everything else takes an ordinal
    level from the same vocabulary `assess` uses:

    `strong_apply` · `worth_applying` · `stretch` · `likely_screen_out` · `blocked`

    Within a level, **order by effort** — `quick` first, then `evening`, `multi_day`,
    `not_closable` — using each row's `effort` field. Ordering by effort-to-close is
    what turns a band into a plan: two `worth_applying` rows are not equally worth the
    user's next hour.

    **Every discover verdict carries `provisional: true` and may not be rendered without
    it.** That is two obligations, and both are checked:

    - in `shortlist.yaml`, the field itself (`MISSING_PROVISIONAL`);
    - in `shortlist.md`, the words **「基于卡片信息的初判」** on the section that renders
      the rows (`MD_MISSING_PROVISIONAL_STAMP`). A YAML boolean is not a disclosure —
      nobody reading the round ever sees it, and `shortlist.md` is what they read.

    The stamp is load-bearing: discover has a card, `assess` has the full JD and
    evidence blocks. Using one vocabulary without marking the confidence source would be
    passing card data off as a completed assessment.
    **规则：discover 的档位永不被带进 assess——assess 一律重算。**

    If a card cannot support any level at all, the card is **dropped from the shortlist**
    and counted in `shortfall_reason` — name it there, with what was missing. It does
    **not** become a row carrying `insufficient_evidence`: that is an orthogonal refusal
    state, not a sixth level and not a listing, and `check_shortlist.py` would reject
    such a row with `BAD_VERDICT`. A shortlist row asserts "this posting exists and here
    is what I make of it"; a card you cannot read supports the first half and not the
    second, so it belongs in the shortfall, not in the list.

    ## Step 8 — detail fetch, top three only

    Fetch detail pages **only** for `strong_apply`, `worth_applying` and `stretch`.
    `likely_screen_out` and `blocked` rows stay card-level and are labelled **未取详情**
    in `shortlist.md`; the user can name one to fetch anyway, which is recorded in
    `shortlist.yaml.detail_fetch_exceptions` with a reason. `check_shortlist.py` enforces
    this as `DETAIL_FETCH_OUT_OF_BAND`. This cap is where detail fan-out stops being a
    crawl, and it is the mechanism that keeps this mode inside the yellow tier of
    `references/source-policy.md`.

    Each detail call goes through `scripts/check_opencli_result.py` too, and its stdout
    lands in `raw/<site>-detail-<id>.json`.

    ## Step 9 — write the outputs

    `shortlist.yaml`:

    ```yaml
    search_slug: 2026-08-09-suanfa-shanghai
    brief: brief.yaml
    shortfall_reason: null          # required (a written sentence) when rows < target_count
    detail_fetch_exceptions: []     # [{id: …, reason: 用户点名要求补取}]
    sources:                        # one entry per site used
      - site: 51job
        command: search
        access: read
        login_state: no_auth_adapter
        classification: ok          # MUST match what journal.jsonl recorded
        invocations: 1
        rows_returned: 25
        identity_field: title
        identity_field_empty_rows: 0
        detail_command: "opencli 51job detail <jobId>"
        raw_files: ["raw/51job-1.json"]
    rows: [...]
    ```

    `identity_field` and `detail_command` for any adapter outside the four inlined in
    SKILL.md come from `references/discovery-sources.md`. There is no other source for
    them, which is why `SOURCE_REPORT_MISSING` is that file's backstop.

    `shortlist.md` carries `## §0 来源与读取质量`, `## §0.1 触发原因`, and — when the run
    is degraded — `## §0.2 披露`. The section that lists the rows carries the stamp in
    its own heading, e.g. `## §1 候选（全部为基于卡片信息的初判 · provisional）`, and each
    row shows its band and its `effort`. Rows below the top three are labelled
    **未取详情**.

    ## Degraded output — when no real postings could be retrieved

    Emit a **direction-level shortlist** (3-5 directions), each with: 目标方向 ·
    检索词 · 建议筛选条件 · 为何比原 JD 更稳 · 要避开的标题与信号 · 手动收集优先序.
    It has no `rows:`, so it cannot claim a posting exists.

    Then the disclosure block, verbatim, in `shortlist.md`:

    ```text
    本次会话已登录：        <是|否|不适用—无 auth adapter>
    Adapter 返回：          <逐字错误信息>
    收到限制信号后重试：    否
    绕过任何平台控制：      否
    取得真实岗位：          否
    降级输出类型：          方向级 shortlist
    ```

    The last four answers ship **pre-filled as 否**. That is the design: concealing a
    retry or a bypass has to be an active overwrite, not an omission.
    `check_shortlist.py` fires `DEGRADED_WITHOUT_DISCLOSURE` when the block is absent and
    `DISCLOSURE_INCOMPLETE` when an answer is blank.

    And the wording rule: **"没有匹配" is a claim, and it needs a receipt.** All-adapters-
    failed and genuinely-found-nothing produce the identical shape, so
    `EMPTY_RESULT_UNSUPPORTED` fires unless at least one adapter exited 0. If every
    adapter died, say *that*, not "there are no jobs".

    ## Step 10 — gates, and cite the receipts

    ```bash
    python3 scripts/check_no_write.py  --workspace .
    python3 scripts/check_shortlist.py --workspace .
    ```

    Both must exit 0. **This mode may not claim success without a passing receipt for
    each in `journal.jsonl`** — a skipped script produces no output, and that looks
    exactly like a clean one.

    | Finding | What it means | What to do |
    |---|---|---|
    | `NO_MODE_ENTRY` | `journal.jsonl` has no `mode_entry` for discover | run `scripts/enter_mode.py --workspace <ws> --mode discover` and read this file — it was not loaded |
    | `MODE_FILE_CHANGED` | this file changed after the run entered the mode | what you read is not what is on disk. Re-enter and re-read. |
    | `SOURCE_ID_NOT_IN_RAW` | a row's identifier is in no capture from that site | delete the row. It was not retrieved. Do not "fix" it by editing `raw/`. |
    | `URL_NOT_FROM_ADAPTER` | the URL was assembled, not returned | replace it with the adapter's URL or drop the field |
    | `DUPLICATE_SOURCE_ID` | one retrieved posting appears as two rows | delete the duplicate; de-duplication removes rows, nothing adds them |
    | `SOURCE_REPORT_COUNT_MISMATCH` | the source report claims more than the receipts recorded | the receipts are right. Never reconcile by editing `raw/` or the journal. |
    | `EMPTY_RESULT_UNSUPPORTED` | "no results" wording with no adapter that exited 0 | rewrite as "every adapter failed", and emit the disclosure block |
    | `DEGRADED_WITHOUT_DISCLOSURE` | degraded run with no disclosure block | add the block, answers pre-filled 否 |
    | `MD_MISSING_PROVISIONAL_STAMP` | `shortlist.md` renders rows without 「基于卡片信息的初判」 | add the stamp to the section heading. The YAML flag is not a disclosure. |
    | `DETAIL_FETCH_OUT_OF_BAND` | a detail fetch below the top three verdicts | remove it, or record a named exception with a reason |
    | `CAP_MISSING` / `CAP_ABOVE_CEILING` | `brief.yaml`'s round caps are absent or raised | read `references/source-policy.md`; the caps are its enforceable half |
    | `SHORTFALL_NO_REASON` | fewer rows than `target_count`, no reason written | write the reason. Never pad. |
    | `SOURCE_REPORT_CONTRADICTS_JOURNAL` | `sources:` disagrees with the receipts | the receipts are right; fix the report |
    | `WRITE_COMMAND` | a write command was journaled | stop. Tell the user exactly what ran. It cannot be undone. |
    | `UNKNOWN_ACCESS` | a command's access could not be resolved | save `opencli <site> --help -f yaml` into `raw/opencli-help/` and re-run |

    ## Self-check before reporting the round

    - [ ] `scripts/enter_mode.py --mode discover` run **first**, and this file read in full.
    - [ ] `search-preferences.yaml` read via `paths.search_prefs(<name>)`; written on
          first run from answers the user gave, never from inference; confirmed once
          this session.
    - [ ] `brief.yaml` written **before** the first adapter call, with `trigger_reason`
          and both round caps.
    - [ ] `raw/opencli-help/<site>.yaml` saved for every site called.
    - [ ] `raw/auth-status.json` saved; `unknown` re-probed with `--full`.
    - [ ] Every adapter call classified by `scripts/check_opencli_result.py`.
    - [ ] Queries generated in both languages of the market.
    - [ ] Identity field asserted non-empty on every row; `indeed` rows recovered.
    - [ ] Every row carries `provisional: true` **and** `shortlist.md` carries
          「基于卡片信息的初判」; no verdict copied into an assessment.
    - [ ] Every row carries an `effort` value, and rows are ordered by it within a band.
    - [ ] Cards that could not support any level were dropped and named in
          `shortfall_reason` — not listed as `insufficient_evidence` rows.
    - [ ] Detail fetched only for `strong_apply` / `worth_applying` / `stretch`.
    - [ ] `references/source-policy.md` re-read if any action felt like it might be
          yellow or red; `references/risk-control-signals.yaml` consulted on any failure.
    - [ ] `references/discovery-sources.md` read before calling any adapter outside the
          four inlined in SKILL.md.
    - [ ] `scripts/check_no_write.py` and `scripts/check_shortlist.py` both exited 0, and
          the completion message cites their `journal.jsonl` receipts.
    - [ ] No chaining into `apply`. The shortlist is handed back for a person to choose.
    ````

- [ ] **Step 4: Run the test to verify it passes**

    Run: `python3 -m pytest scripts/tests/test_discover_mode_doc.py -q`
    Expected: PASS (19 passed)

- [ ] **Step 5: Commit**

    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add modes/discover.md scripts/tests/test_discover_mode_doc.py
    git commit -m "discover: the mode file, with the row schema the gates require

modes/discover.md is layer 1.5 and the only definition of brief.yaml,
shortlist.yaml and search-preferences.yaml, so the gates' field
requirements are a backstop for having read it. Carries the mode-entry
command as step zero, the trigger-reason-first rule, the three auth
states and the empty-string trap, bilingual query generation and why it
matters, the provisional stamp in BOTH outputs (the YAML flag is not a
disclosure — nobody reads it), effort-to-close as the within-band
ordering key, the top-three detail cap, the absolute platform-limit
stop, the pre-filled disclosure block, and a self-check naming every
script and reference.

search-preferences.yaml is defined here because discover owns it: spec
4.3 puts it in the shared spine and assess branches on it, and until now
no mode created it. Every field is asked, never inferred — it is reused
across every later round, so one wrong inference steers months of
searching.

A card that cannot support any level is DROPPED and named in
shortfall_reason. It used to be described as an insufficient_evidence
row, which check_shortlist rejects with BAD_VERDICT: the file was
instructing an output its own gate refuses."
    ```

---

### Task 8: the layer-1.5 mode-entry backstop

**Files:**
- Modify: `scripts/check_shortlist.py` (add `_check_mode_entry` and the `--skill-root` flag)
- Modify: `scripts/tests/discover_fixtures.py` (the valid workspace now records the mode entry)
- Test: `scripts/tests/test_check_shortlist_mode_entry.py`

**Interfaces:**
- Consumes: `enter_mode.latest_mode_entry(workspace, mode)`, `paths.mode_file(mode, root) -> pathlib.Path`, `paths.SKILL_ROOT`, `journal.sha256_file` (Plan 1); `modes/discover.md` (Task 7). **There is no `enter_mode.mode_file`** — Plan 1 puts the mode-file path in `paths.py` on purpose, so `enter_mode` and every gate resolve it the same way. Note the argument order: **mode first, root second.**
- Produces:
  - `check_shortlist.MODE: str` = `"discover"`
  - `check_shortlist._check_mode_entry(workspace, skill_root) -> list[str]`
  - Finding codes `NO_MODE_ENTRY`, `MODE_FILE_CHANGED`
  - `discover_fixtures.mode_entry_record() -> dict`; `discover_fixtures.write_journal(workspace, records, mode_entry=True)`

**Why this is its own task, after the mode file exists.** Spec §4.2 says layer 1.5 avoids the slides_maker regression because it has **two** backstops at once: the mode's gate requires an artifact field defined only in the mode file, **and** `journal.jsonl` records that file's content hash. Tasks 3-4 built the first half. Only `apply` had the second; `discover` had a mode file nothing could prove was read. It lands here rather than in Task 3 for a mechanical reason: the fixture has to hash `modes/discover.md`, which does not exist until Task 7.

- [ ] **Step 1: Write the failing test**

    Create `scripts/tests/test_check_shortlist_mode_entry.py`:

    ```python
    """The second half of the layer-1.5 backstop (spec §4.2).

    A mode file is only 'loaded unconditionally' if something reports that it was
    not. `check_shortlist` requires the mode_entry record, and requires the hash in
    it to still match the file on disk — otherwise what was read is not what is
    here, and the schema the run followed is not the schema being enforced.
    """
    import hashlib
    import pathlib

    import check_shortlist as cs
    import discover_fixtures as fx

    REPO = pathlib.Path(__file__).resolve().parents[2]


    def run(workspace, capsys):
        code = cs.main(["--workspace", str(workspace)])
        return code, capsys.readouterr()


    def test_a_workspace_that_entered_the_mode_is_quiet(tmp_path, capsys):
        # THE quiet twin. build_workspace records the entry the way
        # scripts/enter_mode.py does, so the backstop cannot start firing on an
        # ordinary run without every other shortlist test going red at once.
        workspace = fx.build_workspace(tmp_path)
        code, captured = run(workspace, capsys)
        assert code == 0
        assert captured.out == ""


    def test_no_mode_entry_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        fx.write_journal(workspace, fx.JOURNAL, mode_entry=False)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert captured.out.startswith("NO_MODE_ENTRY:")
        assert "scripts/enter_mode.py" in captured.out


    def test_a_mode_file_changed_after_entry_fires(tmp_path, capsys):
        workspace = fx.build_workspace(tmp_path)
        stale = dict(fx.mode_entry_record(),
                     mode_file_sha256=hashlib.sha256(b"an older draft").hexdigest())
        fx.write_journal(workspace, [stale] + list(fx.JOURNAL), mode_entry=False)
        code, captured = run(workspace, capsys)
        assert code == 1
        assert "MODE_FILE_CHANGED:" in captured.out
        assert "re-enter" in captured.out


    def test_the_hash_is_read_from_the_real_mode_file():
        # If this ever passes against a file that is not modes/discover.md, the
        # check is measuring nothing.
        record = fx.mode_entry_record()
        expected = hashlib.sha256(
            (REPO / "modes" / "discover.md").read_bytes()).hexdigest()
        assert record["mode_file_sha256"] == expected
    ```

- [ ] **Step 2: Run the test to verify it fails**

    Run: `python3 -m pytest scripts/tests/test_check_shortlist_mode_entry.py -q`
    Expected: FAIL, in **three shapes**, and only three of the four tests fail.
    `test_a_mode_file_changed_after_entry_fires` and
    `test_the_hash_is_read_from_the_real_mode_file` error with
    `AttributeError: module 'discover_fixtures' has no attribute 'mode_entry_record'`.
    `test_no_mode_entry_fires` errors with
    `TypeError: write_journal() got an unexpected keyword argument 'mode_entry'`, because
    Task 3's `write_journal(workspace, records)` has no such parameter yet.
    `test_a_workspace_that_entered_the_mode_is_quiet` **PASSES** — it is the quiet twin,
    and there is nothing yet for it to be quiet about. If it fails now, something else is
    already broken and Step 3 will hide it.

- [ ] **Step 3: Teach the fixture to record the mode entry**

    In `scripts/tests/discover_fixtures.py`, add these near the top, after the imports:

    ```python
    import hashlib

    REPO = pathlib.Path(__file__).resolve().parents[2]
    MODE_FILE = REPO / "modes" / "discover.md"


    def mode_entry_record():
        """The record scripts/enter_mode.py writes on entering discover.

        The hash is computed from the real modes/discover.md rather than pinned, so
        editing the mode file never turns every shortlist test red for a reason
        that has nothing to do with the shortlist.
        """
        return {"ts": "2026-08-09T14:01:00Z", "action": "mode_entry",
                "mode": "discover", "mode_file": "modes/discover.md",
                "mode_file_sha256": hashlib.sha256(
                    MODE_FILE.read_bytes()).hexdigest()}
    ```

    Then replace `write_journal` with the version below, and replace the journal-writing
    loop at the end of `build_workspace` with a single call to it:

    ```python
    def write_journal(workspace, records, mode_entry=True):
        """Rewrite journal.jsonl, keeping the workspace valid in every other respect.

        The mode_entry record is prepended by default: a test that mutates the
        adapter history is not also trying to assert that the mode was never
        entered, and if it had to remember to re-add the entry every time, the
        NO_MODE_ENTRY finding would show up in half the suite as noise.
        """
        head = []
        if mode_entry and not any(
                isinstance(r, dict) and r.get("action") == "mode_entry"
                for r in records):
            head = [mode_entry_record()]
        with (workspace / "journal.jsonl").open("w", encoding="utf-8") as handle:
            for record in head + list(records):
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    ```

    In `build_workspace`, this:

    ```python
        with (workspace / "journal.jsonl").open("w", encoding="utf-8") as handle:
            for record in JOURNAL:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return workspace
    ```

    becomes:

    ```python
        write_journal(workspace, JOURNAL)
        return workspace
    ```

- [ ] **Step 4: Add the check to the gate**

    In `scripts/check_shortlist.py`, add **both** imports next to the existing ones:

    ```python
    import enter_mode  # noqa: E402  (Plan 1)
    import paths       # noqa: E402  (Plan 1)
    ```

    `paths` is not optional here. Plan 1 states it in so many words: *there is no
    `enter_mode.mode_file`* — the mode-file path comes from `paths.mode_file(mode, root)`,
    so `enter_mode` and every gate cannot disagree about where a mode file lives. Writing
    `enter_mode.mode_file(...)` raises `AttributeError` on every call to `main`.

    Add the constant directly below `GATE`:

    ```python
    MODE = "discover"
    ```

    Add this function directly above `_fail_to_run`:

    ```python
    def _check_mode_entry(workspace, skill_root):
        """modes/discover.md is layer 1.5, and this is what reports it was not read.

        Mirrors check_apply.py deliberately: the same two findings, the same
        meaning, in the gate that belongs to this mode. Four modes with four
        different words for the same failure would be four things to learn.
        """
        findings = []
        entry = enter_mode.latest_mode_entry(workspace, MODE)
        mode_path = paths.mode_file(MODE, skill_root)   # mode first, root second
        if entry is None:
            findings.append(
                "NO_MODE_ENTRY: journal.jsonl has no mode_entry for discover. "
                "modes/discover.md is loaded unconditionally on entering the mode — "
                "it is the only definition of the brief, shortlist and preferences "
                "schemas — and this record is the only thing that reports it was "
                "not. Run `python3 scripts/enter_mode.py --workspace <ws> --mode "
                "discover`, then read the file.")
        elif (mode_path.is_file()
              and entry.get("mode_file_sha256") != journal.sha256_file(mode_path)):
            findings.append(
                "MODE_FILE_CHANGED: modes/discover.md changed after this run entered "
                "the mode, so the schema that was read is not the schema on disk. "
                "re-enter the mode and re-read it before trusting this shortlist.")
        return findings
    ```

    In `main`, add the flag next to `--workspace`:

    ```python
        parser.add_argument("--skill-root", type=pathlib.Path,
                            default=paths.SKILL_ROOT,
                            help="repo root holding modes/ (default: paths.SKILL_ROOT)")
    ```

    and change the line that builds the findings list from

    ```python
        findings = check_rows(shortlist, raw_texts)
    ```

    to

    ```python
        findings = _check_mode_entry(workspace, args.skill_root)
        findings.extend(check_rows(shortlist, raw_texts))
    ```

- [ ] **Step 5: Run all four shortlist modules to verify they pass**

    Run: `python3 -m pytest scripts/tests/test_check_shortlist_rows.py scripts/tests/test_check_shortlist_run.py scripts/tests/test_check_shortlist_mode_entry.py scripts/tests/test_discover_mode_doc.py -q`
    Expected: PASS (68 passed — 19 rows, 26 run, 4 mode-entry, 19 mode-doc). If the rows or run modules went red instead, the fixture is no longer recording the entry: fix the fixture, never the assertion.

- [ ] **Step 6: Commit**

    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/check_shortlist.py scripts/tests/discover_fixtures.py \
            scripts/tests/test_check_shortlist_mode_entry.py
    git commit -m "discover: require the mode-entry record, and that its hash still matches

Spec 4.2 gives layer 1.5 two backstops at once — the gate requires a
field only the mode file defines, AND journal.jsonl records that file's
content hash. discover had the first and not the second, so nothing
could tell a run that read modes/discover.md from one that improvised
the schema and happened to get the field names right.

NO_MODE_ENTRY and MODE_FILE_CHANGED are worded to match check_apply's:
four modes with four different words for one failure would be four
things to learn. The fixture records the entry the way enter_mode.py
does, so the quiet case is structural rather than aspirational."
    ```

---

### Task 9: end-to-end — hermetic chain, then a live read-only dry run

**Files:**
- Test: `scripts/tests/test_discover_e2e.py`

**Interfaces:**
- Consumes: `scripts/check_opencli_result.py`, `scripts/check_no_write.py`, `scripts/check_shortlist.py` (Tasks 1-4 and 8) run as subprocesses via their CLIs; `scripts/enter_mode.py` (Plan 1); `discover_fixtures.build_workspace` (Tasks 3 and 8)
- Produces: nothing importable — this task's deliverable is the proof that the three CLIs compose.

**One detail worth stating, because it looks like an arbitrary choice and is not.** The hermetic test classifies the **detail** capture, not the search one. Re-classifying the search would append a second `51job search` record, and `sources[51job]` honestly reports `invocations: 1` / `rows_returned: 2` — so `SOURCE_REPORT_COUNT_MISMATCH` would fire, correctly, and the composition test would be red for a reason that has nothing to do with composition. Classifying the detail call exercises the same round trip against a record the source report does not claim.

**The live leg is read-only.** `51job` has **no auth adapter**: it is absent from
`opencli auth status` and exposes no `login` command. Do not attempt a login on any
site. Do not run any command whose published `access:` is `write`. `--limit 3` keeps the
round tiny.

- [ ] **Step 1: Write the failing end-to-end test**

    Create `scripts/tests/test_discover_e2e.py`:

    ```python
    """The three CLIs, composed, on a workspace built from the real 51job capture.

    Unit tests prove each gate fires. This proves they compose: the wrapper's journal
    record is the same record the gates read back, through the real command-line
    interfaces rather than through Python imports.
    """
    import json
    import pathlib
    import subprocess
    import sys

    import discover_fixtures as fx

    REPO = pathlib.Path(__file__).resolve().parents[2]
    SCRIPTS = REPO / "scripts"


    def run(script, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / script), *args],
            capture_output=True, text=True)


    def journal_records(workspace):
        return [json.loads(line) for line
                in (workspace / "journal.jsonl").read_text(
                    encoding="utf-8").strip().splitlines()]


    def test_the_whole_chain_passes_on_a_real_capture(tmp_path):
        workspace = fx.build_workspace(tmp_path)

        detail = workspace / "raw" / "51job-detail-173199597.json"
        classify = run("check_opencli_result.py",
                       "--workspace", str(workspace),
                       "--site", "51job", "--command", "detail",
                       "--exit-code", "0",
                       "--stdout-file", str(detail),
                       "--command-line",
                       "opencli 51job detail 173199597 --window background -f json")
        assert classify.returncode == 0, classify.stderr
        assert json.loads(classify.stdout)["classification"] == "ok"

        no_write = run("check_no_write.py", "--workspace", str(workspace), "--no-fetch")
        assert no_write.returncode == 0, no_write.stdout + no_write.stderr
        assert no_write.stdout == ""

        shortlist = run("check_shortlist.py", "--workspace", str(workspace))
        assert shortlist.returncode == 0, shortlist.stdout + shortlist.stderr
        assert shortlist.stdout == ""

        records = journal_records(workspace)
        assert sum(1 for r in records if r.get("action") == "adapter_call") == 3
        gates = [r for r in records if r.get("action") == "gate"]
        assert {g["gate"] for g in gates} == {"check_no_write", "check_shortlist"}
        assert all(g["verdict"] == "pass" for g in gates)


    def test_a_hand_corrupted_source_id_is_caught_through_the_cli(tmp_path):
        workspace = fx.build_workspace(tmp_path)
        assert run("check_shortlist.py", "--workspace", str(workspace)).returncode == 0

        data = fx.load_shortlist(workspace)
        data["rows"][0]["source_id"] = "173190000"     # plausible, and not in raw/
        fx.save_shortlist(workspace, data)

        result = run("check_shortlist.py", "--workspace", str(workspace))
        assert result.returncode == 1
        assert result.stdout.startswith("SOURCE_ID_NOT_IN_RAW:")
        assert "51job-1.json" in result.stdout

        receipt = journal_records(workspace)[-1]
        assert receipt["gate"] == "check_shortlist"
        assert receipt["verdict"] == "fail"


    def test_a_hand_added_fabricated_row_is_caught_through_the_cli(tmp_path):
        # The failure this whole mode exists to prevent: a plausible row nobody
        # retrieved, with every field the right shape.
        workspace = fx.build_workspace(tmp_path)
        data = fx.load_shortlist(workspace)
        data["rows"].append({
            "id": "51job-173200001",
            "title": "资深计算机视觉算法工程师",
            "company": "某知名半导体设备公司",
            "location": "上海",
            "salary": "4-7万",
            "url": "https://jobs.51job.com/shanghai/173200001.html",
            "source_site": "51job",
            "source_id": "173200001",
            "extraction_method": "adapter_search",
            "retrieved_at": "2026-08-09T14:02:11Z",
            "quality": "card_only",
            "verification": "collected_unverified",
            "raw_text": "资深计算机视觉算法工程师 | 上海 | 4-7万",
            "why_matched": "标题与 brief.target_titles 高度一致",
            "verdict": "strong_apply",
            "provisional": True,
            "effort": "quick",
        })
        fx.save_shortlist(workspace, data)

        result = run("check_shortlist.py", "--workspace", str(workspace))
        assert result.returncode == 1
        codes = {line.split(":", 1)[0] for line in result.stdout.strip().splitlines()}
        assert "SOURCE_ID_NOT_IN_RAW" in codes
        assert "URL_NOT_FROM_ADAPTER" in codes
    ```

- [ ] **Step 2: Prove the test can fail — the negative control**

    Everything before this task watched a test go red before it went green. This one cannot: Tasks 1-4 and 8 are already done, so it passes the first time it runs, and a typo in `assert sum(...) == 3` or an assertion aimed at the wrong stream would be indistinguishable from a real pass. Break the chain on purpose and watch it report:

    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    mv scripts/check_shortlist.py scripts/check_shortlist.py.off
    python3 -m pytest scripts/tests/test_discover_e2e.py -q ; echo "rc=$?"
    mv scripts/check_shortlist.py.off scripts/check_shortlist.py
    ```

    Expected: **FAIL** — all three tests fail on the `check_shortlist.py` subprocess, which exits non-zero with `can't open file … check_shortlist.py`. If any of the three still PASSES with the gate removed, that test is not running the gate: fix it before continuing. Then confirm the file is back: `git status --short scripts/` must be empty.

- [ ] **Step 3: Run the test to verify it passes**

    Run: `python3 -m pytest scripts/tests/test_discover_e2e.py -q`
    Expected: PASS (3 passed). If it FAILS, the failure is real — fix the script, not the test. Do **not** proceed to the live leg with a failing chain.

- [ ] **Step 4: Run every module this plan created**

    Run:

    ```bash
    python3 -m pytest scripts/tests/test_check_opencli_result.py \
        scripts/tests/test_check_no_write.py \
        scripts/tests/test_check_shortlist_rows.py \
        scripts/tests/test_check_shortlist_run.py \
        scripts/tests/test_check_shortlist_mode_entry.py \
        scripts/tests/test_discovery_docs.py \
        scripts/tests/test_source_policy.py \
        scripts/tests/test_discover_mode_doc.py \
        scripts/tests/test_discover_e2e.py -q
    ```

    Expected: PASS (119 passed — 16 + 12 + 19 + 26 + 4 + 10 + 10 + 19 + 3).

    **Not the whole suite yet, and that is deliberate.** `scripts/tests/test_skill_structure.py` is still red: Plan 1 asserts `SKILL.md`'s `## Self-check` section names every script, reference and mode file in the tree, and this plan has added eight of them without registering any; `test_a_mode_that_exists_is_not_still_described_as_not_yet_built` is red too, because Task 7 created `modes/discover.md` while the `## Modes` table still calls it unbuilt. Task 10 does the registration, flips that row, and then runs the whole suite. Do not delete either assertion to make this step green.

- [ ] **Step 5: Live read-only dry run against 51job**

    Run exactly this. It touches only a temp directory and only `access: read` commands.

    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    export WS="$(mktemp -d)/2026-08-09-dryrun-51job"
    mkdir -p "$WS/raw/opencli-help"

    # Step zero of the mode, exercised for real: without it check_shortlist below
    # exits 1 with NO_MODE_ENTRY, which is the backstop doing its job.
    python3 scripts/enter_mode.py --workspace "$WS" --mode discover

    opencli 51job --help -f yaml > "$WS/raw/opencli-help/51job.yaml"
    opencli auth status -f json  > "$WS/raw/auth-status.json"

    set +e
    opencli 51job search "算法工程师" --area 上海 --page 1 --limit 3 \
        --window background -f json > "$WS/raw/51job-1.json" 2> "$WS/raw/51job-1.err"
    RC=$?
    set -e
    echo "exit=$RC"

    python3 scripts/check_opencli_result.py --workspace "$WS" \
        --site 51job --command search --exit-code "$RC" \
        --stdout-file "$WS/raw/51job-1.json" --stderr-file "$WS/raw/51job-1.err" \
        --auth-status-file "$WS/raw/auth-status.json" \
        --command-line 'opencli 51job search "算法工程师" --area 上海 --page 1 --limit 3 --window background -f json'
    ```

    Expected: `exit=0`, and a classification JSON with `"classification": "ok"`,
    `"row_count": 3`, `"empty_identity_rows": []`.

    **If the classification is not `ok`:** copy the classification JSON verbatim into the
    Step 7 commit message, then retry once with `indeed`
    (`opencli indeed search "mri" --limit 3 --window background -f json`, identity field
    `title`, expect `needs_detail_recovery: true`). If that also fails, run
    `opencli doctor`, record its output, and stop. **Do not weaken any test, do not
    fabricate a capture, and do not attempt a login on any site.**

- [ ] **Step 6: Build the dry-run artefacts from the real rows**

    ```bash
    python3 - "$WS" <<'PY'
    import datetime, json, pathlib, sys
    import yaml

    ws = pathlib.Path(sys.argv[1])
    rows_raw = json.loads((ws / "raw" / "51job-1.json").read_text(encoding="utf-8"))
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    rows = [{
        "id": f"51job-{r['jobId']}",
        "title": r["title"],
        "company": r["company"],
        "location": f"{r.get('city','')} {r.get('district','')}".strip(),
        "salary": r.get("salary", ""),
        "url": r["url"].split("?")[0],
        "source_site": "51job",
        "source_id": str(r["jobId"]),
        "extraction_method": "adapter_search",
        "retrieved_at": now,
        "quality": "card_only",
        "verification": "collected_unverified",
        "raw_text": " | ".join(str(r.get(k, "")) for k in
                               ("title", "company", "city", "salary", "degree", "workYear")),
        # GATE REHEARSAL ONLY. This workspace is deleted at the end of this step.
        # In a real round why_matched is written per row against the brief and the
        # raw fields -- it is one of the three places the no-fabrication fence is
        # restated, and a canned string there is exactly the defect being guarded
        # against.
        "why_matched": "闸门演练工作区：brief.target_titles 命中「算法工程师」；raw city 命中 上海。",
        "verdict": "worth_applying",
        "provisional": True,
        # Likewise a rehearsal value. In a real round effort is estimated per row
        # from the card, and it is what orders rows inside a band.
        "effort": "evening",
    } for r in rows_raw]

    brief = {
        "slug": "2026-08-09-dryrun-51job",
        "created": "2026-08-09",
        "trigger_reason": "闸门演练：验证 discover 的三个脚本在真实 adapter 输出上串得起来。",
        "target_titles": ["算法工程师"],
        "markets": ["cn"], "locations": ["上海"], "seniority": "mid",
        "employment_types": ["full_time"], "work_models": ["onsite"],
        "languages": ["Chinese"], "must_have_constraints": [], "nice_to_have": [],
        "avoid": [], "target_count": len(rows), "max_rows_per_round": 25,
        "max_pages_per_site": 2, "max_age_days": 30,
    }

    shortlist = {
        "search_slug": "2026-08-09-dryrun-51job",
        "brief": "brief.yaml",
        "shortfall_reason": None,
        "detail_fetch_exceptions": [],
        "sources": [{
            "site": "51job", "command": "search", "access": "read",
            "login_state": "no_auth_adapter", "classification": "ok",
            "invocations": 1, "rows_returned": len(rows), "identity_field": "title",
            "identity_field_empty_rows": 0,
            "detail_command": "opencli 51job detail <jobId>",
            "raw_files": ["raw/51job-1.json"],
        }],
        "rows": rows,
    }

    (ws / "brief.yaml").write_text(
        yaml.safe_dump(brief, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (ws / "shortlist.yaml").write_text(
        yaml.safe_dump(shortlist, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (ws / "shortlist.md").write_text(
        "# Shortlist — 2026-08-09 闸门演练\n\n"
        "## §0 来源与读取质量\n\n"
        "| site | command | access | 登录态 | 返回行 | 标识字段 | 分类 |\n"
        "|---|---|---|---|---|---|---|\n"
        f"| 51job | search | read | 无 auth adapter | {len(rows)} | `title` | ok |\n\n"
        "原始捕获：`raw/51job-1.json`。\n\n"
        "## §0.1 触发原因\n\n闸门演练：验证三个脚本在真实 adapter 输出上串得起来。\n\n"
        # The reader-facing half of the provisional stamp. Without it
        # check_shortlist exits 1 with MD_MISSING_PROVISIONAL_STAMP -- which is
        # the point: even the rehearsal workspace cannot render a band without
        # saying what it is based on.
        "## §1 候选（全部为基于卡片信息的初判 · provisional）\n",
        encoding="utf-8")
    print("rows:", len(rows), [r["source_id"] for r in rows])
    PY
    ```

    Expected: `rows: 3` and three numeric ids.

- [ ] **Step 7: Prove the gates pass live, then prove they catch a corrupted row**

    ```bash
    python3 scripts/check_no_write.py  --workspace "$WS"; echo "no_write=$?"
    python3 scripts/check_shortlist.py --workspace "$WS"; echo "shortlist=$?"

    # Hand-corrupt one row's source_id to something plausible that is NOT in raw/.
    python3 - "$WS" <<'PY'
    import pathlib, sys, yaml
    ws = pathlib.Path(sys.argv[1])
    data = yaml.safe_load((ws / "shortlist.yaml").read_text(encoding="utf-8"))
    data["rows"][0]["source_id"] = "173190000"
    (ws / "shortlist.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    PY

    python3 scripts/check_shortlist.py --workspace "$WS"; echo "corrupted=$?"
    tail -n 1 "$WS/journal.jsonl"
    ```

    Expected: `no_write=0`, `shortlist=0`, then `corrupted=1` with a stdout line starting
    `SOURCE_ID_NOT_IN_RAW:` naming `51job-1.json`, and a last journal line whose
    `"gate"` is `"check_shortlist"` and `"verdict"` is `"fail"`.

    Then delete the temp workspace: `rm -rf "$(dirname "$WS")"`. Nothing from the dry run
    is committed — the committed evidence is the classification line and the two exit
    codes, recorded in the commit message below.

- [ ] **Step 8: Commit**

    Fill the placeholders with what actually happened; if the live leg did not reach
    `ok`, say so plainly and paste the verbatim classification instead.

    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add scripts/tests/test_discover_e2e.py
    git commit -m "discover: end-to-end, hermetic chain plus a live read-only dry run

The three CLIs compose: the wrapper's adapter_call record is the record
the gates read back, and a hand-corrupted source_id and a hand-added
fabricated row are both caught through the real command lines. The
composition test cannot be trusted without a negative control, because
by this point it passes on its first run — so it was watched failing
with check_shortlist.py moved aside before it was believed.

Live dry run 2026-08-09, read-only, no login attempted:
  opencli 51job search 算法工程师 --area 上海 --page 1 --limit 3 --window background -f json
  exit=<RC>, classification=<CLASSIFICATION>, row_count=<N>
  check_no_write=<0|1>, check_shortlist=<0|1>, corrupted-row run=<1>"
    ```

---

### Task 10: register everything in SKILL.md, and retract "discover is not yet built"

**Files:**
- Modify: `SKILL.md` (the `## Self-check` section, the gate table, this plan's row of the `## Modes` table)
- Modify: `scripts/tests/test_skill_structure.py` (Plan 1) — append one entry to the library-only skip set (Plan 4 appends to the same literal; see Step 7)
- Test: `scripts/tests/test_discover_registration.py`

**Interfaces:**
- Consumes: Plan 1's `test_skill_structure.py` assertions (`test_the_self_check_names_every_script`, `..._every_reference_file`, `..._every_mode_file`, `test_every_path_the_self_check_names_exists`, `test_every_mode_named_in_skill_md_has_a_file_or_is_marked_unbuilt`, `test_a_mode_that_exists_is_not_still_described_as_not_yet_built`) and the shipped `## Modes` table Plan 1's Task 20 writes
- Produces: a green full suite, and a `SKILL.md` that no longer tells the model to refuse a mode that works.

**Why this exists and why it is last.** Plan 1's structural test asserts that `SKILL.md`'s `## Self-check` section names **every** `scripts/*.py`, `references/*.md` and `modes/*.md` in the tree. Those assertions are correct and stay — a checklist that silently stops covering new files is the exact failure the self-check was added to prevent. But it means every plan that adds files must also register them, and this plan adds eight. Until now nothing in Plans 2-4 did, so the suite would have gone red from Plan 2 onward and stayed red, which trains everyone to ignore it.

The second half is the same defect in prose. `SKILL.md`'s `## Modes` table gives `discover` the status **`discover` is not yet built in this repo**, and the paragraph under the table says to say so and stop rather than improvise. That status was true when Plan 1 wrote it. It is false the moment Task 7 lands, and a stale "not built" costs more than a missing one: layer 1 would be instructing the model to refuse a mode that works, while the check guarding the *other* direction (`test_every_mode_named_in_skill_md_has_a_file_or_is_marked_unbuilt`, which only fires when the mode file is **absent**) would still pass. Plan 1 anticipated exactly this and wrote `test_a_mode_that_exists_is_not_still_described_as_not_yet_built`, which has been red since Task 7 landed `modes/discover.md` and goes green at Step 6.

- [ ] **Step 1: Write the failing test**

    Create `scripts/tests/test_discover_registration.py`:

    ```python
    """Registration is a layer-1 obligation, not paperwork.

    Plan 1's test_skill_structure.py already asserts the self-check names every
    file. This module pins the two things it cannot: that the discover entries say
    what they are for, and that the 'not yet built' sentence retracted itself.
    """
    import pathlib
    import re

    REPO = pathlib.Path(__file__).resolve().parents[2]
    SKILL = REPO / "SKILL.md"

    MODES_WITH_FILES = ("discover",)


    def normalised():
        """Backticks stripped and whitespace collapsed, so that a sentence broken
        across lines or wrapped in code formatting cannot hide from the search."""
        return re.sub(r"\s+", " ", SKILL.read_text(encoding="utf-8").replace("`", ""))


    def test_the_not_yet_built_sentence_retracted_itself():
        text = normalised()
        for mode in MODES_WITH_FILES:
            assert (REPO / "modes" / f"{mode}.md").exists()
            assert f"{mode} is not yet built" not in text, (
                f"SKILL.md still tells the model to refuse {mode}, which now works. "
                "A stale 'not built' costs more than a missing one: every check "
                "passes and layer 1 declines a working mode.")


    def test_the_self_check_names_this_plans_files_with_a_reason_to_open_them():
        text = SKILL.read_text(encoding="utf-8")
        for path in ("modes/discover.md", "references/discovery-sources.md",
                     "references/source-policy.md",
                     "references/risk-control-signals.yaml",
                     "scripts/check_opencli_result.py", "scripts/check_no_write.py",
                     "scripts/check_shortlist.py"):
            assert path in text, f"{path} is registered nowhere in SKILL.md"


    def test_the_gate_table_lists_both_discover_gates():
        text = SKILL.read_text(encoding="utf-8")
        for gate in ("scripts/check_no_write.py", "scripts/check_shortlist.py"):
            row = next((line for line in text.splitlines()
                        if line.startswith("|") and gate in line), None)
            assert row is not None, f"{gate} has no row in the gate table"
            assert row.count("|") >= 4, f"{gate}'s gate-table row has no 'fires on'"


    def test_the_wrapper_is_not_described_as_a_gate():
        # check_opencli_result.py is the one named exception to the gate contract:
        # exit 0/2 only, and an adapter_call record instead of a receipt. Listing
        # it as a gate would send someone looking for a receipt that never exists.
        text = SKILL.read_text(encoding="utf-8")
        row = next((line for line in text.splitlines()
                    if line.startswith("|") and "check_opencli_result.py" in line), None)
        assert row is not None
        assert "wrapper" in row.lower()
    ```

- [ ] **Step 2: Run it, and run the full suite, and watch both fail**

    ```bash
    python3 -m pytest scripts/tests/test_discover_registration.py -q ; echo "rc=$?"
    python3 -m pytest scripts/tests/test_skill_structure.py -q ; echo "rc=$?"
    ```

    Expected: the first module fails all four with `AssertionError`. The second fails four: `test_the_self_check_names_every_script` (naming `check_no_write.py` first), `test_the_self_check_names_every_reference_file`, `test_the_self_check_names_every_mode_file`, and `test_a_mode_that_exists_is_not_still_described_as_not_yet_built` — that last one has been red since Task 7 created `modes/discover.md` while the `## Modes` table still called it unbuilt, and Step 6 is what clears it. **This is the red that has been accumulating since Task 1** — see the note in Task 9 Step 4. Read the failures before fixing them; they are the list of what to register.

- [ ] **Step 3: Register the read-when entries in SKILL.md's self-check**

    In `SKILL.md`'s `## Self-check` section, append to the **Read-when** list, keeping the
    existing wording and order of everything already there:

    ```markdown
    - [ ] In discover mode? `modes/discover.md`, loaded on entry, not on demand.
    - [ ] About to make the first live retrieval of a run, or asked to page further,
          fetch more detail pages, or work while the user is away?
          `references/source-policy.md`.
    - [ ] About to call an adapter other than the four in SKILL.md's table?
          `references/discovery-sources.md`.
    - [ ] An adapter call exited non-zero? `references/risk-control-signals.yaml`
          carries the stop-signal patterns `scripts/check_opencli_result.py` matches.
    ```

- [ ] **Step 4: Register the scripts in SKILL.md's self-check, each under a heading that tells the truth about its evidence**

    Plan 1's self-check has no single "ran it" list. It has one heading per **kind of
    evidence** — `Ran, with a receipt in journal.jsonl — scripts/check_apply.py requires
    each of these:`, `Ran, leaving a mode_entry record rather than a gate receipt:`,
    `Ran, leaving nothing in the journal (they render; they do not judge):`, `In CI, not
    in a workspace (no receipt exists for these, by design):` — and closes by saying why:
    *a checklist that promises a receipt where none can exist teaches its reader that one
    of its lines is decorative, and the reader cannot tell which one.* None of this plan's
    three scripts belongs under that first heading: the two discover gates do write
    receipts, but `scripts/check_apply.py` is the **apply** gate and does not require them,
    and `check_opencli_result.py` writes no receipt at all. So add two headings rather
    than three lines to a list that would then be false.

    Immediately **before** the closing paragraph that begins `Every line above says what
    evidence it leaves`, insert:

    ```markdown
    Ran, with a receipt in `journal.jsonl` — the discover gates. `scripts/check_apply.py`
    does not require these; a discover run is not reportable without them:
    - [ ] `scripts/check_no_write.py` (discover)
    - [ ] `scripts/check_shortlist.py` (discover)

    Ran, leaving an `adapter_call` record rather than a gate receipt:
    - [ ] `scripts/check_opencli_result.py` — once per adapter invocation. It is a
          wrapper, not a gate: it exits 0 (classified) or 2 (could not classify), never 1,
          so there is no receipt to look for and no pass/fail to read into the exit code.
    ```

    Then, in that closing paragraph, change `the three headings differ for a reason` to
    `the headings differ for a reason` — there are now six, and a stale count in the
    sentence explaining why the headings are separate is the same defect one level up.
    Change nothing else in it, and leave Plan 1's own four lists byte-identical.

    Append to the **Told the user** list:

    ```markdown
    - [ ] In discover: the §0 来源与读取质量 table, the trigger reason, every row's band
          marked 「基于卡片信息的初判」, and — if the run degraded — the disclosure block
          with its answers filled in.
    ```

- [ ] **Step 5: Add the three rows to the gate table**

    Append to the gate table in `SKILL.md`, matching its existing three-column shape:

    ```markdown
    | Adapter classification | `scripts/check_opencli_result.py` | *(wrapper, not a gate)* a non-zero exit, a login wall, a platform stop-signal, or an empty identity field |
    | Read-only | `scripts/check_no_write.py` | a journaled command whose published `access:` is `write`, or whose access cannot be resolved at all |
    | Shortlist | `scripts/check_shortlist.py` | a row whose `source_id` is in no raw capture; a duplicated or over-counted source report; "no results" with no adapter that exited 0; a missing disclosure block or provisional stamp; a detail fetch outside the top three; an uncapped brief; a missing or stale mode entry |
    ```

- [ ] **Step 6: Flip this plan's row of the `## Modes` table**

    Plan 1's Task 20 ships a purpose-built `## Modes` table in `SKILL.md` — one row per
    mode with a **Status** column — precisely so that each later plan retracts exactly its
    own line and cannot disturb another's. This is what you will find:

    ```markdown
    ## Modes

    | Mode | Question it answers | Status |
    |---|---|---|
    | `discover` | what is out there worth looking at | `discover` is not yet built in this repo |
    | `assess` | is this posting worth applying to | `assess` is not yet built in this repo |
    | `apply` | how do I build and pressure-test the application | live — `modes/apply.md` |
    | `interview` | how do I answer, and what did I get wrong | `interview` is not yet built in this repo |
    ```

    Replace the `discover` row — **and only that row** — with:

    ```markdown
    | `discover` | what is out there worth looking at | live — `modes/discover.md`; enter with `scripts/enter_mode.py --mode discover` |
    ```

    Leave the `assess`, `interview` and `apply` rows byte-identical: Plans 2 and 4 each
    flip their own row in their own final task, and a whole-table rewrite here would take
    theirs with it. Leave the paragraph below the table (*For an unbuilt mode: say so and
    stop. Do not improvise it.*) untouched as well — it is written per-status, not
    per-mode, so it needs no edit and still governs the two rows that remain unbuilt.

    Two tests police this row and both are red right now: this plan's
    `test_the_not_yet_built_sentence_retracted_itself`, and Plan 1's
    `test_a_mode_that_exists_is_not_still_described_as_not_yet_built` in
    `scripts/tests/test_skill_structure.py`, which fires the moment `modes/discover.md`
    exists while the Status column still says otherwise. Both strip backticks and collapse
    whitespace before searching, so re-wrapping the row or dropping the code formatting
    will not hide a stale status from either of them.

- [ ] **Step 7: Extend the library-only skip set — append one entry, do not replace the line**

    In `scripts/tests/test_skill_structure.py`, `test_the_self_check_names_every_script`,
    find the `skip = {...}` set literal and **add one entry to whatever it already holds**.
    Do not retype the line from this plan as a whole-line replacement: Plan 4 appends
    `mock_vocab.py` and `mock_blocks.py` to the same literal, so whichever of the two plans
    ran last would silently delete the other's entry — and Plan 1's four with it. The
    deleted module then quietly stops needing a self-check line, which is the one failure
    this test exists to prevent.

    Expected state on arrival — Plan 1 wrote these four, and Plan 2 added none because it
    has no library-only module:

    ```python
        skip = {"journal.py", "paths.py", "rounds.py", "vocab.py"}
    ```

    After this step:

    ```python
        skip = {"journal.py", "paths.py", "rounds.py", "vocab.py",
                "opencli_meta.py"}      # imported, never invoked
    ```

    If the literal you find holds anything beyond those four, a later plan ran ahead of
    this one: keep every entry it has and add `"opencli_meta.py"` alongside them. Its
    entries are not yours to drop.

    `opencli_meta.py` is this plan's only library-only module: nothing runs it, it has
    no CLI, and `check_no_write.py` is the thing a self-check can ask you whether you
    ran. Add nothing else — a skip set is how a real gap gets waved through, so every
    entry has to be a module with no command line.

- [ ] **Step 8: Run the whole suite**

    Run: `python3 -m pytest scripts/tests -q`
    Expected: PASS, no failures, no errors — including the four `test_skill_structure.py`
    tests that were red in Step 2 (the three self-check-names tests, cleared by Steps 3-5
    and 7, and `test_a_mode_that_exists_is_not_still_described_as_not_yet_built`, cleared
    by Step 6) and all four of `test_discover_registration.py`. This plan's own ten
    modules account for **123** of the passing tests — 16 + 12 + 19 + 26 + 4 + 10 + 10 +
    19 + 3 + 4, which is Task 9 Step 4's 119 plus this task's four — and the rest are
    Plan 1's and Plan 2's. This is the first time in this plan the **full** suite is green, and it is
    the step that proves the accumulated red was registration debt and nothing else.

- [ ] **Step 9: Commit**

    ```bash
    cd /Users/donghanglyu/code_project/job-hunt
    git add SKILL.md scripts/tests/test_skill_structure.py \
            scripts/tests/test_discover_registration.py
    git commit -m "discover: register the new files in SKILL.md, retract 'not yet built'

Plan 1's structural test asserts the self-check names every script,
reference and mode file in the tree. That assertion is right and stays,
so the plan that adds eight files is the plan that registers them —
otherwise the suite goes red on the first new file and stays red, which
teaches everyone to ignore it.

The ## Modes table said discover was not yet built. True when it was
written, false since modes/discover.md landed, and a stale 'not built'
is worse than a missing one: layer 1 would decline a working mode while
the check guarding the other direction still passed. Plan 1 saw it
coming and wrote test_a_mode_that_exists_is_not_still_described_as_not_
yet_built, red since Task 7. Only the discover row moves; assess and
interview stay byte-identical for Plans 2 and 4 to flip.

opencli_meta.py is appended to the library-only skip set rather than
replacing the line, so Plan 4's mock_vocab.py and mock_blocks.py cannot
delete it and it cannot delete them. Nothing else joins, because a skip
set is how a real gap gets waved through."
    ```

---

## Definition of done

- [ ] `python3 -m pytest scripts/tests -q` passes with no failures and no errors. (Only true after Task 10 — see the known-red window in Global Constraints.)
- [ ] `python3 scripts/check_no_write.py --workspace <any run>` exits 0 on every workspace this plan created, and its receipt is in that workspace's `journal.jsonl`.
- [ ] Every one of these files exists and is committed: `references/risk-control-signals.yaml`, `references/discovery-sources.md`, `references/source-policy.md`, `modes/discover.md`, `scripts/opencli_meta.py`, `scripts/check_opencli_result.py`, `scripts/check_no_write.py`, `scripts/check_shortlist.py`.
- [ ] `SKILL.md` contains the `discover-inserts (plan 3)` marker block with the four command pairs, the six-clause platform-limit stop rule, and the evaluable triggers for `references/discovery-sources.md` **and** `references/source-policy.md`. The phrase `about to call an adapter other than the four` appears on a single line in both `SKILL.md` and `references/discovery-sources.md`.
- [ ] `SKILL.md`'s `## Self-check` names every file this plan added, its gate table has rows for both discover gates, and it no longer says `discover` is not yet built.
- [ ] Both halves of the layer-1.5 backstop are live for discover: `modes/discover.md` defines fields the gate requires, **and** `check_shortlist.py` fails with `NO_MODE_ENTRY` / `MODE_FILE_CHANGED`.
- [ ] `git log --oneline` shows ten commits from this plan and `git status` is clean.
- [ ] Nothing was pushed. `git log origin/main..HEAD` (if a remote exists) shows all ten commits still local.
- [ ] No write command is instructed anywhere in the shipped skill:

      ```bash
      grep -rn --exclude-dir=__pycache__ --exclude-dir=tests \
        "opencli [a-z0-9]* \(greet\|batchgreet\|send\|invite\|connect\|safe-send\|login\|mark\|exchange\|salesnav-message\)" \
        SKILL.md modes references scripts
      ```

      Expected: exactly two lines, and read both before ticking this.
      `modes/discover.md` — *"Never run `opencli 51job login`; it does not exist"* — forbids one.
      `scripts/check_no_write.py` — the `parse_command_line` docstring's worked example
      `('boss', 'greet') from 'opencli boss greet --job-id X'` — is the parser's own
      documentation of the string it exists to catch, and deleting it would remove the
      explanation of the guard rather than a write path. **Anything else is a finding.**
      `--exclude-dir=tests` is deliberate: the gate's own fixtures must contain the
      commands the gate catches, and a criterion read literally against them would have
      an executor delete load-bearing test data to make a grep quiet.

## Named residual risks (not closed by this plan)

1. **`check_no_write.py` cannot see a command nobody journaled.** The gate is an after-the-fact scan. The load-bearing half of the read-only guarantee is that no write command appears anywhere in this skill's instructions.
2. **No risk-control body has ever been observed.** Every pattern in `references/risk-control-signals.yaml` except the login-wall handling is a guess, marked `verified: false`. The first real capture must replace it verbatim.
3. **Five of eight adapters were never executed** (boss, linkedin, nowcoder, upwork, maimai). Their columns, flags and caps come from help text only, and `runtime_verified: false` records that in the catalogue.
4. **A verbatim `source_id` in `raw/` is a credibility floor, not a proof.** It proves the identifier was returned by an adapter; it does not prove the row's `why_matched` follows from it.
5. **`why_matched` has no gate.** It is checked for presence, never for truth. That is why the no-fabrication fence is restated in the field's own definition in `modes/discover.md` rather than only at the top of SKILL.md. The presence check is also anchored on the *definition* rather than on the first occurrence of the word — an earlier version of that test measured a window from Step 0's passing mention and was satisfied by an unrelated "Never pad the count", so the entire fence paragraph could have been deleted with the suite green.
6. **`references/source-policy.md`'s backstop covers one section, not the file.** `CAP_MISSING` / `CAP_ABOVE_CEILING` prove the yellow-tier round caps were respected. Nothing reports a run that quietly did something Red — the load-bearing half there is still that no Red action appears anywhere in this skill's instructions, plus `check_no_write.py` for the single Red line a script can see. A Red action taken outside opencli (a browser the skill drove itself, say) would leave no trace this plan can read.
7. **`effort` is an estimate from a card, and nothing checks it against reality.** The gate proves the value is one of four strings, not that a `quick` row is actually quick. It exists so the within-band ordering rule is implementable at all; treat the ordering as a suggestion the user can overrule, and say so when presenting the shortlist.
8. **`search-preferences.yaml` is written by discover and read by assess, and only the writer's schema is enforced.** `modes/discover.md` defines it and the mode-doc test pins the field list, but nothing validates the file on disk at read time. A hand-edited or half-written preferences file will be read as-is. The mitigation is behavioural, not mechanical: every field is asked rather than inferred, and the file is confirmed with the user once per session.
9. **`NO_MODE_ENTRY` proves the entry was recorded, not that the file was read.** `scripts/enter_mode.py` can be run without reading a line of `modes/discover.md`. What the record actually buys is the *hash*: it proves which bytes were on disk at entry, so a shortlist built against an older schema is detectable. Combined with the gate requiring fields defined only in that file, it is two weak proofs that are hard to satisfy together by accident — which is the whole claim, and it is worth not overstating.
