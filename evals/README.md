# job-hunt evaluation harness

Twenty scenarios, two arms, three runs each. The harness is here in the repo;
**the results root is outside the repo**, at
`~/code_project/job-hunt-workspace/iteration-<N>/`, because a run produces a real
workspace containing a real person's profile data and a results tree inside the
repo is one `git add` away from being published.

## What a run of this measures

Whether a run, given a fixed scripted input, produces artifacts and a final
message with specific checkable properties — **and whether an arm without the
skill produces them too.** That second half is the point:
*A property both arms have is a property of the model, not of the skill.*

## What it cannot show

- **Outcomes.** This is a count of behaviours, **not an outcome**. No interview
  rate, no hiring rate, no score. The skill is forbidden from predicting those
  and so is its harness.
- **Quality.** `pass_rate` counts a hand-written assertion list against a
  hand-written scenario list, both written by the people who wrote the skill.
  That is why every assertion must carry a `falsifier`: what an output that
  fails it would look like, written down before the run.
- **Significance.** Three runs notice a coin flip. They do not support a
  confidence interval. Dispersion is printed only where it exists; a single run
  prints `n=1 (no dispersion)`, never `± 0%`.
- **Anything about the job platforms.** Each discover fixture
  **replays a capture measured on 2026-08-09**. It shows how the skill reacts to
  that body. It says nothing about what the site returns today.

## The vocabulary

| term | meaning |
|---|---|
| **arm** | `baseline/` or `with_skill/`. Always those two directory names. |
| **baseline kind** | `old_skill` (the archived `job-application` at tag `job-application-baseline`) or `no_skill` (a bare agent, same prompt, same inputs). Recorded in `eval_metadata.json`, never in the directory name — three config names would make the aggregator subtract one baseline kind from the other and print it as the headline. |
| **role** | `discriminating` (the baseline is expected to fail it) or `regression` (both arms pass today; its job is to catch a drop). Scored in separate tables. |
| **guard / decoy** | A guard scenario fires a defence. Its decoy is the scenario where the honest answer is the opposite one. |
| **twin** | Every guard checker names the checker that decides its decoy. `TWINS` is an involution and the lint requires the twin to be used in the twin eval — *every guard checker is paired with the twin checker that pins its quiet case*. Without that, "always refuse" scores 100%. |
| **not exercised** | A `null` result. **passed: null means not exercised, and never means pass.** Excluded from the numerator and the denominator, listed by name under `## Not exercised`, and counted in `not_exercised`. |

## Two numbers this harness will not take on faith

`aggregate_benchmark.py` from the skill-creator plugin hardcodes
`runs_per_configuration: 3` into its metadata whatever is on disk, and computes
its delta as `configs[0] - configs[1]`, which with our directory names is
`baseline - with_skill` — the sign reads inverted. iteration-1 shipped both:
metadata claiming three runs over a tree holding one, and a pass rate that rose
0.875 → 1.0 printed as `-0.12`. `evals/aggregate.py` reports run counts
**counted from disk** and a `delta_with_minus_baseline` with the sign its label
promises, then patches `benchmark.json` so the viewer shows the same thing.

**An assertion that cannot distinguish the arms is not evidence.** See
`evals/assertions.yaml` for how each one declares that it can, and
`evals/check_discrimination.py` for the two places that claim is tested — once
on the pilot baseline run before the benchmark exists, once over the finished
iteration.

## Running it

- Deterministic half: `make eval-verify` from the repo root.
- The runs themselves are subagent dispatches: follow `evals/run.md` exactly,
  pilot first.
