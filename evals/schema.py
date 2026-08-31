"""The eval-record and assertion-record schemas.

Deliberately NOT importing scripts/vocab.py. The harness has to describe a run
of the old skill and a run with no skill at all, and neither arm has access to
the new skill's vocabulary; a harness that could only express the new skill's
concepts could not describe its own baseline. Where the two genuinely overlap
— verdict strings, defect tags, disclosure labels — the CHECKERS import from
scripts/ directly, so there is still exactly one definition of every closed set
the skill itself owns.
"""

ARMS = ("baseline", "with_skill")

# Which baseline this eval compares against. Recorded in eval_metadata.json,
# never in a directory name: aggregate_benchmark.py discovers configurations by
# listing directories and deltas the first two in sorted order, so a third
# config name would silently make the headline number compare the two baselines
# against each other.
BASELINE_KINDS = ("old_skill", "no_skill")

# discriminating: the baseline is expected NOT to satisfy it, so passing it is
#   evidence about the skill.
# regression: both arms satisfy it today; its job is to catch a drop. Scored in
#   its own table so it cannot inflate the discrimination result.
ROLES = ("discriminating", "regression")

EXPECTED_BASELINE = ("fail", "not_exercised", "pass")

MODES = ("discover", "assess", "apply", "interview")

# The document's own keys. `coverage` is load-bearing -- it is how a mode
# declares it has no discriminating assertion left -- so a typo in it must be a
# finding rather than a declaration that silently exempts nothing.
DOC_KEYS = ("evals", "retired", "coverage")

EVAL_KEYS = ("id", "name", "mode", "baseline_kind", "scenario", "quiet_twin",
             "assertions", "fixture", "prepared_workspace", "notes")
REQUIRED_EVAL_KEYS = ("id", "name", "mode", "baseline_kind", "scenario",
                      "assertions")

ASSERTION_KEYS = ("id", "text", "role", "expected_baseline", "falsifier",
                  "checker", "arms", "twin_assertion", "note")
REQUIRED_ASSERTION_KEYS = ("id", "text", "role", "expected_baseline",
                           "falsifier", "checker")

# `twin_assertion` is the hand-declared quiet pin for a reader-graded row. Most
# guards get their quiet case from TWINS in evals/checkers.py, mechanically; a
# judgement-based guard has no checker to twin, so it names the assertion in one
# of its quiet_twin evals that pins the opposite behaviour. It is the ONLY way a
# discriminating assertion may sit on an untwinned checker (Task 10's
# UNTWINNED_DISCRIMINATING rule), so the escape hatch cannot smuggle in a guard
# with no quiet case.

RETIRED_KEYS = ("id", "text", "reason", "replaced_by")

# A falsifier shorter than this is not a falsifier, it is a shrug.
MIN_FALSIFIER_CHARS = 24
