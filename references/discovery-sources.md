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
| `indeed-cloudflare-challenge` | `Indeed served a Cloudflare challenge page` | yes, 2026-09-08 |
| `http-429-rate-limited` | `HTTP 429` | no |
| `verify-human-en` | `(?i)verify (that )?you are (a )?human` | no |
| `unusual-traffic-en` | `(?i)unusual traffic` | no |
| `captcha-interstitial` | `(?i)captcha` | no |
| `slider-verification-cn` | `滑块` | no |
| `security-verification-cn` | `安全验证` | no |
| `risk-control-cn` | `风控` | no |
| `too-frequent-cn` | `操作过于频繁` | no |
| `access-restricted-cn` | `访问受限` | no |

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
