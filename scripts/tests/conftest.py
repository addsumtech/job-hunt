import pathlib
import sys

import pytest

# Tests import the gate scripts by module name. scripts/ is not a package on purpose:
# each script must also be runnable as `python3 scripts/<name>.py` from the repo root.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

@pytest.fixture
def sample_profile_path():
    return FIXTURES / "sample_profile.yaml"

# The eval harness lives in evals/ and its tests (scripts/tests/test_eval_*.py) import
# it as a package. Insert the REPO ROOT, not evals/ itself: as a package, `import
# checkers` inside a test can never collide with a same-named module under scripts/.
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
