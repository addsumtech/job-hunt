# Weekly Job Digest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A once-a-week, unattended discover round on no-login sources that emails the user only the roles they have not been sent, with cancel/pause/feedback by reply.

**Architecture:** A deterministic `digest.py` owns state, the due rule, the lock and the scheduler entry; an hourly `tick` starts a headless agent only when a digest is due. The agent runs an ordinary discover round in a discover-shaped workspace (so every existing discover gate applies unchanged), then uses `digest.py inbox / compose / sent` and the new gate `check_digest.py`. Small helper modules hold the seen ledger, reply classification and email rendering.

**Tech Stack:** Python 3.10+, PyYAML, pytest; launchd (macOS) / user crontab (Linux); the agent's own email tool (Gmail MCP for this user).

**Spec:** `docs/superpowers/specs/2026-11-02-weekly-digest-design.md`

## Global Constraints

- Scheduled runs read only no-login sources: rows must have `extraction_method` in `public_page`/`official_api` or `source_site` in `NO_LOGIN_ADAPTERS = ("indeed", "51job")`; any capture from `LOGGED_IN_SITES = ("linkedin", "boss")` fails the run (`DIGEST_LOGGED_IN_SOURCE`).
- At most 5 roles per email (`MAX_ROLES = 5`), each with its full posting read (`quality: complete`).
- Due rule: first slot (weekday, hour; system local time) at least 6 days after `last_sent`; one digest for any number of missed weeks.
- Failure budget: at most 3 attempts per calendar day; after 3 consecutive failed days, notify and wait for the next weekly slot.
- Lock is stale after 3 hours.
- Ledger entries older than 180 days are pruned; a sent role is never re-sent.
- No paid API, no browser, no logged-in adapter in the headless agent's tool allowlist.
- If the inbox cannot be read, nothing is sent.
- All state lives under the profile directory (`scripts/paths.py`), never in the skill.
- Existing rules hold: no fit score / probability (`lint_no_prediction.py`), stage named paths only, no push.

## Review Focus

1. A reply that quotes the digest's own "取消推送" instructions must not cancel; one that says "取消" in its own text must → Task 4 test `test_quoted_instructions_do_not_cancel`.
2. Laptop asleep through the slot for three weeks → one digest on wake, next due ≥6 days later → Task 1 `test_missed_weeks_produce_one_due`.
3. Same role reposted under a new URL, or on two sites; same title in another city → Task 3 `test_repost_new_url_is_seen`, `test_other_city_is_new`, `test_remote_matches_any_city`.
4. Agent crashes or exits without sending → ledger untouched, attempt counted, lock released → Task 2 `test_failed_run_counts_attempt_and_releases_lock`.
5. launchd/cron start with a minimal environment → generated entries use absolute interpreter and script paths and set the profile root explicitly → Task 2 `test_scheduler_entries_use_absolute_paths`.

---

### Task 1: Settings, due rule, lock, cancel and pause

**Files:**
- Modify: `scripts/paths.py` (add three functions after `online_presence_dir`)
- Create: `scripts/digest.py`
- Test: `scripts/tests/test_digest_state.py`

**Interfaces:**
- Produces (paths.py): `digest_settings(name) -> Path` (`<profile>/digest.yaml`), `digest_seen(name) -> Path` (`<profile>/digest-seen.yaml`), `digest_workspace(name, date: str) -> Path` (`<profile>/searches/<date>-weekly-digest`, or `-2`, `-3`… if that exists — a retry never reuses a failed run's workspace).
- Produces (digest.py): `load_settings(name) -> dict` (empty-shape dict when absent; `journal.YamlUnreadable` when unreadable), `save_settings(name, data) -> None` (atomic), `due(settings, now: datetime) -> tuple[bool, str]`, `acquire_lock(name, now) -> bool`, `release_lock(name) -> None`, `record_attempt(name, now, ok: bool) -> None`, `cancel(name, words, today) -> None`, `pause(name, weeks: int, words, today) -> None`. Settings keys: `enabled, cancelled, paused_until, schedule{weekday 0=Mon..6, hour}, recipient, transport ("email"|"file"), budget_usd, agent{command, cwd}, standing_brief, last_sent (ISO datetime), threads, processed_messages, attempts{date: n}, failed_days, stuck_until, pending_questions, answers`.

- [ ] **Step 1: Write the failing tests**

```python
NOW = datetime.datetime(2026, 11, 9, 9, 30)          # a Monday
S = {"enabled": True, "schedule": {"weekday": 0, "hour": 9}, "last_sent": "2026-11-02T09:05"}

def test_due_at_the_slot_six_days_after_last_sent():
    assert digest.due(S, NOW) == (True, "due")
    assert digest.due(S, NOW.replace(hour=8))[0] is False

def test_missed_weeks_produce_one_due():
    s = dict(S, last_sent="2026-10-12T09:00")
    assert digest.due(s, NOW)[0] is True        # one digest, not three

def test_never_sent_is_due_now(): ...           # last_sent None -> (True, "due")
def test_paused_and_cancelled_are_not_due(): ...  # reasons "paused", "cancelled"
def test_three_attempts_today_stop_until_tomorrow(): ...  # reason "attempt_cap"
def test_three_failed_days_wait_for_next_slot(): ...      # stuck_until = next slot; reason "stuck"
def test_lock_is_exclusive_and_stale_after_three_hours(tmp_store): ...
def test_cancel_and_pause_record_the_words(tmp_store): ...  # cancelled={date, words}; paused_until = today + 7*weeks
def test_digest_workspace_never_reuses_an_existing_run(tmp_store): ...
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest -q -p no:cacheprovider scripts/tests/test_digest_state.py` — Expected: FAIL (`No module named 'digest'`).
- [ ] **Step 3: Implement** the interfaces above. Slot computation: start at `last_sent + 6 days`, advance to the first datetime with `weekday()==schedule.weekday` and `hour==schedule.hour` at or after it (minutes 0). Lock = `<profile>/digest.lock` holding an ISO timestamp, created with `O_EXCL`; stale when older than 3 h (then replaced).
- [ ] **Step 4: Run** same command — Expected: PASS.
- [ ] **Step 5: Commit** `git add scripts/paths.py scripts/digest.py scripts/tests/test_digest_state.py && git commit -m "feat(digest): settings, due rule, lock, cancel and pause"`

### Task 2: Tick, agent command, scheduler install/uninstall, notifications

**Files:**
- Modify: `scripts/digest.py`
- Test: `scripts/tests/test_digest_tick.py`

**Interfaces:**
- Consumes: Task 1.
- Produces: `agent_command(settings, name, skill_root) -> list[str]`, `tick(name, now, run=subprocess.run, notify=notify) -> str` (returns `"not_due:<reason>"`, `"locked"`, `"ran:ok"`, `"ran:failed"`), `scheduler_entry(name, platform: str, python: Path, skill_root: Path, profiles_root: Path) -> str` (plist XML for `"darwin"`, one crontab line for `"linux"`, `ValueError` otherwise), `install(name, platform=sys.platform, run=subprocess.run) -> Path`, `uninstall(name, platform=sys.platform, run=subprocess.run) -> None`, `notify(title, message) -> None` (osascript / notify-send; never raises). CLI subcommands: `tick`, `install`, `uninstall`, `cancel --words`, `pause --weeks --words`.

- [ ] **Step 1: Write the failing tests**

```python
def test_agent_command_is_budgeted_and_allowlisted(tmp_store):
    cmd = digest.agent_command(settings, "Jane Doe", SKILL)
    assert cmd[0] == "/abs/claude" and "-p" in cmd
    assert cmd[cmd.index("--max-budget-usd") + 1] == "2.0"
    allowed = cmd[cmd.index("--allowedTools") + 1:]
    assert any("mcp__gmail__send_email" in a for a in allowed)
    assert not any("monid" in a.lower() or "chrome" in a.lower() for a in allowed)

def test_tick_not_due_starts_nothing(tmp_store): ...           # run never called
def test_tick_success_is_ok_when_last_sent_moved(tmp_store): ... # fake run writes last_sent -> "ran:ok"
def test_failed_run_counts_attempt_and_releases_lock(tmp_store): ...  # exit 1 -> "ran:failed", attempts[today]==1, lock gone
def test_cancel_or_pause_during_run_is_not_a_failure(tmp_store): ...
def test_stuck_notifies_once(tmp_store): ...
def test_scheduler_entries_use_absolute_paths():
    plist = digest.scheduler_entry("Jane Doe", "darwin", PY, SKILL, ROOT)
    assert str(PY) in plist and f"{SKILL}/scripts/digest.py" in plist
    assert "<key>StartInterval</key>" in plist and "<integer>3600</integer>" in plist and "RunAtLoad" in plist
    assert "JOBHUNT_PROFILES_ROOT" in plist
    line = digest.scheduler_entry("Jane Doe", "linux", PY, SKILL, ROOT)
    assert line.startswith("0 * * * * ") and "# job-hunt digest jane-doe" in line
def test_windows_is_refused(): ...
def test_install_and_uninstall_call_the_scheduler(tmp_path, monkeypatch): ...  # fake run records launchctl bootstrap/bootout
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest -q -p no:cacheprovider scripts/tests/test_digest_tick.py` — Expected: FAIL.
- [ ] **Step 3: Implement.** `agent_command` reads `settings.agent.command` (absolute binary recorded at setup), the fixed prompt `"Run the job-hunt weekly digest for <name>: read <skill>/references/weekly-digest.md and follow 'The run'."`, `--max-budget-usd <budget_usd>`, and `--allowedTools` with: `Bash(<python> <skill>/scripts/*)`, `Bash(mkdir -p *)`, `Read`, `Write`, `Edit`, `mcp__gmail__search_emails`, `mcp__gmail__read_email`, `mcp__gmail__send_email`. `tick` runs it with `cwd=settings.agent.cwd`, success = settings after the run show a later `last_sent`, or `cancelled`/`paused_until` set. Plist label `com.jobhunt.digest.<slug>` under `~/Library/LaunchAgents/`, logs to `<profile>/digest-runs.log`; install via `launchctl bootstrap gui/<uid>`; Linux edits the user crontab by the marker comment.
- [ ] **Step 4: Run** same command — Expected: PASS.
- [ ] **Step 5: Commit** `git add scripts/digest.py scripts/tests/test_digest_tick.py && git commit -m "feat(digest): hourly tick, budgeted headless agent, launchd/cron entries"`

### Task 3: Seen ledger

**Files:**
- Create: `scripts/digest_ledger.py`
- Test: `scripts/tests/test_digest_ledger.py`

**Interfaces:**
- Produces: `norm_company(s) -> str`, `norm_title(s) -> str`, `norm_location(s) -> str` (`"*"` for remote / multi-location), `is_seen(row: dict, ledger: dict) -> bool`, `filter_new(rows, ledger) -> list`, `record_sent(ledger, rows, today) -> dict`, `prune(ledger, today, days=180) -> dict`, `load_ledger(name) -> dict`, `save_ledger(name, ledger) -> None`. Ledger shape: `{"roles": [{"company", "title", "locations": [...], "urls": [...], "first_sent", "last_seen"}]}`. Rows are discover shortlist rows (`company`, `title`, `location`, `url`).

- [ ] **Step 1: Write the failing tests**

```python
ROW = {"company": "Acme B.V.", "title": "Sr. ML Engineer", "location": "Amsterdam", "url": "https://a/1"}
def test_same_url_is_seen(): ...
def test_repost_new_url_is_seen():
    led = ledger.record_sent({"roles": []}, [ROW], D)
    assert ledger.is_seen(dict(ROW, url="https://b/9", company="ACME"), led)
def test_other_city_is_new(): ...                # location "Utrecht" -> not seen
def test_remote_matches_any_city(): ...          # sent "Remote" -> "Utrecht" seen, and the reverse
def test_title_variants_normalise(): ...         # "Senior ML-Engineer" == "Sr. ML Engineer"
def test_near_titles_stay_distinct(): ...        # "ML Engineer II" != "ML Engineer"
def test_non_latin_titles_normalise(): ...       # "机器学习工程师（上海）" stable and non-empty
def test_prune_drops_entries_older_than_180_days(): ...
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest -q -p no:cacheprovider scripts/tests/test_digest_ledger.py` — Expected: FAIL.
- [ ] **Step 3: Implement.** Normalisation: NFKC, casefold, keep `isalnum` per word (Unicode-aware, as `online_presence._norm`); company drops trailing legal suffixes `b.v., bv, n.v., nv, gmbh, ltd, limited, inc, llc, plc, ag, sa, s.a.`; title expands `sr→senior`, `jr→junior`; location `"*"` when it contains remote/hybrid-remote/"multiple"/";"/" / ". Seen = url in urls, or same company+title and (same location or either is `"*"`).
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `git add scripts/digest_ledger.py scripts/tests/test_digest_ledger.py && git commit -m "feat(digest): seen ledger with cross-site identity"`

### Task 4: Reply classification and its effects

**Files:**
- Create: `scripts/digest_inbox.py`
- Modify: `scripts/digest.py` (subcommand `inbox`)
- Test: `scripts/tests/test_digest_inbox.py`

**Interfaces:**
- Consumes: Task 1 (`cancel`, `pause`, settings), Task 2 (`uninstall`).
- Produces: `strip_quoted(body) -> str`, `classify(body) -> dict` `{"cancel": bool, "pause_weeks": int|None, "yes": list[str], "feedback": [{"index": int, "text": str, "reason": str}]}`, `apply_messages(name, messages: list[dict], today, run=subprocess.run) -> dict` returning `{"action": "cancel"|"pause"|"continue", "applied": [...], "ignored": [...]}`, `apply_avoid(name, text, words, today) -> Path` (backup `search-preferences.yaml.bak-<date>`, append to `avoid`, bump `updated`). CLI: `digest.py inbox --name N --messages <json file>`; `--unreadable "<reason>"` records a failed attempt, notifies, and prints `{"action": "stop"}`. Message shape: `{"id", "thread_id", "from", "date", "body"}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_quoted_instructions_do_not_cancel():
    body = "谢谢\n\n在 2026年11月9日 写道：\n> 回复「取消推送」即可停止"
    assert inbox.classify(body)["cancel"] is False
def test_own_cancel_wins_over_everything():
    c = inbox.classify("第 2 个不错，但还是取消推送吧")
    assert c["cancel"] is True
@pytest.mark.parametrize("text,weeks", [("暂停 3 周", 3), ("pause 2 weeks", 2), ("pauzeer 1 week", 1), ("先暂停", 4)])
def test_pause_weeks(text, weeks): ...
def test_feedback_by_index(): ...           # "第 3 个不相关，因为要德语" -> index 3, reason "要德语"
def test_yes_names_a_question(): ...        # "是 A" -> ["A"]; plain "yes" -> ["*"]
def test_wrong_sender_or_thread_is_ignored(tmp_store): ...
def test_processed_message_is_not_applied_twice(tmp_store): ...
def test_cancel_uninstalls_and_reports_cancel(tmp_store): ...
def test_feedback_becomes_a_pending_question_not_a_preference(tmp_store): ...  # prefs file untouched
def test_yes_writes_avoid_with_backup(tmp_store): ...   # only the single pending question, or the named one
def test_unreadable_inbox_stops_and_counts_a_failure(tmp_store): ...
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest -q -p no:cacheprovider scripts/tests/test_digest_inbox.py` — Expected: FAIL.
- [ ] **Step 3: Implement.** Quote stripping: drop lines starting with `>`; cut at the first line matching `^On .+ wrote:$`, `^在.+写道[:：]$`, `^Op .+ schreef .+:$`, or `-----Original Message-----`. Keywords (case-insensitive): cancel `取消推送|取消订阅|退订|停止推送|不要再发|unsubscribe|cancel|stop sending|afmelden|opzeggen`; pause `暂停\s*(\d+)\s*周|pause\s*(\d+)\s*weeks?|pauzeer\s*(\d+)\s*weken?`, bare `暂停|pause|pauzeer` = 4 weeks; yes `^(是|好|确认|yes|ja)\b\s*([A-Z])?`; feedback `第\s*(\d+)\s*个|#(\d+)` with reason after `因为|because|omdat`. Accepted only when the address in `from` equals `recipient` (casefold) and `thread_id` is in `threads`. A question asked twice without a yes is dropped.
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `git add scripts/digest_inbox.py scripts/digest.py scripts/tests/test_digest_inbox.py && git commit -m "feat(digest): cancel, pause and feedback by reply"`

### Task 5: Compose, gate, record the send

**Files:**
- Create: `scripts/digest_compose.py`, `scripts/check_digest.py`
- Modify: `scripts/digest.py` (subcommands `compose`, `sent`, `deliver-file`)
- Test: `scripts/tests/test_digest_compose.py`, `scripts/tests/test_check_digest.py`

**Interfaces:**
- Consumes: Tasks 1, 3, 4; discover workspace files `brief.yaml`, `shortlist.yaml`, `raw/`, `journal.jsonl`.
- Agent-written inputs in the workspace: `digest-picks.yaml` = `{"roles": [{"id": <shortlist row id>, "why": str, "gaps": str}], "unread": int}` and `digest-sources.yaml` = `{"checked": [site], "unchecked": [{"site", "reason"}]}`.
- Produces: `compose(settings, workspace, today) -> dict` `{"to", "subject", "body"}` written to `<ws>/digest-email.json` and `<ws>/digest-email.txt`; subject `"[job-hunt weekly] <YYYY-MM-DD> — <n> new role(s)"`; body lists roles (title, company, location, link, why, gaps), checked and unchecked sources with reasons, the line that logged-in sources (LinkedIn etc.) are not searched automatically, pending questions with their letters, and the reply instructions. `check_digest.main(["--workspace", ws, "--name", n]) -> int` (0 pass, 1 findings). `digest.py sent --name --workspace --message-id --thread-id` runs the gate in-process, then `record_sent`, `last_sent=now`, appends `thread_id`, increments `asked` on pending questions, resets failures. `deliver-file` writes `~/Downloads/job-digest/<date>.html` (escaped body in `<pre>`), notifies, then does what `sent` does without ids.

- [ ] **Step 1: Write the failing tests** — `test_check_digest.py` builds a minimal discover workspace with `discover_fixtures.py` helpers and asserts each code: `DIGEST_TOO_MANY_ROLES` (6 picks), `DIGEST_ROW_NOT_IN_SHORTLIST`, `DIGEST_ROW_NOT_READ` (row `quality != complete`), `DIGEST_ROW_ALREADY_SENT`, `DIGEST_NO_REASON` (empty why), `DIGEST_UNCHECKED_NOT_NAMED` (a journal capture whose classification is not `ok` and whose site is not in `unchecked`), `DIGEST_LOGGED_IN_SOURCE` (a `raw/linkedin-*.json` or a row with `source_site: linkedin`), `DIGEST_PREDICTION` (body containing "high chance of an interview", via `lint_no_prediction`), and a clean workspace passes with 0 picks (empty week). `test_digest_compose.py`: `test_empty_week_names_checked_sources`, `test_body_has_link_why_gaps_and_reply_instructions`, `test_sent_refuses_when_gate_fails` (ledger and last_sent unchanged), `test_sent_records_ledger_threads_and_last_sent`, `test_deliver_file_writes_html_and_counts_as_sent`.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest -q -p no:cacheprovider scripts/tests/test_digest_compose.py scripts/tests/test_check_digest.py` — Expected: FAIL.
- [ ] **Step 3: Implement** to the interfaces; `check_digest` also runs `check_shortlist.main` on the workspace and reports its failure as `DIGEST_SHORTLIST_GATE`.
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `git add scripts/digest_compose.py scripts/check_digest.py scripts/digest.py scripts/tests/test_digest_compose.py scripts/tests/test_check_digest.py && git commit -m "feat(digest): compose, gate and record the weekly email"`

### Task 6: Policy, procedure and wiring

**Files:**
- Create: `references/weekly-digest.md` (Setup; The run, steps 1–6 of the spec with exact commands; Cancel/pause; What it never does)
- Modify: `references/source-policy.md` (Red line narrowed exactly as the spec's "Policy change"), `SKILL.md` (one line under "Enter a full mode" pointing weekly-digest requests to `references/weekly-digest.md`), `references/workflow-checklist.md` (digest gate entry), `modes/discover.md` (one paragraph: an unattended digest round follows `references/weekly-digest.md` overrides — standing brief, no interview, no login hand-off, no-login sources only)
- Test: `scripts/tests/test_digest_docs.py`

- [ ] **Step 1: Write the failing tests:** source-policy Red still forbids unattended logged-in use and names the digest exception; `weekly-digest.md` contains `digest.py tick`, `inbox`, `compose`, `check_digest.py`, `sent`, "LinkedIn", "nothing is sent"; SKILL.md links the reference; every `digest.py` subcommand and flag named in the docs exists in `digest.py --help`.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest -q -p no:cacheprovider scripts/tests/test_digest_docs.py scripts/tests/test_documented_commands_run.py` — Expected: FAIL on the new tests.
- [ ] **Step 3: Write the docs.**
- [ ] **Step 4: Run** the same, then `make check PY=python` — Expected: all pass (record the count).
- [ ] **Step 5: Commit** the named doc and test paths: `git commit -m "docs(digest): procedure, narrowed source policy, wiring"`

### Task 7: Real run on this machine (stop and ask first)

Outward-facing: it sends real email and installs a launchd job. Ask the user (selectable options) before each of: the first real send to their address, and installing the schedule.

- [ ] **Step 1:** Setup in conversation per `references/weekly-digest.md` with the user's answers; standing brief from one of the user's earlier discover rounds' `brief.yaml` (confirm with the user).
- [ ] **Step 2:** Run `digest.py tick` by hand with the due rule satisfied; read the run log, the workspace, the email in the inbox (look at it, not the exit code).
- [ ] **Step 3:** Reply-path check: send a test reply "暂停 1 周" from the user's address only with their consent, run the inbox step, confirm `paused_until`, then undo with their consent.
- [ ] **Step 4:** Inbox-unreadable stop: run with the Gmail tool removed from the allowlist once; confirm nothing was sent and a notification and log line appeared.
- [ ] **Step 5:** Install the schedule only after the user says yes; show `launchctl print` output.

---

Self-review notes: every spec goal maps to a task (1–2 cadence/due/failure, 3 only-new, 4 cancel/pause/feedback, 5 content/empty week/loud gaps/no prediction, 6 policy/procedure, 7 real check). Ruling recorded here: the spec's `digest-runs/<date>/` becomes `searches/<date>-weekly-digest[-n]/` so the run is an ordinary discover workspace and all discover gates and `paths.profile_dir_of`-style lookups apply unchanged; the spec's `modes/digest.md` becomes `references/weekly-digest.md` because the run is a discover round, not a fifth mode (no change to `enter_mode.MODES`).
