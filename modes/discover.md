# Mode: discover — 找什么

Loaded unconditionally on entering discover mode. Read it in full before the first
adapter call.

**What this mode does:** turn a search intent into a shortlist of real, retrieved
job listings with a provisional verdict on each. **What it does not do:** it never
chains into `apply`. Thirty rows do not become thirty CVs; the whole point of
ranking a shortlist is to let a person choose.

**The shortlist is written in the user's language** — spec §10: CV 跟市场走，评估 /
shortlist / 面试复盘**跟用户走**. A Dutch- or US-market round run by someone who
writes to you in English produces an English `shortlist.md`, and that is ordinary
output, not an edge case. Every literal `check_shortlist.py` requires the document
to contain follows that language: the English and Chinese examples are below,
and Japanese, Korean and Spanish templates are in
[report-localization.md](../references/report-localization.md). The gate accepts
all five. **Pick one and stay in it.** A document with English prose and Chinese
furniture is worse than either language alone: it reads to the user as a bug, and
no gate can report it, because both halves are individually correct.

Native report anchors (use the complete templates and real answers from the
language contract; no invented retrieval or login state):

| Element | ja | ko | es |
|---|---|---|---|
| Provisional stamp | 求人カードの情報だけに基づく暫定判断 | 채용 카드 정보만을 바탕으로 한 잠정 판단 | valoración provisional basada únicamente en las fichas |
| Login disclosure | 今回のセッションでログイン済み： | 이번 세션에서 로그인함: | Sesión iniciada en esta ejecución: |
| Adapter result | Adapter の返却結果： | Adapter 반환 결과: | Respuesta del adaptador: |
| Retry after restriction | 制限通知後の再試行： | 제한 신호 이후 재시도: | Reintento tras una señal de restricción: |
| Control bypass | プラットフォームの制御の回避： | 플랫폼 통제 우회: | Elusión de controles de la plataforma: |
| Real postings obtained | 実際の求人の取得： | 실제 채용 공고 확보: | Ofertas reales obtenidas: |
| Degraded output | 代替出力の種類： | 대체 출력 유형: | Tipo de salida alternativa: |

## Supplementary public research

Use `references/supplementary-sources.md` when official web/news, GitHub,
WeChat articles or relevant role discussions can fill a concrete
career evidence gap. It defines provider availability checks, source quality and
source-selection records. These sources supplement
formal posting evidence; they do not replace it or run automatically on every task.

## On entering this mode — before anything else

```bash
python3 scripts/enter_mode.py --workspace <ws> --mode discover \
    --because "<why discover, in one line, from what the user asked>"
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
                             (English round: §0 Sources and read quality,
                              §0.1 Trigger, §0.2 Disclosure)
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
employer_types: ["国企", "外企"]     # cn only — see below; omit for other markets
```

**`employer_types` is asked for a `cn` round and omitted everywhere else.** In the
Chinese market the same job title means different work, hours, pay structure and
security depending on whether the employer is a 大型私企, a 中小型私企, a 国企 or
a 外企, and the adapter hands you that distinction for free: 51job returns
`companyType` and `companySize` on every card, so a stated preference can be
applied to real rows instead of guessed at. Ask it as a multi-select alongside
the other preferences, and treat "no preference" as a legitimate answer rather
than as all four.

It is a preference, not a filter: a row outside the chosen types is not dropped
silently — it is ranked below and its `why_matched` says which type it is. The
user asked for a lean, not a wall.

**Every field here is asked, never inferred.** Reading a salary floor off a past
payslip, an avoid-list off a CV, or a target market off the language someone happens
to be typing in produces a file that looks like the user's preferences and is not —
and because it is reused across every later round, one wrong inference quietly
steers months of searching.

- **First run** (the file does not exist): ask the questions above, in the
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

## Before Step 0 — region, then platforms, then the login hand-off

**This order is not a suggestion, and getting it wrong costs the round.** Measured
2026-09-06: a round opened by confirming a stored `search-preferences.yaml` whose
`target_market` was `nl`, bundling the region into a yes/no confirmation of eight
other fields. The user actually wanted China. Everything downstream — which
adapters exist, which languages the queries run in, which convention table
applies, whether the stored salary floor means anything — had to be redone.

Run these three in order, before the trigger reason and before `brief.yaml`.

### 1. Ask the region, as options, on its own

Never infer it. Not from the language the user is typing in, not from their
profile's `meta.target_market`, and not from a stored preference file — a stored
`target_market` is shown for confirmation, and the region for THIS round is asked
whether or not one exists. `brief.locations` is the round's own narrowing;
`search-preferences.target_market` is the durable setting, and the two can
legitimately differ.

Offer concrete regions rather than a blank question — United States, United
Kingdom, Netherlands / Europe, China, Middle East, and whatever else fits what
you know about them. Then ask cities inside it, because an adapter's location
parameter takes a city, not a country.

**If the round's region is a different market than the stored `target_market`,
re-ask the whole preferences file**, not just the market: a salary floor in EUR
and an avoid-list entry reading "roles requiring fluent Dutch" mean nothing in
Shanghai. Back the old file up before rewriting it — the user may be exploring,
not switching, and a durable preference file silently overwritten is a job search
the user has to reconstruct from memory.

### 2. Say which platforms that region actually has

Before any search, tell the user which adapters serve their region and which need
a login. This is what lets them fix a missing session BEFORE the round runs
rather than after it.

This table is about ONE thing: which adapters return **job listings**, i.e. rows
that can become `shortlist.yaml` entries. Everything else about any adapter —
flags, pagination, measured login state, identity field — lives in
`references/discovery-sources.md`, which is the source of truth and must be read
before calling anything outside SKILL.md's four.

| region | job listings, no login | job listings, needs a login | do not use for listings |
|---|---|---|---|
| United States | `indeed` (its native site) | `linkedin` | — |
| China | `51job` | `boss` | — |
| Netherlands · Germany · UK · rest of Europe | — | `linkedin` | **`indeed`** — it resolves locations against a US gazetteer and answers a London search with Ohio |
| Middle East · anywhere with no convention table | — | `linkedin` | `target_market: other`; say plainly there is no convention data for this market |

**A site being absent from the "job listings" columns does not make it useless,
and saying it has "no search command" is wrong.** `nowcoder` and `1point3acres`
both have one; `discovery-sources.md` records what those searches actually
return, and the distinction it draws is the one that matters — nowcoder is
"an interview-experience (面经) source, not a job source", and 1point3acres is a
forum. They inform a round and they do not produce shortlist rows, because a
forum thread is not a posting with a `source_id` a row can be traced to.

For a Chinese campus round (`seniority: new_grad`) both are worth naming to the
user as places to read 面经 and 内推 threads alongside the shortlist — that is a
pointer, not a row. `maimai`'s only read command is `search-talents`, the
recruiter side, so it has nothing to offer a candidate. `upwork` is freelance
work rather than employment.

Get this wrong in the other direction and the cost is real: told that nowcoder
"has no job-search command", a 校招 round skips the site most relevant to it.

### 3. Hand the login to the user, then wait

`opencli <site> login` is a **write** command. `references/source-policy.md` puts
it on the Red list: it is handed to the user to run and never run here, and there
is no confirm-then-send path because a confirmation flow is a write path with a
speed bump.

So say it plainly and wait:

> `boss` needs a browser session. Run `opencli boss login` yourself, finish the
> login in the browser, and tell me when it's done — then I can search there.
> It is a logged-in adapter, which `source-policy.md` puts in the yellow tier:
> the search runs inside your own session, and account risk is not zero.

**`opencli auth status` can be confidently wrong, so re-probe before you believe
it.** Measured 2026-09-06: the quick probe reported `boss` as `not_logged_in`
while the session was live — `opencli boss login` answered `already_logged_in`
and `opencli auth status --site boss --full` returned `logged_in`. This is worse
than the `unknown` case the probe section below describes, because the answer
looks decided. **Before telling a user to log into a site the probe called
`not_logged_in`, re-probe that site with `--full`.** A round that skips a site on
a false negative reports a thin market that is not thin: in the measured round,
`boss` turned out to hold the three best-matched postings of the day, and it was
one wrong probe away from never being searched.

Only once the region is fixed, the platforms are named, and the sessions the
round needs are actually live, go on to the trigger reason and `brief.yaml`.

## Step 0 — state the trigger reason BEFORE searching

Say why this search is happening, then write it into `brief.yaml` as
`trigger_reason` and into `shortlist.md` under `## §0.1 触发原因` (English round:
`## §0.1 Trigger`; the gate keys on the language-agnostic `§0.1`). Stating it
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

**`target_count` is asked, not chosen for the user.** It is the one brief field
that is purely their preference — how many rows they want to look at — and it sits
outside `search-preferences.yaml`, whose eight fields carry the "asked, never
inferred" rule. That rule applies here for the same reason: a number picked on
their behalf silently sets how much of the market they get shown. Ask it with the
brief, in the same pass as the trigger reason.

`target_count` and `max_rows_per_round` are different things: the first is the goal,
the second is the politeness cap from `references/source-policy.md`. Falling short of
`target_count` requires a written `shortfall_reason` in `shortlist.yaml`
(`SHORTFALL_NO_REASON`). **Never pad the count.**

## Retrieval backend — OpenCLI first; one-way web-access fallback

Before using OpenCLI for the first Indeed or 51job read, follow `references/opencli-compat.md`:
check and automatically apply only the known version/hash-matched local repairs
with `scripts/opencli_compat.py`. Do not overwrite custom edits or force a patch
onto another version. This local preparation performs no site reads and cannot
reset a site's refusal. Browser fallback can use the site's own search box;
it is not limited to Google or other search engines.

Before Step 1, run `opencli doctor` with a bounded timeout and inspect the
adapter's documented read help. **OpenCLI is the initial backend:** when its
read adapter and connection are usable, perform the round through OpenCLI; do
not choose web-access for convenience or richer-looking results. Only a
diagnosed `cli_missing`, `bridge_disconnected`, or `unsupported_extraction`
permits the one-way fallback in `references/browser-fallback.md` to an available
web-access skill. On that path skip OpenCLI-only auth/help commands and retain
the same source selection, query, page, row, detail and disclosure rules. There
is no web-access-to-OpenCLI fallback for the same round: if web-access is also
unavailable after the initial OpenCLI capability diagnosis, disclose the gap.
Do not stop merely because an optional adapter executable is absent.

### Local browser bridge versus a sandbox boundary

`BROWSER_CONNECT`, `Failed to start opencli daemon`, or an `EPERM` listener error
on `127.0.0.1:19825` can mean the **agent runner** cannot reach the user's local
OpenCLI bridge, not that OpenCLI or the site is unavailable. Before selecting
web-access, preserve the failed transport output and run one bounded `opencli
doctor` through the platform's approved host-local or unsandboxed execution path
(ask for the required permission). This is a local capability probe; it does not
read a job site. Save both diagnostic outputs under `raw/`.

- If that host-level doctor reports both daemon and extension connected, repeat
  the same single bounded, read-only OpenCLI call through that path. Keep the
  earlier `transport` record; this is recovery from an execution boundary, not a
  retry after a site refusal.
- If the host-level doctor still cannot connect, diagnose `bridge_disconnected`
  and take the one-way web-access fallback. Do not infer the cause from the
  extension's visual “running” indicator alone.
- `EADDRINUSE` while starting a daemon means a process already owns the port:
  inspect with `opencli doctor` through the host path. Do not kill a process,
  change the port, reinstall, update, or restart the user's browser as a search
  workaround.

This exception is only for a local bridge failure observed before the site returned
a refusal. It never permits a different execution path to bypass captcha, login,
403/429, or a platform limit.

For another generic timeout, blank extraction, or unclassified transport error,
follow `references/network-recovery.md` before recording an OpenCLI fallback
reason. Use `references/daily-browser.md` only after the documented OpenCLI
diagnosis permits web-access; it selects the browser route and preserves the
same source, query, page, row, detail, and disclosure rules. Site login remains
a user action when a real login wall is encountered.

Browser captures use `scripts/record_browser_capture.py`, `browser_call` journal
records and `extraction_method: browser_page`. They are not adapter responses.
Both `check_no_write.py` and `check_shortlist.py` consume these records. A captcha,
403, login wall or platform limit is a **site refusal**, not a backend-capability
failure: it stops the site across tools for this round. Never try web-access to
route around an OpenCLI site refusal, or vice versa.
A stop is a pause for [user recovery](../references/user-recovery.md), not a
reason to abandon the requested search. Explain the actual obstacle and wait for
the user's explicit completion/continue reply before a new linked round.

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

**`indeed` serves the US site only, and its `--location` is inert outside the US.**
It does not fail on a non-US place — it resolves the name against a US gazetteer
and returns US rows: `opencli indeed search … --location "London"` came back with
every row in Columbus, Ohio (London, OH), exit 0, `classification: ok`; `--location
"Manchester, United Kingdom"` returned California and New York (measured
2026-08-16). So **for a `uk`, `nl` or `de` market, `indeed` is not the no-login
default** — use `linkedin` and record in `§0` that `indeed` was skipped, with this
reason. If you use it anyway, read every returned `location` before it becomes a
row, and never let it produce a "no results" conclusion: the adapter searched a
different country, which is not the same as the country having no jobs. Downstream,
`check_shortlist.py` warns with `WARN_ROW_OUTSIDE_BRIEF_MARKET` on a row whose
location names a country outside `brief.markets` — but an empty shortlist has no
rows to warn about, so the only thing standing between a UK user and "there are no
London backend roles" is this paragraph, read before the call.

## Step 3 — generate queries in BOTH languages

Generate the keyword set in English **and** in the market's local language, and run
both. **English-only keywords miss local-language postings**, which is not a
rounding error in NL/DE/CN: a Dutch employer posting "Onderzoeker beeldreconstructie"
or a Chinese one posting "图像重建算法工程师" is invisible to an English-only query,
and the resulting empty result looks exactly like "there are no such jobs".

Record every query string in `brief.yaml.target_titles` so the round is reproducible.

**Split the row budget across the query set BEFORE the first call — the cap is per
site per round, not per query.** `max_rows_per_round` is 25 and a single
`--limit 25` spends all of it, so a round that runs its first query at full limit
has no budget left for the other nine and for the second language. That is not
hypothetical: a measured round declared ten queries, ran one English query at
`--limit 25`, and never issued the Dutch-language or medical-imaging queries at
all — two of the three tracks the user asked for, missing from a shortlist that
read like an answer to the whole brief.

Divide first: with N queries and a cap of R rows, run each at roughly `R // N`,
rounding up for the tracks the user named first and down for the speculative
ones. Two or three well-aimed queries at 8-12 rows each beat one at 25. If the
brief genuinely needs more coverage than one round's cap allows, that is a second
round with its own slug — never a raised cap.

**Then order them: most specific first, broadest last.** Dividing the budget is
not enough on its own, because a broad query fills whatever budget it is given
and a narrow one usually does not. Run `MRI reconstruction` before
`medical imaging AI` before `machine learning engineer`, and hand the leftover
rows back to the broad query at the end.

The reason is what each query is worth to THIS candidate, not how many rows it
returns. A specialist term is where their credential is a hard qualification and
where few applicants compete; the generic term returns what every ML engineer in
the market already sees. Measured: a round ran `machine learning engineer` first,
at the full cap, and never reached `MRI reconstruction` at position six — the
most expensive rows in the round were spent on its least informative query, and
the candidate's own specialism went unsearched.

So `brief.target_titles` is written in run order, specific to broad, and the
order is part of the plan rather than the sequence they were thought of in.

`check_shortlist.py` reports a declared query that appears in no adapter call as
`QUERIES_DECLARED_NOT_RUN`, so under-searching is now visible rather than
silent — but it fires at the END, after the calls are spent. The arithmetic above
is what stops the round from getting there.

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
| `not_logged_in` | login wall, and auth says the session is absent or unknown | cross-check auth; hand `opencli <site> login` **to the user** — it is a write command. Pause for [user recovery](../references/user-recovery.md); no read retry while logged out. **Do not treat `strategy: public` as evidence that no login is needed** — 1point3acres' public-strategy `forum` still 403s. |
| `no_auth_adapter` | login wall on a site with no login concept | no CLI login command is available. Pause and ask the user to inspect the browser page; do not invent a login command or infer a missing session. |
| `platform_limit` | a stop-signal from `references/risk-control-signals.yaml`, or a refusal while auth says logged in | **立即停止。不重试、不改参数重试、不绕过。** Pause this source, not the whole task. Explain whether it is verification, rate limiting or an unknown refusal; follow [user recovery](../references/user-recovery.md) before offering degraded output. |
| `transport` | unrecognised failure, or exit 0 with unparsable stdout | Check the actual selected connection (`opencli doctor` when using OpenCLI), then follow [bounded network recovery](../references/network-recovery.md). Distinguish a disconnected browser from a site loading or route failure; a timeout alone is not evidence that a VPN caused it. |

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
  url: https://jobs.51job.com/xian-gxjs/173198362.html   # non-empty direct posting URL returned by the source; tracking params stripped
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

**Three fields anchor the row to the capture — and `title` is deliberately not one
of them.** Verifying `source_id` alone let a row keep a real jobId and invent
title, company, location, salary and `raw_text`: an identifier is one field to
copy. So `check_shortlist.py` also requires

- `raw_text` — the card text **copied**, not summarised and not translated. It is
  checked in pieces against `raw/<site>-*.json` (a hand-joined card is never one
  contiguous substring of the JSON) and most of it must be found there, or
  `RAW_TEXT_NOT_IN_RAW` fires and names the parts that were not. Your own words
  belong in `why_matched`. Normalising the title above is expected output, and is
  exactly why the title is not the anchored field.
- `id` — exactly `<site>-<source_id>`, or `BAD_ROW_ID`. It is the only thing tying
  the id a reader quotes back to the capture the row was traced to.

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
- in `shortlist.md`, the words **「基于卡片信息的初判」** — English round:
  **"provisional, from card data only"** — on the section that renders the rows
  (Japanese, Korean and Spanish use the matching stamp from
  [report-localization.md](../references/report-localization.md))
  (`MD_MISSING_PROVISIONAL_STAMP`; any supported spelling satisfies it, and case does
  not matter). A YAML boolean is not a disclosure — nobody reading the round ever
  sees it, and `shortlist.md` is what they read.

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
(English round: **no detail fetched**) in `shortlist.md`; the user can name one to
fetch anyway, which is recorded in
`shortlist.yaml.detail_fetch_exceptions` with a reason. `check_shortlist.py` enforces
this as `DETAIL_FETCH_OUT_OF_BAND`. This cap is where detail fan-out stops being a
crawl, and it is the mechanism that keeps this mode inside the yellow tier of
`references/source-policy.md`.

**A fetch that DEMOTES its own row is the normal case, and the gate cannot see
it.** `DETAIL_FETCH_OUT_OF_BAND` compares the fetch against the row's FINAL
verdict, while the decision to fetch was made on the verdict before it. Measured:
a row was fetched as `worth_applying`, its description read "Fluent in English and
Dutch", and it became `blocked` — the fetch was in band when it was made, and it
is the only reason that row's language requirement is known rather than guessed.
Record it in `detail_fetch_exceptions` with that as the reason. The gate's remedy
text says "if the user named this row", which is the other cause; this one is
yours to write down.

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
    detail_command: "opencli 51job detail <jobId> --url <captured-url>"
    raw_files: ["raw/51job-1.json"]
rows: [...]
```

`identity_field` and `detail_command` for any adapter outside the four inlined in
SKILL.md come from `references/discovery-sources.md`. There is no other source for
them, which is why `SOURCE_REPORT_MISSING` is that file's backstop.

`raw_files` entries are **workspace-relative and keep the `raw/` prefix** —
`raw/51job-1.json`, never the bare basename. One spelling, so that a name which
resolves is a name that was captured; `SOURCE_REPORT_RAW_PATH` fires on the other
one rather than letting a correct file report as a missing capture.

`shortlist.md` carries `## §0 来源与读取质量`, `## §0.1 触发原因`, and — when the run
is degraded — `## §0.2 披露`. The section that lists the rows carries the stamp in
its own heading, e.g. `## §1 候选（全部为基于卡片信息的初判 · provisional）`, and each
row shows its band, its `effort`, and a Markdown link using that row's direct
`url` (e.g. `[打开职位](https://...)`). A category, search, company, or source page
is not a replacement for the posting link. Rows below the top three are labelled
**未取详情**.

An English round writes the same document with the same numbering: `## §0 Sources
and read quality`, `## §0.1 Trigger`, `## §0.2 Disclosure`, a row section headed
e.g. `## §1 Candidates (all provisional, from card data only)`, and rows below the
top three labelled **no detail fetched**. The `§n` markers are the same in both —
they are what the gate keys on, so they are never translated away.

## Degraded output — when no real postings could be retrieved

First offer the recovery hand-off above. While waiting, preserve partial results
and say the search is paused; do not present this fallback as the completed task.
Use it when the user declines recovery, cannot regain access, or asks to proceed
with the remaining sources. A user saying “done, continue” after the hand-off
requests a new linked round; follow the recovery reference rather than retrying
inside this stopped round.

Emit a **direction-level shortlist** (3-5 directions), each with: 目标方向 ·
检索词 · 建议筛选条件 · 为何比原 JD 更稳 · 要避开的标题与信号 · 手动收集优先序 —
in English: direction · search terms · suggested filters · why it is steadier than
the original JD · titles and signals to avoid · manual-collection priority.
It has no `rows:`, so it cannot claim a posting exists.

Then the disclosure block, verbatim, in `shortlist.md` — one language, all six
lines, in whichever language the rest of the document is in:

```text
本次会话已登录：        <是|否|不适用—无 auth adapter>
Adapter 返回：          <逐字错误信息>
收到限制信号后重试：    否
绕过任何平台控制：      否
取得真实岗位：          否
降级输出类型：          方向级 shortlist
```

```text
Logged in this session:         <yes|no|n/a — no auth adapter>
Adapter returned:               <verbatim error message>
Retried after a stop signal:    no
Bypassed any platform control:  no
Obtained real postings:         no
Degraded output type:           direction-level shortlist
```

The last four answers ship **pre-filled as 否 / no**, in both blocks. That is the
design: concealing a retry or a bypass has to be an active overwrite, not an
omission — which is why the pre-filled answer matters as much as the label, and why
`check_shortlist.py` checks the answer of every spelling it finds, not just the
Chinese one, or the Japanese, Korean or Spanish template. It fires
`DEGRADED_WITHOUT_DISCLOSURE` when the block is absent in all supported
languages and `DISCLOSURE_INCOMPLETE` when a line is missing or an answer is blank.

And the wording rule: **"没有匹配" is a claim, and it needs a receipt.** All-adapters-
failed and genuinely-found-nothing produce the identical shape, so
`EMPTY_RESULT_UNSUPPORTED` fires unless at least one adapter exited 0. If every
adapter died, say *that*, not "there are no jobs".

## Step 10 — gates, and cite the receipts

```bash
python3 scripts/check_no_write.py       --workspace .
python3 scripts/lint_no_prediction.py   --workspace .
python3 scripts/check_shortlist.py      --workspace .
```

All three must exit 0. **This mode may not claim success without a passing receipt for
each in `journal.jsonl`** — a skipped script produces no output, and that looks
exactly like a clean one.

| Finding | What it means | What to do |
|---|---|---|
| `NO_MODE_ENTRY` | `journal.jsonl` has no `mode_entry` for discover | run `scripts/enter_mode.py --workspace <ws> --mode discover` and read this file — it was not loaded |
| `MODE_FILE_CHANGED` | this file changed after the run entered the mode | what you read is not what is on disk. Re-enter and re-read. |
| `SOURCE_ID_NOT_IN_RAW` | a row's identifier is in no capture from that site | delete the row **from `shortlist.yaml` AND from `shortlist.md`**. It was not retrieved. Do not "fix" it by editing `raw/`. |
| `RAW_TEXT_NOT_IN_RAW` | most of a row's card text is in no capture from that site | copy the card text the adapter returned. If you cannot, the row was not retrieved — delete it **from both files**. Paraphrase belongs in `why_matched`. |
| `NO_RAW_TEXT` | a row has an empty `raw_text` | recover the card text, or drop the row; nothing else ties its claims to the capture |
| `BAD_ROW_ID` | a row's `id` is not `<site>-<source_id>` | rewrite the id. It is the handle a reader quotes, and it must name the posting the row was traced to. |
| `SOURCE_REPORT_RAW_PATH` | a `raw_files` entry is not a `raw/…` workspace-relative path | write `raw/<site>-<n>.json`. One spelling for one file. |
| `WARN_ROW_OUTSIDE_BRIEF_MARKET` | *(warning, does not fail)* a row's location names a country outside `brief.markets` | check the adapter's geography — see `indeed` in Step 2. Drop the row, or keep it and say why the warning is a false alarm. |
| `URL_NOT_FROM_ADAPTER` | the URL was assembled, not returned | replace it with the adapter's URL or drop the field. If you delete the row, delete it **from both files**. |
| `MD_ROW_NOT_IN_SHORTLIST` | `shortlist.md` renders a posting URL that is in no `shortlist.yaml` row | the .md is what the user acts on. Either the row belongs in the yaml and was traced, or it was retrieved by nothing — delete it from the .md. |
| `MISSING_POSTING_URL` / `BAD_POSTING_URL` / `MD_POSTING_URL_MISSING` | a row has no usable direct URL, or the user-facing list omits it | retain only rows whose captured posting URL is absolute HTTP(S), and render that same URL as a Markdown link in §1. |
| `COMPANY_NOT_IN_RAW` / `SALARY_NOT_IN_RAW` | a row's employer or pay contradicts the capture it cites | copy what the adapter returned, or leave the field empty. Salary is the field a reader acts on hardest and the one most easily invented from a blank. |
| `PAGES_ABOVE_CAP` / `ROWS_ABOVE_CAP` | the round actually exceeded a cap `brief.yaml` declares | the cap is compared to the run, not only to the ceiling. Both-language queries on one page are one page. |
| `DUPLICATE_SOURCE_ID` | one retrieved posting appears as two rows | delete the duplicate; de-duplication removes rows, nothing adds them |
| `SOURCE_REPORT_COUNT_MISMATCH` | the source report claims more than the receipts recorded | the receipts are right. Never reconcile by editing `raw/` or the journal. |
| `EMPTY_RESULT_UNSUPPORTED` | "no results" wording with no adapter that exited 0 | rewrite as "every adapter failed", and emit the disclosure block |
| `DEGRADED_WITHOUT_DISCLOSURE` | degraded run with no disclosure block in a supported report language | add the matching template, check and fill every answer |
| `MD_MISSING_PROVISIONAL_STAMP` | `shortlist.md` renders rows without 「基于卡片信息的初判」 / "provisional, from card data only" | add the stamp, in the round's own language, to the section heading. The YAML flag is not a disclosure. |
| `DETAIL_FETCH_OUT_OF_BAND` | a detail fetch below the top three verdicts | remove it, or record a named exception with a reason |
| `CAP_MISSING` / `CAP_ABOVE_CEILING` | `brief.yaml`'s round caps are absent or raised | read `references/source-policy.md`; the caps are its enforceable half |
| `SHORTFALL_NO_REASON` | fewer rows than `target_count`, no reason written | write the reason. Never pad. |
| `SOURCE_REPORT_CONTRADICTS_JOURNAL` | `sources:` disagrees with the receipts | the receipts are right; fix the report |
| `WRITE_COMMAND` | a write command was journaled | stop. Tell the user exactly what ran. It cannot be undone. |
| `UNKNOWN_ACCESS` | a command's access could not be resolved | save `opencli <site> --help -f yaml` into `raw/opencli-help/` and re-run |

**Deleting a row means deleting it from both files.** `shortlist.yaml` is what
the provenance checks read; `shortlist.md` is what the user reads and acts on.
Removing a fabricated row from the machine file alone moves it out of the
checked artifact and leaves it in the read one — the remediation becomes the
cover-up. `MD_ROW_NOT_IN_SHORTLIST` reports it if you forget.

## Hand the artifacts over — `deliver.py`, not a sentence in the final message

A workspace under `~/.claude/job-profiles/` is where the skill works, and it is
not where a person looks. Nobody browses a dotfile directory, and a path pasted
into a chat message is gone the moment the session scrolls. So the last step of
every mode is a command, not a claim:

```bash
python3 scripts/deliver.py --workspace <ws>
```

Delivery uses two child folders: `简历/` for `简历.docx`, `简历.pdf` and other requested application documents; `报告/` for `求职建议报告.pdf` and its editable text. Filenames never include the employer, role or internal workspace slug.

Author `report.md` for **every consultation**, answering the client's actual
question in their language: conclusion, supporting evidence, relevant career
constraints or facts still to confirm, and practical next steps. Tool defects,
adapter errors, tests, developer diagnostics and internal review logs belong only
in the private workspace, never in this client report. Do not copy an internal
`completion.md` into it. A general question still receives a PDF reply report.

After authoring `report.md`, run `lint_no_prediction.py --workspace <ws>`.
Delivery also refuses prediction language in the report.

Run `deliver.py` as the last step. It requires `report.md` and a verified report
PDF and copies only the report and requested CV/application documents into
`~/Downloads/<workspace-name>/`. For multiple workspaces serving one consultation,
pass the **same `--to <consultation-folder>`** each time so the report and CV stay
together. Quote that folder and its client files in the reply. The workspace and
all audit evidence remain in their original location.

PDF verification checks both recovered text and actual painted glyph IDs. A
missing or refused PDF means incomplete delivery (exit 2); repair the cause and
rerun before declaring completion. `--no-pdf` is only for an explicit user format
exception. A cover letter is provided on demand; it is not the domestic default.
Do not automatically start a mock interview or another mode.


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
- [ ] Every row's `raw_text` is the card text **copied** from the capture, and its
      `id` is `<site>-<source_id>`.
- [ ] `indeed` not used as the no-login default for a non-US market, and if it was
      used, every returned `location` read against `brief.markets` before the row
      was kept — the US site answers a London search with Ohio.
- [ ] Every row carries `provisional: true` **and** `shortlist.md` carries
      「基于卡片信息的初判」 / "provisional, from card data only", or the native
      Japanese, Korean or Spanish stamp in [report-localization.md](../references/report-localization.md); no verdict copied
      into an assessment.
- [ ] `shortlist.md` is in **one** language — the user's — end to end: section
      names, the stamp, the 未取详情 / no detail fetched labels and the disclosure
      block, with no furniture left in the other one.
- [ ] Every rendered candidate has a clickable direct posting link copied from
      its `url` field. A search/category/source page is not a job link.
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

**Voice.** The shortlist is a document the user reads, not a dump. `SKILL.md`, "How this skill writes to the user", governs its prose — every row's provenance visible, what was not searched said out loud, no closing offer to help further.
