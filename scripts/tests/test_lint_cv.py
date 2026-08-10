import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import journal
import lint_cv

CLEAN = """# Test User

## Experience

### Research Engineer — Acme (2022–present)
- Built a GPU reconstruction pipeline that cut scan time from 12 to 7 minutes.
- Drove the migration of 40 clinical protocols onto the new solver.
- Drove a two-person team through the vendor integration with Philips.
- Advised the finance team on a leveraged buyout of the imaging division.

## Skills
- Python, C++, PyTorch
"""


def _cv(tmp_path, text=CLEAN):
    ws = tmp_path / "acme-engineer-2026-08-09"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "cv.md").write_text(text, encoding="utf-8")
    return ws


def test_a_clean_cv_passes_silently(tmp_path, capsys):
    ws = _cv(tmp_path)
    assert lint_cv.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_leveraged_buyout_is_not_a_cliche(tmp_path):
    """A finance CV legitimately says 'leveraged buyout'. Firing on it would
    teach the reader to skip every CLICHE line."""
    assert lint_cv.findings_for("- Advised on a leveraged buyout of the division.") == []


def test_two_bullets_opening_with_the_same_verb_is_not_flagged(tmp_path):
    """Two is variation; three is a template. The threshold has to sit where
    ordinary writing does not trip it.

    The fixture opens two bullets with 'Drove' rather than 'Led' on purpose:
    `findings_for` only tracks openers of 4+ characters, so a three-letter verb
    is never counted and a test built on it would pass without the threshold
    ever being reached — proving the button exists, not that pressing it does
    anything. Measured on CLEAN: openers == {'built': [6], 'drove': [7, 8],
    'advised': [9], 'python': [12]}."""
    assert [f for f in lint_cv.findings_for(CLEAN) if f.startswith("REPEATED_VERB")] == []


def test_cliche_is_reported_with_its_line_number(tmp_path, capsys):
    ws = _cv(tmp_path, CLEAN + "\n- A results-driven engineer with a proven track record.\n")
    assert lint_cv.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "CLICHE: cv.md:" in out
    assert "results-driven" in out and "proven track record" in out


def test_weak_openers_are_reported(tmp_path, capsys):
    ws = _cv(tmp_path, "# X\n- Responsible for the reconstruction pipeline and its tests.\n")
    assert lint_cv.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "WEAK_OPENER: cv.md:2" in out and "Responsible for" in out


def test_an_over_long_bullet_is_reported_with_its_length(tmp_path, capsys):
    long_bullet = "- " + ("Rebuilt the acquisition pipeline end to end " * 8).strip() + "."
    ws = _cv(tmp_path, "# X\n" + long_bullet + "\n")
    assert lint_cv.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "LONG_BULLET: cv.md:2" in out and "characters" in out


def test_three_bullets_with_the_same_opening_verb_are_reported(tmp_path, capsys):
    text = ("# X\n"
            "- Spearheaded the solver rewrite across two teams.\n"
            "- Spearheaded the vendor migration for 40 protocols.\n"
            "- Spearheaded the clinical rollout at three sites.\n")
    ws = _cv(tmp_path, text)
    assert lint_cv.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "REPEATED_VERB" in out and "spearheaded" in out
    assert "2, 3, 4" in out


def test_missing_cv_is_exit_2(tmp_path, capsys):
    ws = tmp_path / "empty"; ws.mkdir()
    assert lint_cv.main(["--workspace", str(ws)]) == 2
    assert "cv.md" in capsys.readouterr().err


def test_each_run_leaves_exactly_one_receipt_including_the_exit_2_path(tmp_path):
    ws = _cv(tmp_path)
    lint_cv.main(["--workspace", str(ws)])
    (ws / "cv.md").unlink()
    assert lint_cv.main(["--workspace", str(ws)]) == 2
    assert [r["verdict"] for r in journal.read_receipts(ws, "lint_cv")] == \
        ["pass", "could_not_run"]
