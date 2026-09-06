# iteration-2 — stage 2, with_skill arm

Fifteen `with_skill` runs, one per eval on the stage-1 list, 2026-09-05/06.
Each is matched one-to-one against the baseline run of the same eval from the
pilot. n = 1 per cell, so nothing here says anything about spread; it answers
one question only — **the guards the baseline failed, does the skill pass them?**

Every number is counted from `grading.json` and `timing.json` on disk. Token and
duration figures come from the subagent completion notifications, which are the
only place that data exists. Nothing is estimated.

## The result

**Every one of the ten discriminating guards went FAIL on the baseline and PASS
with the skill.**

| eval | guard | baseline | with_skill |
|---|---|---|---|
| 0 | `us-rn-nurse` — the Cluster-1 interlock is audible | FAIL | PASS |
| 5 | `discover-blocked-adapter` — degraded round carries the disclosure block | FAIL | PASS |
| 11 | `assess-thin-inputs` — refusal floor, no verdict, no count | FAIL | PASS |
| 12 | `assess-usable-posting` — a verdict IS produced on a readable posting | FAIL | PASS |
| 13 | `assess-expired-convention` — expired entry rendered under its banner | FAIL | PASS |
| 14 | `apply-us-personal-data` — the suppression is audible | FAIL | PASS |
| 16 | `apply-ats-reject-genuine-gap` — the loop stops honestly | FAIL | PASS |
| 17 | `apply-ats-reject-buried-evidence` — buried evidence surfaced, not stopped | FAIL | PASS |
| 18 | `interview-unsourced-drift` — no hire verdict, no invented score | FAIL | PASS |
| 19 | `interview-well-sourced` — same, on the decoy round | FAIL | PASS |

n = 1 per cell. This says the skill reached the behaviour on one run each; it
says nothing about how often it does, and it is not a claim about spread.

Regression assertions on the with_skill arm: **29 PASS, 2 not exercised, 1 FAIL**
— and the one FAIL is a scenario defect, recorded below.

Two rows on eval-0 were `AWAITING_READER_GRADE` and were graded by hand from the
rendered `cv.md`, with the quotes written into `grading.json` as the runbook
requires.

### Cost

Nothing here is estimated; every figure is from a completion notification.

| eval | with_skill tokens | with_skill s | baseline tokens |
|---|---|---|---|
| 0 | 252,554 | 1067 | 159,208 |
| 5 | 167,947 | 641 | 43,215 |
| 6 | 151,042 | 525 | 48,949 |
| 8 | 150,197 | 593 | 41,563 |
| 9 | 126,633 | 370 | 49,534 |
| 10 | 135,054 | 575 | 32,811 |
| 11 | 155,308 | 464 | 35,736 |
| 12 | 184,644 | 667 | 39,606 |
| 13 | 177,692 | 703 | 45,688 |
| 14 | 266,873 | 1049 | 160,255 |
| 15 | 252,806 | 1121 | 286,524 |
| 16 | 260,526 | 812 | 152,258 |
| 17 | 286,021 | 1381 | 215,402 |
| 18 | 181,246 | 578 | 41,641 |
| 19 | 202,643 | 823 | 45,866 |
| **total** | **2,951,186** | | |

## The one with_skill FAIL was the scenario's fault, not the run's

eval-19 `interview-well-sourced` is the quiet twin for eval-18: its assertion is
*"a round in which every answer traces to the CV produces no defensive tags"*,
and its job is to fail a skill that tags defensively.

Its CV said only *"offline reconstruction pipeline in C++17; CUDA gridding;
nightly Slurm regressions"*. Its scripted answers said *"I **own** the
pipeline"*, *"I **wrote** the job templates"*, *"I **profiled** the gridding
kernel"*. The run tagged all three, and reading the CV, **all three tags were
right** — the CV asserts neither ownership nor authorship nor the profiling
detail.

So the premise was false in the scenario's own text, which makes the assertion
unpassable by a correct run: the same shape as a guard that cries wolf, one level
up. A `no_skill` baseline cannot catch it, because it emits no tags at all and
passes the twin by never doing the thing the twin is about.

The scenario's CV now carries every scope word its answers use, and
`test_eval_scenarios_carried.py` fails if that stops being true. **The eval-19
twin result above is therefore void rather than a skill failure**, and the twin
is only measured for real from the next run of that scenario onward.

## Three harness defects found by running the arm

All three were found the same way: a guard reported FAIL, and reading the actual
artifact showed the run had done exactly what the skill asks. **Two of the three
were cry-wolf — the guard firing on correct output** — which is worse than a
miss, because a guard that fires on correct output gets switched off and then
protects nothing.

The pattern is worth naming, because it will recur: the harness was written and
calibrated against the BASELINE arm, where the runs do not use the skill. Every
one of these defects is the harness failing to recognise the skill's own correct
behaviour, so none of them could have shown up before this arm ran.

### 1. The disclosure checker could not see a nested shortlist

`_disclosure_carrier` read the exact path `workspace/shortlist.md`. A run that
keeps the skill's own directory shape writes to
`workspace/<person>/searches/<slug>/shortlist.md`.

Measured on eval-5. The six-line disclosure block was there, in English, every
line answered — and the guard reported "missing disclosure line(s) from every
reader-facing document". A harness bug rendered as a skill failure, on the arm
the harness exists to measure.

This is the blindness `runlib.read_any` was added for after eval-15 in the
pilot, surviving in one more function; `_reader_text` two hundred lines below
was already the correct idiom. Fixed by using it. Pinned by three tests
(nested-and-complete passes, nested-and-absent still fires, nested-and-blank
still fires).

### 2. The refusal-floor guard cried wolf on prose naming the scale

`refusal_floor_fires` scanned for the five verdict words as bare substrings.

Measured on eval-11. The run refused exactly as the skill asks —
`verdict: insufficient_evidence`, no coverage card, no recommendation — and
explained itself in the one sentence that has to name the scale in order to say
the answer is not on it:

> not a point on the scale that runs from *apply* to *blocked*, so it does not
> get a position on it

`"blocked" in md` was True and the guard reported a printed conclusion.

Fixed positionally: a verdict is a conclusion when it stands in a line's value
position, after the first colon. Deliberately **not** a whitelist of labels —
`count_coverage.py` writes two spellings, SKILL.md's FIT SNAPSHOT a third, and
an English assessment may reach for a fourth of its own. A pre-existing test
using `Recommendation: worth_applying` is exactly that case, and it is what
caught the label-whitelist version of this fix before it shipped.

### 3. The stale-banner guard knew only the Chinese spelling

`modes/assess.md` says in as many words: *"On an English card the banner is
**past its review date**"*, and `check_assessment.py` matches the pair
case-insensitively. The eval checker had `_EXPIRY_BANNER = "已过复核期"`.

Measured on eval-13. An English assessment rendered the expired NL entry under
`**Past its review date**` and the guard reported no banner. Worse than
eval-11's: on an English card the only correct output IS the one the guard
rejected, so the guard was unpassable in that language.

Fixed by importing `STALE_BANNER` from the skill rather than re-typing it, so
the two copies cannot drift apart again, with a test pinning the import.

## A documentation defect the same reading turned up

`run.md`'s guards column claimed 24 discriminating assertions across 15 evals.
`assertions.yaml` holds **10, across 10 evals** — the pilot re-roled every
assertion its baseline passed, and the hand-maintained table was never updated.

`test_eval_runbook.py`'s existing guard test could not see it: it checks only
that no guard-carrying eval is left out of stage 1, never the reverse. The
column is now generated from `assertions.yaml` and pinned in both directions.

The harm is not the wrong number. It is that a reader comparing the arms off
that table reads a `regression` result as a guard result — eval-9 is the ready
example, where both arms pass both assertions and the old table called them two
guards.
