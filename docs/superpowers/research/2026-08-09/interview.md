# Mock-Interview Module — Design Brief

**Researched 2026-08-09.** Every factual claim below carries a provenance tag:

| Tag | Meaning |
|---|---|
| `[C]` | A command I ran in this session; output quoted or summarised from what came back |
| `[F]` | A page I fetched with WebFetch and read |
| `[S]` | A WebSearch *result summary* only — I did **not** open the underlying page. Weaker. Treat as a lead, not a fact |
| `[U]` | Could not source. Collected under the UNVERIFIED heading at the end |

Sections marked **RECOMMENDATION** are my design proposal, not a report of anything observed.

---

## 0. What already exists (read, not redesigned)

- `/Users/donghanglyu/.claude/skills/job-application/references/interview-prep.md` (40 lines) — produces `<workspace>/interview-brief.md`: three parts (tailored-claim defence with source facts, honest-gap framings, carried-over judge questions). Its own §Rules line 38: *"Keep it thin. This is a defense brief generated from data you already hold — not a mock-interview module. A page or less."* Line 39: *"Flag the over-reach signal. If preparing the brief surfaces a claim the candidate cannot truthfully defend, treat it as a tailoring error and walk the claim back on the CV."*
- `agents/hiring-manager.md` (166 lines) — a **one-shot** judge. Line 21: inputs are *"pasted directly below this prompt when you are dispatched"*; line 97: *"You MUST end your response with EXACTLY the following block."* No dialogue contract. Rubric: 5 dimensions × 1–5 + a deterministic PASS bar (lines 54–62). Emits `SUPPLEMENTARY_QUESTIONS_FOR_CANDIDATE`, `STANDOUT_SIGNAL`, `LEVELING`.
- `references/role-families.md` (107 lines) — 9 CV families + a fallback. It is a **CV-layout** document: `meta.section_order`, `meta.headings`, "evidence currency" per family. It says nothing about interviews. Extending it means adding an *interview shape* axis, not rewriting the layout recipes.
- `SKILL.md` line 22 — the load-bearing rule; line 154 — the actor stays inline *"because it already holds full context and is the only party that can ask the candidate honest supplementary questions"*; line 95–101 — workspace at `~/.claude/job-profiles/<name>/applications/<company>-<role>-<YYYY-MM-DD>/`.

The module I design below **adds a step after Step 8**, consumes `interview-brief.md` rather than replacing it, and writes back into it.

---

## 1. Interview shapes by market

### 1a. Mainland China (tech / campus)

Verified pipeline `[F` chengxuchu.com/3-interview_guide `]`:

> 简历初筛 → 笔试 → 技术一面 → 技术二面 → 技术三面 → HR面 → offer

with elimination possible at every stage, and 简历初筛 described as the highest-elimination stage.

Round contents `[F]`:

| Round | Content | Notes |
|---|---|---|
| 笔试 | Coding assessment, "most require ACM-style input/output format" | Pre-interview gate; not present in most Western loops |
| 技术一面 | *"基础知识 + 项目 + 开放性问题 + 手撕算法"* — i.e. 八股文 + project + open question + live-coded algorithm. Problems "easy-to-medium difficulty classics" | The four-part composition is the key structural fact |
| 技术二面 | Project depth and architecture; interviewer explores implementation details and challenges faced | |
| 技术三面 | Often leadership-level; broader technical topics, research direction, career plans | |
| HR面 | Career goals, work location, values; "conversational" | |

Duration: *"30-45 minutes per round"* `[F]`. Formats: 一对一 (standard), 一对多 (multiple interviewers, one candidate — *"common at state enterprises and banks"*), 多对一 (群面 / group discussion scored by one interviewer) `[F]`.

**交叉面** `[S` — zhihu.com/question/280591490, jianshu, dachangrenshi via search summary; I did not open these `]`: only at large tech companies; interviewers of the *same level from a different business department*; no fixed number of rounds — the company decides case-by-case; purpose is to give the main interviewer an outside read and reduce cognitive bias; used when a candidate is uncertain or the role is important.

Design consequences for the module:
- **八股文 is a distinct register**, not a topic. It is rapid rote recall of canonical fundamentals. Simulating it as three thoughtful discussion questions misses the experience entirely — the pressure is *volume and speed*, and a candidate who can answer any one of them can still fail the round.
- **手撕代码 is unrunnable in this module** — a terminal agent with no shared editor cannot reproduce a live-coded round under a watching interviewer. Say so; do not fake it. What the module *can* do is the verbal half: "state your approach before you code", "what's the complexity", "what breaks on an empty input".
- **交叉面 and HR面 are separately scored gates** the candidate will not expect if they have only prepared US-style. Rehearsing 离职原因 / 期望薪资 / 职级 / base城市 is worth a round of its own (all four appeared verbatim in real posts I pulled — see §3).

### 1b. United States (tech)

Amazon, published `[F` aboutamazon.com/news/workplace/amazon-interview-guide `]` — named steps: **Application → Initial screening → (STAR prep) → Interview loop → Post-interview and follow-up**. Loop is *"four to six intensive interviews lasting 45-60 minutes each."* Bar Raiser: *"an objective interviewer from outside the hiring team who ensures Amazon's high hiring standards are maintained."* Pronoun guidance quoted verbatim: *"use 'I' statements... Instead of saying 'we improved customer satisfaction,' say 'I implemented a new feedback system that increased customer satisfaction scores by 40%.'"*

Google `[F` rework.withgoogle.com guide `]`: *"Google often documents with illustrative examples what a poor, borderline, solid, and outstanding answer would cover for attributes the questions are each designed to test"*, and interviewers *"take detailed notes of applicant responses, so they can later be reviewed throughout the hiring process."*

`[S]` The generic US shape (recruiter screen → technical phone → onsite loop of coding + system design + behavioural, sometimes a take-home) is consistent across the ML/DS/PM search summaries in §2 but I did not find a single primary source that states it as a canonical sequence. Treat the *sequence* as `[S]`, the *Amazon and Google specifics above* as `[F]`.

Design consequence: the US loop is the one shape where **each round has a named owner and a named signal**, and where a "no" from one interviewer is discussed rather than automatic. Rehearsing "which signal is this round for" is itself a preparation move that has no analogue in the Chinese loop.

### 1c. UK / EU public and academic sector

This is the best-documented market and the one with a **real published rubric** — which matters enormously for §4.

**UK Civil Service Success Profiles** `[F` gov.uk/government/publications/success-profiles `]`: five elements, quoted verbatim —

1. **Behaviours** — *"the actions and activities that people do which result in effective performance in a job"*
2. **Strengths** — *"the things we do regularly, do well and that motivate us"*
3. **Ability** — *"the aptitude or potential to perform to the required standard"*
4. **Experience** — *"the knowledge or mastery of an activity or subject gained through involvement in or exposure to it"*
5. **Technical** — *"the demonstration of specific professional skills, knowledge or qualifications"*

Nine named behaviours `[F` gov.uk/.../success-profiles-civil-service-behaviours `]`: Seeing the big picture; Changing and improving; Making effective decisions; Leadership; Communicating and influencing; Working together; Developing self and others; Managing a quality service; Delivering at pace. Defined across **7 grade groupings** (AA/AO, EO, HEO/SEO, G7/G6, Deputy Director, Director, Director General). Notable format fact `[F]`: the document gives **positive examples only** — *"Examples of [behaviour name] at [grade level] are when you:"* — it does not publish ineffective-behaviour counter-indicators.

**The scoring scale**, verbatim `[F` copfs.gov.uk/about-copfs/careers/how-your-application-is-assessed-success-profiles `]`:

| Score | Label | Descriptor (verbatim) |
|---|---|---|
| 1 | Not Demonstrated | "No positive evidence and/ or substantial negative evidence demonstrated" |
| 2 | Minimal Demonstration | "Limited positive evidence and/ or mainly negative evidence demonstrated" |
| 3 | Moderate Demonstration | "Moderate positive evidence but some negative evidence demonstrated" |
| 4 | Acceptable Demonstration | "Adequate positive evidence and any negative evidence would not cause concern" |
| 5 | Good Demonstration | "Substantial positive evidence of the behaviour" |
| 6 | Strong Demonstration | "Substantial positive evidence; includes some evidence of exceeding expectations at this level" |
| 7 | Outstanding Demonstration | "The evidence provided wholly exceeds expectation at this level" |

Pass bar `[F]`: *"A minimum score of 4 is required across all behaviours. However, candidates may score a single 3 where all other behaviour scores are high."*

**This is the single most important find in the whole brief** and §4 is built on it — see below.

**STAR**, UK National Careers Service definitions verbatim `[F` nationalcareers.service.gov.uk/careers-advice/interview-advice/the-star-method `]`: Situation = *"the situation you had to deal with"*; Task = *"the task you were given to do"*; Action = *"the action you took"*; Result = *"what happened as a result of your action **and what you learned from the experience**"*. Advice: *"keep examples short and to the point"* and *"try to get your points across in a conversational way so as not to appear too rehearsed."*

**UK academic panels** `[S` — Sheffield / Manchester / UCL / Birkbeck HR pages via search summary; the Sheffield page is now behind a CAS login and I could not open it `]`: candidates scored numerically against each **person-specification** criterion; the person spec is *"the only basis for scoring"*; marks allocated per criterion decided at the outset; panel of three or more typically including a senior departmental member, a senior manager independent of the department, and an HR representative; panel reaches consensus per criterion; applicants not meeting all essential criteria should not be shortlisted.

**EU institutions / EPSO** `[S]`: 8 general competencies, each composed of observable elements called **"anchors"**. The 2024 list reported by eutraining.eu is: critical thinking/analysing/creative problem-solving; decision-making & getting results; information management; self-management; working together; learning as a skill; communication; intrapreneurship. `[S]` also reports the 2010-era Assessment Centre and its oral tests have ceased, replaced by a written test. I fetched the eu-careers landing page `[F]` which confirms the framework exists and that some competencies are assessed by EPSO at selection and others by the institutions at recruitment, but the competency list itself is only in PDFs I could not decode (7MB binary).

Design consequence: **for a Success-Profiles posting, the module should not invent a rubric.** The employer publishes one. Score against the *named behaviours in that specific advert*, at the *grade level in that advert*, using the *published 1–7 wording* — and label it as *the employer's scale being used as a checklist*, never as a prediction of the panel's actual mark. This is the one case where a number is honest, because the number is a quotation.

### 1d. Netherlands / Germany private sector

**Netherlands** `[F` dutchreview.com/expat/work/job-interviews-netherlands `]`: *"in the Netherlands it is common that you'll need to survive and thrive through multiple interviews"* — typically hiring manager, then the potential team, then possibly leadership. *"The Dutch are known for saying exactly what they think — no niceties needed"*; they will ask directly about anything questionable on the CV. Straight answers backed by data and concrete results are expected; vague answers are penalised. *"Dutch workplaces are often non-hierarchical and place high value on cooperation"* — teamwork evidence is load-bearing.

**STARR** `[F` carrieretijger.nl/.../gesprekstechnieken/star `]` — the Dutch variant, verbatim: **S**ituatie, **T**aak, **A**ctie, **R**esultaat, plus a second **R** = **reflectie** (*what did you learn, how would you do it differently, what feedback did you get*), and **STARRT** adding **T** = *transfer/toepassen* — how you will apply the lesson to future work, demonstrating *"leervermogen en aanpassingsvermogen."* Rationale quoted: *"gedrag uit het recente verleden is de beste voorspeller van toekomstig gedrag."*

`[S]` Additional NL process facts from search summaries of iamexpat / expatica / hays / RefugeeHelp, which I did not open: a case **opdracht** (take-home assignment, a few days, often 2–3 tasks) may come before the first or before the second interview; psychometric / assessment testing scales with role seniority, sometimes via external consultants; the process closes with an **arbeidsvoorwaardengesprek** — a distinct employment-conditions conversation covering salary, hours, vakantiegeld, thirteenth month, travel reimbursement — held *after* the hiring decision and *before* contract signature.

**Germany** `[F` stepstone.de/magazin/artikel/vorstellungsgespraech-ablauf-und-optimale-vorbereitung `]`: five phases — greeting/small talk, application questions and self-presentation, company presentation, candidate questions, farewell. Duration **45–60 minutes**. Attendees vary: *"Je nach Größe und Struktur des Unternehmens kommt dein\*e Gesprächspartner\*in aus der Geschäftsführung, der Personalabteilung oder der Fachabteilung."* Legally impermissible questions, listed: family planning, sexual orientation, health, religion, political beliefs, union membership, financial situation — and the candidate *"muss nicht ausweichen oder [sich] rechtfertigen. Eine klare, höfliche Abgrenzung... reicht völlig aus."*

`[F` roberthalf.com/de/de/insights/karriereentwicklung/ablauf `]` corroborates the five phases and gives 30–60 minutes, with the caveat *"kein Jobinterview gleicht dem anderen."*

Design consequences:
- The **NL reflectie step is a scored element**, not politeness. A candidate who gives a perfect STAR and stops has given an incomplete Dutch answer. This is a real, cheap, high-value coaching point that a US-calibrated mock would never surface.
- The **arbeidsvoorwaardengesprek is a separate rehearsable event** with its own vocabulary. Folding it into "salary negotiation at the end of the final round" mis-times it.
- The **German prohibited-question list is a rehearsal item in the opposite direction**: the candidate needs a prepared *polite refusal*, not a prepared answer. That is a distinct answer type the module should generate for DE/AT/CH targets.

---

## 2. Interview shapes by role family — extending `role-families.md`

**RECOMMENDATION on structure:** do not duplicate the nine CV families. `role-families.md` is organised by *evidence currency for a CV*. Interviews want a different axis: **what artifact the candidate must produce live**. Add a second table to a new `references/interview-shapes.md`, cross-referenced from the CV families, keyed on the live artifact:

| Live artifact demanded | Families | Can this module simulate it? |
|---|---|---|
| Working code, watched | SWE, ML eng, quant | **Partly** — verbal half only. See below |
| A design argued aloud | SWE (system design), ML (ML system design), data (experiment design) | **Yes** — this is text-native and the module's strongest mode |
| A prepared talk | research scientist, academic, senior clinical, some PM | **Yes, via file** — candidate writes/outlines, agent plays the Q&A |
| A defended past artifact | research scientist, PhD track, legal, creative | **Yes** — deep-dive on a real paper/repo/matter the candidate names |
| A live role-play with a counterpart | sales, clinical comms, teaching, hospitality, consulting | **Yes** — the agent plays the counterpart |
| Structured evidence against named criteria | UK/EU public sector, NHS, academic, EU institutions | **Yes** — and here the criteria are *published*, so the rubric is not invented |
| Rote recall at speed | China tech 八股文, some finance/licensing | **Yes** — but must be run as volume, not as three questions |

Per-family detail I could source:

**Software / ML engineering.** `[S` Exponent, InterviewKickstart, IGotAnOffer, techinterview.org — commercial prep sites, none opened `]`: three stages (pre-screen → technical screen → onsite loop); loop typically DSA + ML system design + ML domain deep-dive + behavioural, commonly 4–6 rounds. `[S]` reports Meta introduced an AI-assisted coding round in 2025 (solve/debug in CoderPad with an AI model available). I would not put a claim that specific into a skill on `[S]` alone.

**Research scientist / PhD-track — industry.** `[S` interviewquery.com, sundeepteki.org, techinterview.org `]`: an OpenAI research-scientist loop reported as a 45-minute **Research Deep-Dive** on the candidate's own recent work; a two-part research discussion where a paper is sent in advance and discussed for *idea, method, findings, advantages and limitations*; an ML-debugging round (fix bugs in a given model, add features); a team-lead behavioural round. DeepMind reported to have a distinct paper-discussion round and a math/theory round, with a slow committee (3–4 weeks) and heavy weight on publication record. All of this is prep-site sourced and should be marked as such in the skill.

**Research scientist / PhD-track — academic.** `[F` capd.mit.edu/resources/academic-interviews-faculty-positions `]`, verbatim: first round is *"an initial screening interview with members of the search committee"*, **"20-40 minutes"**, by phone or video, covering research experience, teaching philosophy, funding plans, industry partnerships. Campus visit **"1-2 days"** with search committee, departmental faculty, chair, students, postdocs, administrators, plus tour and meals. **Job talk "45 minutes -1 hour"** on past accomplishments and future research goals. Teaching demo sometimes requested — *"prepare a lecture on a given topic, or to submit a teaching video."* **Chalk talk**: *"informal discussion about your future research plans"*, whiteboard, address feasibility questions. `[S` MIT EECS CommLab, Harvard postdoc affairs `]` add: the talk must show you are a good researcher, a good teacher, and a good colleague — *the Q&A is where "good colleague" is judged*; plan the talk for ~75% of the slot.

Design consequence: the *meal and the hallway* are part of the academic loop and are scored informally. A module that simulates only the job talk Q&A misses the failure mode that actually sinks candidates.

**Data / analytics.** `[S` Exponent, InterviewQuery, DataLemur, hackingthecaseinterview `]`: 4–6 rounds of 45–60 min built from five blocks — recruiter screen, SQL/technical screen, statistics & experimentation, product-sense / business case, behavioural. SQL screens reported as 4–5 questions in 30–45 min covering joins, aggregations, window functions. Case archetypes reported: *metric drop/spike investigation* and *measure the impact of a feature*. A/B testing questions including two-sided-marketplace network effects. Take-homes common at startups; a named example is a 24–48h dataset challenge with a presentation.

**Product.** `[S` Exponent, IGotAnOffer, Lenny's Newsletter, nazuk.substack `]`: question families are product sense, product strategy, analytical/execution, behavioural, plus technical/AI-fluency where relevant. Reported loops: Meta IC — two phone screens (product sense; product execution/analytical) then onsite with another product sense, another analytical, a behavioural/leadership; Google L6 — recruiter screen, one PM screen, four-round final (behavioural, product design, analytics, strategy); Amazon PM — 4–5 rounds *almost entirely behavioural*, grounded in Leadership Principles, interviewers deliberately overlapping on the most important LPs.

**Clinical and other regulated professions.** `[S` NHS England / HEE values-based-recruitment PDFs and an NCBI paper; I could not open the HEE PDFs — one WebFetch failed on a classifier error `]`: **Multiple Mini Interviews (MMI)** — structured questions per station; reliability rises with the number of stations; each scenario assesses *"generic and station-specific values or attributes for example: communication skills, kindness, compassion and empathy, respect for the individual, privacy and dignity, advocacy, decision-making, team working and integrity."* Scenarios are deliberately **not clinical** — *"they are not designed to measure clinical knowledge."* Assessors get *"a series of standardised probing questions."* Interviewers have no prior knowledge of candidates, to dilute examiner bias. **Scoring: three domains per station on a five-point scale, giving a station range of 3–15.**

Design consequence: for regulated professions the interview is a *values* instrument, and the candidate's instinct to demonstrate clinical knowledge is the classic failure. The module should say so explicitly.

**Sales.** `[S` 30mpc.com, Procore careers, Databricks sales-interview-prep PDF, yardstick.team `]`: reported stages — recruiter screen (30 min), hiring manager (1 hr), full panel (2–3 × 1 hr), presentation (1 hr), references, offer. The distinctive artifact is a **mock discovery call / role-play**: candidate given a one-pager on a fictional company, runs a ~20–30 minute discovery call, then a 10–30 minute debrief. Reported evaluation criteria: does the candidate lead with the prospect's problem or with features; do they understand the value proposition; can they pivot on an objection; do they **close for a next step** rather than just ending the call.

Design consequence: sales is the family where **this module is at its best**, because the deliverable is pure dialogue and the failure modes are structural and observable ("you never asked for a next step" is a fact about the transcript).

**Non-technical / the rest.** `role-families.md §10` already has the right move — one question that resolves the layout. **RECOMMENDATION:** mirror it for interviews with a different single question: *"In your field, what does the employer make you do live — talk, demonstrate, be scored against written criteria, or be role-played at?"* That answer picks a row from the artifact table above, and everything else follows.

---

## 3. Real question sources — `opencli`

### 3a. What the adapters expose (verified)

`[C]` `opencli nowcoder --help -f yaml` → `command_count: 18`. Seventeen `access: read`, one `access: write` (`login`).
`[C]` `opencli 1point3acres --help -f yaml` → `command_count: 11`. Ten `access: read`, one `access: write` (`login`).
`[C]` `opencli auth status -f yaml` → `1point3acres: status: not_logged_in, logged_in: false`; `nowcoder: status: unknown, checked: skipped, error: "quickCheck not implemented; use --full to run whoami"`.

I ran no write command and attempted no login.

**nowcoder — commands that could pull real, company-specific interview questions, as actually tested:**

| Command | Login? | What it actually returned | Verdict |
|---|---|---|---|
| `search <query>` | **No** `[C]` | `rank, title, author, school, content, id`. The `content` field contains **real numbered interview questions**, truncated with `...` elisions. `search "字节跳动 算法 面经" --limit 3` returned e.g. *"1.扣项目细节…2.介绍下多路复用 3.算法：最长有效括号，你的时间、空间复杂度是多少"*, *"2. 为什么需要预训练ESMM？3. 多目标双塔粗排模型的理解？4. 粗排样本怎么构造？"* | **The single highest-value command.** This is the workhorse |
| `detail <id>` | **No** `[C]` | Full untruncated `content`, plus `title, author, school, likes, comments, views, location`, and — critically — **`time` as an ISO timestamp**. One call returned a full round-by-round timeline (`6.29 1面`… `7.13 …沟通薪资`) plus a per-round question list | **Required second step.** Never quote a question from a `search` row; the row is elided |
| `papers` | **No** `[C]` | Only `rank, title, company, practitioners` — i.e. the *titles* of question sets (`2025年-字节跳动-算法/AI岗高频面试题`), **not the questions**. **Its documented `--company` and `--job` filters do not work**: `--company 139`, `--company 138`, and `--job 11229` all returned byte-identical rows | Useful only as a company/role *index*. Do not build on the filters |
| `experience` | **Yes** `[C]` | `Error: need login` | Unusable in current auth state |
| `practice` | Probably | `[]` (empty array) with `--job 11226 --limit 5` | Unusable |
| `trending`, `topics`, `hot`, `recommend`, `creators` | No `[C]` for trending/topics | Post titles + ids + heat. `trending` returned e.g. *"腾讯微信后端一面，问麻了！！！"* | Discovery only — feed ids into `detail` |
| `companies`, `jobs` | No `[C]` | `companies` → `百度/139, 腾讯/138, 杭州银行/1509`. `jobs` → 13 career ids incl. `11226 软件开发`, `11229 产品/项目/运营`, `143882 生物医疗`, `11230 金融`, `11264 教育/科研` | ID lookup for the (broken) `papers` filters and for `suggest` |
| `salary`, `referral`, `notifications`, `whoami`, `suggest` | mixed | Not relevant to question mining (`notifications`/`whoami` are account-scoped) | — |

Two more verified quirks: **`--type post` breaks `search`** — `search "产品经理 面经 结构化" --type post` returned `[]` while the same query family with default `--type all` returned three good hits `[C]`. And `search` has **no date parameter** at all (see help output, lines 457–465).

**1point3acres — currently unusable:**

`[C]` Every read command I tried returned HTTP 403 from an anonymous request:
- `1point3acres forums --filter 面经` → `HTTP 403 Forbidden from https://www.1point3acres.com/bbs/forum.php`
- `1point3acres hot --limit 3` → `HTTP 403 Forbidden from .../forum.php?mod=guide&view=hot`
- `1point3acres digest --limit 3` → `HTTP 403 Forbidden from .../forum.php?mod=guide&view=digest`

These are the `browser: false` commands — the ones that *should* work anonymously. The adapter's own help additionally documents `search` as **需要登录** and `notifications` as **需要登录**. Useful metadata that survives the 403: `forum <fid>` documents **fid 145 = 海外面经**, 198 = 海外职位内推, 27 = 研究生申请; `thread <tid>` is `browser: false` with `--page`, `--limit` (floors) and `--contentLimit` (default 400 chars, min 50).

**Conclusion for the skill:** treat 1point3acres as **not available** today. Do not code around the 403, and do not prompt the user to log in as a workaround for a wall the site is deliberately putting up — surface it as "the North-American archive is unreachable; I'll use generation plus the Chinese archive where relevant" and move on. nowcoder is available anonymously for exactly two commands that matter: **`search` → `detail`**.

### 3b. Coverage limits (verified, and they bite)

`[C]` I tested the archives against Dutch employers, since that is this user's market:

- `nowcoder search "ASML 面试"` returned three real posts — but all describe the **China entity's** process: `ASML-Brion软件开发实习二面`, `Asml 睿初C++软开面经分享` with a timeline of `10月31日 线下宣讲 笔试 → 11-16 二面 → 11-22 hr面（电话面）→ 11-22 hrbp面（电话面）`, and `ASML 计算光刻-产品 现场笔试`.
- `nowcoder search "Philips 飞利浦 面试"` likewise returned China-entity content (`笔试 + 单面`, 宣讲会, plus an employer-review post about vacation days).

So: **the same employer has a different loop in a different country, and the archive silently gives you the wrong one.** An 宣讲会-and-笔试 pipeline is not the ASML Veldhoven loop. This is the most dangerous failure mode in the whole source, because the company name matches and the content is real.

The archives are also structurally narrow: nowcoder is China + campus + tech-heavy (its own `jobs` list is 13 categories, 4 of them engineering `[C]`), 1point3acres is North-American tech. Neither covers UK/EU public sector, clinical, trades, teaching, legal, or hospitality — i.e. six of the nine families in `role-families.md`.

### 3c. Staleness — verified, not hypothetical

`[C]` Three post ids returned by searches I ran on **2026-08-09**, with their `detail` timestamps:

| id | title | `time` | Age |
|---|---|---|---|
| `057523b2ca9d…` | 字节后端社招面经 | `2026-08-06T11:06:49` | 3 days |
| `ce23c4da4205…` | 字节推荐算法一面面经 | `2026-08-03T11:12:22` | 6 days |
| `022b19c99c24…` | 搜狐产品经理面经 | `2025-10-28T09:30:27` | ~9.5 months |

One result set, an order-of-magnitude spread in age, no way to filter. Separately, every `papers` title `[C]` is prefixed `2025年` — a year old, presented without any recency signal.

And the archive contains **advertising dressed as 面经**: one `search` hit `[C]` opened *"27届秋招即将开始…可以了解下算法项目辅导，帮助你在简历中增加高含金量的对口项目"* before listing its questions; another `[C]` was a `校招小喇叭` post whose "content" was a recruitment-service pitch with a contact email. A naive pipeline pastes those into a mock interview as if they were questions.

### 3d. The design question — scraped vs generated

**RECOMMENDATION: scraped material sets the SHAPE; generated material sets the CONTENT. They are not competing sources of the same thing.**

**Use a scraped item when the thing you need is a fact about the employer's process that you cannot derive from the posting:**
- Named rituals that don't exist elsewhere — 交叉面, HRBP面, Bar Raiser, 宣讲会, a 群面, a specific take-home. Getting the *shape* wrong is the expensive surprise; a candidate who is ready for four rounds and gets six is rattled in a way that no amount of question practice fixes.
- Round count, order, timeline, and who is in the room. These are cheap to corroborate across posts and — crucially — **they never enter the candidate's mouth as a claim**, so they cannot become a fabrication.
- The register. That 手撕代码 comes at the *end* of a 一面 that opened with 八股文 is a fact about pacing you will not generate.
- Repeating house questions where they genuinely exist (a canonical 八股文 set for a stack; a company's standard product-sense prompt).

**Use a generated question when the question must be about *this candidate*:**
- Every question derived from the interview-readiness brief. *"You wrote that you cut deploy time 40% — how did you measure that?"* exists nowhere in any archive, and it is the highest-value question this module can ask, because it is the one that catches an over-tailoring the three CV judges passed.
- Any role or market the archives don't cover — verified above, that is most of them.
- Coverage: a generated set can be built to hit every must-have in `posting.yaml`. An archive hits whatever one anonymous person happened to remember.
- Follow-ups. An archive gives you a first question and never a third.

**Failure modes of scraped:**
1. **Stale, invisibly.** Verified above: 3 days and 9.5 months in the same result set, no date filter on `search`.
2. **Wrong entity, same name.** Verified above with ASML and Philips. The most dangerous one, because nothing looks wrong.
3. **Survivorship and selection bias.** 面经 are written by people who chose to write. Skewed toward campus hires, toward people who passed, and toward dramatic rejections.
4. **Single unverifiable source.** One person's recollection of a conversation, often written days later, sometimes reconstructed. There is no second witness.
5. **Advertising contamination.** Verified above — two of the posts I pulled were commercial pitches.
6. **Truncation.** `search`'s `content` is elided; questions read out of a search row are fragments. Always `detail`.
7. **It can carry an answer with it.** A 面经 that includes the poster's own answer is a script. Handing that to a candidate is the exact thing §6 forbids.
8. **Access legitimacy.** 1point3acres returns 403 anonymously and documents `search` as 需要登录. Respect that.

**Failure modes of generated:**
1. **Defaults to a US loop for every market.** Left alone, a model will give a Dutch public-health researcher a system-design round.
2. **Too fair.** It asks the question the CV is prepared for. Real interviewers ask the awkward one, and follow up on the answer that wobbled.
3. **Register collapse.** It will render 八股文 as three thoughtful discussion questions, which is not the experience.
4. **False premises smuggled into the question.** *"When you led that team of twelve…"* when the CV says four. The candidate accepts the premise, and now the fabrication is in *their* transcript. This is a real honesty risk and needs its own check (§6 tripwire).

**Concrete rules that fall out — paste-ready:**

```
Every scraped item is (a) opened with `detail` for untruncated text, (b) stamped with
its `time` in the question log, and (c) shown to the candidate with that date.
Anything older than ~12 months may be used for SHAPE (round count, order, ritual names)
but never quoted as a specific technical question.
Never use a scraped item whose company entity is in a different country from the posting
unless the post itself names that country.
Never paste a scraped post's ANSWER to the candidate — questions only.
If the adapter returns 403 or "need login", report the source as unavailable and
generate instead. Do not log in to work around it.
```

---

## 4. Honest scoring

### 4a. What real rubrics actually do

The finding that resolves this whole section: **the best published rubrics do not score the candidate. They score the evidence.** Look again at the verbatim Civil Service scale `[F` COPFS `]`:

> 1 — "No positive evidence and/ or substantial negative evidence demonstrated"
> 4 — "Adequate positive evidence and any negative evidence would not cause concern"
> 7 — "The evidence provided wholly exceeds expectation at this level"

Every descriptor is a statement about **what appeared in the room**. Not one is a statement about the person, and not one is a prediction. That is the trick, and it is available for free.

Google does the same thing in a different register `[F` re:Work `]`: illustrative examples of what a *"poor, borderline, solid, and outstanding answer would cover"* — the object of the rating is *the answer*, and the anchor is an example of a comparable answer. And the accompanying instruction is *"take detailed notes of applicant responses"* — the note, not the number, is the deliverable.

The NHS MMI does it too `[S]`: three domains, five-point scale, station range 3–15 — and it is explicit that the stations are *"not clinically based as they are not designed to measure clinical knowledge"*, i.e. the rubric names exactly what it is and is not looking at.

`[S]` The structured-interview literature is the backing: Levashina, Hartwell, Morgeson & Campion (2014), *The Structured Employment Interview: Narrative and Quantitative Review of the Research Literature*, Personnel Psychology 67, 241–293, is reported to identify as many as **18 distinct structuring elements**, with an average of six actually used; anchored rating scales are reported to raise reliability and predictive validity and to reduce bias. I could not open the paper — the author's PDF has an expired certificate, Wiley returned 402, and Semantic Scholar returned an empty body — so treat the "18 elements / average six" figure as `[S]`.

### 4b. The rule

**RECOMMENDATION — the one-line policy:**

> **Report what was in the transcript. Never report what a human would conclude from it.**

*"Your answer to Q3 never named what changed as a result"* is a fact about a text file. *"That was a solid answer"* is a guess about a stranger's judgement, and *"you'd have a 60% chance"* is an invented number. The first is always available; the other two never are.

Corollary that matters: **the honest version is more useful anyway.** A candidate cannot act on "6/10". They can act on "in four of your six answers, the result came out as 'it went well' with no object."

### 4c. Proposed dimensions

**RECOMMENDATION.** Six dimensions. Each is decidable by reading the transcript, and each maps to a repair the candidate can make tonight.

| # | Dimension | The question it answers, purely about the transcript |
|---|---|---|
| 1 | **Instance** | Did the answer name a specific occasion, or describe a general practice? |
| 2 | **Completeness** | Which STAR/STARR elements are present? (For NL/EU targets, `R2 = reflectie` is a required element, not a bonus — `[F]` carrieretijger) |
| 3 | **Ownership** | Is the candidate's own action separable from the team's, in their own words? |
| 4 | **Outcome named** | Did the answer state what changed, in an object a listener could repeat back? |
| 5 | **Held under probe** | When asked for a detail the candidate had not volunteered, what happened? |
| 6 | **Provenance** | Does every load-bearing fact in the answer trace to the profile, `interview-brief.md`, or an earlier answer this session? |

Dimension 6 is the one no generic interview coach has, and it is the reason this module belongs inside *this* skill rather than standing alone: the readiness brief already holds the claim→source map. It is also the honesty tripwire (§6).

Two separate axes, reported as tables rather than scores:
- **Requirement coverage** — one row per must-have from `posting.yaml`: `evidenced this session` / `asked, thin` / `not asked yet`. This is the *session's* coverage, not the candidate's competence.
- **Shape coverage** — one row per round the target market/family actually runs (§1, §2): `rehearsed` / `partially` / `not attempted` / `cannot be simulated here` (手撕代码, an in-person MMI circuit, a whiteboard chalk talk).

### 4d. Proposed level descriptors

**RECOMMENDATION.** Four bands, worded as evidence-presence in the COPFS style, deliberately **not numbered** so they cannot be averaged into a fake score:

| Band | Descriptor (this is the wording to paste) |
|---|---|
| **NOT PRESENT** | Nothing in the answer addresses this. Quote the closest thing the candidate did say. |
| **ASSERTED** | The candidate stated it but gave no occasion, no object, or no detail that could be checked. ("I'm good at stakeholder management.") |
| **INSTANCED** | A specific, dated-or-datable occasion with named people, systems, or numbers that the candidate volunteered unprompted. |
| **HELD UNDER PROBE** | Instanced, **and** the candidate supplied a further concrete detail when asked for one they had not already given. |

Plus one flag that is not a band, because it is a different kind of thing:

| Flag | Descriptor |
|---|---|
| **CONTRADICTED** | The answer conflicts with the CV, with `interview-brief.md`, or with an earlier answer this session. Quote both sides. Never scored — always escalated to the walk-back list. |

Note the asymmetry with COPFS on purpose: the published scale has a 6 and a 7 for "exceeds expectations at this level", which requires knowing the level's expectations. This module does not know them. **HELD UNDER PROBE is the ceiling, and that is honest** — it says the answer survived one real dig, which is all we observed.

### 4e. Proposed defect vocabulary (closed set)

**RECOMMENDATION.** A closed tag set is what makes feedback repeatable across sessions and lets the night-before artifact be a list rather than an essay. Each tag must be emitted **with the quoted line that triggered it**. No quote, no tag.

| Tag | Fires when |
|---|---|
| `NO-INSTANCE` | A general practice, not a specific time ("I always make sure to…") |
| `NO-OUTCOME` | The answer ends without saying what changed |
| `VAGUE-OUTCOME` | An outcome word with no object ("it went really well", "it was a success") |
| `NO-ACTOR` | "We" throughout; the candidate's own action is not separable |
| `PREAMBLE-HEAVY` | More than half the answer elapses before the first action the candidate took |
| `DRIFT` | The answer finishes on a different question than the one asked |
| `NO-REFLECTION` | **NL/EU targets only** — no reflectie step (`[F]` carrieretijger: STARR/STARRT) |
| `NO-TRADEOFF` | A design or decision answer presents one option and no alternative considered |
| `JARGON-UNGLOSSED` | A domain term used undefined to an interviewer the candidate was told is non-expert |
| `NO-NEXT-STEP` | **Sales role-play only** — the call ended without asking for a next step (`[S]` 30mpc / Procore) |
| `CLINICAL-DRIFT` | **Regulated/values interview only** — answered a values scenario with clinical knowledge (`[S]` NHS VBR: stations are explicitly not clinical) |
| `PROBE-COLLAPSE` | Under follow-up the candidate withdrew, hedged away, or contradicted the original claim |
| `UNSOURCED-FACT` | A figure, tool, employer, title, or scope appears that is in neither the profile, the readiness brief, nor an earlier answer |
| `OVER-CLAIM` | The stated scope or credit exceeds the source fact recorded in `interview-brief.md` |

The last two are honesty tags, not quality tags, and they route to §6, not to the feedback list.

### 4f. Banned output vocabulary

**RECOMMENDATION — paste into SKILL.md verbatim:**

```
The mock interviewer and assessor MUST NOT emit:
  - any score, grade, percentage, or "X out of Y" of their own invention
  - any probability, likelihood, odds, or "chance of"
  - "you would pass / you would fail / they would hire you"
  - "strong candidate", "weak candidate", "hire", "no-hire", "leaning hire"
  - any comparison to other candidates, real or imagined ("better than most applicants")
  - any claim about what the interviewer thought, felt, or would conclude
  - a rating on a scale the employer did not publish

THE ONE EXCEPTION: where the employer publishes its own rubric — UK Civil Service
Success Profiles behaviours at the grade named in the advert, an NHS values framework,
a university person specification — you MAY walk the candidate through that published
scale, using the employer's own wording, as a CHECKLIST of what evidence the panel is
told to look for. Attribute it ("the Civil Service scale used here reads: 4 = 'Adequate
positive evidence and any negative evidence would not cause concern'"). Never assert
what the panel would actually mark. Quoting an employer's scale is reporting; applying
it as a verdict is fabrication.
```

---

## 5. Session mechanics in a terminal agent

### 5a. The constraint that decides it

There is a hard mechanical fact here, and it is visible in the parent skill's own agent contracts: **a spawned subagent cannot hold a turn-by-turn conversation with the human.** `agents/hiring-manager.md` line 21 says its inputs are *"pasted directly below this prompt when you are dispatched"* and line 97 says it *"MUST end your response with EXACTLY the following block"* — a one-shot dispatch/return contract, with no channel for asking the user something and waiting. All three judges in `SKILL.md` Step 7 are used that way.

So **option (b) as literally specified — a fresh subagent per round acting as the interviewer — cannot conduct a live interview.** It can generate a question list, or assess a completed transcript, but it cannot ask a question, receive the human's answer, and follow up. That eliminates half of (b) before any trade-off analysis.

### 5b. Trade-offs

| | (a) Inline interviewer | (b) Subagent interviewer + subagent assessor | (c) Scripted bank, agent only scores |
|---|---|---|---|
| **Can it actually interview?** | Yes | **No** — no user-input channel mid-run | Yes (reading from a list) |
| **Realism** | High — adapts to what the candidate just said, can go off-book, can play a specific persona | n/a | Low — a real interviewer's next question is a *function of your last answer*; a bank's is not |
| **Follow-up quality** | **The whole point.** Can hear a wobble and dig: "you said the team decided — who proposed it?" | n/a | **Structurally impossible.** A bank can hold one canned follow-up per question; it cannot dig into an answer it did not anticipate. This is (c)'s disqualifying weakness — and per §4, "held under probe" is the *only* band above ASSERTED that means anything |
| **Assessment honesty** | **Poor.** The inline agent has read `interview-brief.md`. It knows the true source fact. It will hear the answer the candidate *meant* and credit it. The parent skill already legislates against this: *"This skill does not judge its own output"* (SKILL.md line 24) | Good — a fresh assessor sees only the transcript | Good, but assessing thin material |
| **Context cost** | Transcript accumulates in the main conversation; a 12-question round with follow-ups is substantial, and it compounds across rounds | Low per-agent | Lowest |
| **Pause / resume** | Only if the transcript is on disk — the conversation itself is not a resumable artifact | n/a | Trivially |

### 5c. RECOMMENDATION

**Inline interviewer + subagent assessor, both anchored to an on-disk transcript, with the question bank demoted to seed material.**

This is the same actor–critic split the parent skill already runs, for the same stated reason — `SKILL.md` line 154: *"The actor stays inline (not a separate subagent) because it already holds full context and is the only party that can ask the candidate honest supplementary questions."* Substitute "interviewer" for "actor" and the argument is unchanged.

Four design details that make it work:

**1. Split the packs, so the assessor cannot be contaminated.**
- *Interviewer pack* (inline, in main context): `posting.yaml`, `cv.md`, `interview-brief.md`, the market/family shape from §1–§2, any scraped shape facts with dates.
- *Assessor pack, pass 1* (subagent): the transcript file, `posting.yaml`, `cv.md`. **Not** `interview-brief.md`. It therefore cannot credit the candidate for a source fact the candidate never actually said — which is precisely the leniency failure of option (a).
- *Assessor pack, pass 2* (subagent, cheap): the transcript **and** `interview-brief.md`, with one job only — emit `UNSOURCED-FACT` / `OVER-CLAIM` / `CONTRADICTED` by diffing what the candidate said against the provenance map.

Two passes with deliberately different inputs is what turns the honesty tripwire from a good intention into a mechanism.

**2. Write the transcript after every single answer, not at the end of the round.** This is what buys pause/resume for free, keeps the assessment reasoning out of the main conversation (the subagent reads the *file*), and means a crashed session loses one answer, not a round.

**3. Cap the inline interviewer to one round per dispatch.** Between rounds, the assessor runs and the transcript is flushed to disk. Round 2's interviewer prompt carries a short *carry-forward* block (open loops, unresolved probes) rather than the full round-1 transcript. That is the context-cost mitigation.

**4. The question bank is seed material and nothing else.** Scraped items and generated items both land in `question-log.yaml` *before* the round as candidate openers with their provenance and dates. The inline interviewer picks from them and then goes wherever the answer leads. Option (c)'s only real virtue — coverage of the posting's must-haves — is preserved by *auditing the log after the round*, not by reading from it during.

**On the anti-realism of a friendly interviewer:** give the inline interviewer an explicit persona pulled from the market/family shape — a 交叉面 interviewer from a different department who has not read your CV closely, an Amazon Bar Raiser from outside the team `[F]`, a Success Profiles panel scoring one named behaviour at a named grade `[F]`, a Dutch hiring manager who *"will ask tough questions about any questionable resume items without beating around the bush"* `[F]`. The persona is what makes a text interview feel like anything at all, and it costs nothing.

---

## 6. The anti-coaching line

**RECOMMENDATION — this is written to be pasted into SKILL.md as-is.**

```markdown
### The line: rehearse retrieval, never rehearse content

A mock interview may help the candidate FIND, ORDER, and COMPRESS a true story they
already lived. It may not help them ACQUIRE one. The test is where the fact came from:

- If a detail traces to the profile, to the provenance map in `interview-brief.md`, or
  to something the candidate told you earlier in this session — helping them say it
  better is preparation.
- If a detail first appears in YOUR mouth — a number, a tool, a scope, a motive, a
  result — it is fabrication, however plausible, and it stays fabrication after the
  candidate agrees with it.

**Four hard rules.**

1. **Never write an answer for the candidate.** You may name what is missing ("your
   answer never said what changed as a result"). You may not supply the missing part.
   Naming a gap is feedback; filling it is ghostwriting a lie.

2. **A leading question is a fabrication vector.** "So you'd say you owned the
   migration?" hands the candidate an over-claim they will repeat in the real room and
   will not be able to defend. Ask "who owned the migration?" — open, and let the
   answer be whatever it is. This applies to your interview questions too: never build
   a question on a premise the CV does not support ("when you led that team of twelve").

3. **An undefendable claim is a CV bug, not a story to drill.** If the candidate cannot
   truthfully support a CV claim under ONE follow-up, that is a tailoring error. Log it
   to the walk-back list and change the CV. This is `references/interview-prep.md`'s
   over-reach rule — the mock interview is the stage where it actually fires, because
   the three CV judges only read the page and the page does not stammer.

4. **Never rehearse a gap into a non-gap.** For an HONEST-GAP the only preparation is
   the truthful framing already chosen in the tailoring plan. Do not produce a smoother
   version that implies experience the candidate lacks. "I haven't done X" must survive
   rehearsal intact; only the sentence around it may improve.

**The tripwire.** Any figure, tool, employer, title, or scope that appears in the
candidate's answer and is in NEITHER the profile, NOR `interview-brief.md`, NOR an
earlier answer this session, is tagged `UNSOURCED-FACT` (or `OVER-CLAIM` if it exceeds
a recorded source fact) and the candidate is asked where it came from BEFORE it may
enter the answer bank. Usually the answer is "it's true, it's just not on my CV" — that
is a real finding and it should probably go on the CV. Sometimes it is drift under
pressure. Either way it gets resolved, never silently kept: an answer-bank entry
containing an unsourced fact is worse than no answer bank, because the candidate will
say it out loud in the real interview believing you vetted it.
```

---

## 7. What the session should leave on disk

**RECOMMENDATION.** Under the existing workspace (`~/.claude/job-profiles/<name>/applications/<company>-<role>-<YYYY-MM-DD>/`, `SKILL.md` line 95–101), add a `mock/` subdirectory. Six files, each justified by the test *"would you read this at 11pm the night before?"*

| File | Contents | Why it earns its place |
|---|---|---|
| `mock/transcript-<n>.md` | Verbatim Q&A, appended after every answer, with round label, simulated persona, and the market/family shape being run | Resume substrate; the assessor's only input on pass 1; the candidate's own record |
| `mock/assessment-<n>.md` | Per-answer defect tags **each with the quoting line**, per-dimension bands, requirement-coverage table, shape-coverage table | The night-before diagnostic. No prose paragraphs — a table you can scan |
| **`mock/answer-bank.md`** | **One entry per real story**: the S/T/A/R(/R) fields *in the candidate's own words as actually spoken*, a `source:` line copied from `interview-brief.md`'s provenance map, and `serves:` — which questions it has answered so far | **The single most valuable artifact.** It is the only thing that compounds across sessions and across applications, and the `source:` line is what keeps it honest. This is what you actually re-read |
| `mock/open-loops.md` | Every question the candidate could not answer, sorted into three buckets: **(i) fact you have but didn't recall** → go find it before the real thing; **(ii) genuine gap** → use the honest framing from `interview-brief.md`; **(iii) tailoring error** → the claim comes off the CV | The three buckets have three completely different actions. Merging them into one "weak areas" list destroys the artifact |
| `mock/question-log.yaml` | Every question asked, with `source: generated \| scraped \| judge-supplementary`; for scraped, the `tid`/`id`, URL, and the `time` from `detail` | Makes every scraped question attributable and dateable, so the candidate can discount a 9-month-old one themselves. Also the coverage audit input |
| `mock/cheatsheet.md` | **One page.** Your stories, one line each. Your 2–4 honest gaps with their exact framing. The questions you still can't answer. Your questions for them. The loop shape you're walking into, with round names in the local vocabulary | The actual night-before read. If it exceeds one page it has failed |

Plus **two write-backs into the existing pipeline**, which is where this module pays for itself:

1. **Append a `## Walk-back list` section to `<workspace>/interview-brief.md`** — every CV claim that failed under probe, with the transcript quote and the recommended softened wording. Then offer to re-run the tailoring edit and re-render. This closes the loop `interview-prep.md` line 39 opens but has no mechanism to fire.
2. **Promote confirmed-but-absent facts.** When an `UNSOURCED-FACT` resolves to "true, just not on my CV", that is a genuine gap-analysis finding — route it back to the tailoring plan through the normal claim-provenance checkpoint, with the session answer as its source (`SKILL.md` line 89 already permits *"an answer the user gave during this session"* as valid provenance).

**One layering note**, given the owner's rule that layer 2 needs a backstop: `mock/assessment-<n>.md` and `mock/answer-bank.md` are **required artifacts that cannot be written without having read the defect vocabulary and the band descriptors.** That makes §4's tables safe to live in `references/interview-shapes.md`. The **banned-vocabulary block (§4f) and the anti-coaching rules (§6) have no such backstop** — nothing fires if they are skipped, the session just quietly coaches the candidate into a lie — so those two blocks belong **inline in SKILL.md**, however bulky.

---

## UNVERIFIED / COULD NOT SOURCE

Everything in this list is either unsourced or sourced only from a search-result summary I did not open. Do not write any of it into the skill as fact without checking.

1. **Levashina et al. (2014) full text.** Could not open: `morgeson.com` PDF → *"certificate has expired"*; Wiley → HTTP 402; Semantic Scholar → empty body. The "18 structuring elements, average six used" figure and the BARS-improves-validity claim are `[S]` only. The citation itself (Personnel Psychology 2014, 67, 241–293) came from a search-result title, not from the paper.
2. **EPSO's competency list and anchors.** The eu-careers landing page `[F]` confirms a framework exists but not its contents. `eu-careers.europa.eu/system/files/2023-04/EN.pdf` returned an undecodable 7MB binary; two other EPSO PDF URLs 404'd. The 8-competency 2024 list is `[S]` from eutraining.eu, a commercial trainer.
3. **NHS MMI specifics** (3 domains, 5-point scale, 3–15 range, non-clinical scenarios). `[S]` only — the HEE PDF fetch failed on a classifier error. Verify before writing the numbers.
4. **UK academic panel scoring mechanics.** `[S]` only — the Sheffield HR page is now behind a CAS login; I did not open UCL, Manchester, or Birkbeck.
5. **交叉面.** `[S]` only, from Zhihu/Jianshu/CSDN search summaries. Plausible and consistent across several, but I opened none of them.
6. **Whether German private-sector hiring normally runs multiple rounds** with a separate Fachgespräch or Probearbeiten. StepStone `[F]` and Robert Half `[F]` both describe a *single* five-phase interview and neither mentions round count. Assessment Center as a multi-hour/full-day format is `[S]`. **Do not assert a German multi-round loop on this evidence.**
7. **Dutch case-opdracht timing, psychometric assessment prevalence, and the arbeidsvoorwaardengesprek.** All `[S]` from iamexpat / expatica / hays / Indeed NL / FNV summaries. The STARR/STARRT structure itself is `[F]` and solid; the process facts around it are not.
8. **All role-family loop structures in §2 for ML, data, product, sales, and industry research** — Meta/Google/Amazon/OpenAI/DeepMind round compositions, SQL screen lengths, take-home durations, discovery-call timings. Every one is `[S]` from commercial interview-prep sites (Exponent, IGotAnOffer, InterviewQuery, InterviewKickstart, DataLemur, 30mpc, techinterview.org). These sites have an incentive to sound authoritative and to describe loops as more fixed than they are. The Amazon numbers (4–6 interviews, 45–60 min, Bar Raiser definition) and the MIT academic-interview numbers are the only role-family facts here that are `[F]` from a primary source.
9. **The generic US "recruiter screen → technical phone → onsite loop" sequence.** Universally repeated but I found no primary source stating it canonically. `[S]`.
10. **Meta's 2025 AI-assisted coding round.** `[S]`, single prep-site mention. Too specific and too recent to state.
11. **Whether `nowcoder search` is rate-limited, or whether the anonymous access I observed is stable.** I ran roughly a dozen read calls without hitting a limit; that is not evidence of no limit. Also unverified: whether `experience` and `practice` would return useful data *with* login — I did not log in.
12. **Why `nowcoder papers --company/--job` are inert.** Verified that they are `[C]`, not why. Could be an upstream API change or an adapter bug. The skill should not depend on them either way.
13. **Whether the 1point3acres 403 is permanent, geo-based, IP-based, or transient.** Three commands, one session, one moment. Re-probe rather than hard-coding "unavailable".
14. **Google's sample-rubric categories.** The re:Work *guide* `[F]` says "poor, borderline, solid, and outstanding". A search summary `[S]` attributes "Poor, Mixed, Good, and Excellent" to the linked sample-rubric Google Doc, which I did not open. Use the fetched wording; note the discrepancy.

---

### Files read

- `/Users/donghanglyu/.claude/skills/job-application/references/interview-prep.md`
- `/Users/donghanglyu/.claude/skills/job-application/agents/hiring-manager.md`
- `/Users/donghanglyu/.claude/skills/job-application/references/role-families.md`
- `/Users/donghanglyu/.claude/skills/job-application/SKILL.md` (lines 1–60 read; lines 45, 84–89, 95–123, 154, 164–210 grepped)
- CLI help captured to `/private/tmp/claude-501/-Users-donghanglyu/d1ca171b-6798-42dc-9582-87e4635be401/scratchpad/nowcoder_help.yaml` (654 lines) and `.../1p3a_help.yaml` (403 lines)

### Web sources opened (`[F]`)

[gov.uk — Success Profiles](https://www.gov.uk/government/publications/success-profiles) · [gov.uk — Civil Service behaviours](https://www.gov.uk/government/publications/success-profiles/success-profiles-civil-service-behaviours) · [COPFS — how your application is assessed](https://www.copfs.gov.uk/about-copfs/careers/how-your-application-is-assessed-success-profiles/) · [National Careers Service — the STAR method](https://nationalcareers.service.gov.uk/careers-advice/interview-advice/the-star-method) · [Google re:Work — guide to structured interviewing](https://rework.withgoogle.com/intl/en/guides/a-guide-to-structured-interviewing-for-better-hiring-practices) · [About Amazon — interview guide](https://www.aboutamazon.com/news/workplace/amazon-interview-guide) · [MIT CAPD — academic interviews](https://capd.mit.edu/resources/academic-interviews-faculty-positions/) · [程序厨 — 面试流程及形式](https://www.chengxuchu.com/3-interview_guide/03-%E9%9D%A2%E8%AF%95%E6%8C%87%E5%8D%97/2-%E9%9D%A2%E8%AF%95%E6%B5%81%E7%A8%8B%E5%8F%8A%E9%9D%A2%E8%AF%95%E5%BD%A2%E5%BC%8F.html) · [DutchReview — job interviews in the Netherlands](https://dutchreview.com/expat/work/job-interviews-netherlands/) · [Carrièretijger — STAR/STARR/STARRT](https://www.carrieretijger.nl/carriere/solliciteren/sollicitatiegesprek/gesprekstechnieken/star) · [StepStone — Vorstellungsgespräch Ablauf](https://www.stepstone.de/magazin/artikel/vorstellungsgespraech-ablauf-und-optimale-vorbereitung) · [Robert Half DE — Ablauf](https://www.roberthalf.com/de/de/insights/karriereentwicklung/ablauf) · [EU Careers — EPSO competency framework](https://eu-careers.europa.eu/en/documents/epsos-competency-framework/13068)
