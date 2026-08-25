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
| 0 | `us-rn-nurse` | apply | old_skill | 2 |
| 1 | `cjk-chinese-swe` | apply | old_skill | — |
| 2 | `career-switch-teacher-ux` | apply | old_skill | — |
| 3 | `senior-exec-coo` | apply | old_skill | — |
| 4 | `uk-nhs-structured` | apply | old_skill | — |
| 5 | `discover-blocked-adapter` | discover | no_skill | 2 |
| 6 | `discover-blank-identity-rows` | discover | no_skill | 1 |
| 7 | `discover-honest-zero` | discover | no_skill | — |
| 8 | `discover-clean-retrieval` | discover | no_skill | 3 |
| 9 | `discover-fabricated-row` | discover | no_skill | 2 |
| 10 | `assess-login-wall-200` | assess | no_skill | 1 |
| 11 | `assess-thin-inputs` | assess | no_skill | 2 |
| 12 | `assess-usable-posting` | assess | no_skill | 3 |
| 13 | `assess-expired-convention` | assess | no_skill | 1 |
| 14 | `apply-us-personal-data` | apply | old_skill | 2 |
| 15 | `apply-de-photo-conventional` | apply | old_skill | 1 |
| 16 | `apply-ats-reject-genuine-gap` | apply | old_skill | 1 |
| 17 | `apply-ats-reject-buried-evidence` | apply | old_skill | 1 |
| 18 | `interview-unsourced-drift` | interview | no_skill | 2 |
| 19 | `interview-well-sourced` | interview | no_skill | 2 |
"guards" counts assertions with `role: discriminating`. An eval with none is
still worth running — it is a regression eval, and several are the quiet twins
that stop a guard from scoring well by always firing.

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

## Toolchain the apply evals depend on

`xelatex` was NOT installed on this machine at iteration-2 (`pandoc` and
`soffice` were). Several apply assertions ask that BOTH docx and pdf were
produced. Check the renderer's dependencies before the matrix and record what is
missing: a PDF that failed because a binary is absent is an environment result,
not a skill result, and grading it as the latter would be the harness lying about
its own subject.

## Stage 1 — pilot (baseline only, one run per guard eval)

1. `mkdir -p ~/code_project/job-hunt-workspace/iteration-2`
2. For each eval, write `eval-<ID>/eval_metadata.json`:
   `{"eval_id": N, "eval_name": "...", "baseline_kind": "...", "prompt": "<the scenario's TASK line, verbatim>", "assertions": []}`
3. Dispatch **one baseline run** for each of the FIFTEEN evals that carry a
   discriminating assertion, in one turn:

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

Evals 8 and 9 start from a prepared workspace: copy
`evals/fixtures/workspaces/{clean,fabricated}/` into the run's working directory
before dispatch.

Eval 13 uses `evals/fixtures/conventions/expired-nl.yaml` as the session's `nl`
table; say so in the prompt and do not edit the shipped table.

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
