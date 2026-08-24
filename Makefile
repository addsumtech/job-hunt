# The checks this repo is held to. `make check` is what actually runs today —
# the workflow file below it is the same three commands for whenever this repo
# gains a remote. Two entry points that run different things would be worse than
# one, so scripts/tests/test_ci.py asserts they stay in step.
.PHONY: test lossless conventions check mutants mutants-record
PY ?= python3
# The pre-migration tip of job-application, made an ancestor of HEAD by the migration
# merge — so it resolves in any clone, with nothing to distribute. The tag
# `job-application-baseline` is a readable alias for this commit and exists only in the
# clone that created it; depending on it would make the check exit 2 everywhere else,
# and a check that cannot run looks exactly like a check that passed.
BASELINE ?= 864ad7f

test:
	$(PY) -m pytest scripts/tests -q

lossless:
	$(PY) scripts/check_skill_lossless.py --baseline $(BASELINE)

conventions:
	$(PY) scripts/check_conventions.py --ci

check: test lossless conventions

# Mutation testing: break the code on purpose and see whether the suite notices.
# DELIBERATELY NOT part of `check`. It copies the repo and re-runs the suite once
# per mutant, so it is minutes-to-hours, not seconds — putting it in the gate
# everyone runs before every commit is how a slow check gets commented out.
# CI runs it on a schedule and on demand instead (.github/workflows/mutants.yml).
#
# `--ci` fails only on survivors that are NOT in scripts/mutants-baseline.json,
# so the debt measured on 2026-08-24 does not block anyone, while a change that
# makes the suite blinder than that does.
mutants:
	$(PY) scripts/mutants.py --ci

# Rewrite the baseline. Never available to CI: a harness that updates its own
# baseline reports success by forgetting.
mutants-record:
	$(PY) scripts/mutants.py --record
