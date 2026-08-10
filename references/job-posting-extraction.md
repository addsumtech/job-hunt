# Job Posting Extraction Reference

How to read a job posting and turn it into a structured object that drives CV tailoring and the cover letter. Every step here is directly actionable — no guessing, no skipping.

---

## 0. Get the posting text reliably (before you extract anything)

Garbage in, garbage out: extracting from a page that isn't actually the posting produces fabricated requirements that then drive the whole application. So validate the source first.

- **A `200 OK` is not proof you have the posting.** LinkedIn, Workday, Greenhouse, Indeed, and most portals return a success status for a **login wall, cookie/consent banner, bot check, or search page**. If the fetched text has no responsibilities and no requirements, is dominated by "sign in" / "create account" / cookie text, or is suspiciously short, you did **not** get the posting.
- **When the fetch is thin or wrong, do not extract — ask the user to paste the full posting text.** Inventing must-haves off a login wall is worse than asking.
- **Terminal case:** if the posting genuinely can't be obtained (dead link, nothing to paste), stop and say so. Never proceed on guessed requirements.

---

## 1. The Extraction Schema

Extract exactly these fields. Populate each as described below.

| Field | Type | How to populate |
|---|---|---|
| `role_title` | string | The exact title as written in the posting (e.g. "Senior Data Engineer", "Machine Learning Engineer II"). |
| `seniority` | enum: `intern / junior / mid / senior / lead` | Infer from title words, years-of-experience stated, and scope of responsibilities. See §2 for implicit seniority signals. |
| `location` | object: `{city, country, arrangement}` | `arrangement` ∈ `remote / hybrid / onsite`. Pull from the header or location line. If no arrangement is stated and the role is tied to a physical office, default to `onsite`. |
| `must_haves[]` | list of strings | Hard requirements the posting marks as required, essential, must-have, or minimum. Include degrees/certs if stated as required (not just "preferred"). See §2 for phrasing heuristics. |
| `nice_to_haves[]` | list of strings | Skills/experience the posting marks as preferred, bonus, a plus, nice to have, or "we'd love". Include items in a separate "Preferred Qualifications" section. |
| `responsibilities[]` | list of strings | Day-to-day duties — what the person will actually do. Drawn from "What you'll do" / "Responsibilities" / "Day in the life" sections. Use the posting's own phrasing. |
| `keywords[]` | list of strings | **Exact ATS terms** to mirror in the CV and cover letter: tool names, language names, frameworks, methodologies, certifications, domain-specific jargon. Extract casing exactly (e.g. "PyTorch", "CI/CD", "REST APIs", "Agile/Scrum"). |
| `company_values_tone` | string | Culture signals + voice. Note: formal vs. casual writing style, mission language ("we believe", "our north star"), DEI statements, pace signals ("fast-moving", "startup within a larger company"), team descriptors ("collaborative", "autonomous"). This shapes the cover letter's register. |
| `salary_range` | string or null | The stated pay range, if the posting gives one (e.g. "€65k–80k"); else `null`. Many EU/US postings now state a range. |
| `red_flags` | list of strings | Signals of a problematic role. See the full list of red-flag patterns in §2. |
| `application_type` | enum: `cv / structured` | `structured` when the posting splits requirements into **Essential / Desirable** criteria, names **behaviours / "Success Profiles" / a competency framework**, or tells the applicant to "evidence how you meet each criterion" / submit a scored supporting statement (common for UK NHS, Civil Service, public-sector, NGO, and many academic roles). Otherwise `cv`. When `structured`, the primary deliverable is a criterion-mapped supporting statement — follow `references/structured-applications.md`. |

**Salary fit (when a range is stated):** if `salary_range` is present, ask the user **once** whether it fits their expectation — a band mismatch is a common silent screen-out, and it's better surfaced now than after a full application. Keep it a single optional question; if no range is stated, don't ask (don't volunteer salary the posting didn't raise).

### JSON shape (for internal use by the orchestrator)

```json
{
  "role_title": "Senior Backend Engineer",
  "seniority": "senior",
  "location": {
    "city": "Amsterdam",
    "country": "Netherlands",
    "arrangement": "hybrid"
  },
  "must_haves": [
    "5+ years of backend engineering experience",
    "Proficiency in Go or Python",
    "Experience designing distributed systems"
  ],
  "nice_to_haves": [
    "Experience with Kafka",
    "Prior work in fintech"
  ],
  "responsibilities": [
    "Design and maintain high-throughput data pipelines",
    "Collaborate with product and data science to scope features",
    "Mentor junior engineers and participate in code review"
  ],
  "keywords": [
    "Go", "Python", "distributed systems", "Kafka",
    "REST APIs", "PostgreSQL", "Docker", "Kubernetes"
  ],
  "company_values_tone": "Casual but purposeful tone. Emphasises autonomy and ownership. Mission framing around financial inclusion. Uses 'you'll' rather than 'the candidate will'. Fast-moving but not chaotic.",
  "red_flags": []
}
```

---

## 2. Heuristics for Messy Postings

Real postings are inconsistent, duplicated, and full of noise. Use these rules to produce a clean extraction.

### Mapping phrasing to must_have vs. nice_to_have

| Posting language | Classify as |
|---|---|
| "required", "must have", "essential", "minimum qualifications", "you must" | `must_have` |
| "preferred", "bonus", "a plus", "nice to have", "ideally", "we'd love", "advantageous" | `nice_to_have` |
| "you have…" (declarative, not conditional) in a requirements list | `must_have` |
| "we'd love it if you have…", "bonus points for…" | `nice_to_have` |
| Degree listed in "Minimum Qualifications" | `must_have` |
| Degree listed in "Preferred Qualifications" or "a degree in X is a plus" | `nice_to_have` |
| No qualifier given, but listed alongside clearly hard requirements | Default to `must_have`; note ambiguity |

**Non-English postings:** the cue words above are English; apply the same logic to the local-language equivalents. German: `Erforderlich` / `Voraussetzungen` / `Sie bringen mit` → `must_have`; `Wünschenswert` / `von Vorteil` / `idealerweise` → `nice_to_have`. French: `Exigé` / `Requis` → `must_have`; `Souhaité` / `un plus` → `nice_to_have`. Japanese: `必須` → `must_have`; `歓迎` / `尚可` / `あれば尚可` → `nice_to_have`. Extract `keywords` in the **posting's language** (tool names and proper nouns stay as-is). Record the posting language and carry it to `meta.language` so the CV and letter are written to match (see `cv-craft.md §2`).

### Implicit must-haves for senior/lead roles

When a posting titles the role "Senior" or "Lead" but does not list years of experience or leadership expectations explicitly, add these as implicit must-haves (mark them `[implicit]` for the user to confirm):

- `[implicit] 5+ years of relevant industry experience` — senior implies this
- `[implicit] Demonstrated ownership of significant features or systems`
- `[implicit] Ability to work with minimal supervision`
- For "Lead": also `[implicit] Experience mentoring engineers or technical leadership`

### Hard disqualifiers (tag separately — they are walls, not wishes)

Some must-haves are **non-negotiable barriers** the candidate cannot close by tailoring or learning: **work authorization / visa** for the country, a **legally required license or security clearance**, a **hard on-site/location** requirement, **language fluency**, or a **regulated experience floor**. Tag these `[disqualifier]` (distinct from an ordinary must-have like "Kubernetes", which is recoverable).

Surface `[disqualifier]` items **first** in the §4 confirmation and ask the user directly: *"These look non-negotiable — do you meet them? If not, this may not be worth a full application."* This protects the user's time on day one (the recruiter judge would otherwise only catch a logistics wall after a whole package is built), and it keeps a genuine legal barrier from being mis-handled downstream as a soft "framing" gap (see `gap-analysis.md §3`).

### Stripping boilerplate

Ignore and do not extract as requirements:
- EEO/EEOC statements ("We are an equal opportunity employer…")
- Legal disclaimers and data-processing notices
- Generic perks lists (health insurance, 401k, office snacks)
- Generic soft-skill padding appearing identically across all roles at a company (e.g. "You are a team player who communicates well")
- Carbon-copy "About the Company" paragraphs that describe the company's history

Keep soft skills that appear in the specific requirements section of *this* posting as likely intentional signals (e.g. "exceptional written communication required for a client-facing role" is real).

### Handling duplicated requirements

Postings often list the same skill in both "Requirements" and "Responsibilities" sections. De-duplicate: keep one entry in the most appropriate field (`must_have` if it was in Requirements, `responsibility` if it was only in Responsibilities).

### Very short postings (under 150 words)

If the posting gives almost no detail (a brief LinkedIn summary, a generic title + one paragraph):
1. Extract what is there.
2. Infer from the role title + company: look up the company type/size mentally and note it in `company_values_tone`.
3. Add a note to the user: "This posting is unusually short. The extracted schema may be incomplete. Please review and add anything you know about the role."
4. Do not fabricate requirements.

### Red-flag patterns to detect

Add to `red_flags[]` if any of these appear:

| Pattern | Example |
|---|---|
| Rockstar/ninja/guru language | "We're looking for a coding ninja" |
| Unpaid or ambiguously paid | "Stipend-based", "equity only at the start" |
| Unrealistic stack breadth | Requires 10+ distinct specialisms at senior level |
| Scope creep signals | "Other duties as assigned" is vague; extreme version: the whole posting is vague |
| Churn / pressure signals | "Move fast", "wear many hats" combined with no stable team description, or former employees' LinkedIn shows <1 year tenures |
| Missing salary range (jurisdiction-dependent) | Red flag in US states/EU contexts where it is required or expected |
| "We're a family" | Boundary-setting risk; common in high-burnout cultures |
| No mention of team structure | Unclear whether IC role exists inside a real team |

---

## 3. The Fetch Procedure

Follow this order every time. Do not skip ahead.

**Step 1 — Try to fetch the URL.**

Use `WebFetch` on the provided URL. Examine the returned text:
- Is it at least ~300 words of readable job-description prose?
- Does it contain a requirements or qualifications section?

If yes, proceed to extraction.

**Step 2 — Detect a blocked or unusable page.**

The following platforms frequently return login walls, empty shells, or JavaScript-rendered content that is not usable as text:
- LinkedIn job postings (most return a login prompt or a thin snippet)
- Workday embeds (e.g. `company.wd5.myworkdayjobs.com`) — often return near-empty HTML
- Greenhouse iframes loaded inside a company's own site
- Lever postings embedded in iframes
- Taleo and iCIMS portals

If `WebFetch` returns fewer than ~200 words, no qualifications language, or a login/sign-in prompt, **do not guess**.

**Step 3 — Ask the user to paste the full text.**

Say exactly this (adjust as needed):

> The job posting at [URL] is behind a login wall / returned too little text to extract reliably. Please paste the full posting text here and I'll extract the structured schema from it.

Wait for the pasted text. Then extract.

**Step 4 — Extract from the text.**

Apply the schema in §1 and the heuristics in §2. Produce the JSON object internally (the orchestrator uses it downstream). Do not show the raw JSON to the user — show the confirmation summary in §4 instead.

---

## 4. Confirm with the User

After extracting, always show a concise plain-English summary and ask for confirmation before proceeding. Use this format:

---

**Role:** [role_title] at [Company] — [arrangement] in [city / remote]

**Must-haves I extracted:**
1. …
2. …
3. …

**Nice-to-haves I extracted:**
1. …
2. …

**Key ATS keywords I'll mirror:**
[comma-separated list]

**Culture/tone signal:** [one sentence]

**Red flags:** [none / list]

Any implicit must-haves I inferred (marked [implicit]): [list or "none"]

---

Does this look right? Please correct anything I got wrong or add context the posting omits (e.g. team size, internal context, whether a requirement is actually negotiable). I'll use your input before moving to gap analysis.

---

This step is not optional. The user often knows:
- That "5 years experience required" is a negotiable guideline, not a hard cutoff
- That the role is actually a different seniority than the title suggests
- That the company cares far more about one skill than the posting implies
- That they have additional relevant experience not yet in the CV

Incorporate all corrections, then proceed to gap analysis.

---

## 5. Worked Mini-Example

### Input: raw job blurb

> **Data Analyst — London, UK (Hybrid)**
>
> We're a fast-growing fintech and we want a sharp data analyst to join our Growth team. You'll work closely with marketing and product to turn raw event data into insights that drive decisions.
>
> **You must have:**
> - 2+ years experience in an analytical role
> - Strong SQL skills
> - Experience with Python or R for data manipulation
> - Comfortable presenting findings to non-technical stakeholders
>
> **Nice to have:**
> - Experience with dbt
> - Familiarity with Looker or Tableau
> - Prior fintech or payments background
>
> We move fast and value ownership. If you're the kind of person who spots a question in the data and digs in without being asked, you'll fit right in.

### Extracted schema

```json
{
  "role_title": "Data Analyst",
  "seniority": "junior",
  "location": {
    "city": "London",
    "country": "United Kingdom",
    "arrangement": "hybrid"
  },
  "must_haves": [
    "2+ years of experience in an analytical role",
    "Strong SQL skills",
    "Python or R for data manipulation",
    "Ability to present findings to non-technical stakeholders"
  ],
  "nice_to_haves": [
    "Experience with dbt",
    "Familiarity with Looker or Tableau",
    "Prior fintech or payments background"
  ],
  "responsibilities": [
    "Collaborate with marketing and product teams",
    "Turn raw event data into actionable insights",
    "Drive data-informed decisions"
  ],
  "keywords": [
    "SQL", "Python", "R", "dbt", "Looker", "Tableau",
    "data manipulation", "stakeholder communication", "fintech", "payments",
    "event data", "Growth"
  ],
  "company_values_tone": "Casual, direct, startup pace. 'We move fast', 'ownership' valued. Self-directed working style implied ('digs in without being asked'). Growth team context = marketing-adjacent. No formal mission statement.",
  "red_flags": [
    "'We move fast' without team structure detail — verify whether Growth team is stable or ad hoc"
  ]
}
```

### Confirmation summary shown to user

> **Role:** Data Analyst at [Company] — hybrid in London, UK
>
> **Must-haves I extracted:** 2+ years analytical experience; strong SQL; Python or R; stakeholder communication
>
> **Nice-to-haves I extracted:** dbt; Looker or Tableau; fintech/payments background
>
> **Key ATS keywords I'll mirror:** SQL, Python, R, dbt, Looker, Tableau, event data, fintech
>
> **Culture/tone signal:** Fast-moving startup; values autonomous, ownership-driven analysts.
>
> **Red flags:** "We move fast" without team structure detail — worth verifying.
>
> Does this look right? Please correct or add anything before I run the gap analysis.
