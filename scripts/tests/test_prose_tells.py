"""Does the output read as machine-written?

The letter was the ONE artifact with no cliché or AI-tell check at all.
Reproduced 2026-09-06: a letter carrying results-driven, spearheading, pivotal,
leverage, robust, delve, intricate, realm, showcasing, "not just X — it is Y",
three tricolons and three em dashes passed `check_letter` reporting only its word
count. `lint_cv` covered the CV, but only its BULLETS — the same three clichés
produced one finding in a bullet and zero in the summary, which is the line a
recruiter reads first.

Two rules govern everything here, and both are the repo's own:

  A gate that fires on correct output gets switched off. So every threshold is
  calibrated against real text — including this skill's own letters from the
  iteration-2 eval — and errs toward missing.

  A tell known only in English is reported as English-only. `lint_cv`'s
  weak-opener list carries the scar of enforcing a style rule on one alphabet.
"""
import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_letter  # noqa: E402
import lint_cv  # noqa: E402
import prose_tells  # noqa: E402

MACHINE_LETTER = [
    "I am a results-driven professional with a proven track record of "
    "spearheading pivotal initiatives that leverage cutting-edge technology to "
    "deliver robust, scalable, and impactful solutions.",
    "This role is not just an opportunity to write code — it is a chance to "
    "delve into the intricate realm of medical imaging, showcasing my ability "
    "to innovate, collaborate, and excel.",
    "I am passionate about technology — a team player who thrives in a "
    "fast-paced environment — and I am confident that my dedication to "
    "excellence, my relentless drive, and my synergy with your mission would "
    "make me a valuable asset.",
]

HUMAN_LETTER = [
    "I read the posting for the reconstruction role and wanted to write "
    "directly. For the last three years I have worked on cardiac MRI "
    "reconstruction at LUMC, mostly on undersampled k-space.",
    "Two of my first-author papers are on cine reconstruction, and one of them "
    "runs on a single GPU because that was all we had. Your advert mentions "
    "CUDA and a fixed per-study time budget. That is the part I would want to "
    "talk about.",
    "I do not have production C++ at the scale you describe. I have written "
    "CUDA kernels and maintained a nightly regression suite on a Slurm cluster, "
    "which is adjacent but not the same thing. I would rather say that now than "
    "have it come out in the second interview.",
]


def _scan(paragraphs):
    joined = "\n".join(paragraphs)
    return (prose_tells.vocabulary_findings(joined, "b")
            + prose_tells.prose_findings(joined, "b"))


# ---- the tells fire on machine prose --------------------------------------

@pytest.mark.parametrize("term", [
    "spearheaded", "pivotal", "intricate", "showcasing", "delve", "realm",
    "robust", "cutting-edge", "valuable asset",
])
def test_the_2026_vocabulary_is_caught(term):
    """The terms recruiters report flagging most. `lint_cv.CLICHES` held four of
    the older ones; these were missing."""
    found = {f.split("'")[1] for f in _scan(MACHINE_LETTER) if "AI_VOCABULARY" in f}
    assert term in found


def test_the_not_just_pivot_is_caught():
    assert any("NOT_JUST_PIVOT" in f for f in _scan(MACHINE_LETTER))


@pytest.mark.parametrize("phrasing", [
    "This is not just a job, but a calling.",
    "It's not only about the code — it is about the patients.",
    "The role is more than just engineering; it is stewardship.",
    "This isn't merely a position, but a partnership.",
    "It was not just an audit — it was a chance to rebuild trust.",
    "Not only were the deadlines tight; these are the conditions I work best in.",
])
def test_the_pivot_is_caught_in_its_common_phrasings(phrasing):
    """One template pinned is one regression caught; the family is what the
    construction actually is."""
    assert prose_tells.NOT_JUST_PIVOT.search(phrasing), phrasing


# ---- and stay silent on human prose ---------------------------------------

def test_a_human_letter_is_clean():
    """The cry-wolf check. A gate that fires here gets switched off, and this
    repo has closed three of those this week."""
    assert _scan(HUMAN_LETTER) == []


def test_a_single_em_dash_is_ordinary_writing():
    text = "Two of my papers are on cine reconstruction — one runs on a single GPU."
    assert prose_tells.prose_findings(text, "b") == []


def test_one_tricolon_is_ordinary_writing():
    text = "I have worked in Python, C++ and MATLAB across three reconstruction projects."
    assert prose_tells.prose_findings(text, "b") == []


# ---- the calibration itself, so a threshold cannot drift by taste ---------

@pytest.mark.parametrize("sample, per_100, fires", [
    ("hand-written", 0.7, False),
    ("this skill's Brainlab letter", 1.0, False),
    ("this skill's Cedars letter", 1.8, True),
    ("deliberately machine-written", 3.2, True),
])
def test_the_em_dash_threshold_sits_where_it_was_measured(sample, per_100, fires):
    """Measured densities from 2026-09-06. A first pass put the line at 1.0 and
    fired on BOTH of the skill's real letters — but the human baseline is a
    single sample, which is not enough evidence to call 1.0 machine-like."""
    assert (per_100 > prose_tells.EM_DASH_PER_100_WORDS) is fires, sample


def test_the_absolute_floor_stops_a_short_line_from_firing():
    """Density alone makes a six-word line with one dash read as 16 per 100."""
    assert prose_tells.prose_findings("A short line — like this.", "b") == []


# ---- both surfaces are covered, and only the right checks on each ---------

def test_the_letter_gate_reports_the_tells():
    """It reported only word count and role naming before."""
    findings = check_letter.findings_for(
        {"body": MACHINE_LETTER, "recipient": {"company": "Philips"},
         "sender": {"name": "D"}, "salutation": "Dear Hiring Team,",
         "closing": "Sincerely,"},
        {"role_title": "Engineer", "company": "Philips"})
    assert any("AI_VOCABULARY" in f for f in findings)
    assert any("EM_DASH_DENSITY" in f for f in findings)
    assert any("NOT_JUST_PIVOT" in f for f in findings)


def test_the_cv_summary_is_linted_not_only_its_bullets():
    """The same three clichés produced one finding in a bullet and ZERO in the
    summary — invisible in the more damaging place."""
    cv = ("# Jane Doe\n\nResults-driven professional with a proven track record "
          "of leveraging synergy.\n\n## Experience\n- Built a thing.\n")
    assert any("CLICHE" in f and ":3" in f for f in lint_cv.findings_for(cv))


def test_a_cv_bullet_gets_the_new_vocabulary_too():
    cv = "# X\n\n## Experience\n- Spearheaded a pivotal rebuild.\n"
    found = lint_cv.findings_for(cv)
    assert any("spearheaded" in f for f in found)
    assert any("pivotal" in f for f in found)


def test_a_cv_is_exempt_from_the_structural_checks():
    """A skills line reads "Python, C++, MATLAB" and a bullet is terse by design,
    so tricolon and em-dash density would fire on every correct CV."""
    cv = ("# X\n\n## Skills\nPython, C++, MATLAB — and CUDA\n\n"
          "## Experience\n- Built A, B and C.\n- Shipped D, E and F.\n"
          "- Ran G, H and I.\n")
    assert not any("TRICOLON" in f or "EM_DASH" in f for f in lint_cv.findings_for(cv))


def test_a_heading_or_contact_line_is_not_prose():
    """A company legitimately called "Robust Systems" must not be reported as a
    cliché on the line that merely names it."""
    cv = ("# Jane Doe\n\njane@example.com · https://robust.example\n\n"
          "### Engineer, Robust Systems Ltd\n- Built a thing.\n")
    assert lint_cv.findings_for(cv) == []


# ---- the real artifacts this was calibrated on ----------------------------

def _letter_corpus_paths():
    """An explicit fresh corpus is required to exist and contain letters.

    Without JOBHUNT_PROSE_CORPUS, retain the optional historical calibration
    corpus used by the default CI run. Never fall back from an explicit corpus.
    """
    import glob

    if "JOBHUNT_PROSE_CORPUS" in os.environ:
        value = os.environ["JOBHUNT_PROSE_CORPUS"]
        assert value.strip(), "JOBHUNT_PROSE_CORPUS must name a corpus directory"
        corpus = pathlib.Path(value).expanduser()
        assert corpus.is_dir(), f"JOBHUNT_PROSE_CORPUS is not a directory: {corpus}"
        letters = sorted(path for path in corpus.rglob("letter.yaml") if path.is_file())
        assert letters, f"JOBHUNT_PROSE_CORPUS contains no letter.yaml files: {corpus}"
        return letters

    return sorted(pathlib.Path(path) for path in glob.glob(str(
        pathlib.Path.home() / "code_project/job-hunt-workspace/iteration-2"
        / "eval-*/with_skill/run-1/outputs/workspace/**/letter.yaml"), recursive=True))


def _assert_letter_corpus_clean(letters):
    import yaml

    for path in letters:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        body = doc.get("body") or []
        joined = "\n".join(str(p) for p in (body if isinstance(body, list) else [body]))
        noisy = [f for f in prose_tells.vocabulary_findings(joined, path)
                 + prose_tells.prose_findings(joined, path)
                 if "NOT_JUST" in f or "AI_VOCABULARY" in f or "TRICOLON" in f]
        assert not noisy, f"{path}: {noisy}"


def test_the_skill_own_letters_do_not_trip_the_vocabulary_or_the_pivot():
    """Use JOBHUNT_PROSE_CORPUS for fresh output, or optional iteration-2 data."""
    letters = _letter_corpus_paths()
    if not letters:
        pytest.skip("the iteration-2 results tree is not on this machine")
    _assert_letter_corpus_clean(letters)


@pytest.mark.parametrize("machine_written", [False, True])
def test_an_explicit_fresh_letter_corpus_is_actually_linted(tmp_path, monkeypatch,
                                                          machine_written):
    import yaml

    letter = tmp_path / "fresh-run" / "outputs" / "letter.yaml"
    letter.parent.mkdir(parents=True)
    letter.write_text(yaml.safe_dump({"body": MACHINE_LETTER if machine_written
                                     else HUMAN_LETTER}), encoding="utf-8")
    monkeypatch.setenv("JOBHUNT_PROSE_CORPUS", str(tmp_path))
    assert _letter_corpus_paths() == [letter]
    if machine_written:
        with pytest.raises(AssertionError, match="AI_VOCABULARY"):
            test_the_skill_own_letters_do_not_trip_the_vocabulary_or_the_pivot()
    else:
        test_the_skill_own_letters_do_not_trip_the_vocabulary_or_the_pivot()


@pytest.mark.parametrize("state", ["missing", "empty", "file", "blank"])
def test_an_invalid_explicit_corpus_fails_instead_of_skipping(tmp_path, monkeypatch,
                                                           state):
    corpus = tmp_path / "corpus"
    if state == "empty":
        corpus.mkdir()
    elif state == "file":
        corpus.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("JOBHUNT_PROSE_CORPUS", "" if state == "blank" else str(corpus))
    with pytest.raises(AssertionError, match="JOBHUNT_PROSE_CORPUS"):
        test_the_skill_own_letters_do_not_trip_the_vocabulary_or_the_pivot()


def test_the_default_historical_corpus_remains_optional(tmp_path, monkeypatch):
    monkeypatch.delenv("JOBHUNT_PROSE_CORPUS", raising=False)
    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: tmp_path))
    with pytest.raises(pytest.skip.Exception, match="iteration-2"):
        test_the_skill_own_letters_do_not_trip_the_vocabulary_or_the_pivot()


def test_a_finding_location_is_not_given_a_phantom_column():
    """`where` is used verbatim when the caller already resolved the line.
    Appending unconditionally produced "cv.md:7:1" — a location that reads like a
    column and is not one, on every bullet finding."""
    one = prose_tells.vocabulary_findings("Spearheaded a rebuild.", "cv.md:7")
    assert one and one[0].startswith("AI_VOCABULARY: cv.md:7: ")
    many = prose_tells.vocabulary_findings("ok\nSpearheaded a rebuild.", "letter.md")
    assert many and many[0].startswith("AI_VOCABULARY: letter.md:2: ")


def test_a_repeated_term_is_reported_once():
    """The docstring promises one finding per distinct term. Reporting each
    occurrence turns one habit into six lines and buries the other findings —
    the reader stops reading a gate that repeats itself."""
    text = "A robust design.\nA robust pipeline.\nA robust test suite."
    found = prose_tells.vocabulary_findings(text, "letter.md")
    assert len(found) == 1 and "letter.md:1" in found[0]


# ---- the third surface: the answer that is actually marked -----------------

HUMAN_STATEMENT = """### Making Effective Decisions (250 words)

Our ward ran a paper triage list until 2024. I proposed replacing it after a
night shift where two escalations were missed because the list was in a folder
someone had taken to another floor.

I wrote the case, took it to the ward manager and the clinical governance lead,
and lost the first round: they wanted evidence it would not slow handover. So I
timed thirty handovers on the old process and thirty on a paper prototype, and
came back with the numbers. The second round passed.

Six months on, the escalation log shows no missed escalations attributable to
the list. I would not claim the change caused that on its own; the ward also
gained two band-6 nurses in the same period.
"""


def _statement_gate(text, tmp_path):
    import subprocess
    (tmp_path / "supporting-statement.md").write_text(text, encoding="utf-8")
    (tmp_path / "posting.yaml").write_text("application_type: structured\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_word_limits.py"),
                        "--workspace", str(tmp_path)], capture_output=True, text=True, encoding="utf-8")
    return r.stdout


def test_the_scored_supporting_statement_reports_the_tells(tmp_path):
    """This is the artifact that actually gets MARKED — the three CV judges are
    routed away from a structured application by design, so before this the most
    machine-sounding statement possible exited 0 clean."""
    out = _statement_gate("""### Making Effective Decisions (250 words)

I spearheaded a pivotal review of the triage process. This was not just an
administrative exercise — it was a chance to delve into the intricate realm of
clinical prioritisation, showcasing my ability to analyse, consult, and decide.
I would be a valuable asset to your team.
""", tmp_path)
    assert "AI_VOCABULARY" in out and "spearheaded" in out
    assert "NOT_JUST_PIVOT" in out


def test_a_real_supporting_statement_is_clean(tmp_path):
    """The cry-wolf check on the third surface. A gate that fires on a good
    criterion answer is a gate that gets switched off."""
    assert _statement_gate(HUMAN_STATEMENT, tmp_path).strip() == ""


def test_each_criterion_is_measured_on_its_own_body(tmp_path):
    """Densities over the whole file let a clean 250-word answer dilute a dense
    one, and the finding could not say which criterion to rewrite."""
    out = _statement_gate(HUMAN_STATEMENT + """
### Communicating and Influencing (250 words)

I thrive in a fast-paced environment and bring a relentless drive to every
project — a cutting-edge, seamless approach to stakeholder engagement.
""", tmp_path)
    assert "'Communicating and Influencing (250 words)'" in out
    assert "'Making Effective Decisions (250 words)'" not in out


def test_the_past_tense_pivot_is_caught():
    """A criterion answer is written about work already done. Listing only the
    present forms meant "not just an audit — it WAS a chance to…" went
    unreported with the whole construction sitting there."""
    assert prose_tells.NOT_JUST_PIVOT.search(
        "This was not just an audit — it was a chance to rebuild trust.")
