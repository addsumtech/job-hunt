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
actually executed; `false` means only the help text was read. An entry upgraded
later carries its own `runtime_verified_on` date, because the header date does
not travel with it — read that field before trusting the flag. Do not
upgrade a `false` to a `true` without running the command and recording the
output, and say in the notes which flags the run did **not** exercise: the flag
means a command ran, never that every documented option works.

For newer evidence, see [2026-09-12 live source acceptance](../docs/testing/live-sources-2026-09-12.md).
It records the tested job/interview sources, including partial LinkedIn results.
The catalogue retains dated 2026-08-09 measurements for the remaining adapters;
it is not a current access guarantee. Sources removed from product scope are
not retained as available adapters.

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
    detail_command: "opencli 51job detail <jobId> --url <captured-url>"
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
      This adapter is US-only — its origin is hardcoded to www.indeed.com — but
      Indeed is not. Outside the US the country site (cn/nl/de/uk.indeed.com) is
      read through the diagnosed browser route, never through this adapter; see
      the region table in modes/discover.md. Expect a bot-block there: a
      Cloudflare challenge on 2026-09-08, HTTP 403 to a plain HEAD on 2026-09-20.
  linkedin:
    domain: www.linkedin.com
    login_state_2026_08_09: logged_in
    runtime_verified: true
    runtime_verified_on: "2026-09-20"
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
      RUN 2026-09-20 (opencli 1.8.6, logged in, Netherlands round): `search` 4
      invocations, 2 exit 0 returning 8 and 10 rows with every documented column
      populated and `title` non-empty on all 18; `job-detail` 13 invocations, 8
      exit 0 returning title/company/location/workplace_type/job_type/listed/
      applicants/apply_url/description. The row `url` is a direct
      /jobs/view/<id> link, while a detail capture's own `url` is the
      /jobs/search/?currentJobId=<id> form — take the posting link from the
      search row. Exercised --location, --date-posted month, --start, --limit,
      --window background, -f json. NOT exercised, so still help-text only:
      --experience-level, --job-type, --date-posted week, --details, and every
      value enum (there is none, per the note above).
      The other 4 searches and 5 detail reads failed as `transport` with
      "Pre-navigation to https://www.linkedin.com failed: Navigation rejected."
      This is intermittent, NOT a platform stop: it is deliberately absent from
      risk-control-signals.yaml, and one bounded retry recovered 1 of 3 retried
      calls. Treat it under network-recovery.md, retry once, and if it persists
      record the row as detail_unavailable with the captured failure rather than
      stopping the site.
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
| `indeed-cloudflare-challenge` | `Indeed served a Cloudflare challenge page` | yes, 2026-09-08 |
| `http-429-rate-limited` | `HTTP 429` | no |
| `verify-human-en` | See the expanded human-verification patterns below | no |
| `unusual-traffic-en` | `(?i)unusual traffic` | no |
| `captcha-interstitial` | `(?i)captcha` | no |
| `slider-verification-cn` | `滑块` | no |
| `security-verification-cn` | `安全验证` | no |
| `risk-control-cn` | `风控` | no |
| `too-frequent-cn` | `操作过于频繁` | no |
| `access-restricted-cn` | `访问受限` | no |

Human-verification patterns also cover a check that stays loading. These are
recognition regressions, not claims that every variant was emitted by a live
adapter's stderr. The Upwork waiting message was observed in a live page trace.

```text
verify-human-en: (?i)(verify|verifying|confirm) (that )?you are (a )?human
human-verification-cn: (?:验证|确认)(?:您|你)(?:是否)?是(?:真人|人类)|(?:正在|请|需要).{0,8}(?:真人验证|人机验证)
human-verification-pending: (?i)验证成功[。.!！\s]*正在等待|verification successful[.!\s]*waiting for|checking your browser
```

A guest-group denial such as `抱歉，您所在的用户组(游客)无法进行此操作`
is a login request, even if cached auth metadata says logged in. It is classified
separately from a CAPTCHA; hand off to the user and resume only after confirmation.

**2026-09-08 runtime check (OpenCLI 1.8.7):** an Indeed search for Python in
New York returned exit 1, empty stdout and `Indeed served a Cloudflare challenge
page`. The raw stderr is retained in `scripts/tests/fixtures/indeed-cloudflare.err`.
A separate 51job Python search in Beijing returned structured `error.code:
ANTI_BOT` and `51job returned HTML (likely Aliyun WAF slider). Refresh browser
session.` The classifier uses that machine code as a stop (`opencli-anti-bot`),
not as a reason to refresh/retry. The raw error is in
`scripts/tests/fixtures/51job-anti-bot.err`. Both sites were stopped.

Searches for London/Berlin and live Indeed job details were
**not completed**. Other patterns remain unverified unless explicitly marked.

The installed adapter's help labels search as `US site`; its `INDEED_ORIGIN`
constant is `https://www.indeed.com` and it has no country/domain option. Calling
its URL builder locally with New York, London, Berlin and Amsterdam changes only
`l=`, not the origin. That confirms the adapter's configured origin; it does not
prove which jobs the live site would return for those locations. The older London
→ Ohio result elsewhere in this repo remains a dated observation, not a result
reproduced by this check.

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
