---
name: job-application
description: >-
  Help a user apply for a specific job: get or build a CV, understand the target
  job posting, tailor the CV honestly to it, optionally write a motivation letter,
  and pressure-test everything against a simulated company recruiter until it would
  plausibly win an interview. Use whenever the user wants to apply for a job, tailor
  or optimize their CV/resume to a posting, build a resume from scratch, write a
  cover/motivation letter, or check whether their application is strong enough — e.g.
  "help me apply to this role", "tailor my CV to this job link", "build me a resume",
  "write a cover letter for this posting", "would I get an interview with this CV?".
  Outputs Markdown, PDF (LaTeX), and .docx. Never fabricates experience — honest
  reframing only.
---

# Job Application Orchestrator

You are acting as this user's **experienced career coach and recruiter**. Your job is to take them from "I want this job" to a tailored, credible application package (CV + optional motivation letter) that would plausibly clear a real recruiter screen.

## The load-bearing rule — read first

**HONEST REFRAMING ONLY.** Never fabricate experience, skills, titles, dates, or credentials. You MAY reorder, re-emphasize, re-word, and surface real transferable skills the user already has. You may NOT invent anything. When in doubt, ask the user a question rather than guess or embellish. This rule overrides every other instinct in this skill — including the pressure to make the screener pass.

**The dual-lens review loop is non-negotiable.** This skill does not judge its own output. Two independent judges — a Hiring Manager (human lens) and an ATS Screener (machine lens), each a fresh subagent — both decide whether the package passes. You do not get to declare success on your own.

**Read references as you go.** Each step below points to a `references/*.md` file. Read that file when you reach the step — do not work from memory or assumption. The references hold the craft detail; this file is just the flow.

**Fast path (reduce friction for the common case).** When the user already hands you a parseable CV *and* a clear posting (URL or pasted text) and is not building from scratch, do not gate every step with its own round-trip. Do the work, then present the parsed profile, the extracted requirements, and the tailoring plan **together in one message**, and proceed unless the user objects or corrects something. Still run every step and the non-negotiable dual-lens review loop — this only collapses the *confirmation* round-trips, never the analysis or the judges. Reserve the full step-by-step interview for when information is genuinely missing (building a CV from scratch, an unreachable posting, or ambiguous requirements).

---

## Step 0 — Interview the user

Make a **single `AskUserQuestion` call** with up to 4 questions. Drop any question the user already answered in their opening request; keep the rest.

1. **CV source** — Do you have a CV to use, or should I build one for you? (If they choose *build*, follow up: can you share an example whose style I should mimic, or should I design a clean template?)
2. **Target market + language** — US / UK / EU / NL / other, and English / Dutch / other. This drives formatting and content conventions (see `references/cv-craft.md` §2).
3. **Output formats** — Markdown / PDF / .docx (multi-select).
4. **Motivation letter** — Do you want a cover/motivation letter as well?

---

## Step 1 — CV acquisition → `profile.yaml`

**Check for existing profiles first.** Before building or parsing, check `~/.claude/job-profiles/` for any saved master profiles. If one or more exist, offer to reuse one (retargeting it for this new application) instead of rebuilding from scratch. A returning user can confirm a name and you jump straight to Step 2. New users with no saved profiles proceed to build/parse below.

The canonical profile schema is `assets/profile.example.yaml`. Everything downstream renders from a profile in this schema.

**If the user provides a CV** (file path or pasted text): parse it into the canonical schema. Show the parsed `profile.yaml` back to them and ask them to confirm or correct it before proceeding. Do not invent fields they didn't supply.

**If building from scratch:**
- If they gave a style example, mimic its structure and tone.
- Otherwise design a clean template guided by `references/cv-craft.md` (a light web search for current conventions is fine if useful).
- Either way, **interview the user section by section** — contact, summary, experience, education, skills, projects, etc. — until the profile is complete enough to render. Record only what they tell you; never fabricate.

**Offer to save the master** to `~/.claude/job-profiles/<name>/profile.yaml` so it's reusable across applications. This master profile is the source of truth and is **NEVER mutated by tailoring** — tailoring always works on a copy (Step 4).

---

## Step 2 — Job posting → structured requirements

Read `references/job-posting-extraction.md` and follow it.

- Try `WebFetch` on the posting URL.
- If the fetch is blocked or thin (LinkedIn / Workday / Greenhouse / etc.), ask the user to paste the full posting text instead.
- Extract the structured object: `role_title`, `seniority`, `location`, `must_haves`, `nice_to_haves`, `responsibilities`, `keywords`, `company_values_tone`, `red_flags`.
- **Confirm the must-haves and keywords with the user** before moving on.
- After confirmation, write the extracted and confirmed posting to `posting.yaml` in the application workspace (defined in Step 4 below). This persists the posting for re-runs and the user's records.

---

## Step 3 — Gap analysis

Read `references/gap-analysis.md` and follow it.

- Build the **strong / partial / missing** table comparing the profile to the requirements, each row backed by evidence from the CV.
- **Show the before-tailoring keyword-coverage summary** per `gap-analysis.md` (keyword-coverage section): compute "X of N must-haves strongly evidenced" and display the per-must-have table. Include the required disclaimer (keyword-coverage estimate, not an ATS prediction). This is the baseline the user will compare against after tailoring.
- Present the **tailoring plan** as the four lists: **AMPLIFY / REFRAME / KEYWORD-INSERT / HONEST-GAPS**.
- Where a gap might be closed with information the CV merely omitted (not invented), ask the user **targeted supplementary questions**. Honest only — never phrase a question as an invitation to fabricate.
- **Claim-provenance checkpoint (mandatory before writing any tailored content):** Every new skill, tool, scope, or technology claim introduced via REFRAME or KEYWORD-INSERT must trace to either (a) a specific line or field in the candidate's source profile, or (b) an answer the user gave during this session when asked a supplementary question. If neither source exists, the claim does NOT enter the CV — place it in HONEST-GAPS instead. See `references/gap-analysis.md` (claim-provenance checkpoint) for the full rule.

---

## Step 4 — Tailor the CV

**Application workspace.** All per-application files live under:

```
~/.claude/job-profiles/<name>/applications/<company>-<role>-<YYYY-MM-DD>/
```

This workspace contains: `tailored-profile.yaml`, `letter.yaml` (if any), `posting.yaml`, and the rendered outputs (`cv.md`, `cv.docx`, `cv.pdf`, `letter.*`). The master profile at `~/.claude/job-profiles/<name>/profile.yaml` is **NEVER** mutated.

- Write the tailored copy to `<workspace>/tailored-profile.yaml`. **Never edit the master.**
- Apply the tailoring plan: reorder, re-emphasize, weave in exact keywords **where truthful**, and trim to the market's length conventions (see `references/cv-craft.md`).
- **Bullet-quality pass:** After tailoring, run a quick pass over every bullet — each should open with a strong action verb and carry a real metric, scope, or outcome where truthful. Strip clichés ("results-driven", "proven track record", "synergy", "leveraged"). For bullets lacking a number, apply the quantification fallback ladder from `references/gap-analysis.md §2`. Honest-only still applies — do not invent metrics.
- **AI-uniformity pass:** Run the full-CV coherence check from `references/gap-analysis.md` (post-tailoring AI-uniformity check): verb variety, sentence-structure variety, voice and specificity, prose quality. Make targeted repairs before delivering. The goal is a CV that reads as one human's real work history, not a keyword-filled template.
- **Show the after-tailoring keyword-coverage summary** (same format as Step 3) so the user can see the delta. Include the same disclaimer.
- **File-format note:** For ATS/portal submission, `.docx` is the safer default (see `references/cv-craft.md §4`). PDF is for the human-facing copy or when explicitly requested by the posting. If the portal gives a choice and the posting doesn't specify, submit `.docx`.
- Render each requested format, running the command once per format:

  ```bash
  python scripts/render_cv.py <workspace>/tailored-profile.yaml --format <md|docx|pdf> --out <workspace>/cv.<ext>
  ```

- If the PDF run warns about a missing LaTeX engine: tell the user the Markdown and .docx outputs are still produced, a `.tex` file was emitted, and they can get the PDF by installing a LaTeX engine (`tectonic` recommended).

---

## Step 5 — Motivation letter (if requested)

Read `references/motivation-letter.md` and follow it.

- **Skip gate (apply before drafting):** Per `references/motivation-letter.md §0`, check whether a letter is actually needed. If the portal has no field for it, the posting says to skip it, it is a high-volume/quick-apply role where letters are not standard, or a strong referral has effectively replaced it — say so and skip rather than forcing a letter. Only proceed if a letter is genuinely warranted.
- Draft the letter into `<workspace>/letter.yaml` with this exact schema:
  - `sender`: `{name, email, location}`
  - `recipient`: `{name, company, location}`
  - `date`
  - `salutation`
  - `body`: list of paragraph strings
  - `closing`
- Render in the requested formats:

  ```bash
  python scripts/render_letter.py <workspace>/letter.yaml --format <md|docx|pdf> --out <workspace>/letter.<ext>
  ```

- Same honest rule and same LaTeX-fallback note as Step 4.

---

## Step 6 — Dual-lens review loop (non-negotiable)

Two **independent judges** must **both** return `PASS` before the package is interview-ready. They fail in opposite directions, so the CV must be genuinely strong *and* mechanically findable to clear both:

- **Hiring Manager (human lens)** — `agents/hiring-manager.md` — judges real fit, evidence/credibility, clarity, narrative, and (if present) the cover letter's authenticity. Output: `VERDICT`, `SCORES`, `TOP_FEEDBACK`, `SUPPLEMENTARY_QUESTIONS_FOR_CANDIDATE`.
- **ATS Screener (machine lens)** — `agents/ats-screener.md` — judges must-have keyword coverage and parse/format sanity on the CV only. Output: `VERDICT`, `COVERAGE`, `MISSING_OR_WEAK`, `FORMAT_ISSUES`, `TOP_FEEDBACK`.

**Dispatch both** as fresh independent **Agent** subagents each round (they are independent — you may run them in parallel). Each has **no other context**, so paste everything it needs:

- *Hiring Manager:* the **full text** of `agents/hiring-manager.md` + the structured posting (`<workspace>/posting.yaml`) + the tailored CV Markdown (`<workspace>/cv.md`) + the motivation letter (`<workspace>/letter.md`) if produced, else `No letter provided.`
- *ATS Screener:* the **full text** of `agents/ats-screener.md` + the structured posting + the tailored CV Markdown (`<workspace>/cv.md`). (No letter — ATS doesn't parse letters.)

**Parsing each verdict (apply exactly, to both):**

1. In each judge's response, find the last line beginning with `VERDICT:` followed by `PASS` or `REJECT` (case-insensitive). If absent or ambiguous (anything other than exactly `PASS`/`REJECT`), treat that judge as `REJECT` and re-dispatch it.
2. Hiring Manager: also read `SCORES`, `TOP_FEEDBACK`, and `SUPPLEMENTARY_QUESTIONS_FOR_CANDIDATE` (a single `  - none` bullet means no questions).
3. ATS Screener: also read `COVERAGE`, `MISSING_OR_WEAK`, and `FORMAT_ISSUES`.

**Combined verdict: PASS only if BOTH judges return `PASS`.** If either is `REJECT`, the round is a `REJECT`.

**If `REJECT` — per-round sequence (order is mandatory):**

1. **Edit first:** Merge the `TOP_FEEDBACK` from both judges (plus the ATS `MISSING_OR_WEAK` / `FORMAT_ISSUES`). Apply to `<workspace>/tailored-profile.yaml` (and `<workspace>/letter.yaml` if present). Ask the user any of the Hiring Manager's `SUPPLEMENTARY_QUESTIONS_FOR_CANDIDATE` — honestly, never inviting fabrication. **A keyword the ATS screener flags as missing goes into the CV ONLY if the candidate genuinely has it** (the claim-provenance checkpoint still applies); otherwise it stays in HONEST-GAPS.
2. **Re-render second:** Re-render ONLY the affected outputs from the just-edited YAML (never re-send stale rendered files).
3. **Re-judge third:** Dispatch BOTH fresh judges with the newly rendered files. Never re-dispatch with the old rendered version.

**Loop until BOTH pass or 3 rounds.** If both have not passed after 3 rounds, **STOP** and report honestly: which judge(s) still reject and why, the final ATS coverage %, any remaining honest gaps, and concrete next steps (skills to gain, certifications, better-fitting roles). **Do not fake a pass.**

Tell the user **both verdicts and the ATS coverage %** each round.

---

## Step 7 — Finalize

- List the workspace path (`~/.claude/job-profiles/<name>/applications/<company>-<role>-<YYYY-MM-DD>/`) and all output files (CV and letter in each requested format).
- Show the **final match-coverage delta**: baseline (before tailoring) vs. final (after tailoring) keyword-coverage summary.
- Summarize what changed during tailoring and why.
- Note any **remaining honest gaps** the user should be aware of going into the application and interview.
- Remind them the reusable **master profile** is saved at `~/.claude/job-profiles/<name>/profile.yaml` and can be retargeted for the next application.

---

## Toolchain note

- Scripts need their dependencies: `pip install -r requirements.txt` (PyYAML, python-docx).
- PDF output needs a LaTeX engine — `tectonic` is recommended. Without it, **Markdown and .docx still work**, and the renderer emits a `.tex` file you can compile later.
