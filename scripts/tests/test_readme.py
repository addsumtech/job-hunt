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
    """DERIVED from the tree, not a hand-picked sample.

    This used to assert four script names. That is why the README could describe
    a single-mode `job-application` — three of four modes, fourteen of thirty-two
    scripts, the whole market-conventions directory and the entire searches/
    workspace missing — and stay green for months. A layout nothing derives is a
    layout that drifts, and it drifts in the direction of the thing that was true
    when someone last edited it by hand.
    """
    text = _text()
    assert "cv/template.tex" not in text and "letter/template.tex" not in text
    missing = []
    for path in sorted((ROOT / "scripts").glob("*.py")):
        if path.name not in text:
            missing.append(f"scripts/{path.name}")
    for folder in ("modes", "agents", "references"):
        for path in sorted((ROOT / folder).iterdir()):
            if path.name.startswith("."):
                continue
            if path.name not in text:
                missing.append(f"{folder}/{path.name}")
    assert not missing, "the README layout does not mention: " + ", ".join(missing)


def test_the_readme_names_the_skill_it_documents():
    text = _text()
    assert text.startswith("# job-hunt"), "the README still has the old title"
    for mode in ("discover", "assess", "apply", "interview"):
        assert mode in text, f"the README does not mention the {mode} mode"


def test_the_readme_does_not_imply_an_evaluation_that_never_ran():
    """The repo has never claimed to be evaluated, and that honesty is worth
    pinning: plan 5 is unbuilt, so `make check` green means the unit tests agree
    with themselves and nothing more."""
    text = _text()
    assert "No end-to-end behavioural evaluation has ever been run" in text
    # Asserting that words like "baseline arm" are ABSENT does not work and is
    # worth recording: the honest paragraph above uses those very words to say
    # the measurement never happened. A bare substring cannot tell a claim from
    # its negation — the same free-substring mistake this audit found in
    # check_apply's NO_PASS_NO_STOP test.
    assert "evals/" in text, "the README must name the harness that does not exist"
    assert "does\n**not** mean" in text or "does **not** mean" in text


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
