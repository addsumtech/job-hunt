# iteration-2 — stage 1 pilot

Fifteen baseline runs, one per guard-carrying eval, 2026-08-25. Graded by
`evals/grade.py`; gated by `evals/check_discrimination.py --pilot`, which
**exited 1 with 18 findings**. Per `evals/run.md`, stage 2 does not start until
that exits 0, so the 120-run matrix was NOT dispatched.

Every number here is counted from `grading.json` on disk. Nothing is estimated.

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

## Before stage 2

1. Re-role or re-aim the 12 unexercised guards. A checker that reads the skill's
   private files cannot be a guard; point it at the final message, or make it a
   regression assertion with the reason written down.
2. Re-role the 6 the baseline passed to `regression`, each with its reason.
3. Re-run the pilot. It must exit 0.

Findings as emitted: `<results>/pilot-findings.txt`.
