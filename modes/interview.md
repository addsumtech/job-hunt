# Mode: interview

**Entry:** the workspace holds an application package, **or** the user has a posting plus
a CV and says they have an interview.

**Reads:** `posting.yaml`, `cv.md`, `tailored-profile.yaml`, `fit-assessment.*`,
`interview-brief.md`, `claims.yaml`.
**Interview artifacts:** `mock/`. Also author the client `report.md` required by
the delivery contract below. Plus two append-only write-backs: a `## Walk-back list`
section on `interview-brief.md`, and `source_kind: session-answer` rows on `claims.yaml`.
Nothing else in the workspace is modified, and `profile.yaml` is never touched.

## Supplementary public research

Use `references/supplementary-sources.md` when official web/news, WeChat
public accounts or relevant GitHub projects can fill a concrete career evidence
gap. It defines source selection, availability checks and evidence quality.
These sources supplement formal posting evidence; select only what the current
question needs.

## 0. Before the first question

**Record the mode entry first, before reading anything else:**

```bash
python3 scripts/enter_mode.py --workspace <workspace> --mode interview \
    --because "<why interview, in one line, from what the user asked>"
```

This writes the content hash of this file to `journal.jsonl`. `scripts/check_mock.py`
fails the round with `NO_MODE_ENTRY` if the record is absent and `MODE_FILE_CHANGED` if
this file was edited after you read it. That is not bookkeeping: this file is layer 1.5,
loaded unconditionally on entering the mode rather than "if relevant", and a file skipped
with nothing reporting it is a file that has been silently deleted.

Then read `references/interview-shapes.md` in full. It holds the market × family loop
shapes, the four band descriptors, and both closed tag sets — you cannot write
`mock/assessment-<n>.md` without them, and you cannot pick a realistic round order without
the shapes.

Then confirm three things with the user, in one message:

1. **Market** — ask; never infer it from a place name. `cn | nl | de | uk | us | other`.
2. **Role family** — from `references/role-families.md`. If it is not one of the nine, ask
   the one question that resolves the shape: *"In your field, what does the employer make
   you do live — talk, demonstrate, be scored against written criteria, or be role-played
   at?"*
3. **Round type for this session** — `behavioural | technical | design | hr`. One per
   session; see §3.

## 1. Fix the shape

From `references/interview-shapes.md`, state the loop the candidate is walking into: the
rounds, in the local vocabulary, with who is in the room. Say plainly which rounds this
mode **cannot** simulate (手撕代码 under a watching interviewer, an in-person MMI circuit,
a whiteboard chalk talk) rather than running a thin imitation of them.

Give the interviewer a **named persona** drawn from that shape — a 交叉面 interviewer from
another department who has not read the CV closely; a Bar Raiser from outside the team; a
panel member scoring one named Success Profiles behaviour at the grade in the advert; a
Dutch hiring manager who will ask about anything questionable on the CV without preamble.
The persona costs nothing and is most of what makes a text interview feel like anything.

## 2. Seed `mock/question-log.yaml`

Each question records its source: `generated`, `scraped`, `judge-supplementary`
(carried over from the CV judges' `SUPPLEMENTARY_QUESTIONS_FOR_CANDIDATE`), or
`user-provided` (questions or an existing transcript supplied by the user).

For `user-provided` questions, preserve the original input in the workspace and
keep the questions and answers verbatim. They are user-supplied material, not
independently verified evidence of the employer's process. When asked to debrief
an existing round, analyse those answers; do not invent a new conversation or
relabel them as generated questions. All assessment and provenance checks still apply.

**Generated questions are the high-value ones.** *"You wrote that you cut deploy time 40% —
how did you measure that?"* exists in no archive, and it is the question that catches an
over-tailoring the three CV judges passed. Build the generated set to cover every must-have
in `posting.yaml`.

**Scraped material sets SHAPE; generated material sets CONTENT.** They are not competing
sources of the same thing. Reach for a scraped item when you need a fact about the
employer's process you cannot derive from the posting: a named ritual (交叉面, HRBP面, Bar
Raiser, 宣讲会, 群面, a specific take-home), the round count and order, who is in the room,
the pacing.

### Scraped material — the rules

```
Every scraped item is (a) opened with `detail` for untruncated text — a `search` row is
  elided and must never be quoted, (b) stamped with its `time` in question-log.yaml, and
  (c) shown to the candidate with that date.
Anything older than ~12 months may be used for SHAPE (round count, order, ritual names)
  but is never quoted as a specific technical question.
COUNTRY RULE. Never use a scraped item whose company entity sits in a different country
  from the posting, unless the post itself names that country. Log it under `rejected:`
  with `reason: wrong_country` so the filter is visible.
Never paste a scraped post's ANSWER to the candidate — questions only. A 面经 that
  includes the poster's own answer is a script, and handing over a script is the exact
  thing the anti-coaching rules forbid.
Filter advertising. Posts that open with a course pitch, a 辅导 offer, or a contact email
  are commercial material wearing a 面经 costume. Log them `reason: advertising`.
If the adapter returns 403 or "need login", report the source as unavailable and generate
  instead. Do not log in to work around it.
`nowcoder papers --company/--job` filters are inert (verified: three different filter
  values returned byte-identical rows). Use `papers` as a company/role index only.
```

**Why the COUNTRY RULE is first among equals.** `opencli nowcoder search "ASML 面试"`
returns three real posts, all describing that company's **China entity** — 宣讲会, 笔试,
then 二面 and an HR call. That is not the Veldhoven loop. The company name matches, the
content is genuine, the process is the wrong one, and **nothing about it looks wrong.** The
same held for Philips. This is the most dangerous failure available in this source.

### `mock/question-log.yaml`

`check_mock.py` reads this file. Keys marked **scraped-only** are required on any row with
`source: scraped` and ignored elsewhere.

| Key | Meaning |
|---|---|
| `round` | integer, the round this log belongs to |
| `posting_country` | ISO-2 country of the **posting** — without it the country rule cannot fire |
| `questions[].id` | `Q1`, `Q2`, … — must match the transcript's `## Q<n>` headings |
| `questions[].text` | the question as it will be asked |
| `questions[].source` | `generated` \| `scraped` \| `judge-supplementary` \| `user-provided` |
| `questions[].asked` | whether it was actually put to the candidate |
| `questions[].source_site` | **scraped-only** — e.g. `nowcoder` |
| `questions[].source_id` | **scraped-only** — the id `detail` was called with |
| `questions[].source_url` | **scraped-only** |
| `questions[].source_time` | **scraped-only** — the ISO timestamp from `detail`, verbatim |
| `questions[].entity_country` | **scraped-only** — ISO-2 of the entity the post describes |
| `questions[].country_named_in_post` | **scraped-only** — true only if the post itself names the posting's country |
| `questions[].use` | **scraped-only** — `question` (may be quoted) or `shape` (structure only) |
| `rejected[].reason` | `wrong_country` \| `stale_specific` \| `advertising` \| `needs_login` \| `answer_included` |

<!-- example: question-log.yaml -->
```yaml
round: 2
posting_country: NL
questions:
  - id: Q1
    text: Walk me through the reconstruction pipeline you owned.
    source: generated
    asked: true
  - id: Q2
    text: You wrote that you rewrote the recon loop for GPU batching — how did you measure the change?
    source: judge-supplementary
    asked: true
  - id: Q3
    text: 讲一下 variational network 的展开步数怎么定的
    source: scraped
    source_site: nowcoder
    source_id: "ce23c4da4205"
    source_url: https://www.nowcoder.com/discuss/ce23c4da4205
    source_time: "2026-08-03T11:12:22"
    entity_country: NL
    country_named_in_post: true
    use: question
    asked: true
rejected:
  - id: R1
    text: "ASML 宣讲会 → 笔试 → 二面 → HR 电话面 timeline"
    source: scraped
    source_site: nowcoder
    source_id: "057523b2ca9d"
    source_time: "2026-08-06T11:06:49"
    entity_country: CN
    reason: wrong_country
  - id: R2
    text: "27届秋招…可以了解下算法项目辅导"
    source: scraped
    source_site: nowcoder
    source_id: "a1b2c3d4e5f6"
    source_time: "2026-07-30T08:00:00"
    entity_country: CN
    reason: advertising
```

## 3. Run ONE round, inline

**The interviewer is you, in this conversation.** A spawned subagent has no channel to ask
a question and wait for the human — `agents/hiring-manager.md:21` pastes its inputs at
dispatch time and `:97` requires it to end with a fixed block. That is a mechanical fact,
not a preference, and it decides the architecture before any trade-off analysis.

**One round per dispatch.** Finish the round, assess it, write the artifacts, and stop.
Round n+1 starts fresh.

**FLUSH THE TRANSCRIPT AFTER EVERY ANSWER.** Append the question and the answer to
`mock/transcript-<n>.md` the moment the candidate finishes speaking — not at the end of the
round. This buys pause/resume for free, keeps the assessors reading a *file* rather than
this conversation, and means a crashed session loses one answer instead of a round. The
transcript is a raw capture: **never edit it.** Every downstream claim's source chain
terminates here.

**One `## Q<n> — <the question>` heading per question, and the `<n>` matches
`question-log.yaml`.** Those headings are the only thing `ref=` can point at: without
them `check_mock.py` has nothing to check an assessor's references against, and it says
so with `NO_QUESTION_HEADINGS` rather than passing them all in silence.

Ask from the log, then go where the answer leads. The log is seed material — its coverage
value is realised by **auditing it after the round**, not by reading from it during. A
question bank cannot follow up on an answer it did not anticipate, and "held under probe"
is the only band above `asserted` that means anything.

While you interview, the anti-coaching rules in SKILL.md bind on every turn: never write an
answer for the candidate, never ask a leading question, never build a question on a premise
the CV does not support, and never rehearse a gap into a non-gap.

<!-- example: transcript-<n>.md -->
```markdown
# Mock transcript — round 2
Round type: technical
Market: nl
Family: ml-engineering
Persona: Sanne de Vries, MR reconstruction team lead — direct, asks for numbers

## Q1 — Walk me through the reconstruction pipeline you owned.
**Interviewer:** Walk me through the reconstruction pipeline you owned.
**Candidate:** At the university hospital I owned the offline recon pipeline for a 3T scanner study.

## Q2 — What did you change about it, and what happened as a result?
**Interviewer:** What did you change about it, and what happened as a result?
**Candidate:** I replaced the per-slice loop with a batched GPU implementation.
```

## 4. Assess — two passes, deliberately different inputs

Dispatch **both** assessors in one message (two `Agent` calls, in parallel). Each gets
exactly the files in its row and nothing else:

| Pass | Agent file | Given | **Deliberately NOT given** |
|---|---|---|---|
| 1 — transcript | `agents/mock-assessor-transcript.md` | `mock/transcript-<n>.md`, `posting.yaml`, `cv.md` | `interview-brief.md`, `claims.yaml` — so it cannot credit the candidate for a source fact they never said out loud |
| 2 — provenance | `agents/mock-assessor-provenance.md` | `mock/transcript-<n>.md`, `claims.yaml`, `interview-brief.md` | the rubric — so it cannot drift into grading, which is what makes a provenance-holding assessor lenient |

Two passes fed different inputs is what turns the honesty tripwire from an intention into a
mechanism. Do not "helpfully" hand pass 1 the brief.

Then assemble `mock/assessment-<n>.md`: **both output blocks copied in verbatim**, plus a
short human-readable summary above them. Never hand-edit an assessor's block.

### Recover an invalid assessor block

If `scripts/check_mock.py` reports `PARSE_FAIL`, `MISSING_BLOCK`, or
`QUOTE_NOT_IN_TRANSCRIPT`, use this bounded recovery:

1. Identify the failed pass from the block name in the diagnostic:
   `MOCK-ASSESSMENT-V1` is transcript; `MOCK-PROVENANCE-V1` is provenance. A quote can
   exist elsewhere in the transcript and still be invalid: `ref=Q1` must quote the
   candidate's answer under that same heading, not Q2 or the interviewer.
2. Preserve the original failed assessment, raw assessor output, gate stdout/stderr,
   and journal receipt under `mock/raw/recovery-<n>/` before replacing anything. The
   `raw/` directory keeps failed drafts and audit logs out of `deliver.py` exports.
   Keep the original receipt in `journal.jsonl`; the recovery adds evidence, never
   erases it.
3. Re-dispatch only the failed pass, in a fresh context, with the same agent prompt and
   byte-identical source files from its row above. Add only that pass's gate diagnostics
   and an instruction to produce a complete block whose quotes belong to their cited
   candidate answers. Never supply the other pass's output, diagnostics, or input pack.
   Keep any valid pass's block byte-identical. If both failed, reassess each separately
   with its own permitted pack. Allow **at most one corrective reassessment per failed
   pass per round**, including parse, missing-block, and quote failures together.
4. Preserve the corrective dispatch inputs and raw output alongside the failure. Copy
   its new block verbatim, update session artifacts under §5–6 where required, and
   re-run the full gate. Never hand-edit a block, including its `ref=` or `quote=`.
   Never change the transcript or candidate facts to make a quote validate.
5. If it still fails, stop and report the remaining findings and both gate receipts.
   Do not loop until green or call the round complete. A new assessor finding is handled
   honestly under §5–6; it is not a reason to erase the finding or reroll the assessor.

<!-- example: assessment-<n>.md -->
```markdown
# Mock assessment — round 2

Two passes ran on this transcript with deliberately different inputs.

MOCK-ASSESSMENT-V1
ROUND: 2
ROUND-TYPE: technical
MARKET: nl
FAMILY: ml-engineering
FINDING: tag=VAGUE-OUTCOME | ref=Q2 | quote=It went really well after that.
BAND: dimension=outcome | value=asserted | ref=Q2 | quote=It went really well after that.
COVERAGE: status=evidenced | must_have=MRI reconstruction pipelines in a clinical setting
SHAPE: status=rehearsed | round_name=technisch gesprek met de vakinhoudelijke manager
END-MOCK-ASSESSMENT-V1

MOCK-PROVENANCE-V1
ROUND: 2
FINDINGS: none
END-MOCK-PROVENANCE-V1
```

## 5. Write the session artifacts

**`~/.claude/job-profiles/<name>/answer-bank.md`** — the profile-level file, not a
per-application one. It is the only artifact that compounds across applications. One entry
per real story, in the candidate's **own words as actually spoken**, with a `- source:` line
that traces the load-bearing fact to `profile.yaml`, to `interview-brief.md`'s provenance
map, or to a session answer with its date. `check_mock.py` fails an entry with no
`- source:` line: an entry the candidate cannot trace is worse than no entry, because they
will say it out loud in the real room believing it was vetted.

<!-- example: answer-bank.md -->
```markdown
# Answer bank

## Batched GPU reconstruction on the 3T study
- serves: "tell me about an optimisation you made"; round 2 Q2
- source: profile.yaml:experience[0].bullets[2] — "rewrote the recon loop for GPU batching"
- session: 2026-08-09 — applications/asml-mr-recon-engineer-2026-08-09/mock/transcript-2.md#Q2
- S: offline recon for a 3T scanner study at the university hospital
- T: the per-slice loop was the bottleneck in the nightly batch
- A: replaced the per-slice loop with a batched GPU implementation
- R: open loop — the measured change was not stated in the room
- R2 (reflectie): profile before optimising, and write the baseline down first
```

**`mock/open-loops.md`** — every question the candidate could not answer, in **three
buckets**, because they have three completely different actions:

1. **a fact you have but did not recall** → go and find it before the real interview;
2. **a genuine gap** → use the honest framing already chosen in `interview-brief.md`;
3. **a tailoring error** → the claim comes off the CV (this bucket feeds §6).

Merging them into one "weak areas" list destroys the artifact.

**`mock/answer-guide.md`** — per-question guidance, and the one artifact in this mode
where being useful pulls directly against the load-bearing rule. A question list with
nothing about what a good answer contains is half a deliverable. But the questions that
most need a model answer are exactly the ones the candidate has no evidence for, and a
satisfying answer to those can only be written by inventing the experience — so the
distinction is made mechanical rather than left to tone.

**Never write the candidate's answer in their voice.** What ships is a skeleton they
fill: the STARR slots carrying only facts already in the profile, what the interviewer
is listening for, and which defect tag the answer fails on. A first-person paragraph is
a script, it gets recited, and a recited answer collapses on the first Dutch follow-up —
which is `PROBE-COLLAPSE`, arriving in the real room instead of this one.

`## ` is reserved for entries. A section divider written as a heading is read as an
entry with no fields and fails — which is the right way round: letting some `## `
headings be exempt would make "call it a divider" a way to ship guidance with no
source. Use bold prose or `### ` for structure.

Every entry carries three lines `check_mock.py` reads:

| Line | Meaning |
|---|---|
| `- row:` | the requirement id(s) in `fit-assessment.yaml` this answer serves; several are comma-separated |
| `- basis:` | `evidenced` \| `honest_gap` — there is no third value and no default |
| `- source:` | where the load-bearing fact comes from: a `profile.yaml` path, or a session answer with its date |

The gate reads `fit-assessment.yaml` and fails `GUIDE_GAP_AS_EVIDENCED` when an entry
serves a row scored `gap` or `no_evidence` and declares itself `evidenced`. There is no
default for `basis` on purpose: defaulting picks a side of the honesty distinction on
the author's behalf, and the safe-looking default is the unsafe one. An entry naming an
evidenced row alongside a gapped one does not launder the second through the first.

For a `honest_gap` entry the content is the framing from `references/interview-prep.md`
§2 — the nearest real thing the candidate HAS done, then how they would come at the
requirement — and never a narrated instance of work they have not done. That is not
rehearsing a gap into a non-gap; it is the only honest answer to the question, and
withholding it leaves the candidate to improvise on exactly the questions that will
decide the round.

When the workspace has no `fit-assessment.yaml` the cross-check cannot run and says so
on stderr (`NO_ASSESSMENT_TO_CHECK_AGAINST`); the shape checks still run.

**`mock/cheatsheet.md`** — one page. The stories, one line each; the 2–4 honest gaps with
their exact framing; the questions still unanswered; the candidate's questions for them;
the loop shape with round names in the local vocabulary. If it exceeds one page it has
failed.

## 6. Write-backs

**(a) Walk-back list.** Append a `## Walk-back list` section to `interview-brief.md` for
every CV claim that collapsed under **one** follow-up. Then **offer to re-run the tailoring
edit and re-render** — that is the point of the section; a list nobody acts on is a note.

An undefendable claim is a **CV bug, not a rehearsal topic.** This is the mechanism that
fires `references/interview-prep.md`'s over-reach rule, which until now had no trigger: the
three CV judges read a page, and the page does not stammer.

<!-- example: walk-back list -->
```markdown
## Walk-back list

### WB-1 — "Rewrote the offline reconstruction loop for GPU batching, cutting runtime 40%."
- transcript: mock/transcript-2.md — Q3
- quote: Honestly it might have been closer to a third, I am not sure any more.
- defect: PROBE-COLLAPSE
- softened: "Rewrote the offline reconstruction loop for GPU batching (measured speed-up; exact figure not retained)."
- status: proposed
```

`check_mock.py` requires this section whenever `PROBE-COLLAPSE`, `OVER-CLAIM`, or
`CONTRADICTED` fired, and requires an entry quoting **each** such finding.

**(b) Promote a confirmed-but-absent fact.** An `UNSOURCED-FACT` usually resolves to "it's
true, it's just not on my CV". Ask the candidate where it came from **before** it enters the
answer bank. If the answer is that it is real, that is a genuine gap-analysis finding: append
a row to `claims.yaml` with `source_kind: session-answer` — an already-permitted provenance
— and route it back into the tailoring plan.

```yaml
- term: PACS export
  where: tailoring-plan.md:promoted-from-mock
  source_kind: session-answer
  source_ref: mock/transcript-2.md#Q1
  session_date: "2026-08-09"
  retracted: null
```

If instead it was drift under pressure, it goes on the walk-back list. Either way it is
resolved, never silently kept.

## 7. Gate

Run:

```
python3 scripts/check_mock.py --workspace <workspace> --round <n>
```

Exit 0 = the round holds up. Exit 1 = findings on stdout, one per line. Exit 2 = it could
not run — fix the input, never proceed. **Do not report the round as complete without
quoting the `check_mock` receipt from `<workspace>/journal.jsonl`.** A gate that was skipped
produces no output, and that looks exactly like a gate that passed.

The `MOCK-ASSESSMENT-V1` block must actually assess something: at least one `BAND:`
(`NO_BANDS`), at least one `SHAPE:` (`NO_SHAPE`), and one `COVERAGE:` row per must-have in
`posting.yaml` (`NO_COVERAGE_ROW`, which names the uncovered one). `mock/open-loops.md` and
`mock/cheatsheet.md` must exist and be non-empty (`NO_OPEN_LOOPS`, `NO_CHEATSHEET`). None of
these applies to `MOCK-PROVENANCE-V1`: `ROUND:` plus `FINDINGS: none` is its documented clean
shape. Until 2026-08 none of them was checked at all, so headers plus `FINDINGS: none` in both
blocks was a fully passing round — an assessor that produced nothing produced this exit 0.

## 8. Round n+1

Carry forward an **open-loops summary** only — the unresolved probes and the questions that
wobbled — not the full transcript. The transcript is on disk; the assessors read it there.
That is the context-cost mitigation, and it is why the transcript is flushed after every
answer rather than held in this conversation.

## Published employer rubric — the one place a number is honest

Where the employer publishes its own scale — UK Civil Service Success Profiles behaviours at
the grade named in the advert, an NHS values framework, a university person specification —
you may walk the candidate through **that** scale, in the employer's own wording, **attributed**,
as a checklist of what the panel is told to look for:

> the Civil Service scale used here reads: 4 = "Adequate positive evidence and any negative
> evidence would not cause concern"

**Never as a prediction of the mark.** Quoting an employer's scale is reporting; applying it
as a verdict is fabrication. Everywhere else, no score, no percentage, no probability, no
"strong candidate", no invented scale — see the banned-vocabulary block in SKILL.md.

## Hand the artifacts over — `deliver.py`, not a sentence in the final message

Deliver the debrief report. The CV used by the assessors remains source material;
`deliver.py` does not copy or render it in this mode unless the user explicitly
requests the existing application documents and you pass `--include-applications`.

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

Before drafting, read `references/report-writing.md`; revise the report for clear
recommendations, specific reasons and actionable advice, then inspect the rendered
pages. Preserve source facts, required labels and the user's approved formatting.

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


## Self-check before reporting the session complete

- [ ] `references/interview-shapes.md` was read this session
- [ ] `mock/transcript-<n>.md` was appended to after **every** answer, and never edited
- [ ] both assessors were dispatched, each with exactly its own pack (`agents/mock-assessor-transcript.md`, `agents/mock-assessor-provenance.md`)
- [ ] `mock/assessment-<n>.md` contains both blocks verbatim
- [ ] `mock/question-log.yaml`, `mock/open-loops.md`, `mock/answer-guide.md`, `mock/cheatsheet.md` and the profile-level `answer-bank.md` are written
- [ ] every `answer-guide.md` entry carries `- row:`, `- basis:` and `- source:`, no entry is a first-person script, and no entry serving a gapped row claims `evidenced`
- [ ] every walk-back and every promoted claim from §6 is on disk
- [ ] `scripts/check_mock.py` exited 0 and its receipt is in `journal.jsonl`

**Voice.** The debrief tells someone what they got wrong. `SKILL.md`, "How this skill writes to the user", governs its prose — quote them rather than characterise them, and say the finding before the cushioning.
