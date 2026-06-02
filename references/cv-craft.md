# CV Craft Reference

Actionable guidelines for building and tailoring CVs. Every rule here tells you *what to do*, not just *what to aim for*.

---

## 1. Section Ordering by Career Stage

### Early-career / Student (0–3 years experience, or still in education)

```
1. Contact header
2. Summary (optional — omit if no clear target; include if career-changing or injecting keywords)
3. Education  ← near top; it is your primary credential
4. Relevant Projects / Research
5. Work Experience  (internships, part-time, student jobs)
6. Skills (technical stack, languages, tools)
7. Awards / Honors / Certifications (if relevant)
8. Volunteer / Activities (only if it adds signal)
```

**Why:** A 2019 CS grad with a Google internship has more to show from coursework + projects than from 18 months of work history. Education and projects anchor the story.

### Experienced / Mid-to-Senior (3+ years)

```
1. Contact header
2. Summary / Professional Profile  ← 2–4 sentences; see §6
3. Work Experience  ← chronological, most recent first; takes the lion's share
4. Skills
5. Education  ← condensed: degree, school, year — no GPA unless <5 years ago and ≥3.7
6. Certifications / Courses (if relevant)
7. Publications / Patents / Talks (for technical/academic roles)
```

**Why:** Recruiters spend 6–10 seconds on first pass. Years of relevant impact must be front and centre.

---

## 2. Regional Conventions

| Dimension | US (résumé) | UK (CV) | EU / NL | Default (unknown market) |
|---|---|---|---|---|
| **Length** | 1 page (2 if 10+ years or senior); strictly never 3+ | 2 pages max; 1 page acceptable for junior | 2 pages; academic CVs can be longer | Follow US/UK conservative style |
| **Photo** | NEVER include | Not expected; omit | Optional; common in NL, DE, FR | Omit |
| **DOB / Marital status / Nationality** | NEVER include | NEVER include (illegal basis for discrimination) | Nationality common in NL/EU; DOB optional in some countries; driving licence relevant for certain roles | Omit unless user says otherwise |
| **Personal statement / Summary** | Optional; at top if included | Common; 3–5 lines at top is expected at senior level | Common | Include if senior or career-changing |
| **References section** | Omit completely; "references available on request" is also unnecessary filler | "References available on request" acceptable; or omit | Omit or one line | Omit |
| **Format** | Reverse-chronological, clean single column, standard headings | Same; may use 2-column for skills/contact | Same; may follow Europass but a clean custom CV is almost always received better | Reverse-chronological, single column |
| **Contact fields** | Name, phone, email, city+state (no street address), LinkedIn URL, portfolio/GitHub if relevant | Same; can add city without county | Same; some add nationality/driving licence per above | Name, phone, email, city, LinkedIn |
| **Language** | English | English | English widely accepted in NL tech; Dutch preferred for non-tech/government NL roles; match language to job posting | Match job-posting language; default English |
| **File format** | PDF (unless .docx explicitly requested) | PDF | PDF | PDF |

**NL-specific note:** For Dutch tech and international companies based in NL, English CVs are standard and expected. For Dutch-language job postings (overheid, onderwijs, traditional industries), write the CV in Dutch or offer both.

**Europass note:** Europass is bureaucratically recognised (EU institutions, some public-sector roles) but recruiters at private companies often find it verbose and dated. Use a clean custom CV by default; only switch to Europass if the posting explicitly requests it.

---

## 3. The Bullet Pattern

### Formula

```
[Strong action verb] [what you did / what you built] [resulting in / by / which] [quantified outcome]
```

**Key rules:**
- Start every bullet with a past-tense action verb (present tense for current role is acceptable but less common).
- Quantity wherever possible: %, $, hours, users, latency, error rate, team size.
- If you have no number, name the scope or scale: "across 3 microservices", "for a team of 12", "supporting 200k MAU".
- One bullet = one accomplishment. Not a job description.
- Target 1–2 lines per bullet. Three lines is a paragraph — split it.

### Action Verb Bank (~25 verbs, grouped)

| Category | Verbs |
|---|---|
| **Led / Managed** | Led, Managed, Directed, Owned, Oversaw, Mentored, Coordinated |
| **Built / Created** | Built, Architected, Designed, Developed, Implemented, Launched, Deployed |
| **Improved / Optimised** | Reduced, Cut, Accelerated, Optimised, Streamlined, Automated, Refactored |
| **Analysed / Modelled** | Analysed, Modelled, Evaluated, Benchmarked, Audited, Diagnosed, Investigated |
| **Delivered / Shipped** | Delivered, Shipped, Migrated, Integrated, Released, Rolled out |

Avoid weak openers: "Responsible for", "Worked on", "Helped with", "Assisted in", "Was involved in" — these describe a job description, not an achievement.

### BEFORE → AFTER Example

**BEFORE (weak):**
> Responsible for the data pipeline, including making sure it ran on time and fixing bugs when they came up.

**AFTER (strong):**
> Cut data-pipeline end-to-end latency 40% by rewriting the batch layer in Rust, eliminating a 3-hour SLA breach and saving ~6 engineer-hours/week in on-call firefighting.

**Why it's better:** Starts with the outcome-oriented verb "Cut", quantifies the improvement (40%), names the concrete action (rewrote in Rust), and shows downstream business impact (SLA, engineer hours).

**Second example:**

**BEFORE:**
> Worked on improving model accuracy for the recommendation system.

**AFTER:**
> Raised recommendation CTR by 12% (from 3.1% to 3.5%) by replacing collaborative filtering with a two-tower neural model, deployed to 4M users in production.

---

## 4. ATS (Applicant Tracking System) Rules

ATS parsers are used by most companies with 50+ employees. A CV that confuses the parser gets zero human eyes.

### Do

- **Use standard section headings exactly:** `Experience` or `Work Experience`, `Education`, `Skills`, `Summary` or `Professional Summary`. Non-standard headings like "Where I've Worked" or "My Toolkit" may not be parsed.
- **Mirror the job posting's exact phrasing.** If the posting says "CI/CD", write "CI/CD" — not only "continuous integration/continuous delivery". If it says "React.js", match that casing.
- **Single-column layout.** ATS reads left-to-right, top-to-bottom in the document order. Multi-column layouts split mid-sentence.
- **Use a common system font:** Calibri, Arial, Helvetica, Garamond, Georgia, Times New Roman. Avoid decorative or web-only fonts.
- **Keep critical content in the body.** Text in headers, footers, text boxes, and tables may be skipped by parsers. Do not put your name only in the document header.
- **Save as PDF.** Most modern ATS (Greenhouse, Lever, Workday, iCIMS) handle PDF well. Use `.docx` only if the job portal explicitly warns against PDF or requests Word format.

### Do Not

- Multi-column layouts for parsed sections (a two-column Skills section is a common trap).
- Text boxes (MS Word text boxes are invisible to many parsers).
- Tables for experience/education content (thin borders sometimes parse correctly, but it's fragile).
- Images of text (e.g., scanned letterhead, logo-as-text).
- Fancy dividers, icons, progress-bar skill ratings — they add noise and confuse parsers.
- Putting your phone/email exclusively in a page header or footer.

### Keyword mirroring — practical steps

1. Copy the job posting into a text file.
2. Identify the 10–15 skills, tools, and role-specific phrases that appear most (especially in "Requirements" and "Responsibilities").
3. For each one, check if the CV already contains it in any form.
4. Add the exact keyword where it naturally fits (in a bullet, in the skills list, or in the summary). Do not add keywords that are not genuinely part of your background — see §7.

---

## 5. Length and Trimming

### Target lengths

| Career stage | Target |
|---|---|
| Student / 0–2 years | 1 page |
| 3–7 years | 1–2 pages |
| 8–15 years | 2 pages |
| 15+ years / senior / executive | 2 pages (3 only if roles are very distinct and all relevant) |
| Academic / research CV | No page limit; list all publications, grants, talks |

### What to cut first (in this order)

1. **Roles older than 10–15 years** that add no unique signal. If you held 5 early jobs all with the same scope, condense to one line: "2003–2008: Various junior roles in X sector."
2. **Generic soft-skill filler:** "Excellent communicator", "Team player", "Results-oriented", "Passionate about technology" — these are assumed and waste space.
3. **Obvious tools for the level:** A senior engineer does not need to list "Microsoft Word", "Slack", "Email". Reserve the skills section for things that are a real filter for the role.
4. **Repetitive bullets:** If three roles all say "collaborated with cross-functional teams", keep the most quantified one and cut the others.
5. **Long objective statements** on junior CVs (replace with a targeted 2-sentence summary or cut entirely).
6. **Bullet points beyond 4–5 per role** for older positions. Recent role: up to 6. Role from 7+ years ago: 2–3 at most.

### Getting from 3 pages to 2

- Reduce margins to 0.6–0.75 in (not less — it looks cramped).
- Reduce font size to 10–10.5pt body, 11–12pt headings.
- Merge two thin bullets into one compound bullet.
- Drop the oldest role entirely or replace with a single-line entry.
- Remove the "References available on request" line.
- Remove the "Hobbies" section unless it is genuinely relevant to the role.

### Getting from 2 pages to 1 (junior/early career)

- Keep only the most relevant 2–3 bullets per role.
- Condense Education: one line per degree (no coursework list unless it's directly requested or you have no experience).
- Merge Skills into one compact section; drop any skill you could not speak to in an interview.
- Remove the summary if the space is tight and the target role is obvious.

---

## 6. Summary / Professional Profile Writing

### When to include

- **Include:** Senior candidates (5+ years), career-changers, roles where keyword injection in the summary increases ATS score, or anyone with an unconventional path that needs framing.
- **Skip:** Students applying for their first role (let the education and projects speak), people with a clearly linear path applying in the same field, when space is tight on a 1-pager.

### Structure (2–4 sentences)

```
Sentence 1: Role/identity + years of experience + domain
Sentence 2: 1–2 signature technical/domain strengths with concrete evidence
Sentence 3: One differentiator or notable outcome
Sentence 4 (optional): What you're targeting / the value you bring next
```

### Strong example

> Machine learning engineer with 7 years building production recommendation and ranking systems at scale (50M+ users). Specialise in two-tower retrieval models and real-time feature pipelines using Spark and Flink; shipped a CTR uplift that generated $4M incremental ARR in 2023. Seeking a senior IC role in a product-led ML team where close collaboration with growth and product is expected.

**Why it works:** Specific identity, concrete scale, two named technical areas, a quantified achievement, a clear target.

### Weak example

> Experienced software engineer with a passion for technology and a proven track record of success. Strong communicator who works well in teams and individually. Looking for an exciting opportunity to contribute and grow.

**Why it fails:** No domain, no numbers, no technologies named, entirely generic — could describe anyone. Every adjective ("experienced", "proven", "strong") needs evidence to mean anything.

---

## 7. Honest Reframing Only

**What is allowed:**

- Emphasising the most relevant experience for this specific role (ordering bullets by relevance, not strictly by time within a role).
- Reframing transferable skills with accurate language: "Managed a student project team of 5" is legitimate if you did.
- Using the job posting's terminology when it accurately describes what you did: if you "built CI/CD pipelines" and they call it "DevOps automation", you can use both.
- Surfacing contributions that were real but under-documented: a performance optimisation you drove is worth a bullet even if it was never formally acknowledged.
- Choosing which roles to omit (irrelevant short-term jobs need not appear).

**What is not allowed:**

- Inventing skills you do not have.
- Inflating a title (e.g. listing "Senior Engineer" when your contract says "Engineer II").
- Changing employment dates to hide a gap or shorten tenure.
- Claiming sole credit for team accomplishments you contributed to partially — use "Co-led", "Contributed to", or "Part of the team that…" as appropriate.
- Adding a keyword from the job posting that does not reflect genuine experience.

**Cross-reference:** See `gap-analysis.md` for detailed rules on how to handle skill gaps, experience gaps, and how to frame partial/adjacent experience honestly when tailoring for a specific posting.
