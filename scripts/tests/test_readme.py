import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
README = ROOT / "README.md"


def _text():
    return README.read_text(encoding="utf-8")


def test_the_pipeline_is_not_duplicated_here():
    """Spec §9. The copy that lived here already omitted Step 7.5, so a reader
    who trusted it believed the run ended at 'Finalize'. One pipeline, in the
    file the model actually loads."""
    text = _text()
    assert "The skill executes these 8 steps" not in text
    assert not re.search(r"^\s*4\.\s+\*\*Gap analysis\*\*", text, re.M)
    assert "SKILL.md" in text and "modes/apply.md" in text


def test_the_layout_matches_the_repo():
    """A layout that names a deleted file sends a reader to look for it, and a
    layout that omits modes/ hides the one directory layer 1.5 lives in."""
    text = _text()
    assert "cv/template.tex" not in text and "letter/template.tex" not in text
    assert "modes/" in text
    for script in ("check_apply.py", "check_claims.py", "enter_mode.py",
                   "check_skill_lossless.py"):
        assert script in text, f"the layout does not mention {script}"


def test_the_workspace_layout_is_documented_including_the_derived_files():
    """cv-source.txt, coverage.json and master-fingerprint.json are written into
    a workspace by this skill and appear in no design document. An undocumented
    artifact is one a later reader deletes as junk."""
    text = _text()
    for name in ("applications/<company>-<role>-<YYYY-MM-DD>", "journal.jsonl",
                 "claims.yaml", "master-fingerprint.json", "cv-source.txt",
                 "coverage.json", "posting-source.txt", "judge-round-<n>.json"):
        assert name in text, f"the workspace layout does not mention {name}"


def test_no_stale_test_count_claim():
    """'Expected: 41 tests' was wrong before the migration and is wrong by more
    than a hundred now. A number that nothing updates is a number that lies."""
    assert not re.search(r"\b\d+\s+tests?,\s+all passing", _text())
