# Running an iteration

Read `evals/README.md` first — it says what this can and cannot show.

Results root: `~/code_project/job-hunt-workspace/iteration-<N>/`. Outside the
repo, deliberately. Never write run outputs inside the repo.

## The output contract — every run saves exactly this

~~~
<results>/eval-<ID>/<arm>/run-<n>/outputs/
  final-message.md   the run's last user-facing message, verbatim
  RUN_NOTES.md       free-form: what broke, what was skipped, what was odd
  workspace/         a copy of the whole job-hunt workspace the run produced
  stderr.log         concatenated stderr of every script the run executed
~~~

`final-message.md` is not optional. Half the guards ask what the run *said* —
whether it claimed there were no matching jobs, whether it asked for a paste —
and iteration-1 saved no such file, so those questions were unanswerable from
the artifacts. `RUN_NOTES.md` is where iteration-1's real diagnostic value sat:
it is the only place a renderer bug or a reference file nobody read gets
recorded, because no assertion covers those.

## The twenty evals

| id | name | mode | baseline_kind | guards |
|---|---|---|---|---|
| 0 | `us-rn-nurse` | apply | old_skill | 1 |
| 1 | `cjk-chinese-swe` | apply | old_skill | — |
| 2 | `career-switch-teacher-ux` | apply | old_skill | — |
| 3 | `senior-exec-coo` | apply | old_skill | — |
| 4 | `uk-nhs-structured` | apply | old_skill | — |
| 5 | `discover-blocked-adapter` | discover | no_skill | 1 |
| 6 | `discover-blank-identity-rows` | discover | no_skill | — |
| 7 | `discover-honest-zero` | discover | no_skill | — |
| 8 | `discover-clean-retrieval` | discover | no_skill | — |
| 9 | `discover-fabricated-row` | discover | no_skill | — |
| 10 | `assess-login-wall-200` | assess | no_skill | — |
| 11 | `assess-thin-inputs` | assess | no_skill | 1 |
| 12 | `assess-usable-posting` | assess | no_skill | 1 |
| 13 | `assess-expired-convention` | assess | no_skill | 1 |
| 14 | `apply-us-personal-data` | apply | old_skill | 1 |
| 15 | `apply-de-photo-conventional` | apply | old_skill | — |
| 16 | `apply-ats-reject-genuine-gap` | apply | old_skill | 1 |
| 17 | `apply-ats-reject-buried-evidence` | apply | old_skill | 1 |
| 18 | `interview-unsourced-drift` | interview | no_skill | 1 |
| 19 | `interview-well-sourced` | interview | no_skill | 1 |
"guards" counts assertions with `role: discriminating`, and the column is
generated from `assertions.yaml`, not maintained by hand — `test_eval_runbook.py`
fails if the two disagree. It used to be hand-written and drifted: it claimed 24
guards across 15 evals while the file held 10 across 10, because the iteration-2
pilot re-roled every assertion its baseline passed and nobody came back to the
table.

An eval with no guard is still worth running — it is a regression eval, and
several are the quiet twins that stop a guard from scoring well by always firing.
That is also why Stage 1 dispatches more evals than there are guards: its list is
a superset, chosen to include the twins, and the test checks only that no
guard-carrying eval is left out of it.

## Arms

| arm dir | what it is | used by |
|---|---|---|
| `with_skill` | `job-hunt` at the current commit | every eval |
| `baseline` (`baseline_kind: old_skill`) | the archived `job-application` at tag `job-application-baseline`, snapshotted with `git -C <repo> worktree add <snapshot> job-application-baseline` | the apply-mode evals |
| `baseline` (`baseline_kind: no_skill`) | no skill at all: the same prompt and the same input files, nothing else | the discover, assess and interview evals |

Two directory names only. The kind goes in `eval_metadata.json`, because the
plugin aggregator discovers configurations by listing directories and deltas the
first two in sorted order — a third name makes the headline compare the two
baselines against each other.

## Baseline isolation — do this before any baseline run

A subagent dispatched on a machine where `job-hunt` is installed CAN SEE AND
INVOKE IT. Measured 2026-08-25 with a probe agent, before the iteration-2 pilot:

    job-hunt: PRESENT   job-application: PRESENT   (43 skills visible)

A `no_skill` baseline run in that state is not a bare agent, and an `old_skill`
run could invoke the NEW skill while being recorded as the old-skill arm. Either
one voids the comparison this whole harness rests on — *a property both arms
have is a property of the model, not of the skill* — so the isolation is a
precondition, not a refinement.

There is no per-agent skill-scoping setting, and subagents run in-process, so
they cannot be given a different HOME. The only mechanism that works is making
the skills undiscoverable in `~/.claude/skills` for the duration:

| arm | `job-hunt` | `job-application` |
|---|---|---|
| `no_skill` baseline | moved aside | moved aside |
| `old_skill` baseline | moved aside | present, at tag `job-application-baseline` |
| `with_skill` | present | moved aside |

**Verify with a probe agent after each change and before dispatching**, asking
only what its own available-skills listing contains. The states above were each
confirmed that way for iteration-2; do not assume a move took effect.

Two things that cost time here, recorded so they do not cost it again:

- **A symlink to a git WORKTREE was not discovered as a skill.** `job-hunt`
  installed as a symlink to a normal repo IS discovered, so symlinks as such are
  fine; a symlink to a worktree of the tag came back ABSENT from a probe, while
  a real directory of the same content came back PRESENT. The mechanism was not
  isolated — caching or timing could explain it — so the safe instruction is to
  use a real directory, not a worktree symlink, and to probe either way.
- **Write the restore path down before moving anything.** Anything that leaves
  the skills directory must have a one-line restore committed to disk first; a
  session that dies mid-run otherwise leaves the user without their skills and
  without the command to get them back.

## Telling a run which arm it is in

Installing the right skills is half of it. The run also has to be TOLD, without
ambiguity, that using the installed skill is correct — or it will infer the arm
from its surroundings and can infer it wrong.

Measured at iteration-2. Five `old_skill` baselines were dispatched with
`job-application` installed and a prompt saying "use whatever tools and skills you
have available", plus "do NOT read anything under `~/code_project/job-hunt`".
**Three of the five declined to invoke the skill and did the work by hand.** The
run directory is named `baseline` and the prompt forbade the newer skill's repo;
together those read as "this is the no-skill arm". From eval-16's notes:

> this run lives under `job-hunt-workspace/.../baseline/` and I was explicitly
> forbidden from reading `~/code_project/job-hunt`. That reads to me as "this is
> the no-skill arm". [...] this is genuinely ambiguous and I may have called it
> wrong.

Nothing in the artifacts would have flagged it. Three no_skill runs would have
been scored as the old_skill arm, and the apply-mode comparison — five of the
twenty evals — would have been against the wrong control.

So the old_skill dispatch prompt must say, in as many words:

> There is a skill named `job-application` installed at
> `~/.claude/skills/job-application`. It is part of this run's intended
> environment. Invoke it and use it exactly as you normally would. This directory
> is named `baseline` because it is the control arm for a DIFFERENT, newer skill
> that is deliberately not installed right now.

and any "do not read X" restriction must say explicitly that it does NOT extend
to the skill the arm is exercising.

**Verify from the artifacts, not from the prompt.** Whether the skill was used is
visible in the workspace layout, which is independent of what the run says about
itself:

| | used `job-application` | hand-rolled |
|---|---|---|
| apply-mode workspace holds | `profile.yaml`, `posting.yaml`, `cv.tex`, `tailored-profile.yaml`, `job-profiles/` | `build_cv.py` and similar one-off scripts |

Check every old_skill run against that before grading, and discard the ones that
did not use it — under `<results>/discarded/`, which `runlib.iter_runs` cannot
see, with the reason written down. A discarded run with no record is
indistinguishable from one that never happened.

## Toolchain the apply evals depend on

Several apply assertions ask that BOTH docx and pdf were produced, so check the
renderer's dependencies before the matrix and record what is missing. A PDF that
failed because a binary is absent is an environment result, not a skill result,
and grading it as the latter would be the harness lying about its own subject.

What was actually present at iteration-2, and a correction worth keeping: a first
pass checked only `xelatex`, `pdflatex`, `pandoc` and `libreoffice`, found no
xelatex, and concluded PDF rendering was at risk. **That conclusion was wrong.**
The runs' own notes reported `tectonic` installed — a LaTeX engine the check had
not thought to look for — alongside `pandoc`, `soffice`, `pdftoppm` and
`pdftotext`, and every apply run produced its PDF. Check for the CAPABILITY (can
this machine turn the renderer's input into a PDF) rather than for one binary's
name, and confirm it by rendering something rather than by `command -v`.

## Stage 1 — pilot (baseline only, one run per guard eval)

1. `mkdir -p ~/code_project/job-hunt-workspace/iteration-2`
2. For each eval, write `eval-<ID>/eval_metadata.json`:
   `{"eval_id": N, "eval_name": "...", "baseline_kind": "...", "prompt": "<the scenario's TASK line, verbatim>", "assertions": []}`
3. Dispatch **one baseline run** for each of these FIFTEEN evals, in one turn.
   They are every guard-carrying eval plus its quiet twins — a superset of the
   ten that carry a discriminating assertion, not a list of them:

   - eval-0 `us-rn-nurse`
   - eval-5 `discover-blocked-adapter`
   - eval-6 `discover-blank-identity-rows`
   - eval-8 `discover-clean-retrieval`
   - eval-9 `discover-fabricated-row`
   - eval-10 `assess-login-wall-200`
   - eval-11 `assess-thin-inputs`
   - eval-12 `assess-usable-posting`
   - eval-13 `assess-expired-convention`
   - eval-14 `apply-us-personal-data`
   - eval-15 `apply-de-photo-conventional`
   - eval-16 `apply-ats-reject-genuine-gap`
   - eval-17 `apply-ats-reject-buried-evidence`
   - eval-18 `interview-unsourced-drift`
   - eval-19 `interview-well-sourced`
   This list is not typed by hand — `scripts/tests/test_eval_runbook.py`
   recomputes it from `assertions.yaml` and fails if the runbook drifts.

   THE PLAN THIS RUNBOOK COMES FROM NAMED TEN, AND THAT LIST WAS WRONG. It
   omitted six guard-carrying evals and included `discover-honest-zero`, which
   carries no guard at all. Simulated against the real `assertions.yaml` — every
   one of its ten piloted, every guard failing the baseline, the best possible
   case — step 6 still returned 12 `NO_PILOT_RUN` findings and exited 1. Stage 2
   could never legitimately have begun, so whoever ran it would have had to
   override the gate that exists to protect the matrix.

4. Capture `total_tokens` and `duration_ms` from each completion notification
   into that run's `timing.json` **as it arrives**. That notification is the only
   place the data exists.
5. `python3 evals/grade.py --iteration <results> --arm baseline`
6. `python3 evals/check_discrimination.py --iteration <results> --pilot`

**Do not dispatch stage 2 until step 6 exits 0.** A `BASELINE_PASSED_A_GUARD`
finding means either the scenario does not force the branch or the property
belongs to the model rather than the skill. Fix the scenario, or re-role the
assertion to `regression` with the reason in the commit message. Re-running the
pilot for one eval is cheap; discovering it in the aggregate is what iteration-1
did.

## Stage 2 — the matrix

Twenty evals × two arms × three runs = **120 runs**. Dispatch per eval, both arms
in the same turn, so the two arms of a pair meet the same conditions.

The only cost data that exists is iteration-1's, over a different scenario set:
with-skill 354.4s ± 96.1s and 82,601 ± 24,304 tokens per run; old-skill 216.0s ±
17.7s and 69,448 ± 3,099 tokens. Quoted, **not a prediction** for this set — the
discover and interview scenarios have no counterpart there.

Discover runs need the stub on PATH and a fixture selected:

~~~bash
# A DIRECTORY named `opencli` already exists under evals/fixtures — it holds the
# JSON fixtures. So putting evals/fixtures itself on PATH provides no `opencli`
# command at all, and symlinking the stub "onto" that path just drops a link
# INSIDE the fixture directory. Do neither. Give the stub its own bin dir:
EVALBIN="$(mktemp -d)/bin"; mkdir -p "$EVALBIN"
ln -sf "$PWD/evals/fixtures/opencli-stub" "$EVALBIN/opencli"
export PATH="$EVALBIN:$PATH"
export JOBHUNT_EVAL_FIXTURE="$PWD/evals/fixtures/opencli/51job-403.json"

# VERIFY BEFORE EVERY DISCOVER RUN. This must print $EVALBIN/opencli.
which opencli
~~~

**Check `which opencli` every time.** A real `opencli` is installed at
`~/.local/bin/opencli` on this machine. With the wiring above missing or wrong,
`opencli` resolves to THAT — a live, networked tool — and the discover evals
silently run against the real site: not reproducible, not the fixture the
scenario promises, and reaching a network the harness says it never reaches. The
failure is silent, which is why the check is a step and not a footnote.

| eval | fixture |
|---|---|
| 5 `discover-blocked-adapter` | `opencli/51job-403.json` |
| 6 `discover-blank-identity-rows` | `opencli/indeed-blank-titles.json` |
| 8 `discover-clean-retrieval` | `opencli/51job-ok.json` |
| 9 `discover-fabricated-row` | none — starts from the prepared `fabricated` workspace and runs no new search |

The stub refuses any write command outright; **do not attempt a login on any
site**, in any arm, for any reason, and do not point a discover eval at a live
adapter.

**Eval 9 — and only eval 9 — starts from a prepared workspace.** Copy the CONTENTS
of `evals/fixtures/workspaces/fabricated/` into `<run>/outputs/workspace/` before
dispatch, and tell the run to search nothing.

This line used to name evals 8 and 9 together, and that was wrong. eval 8 is
`discover-clean-retrieval`: its scenario asks for an ordinary successful round
against the `51job-ok` fixture, says nothing about a saved workspace, and the
iteration-2 baseline ran it with nothing staged. Staging `workspaces/clean/` into
one arm and not the other would have made the pair meet different conditions,
which is the one thing a matched pair may not do. `workspaces/clean/` is a
checker fixture, not a run input.

Eval 13 uses `evals/fixtures/conventions/expired-nl.yaml` as the session's `nl`
table; say so in the prompt and do not edit the shipped table.

Eval 15 needs its photo staged, or its guard measures the harness rather than
the run:

~~~bash
mkdir -p "<run>/outputs/workspace/assets"
cp evals/fixtures/assets/jonas.jpg "<run>/outputs/workspace/assets/jonas.jpg"
~~~

`apply-de-photo-conventional.md` says the Bewerbungsfoto is attached. In the
iteration-2 pilot no such file was staged, so the run rendered without a photo —
it had no other option — and `personal_data_retained_where_conventional` failed
it for dropping a conventional field. The checker now reports an absent file as
unmeasurable rather than as a drop, but that turns the assertion off; staging
the file is what turns it back into a measurement of behaviour.

## How many runs to dispatch at once

Measured 2026-09-05, dispatching the with_skill arm: **eight concurrent Opus runs
exhausted the session limit and all eight died mid-run** with HTTP 429, between one
and thirteen files written each. Nothing was gradable and every one had to be reset
and re-staged.

**Count agents, not runs.** An apply run dispatches all three judges in parallel,
so it is four concurrent agents, not one; an interview run dispatches two
assessors. Measured again 2026-09-06: three runs dispatched together (evals 0, 18
and 19 — one apply, two interview) hit the limit a second time, because eval-0's
three judges were live at the same moment. Four *discover* or *assess* runs are
four agents and were fine twice; three runs including one apply were not.

Dispatch in batches of about four agents, and reset an aborted run rather than
grading what it left behind. A partially written run directory is the dangerous artifact here: it
holds a real `scenario.md`, a real workspace and some real output, so it looks like a
short run rather than a killed one, and `grade.py` cannot tell the difference. Delete
`outputs/`, re-stage, re-dispatch.

Both arms of a pair must still be dispatched under the same model. The arms differ by
which skill is installed and by nothing else; a with_skill arm run on a cheaper model
to save budget measures the model, which is the one thing this harness exists to
control for.

## Keeping a run out of the real profile store

The skill's prose tells the model to work under `~/.claude/job-profiles/`, and
`scripts/paths.py` resolves `PROFILES_ROOT` there. On the machine this harness
runs on that directory holds a REAL person's CVs, applications and search
preferences. A run that follows the skill faithfully writes a fictional
candidate's profile straight into it.

There is no clean mechanism to prevent that. Subagents run in-process, so they
cannot be given a different HOME (same constraint as the skill isolation above),
and they do not inherit a per-call environment variable either — so an env-var
override in `paths.py` would only be as strong as an instruction telling the run
to export it, i.e. no stronger than just naming the directory. One was written
and reverted for exactly that reason; do not add it back believing it isolates
anything.

What actually works is two things together:

1. **Say it in the dispatch prompt.** Give the run its workspace root explicitly
   and say that everything the skill would put under `~/.claude/job-profiles/`
   goes there instead, keeping whatever subdirectory shape the skill calls for —
   only the root moves. Add "do not write to `~/.claude/job-profiles/`, it holds
   a real person's data". `runlib` already finds artifacts wherever the run put
   them, so a nested `job-profiles/<person>/applications/<slug>/` grades fine.
2. **Prove it afterwards.** Snapshot the live store before dispatch and diff it
   after every run has finished:

~~~bash
find ~/.claude/job-profiles -print0 | xargs -0 -I{} stat -f '%N %z %m' {} \
  | sort > <results>/profiles-before.txt
# ... run everything ...
find ~/.claude/job-profiles -print0 | xargs -0 -I{} stat -f '%N %z %m' {} \
  | sort | diff <results>/profiles-before.txt -
~~~

An empty diff is the only evidence that the instruction held. Without the
snapshot, a leak is indistinguishable from no leak, and the run notes would not
mention it because the run would not think it had done anything wrong.

## Stage 3 — grade, aggregate, view

~~~bash
RES=~/code_project/job-hunt-workspace/iteration-2
python3 evals/grade.py --iteration "$RES"
# then grade every AWAITING_READER_GRADE row by hand, in grading.json,
# writing a quote or a file:line into `evidence` — never "looks good".
python3 evals/lint_grading.py --iteration "$RES"
SC=~/.claude/plugins/cache/claude-plugins-official/skill-creator/unknown/skills/skill-creator
(cd "$SC" && python3 -m scripts.aggregate_benchmark "$RES" --skill-name job-hunt)
python3 evals/aggregate.py --iteration "$RES" --write-record
python3 evals/check_discrimination.py --iteration "$RES"
python3 "$SC/eval-viewer/generate_review.py" "$RES" --skill-name "job-hunt" \
  --benchmark "$RES/benchmark.json" \
  --previous-workspace ~/.claude/skills/job-application-workspace/iteration-1 \
  --static "$RES/review.html"
~~~

Run `evals/aggregate.py` **after** the plugin aggregator: it patches
`benchmark.json`'s hardcoded run count and its inverted delta, and the viewer
reads that file.

## Stage 4 — read the run notes

The aggregate says whether the assertions passed. It cannot say what nobody
thought to assert. Read every `RUN_NOTES.md`; that is where iteration-1 recorded
the LaTeX `&`-in-heading bug, the PATH-based engine-discovery failure and a run
declining to read `references/motivation-letter.md` and then filing a finding
that the guidance it contained was missing. None of those had an assertion.
