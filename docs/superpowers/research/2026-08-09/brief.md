# Design Brief — `job-search` skill (discover → assess → apply → interview)

**Status:** design brief only. Nothing below has been built or run. Factual claims are tagged with their source input (`[1]`–`[6]`); where an input distinguished *measured* from *help-text-only*, I carry that distinction. Everything under **RECOMMENDATION** or in a "decision" line is my proposal, not a report.

**Naming:** I use `job-search` as the skill name and `<skill>/` as its root. The old `job-application` tree is retired and absorbed as `apply` mode.

---

## A. SHARED SPINE

### A.1 The seven data objects

| # | Object | Path | Written by | Read by | Mutability rule |
|---|---|---|---|---|---|
| 1 | **Master profile** | `~/.claude/job-profiles/<name>/profile.yaml` | profile-build step only, after explicit user confirmation | all four modes | **IMMUTABLE to every mode.** Tailoring always copies. Rule from `[1]` (SKILL.md:60, :95-101, :103): the master is the source of truth and is never mutated. Enforced by `check_claims.py`, which fails if `mtime(profile.yaml)` changed during an apply run. |
| 2 | **Search preferences** | `~/.claude/job-profiles/<name>/search-preferences.yaml` | discover (with user) | discover, assess | Mutable by user request. Restructured from `[2]`'s `inputs/job_search_preferences.md` — city, direction, salary floor, experience track (社招/校招/实习), industry, company stage, 外包 tolerance. `[2]`'s `是否允许系统自动发送打招呼` field is **deleted, not defaulted** — see §F. |
| 3 | **Market conventions** | `<skill>/references/market-conventions/<key>.yaml` | **a human, in a commit** | assess, apply, interview | **IMMUTABLE at runtime.** The model may never author, strengthen or extend an entry, and never round-trips the text through itself. Rule and rationale from `[3]` (`src/market/conventions.js:1-41`). Content from `[5]`. |
| 4 | **Shortlist** | `~/.claude/job-profiles/<name>/searches/<YYYY-MM-DD>-<slug>/` → `shortlist.yaml`, `shortlist.md`, `raw/<site>-<n>.json` | discover | assess, user | Append-only within a search. Raw adapter captures are never edited — they are the provenance for every row. |
| 5 | **Posting** | `<workspace>/posting.yaml` + `<workspace>/posting-source.txt` | assess | apply, interview | Written once per extraction. Re-extraction overwrites and journals the fact. `posting-source.txt` is the raw fetched/pasted text and is never edited. |
| 6 | **Assessment** | `<workspace>/fit-assessment.md`, `fit-assessment.yaml`, `evidence-blocks.json` | assess | apply, interview, user | `evidence-blocks.json` is **derived, never hand-edited** — it is regenerated from `posting-source.txt` + `cv.md`/profile by `scripts/evidence_blocks.py`. |
| 7 | **Application package** | `<workspace>/` — `tailored-profile.yaml`, `tailoring-plan.md`, **`claims.yaml`**, `cv.{md,docx,pdf,tex}`, `letter.{yaml,md,…}`, `supporting-statement.md`, `judge-round-<n>.json`, `interview-brief.md` | apply | interview, user | `claims.yaml` is **append-only**; an entry may be marked `retracted: walk-back-<date>` but never deleted. |
| 8 | **Interview session** | `<workspace>/mock/` — `transcript-<n>.md`, `assessment-<n>.md`, `answer-bank.md`, `open-loops.md`, `question-log.yaml`, `cheatsheet.md` | interview | user; `answer-bank.md` carries across applications | `transcript-*.md` and `question-log.yaml` are **append-only**, flushed after every answer `[6 §5c]`. |
| 9 | **Run journal** | `<workspace>/journal.jsonl` (and `<search-dir>/journal.jsonl`) | every mode | every gate script | Append-only. One line per external call, gate run, and subagent dispatch: `{ts, mode, action, target, exit_code, rows, gate, receipt_hash}`. |

**Workspace path shape is load-bearing and stays byte-identical to the old skill:**
`~/.claude/job-profiles/<name>/applications/<company>-<role>-<YYYY-MM-DD>/`
`[1]` records that resume-an-in-progress-application (SKILL.md:45) keys off this shape and that a run inventing its own layout breaks resumption with no error.

### A.2 Ownership, in one sentence each

- **discover owns** search-preferences and the shortlist. It never writes into an application workspace.
- **assess owns** the posting and the assessment. It never writes a CV.
- **apply owns** the tailored profile, all rendered outputs, `claims.yaml`, and `interview-brief.md`.
- **interview owns** `mock/` and may append exactly one section (`## Walk-back list`) to `interview-brief.md`, plus new entries to `claims.yaml` with `source: session-answer <date>`.

### A.3 What is immutable, and by what rule

1. **`profile.yaml`** — because overwriting it is destructive and unrecoverable, and it surfaces only on the *next* application, when the "master" is already narrowed to the previous job `[1]`.
2. **Market conventions** — because they are the one class of statement in the whole skill with nothing to cite, so a wrong one looks exactly like a right one on screen `[3]`. Only a dated, provenance-kinded, human-authored entry may make such a claim.
3. **Raw captures** (`raw/*.json`, `posting-source.txt`, `transcript-*.md`) — because every downstream claim's provenance terminates here. If these are editable, provenance is theatre.
4. **`claims.yaml` entries** — because the whole point is that a retracted claim leaves a visible scar.
5. **The read-only guarantee** — no mode, in any circumstance, may invoke an `opencli` command whose adapter metadata says `access: write` `[4]`. Not a preference, not a confirmation flow: an allowlist plus `scripts/check_no_write.py` over `journal.jsonl`.

---

## B. MODE-BY-MODE

### B.1 `discover`

**Entry condition (any of):**
- User asks to find/search/compare jobs.
- An assess run produced verdict `likely screen-out` or `blocked`, or the honest-gap early-stop fired.
- An assess run produced `stretch` *and* the user has not said they want this specific role.
- User supplied two or more postings (ranking mode).

This is `[2]`'s JD-fit auto-trigger gate, re-anchored. **Conflict resolved:** `[2]`'s gate fires on `JD 岗位匹配分 < 65`, `< 70`, and probability bands `0-10% / 10-25%` — three of five conditions reference the two things the owner has cut, so carried over literally the gate never fires. I map them onto the verdict scale instead. Keep verbatim from `[2 12:47]`: **the trigger reason must be stated before the search runs and written into the shortlist.**

**Inputs:** `search-preferences.yaml`, `profile.yaml` (for the role picture), the triggering assessment if any, market key.

**Steps:**

0. State the trigger reason. Write it to `shortlist.md §0`.
1. **Auth probe.** `opencli auth status --site boss,linkedin,indeed,51job -f json`. Three states, never two: `logged_in`, `not_logged_in`, `unknown`. `unknown` returns `logged_in: ""` — an empty string, not `false` — and must be re-probed with `--full --timeout 40` `[4, measured on nowcoder/maimai]`. Sites absent from the listing entirely (`indeed`, `51job`) have **no auth adapter**; that is not an error `[4, measured]`.
2. **Source selection.** Prefer no-auth sources. `51job` is the only adapter verified to return fully-populated rows on every documented column `[4, probed]`. `indeed` works without login but returned **empty `title`, `salary`, `tags`** on both probe rows `[4, probed]`.
3. **Search, read-only.** Exact commands live inline in SKILL.md (see §C); full flag catalogues in `references/discovery-sources.md`.
4. **Row-integrity check** before anything else looks at the rows: assert the identifying field (`title`) is non-empty. For indeed, follow `opencli indeed job <id>` per row to recover it `[4]`.
5. **Detail fetch** for candidate rows: `boss detail <security_id>`, `51job detail <jobId>`, `linkedin job-detail <job-url>`, `indeed job <id>`.
6. **Rank and bucket** using the *same five-level vocabulary as assess* (see §B.2) — not `[2]`'s A/B/C/D. **Conflict resolved:** `[2]` itself warns that carrying both vocabularies gives the user two verdicts that can disagree; I keep one. `[2]`'s per-bucket columns survive because they carry the actual instruction: `worth applying` → 投递策略, `stretch` → 补强动作/最大缺口, `likely screen-out`/`blocked` → 替代方向. Drop `回音可能性 0-100` entirely — a fabricated number by construction.
7. Keep verbatim from `[2 12:146]`: *if the original JD was judged unsuitable, this round's candidates must be visibly steadier than it, not just similar in title.*
8. Write `shortlist.yaml`, `shortlist.md`, and the **source report**.

**Artifacts:** `shortlist.yaml`, `shortlist.md` (with §0 source-and-read-quality, §0.1 trigger reason), `raw/*.json`, `journal.jsonl`.

**Failure modes:**

| Mode | Detection | Response |
|---|---|---|
| Login-gated 403 | exit 1, **stdout empty**, stderr is YAML `error.code: COMMAND_EXEC` even under `-f json` `[4, measured on 1point3acres]` | Cross-check auth status. Surface `opencli <site> login` to the *user* — it is a write command. Do not retry; the 403 is deterministic while logged out. Do not trust `strategy: public` as evidence no login is needed. |
| Silent partial extraction | exit 0, well-formed JSON, documented columns empty `[4, measured on indeed]` | Assert identifying field non-empty. Follow the detail command. Report the gap. **Never** infer "the site has no such jobs" from blank fields. |
| Platform limit / risk control | Trigger-string list per platform profile `[2 §7.1]` | Stop immediately. No retries, no parameter variation, no circumvention. Emit the direction-level fallback + the disclosure form. |
| Zero results vs blocked | exit code branch **before** interpreting emptiness `[4]` | Only "no results" when exit==0 AND stdout parsed to an array. |
| Bridge outage | `opencli doctor` `[4]` | Distinguishes infrastructure failure from a single-site problem. |

**Degraded output — carried over nearly byte-for-byte from `[2 §7.1–7.2]`, generalized off BOSS:** when no real listings can be retrieved, emit a **direction-level shortlist** (3–5 target directions, search keywords per direction, recommended filters, why each is steadier than the original JD, titles/signals to avoid, manual-collection priority order) plus a **pre-filled disclosure block whose answers are hardcoded to "no"**:

```
Session logged in:              <yes|no|n/a — no auth adapter>
Adapter response:               <verbatim error.message>
Retried after the limit signal: no
Bypassed any platform control:  no
Real listings retrieved:        no
Degraded output type:           direction-level shortlist
```

That fourth property — a required artifact with the answers pre-set — is what makes concealment require an active overwrite. It is the single most transferable design in `[2]` and it generalizes to every source.

**Gate (`scripts/check_shortlist.py`) — must pass before discover claims success:**
- Every row has a `source_site`, a `source_id` **that appears verbatim in `raw/`**, a `retrieved_at` timestamp, a non-empty title, and a `why_matched` line.
- No URL that was not returned by an adapter. Where a source has no URL, a traceable identifier (`security_id`, `jobId`, `id`) and its source file.
- Count reconciliation: if fewer rows than the target were produced, a written shortfall reason exists. `[2 anti_hallucination:112]` — never pad.
- **Empty-result disambiguation:** the script reads `journal.jsonl` and refuses to let the run say "nothing matched" unless at least one adapter returned exit 0. All-adapters-failed and found-nothing produce the same shape otherwise.
- `check_no_write.py` finds zero `access: write` invocations.

---

### B.2 `assess`

**Entry condition:** a posting exists — a URL, pasted text, or a shortlist row the user picks.

**Inputs:** posting text, `profile.yaml` or a supplied CV, resolved market key, `references/market-conventions/<key>.yaml`.

**Steps:**

1. **Fetch-integrity gate.** A `200 OK` is not proof you have the posting `[1]`. Thresholds inline: ~300 words of readable prose plus a requirements section = usable; under ~200 words, no qualifications language, or a login/consent/bot-check prompt = blocked. On block: ask for a paste. Terminal case: stop and say so. Never extract requirements off a login wall — everything downstream is internally consistent and wrong.
2. **Market resolution: ask the user.** **Conflict resolved:** `[3]` ships a 1000+-line `resolveMarket` pattern matcher and documents three uncovered defect classes it cannot close without a real gazetteer; `[5]`'s tables carry `applies_when` gating that implies automatic resolution. I take `[3]`'s own advice — a skill can just ask, which deletes the entire documented defect class. `applies_when` then filters *within* the chosen market.
3. **Extract `posting.yaml`.** Complete field list, inline in SKILL.md: `role_title, seniority, location, must_haves, nice_to_haves, responsibilities, keywords, company_values_tone, red_flags, salary_range, application_type`. `[1]` records that the old SKILL.md:71 silently dropped `salary_range` and `application_type` — and `application_type: structured` is the **only** signal routing to the supporting-statement branch. That condensation defect already shipped; do not repeat it.
4. **Surface `[disqualifier]` items first** and ask directly `[1]`.
5. **Build evidence blocks.** `scripts/evidence_blocks.py` chunks `posting-source.txt` → `JD-nnn` and the CV → `CV-nnn`. Parameters from `[3]`: 900 chars max, 80 blocks/source, split on blank lines or a newline before a bullet/number/CJK numeral, sentence-split over-long paragraphs on `[。.!?]`, drop chunks under 8 chars, ids zero-padded to three digits.
6. **Requirement table.** One row per must-have and per named responsibility, each with `level` (required/preferred/unclear), `screening` (knockout/weighted/nice_to_have), `match` (strong/partial/gap/no_evidence), `recency` (current/recent/dated/undated), and `evidence: [{ref: CV-012}, {ref: JD-004}]`. Enum set from `[3 §5]`; the `level`-vs-`screening` split is the non-obvious win — most "required" lists are wish-lists, and counting the label is what turns a missing clearance into a score deduction instead of a stop.
7. **Countable facts, no scores:**
   ```
   Must-haves strongly evidenced:   X of N   (P partial, G gap, U no evidence)
   Core responsibilities demonstrated: M of K
   Seniority fit:  <step_up | lateral | step_down | unclear>
   Effort to close what is closable: <quick | evening | multi_day | not_closable>
   APPLY VERDICT:  <strong apply | worth applying | stretch | likely screen-out | blocked>
   ```
   Every one of the N and K is printed with its evidence refs, so the denominator is auditable. `strongly evidenced` counts `strong` only; `partial` and `gap` are never merged into a "covered" number `[1]`. Stale-only evidence is `partial`, not `strong` `[1]`.
8. **Refusal state.** `INSUFFICIENT EVIDENCE — no verdict` when the inputs cannot support one: no readable posting, no readable CV, image-only source with unreadable regions, or a CV that is a skills list with no supporting bullets. This is `[2]`'s score-consistency gate translated off numbers: *a confident positive verdict is forbidden when the inputs cannot support one.* `[1]` has no such floor today.
9. **Render market conventions verbatim** for the resolved market whose `applies_when` matches, by id, from an allowlist. Conventions feed **neither the verdict nor any consistency check** — isolation rule from `[3]`.
10. **When the verdict is `likely screen-out` or `blocked`:** produce the "what to do instead" half — this is `[2]`'s career-coach value, kept as an *output of assess*, not a fifth mode. Forced single strategy from a closed set (apply-and-test / reposition / skill-sprint / adjacent-entry / redirect), plus a 30/60/90 table whose columns are `目标 | 行动 | 验收标准` and a roadmap whose rows carry `输出物`. Those two columns are the whole value: they convert advice into something checkable `[2 §6]`.

**Artifacts:** `posting.yaml`, `posting-source.txt`, `evidence-blocks.json`, `fit-assessment.yaml`, `fit-assessment.md`, journal entries.

**Gate (`check_assessment.py` + `check_evidence_refs.py` + `consistency.py` + `lint_no_prediction.py`):**
- Every requirement row has at least one resolvable evidence ref, or `match: no_evidence` with no refs.
- Zero unresolvable refs survive into the rendered file; zero block ids appear in reader-facing prose.
- Zero percentages, zero invented scales, zero prediction vocabulary.
- Required disclaimer present.
- Disqualifiers rendered before the verdict.
- Consistency notices attached where they fire (never repaired).

---

### B.3 `apply`

This is the absorbed `job-application` skill. I do not restate its pipeline; I record what **changes**.

**Entry condition:** an assessment exists. `stretch` and `likely screen-out` do **not** block entry — a well-built application to a reach role is not a defect `[1]`. `blocked` prompts once ("this requirement is a legal barrier, not a framing problem — do you still want to apply?") and proceeds if the user says yes.

**Five changes from the old skill:**

1. **`claims.yaml` becomes a required artifact.** Every REFRAME / KEYWORD-INSERT / AMPLIFY term that enters the tailored profile gets a row: `{term, where, source_kind: profile-line|session-answer|fetched-artifact, source_ref, session_date}`. This converts `[1]`'s highest-value silent rule — the claim-provenance checkpoint, which "produces no artifact, no provenance file, no citation column, no diff" — into something `check_claims.py` can fail on.
2. **`scripts/parse_verdicts.py` replaces the model as parser.** Every agent file says *"the orchestrator parses this block programmatically"* and no such program exists `[1]`. Now it does: last `VERDICT:` line per judge, exact `PASS`/`REJECT` else `AMBIGUOUS`, AND-combine, extract `COVERAGE`/`SCORES`/`MISSING_OR_WEAK`/`LEVELING`/`STANDOUT_SIGNAL`/`SUPPLEMENTARY_QUESTIONS_FOR_CANDIDATE`, write `judge-round-<n>.json`. The round becomes a durable artifact, which also supplies the round counter the loop currently lacks.
3. **Render freshness is hashed.** `judge-round-<n>.json` records the sha256 of every file pasted into each judge. `check_render_freshness.py` fails if a round's hash does not match the file on disk at judge time. `[1]`: re-judging a stale `cv.md` produces a perfectly valid-looking verdict block and is self-confirming, because the judges return the same feedback that was supposedly just addressed.
4. **The Cluster-1 personal-data interlock is fixed and made loud.** `[1]` measured DOB leaking through for `United States of America`, `US (Boston)`, `Los Angeles, CA`, `U.K.`, `remote (US)` — and the eval-0 scenario input literally reads `TARGET MARKET: United States (Los Angeles, CA)`. Normalize before matching; warn to stderr and name the fields when a market resolves to no known cluster and personal data is present.
5. **`render_letter.py` engine bug is fixed.** `render_letter.py:101` compares the engine to the bare string `"tectonic"` where `render_cv.py:992` compares `pathlib.Path(engine).name`; on the owner's machine `find_latex_engine()` returns `/opt/homebrew/bin/tectonic`, so the CV PDF builds (15,927 bytes) and the letter PDF fails — same engine, same run, 51/51 tests green `[1, reproduced]`. Fix, hoist argv construction into one shared helper, and add the regression test the suite lacks.

**Gate (`check_apply.py`):** three PASS verdicts parsed from `judge-round-<n>.json`, or an honest-stop reason recorded and classified as **poorly built** vs **honest stretch** `[1]`; every term in `tailored-profile.yaml` absent from `profile.yaml` appears in `claims.yaml`; render hashes fresh; `profile.yaml` mtime unchanged; personal-data interlock fired or warned; `lint_cv.py` and `check_letter.py` clean; `interview-brief.md` exists.

---

### B.4 `interview`

**Entry condition:** an application package exists in the workspace, **or** the user supplies a posting + CV and says they have an interview.

**Architecture — decided, with the mechanical reason:** inline interviewer + two-pass subagent assessor, both anchored to an on-disk transcript, question bank demoted to seed material `[6 §5]`.

The deciding fact is mechanical, not aesthetic: a spawned subagent **cannot hold a turn-by-turn conversation with the human**. `agents/hiring-manager.md:21` says its inputs are pasted below the prompt at dispatch; `:97` says it must end with an exact block. There is no channel to ask and wait. So "subagent as interviewer" is eliminated before any trade-off analysis. And a scripted bank cannot follow up — which matters because *held under probe* is the only band above ASSERTED that means anything.

**The pack split is what makes the assessment honest:**

| Party | Sees | Deliberately does **not** see |
|---|---|---|
| Interviewer (inline) | `posting.yaml`, `cv.md`, `interview-brief.md`, market/family shape, dated scraped shape facts | — |
| Assessor pass 1 (`agents/mock-assessor-transcript.md`) | `transcript-<n>.md`, `posting.yaml`, `cv.md` | **`interview-brief.md`, `claims.yaml`** — so it cannot credit the candidate for a source fact the candidate never actually said |
| Assessor pass 2 (`agents/mock-assessor-provenance.md`) | `transcript-<n>.md`, `claims.yaml`, `interview-brief.md` | the rubric — its only job is `UNSOURCED-FACT` / `OVER-CLAIM` / `CONTRADICTED` |

Two passes with deliberately different inputs is what turns the honesty tripwire from an intention into a mechanism.

**Steps:** pick the loop shape (market × live-artifact family, `[6 §1–2]`); seed `question-log.yaml` with generated + scraped openers, each stamped with provenance and date; run one round inline with a named persona; **flush the transcript after every answer**; run both assessor passes; write `assessment-<n>.md`, update `answer-bank.md` and `open-loops.md`; carry a short open-loops block into round *n+1* rather than the full transcript.

**Scraped material rules (paste-ready, from `[6 §3d]`):**
```
Every scraped item is (a) opened with `detail` for untruncated text, (b) stamped with
its `time` in question-log.yaml, and (c) shown to the candidate with that date.
Anything older than ~12 months may set SHAPE (round count, order, ritual names) but is
never quoted as a specific technical question.
Never use a scraped item whose company entity is in a different country from the posting
unless the post itself names that country.
Never paste a scraped post's ANSWER to the candidate — questions only.
If the adapter returns 403 or "need login", report the source as unavailable and generate
instead. Do not log in to work around it.
```
The country rule is not hypothetical: `nowcoder search "ASML 面试"` returned three real posts, all describing the **China entity's** 宣讲会/笔试 pipeline, which is not the Veldhoven loop `[6, probed]`. Same company name, real content, wrong process. It is the most dangerous failure in the source because nothing looks wrong.

**Scoring: bands, not scores.** Four bands worded as evidence-presence and deliberately **unnumbered so they cannot be averaged**: `NOT PRESENT` / `ASSERTED` / `INSTANCED` / `HELD UNDER PROBE`, plus a non-band flag `CONTRADICTED`. `HELD UNDER PROBE` is the ceiling on purpose — the published Civil Service scale has bands for "exceeds expectations at this level" and this module does not know the level's expectations `[6 §4d]`.

**The one place a number is honest:** where the employer publishes its own rubric — UK Civil Service Success Profiles at the grade named in the advert, an NHS values framework, a university person specification — the skill may walk the candidate through *that* scale, **in the employer's own wording, attributed, as a checklist of what the panel is told to look for**, never as a prediction of the mark. Quoting an employer's scale is reporting; applying it as a verdict is fabrication.

**Write-backs (this is where the mode pays for itself):**
1. `## Walk-back list` appended to `interview-brief.md`: every CV claim that failed under one follow-up, with the transcript quote and softened wording — then offer to re-run the tailoring edit and re-render. This fires the over-reach rule that `interview-prep.md:39` states and has no mechanism to trigger; the three CV judges only read the page, and the page does not stammer.
2. An `UNSOURCED-FACT` that resolves to "true, just not on my CV" becomes a new `claims.yaml` entry with `source_kind: session-answer` — already a permitted provenance source `[1]` — and routes back into the tailoring plan.

**Gate (`check_mock.py`):** every defect tag is in the closed set **and carries the quoted line that triggered it** (no quote, no tag); zero banned vocabulary; every scraped question in `question-log.yaml` has a `time` and a source id; every `answer-bank.md` entry has a `source:` line; if any `PROBE-COLLAPSE` / `OVER-CLAIM` / `CONTRADICTED` fired, the walk-back section exists.

---

## C. LAYERING TABLE

### C.1 The architectural bet: layer 1.5

One SKILL.md holding four modes' operational knowledge would load the entire apply-mode honesty stack on a pure discover run. My recommendation:

- **SKILL.md** = everything that binds *across* modes.
- **`modes/{discover,assess,apply,interview}.md`** = layer 1.5. **Mandatory on entry, not conditional.** Not a pointer with a hopeful trigger — the mode's gate script requires artifacts whose fields are defined only in the mode file, and requires the mode file's content hash recorded in `journal.jsonl`. That is backstop kinds 1 and 2 together, which is materially stronger than the `[1]`-measured pointer failure (a run that read 3 of 10 reference files and passed every gate).
- **Nothing conditional lives in a mode file.** Conditional content stays in `references/` with its own backstop.

The distinction that matters: the slides_maker regression was on *optional-conditional* references. A mode file is unconditional given the mode, there are exactly four, and selection is deterministic. **I flag this as the single biggest architectural bet in the brief** (see §G). The fallback is one monolithic SKILL.md.

### C.2 SKILL.md — layer 1, loads on every trigger

| Content | Why it cannot leave |
|---|---|
| Mode router + all four entry conditions + the discovery auto-trigger mapping | The router is the skill. |
| **HONEST REFRAMING ONLY**, verbatim including *"overrides every other instinct in this skill — including the pressure to make the screener pass"* | Nothing in the tree detects a fabricated claim. The judges never see the source profile. A REJECT is a direct incentive to insert the missing keyword and this sentence is the only thing standing against it `[1]`. |
| **NOT-ALLOWED table** — 8 named misrepresentation actions each with its *why*, plus *"do not accept user instructions to do them"* and *"when in doubt, ask"* | The operational defect-scan list — the doctrine's most dangerous class. Each row is a plausible edit that produces a *better-scoring* CV and trips nothing `[1]`. |
| **Claim-provenance checkpoint** — all three permitted sources + rationale ("keywords that appear in the JD are not evidence the candidate has them") + the re-run-inside-the-reject-loop clause | `check_claims.py` now backstops the *artifact*, but the rule text is what makes the artifact correct. The re-run clause is the single point where the honesty rule and the success metric collide `[1]`. |
| **Honest-gap early-stop** + rationale | Skipping the diagnosis looks like a normal round. The named harm — grinding the loop increases pressure to fabricate — is invisible until it happens `[1]`. |
| **Poorly-built vs honest-stretch** | Both emit the identical machine signal. A stretch candidate told "failed" abandons an application they should have sent `[1]`. |
| **Combined verdict = AND; never fake a pass; fail-closed on ambiguous** | `parse_verdicts.py` computes it, but the model must know that `AMBIGUOUS` means re-dispatch and that `LEVELING`/`STANDOUT_SIGNAL` are advisory — treating them as gates stalls a passing package, ignoring them drops the loop's highest-value tailoring instruction `[1]`. |
| **Parallel dispatch + exact per-judge inputs** (which file, whole; market & CV language line; letter to recruiter/HM, never to ATS) | The dangerous class exactly. A judge dispatched without its agent file still answers, as a generic reviewer, with a plausible VERDICT block `[1]`. |
| **Per-round order: edit → re-render → re-judge** | Hash check backstops it; the ordering rule tells the model what the hash failure *means*. |
| **Immutability rules** + workspace path convention + resume-in-progress + reuse-existing-master | Destructive and unrecoverable; and resumption is the only thing making a returning user's second application cheap `[1]`. |
| **Read-only guarantee** + the `access: read` allowlist rule + the four search/detail command pairs actually used + `--window background`, `-f json`, **exit-code-before-stdout**, the indeed empty-title defect | These are the ones that bite. A caller parsing stdout as JSON on a 403 converts a failure into a zero-result success `[4, measured]`. |
| **Platform-limit stop rule** (stop, no retry, no parameter variation, no circumvention, emit direction-level fallback, fill the disclosure form) | The generic half of `[2]`'s best-engineered section. The per-platform trigger strings are data; the doctrine is not. |
| **FIT ASSESSMENT block template + the required disclaimer** | `[1]` calls this the highest-consequence single paragraph currently sitting in layer 2 with zero backstop. Now artifact-backed, but the template is short and the disclaimer is the thing that stops a count being read as a prediction. |
| **Banned output vocabulary** `[6 §4f]` + the published-employer-rubric exception | `lint_no_prediction.py` catches the lexical half; the exception's *shape* (quote, attribute, never assert the mark) is judgement. |
| **Anti-coaching four rules + the tripwire** `[6 §6]` | `[6]` says this explicitly: nothing fires if skipped, the session just quietly coaches the candidate into a lie. |
| **Equivalence test** (honest ≠ timid) | The counterweight to the honesty rule, with no gate at all — under-claiming is invisible to every judge and every test, and its absence systematically under-sells exactly the stretch/career-switcher cases the skill exists for `[1]`. |
| **Case C — a hard disqualifier is a wall** | `grep disqualifier SKILL.md` returns nothing today. A fake "mitigation" counts as *addressed* to the recruiter judge `[1]`. |
| **Quantification fallback ladder** (5 levels) + **qualitative-evidence rule** for non-metric professions + **recency downgrade** | Without the ladder the model has two executable options: vague, or invented. The soft metric is a fabrication that *improves* the CV against a naive reading `[1]`. |
| **LEAD-WITH prioritization + name-the-cuts** | No renderer measures page position; a well-covered, badly-ordered CV passes the ATS gate outright `[1]`. |
| **AI-uniformity check, four named dimensions** | The harm lands entirely at the real human recruiter, outside every loop the skill can observe `[1]`. |
| **Cluster-1 personal-data interlock** | Highest legal consequence; its documented backstop was false for plausible inputs `[1, measured]`. |
| **Posting-fetch integrity thresholds + platform list** | The garbage-in root of the entire pipeline. |
| **Complete extraction field list** including `salary_range` and `application_type` | A condensation defect that already shipped `[1]`. |
| **Structured-application review substitution** | Silently overrides a rule SKILL.md declares "non-negotiable" `[1]`. |
| **Localized salutation table** (DE/FR/ES/IT/NL, named-recipient rule, never `To Whom It May Concern`, never a guessed name) | Renders perfectly, read by no gate, instantly noticed at the real employer `[1]`. Six lines. |
| **Mock session mechanics** — the pack split, one round per dispatch, flush-after-every-answer | Operational; a contaminated assessor produces a normal-looking assessment. |
| **Grounding contract summary** — the three-mechanism map (§E) | The skill's spine. |
| **Gate table** — every gate, its script, and "a mode may not claim success without its receipt in `journal.jsonl`" | |
| **Self-check list naming every reference file, every script, and every mode file** | `[1]`'s single most important structural finding: `grep -n "checklist\|self-check" SKILL.md` matches one line and it is prose about the posting. The doctrine's third backstop form **does not exist anywhere in the current skill.** |

### C.3 Layer 1.5 — mode files

| File | Backstop |
|---|---|
| `modes/discover.md` | `check_shortlist.py` requires `shortlist.yaml` fields (`source_site`, `source_id`, `retrieved_at`, `why_matched`, `verdict`, bucket column) defined only here; `check_no_write.py`; journal must record the file hash. |
| `modes/assess.md` | `check_assessment.py` + `check_evidence_refs.py` require `fit-assessment.yaml`'s row schema (level/screening/match/recency/evidence) defined only here. |
| `modes/apply.md` | `check_apply.py` requires `claims.yaml`, `tailoring-plan.md` sections, `judge-round-<n>.json`. |
| `modes/interview.md` | `check_mock.py` requires `question-log.yaml`, `answer-bank.md`'s `source:` line, transcript flush cadence. |

### C.4 Layer 2 — references, each with its backstop

| File | Trigger (evaluable without reading it) | Backstop |
|---|---|---|
| `references/market-conventions/<key>.yaml` | Always, once a market is chosen | **Deterministic:** `check_conventions.py` (digit/percent ban, `source.kind` ∈ {maintainer, published}, `retrieved` ISO date, `review_by` in future, no protected trait, id uniqueness) + id-allowlist in `render_assessment.py` (unknown/duplicate ids dropped) + the assessment artifact renders convention ids that must resolve. |
| `references/market-conventions/README.md` (rules for adding an entry) | When a human edits the table | Same lint; the rules *are* the lint's spec. |
| `references/discovery-sources.md` (per-adapter flags, trigger strings, degraded-fallback fields) | "You are in discover mode and about to call an adapter other than the four inlined in SKILL.md" | **Required artifact:** the source report cannot be filled without per-source fields; + `check_shortlist.py`. |
| `references/interview-shapes.md` (market × family loop shapes, live-artifact table, band descriptors, closed defect-tag set) | Always in interview mode | **Deterministic:** `check_mock.py` holds the closed tag set and fails on an invented tag, and requires quote-per-tag; `assessment-<n>.md` and `answer-bank.md` cannot be written without the bands. |
| `references/cv-craft.md` (three clusters, ATS mechanics, bullet craft, projects-vs-experience, section ordering, CJK path, links) | "The target market is not the one you last built for" / "you are about to write bullets" | **Partial.** Deterministic for links, CJK, section-order *mechanism*, banned phrases, bullet length (`lint_cv.py`, renderer tests). **Not backstopped:** the cluster convention content itself (2 pages EU, photo norms). Mitigated by `check_pages.py` and by moving the highest-consequence cluster rule (Cluster-1 personal data) inline. Honest residual risk. |
| `references/role-families.md` (9 recipes + the one fallback question) | "The target is not a software/research/engineering job" | **Required artifact field:** `tailoring-plan.md` must carry a `section_order_decision:` line naming the family and the reason; `check_apply.py` fails without it for non-tech targets. Plus `render_cv.py` now warns on dropped `meta.headings` / `meta.section_order` keys and lists the valid set. |
| `references/candidate-situations.md` (8 playbooks) | "The profile shows a gap, a pivot, a re-entry, over-qualification, thin history, exec scope, military service, or foreign credentials" | **Partial.** The eight **Do-NOT lists move inline** (they are fraud variants that exist nowhere else — "imply a clearance level higher than the real one", "invent a credential equivalency"). The playbooks stay, backstopped by the `tailoring-plan.md` `situation:` field + a layer-1 checklist item naming the file. |
| `references/motivation-letter.md` (skip gate, structure, market calibration, formatting contract) | "A letter is in scope" | **Deterministic:** `render_letter.py` validates body markdown, word count, paragraph count, closing-name duplication; `check_letter.py` diffs company/role against `posting.yaml`. The NL "letter universally expected" fact **relocates into the nl market conventions table**, which is rendered — a real backstop upgrade. Salutations move inline. |
| `references/structured-applications.md` | "The posting splits Essential/Desirable, names behaviours or Success Profiles" | **Required artifact:** `supporting-statement.md` with one heading per criterion + `check_word_limits.py`. Review-substitution rule inline. |
| `references/rirekisho.md` | "Target is Japan AND a traditional/domestic employer" | **Deterministic refusal:** `render_rirekisho.py` CLI has `choices=["md","docx"]`, no pdf — the export step cannot be silently skipped. Age-computation rule inline. |
| `references/tailoring-plan.md` (gap-table format, worked examples) | Always in apply mode | **Required artifact:** `tailoring-plan.md` itself. |
| `agents/*.md` (5 files) | Named at dispatch | **Required artifact:** the file's full text IS the dispatch payload; + fail-closed verdict parsing catches a judge answering free-form. |

### C.5 Inline, no backstop available — the honest list

These have no artifact, no lint, and no checklist that can prove they were applied. They stay in SKILL.md however bulky:

1. HONEST REFRAMING ONLY (the arbitration clause).
2. Equivalence test — under-claiming is invisible to every gate.
3. Poorly-built vs honest-stretch distinction — identical machine signal either way.
4. Anti-coaching rules 1–4 (never write an answer; no leading questions; undefendable claim is a CV bug; never rehearse a gap into a non-gap).
5. The advisory/non-advisory split on `LEVELING` and `STANDOUT_SIGNAL`.
6. The judge-lane boundaries and the deliberate `>= 3` recruiter / `>= 4` hiring-manager asymmetry — properties of the *ensemble*, so no agent file can enforce them and no code composes them. Break the asymmetry and "honest stretch" becomes unstateable.
7. The fast-path bounded permission (collapses confirmations, never the analysis or the judges).
8. Enrich-from-the-candidate's-own-papers, including the attribute-honestly half — the one place the third provenance source legitimately opens up, and misreading it produces a fabrication *with a real citation behind it*.
9. Cluster-conventions content (partially mitigated, see C.4).

### C.6 Size, and whether it is acceptable

**Estimate, not a measurement:** the old SKILL.md is 218 lines for one mode `[1]`. The cross-mode spine above is roughly 320–420 lines; each mode file 120–250. Total layer-1 + 1.5 ≈ 800–1,300 lines, of which **320–420 load on every trigger and one mode file loads per run.**

Is that acceptable? For layer 1 alone, yes, and here is the argument. The doctrine's cost of bulk is tokens, rule conflicts, buried priorities, and maintenance. Of those, only "buried priorities" is a correctness risk, and it is bounded by ordering: the honesty stack comes first, the router second, the gate table third, the self-check last. The cost of the alternative is measured, not theoretical — a lossless split of another skill produced a run that read 3 of 10 reference files, used the wrong helper with the wrong parameter, and passed every automated gate.

The place I would *not* accept the size is a single monolith at 1,300 lines loading for a user who just said "find me some jobs in Amsterdam". That is what layer 1.5 buys, and it is why the mode files need a hard backstop rather than a hopeful trigger.

**Migration discipline:** `scripts/check_skill_lossless.py`, run in CI, asserting every substantive line of the old `job-application` tree is findable somewhere in the new tree, with an allowlist carrying a written reason per deletion. And a warning the check cannot give: it measures whether bytes exist, not whether they reach context when needed. The only real test is running the end-to-end evals afterwards and reading what the outputs are missing.

**One flagged rewrite.** `[1]` requires the FIT SNAPSHOT disclaimer be moved byte-for-byte. But that disclaimer is *about keyword-coverage percentages*, which this skill no longer emits. Moving it verbatim would ship an incoherent paragraph. **Conflict resolved:** this is a genuine rewrite, so per the doctrine it goes in a separate, small, readable commit — not smuggled into the migration diff — and the migration allowlist records it by name.

---

## D. DETERMINISTIC CHECKS

Ordered by "has this defect already bitten the owner?"

### P0 — closes a measured, live defect

| Script | Decides | Inputs | Failure output |
|---|---|---|---|
| `render_letter.py` engine fix + shared `_engine_cmd(engine, tex, outdir)` | Whether the LaTeX argv matches the engine | engine path | Regression test: monkeypatch `find_latex_engine` to return an absolute path ending `/tectonic`, assert argv is `[engine, tex, "--outdir", parent]`. **Reproduced today:** CV PDF 15,927 bytes, letter PDF *"LaTeX compile failed"*, same machine, 51/51 tests green `[1]`. |
| `check_personal_data.py` + normalized `_is_cluster1` | Whether protected personal data can reach a Cluster-1 CV | `tailored-profile.yaml`, `meta.target_market` | Strip parentheticals, split on `,` `(` `/`, match any token. On unknown market **with** `contact.personal` or `meta.photo`: `WARNING` to stderr naming the fields and the market string, never a silent render. Test asserts every string in a fixture list of realistic spellings either suppresses or warns. Measured leaks: `United States of America`, `US (Boston)`, `Los Angeles, CA`, `U.K.`, `remote (US)` `[1]`. |
| `parse_verdicts.py` | The combined verdict | three judge transcripts | JSON `judge-round-<n>.json`. Last `VERDICT:` line per judge, case-insensitive; anything other than exactly PASS/REJECT → `AMBIGUOUS` (fail-closed, re-dispatch). Combined PASS only when all three are exactly PASS. Gives the loop the round counter it lacks. |
| `check_render_freshness.py` | Whether judges saw the current files | `judge-round-<n>.json`, files on disk | `STALE: cv.md hash at judge time <a> != on disk <b>` — the round is void. |
| `check_claims.py` | Whether every new claim is sourced | `profile.yaml`, `tailored-profile.yaml`, `claims.yaml` | Per unsourced term: `UNSOURCED: "Kubernetes" appears in tailored-profile.yaml:skills.infra, not in profile.yaml, no claims.yaml entry`. Also fails if `profile.yaml` mtime changed during the run. |
| `lint_no_prediction.py` | Whether any output invented a number or a prediction | `fit-assessment.md`, `shortlist.md`, `mock/assessment-*.md`, `cheatsheet.md` | Bans `%`, `\b\d+\s*/\s*\d+\b` scores, `chance`, `probability`, `odds`, `likely to be (hired|interviewed)`, `strong candidate`, `weak candidate`, `would pass`, `no-hire`. **Allowlist:** text inside a blockquote that is followed within two lines by an attribution line naming a published employer rubric. Exit non-zero with line numbers. |
| `check_evidence_refs.py` | Whether every citation points at real text | `fit-assessment.yaml`, `evidence-blocks.json`, rendered `.md` | Unresolvable ref → dropped and listed, never fatal to the whole assessment `[3]`. Separately: any `CV-\d{3}`/`JD-\d{3}` token in reader-facing prose is stripped and reported — refs travel in the evidence arrays, ids in a sentence are noise to a reader who never sees the block list. |
| `check_shortlist.py` | Whether the shortlist is real | `shortlist.yaml`, `raw/*.json`, `journal.jsonl` | Per-row: missing source id / id not found in raw capture / empty title / missing `retrieved_at` / composed URL. Global: shortfall without a reason; **"no results" claimed while the journal shows zero adapters at exit 0**. |
| `check_opencli_result.py` (wrapper, not a gate) | How to read an adapter invocation | exit code, stdout, stderr | Classifies into `{ok, platform_limit, not_logged_in, no_auth_adapter, transport}`. **Exit code first, always** — a 403 gives exit 1 with empty stdout, which `JSON.parse(stdout \|\| '[]')` silently converts into a zero-result success `[4]`. |
| `check_no_write.py` | Whether a write command ran | `journal.jsonl`, `opencli <site> --help -f yaml` | Reads the tool's own `access: read\|write` field and fails on any invocation of a `write` command. Strongest available guard, because the authority is the tool's published metadata, not a list we maintain. |
| `check_conventions.py` | Whether the market table is shippable | `references/market-conventions/*.yaml` | `Market convention <id> states a number: <field>` (digit or `%` in any prose field; `url`, `title`, `retrieved` exempt — a cited document's title is an identifier, not a claim, and statutes are numbered). `<id> has no usable source`. `published` requires `^https://\S+$` and `^\d{4}-\d{2}-\d{2}$`. Protected-trait scan. Duplicate ids. **`review_by` in the past → fail.** `[5]`'s review found live violations of exactly these: `"51job"` in an English convention body, `"30% ruling"` in both languages of another, `"2023/970"` in a third. |

### P1 — closes a defect class the inputs demonstrate

| Script | Decides | Inputs | Failure output |
|---|---|---|---|
| `consistency.py` | Whether the assessment contradicts itself | `fit-assessment.yaml` | Port of `[3 src/ui/consistency.js]`, re-anchored: (a) verdict/effort conflict — `strong apply` with effort `multi_day`/`not_closable`; (b) loose knockouts — more than two `screening: knockout` rows; (c) uncovered gap actions — more closable gaps than there are actions in total. Plus work-authorization alignment: `requires_existing` × `needs_sponsorship` → `conflict`; × `student_or_graduate`/`temporary_route` → `verify`, never `conflict` — calling that a conflict would wrongly kill viable applications. **Reports, never repairs**; code can see two fields disagree, not which is right. Every test pins the quiet case as hard as the firing one — a check that cries wolf on ordinary output is worse than no check, because the reader learns to skip the line. |
| `lint_cv.py` | Mechanically-decidable CV defects | `cv.md` | Banned phrases, weak openers, bullets over ~2 rendered lines, repeated opening verb across roles (AI-uniformity dimension 1), `References available on request`. Voice and specificity stay inline — code cannot see those. |
| `check_letter.py` | Letter contract violations | `letter.yaml`, `posting.yaml` | Markdown markup in a `body` string (renders literally — `**bold**` prints four asterisks `[1]`); word count outside 250–400; paragraph count outside 3–5; sender name in `closing` (prints twice); `recipient.company` ≠ `posting.yaml:company`; role title mismatch. |
| `check_mock.py` | Whether the mock session is honest and legible | `mock/*` | Tag not in the closed set; tag without a quote; scraped question without `time` or source id; answer-bank entry without `source:`; banned vocabulary; walk-back section missing after a collapse. |
| `render_cv.py` heading/order warnings | Whether a relabel silently vanished | `meta.headings`, `meta.section_order` | `WARNING: meta.headings key 'selected_matters' is not a section key; valid keys: …`. Verified silent today: a legal CV built from the role-families recipe loses its "Selected Matters" heading on a key typo `[1]`. |
| `check_skill_lossless.py` | Whether the migration lost a line | old tree, new tree, allowlist | Per unaccounted line: path + text + "not found in new tree and not in allowlist". |

### P2 — worth writing, lower urgency

`check_pages.py` (PDF page count vs market target — closes the one gap "name the cuts" polices by hand); `render_rirekisho.py` date sentinel (`_ym('Sep 2023')` → `('','')` today, producing blank 年/月 cells in a structurally invalid form that renders, saves and passes pytest `[1]`); `check_word_limits.py` (per-criterion supporting-statement counts); `count_coverage.py` (compute X-of-N in code from the printed requirement rows, so there is exactly one count-producing path).

**Cross-cutting testing discipline, from `[3]`:** two of its checks exist specifically because their absence produced silent failures — one imports the panel against real markup so a stale element id fails the suite instead of blanking the page, and one *fires the registered click handlers*, because a test that only imports the module proved the button existed and never that pressing it did anything. Apply the same rule here: `test_letter_pdf_degrades_without_engine` monkeypatches the engine to `None` and never exercises the tectonic branch — which is exactly why 51/51 tests pass on a broken renderer.

---

## E. GROUNDING ARCHITECTURE

Three mechanisms, three different jobs. They do not overlap and none substitutes for another.

```
  raw source text                what the skill says                who checks
  ───────────────                ───────────────────                ──────────
  posting-source.txt  ──chunk──► JD-001…JD-080  ──cited by──► requirement rows
  cv.md / profile     ──chunk──► CV-001…CV-080                     │
                                                                    ▼
                                                        check_evidence_refs.py
                                                        (resolve or DROP the ref)

  profile.yaml line   ─┐
  session answer      ─┼──────► claims.yaml ──required by──► every REFRAME /
  fetched artifact    ─┘                                      KEYWORD-INSERT term
                                                                    │
                                                                    ▼
                                                             check_claims.py

  a human, in a commit ────────► market-conventions/<key>.yaml
                                        │  id allowlist, rendered VERBATIM,
                                        │  never round-tripped through the model
                                        ▼
                                 check_conventions.py
```

**1. Evidence blocks bind *analysis* to source text.** The model may only cite blocks that exist; every reference is resolved on arrival and any that does not resolve is **dropped, not fatal** `[3]`. An empty evidence list is not an error — rejecting it discarded the analysis while an *invented* ref sailed through to the same empty array, which punishes the honest shape and passes the dishonest one. Carry the honest bound into the skill's own output: **this is a plausibility bound, not a proof — it guarantees a claim points at something real, not that the claim follows from it.**

**2. The claim-provenance checkpoint binds *output* to source facts.** Three permitted sources and no fourth: a specific line or field in the profile; an answer the user gave this session; a paper or repo the candidate authored, fetched and read this session. Anything else goes to HONEST-GAPS. `claims.yaml` makes this a diffable artifact for the first time.

**3. The market table binds the one claim class with nothing to cite.** In the entire skill, exactly one kind of statement is not traceable to user-supplied text: what a market screens on that the posting does not say. That is why it is written by a person, dated, provenance-kinded, allowlisted by id, and **rendered verbatim** — so the model cannot strengthen a "usually" into a "must", attach a number, or invent an entry. The model's only authored sentence in that section is where *this CV* stands against the convention, which cites CV blocks like any other claim.

**How they compose per mode:**

- **discover** — no analytical claims about the candidate exist yet. The grounding object is the *listing*: every field either came from an adapter row or is written `未显示` / `not shown`, never inferred `[2]`. Source id + `retrieved_at` mandatory; listings decay and a copied one may already be closed. Conventions may be rendered (e.g. the BOSS profile-is-the-screen entry) verbatim, because they change how the user should read the whole result set.
- **assess** — evidence blocks carry the analysis; conventions render alongside and feed **neither the verdict nor any consistency check**. Requirements, screening, verdict and effort stay derived from the posting and the CV alone.
- **apply** — `claims.yaml` is the spine. An evidence-block ref from assess is a valid `source_ref`. Conventions govern the *artifact set and format*, not the content: the letter is expected in NL, the graded Arbeitszeugnis is expected in DE, the supporting statement replaces the CV in NHS/Civil Service.
- **interview** — `claims.yaml` becomes the interview provenance map. Assessor pass 2 diffs the transcript against it. Resolution routes both ways: "true, not on my CV" → new `claims.yaml` entry → tailoring plan; "drift under pressure" → walk-back list → CV edit. **Interview mode is the only stage that can falsify a claim the CV judges already passed**, because the judges read a page and the page does not stammer.

**Two patterns worth naming explicitly, both from `[3]`:**

- **Restate the fence locally at the field that invites the violation.** A rule stated once at the top of a fifty-instruction prompt is not where the model will be standing when it writes the dangerous field. Restate the no-fabrication rule at exactly three places: the KEYWORD-INSERT step, the mock interviewer's question generation (a question premise the CV does not support is a fabrication the *candidate* then repeats), and the shortlist's `why_matched` field.
- **An instruction the model reliably disobeys is deleted and the rule moves to code.** `[3]` removed "do not use Markdown fences" after the model opened with ```` ```json ```` three runs out of three — because the instruction bought nothing and *"an instruction that is reliably disobeyed also teaches nothing about the ones around it."* Audit for this after the first real runs.

---

## F. WHAT NOT TO BUILD

| Rejected | Reason |
|---|---|
| Interview-probability bands, match percentages, any 0–100 score | Owner's decision. Independently: collapsing met/partial/missing into one number needs a weight for a partial match, and any weight would be invented `[3]`. The old skill's two coverage formulas over the same must-have list always disagreed and were managed by prose `[1]`. |
| A fourth CV judge ("technical lead") | ~70% redundant with the hiring manager's `evidence` and `credibility` dimensions; a fourth judge produces correlated verdicts — paying a subagent to agree `[2 §1.1]`. **Salvage:** the project-realism table (`项目 / 可信证据 / 可疑点 / 面试追问`) and the "top 5 questions that will break you" become mock-interview question seeds. |
| A debate-moderator agent | Structurally redundant with the orchestrator's existing merge step, and it inserts a serialisation point into a loop whose whole speed argument is parallelism. Its `至少修正 1 个初始判断` quota instructs the model to change something whether or not anything is wrong — and directly contradicts its own `不要为了形式而辩论` two lines later `[2 §1.5]`. **Salvage:** the ATS-vs-recruiter conditional becomes one `if` in the merge step. |
| An industry/trend analyst | Forbids itself real data and then asks for a 6–12 month forecast. `[2]`'s own anti-hallucination file bans 市场薪资 and 招聘政策 but not "this field is growing" — the analyst sits in the one gap it leaves open `[2 §1.4]`. |
| A salary negotiator as a judge | Negotiation is post-offer, outside a skill that ends at interview-ready. Bolting it onto the review loop would have it evaluate a CV `[2 §1.3]`. **Salvage:** the grade-not-number doctrine (定位等级 / 筹码 / 压价风险, no figures without region+level) lands in the market conventions table where it belongs. |
| A PDF packager / `md_to_pdf.py` | Renderers exist with a LaTeX fallback that ships the `.tex` `[2 §8]`. |
| `INPUT_OPTIONS.md`-style file-slot ceremony | Exists because the source product is a copy-paste bundle with no filesystem agency. A Claude Code skill reads paths the user names `[2 §8]`. **Salvage:** the input-accuracy ordering (copyable text > PDF/DOCX > clear screenshot > blurry) as one line. |
| `resume_rewrite_template.md` | A Markdown fill-in form is strictly worse than a YAML schema that renders to three formats `[2 §8]`. |
| `examples/sample_final_report.md` | Its numbers (`简历表达分 72`, `面试概率区间 25-45%`, `修改后可提升到 45-65%`) are exactly the fabricated-precision pattern being rejected. Useful only as a counter-example in evals; shipped as a template it teaches the defect `[2 §8]`. |
| Any write to any platform | Owner's decision, made mechanical: `access: read` allowlist + `check_no_write.py`. No auto-greeting, no connection request, no submission, no auto-login, no "confirm before sending" flow (a confirmation flow is a write path with a speed bump). |
| `resolveMarket` place-name pattern matcher | `[3]` documents three uncovered defect classes it cannot close without a real gazetteer, and notes a wrong market card cites nothing so it reads exactly like a right one. Asking the user deletes the class. |
| Any local keyword-scoring fallback | `[3]` removed one rather than keep it as a fallback, because a heuristic presented as career advice is worse than no answer, and lints against reintroduction. |
| 1point3acres integration | Every read command returned HTTP 403 anonymously — including the `browser: false` ones that should work `[4, measured]`; `search` is documented 需要登录. Do not code around it and do not prompt login as a workaround for a wall the site is deliberately putting up. |
| `nowcoder papers --company/--job` filters | Verified inert: `--company 139`, `--company 138`, `--job 11229` all returned byte-identical rows `[6, measured]`. Use `papers` as a company/role index only. |
| A screenshot/OCR intake pipeline | Scope creep. `[2]`'s two genuinely-new gates ("blurry/cropped screenshot", "unreadable file") do not require OCR — they require a **verdict floor**: state the read quality and emit `INSUFFICIENT EVIDENCE` rather than guessing. Build the floor, not the pipeline. |
| A fifth "career coach" mode | The 30/60/90 + roadmap is real value, but it is the *second half of assess* — what to do instead of this posting — not a mode with its own entry condition. Keep the 验收标准 and 输出物 columns; they are what stop a plan being a wish list. |
| A question bank read verbatim during a mock round | Cannot follow up on an answer it did not anticipate, and *held under probe* is the only band above ASSERTED that means anything `[6 §5b]`. Bank is seed material, audited after the round for coverage. |
| `assets/cv/template.tex` and `assets/letter/template.tex` | Dead and actively misleading: nothing loads them, both renderers assemble LaTeX inline, and both files have drifted from what is generated `[1]`. Delete. |
| README's duplicated 8-step pipeline list | A second, lower-fidelity copy that no one updates — it already omits Step 7.5 `[1]`. Point at SKILL.md. |
| Cross-session analytics, application dashboards, response-rate tracking | YAGNI, and every metric invites a number. |

---

## G. OPEN QUESTIONS

1. **What is the fifth apply-verdict level?** I chose `strong apply / worth applying / stretch / likely screen-out / blocked`, with `INSUFFICIENT EVIDENCE` as an orthogonal **refusal state** rather than a level — because a verdict scale should be ordered and "we could not read the inputs" is not a point on it. The alternative reading of the owner's instruction is that `insufficient evidence` *is* the fifth level and there is no separate `blocked`. Owner decides; it changes `consistency.py`'s verdict/effort table.
2. **Layer 1.5.** Accept `modes/*.md` as mandatory-on-entry files with gate-script backstops, or collapse everything into one SKILL.md and accept the load cost? This is the largest architectural bet in the brief.
3. **Market key set.** `[5]` ships `nl_weu` mixing NL and BE with BE thin (its own reviewer says: scope to NL or source BE), and `us_uk` bundling two very different markets. Given the CN/NL tuning, I'd propose keys `cn`, `nl`, `de`, `uk`, `us` and let `applies_when` do regional work — but that means re-scoping entries the reviewer already edited.
4. **Convention review ownership and cadence.** The table already contains entries that are stale *today*: the Shanghai 落户 notice cited is superseded by a 2026 successor and that cycle has closed for non-PhD graduates; the Dutch expat-ruling percentage has an announced change; the Dutch pay-transparency implementation status will move `[5]`. Who owns `review_by`, and does `check_conventions.py` fail the build or warn?
5. **Does discovery run by default?** `[4]` explicitly could not verify whether read commands leave server-side traces — whether `linkedin inbox`, `boss chatlist`/`chatmsg` mark anything read. Opt-in per session, or on by default with a stated caveat?
6. **Keep the Japan rirekisho fork?** It is well-backstopped and cheap, but it is outside the CN/NL/Western-Europe tuning, and its age-computation rule has to live inline.
7. **Bilingual policy per artifact.** Conventions are bilingual by design. Is `fit-assessment.md` bilingual, or does it follow the user's language while the CV follows the market's?
8. **`interview` mode without an application.** Does a user with a real interview but no package in this skill get a degraded path, and does the cheatsheet need a `scheduled:` date to prioritise?
9. **Which `[6]` shape facts are shippable.** 交叉面, the generic US loop sequence, most role-family loop structures, and all the Meta/Google/OpenAI round compositions are `[S]` (search-summary only, largely from commercial prep sites with an incentive to sound authoritative). The Amazon and MIT figures and the UK Civil Service scale are primary-source. Ship the `[S]` material with a visible source-quality label, or cut it?
10. **Eval rebuild.** The recorded baseline is one run per configuration despite metadata claiming three, only two of five evals have a baseline arm, and one baseline assertion is logged as non-discriminating `[1]`. Iteration-2 needs new evals covering discover (blocked adapter, blank-title rows, zero-vs-403) and interview (a candidate who drifts into an unsourced fact). Who runs them, and against which model?
11. **Where does `answer-bank.md` live long-term?** It is the one artifact that compounds *across applications* — arguably it belongs at `~/.claude/job-profiles/<name>/answer-bank.md`, not inside a single workspace. That makes it a shared-spine object, and it then needs its own immutability rule.

---

## H. RISK REGISTER — the silent failures

Each row is a way this skill passes its own checks while shipping something wrong.

| # | Silent failure | Why nothing reports it | Countermeasure |
|---|---|---|---|
| 1 | **A platform returns nothing and the model fills the gap** with plausible listings | A fabricated shortlist is internally consistent, well-formatted, and every field is the right shape | Every row's `source_id` must appear verbatim in `raw/`; `check_shortlist.py` greps the capture. Shortfall requires a written reason. Degraded output is a **named artifact** (direction-level shortlist) with a **pre-filled disclosure form whose answers are hardcoded to "no"**, so concealment requires an active overwrite. |
| 2 | **All adapters died and the run says "no matching jobs"** | Found-nothing and everything-failed produce the same shape | `check_shortlist.py` reads `journal.jsonl` and refuses the "no results" wording unless at least one adapter exited 0. This is the owner's own empty-workflow trap, made mechanical. |
| 3 | **Exit 0 with blank fields presented as "no data"** | Every status check passes; the JSON is well-formed | Assert the identifying field non-empty on returned rows, not the exit code. Follow the detail command. **Never** infer absence from blank fields — the rows existed `[4, measured on indeed]`. |
| 4 | **A market convention is out of date** | A wrong market card cites nothing the reader can check, so it reads exactly like a right one | `retrieved` + `review_by` on every entry, both linted; the rendered card shows the retrieval date; the digit ban makes numeric staleness structurally impossible for figures, and entries say "look up the current amount at <official page>" instead of carrying one. **Named residual:** a convention can be *substantively wrong* rather than numerically stale, and nothing detects that. Only human review does. |
| 5 | **zh says something stronger than en** | Both render; no reader sees both | `[5]`'s review found this repeatedly — `被要求` where the source says 引导, `根本不含` where the statute only bounds the entitlement, `所有对外发布的` where the law says "designated". Partial countermeasure: `check_conventions.py` requires both fields and flags length ratios outside a band and modal-verb asymmetry (`must`/`必须` present in one language only). **Named residual:** semantic drift is not scriptable; the review step is human. |
| 6 | **An `unverified` note disclaims a claim the rendered text makes anyway** | The `unverified` field ships alongside the table but is not what the user reads | `[5]`'s single cross-cutting finding, hit in four entries. Countermeasure: `unverified` items must name the field they disclaim, and `check_conventions.py` warns on keyword overlap between an `unverified` note and `text_en`/`text_zh`. Rule inline: **every claim the unverified section disclaims must be removed from the rendered text, not footnoted.** |
| 7 | **The mock interview coaches a misrepresentation** | The candidate agrees, the answer bank looks vetted, and the fabrication surfaces in the real room | Never write an answer; name the gap, don't fill it. No leading questions and no question premises the CV does not support. **Pass 1 assessor never sees `claims.yaml`**, so it cannot credit an unsaid fact. Pass 2 exists only to diff. `check_mock.py` fails on an answer-bank entry without a `source:` line. An undefendable claim goes on the walk-back list, not into rehearsal. |
| 8 | **The assessment reads as precise because it is numeric** | "8 of 11" carries the authority of arithmetic | Every one of the 11 is printed with its evidence refs, so the denominator is auditable and the reader can disagree with a row. `lint_no_prediction.py` bans percentages and invented scales. The verdict is a word. The disclaimer sits under the counts. `count_coverage.py` is the only count-producing path, so there is no second number to conflict with. |
| 9 | **Judges re-run on a stale render** | The verdict block is valid, and it is self-confirming — the judges return the feedback that was supposedly just addressed | Hash every file at dispatch into `judge-round-<n>.json`; `check_render_freshness.py` voids the round on mismatch. |
| 10 | **The Cluster-1 interlock does not fire** | The CV renders perfectly and every judge is told to calibrate to the market it was handed | Normalized matching plus a loud warning on unknown-market-with-personal-data, plus a fixture test over realistic spellings. The failing input is not hypothetical: the eval scenario literally says `United States (Los Angeles, CA)`. |
| 11 | **A reference file is never read** | The build succeeds, the lint passes, the output is quietly wrong | Measured precedent inside this very skill: a run recorded *"`references/motivation-letter.md` was not read explicitly"* and then filed a finding that the skill lacked guidance it had chosen not to read. Countermeasures: layer-1 self-check naming every file; gate scripts requiring artifact fields only that file defines; the highest-consequence content moved inline. **Named residual, honestly:** `references/candidate-situations.md` playbooks and the cluster-conventions content are only partially backstopped. |
| 12 | **A gate "passes" because it never ran** | A skipped script produces no output, which looks like a clean script | Gates write a receipt (`{gate, input_hashes, verdict, ts}`) into `journal.jsonl`; the mode's completion message must quote it; downstream gates require upstream receipts. |
| 13 | **A write command runs** | A greeting sent is unrecoverable and leaves no local trace | Allowlist derived from the tool's own `access:` metadata, plus a post-hoc journal scan. No confirmation-flow escape hatch. |
| 14 | **A scraped 面经 describes the wrong country's process for the right company** | The company name matches and the content is real | Country rule + date stamp + shape-only-past-12-months. Verified live on ASML and Philips `[6]`. Also filter advertising: two of the posts pulled in the probe were commercial pitches dressed as 面经. |
| 15 | **A check cries wolf and gets ignored** | A gate someone learns to skip stops working on the run that mattered | `[3]`'s hardest-won lesson, twice over: a secret-scan regex that matched no real key *and* fired on the repo's own fixture, and an orphan detector that reported live keys. Every check's tests pin the quiet case as hard as the firing one, and every check that cannot decide reports rather than repairs — code can see that two fields disagree, it cannot see which one is right, and picking silently replaces a visible contradiction with an invisible guess. |
