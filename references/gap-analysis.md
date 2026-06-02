# Gap Analysis Reference

A deterministic procedure to compare a candidate's profile against extracted job requirements and produce a tailoring plan. Every rule here is actionable with no ambiguity left to resolve at runtime.

---

## 1. The Comparison Procedure

Work through every `must_have` and `nice_to_have` from the extracted schema (see `job-posting-extraction.md`). For each requirement, classify the candidate as `strong`, `partial`, or `missing`, and cite the evidence.

### Classification definitions

| Label | Meaning |
|---|---|
| `strong` | The profile clearly and directly satisfies the requirement. Evidence is explicit (named tool, quantified outcome, relevant title/role). |
| `partial` | The profile has adjacent or transferable experience that partly covers the requirement, but there is a gap in depth, recency, or exact match. |
| `missing` | The profile has no evidence of meeting this requirement. May be a genuine gap or an omission from the CV — see §3 to determine which. |

### Output: the gap table

Produce this table after comparing every requirement:

| Requirement | Label | Evidence from profile |
|---|---|---|
| 5+ years backend engineering experience | strong | 7 years across Role A (2017–2021) and Role B (2021–present) |
| Proficiency in Go or Python | strong | Python throughout roles; Go used in Role B side project (confirmed by user) |
| Experience designing distributed systems | partial | Worked on microservices at Role B but as a consumer, not architect — see §3 |
| Experience with Kafka | missing | No mention in CV — ask user before classifying as genuine gap |
| Prior work in fintech | missing | Retail e-commerce background only; fintech is a genuine gap |
| Mentoring junior engineers | partial | One bullet mentions code review; no explicit mentoring language |

Build the full table — do not skip nice-to-haves. Label each one even if obviously missing. Nice-to-haves with `strong` evidence are differentiators; surface them.

### How to find evidence

Look in this order:
1. Work experience bullets (most authoritative — real context, real scope)
2. Skills section (take note: skills listed without context bullets carry weaker weight for `strong` classification)
3. Education / coursework (valid evidence for academic or early-career candidates, or for foundational knowledge)
4. Projects / publications / open-source (valid for technical depth claims)
5. Summary / profile statement (evidence of framing, not of fact — do not use as sole evidence for `strong`)

---

## 2. The Honest-Reframing Decision Rules

Every tailoring decision must pass through these rules before the plan is written. These rules have no exceptions.

### ALLOWED

**Reordering and reprioritising bullets within a role.**
Move the most relevant bullet to the top. If a role had five accomplishments and one is directly relevant to the posting, lead with it. Do not change the dates or the role title.

**Rewording real achievements using the posting's exact terminology.**
If the candidate "built automated deployment scripts" and the posting wants "CI/CD experience", rewrite the bullet to say "built and maintained CI/CD pipelines" — provided the scripts were genuinely part of a deployment workflow. Use `keywords[]` from the extracted schema as the target vocabulary.

> Example:
> Original bullet: "Wrote Python scripts to automate data cleaning."
> Posting keywords: "data pipeline automation", "ETL"
> Rewritten: "Automated ETL data-cleaning pipeline in Python, reducing pre-processing time by 60%."
> ✓ Allowed: same real work, terminology now matches the posting.

**Surfacing transferable skills with honest framing.**
If the candidate has not used the exact tool but has used a directly comparable one, note it transparently.

> Example: Posting requires "Tableau". Candidate has used "Power BI" extensively.
> Honest framing: "Experienced with Power BI for executive dashboards; familiar with Tableau's interface from evaluations."
> ✓ Allowed: the framing is true and the transferability is real.

**Adding real-but-omitted detail the user confirms.**
A CV may omit things that are genuinely part of the candidate's background. If gap analysis reveals a potential gap, ask the user first (see §3). If they confirm real experience, add it.

> Example: CV does not mention Docker. User confirms: "Yes, I use Docker every day locally." Add Docker to the skills list and to relevant bullets where accurate.
> ✓ Allowed: real experience, just not yet documented.

**Quantifying vaguely-stated real impact.**
If a bullet says "improved system performance" and the user can supply the actual numbers, update the bullet. If the user cannot recall specifics, use honest scope language: "improved performance for a system serving ~200k monthly users."

> ✓ Allowed: honest quantification is better than vague language, and honest approximation is better than silence.

---

### NOT ALLOWED

These actions constitute misrepresentation. Do not do them, do not suggest them, and do not accept user instructions to do them.

| Action | Why it is not allowed |
|---|---|
| Inventing a skill or tool the user has never used | Creates a falsehood the candidate cannot defend in an interview |
| Inflating a title ("Senior Engineer" when the contract says "Engineer II") | Verifiable via background check; also dishonest |
| Changing employment dates to hide a gap or shorten a short tenure | Employment dates are checked; altering them is fraud |
| Claiming sole credit for team accomplishments | Use "Co-led", "contributed to", "part of the team that" |
| Adding a posting keyword the candidate has no genuine experience with | Keyword stuffing that the interview will immediately expose |
| Claiming a degree, certification, or licence not held | Verifiable; fraudulent |
| Implying seniority, scope, or leadership not earned | "Led a cross-functional team" when the candidate was a participant, not the lead |
| Fabricating metrics ("improved performance by 40%") when the user cannot confirm any real number | An invented metric is a lie, not an approximation |

**The one-line rule:** Emphasis and honest reframing — yes. Misrepresentation — no.

**When in doubt:** If you are unsure whether a reframing crosses the line, ask the user. Do not make the call yourself; surface the question explicitly.

---

## 3. Phrasing Gaps to the User and Supplementary Questions

For every `missing` or `partial` requirement, decide which of two cases applies before writing anything into the tailoring plan.

### Case A: The CV may simply omit real experience

The requirement looks like something the candidate might have done but just never wrote down. Ask a targeted question.

**Decision signal:** The skill is foundational for the candidate's level/domain, or it appears in a context (a tool, a methodology) that is common in roles the candidate has held.

**Example supplementary questions by requirement type:**

| Gap type | Question to ask the user |
|---|---|
| Specific tool (e.g. Docker) | "Have you used Docker, even in personal projects, coursework, or a non-primary work context?" |
| Methodology (e.g. Agile/Scrum) | "Did any of your teams run sprints, standups, or retrospectives? Even informally?" |
| Leadership/mentoring | "Did you ever review others' code, onboard a new colleague, or lead a project even informally?" |
| Domain knowledge (e.g. fintech) | "Have you worked with financial data, payment flows, or regulatory requirements in any project or role?" |
| Degree/certification listed as required | "Do you hold this degree or certification, or anything equivalent? If not, are you currently pursuing it?" |
| Quantifiable outcome | "Do you recall the actual numbers for [outcome]? Even an approximate range is fine." |

Ask each question once, clearly, and wait for the answer before writing the tailoring plan. Do not ask the user to speculate about whether they could learn something quickly — the question is strictly about existing experience.

### Case B: A genuine gap

The candidate has genuinely never done this thing and cannot honestly claim related experience. Do not fabricate. Instead:

1. Record it in the tailoring plan as an `HONEST-GAP`.
2. Determine the mitigation from the options in §4.
3. Note the mitigation in the tailoring plan.

**Do not tell the user to pretend the gap does not exist in the cover letter.** The cover letter can address gaps directly and positively (see §4, HONEST-GAPS mitigation option: cover letter).

---

## 4. The Tailoring Plan

The tailoring plan is the structured output of gap analysis. It has exactly four lists. Produce it after the gap table is complete and all supplementary questions have been answered.

### Structure

```
TAILORING PLAN — [Role Title] at [Company]

─── AMPLIFY ─────────────────────────────────────────────────────
Move up / expand these real strengths; they are strong matches:
  1. [Requirement matched] → [Which experience to lead with; where to move it in the CV]
  2. …

─── REFRAME ─────────────────────────────────────────────────────
Reword these real experiences using the posting's vocabulary:
  1. [Current bullet / section] → [Suggested rewording] (target keyword: [keyword])
  2. …

─── KEYWORD-INSERT ──────────────────────────────────────────────
Weave these exact posting terms into the CV where truthful:
  (Only include a keyword here if the candidate has genuine experience with it)
  1. [Keyword] → [Where to insert: skills section / specific bullet / summary]
  2. …

─── HONEST-GAPS ─────────────────────────────────────────────────
These requirements remain weak after honest tailoring:
  1. [Requirement] — Genuine gap / partial coverage
     Mitigation: [choose one or more]
       • Transferable framing: "[Honest framing sentence to use in the CV or cover letter]"
       • Address in cover letter: "Acknowledge the gap; explain adjacent strength and learning trajectory."
       • Leave: "Do not mention. The gap is minor relative to strong matches and addressing it draws attention."
  2. …
```

### Mitigation options for HONEST-GAPS

| Option | When to use it |
|---|---|
| **Transferable framing** | A directly adjacent skill exists and can be honestly stated (e.g. Power BI → Tableau). The framing must be true. |
| **Address in cover letter** | The gap is material and likely to be noticed; proactively framing it with strength is better than leaving silence. E.g. "No fintech experience, but direct experience with high-volume transaction data in e-commerce." |
| **Leave** | The gap is minor (a nice-to-have, not a must-have), and the candidate is otherwise strong. Calling attention to a small gap where the rest is strong costs more than it gains. |

Never use "address in cover letter" for a fabricated or exaggerated claim. The cover letter can only say true things.

### Example tailoring plan (abbreviated)

```
TAILORING PLAN — Data Analyst at FinCo (London, hybrid)

─── AMPLIFY ─────────────────────────────────────────────────────
1. SQL proficiency → Lead the Role B bullet with the complex query work;
   move to top of that role's bullet list.
2. Stakeholder communication → Add a bullet to Role A about the quarterly
   board presentation (user confirmed this is real; not yet in CV).

─── REFRAME ─────────────────────────────────────────────────────
1. "Wrote Python scripts to automate data cleaning" →
   "Built Python-based ETL pipeline to automate data cleaning for 5M-row
   event datasets, cutting analyst prep time by 3 hours per sprint."
   (target keywords: ETL, event data, Python)

─── KEYWORD-INSERT ──────────────────────────────────────────────
1. "dbt" → Add to skills section (user confirmed: used dbt in a side
   project to model data for a personal analytics dashboard).
2. "SQL" → Already present; ensure it appears in the summary and the
   skills list, not just in a buried bullet.

─── HONEST-GAPS ─────────────────────────────────────────────────
1. Fintech/payments background — Genuine gap.
   Mitigation (address in cover letter):
   "My analytical work has been in e-commerce at scale (10M+ transactions/
   month), giving me direct exposure to high-volume transactional data
   quality and funnel analysis — skills that transfer directly to a
   fintech Growth team."

2. Looker familiarity — Nice-to-have; partial (used Tableau, not Looker).
   Mitigation (transferable framing):
   "Experienced with Tableau for executive reporting; familiar with Looker's
   data-model approach through self-directed evaluation."
```

---

## 5. Cross-References

**`cv-craft.md`** — consult for:
- Bullet pattern and action-verb bank when rewriting bullets in REFRAME
- ATS keyword mirroring rules (§4 of cv-craft.md) — the same principle drives KEYWORD-INSERT
- Honest reframing rules in §7 of cv-craft.md — identical standard governs this file

**Motivation letter / cover letter** — the same honest-reframing rule that governs the CV governs the cover letter. HONEST-GAPS mitigations that involve the cover letter must still be factually accurate. The cover letter may frame, contextualise, and project forward — it may not invent.

**Interaction between gap analysis and the final CV** — the tailoring plan is the bridge. Once approved, each item in AMPLIFY, REFRAME, and KEYWORD-INSERT translates to a specific edit in the CV. HONEST-GAPS drive the cover-letter strategy. Do not edit the CV before the tailoring plan is confirmed by the user.
