## Step 0 — Interview the user

Make a **single `AskUserQuestion` call** with up to 4 questions. Drop any question the user already answered in their opening request; keep the rest.

On a host without that tool — codex, another agent, or a Claude Code **subagent**, which does not get it either — the requirement is the SHAPE, not the tool: the same questions, in ONE message, each with concrete lettered options rather than an open prompt. Never degrade to one question per turn; a four-round interrogation before any work is what makes people abandon the run. With no interactive user at all, state the assumptions you proceeded on and carry them into the completion message. Measured: ten of the fifteen with_skill eval runs recorded this tool as unavailable. See `references/portability.md`.

1. **CV source** — Do you have a CV to use, or should I build one for you? (If they choose *build*, follow up: can you share an example whose style I should mimic, or should I design a clean template?)
2. **Target region** — offer the three clusters (see `references/cv-craft.md §2`): **(1) Anglophone developed** (US, Canada, UK, Ireland, Australia, NZ), **(2) EU / EEA** (NL, DE, FR, BE, ES, IT, Nordics, …), **(3) East & SE Asia** (China, Japan, Korea, Singapore, Malaysia, Thailand), plus **Other**. The region options ARE these clusters — do **not** promote an individual country to its own top-level choice even when it is a returning user's saved default (e.g. the **Netherlands is offered *inside* EU / EEA**, never as a separate region). Once they pick a cluster, confirm the **specific country** (it refines length/photo/personal-data conventions) and the **CV language**: English for Cluster 1; **English or the official local language** for Clusters 2 and 3 (match the posting when unsure). Set `meta.target_market`, `meta.language`, and — for a non-built-in language — `meta.headings`. This drives formatting, content conventions, and the rendered language.

   **A saved profile is never an answer to this question.** The instruction above to drop questions the user already answered means answered *by the user, in this request* — not found in a file. A master profile's `meta.target_market` records where a PREVIOUS application went; a CV is a record of what someone has done, and nothing in it says where they now want to work. Reading a region off it is the same class of error as reading a salary floor off a payslip.

   The cost is not cosmetic, because this one field arms the personal-data interlock. A returning user whose master says `nl` (Cluster 2) who is now applying in the US gets `_suppress_personal_data` returning False, and a photo or date of birth reaches a CV that US employers route straight to rejection. The reverse is just as wrong: inheriting a Cluster-1 market strips the Bewerbungsfoto a German employer expects. **Ask it every run, of every user, saved profile or not.**

   Discover mode carries the same rule for the same reason (`modes/discover.md`, "Before Step 0"). Assess and interview do not need it: both are handed a posting, and the posting states its own location.
3. **Output formats** — Markdown / PDF / .docx (multi-select).
4. **Motivation letter** — Do you want a cover/motivation letter as well?

## Step 1 — CV acquisition → `profile.yaml`

**Resume an in-progress application first.** Before anything else, check `~/.claude/job-profiles/*/applications/` for a workspace that matches this target (by company/role) and already contains a `posting.yaml` and/or `tailored-profile.yaml`. If one exists, a prior run was interrupted — show the user what's already there and offer to **resume from where it stopped** (e.g. posting already extracted → jump to gap analysis or tailoring) rather than rebuilding from Step 0. Only start fresh if they prefer it or no matching workspace exists.

**Check for existing profiles next.** Before building or parsing, check `~/.claude/job-profiles/` for any saved master profiles. If one or more exist, offer to reuse one (retargeting it for this new application) instead of rebuilding from scratch. A returning user can confirm a name and you jump straight to Step 2. New users with no saved profiles proceed to build/parse below.

**Reusing a master carries their experience forward, never their target.** `meta.target_market`, `meta.language` and any `contact.personal` in that file describe the application it was last built for. Re-ask the region and language (Step 0, question 2) before tailoring, and re-confirm any personal field the new market's cluster would treat differently — the master is the source of truth about the candidate, not about where they are applying.

The canonical profile schema is `assets/profile.example.yaml`. Everything downstream renders from a profile in this schema.

**If the user provides a CV** (file path or pasted text): parse it into the canonical schema. Show the parsed `profile.yaml` back to them and ask them to confirm or correct it before proceeding. Do not invent fields they didn't supply.

**If building from scratch:**
- If they gave a style example, mimic its structure and tone.
- Otherwise design a clean template guided by `references/cv-craft.md` (a light web search for current conventions is fine if useful).
- Either way, **interview the user section by section** — contact, summary, experience, education, skills, projects, etc. — until the profile is complete enough to render. Record only what they tell you; never fabricate.

**Enrich from linked artifacts, don't make the user retype.** When the profile names papers (titles/DOIs/arXiv) or links repositories (GitHub/GitLab), fetch and read them to extract concrete, truthful detail — what was built, the stack, scale, results, and the candidate's specific contribution — rather than asking the user to supply it. Use `WebFetch`/`WebSearch` (and the repo README / `gh` for GitHub). Only ask the user when the source is access-restricted (paywalled paper, private repo) or the fetch is blocked. Honest-only: extract the candidate's real contribution, never sole credit for a multi-author work. Full guidance: `references/gap-analysis.md §1` (Enrich from the candidate's papers and repositories).

**Offer to save the master** to `~/.claude/job-profiles/<name>/profile.yaml` so it's reusable across applications. This master profile is the source of truth and is **NEVER mutated by tailoring** — tailoring always works on a copy (Step 4).

**One candidate has one CV per language, and saving a new one never overwrites another language's.** A Chinese CV is a different document from an English one — different conventions, length rules and personal-data expectations — not a translation of it, so a user who supplies both has two masters: `profile.yaml` and `profile.<lang>.yaml` beside it. **Save through `python3 scripts/save_profile.py --name <name> --profile <file>`, never by writing the path yourself.** It resolves the slot by reading each existing master's own `meta.language` rather than trusting a filename, so a second English CV goes back into the legacy `profile.yaml` instead of becoming a duplicate; it backs up what it replaces; and it refuses a profile with no `meta.language`, because the unsuffixed slot is where a legacy English master usually lives and dropping an untagged CV there is the overwrite this is here to prevent. On the read side the same rule runs backwards: tailor from the master whose language matches the CV language chosen in Step 0, and say which file you took as the base. Reaching for the English master to build a Chinese CV throws away the one the user wrote for exactly that purpose.

## Step 2 — Job posting → structured requirements

Read `references/job-posting-extraction.md` and follow it.

- Try `WebFetch` on the posting URL.
- **Sanity-check the fetched content before extracting.** Many portals (LinkedIn / Workday / Greenhouse / Indeed) return a `200 OK` that is actually a login wall, cookie banner, or error page — not the posting. If the fetched text lacks recognizable posting structure (no responsibilities, no requirements, looks like a sign-in/search page), treat the fetch as **failed** — do not extract requirements from a login wall (you'd fabricate must-haves). Ask the user to paste the full posting text instead.
- If the fetch is blocked or thin, ask the user to paste the full posting text. **Terminal behavior:** if no posting can be obtained at all (URL dead, user can't paste), stop gracefully and say so — never invent a posting or proceed on guessed requirements.
- Extract the structured object — **all twelve names, in this order**, the same list
  as `SKILL.md`'s extraction field table and `modes/assess.md` §3:
  `role_title`, `company`, `seniority`, `location`, `must_haves`, `nice_to_haves`,
  `responsibilities`, `keywords`, `company_values_tone`, `red_flags`, `salary_range`,
  `application_type`.
  This list used to be nine. `company` is what `check_letter.py` verifies the letter's
  recipient against, and `application_type: structured` is the only signal that routes
  to the supporting-statement branch — the document a UK NHS or Civil Service panel
  actually scores. Dropping either is silent: the run simply never produces it.
- **Detect a structured / competency-based application.** If the posting splits requirements into **Essential / Desirable** criteria, names **behaviours / "Success Profiles"**, or instructs the applicant to "evidence how you meet each criterion" / provide a scored supporting statement (common for UK NHS, Civil Service, public-sector, and many academic roles), the deliverable is a criterion-mapped **supporting statement**, not just a CV. Read and follow `references/structured-applications.md`, and tell the user before proceeding.
- **Confirm the must-haves and keywords with the user** before moving on.
- After confirmation, write the extracted and confirmed posting to `posting.yaml` in the application workspace (defined in Step 4 below). This persists the posting for re-runs and the user's records.

## Step 3 — Gap analysis

Read `references/gap-analysis.md` and follow it.

- Build the **strong / partial / missing** table comparing the profile to the requirements, each row backed by evidence from the CV.
- **Run the responsibility-evidence pass** (`gap-analysis.md §1`): for each of the posting's `responsibilities[]`, classify the candidate's strongest real evidence `demonstrated / adjacent / none`. This aligns the CV to the *day-job*, not just the requirements checklist — a `demonstrated` responsibility buried in the CV becomes a LEAD-WITH instruction; a `none` on a core responsibility is a real fit gap to surface.
- **Show the before-tailoring FIT SNAPSHOT** (`gap-analysis.md`, keyword-coverage section): must-have coverage ("X of N strongly evidenced" + per-must-have table), responsibility match ("M of K core responsibilities demonstrated"), and the seniority/domain read in one line each, ending with an honest **apply verdict** (strong apply / worth applying / stretch / likely screen-out). Include the required disclaimer (a count of evidence, not a forecast of the outcome). This is the baseline the user compares against after tailoring.
- Present the **tailoring plan** as the four lists: **AMPLIFY / REFRAME / KEYWORD-INSERT / HONEST-GAPS**.
- **Non-standard candidate?** If the profile shows an employment gap >6 months, a domain/function switch vs. the posting, a seniority mismatch (over- or under-leveled), an extended absence/re-entry, very thin experience (student/new-grad), a **senior-leadership/executive** profile, a **military-to-civilian** transition, or an **internationally-trained/relocating** candidate, read `references/candidate-situations.md` and apply the matching honest-positioning playbook **before** building the tailoring plan. These are the candidates the skill helps most.
- **Non-technical or regulated role?** If the target is not a software/research/engineering job (e.g. clinical, sales, trades, legal, finance, public-sector, creative, teaching, hospitality), read `references/role-families.md` and apply that family's conventions — what to surface first and how competence is evidenced — when shaping the tailoring plan and section order. The metric-in-every-bullet default doesn't fit these; the qualitative-evidence rule in `gap-analysis.md §2` does.
- Where a gap might be closed with information the CV merely omitted (not invented), ask the user **targeted supplementary questions**. Honest only — never phrase a question as an invitation to fabricate.
- **Claim-provenance checkpoint (mandatory before writing any tailored content):** Every new skill, tool, scope, or technology claim introduced via REFRAME or KEYWORD-INSERT must trace to either (a) a specific line or field in the candidate's source profile, or (b) an answer the user gave during this session when asked a supplementary question. If neither source exists, the claim does NOT enter the CV — place it in HONEST-GAPS instead. See `references/gap-analysis.md` (claim-provenance checkpoint) for the full rule.

## Step 4 — Tailor the CV

**Application workspace.** All per-application files live under:

```
~/.claude/job-profiles/<name>/applications/<company>-<role>-<YYYY-MM-DD>/
```

This workspace contains: `tailored-profile.yaml`, `letter.yaml` (if any), `posting.yaml`, and the rendered outputs (`cv.md`, `cv.docx`, `cv.pdf`, `letter.*`). The master profile at `~/.claude/job-profiles/<name>/profile.yaml` is **NEVER** mutated.

### `claims.yaml` — write it as you tailor, not afterwards

The checkpoint in Step 3 is enforced by `scripts/check_claims.py`, and the ledger
it reads is `<workspace>/claims.yaml`. **Append a row at the moment you write each
REFRAME or KEYWORD-INSERT.** A term in the tailored CV that is neither in the
master profile nor sourced by a row here is `UNSOURCED`, and `check_apply.py` will
not let the package be delivered over it.

That matters because the wrong way out is the easy one. Faced with `UNSOURCED`
and no spec for this file, the two visible escapes are to delete a keyword the
candidate has genuinely earned — the under-selling failure this skill names as
its own — or to invent a row shape. Neither is necessary: the file is six keys.

```yaml
- term: PACS export                       # the exact string as it appears in the CV
  where: cv.md:experience[0].bullets[1]   # artifact and place it was inserted
  source_kind: session-answer             # profile-line | session-answer | fetched-artifact
  source_ref: mock/transcript-2.md#Q1     # a real path under the workspace, or a profile field
  session_date: "2026-08-09"              # YYYY-MM-DD
  retracted: null                         # null while live; true once withdrawn
```

- **All six keys on every row.** `retracted` is required even when null: in a
  schema where "absent" and "not retracted" look the same, a withdrawn claim
  leaves no scar, and the scar is why the field exists.
- **Three source kinds, and there is no fourth.** `profile-line` (already in
  `profile.yaml` — the ordinary case), `session-answer` (the candidate said it,
  in a recorded session), `fetched-artifact` (a paper, repo or page this run
  fetched).
- **Append-only.** A claim that turns out to be wrong is marked
  `retracted: true`, never deleted. A retracted row stops being a source:
  `check_mock.py` refuses to let it discharge an `UNSOURCED-FACT`.
- `source_ref` must resolve. For a `session-answer` row, `check_mock.py` requires
  it to name a file that exists under the workspace **and** to contain the term.

A worked file, including a retracted row, is in `assets/claims.example.yaml`.

- Write the tailored copy to `<workspace>/tailored-profile.yaml`. **Never edit the master.**
- Apply the tailoring plan: reorder, re-emphasize, weave in exact keywords **where truthful**, and trim to the market's length conventions (see `references/cv-craft.md`).
- **Section order:** confirm the order fits the candidate and target (`cv-craft.md §1`, **including its 'Deciding between the templates' block** — read it whenever the candidate matches more than one template, which a PhD applying to industry always does). The renderer auto-leads with Education for a current PhD/researcher (or a no-experience student) and with Experience for everyone else; when that's wrong for this application, set `meta.section_order` explicitly in the tailored profile. **What decides it is how RELEVANT the degree is to the target role, not whether the employer is academic or industrial.** A doctorate in the role's own field is a credential the reader is looking for and belongs near the top whoever the employer is; an industry engineering target leads with Experience even for a PhD *only when the doctorate is not in that role's domain*, or once the candidate has 3+ years of formal experience. Academic/research targets lead with Education and surface Publications early. Say which template you applied and offer the alternative — this is the candidate's call to make.
- **Projects vs. Experience (de-duplicate):** work done inside a job belongs as bullets under that role, not restated in a separate Projects section; Projects holds only genuinely standalone work (thesis, coursework, open-source, competitions). Cut a Projects section that merely echoes the day job or lists stale coursework. See `cv-craft.md §9`.
- **Links:** keep links in `contact.links` keyed by service (`scholar`, `github`, `linkedin`, …) so the renderer shows a clean label ("Google Scholar", "GitHub") hyperlinked to the URL — never the raw URL as visible text. Use the `{label, url}` form for anything unusual. See `cv-craft.md §8`.
- **Bullet-quality pass:** After tailoring, run a quick pass over every bullet — each should open with a strong action verb, carry a real metric/scope/outcome where truthful, and be **concise (one line ideally, two at most; front-load the point; cut filler words)** so a skimming recruiter reads it. Strip clichés ("results-driven", "proven track record", "synergy", "leveraged"). For bullets lacking a number, apply the quantification fallback ladder from `references/gap-analysis.md §2`. Honest-only still applies — do not invent metrics. See `cv-craft.md §3` for the conciseness rule.
- **AI-uniformity pass:** Run the full-CV coherence check from `references/gap-analysis.md` (post-tailoring AI-uniformity check): verb variety, sentence-structure variety, voice and specificity, prose quality. Make targeted repairs before delivering. The goal is a CV that reads as one human's real work history, not a keyword-filled template.
- **Show the after-tailoring FIT SNAPSHOT** (same format as Step 3 — coverage, responsibility match, apply verdict) so the user sees the delta. Include the same disclaimer.
- **File-format note:** For ATS/portal submission, `.docx` is the safer default (see `references/cv-craft.md §4`). PDF is for the human-facing copy or when explicitly requested by the posting. If the portal gives a choice and the posting doesn't specify, submit `.docx`.
- Render each requested format, running the command once per format:

  ```bash
  python scripts/render_cv.py <workspace>/tailored-profile.yaml --format <md|docx|pdf> --out <workspace>/cv.<ext>
  ```

- **The PDF always ships with its `.tex` source.** Each `--format pdf` run writes `cv.tex` next to `cv.pdf` (whether or not the compile succeeds), so deliver both — the candidate can hand-tune typography or recompile later. List the `.tex` among the outputs in Step 7.
- If the PDF run warns about a missing LaTeX engine: tell the user the Markdown and .docx outputs are still produced, the `.tex` was emitted, and they can get the PDF by installing a LaTeX engine (`tectonic` recommended) and compiling the `.tex`. That case, and only that case, exits 0.
- **If the PDF run exits non-zero and reports dropped characters, there is no PDF and there must not be one.** The engine reports a `Missing character` per glyph it could not typeset and still exits 0 by itself, so the renderer scans for them and refuses; `cv.md` and `cv.docx` are unaffected and will look perfect while the PDF would have lost letters out of the candidate's own name. Do not hand over a PDF from a previous run, and do not describe the PDF as delivered. Read the codepoints it names, set `meta.main_font` (Latin) or `meta.cjk_font` (CJK) in the tailored profile to a font installed on this machine, and re-render — or ship `.docx` + `.tex` and say plainly that the PDF could not be produced.
- **Japan rirekisho fork:** if the target is Japan AND a traditional/domestic employer (or the user asks for a 履歴書), the standard form differs from the Western CV — render it with `scripts/render_rirekisho.py` per `references/rirekisho.md`. Collect the `jp:` personal-data fields honestly from the user (DOB, address, photo, furigana, 志望の動機 — never invent them), compute `age` from DOB using today's date, output `.docx` (the authentic form; export to PDF from Word/LibreOffice), and keep the Western CV as the companion 職務経歴書. For an international/foreign-capital employer, the normal Western CV (Step 4 above, in Japanese or English) is correct — don't force a rirekisho.

  ```bash
  python scripts/render_rirekisho.py <workspace>/tailored-profile.yaml --format docx --out <workspace>/rirekisho.docx
  ```

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

## Step 6 — Hiring-pipeline review loop (non-negotiable)

**Three independent judges** must **all** return `PASS` before the package is interview-ready. They model the real hiring funnel — **ATS → Recruiter/HR → Hiring Manager** — and fail in *different* directions, so the CV must be **machine-findable, recruiter-skimmable & eligible, and genuinely strong** to clear all three:

**This is an actor–critic loop.** Each round: the three critics judge **in parallel** (one message, three `Agent` calls); if any rejects, the **actor — you, the orchestrator — applies targeted edits** addressing only the flagged points, re-renders, and re-judges **all three**. The actor stays inline (not a separate subagent) because it already holds full context and is the only party that can ask the candidate honest supplementary questions. **Stop the moment all three pass (early exit — often round 1).** The speed comes from parallel critics + targeted edits, not from spawning more agents. (Conceptually the funnel is sequential — ATS gates first — but requiring *all three* to pass yields the same end state, so run them concurrently.)

- **ATS Screener (machine lens)** — `agents/ats-screener.md` — must-have keyword coverage and parse/format sanity on the CV only. Output: `VERDICT`, `COVERAGE`, `MISSING_OR_WEAK`, `FORMAT_ISSUES`, `TOP_FEEDBACK`.
- **Recruiter / HR Screener (fast human screen)** — `agents/recruiter-screener.md` — fast-skim must-have fit, readability, written communication, **logistics/eligibility** (location, work authorization, seniority band, salary), and targeting. The broad first human pass. Output: `VERDICT`, `SCORES`, `SCREEN_NOTE`, `TOP_FEEDBACK`, `SUPPLEMENTARY_QUESTIONS_FOR_CANDIDATE`.
- **Hiring Manager (deep human lens)** — `agents/hiring-manager.md` — real fit, seniority/leveling, evidence/credibility, clarity, narrative coherence, the standout signal, and (if present) the cover letter's authenticity. Output: `VERDICT`, `SCORES`, `LEVELING`, `STANDOUT_SIGNAL`, `TOP_FEEDBACK`, `SUPPLEMENTARY_QUESTIONS_FOR_CANDIDATE`.

The three lenses are deliberately distinct: ATS = literal findability, Recruiter = fast/broad/logistics, Hiring Manager = deep technical fit. Some overlap is expected; each owns its lane (the agent files state the boundaries).

**Dispatch all three in parallel** — as fresh independent **Agent** subagents in a **single message (three tool calls at once)** each round, so they run concurrently. They share no state, so parallel dispatch is both faster and avoids ordering bias; never run one, read its verdict, then run the next. Each has **no other context**, so paste everything it needs:

**The mechanism is replaceable; the isolation is not.** On a host with no subagent tool, dispatch three concurrent fresh invocations of that host's own CLI instead — `codex exec "$(cat agents/ats-screener.md) …"` — because `agents/*.md` are standalone personas that need no particular dispatcher. A judge that watched the tailoring is not a second opinion. If the host can open no fresh context at all, run the loop anyway and say plainly, in the completion message and the run notes, that the judges shared the author's context and their verdicts are weaker evidence than this loop's shape implies — never report three PASSes as a review that happened at arm's length when it did not. `references/portability.md`.

- *ATS Screener:* the **full text** of `agents/ats-screener.md` + the structured posting + the tailored CV Markdown (`<workspace>/cv.md`) + the **CV language**. (No letter — ATS doesn't parse letters.)
- *Recruiter / HR Screener:* the **full text** of `agents/recruiter-screener.md` + the structured posting (`<workspace>/posting.yaml`) + the tailored CV Markdown (`<workspace>/cv.md`) + the motivation letter (`<workspace>/letter.md`) if produced, else `No letter provided.` + the **target market & CV language**.
- *Hiring Manager:* the **full text** of `agents/hiring-manager.md` + the structured posting + the tailored CV Markdown (`<workspace>/cv.md`) + the motivation letter if produced, else `No letter provided.` + the **target market & CV language** (e.g. "Germany / German") so it calibrates conventions and reads the CV in the right language.

**Japan rirekisho fork:** the judges are calibrated to the Western CV / ATS pipeline. For a Japan rirekisho package, run all three on the **companion Western CV / 職務経歴書** (the keyword-and-fit document) as usual, and review the **rirekisho form itself** with the completeness/correctness check in `references/rirekisho.md` (required fields present, 学歴・職歴 chronological and gap-explained, no fabricated personal data) — report that to the user instead of an ATS coverage %. Do not feed the rirekisho `.docx`/`.md` to the ATS screener.

**Parsing each verdict (apply exactly, to all three):**

1. In each judge's response, find the last line beginning with `VERDICT:` followed by `PASS` or `REJECT` (case-insensitive). If absent or ambiguous (anything other than exactly `PASS`/`REJECT`), treat that judge as `REJECT` and re-dispatch it.
2. ATS Screener: also read `COVERAGE`, `MISSING_OR_WEAK`, and `FORMAT_ISSUES`.
3. Recruiter / HR Screener: also read `SCORES`, `SCREEN_NOTE`, `TOP_FEEDBACK`, and `SUPPLEMENTARY_QUESTIONS_FOR_CANDIDATE`. The recruiter's questions are often **logistics** (work authorization, relocation) — surface them to the user.
4. Hiring Manager: also read `SCORES`, `LEVELING`, `STANDOUT_SIGNAL`, `TOP_FEEDBACK`, and `SUPPLEMENTARY_QUESTIONS_FOR_CANDIDATE` (a single `  - none` bullet means no questions). `LEVELING` and `STANDOUT_SIGNAL` are advisory — they do not change the verdict, but relay them to the user and act on them when tailoring (e.g. lead the summary with a buried standout signal; address an under-leveled read).

**Combined verdict: PASS only if ALL THREE judges return `PASS`.** If any is `REJECT`, the round is a `REJECT`.

**If `REJECT` — per-round sequence (order is mandatory):**

1. **Edit first (targeted):** Merge the `TOP_FEEDBACK` from all three judges (plus the ATS `MISSING_OR_WEAK` / `FORMAT_ISSUES` and the Recruiter's logistics/readability flags) and apply edits that address **only the flagged points** — do not re-tailor sections the judges didn't fault. Apply to `<workspace>/tailored-profile.yaml` (and `<workspace>/letter.yaml` if present). Ask the user any `SUPPLEMENTARY_QUESTIONS_FOR_CANDIDATE` from the Recruiter or Hiring Manager — honestly, never inviting fabrication. **A keyword the ATS screener flags as missing goes into the CV ONLY if the candidate genuinely has it** (the claim-provenance checkpoint still applies); otherwise it stays in HONEST-GAPS. **Re-run the claim-provenance checkpoint on every edit made this round before re-rendering** — any term added to satisfy an ATS REJECT must cite its source (a profile line or a user answer this session). The correct response to an ATS gap you cannot honestly close is to let the loop fail at round 3 and report it — *never* to insert an ungrounded keyword. A coverage gate failing because the candidate genuinely lacks must-haves is a true result, not a problem to engineer around.
2. **Re-render second:** Re-render ONLY the affected outputs from the just-edited YAML (never re-send stale rendered files).
3. **Re-judge third:** Dispatch all three fresh judges with the newly rendered files. Never re-dispatch with the old rendered version.

**Honest-gap early-stop (don't grind a loop you cannot win honestly).** After any round, diagnose *why* a judge still rejects before spending another round:
- If the **only** remaining cause is must-haves the candidate **genuinely lacks** — terms the claim-provenance checkpoint forbids you to add — then no honest edit can move that number. Looping again would only pressure you toward the one thing the skill forbids (inserting an ungrounded keyword). **Stop now**, even before round 3, and report it as an honest gap, not a failure of the package. This is the *expected* outcome for a genuine stretch application, and it is a true result — surface it, don't engineer around it.
- Keep iterating only while the rejects are about things you *can* honestly fix: ordering, emphasis, surfacing a buried real qualification, readability, missing logistics notes, a real keyword the candidate has but the CV omitted.

**Loop until ALL THREE pass, the honest-gap early-stop fires, or 3 rounds** (early-exit the instant all three pass — don't run extra rounds). If not all passed, **STOP** and report honestly — but **distinguish the two very different reasons a package can end un-passed**, because they mean opposite things for the user:
- **Poorly built** — a judge rejects over something fixable that tailoring should have caught (weak ordering, vague bullets, an unaddressed logistic, a real-but-hidden qualification). This is a tailoring miss to own and, budget permitting, fix.
- **Honest stretch** — the package is as strong as it can truthfully be, and the only thing keeping a `>= 4` deep-fit gate from passing is that the candidate is genuinely a notch off the role (the Step 3 apply verdict was "stretch"/"worth applying"). This is **not** a defective application: it is a well-built application for a reach role, and the user may well still submit it. Say so plainly — "this is a strong submission for a stretch; the gap is real and the honest framing is X" — rather than reporting a bare "failed review."

In both cases give the final per-judge verdicts, the ATS coverage % (or `n/a`), the remaining honest gaps, and concrete next steps (skills to gain, certifications, better-fitting roles). **Never fake a pass.**

Tell the user **all three verdicts and the ATS coverage %** (report it verbatim — it may be `n/a`, e.g. a rirekisho or a posting with no extractable must-haves) each round.

## Step 7 — Finalize

- List the workspace path (`~/.claude/job-profiles/<name>/applications/<company>-<role>-<YYYY-MM-DD>/`) and all output files (CV and letter in each requested format). When PDF was requested, list the `.tex` source alongside the PDF — it's a deliverable too.
- Show the **final FIT SNAPSHOT delta**: baseline (before tailoring) vs. final (after tailoring) — coverage, responsibility match, and the apply verdict.
- Summarize what changed during tailoring and why.
- Note any **remaining honest gaps** the user should be aware of going into the application and interview.
- **Consistency reminder:** the tailored CV now states specific things about the candidate's roles, scope, and dates. Remind them to make sure their **LinkedIn and any portal profile don't contradict it** — recruiters cross-check, and a mismatch reads as dishonesty. (A reminder only — do not scrape or fetch their profile.)
- Remind them the reusable **master profile** is saved at `~/.claude/job-profiles/<name>/profile.yaml` and can be retargeted for the next application.

### Step 7.6 — Offer what comes next

Apply ends here, and the user is now at the point the other three modes exist
for. **Ask which they want, in one `AskUserQuestion` with selectable options —
and run none of them unasked** (`SKILL.md`, "Hand-off"):

- **`interview`** — rehearse this package and debrief it. The natural next step:
  the CV now makes specific claims, and the mock round is where the candidate
  finds out whether they can defend them under one follow-up.
- **`assess`** — judge another posting before building for it.
- **`discover`** — find more roles worth looking at.

Offer only modes whose inputs exist, and say plainly if the loop ended
un-passed: a `blocked` or `honest_stretch` package makes `interview` more useful,
not less, because the gaps are known going in.

### Step 7.5 — Interview-readiness brief

Produce the brief in `references/interview-prep.md` (write it to `<workspace>/interview-brief.md`). It is **near-free** — you already hold everything it needs: the claim-provenance map (every reframed claim → its real source), the judges' `SUPPLEMENTARY_QUESTIONS_FOR_CANDIDATE`, and the HONEST-GAPS. For each REFRAMED/AMPLIFIED claim, give the source fact and a "be ready to explain…" prompt; for each honest gap, the truthful framing if asked; and carry over the recruiter/manager questions. Honest only — if a claim can't be truthfully defended, that's a tailoring error: walk it back on the CV.

## Toolchain note

- Scripts need their dependencies: `pip install -r requirements.txt` (PyYAML, python-docx).
- PDF output needs a LaTeX engine — `tectonic` is recommended. Without it, **Markdown and .docx still work**, and the renderer emits a `.tex` file you can compile later.

## Entry conditions

An assessment should exist. Its verdict decides how this mode opens, and only one
of the five stops it:

- `强烈建议投` / `值得投` — enter.
- `可以冲刺` (stretch) and `大概率被筛掉` (likely_screen_out) — **enter.** These do
  not block: building a solid application for a role the candidate is reaching for
  is not a defect, and refusing here would systematically underserve exactly the
  people this skill is for — stretch candidates and career switchers. Say the
  verdict out loud, then do the work well.
- `硬性阻断` (blocked) — **ask once**: "this is a legal-level barrier, not a
  phrasing problem — still want to apply?" If the user says yes, proceed and do the
  work properly. Ask once, not every step; a second ask is nagging, and a silent
  refusal is deciding for them.
- `证据不足—不出结论` — this is a refusal, not a level. Say what could not be read
  (the posting, the CV, an illegible region of an image source) and get that first.

No assessment at all is not a blocker either: run apply, and say plainly that no
fit assessment was made.

## On entering this mode

Record the entry before doing anything else — `check_apply.py` requires it, and the
hash is what proves the file you read is the file on disk:

```bash
python3 scripts/enter_mode.py --workspace <workspace> --mode apply \
    --because "<why apply, in one line, from what the user asked>"
# The master path comes from scripts/paths.py, never hand-built — and it takes
# the CV LANGUAGE, because one candidate can have one master per language.
# Without it this resolves to profile.yaml every time, and the provenance gate
# then checks a Chinese CV against an English master: real skills read as
# UNSOURCED, and skills the candidate does not have in this language pass.
#   python3 -c "import sys;sys.path.insert(0,'scripts');import paths;print(paths.master_for_language('<name>', '<cv language>'))"
python3 scripts/check_claims.py --workspace <workspace> \
    --master "$(python3 -c "import sys;sys.path.insert(0,'scripts');import paths;print(paths.master_for_language('<name>', '<cv language>'))")" \
    --record
```

## Gate commands, in the order they run

```bash
# after tailoring, before dispatching the judges
python3 scripts/check_personal_data.py --workspace <ws>
python3 scripts/check_claims.py --workspace <ws>
python3 scripts/lint_cv.py --workspace <ws>
python3 scripts/check_letter.py --workspace <ws>          # required once letter.yaml exists
python3 scripts/check_pages.py --workspace <ws>           # required once cv.pdf exists
python3 scripts/check_word_limits.py --workspace <ws>     # required once supporting-statement.md
                                                          # exists — and for a structured
                                                          # posting that has none, which is
                                                          # a missing deliverable, not a skip
python3 scripts/check_render_freshness.py --workspace <ws> --round <n> \
    --record <ws>/cv.md <ws>/posting.yaml <ws>/letter.md  # letter.md only if produced

# ... dispatch all three judges in parallel, save each reply verbatim ...

python3 scripts/parse_verdicts.py --workspace <ws> --round <n> \
    --ats <ws>/judge-<n>-ats.txt --recruiter <ws>/judge-<n>-recruiter.txt \
    --hiring-manager <ws>/judge-<n>-hiring-manager.txt
python3 scripts/check_render_freshness.py --workspace <ws> --round <n>
# ... at the end of the mode ...
python3 scripts/check_apply.py --workspace <ws>
```

**The `--record` runs are setup; the runs without it are the checks.** `check_claims
--record` and `check_render_freshness --record` store a baseline and verify nothing —
their receipt says `baseline_recorded`, and `check_apply.py` reports a gate whose LATEST
receipt is one of those as `NOT_VERIFIED`. So the order above is not cosmetic: run each
verifying pass **after** the last `--record` for that gate. On a round 2 or a resumed
run this bites — re-recording the dispatch hashes for the new round leaves the previous
round's verification behind, and only the new round's verifying run clears it.

**`check_apply.py` also fails on any gate in `journal.jsonl` whose latest receipt says
`fail`** — including gates it does not require by name. A gate that ran, found something
and was left failing blocks the package; fix the finding and re-run that gate.

**Every round runs the WHOLE pre-dispatch block again, not just the tailoring.** After any
edit to `tailored-profile.yaml` or to a rendered artifact — which is what a round 2 IS —
re-run `check_personal_data`, `check_claims`, `lint_cv`, and `check_pages`/`check_letter`/
`check_word_limits` where they apply, before dispatching the judges again.

This is not a style preference. `check_apply.py` re-hashes each required gate's recorded
`input_hashes` against the bytes on disk and reports `STALE_RECEIPT` when they differ: a
gate's pass is a claim about the file it read, and after an edit it is a claim about a file
that no longer exists. A round-2 package whose gates were only run in round 1 will be
refused, correctly, at the very end — after the judges have been paid for.

## `honest-stop.yaml` — required whenever the loop ends without a PASS

The three-judge loop ending un-passed means one of two opposite things, and they emit
the identical machine signal. Writing this file is how the run says which:

```yaml
classification: honest_stretch     # honest_stretch | poorly_built
verdict: stretch                   # strong_apply | worth_applying | stretch |
                                   # likely_screen_out | blocked
reason: >-
  The package is as strong as it can truthfully be. The only unmet must-have is
  five years of clinical PACS integration, which the candidate genuinely lacks.
evidence:                          # the judge findings the classification rests on
  - "hiring_manager requirement_match: 3/5 — no clinical PACS work"
  - "ats COVERAGE: 78% (7 present, 1 partial of 9 must-haves)"
```

- `honest_stretch` — the package is as strong as it can truthfully be and the candidate
  is genuinely a notch off the role. **Not** a defective application: say so plainly —
  "this is a strong submission for a stretch; the gap is real and the honest framing is
  X" — rather than reporting a bare "failed review".
- `poorly_built` — a judge rejected over something fixable that tailoring should have
  caught. A tailoring miss to own and, budget permitting, fix.

## Hand the artifacts over — `deliver.py`, not a sentence in the final message

A workspace under `~/.claude/job-profiles/` is where the skill works, and it is
not where a person looks. Nobody browses a dotfile directory, and a path pasted
into a chat message is gone the moment the session scrolls. So the last step of
every mode is a command, not a claim:

```bash
python3 scripts/deliver.py --workspace <ws>
```

It copies this round's readable artifacts **straight into `~/Downloads`**, named
`<slug>-<file>`, renders every Markdown to **PDF as well**, and prints the paths.
Quote them in the completion message. The slug prefix is not a folder in
disguise: two rounds both produce `shortlist.md`, and a bare name would have the
second silently overwrite the first.

**The PDF is verified, not trusted.** `pandoc --pdf-engine=tectonic` on a Chinese
document exits 0, prints a warning nobody reads, and writes a PDF whose every CJK
glyph is a box — measured, 528 characters in and 0 read back. So a CJK document
gets a CJK font chosen by probing what this machine actually has, and every PDF
is read back with `pdftotext` and compared against its source before it counts as
delivered. One that lost characters is deleted and reported; the Markdown still
ships.

**It is a copy, and the split is deliberate.** `raw/`, `journal.jsonl` and the
adapter `.err` files stay in the workspace: they are the provenance chain, they
are unreadable to a person, and an audit has to read them where they live rather
than in an export that may have gone stale.

**Do not move the workspace itself.** `scripts/paths.py` owns that layout,
`modes/apply.md`'s resume-an-unfinished-run lookup finds work BY the path shape,
and `check_claims.py` fingerprints the master profile at that path. `~/Downloads`
is also a directory the user's own housekeeping empties.

`deliver.py` exits 0 or 2, never 1 — there is no such thing as a delivery
finding. Exit 2 with `DELIVER_DEST_UNWRITABLE` is the macOS case worth knowing:
`~/Downloads` sits behind TCC, it can start refusing writes part-way through a
session, and `os.access` says yes while the write fails. The script probes by
writing a real file. When it exits 2, say so and offer `--to` with somewhere
else — do not silently leave the artifacts undelivered.
