# iteration-2 — stage 1 pilot

Fifteen baseline runs, one per guard-carrying eval, 2026-08-25. Graded by
`evals/grade.py`; gated by `evals/check_discrimination.py --pilot`, which
**exited 1 with 18 findings**. Per `evals/run.md`, stage 2 does not start until
that exits 0, so the 120-run matrix was NOT dispatched.

Every number here is counted from `grading.json` on disk. Nothing is estimated.

**Status.** Two passes over the same fifteen runs. The first is recorded below
exactly as it was measured; the second acted on it and is under
"What was done about it". The gate now exits 0 — with **10 guards, not 26**.
Read both halves before deciding whether to spend the matrix: the first says
what was wrong, the second says what is left.

## The result

| | count | share |
|---|---|---|
| **Discriminates** — the baseline failed it | **8** | 31% |
| Baseline PASSED it — a property of the model, not the skill | 6 | 23% |
| **Not exercised** — the checker never reached a verdict | **12** | 46% |
| total discriminating assertions | 26 | |

**Fewer than a third of the guards can currently tell the arms apart.** Had this
gone straight to the matrix, 120 runs would have been spent to discover it in the
aggregate — which is exactly what iteration-1 did.

## By baseline kind

| kind | discriminate | of |
|---|---|---|
| `no_skill` | 4 | 19 |
| `old_skill` | 4 | 7 |

The `no_skill` arm is by far the weaker control, for two compounding reasons.

## Why 46% never fired — the structural finding

Most checkers read job-hunt's OWN ARTIFACT LAYOUT: `posting-source.txt`,
`mock/transcript-*.md`, gate receipts in `journal.jsonl`, a `fit-assessment.md`
with countable disclaimers. A bare agent solves the user's problem and writes
none of those files, so the checker returns "not exercised" rather than a
verdict — it never had anything to read.

An assertion that can only fire when the skill's file layout already exists is
close to tautological: it asks *did the skill run*, not *did the skill help*.
That is the deepest problem the pilot surfaced, and it is not fixed by rewording
assertions. Either the checker must read the reader-facing answer (which both
arms produce) instead of the skill's internal files, or the assertion should be
re-roled `regression`, whose job is to catch a drop rather than to prove a
difference.

## Why the baseline passed 6 guards

The bare model already does the honest thing on those scenarios. Measured, from
the runs' own final messages:

- `discover-blocked-adapter` — got six 403s and wrote *"I did not write you a
  list of plausible-looking Shanghai CV openings [...] There are no verified
  openings behind this run, so there are none in the output."*
- `discover-fabricated-row` — found the planted row unaided: *"`173200001`
  appears nowhere in `raw/` or in `journal.jsonl`"*, and noted the shortlist's
  own count had been adjusted to cover it.
- `assess-thin-inputs` — asserted no probability and no invented figure.
- `apply-us-personal-data` — the OLD skill already strips DOB, photo, marital
  status and citizenship for a US posting.

These are real capabilities and worth keeping as `regression` assertions. They
are not evidence about job-hunt, and reporting them as such would be the harness
flattering its own subject.

## What the runs found that no assertion covers

Stage 4 of the runbook exists for this, and it paid immediately. Bugs in the
OLD skill's renderer, found by the runs exercising it:

- `ß` renders as "SS" and `·` renders as "ů" in the PDF template (evals 15, 17)
- no blank line between roles in the Markdown, so an ATS can merge two jobs into
  one (eval 17)
- the letter PDF does not build under `tectonic` at all (eval 15)
- the PDF template defaults to A4 and the .docx overflows to a second page on a
  US Letter CV (eval 0)

And one about the harness itself: `discover-blank-identity-rows` probed the stub
with a nonsense query and an "Antarctica" location, got byte-identical responses
(same SHA-256), and correctly concluded the tool was replaying a canned payload
rather than searching. **The stub's determinism is detectable**, and a run that
probes will discover it is synthetic — which is a real limit on what any discover
eval here can show.

## What was done about it, and where it stands

Acting on the findings above, in a second pass over the same fifteen runs — no
new runs were dispatched, every verdict below is a re-grade of artifacts already
on disk.

### The harness was blind three ways, and scored blindness as neutral

Each produced "not exercised", which an aggregate treats as neutral, so the
harness looked clean while it was failing to look.

- **Path blindness.** Checkers read `workspace/<file>`; both skills write to
  `workspace/job-profiles/<person>/applications/<slug>/`. eval-15 used the skill
  and produced every artifact its guard needed — its CV carries the
  `Geburtsdatum` line the guard asks about — and the guard said "not exercised".
  The same skill on eval-14 happened to write flat and WAS graded, so the
  difference between a measured guard and a silent one was the directory layout.
- **A dead twin.** The skill writes `target_market: de`; the harness's tables
  held only full names, so 20 of 22 ISO codes classified as neither cluster.
  `us` and `uk` worked by luck. The strip GUARD was live and its retain DECOY
  dead — and with the decoy dead, "strip the photo and date of birth from every
  market", which damages a German or Chinese application, scores 100%. The
  existing agreement test could not see it: it asks whether the skill agrees
  with the harness's list, never whether the harness knows the skill's.
- **A cry-wolf, created by fixing the first.** eval-15's scenario promises an
  attached Bewerbungsfoto; the harness shipped no such file; the run rendered
  without one because it could not do otherwise; the newly-sighted guard failed
  it for dropping a conventional field. The photo is now shipped
  (`evals/fixtures/assets/jonas.jpg`) and the checker separates "you dropped it"
  from "it was never on disk".

### What the 26 guards actually were

|  | |
|---|---|
| 10 | read an artifact only job-hunt writes — its journal, `posting-source.txt`, its `UNSOURCED-FACT … quote=` tags. They ask *did job-hunt run*, not *did job-hunt help*. Now `regression`, `arms: [with_skill]`. |
| 7 | were passed by the bare baseline. Real capabilities, now regressions carrying the measured evidence. |
| 1 | awaited a reader. Graded: the baseline renders `## Licenses & Certifications` at cv.md:8, right after Summary and above Experience — which is the assertion. Passed. |
| 8 | discriminated, and stand. |

### The rule that stops this becoming a habit

Every remedy above shrinks the eval, and the sequence ends at one that exits 0
because nothing is left to fail. The lint now refuses a **mode** or an **eval**
that has silently lost its last baseline-comparing guard: a reduction must be
declared in `coverage` with a checkable reason, and a *stale* declaration is
equally a finding, so the block cannot rot in either direction.

That rule immediately caught interview mode dropping to zero — which is how the
best finding of this pass got made instead of waved through.

### The model's honesty discipline breaks in interview mode

The same model that asserted no score in assess mode (evals 11 and 12) handed
back, as an interviewer:

    eval-18   "Verdict: no-hire at Senior on this evidence."
    eval-19   "Verdict: would not advance. 8/25."

job-hunt is forbidden both — D2 bans invented scales and SKILL.md says it never
predicts an interview outcome. A candidate handed "8/25" has been given a number
nobody can source, about an interview that never happened. Two new guards
(A18-3, A19-4) with the quiet twin that stops "decline the round" scoring 100%.

### Where it stands

| | |
|---|---|
| **Guards** | **10, every one measured failing on the baseline** |
| by mode | discover 1, assess 3, apply 4, interview 2 |
| regression assertions | 45, of which 12 are `with_skill`-only audits |
| `check_discrimination --pilot` | **exit 0** |
| `lint_grading` / `lint_assertions` | exit 0 |

The nominal guard count fell 26 → 10 because sixteen were never guards. The real
count rose **8 → 10**, and the two new ones came from a measurement rather than
a re-roling.

Also removed: `RUN_NOTES.md` is no longer a graded surface. It is the run's
candid diary, Stage 4 exists to read it, and every dispatch prompt tells the run
nothing is graded against it — yet eval-12 was failed for a prediction on the
string "5/5 required" inside its own notes. Grading candour is self-defeating.

## Still open for stage 2

1. Nothing blocks the matrix now; the gate passes. What it will
   measure is 10 guards, not 26 — decide whether that is worth 120
   runs before spending them.
2. The 12 `with_skill`-only audits are graded on one arm, so their
   runs still cost what a comparison costs and return less.
3. `evals/fixtures/assets/jonas.jpg` must be staged into eval 15's
   run directory, or its retain-guard measures the harness again.

Findings as emitted: `<results>/pilot-findings.txt`.
