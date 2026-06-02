import pathlib
import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

@pytest.fixture
def sample_profile_path():
    return FIXTURES / "sample_profile.yaml"
