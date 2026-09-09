"""Registration is a layer-1 obligation, not paperwork.

Plan 1's test_skill_structure.py already asserts the self-check names every
file. This module pins the two things it cannot: that the discover entries say
what they are for, and that the 'not yet built' sentence retracted itself.
"""
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[2]
SKILL = REPO / "SKILL.md"

MODES_WITH_FILES = ("discover",)


def normalised():
    """Backticks stripped and whitespace collapsed, so that a sentence broken
    across lines or wrapped in code formatting cannot hide from the search."""
    return re.sub(r"\s+", " ", SKILL.read_text(encoding="utf-8").replace("`", ""))


def test_the_not_yet_built_sentence_retracted_itself():
    text = normalised()
    for mode in MODES_WITH_FILES:
        assert (REPO / "modes" / f"{mode}.md").exists()
        assert f"{mode} is not yet built" not in text, (
            f"SKILL.md still tells the model to refuse {mode}, which now works. "
            "A stale 'not built' costs more than a missing one: every check "
            "passes and layer 1 declines a working mode.")


def test_the_self_check_names_this_plans_files_with_a_reason_to_open_them():
    text = SKILL.read_text(encoding="utf-8")
    for path in ("modes/discover.md", "references/discovery-sources.md",
                 "references/source-policy.md",
                 "references/risk-control-signals.yaml",
                 "scripts/check_opencli_result.py", "scripts/check_no_write.py",
                 "scripts/snapshot_profile.py", "scripts/check_candidate_match.py",
                 "scripts/check_shortlist.py"):
        assert path in text, f"{path} is registered nowhere in SKILL.md"


def test_the_gate_table_lists_discover_gates():
    text = SKILL.read_text(encoding="utf-8")
    for gate in ("scripts/check_no_write.py", "scripts/check_candidate_match.py",
                 "scripts/check_shortlist.py"):
        row = next((line for line in text.splitlines()
                    if line.startswith("|") and gate in line), None)
        assert row is not None, f"{gate} has no row in the gate table"
        assert row.count("|") >= 4, f"{gate}'s gate-table row has no 'fires on'"


def test_the_wrapper_is_not_described_as_a_gate():
    # check_opencli_result.py is the one named exception to the gate contract:
    # exit 0/2 only, and an adapter_call record instead of a receipt. Listing
    # it as a gate would send someone looking for a receipt that never exists.
    text = SKILL.read_text(encoding="utf-8")
    row = next((line for line in text.splitlines()
                if line.startswith("|") and "check_opencli_result.py" in line), None)
    assert row is not None
    assert "wrapper" in row.lower()
