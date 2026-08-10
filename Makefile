# The checks this repo is held to. `make check` is what actually runs today —
# the workflow file below it is the same three commands for whenever this repo
# gains a remote. Two entry points that run different things would be worse than
# one, so scripts/tests/test_ci.py asserts they stay in step.
.PHONY: test lossless conventions check
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
	@if [ -f scripts/check_conventions.py ]; then \
	  $(PY) scripts/check_conventions.py --all; \
	else \
	  echo "check_conventions.py is not in this repo yet (Plan 2 lands it) — skipped"; \
	fi

check: test lossless conventions
