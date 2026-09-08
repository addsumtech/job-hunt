"""The five READMEs are the only thing most people will read.

They are also the documents nothing else in this repo checks, which is why they
drifted before: the layout section once asserted four hardcoded script names, so
the README could describe a single-mode `job-application` — three of four modes,
fourteen of thirty-two scripts, the whole market-conventions directory and the
entire searches/ workspace missing — and stay green for months.

The overview and technical reference must not disagree:

  README.md                 the Chinese overview a reader lands on
  README_EN/JA/KO/ES.md      the other four language editions
  REFERENCE.md               the layout, the workspace shape, the numbers

Language editions are a drift risk: a correction in one must reach the others.
Every shared contract below is therefore asserted on all five editions.
"""
import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
README = ROOT / "README.md"
REFERENCE = ROOT / "REFERENCE.md"
READMES = [README] + [ROOT / f"README_{lang}.md" for lang in ("EN", "JA", "KO", "ES")]


def _text(p=README):
    return p.read_text(encoding="utf-8")


def test_the_pipeline_is_not_duplicated_here():
    """Spec §9. The copy that lived in the README already omitted Step 7.5, so a
    reader who trusted it believed the run ended at 'Finalize'. One pipeline, in
    the file the model actually loads."""
    for p in READMES + [REFERENCE]:
        text = _text(p)
        assert "The skill executes these 8 steps" not in text, p.name
        assert not re.search(r"^\s*4\.\s+\*\*Gap analysis\*\*", text, re.M), p.name
    ref = _text(REFERENCE)
    assert "SKILL.md" in ref and "modes/apply.md" in ref


def test_the_layout_matches_the_repo():
    """DERIVED from the tree, not a hand-picked sample.

    Moved out of the README when that became an overview: a marketing page is the
    wrong place for a file listing, and a listing nobody reads is a listing that
    drifts. The invariant is unchanged — every script and every mode / agent /
    reference entry has to appear — only the file holding it moved.
    """
    text = _text(REFERENCE)
    assert "cv/template.tex" not in text and "letter/template.tex" not in text
    # The LAYOUT section, not the whole file. Checking the whole document meant a
    # name appearing in a usage snippet ("python3 scripts/mutants.py --ci")
    # satisfied the assertion, so the layout — the thing this test is named for —
    # could lose an entry and stay green.
    layout = text.split("## Layout", 1)[1].split("\n## ", 1)[0]
    missing = []
    for path in sorted((ROOT / "scripts").glob("*.py")):
        if path.name not in layout:
            missing.append(f"scripts/{path.name}")
    for folder in ("modes", "agents", "references"):
        for path in sorted((ROOT / folder).iterdir()):
            if path.name.startswith("."):
                continue
            if path.name not in layout:
                missing.append(f"{folder}/{path.name}")
    assert not missing, "the reference layout does not mention: " + ", ".join(missing)


def test_the_readme_names_the_skill_it_documents():
    for readme in READMES:
        assert _text(readme).startswith("# job-hunt"), readme.name
        for mode in ("discover", "assess", "apply", "interview"):
            assert mode in _text(readme), f"{readme.name} omits the {mode} mode"


def test_the_workspace_layout_is_documented_including_the_derived_files():
    """cv-source.txt, coverage.json and master-fingerprint.json are written into
    a workspace by this skill and appear in no design document. An undocumented
    artifact is one a later reader deletes as junk."""
    text = _text(REFERENCE)
    for name in ("applications/<company>-<role>-<YYYY-MM-DD>", "journal.jsonl",
                 "claims.yaml", "master-fingerprint.json", "cv-source.txt",
                 "coverage.json", "posting-source.txt", "judge-round-<n>.json"):
        assert name in text, f"the workspace layout does not mention {name}"


# ---- the honesty statements, in every language -----------------------------

def test_no_stale_test_count_claim():
    """'Expected: 41 tests' was wrong before the migration and wrong by more than
    a hundred after it. A number that nothing updates is a number that lies."""
    for p in READMES + [REFERENCE]:
        assert not re.search(r"\b\d+\s+tests?,\s+all passing", _text(p)), p.name


@pytest.mark.parametrize("readme", READMES, ids=lambda p: p.name)
def test_the_advertised_test_count_is_the_real_one(readme):
    """If a README states a test count, check it rather than trust it.

    The overview may explain the checks without a hand-maintained test count.

    Collected, not passed: "passed" depends on which optional binaries this
    machine has (one PDF test skips without poppler), and a figure that moves
    with the host is not a figure to print.

    A BAND, not an equality. Exact would be stricter and would also go red on
    every commit that adds a test — a check that fires on correct work gets
    switched off, and this repo has switched three of those off already. The
    dishonest direction is over-claiming, so that is the hard bound; the floor
    exists only so the figure cannot quietly fall a thousand behind.
    """
    claimed = {int(n.replace(",", "").replace("_", ""))
               for n in re.findall(r"([\d][\d,_]{2,})\s*(?:tests?|个测试|测试|件のテスト|개 테스트|pruebas)", _text(readme))}
    claimed |= {int(n) for n in re.findall(r"badge/(?:tests|测试)-(\d+)-", _text(readme))}
    if not claimed:
        # SKIP, never a bare return. A README with no count is a legitimate
        # choice; a guard that reports PASS while checking nothing is not.
        # Measured 2026-09-08: after the five-language rewrite dropped every
        # count, this test reported 5 passed and inspected 0 files. The repo has
        # now hit that shape three times (mutants.py's survives(), the
        # opt-in motif check, this), so the suite states its own emptiness.
        pytest.skip(f"{readme.name} states no test count; nothing to verify")
    out = subprocess.run([sys.executable, "-m", "pytest", str(ROOT / "scripts" / "tests"),
                          "-q", "--collect-only"], capture_output=True, text=True).stdout
    m = re.search(r"(\d+) tests? collected", out)
    assert m, f"could not read the collected count from pytest:\n{out[-400:]}"
    real = int(m.group(1))
    assert len(claimed) == 1, f"{readme.name} states two different test counts: {sorted(claimed)}"
    n = claimed.pop()
    assert n <= real, f"{readme.name} claims {n} tests; the suite has {real}"
    assert n >= real * 0.9, (f"{readme.name} claims {n} tests and the suite has {real} — "
                             f"more than 10% stale")


@pytest.mark.parametrize("readme", READMES, ids=lambda p: p.name)
def test_green_tests_are_not_sold_as_measured_behaviour(readme):
    """`make check` green means the code agrees with its own tests. It has never
    meant a mode was measured, and the README is exactly where that gets blurred.
    The earlier version of this test asserted the repo had run NO evaluation —
    true when written, false since iteration 2, and a stale disclaimer is its own
    dishonesty."""
    text = _text(readme)
    assert "evals/" in text, f"{readme.name} does not name the harness"
    phrase = {
        "README.md": "检查通过不等于产物正确",
        "README_EN.md": "Passing checks do not guarantee correct output",
        "README_JA.md": "チェックに通っても、成果物の正しさは保証されません",
        "README_KO.md": "검사를 통과해도 결과물의 정확성이 보장되지는 않습니다",
        "README_ES.md": "Superar las comprobaciones no garantiza que el resultado sea correcto",
    }[readme.name]
    assert phrase in text, f"{readme.name} is missing: {phrase}"


@pytest.mark.parametrize("readme", READMES, ids=lambda p: p.name)
def test_the_eval_result_carries_its_sample_size(readme):
    """Ten guards going FAIL to PASS is the strongest number in this repo, which
    is precisely why it must never appear without `n = 1` beside it. One run each
    is not a rate, and a reader who takes it for one has been misled by us."""
    text = _text(readme)
    if "FAIL" not in text:
        pytest.skip("this README does not quote the guard result")
    assert re.search(r"n\s*=\s*1", text), f"{readme.name} quotes the result without its n"


@pytest.mark.parametrize("readme", READMES, ids=lambda p: p.name)
def test_neither_readme_predicts_an_outcome(readme):
    """The skill is forbidden from predicting an interview or offer probability.
    A README that advertises one would be selling the thing the product refuses
    to do — and the marketing page is where that temptation actually lives."""
    text = _text(readme)
    # Both READMEs REFUSE these in prose, and the refusal has to name the thing
    # it refuses: "no '82% match'", "没有「匹配度 82%」". So a figure inside quotes
    # is the ban, and a figure outside them is the sale. Asserting the words are
    # absent would fail on the paragraph that bans them — the same free-substring
    # mistake this repo has already made twice.
    quoted = [m.span() for m in re.finditer(r'"[^"\n]*"|「[^」\n]*」|“[^”\n]*”', text)]
    for pattern in (r"\d+\s*%\s*(?:match|success|interview)", r"匹配度\s*\d+\s*%",
                    r"(?:interview|offer|面试|录取)\s*(?:rate|probability|概率|率)\s*[:：]\s*\d"):
        for hit in re.finditer(pattern, text, re.I):
            inside = any(a <= hit.start() and hit.end() <= b for a, b in quoted)
            assert inside, f"{readme.name} appears to advertise an outcome: {hit.group(0)!r}"


# ---- every edition stays connected ----------------------------------------

def test_each_readme_links_all_languages():
    for readme in READMES:
        text = _text(readme)
        for target in READMES:
            assert f'href="{target.name}"' in text, (readme.name, target.name)
        assert "README_CN.md" not in text, readme.name
    assert not (ROOT / "README_CN.md").exists()


@pytest.mark.parametrize("readme", READMES, ids=lambda p: p.name)
def test_every_referenced_file_exists(readme):
    """A README linking a moved file is the most-read broken thing in a repo.
    Covers images, docs and the eval record alike."""
    text = _text(readme)
    targets = re.findall(r'(?:src|href)="([^"#:]+)"', text)
    targets += re.findall(r"\]\(([^)#:]+\.(?:md|png|jpg|yaml|py))\)", text)
    missing = [t for t in targets if not (ROOT / t).exists()]
    assert not missing, f"{readme.name} references files that do not exist: {missing}"


@pytest.mark.parametrize("readme", READMES, ids=lambda p: p.name)
def test_the_four_modes_table_is_complete(readme):
    """A README that quietly documents three modes is how the last one went stale
    for months."""
    table = _text(readme).split("|---|", 1)
    assert len(table) > 1, f"{readme.name} has no mode table"
    for mode in ("discover", "assess", "apply", "interview"):
        assert f"**{mode}" in _text(readme), f"{readme.name}'s table omits {mode}"


def test_the_readmes_agree_on_the_market_tables():
    """The market inventory is counted and checked in all five languages."""
    tables = sorted((ROOT / "references" / "market-conventions").glob("*.yaml"))
    total = 0
    for t in tables:
        total += len(re.findall(r"^\s*-\s+id:", t.read_text(encoding="utf-8"), re.M))
    for p in READMES:
        text = _text(p)
        assert str(len(tables)) in text or {"5": "Five"}.get(str(len(tables)), "") in text, p.name
        assert str(total) in text, f"{p.name} does not state the real entry count ({total})"
