import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import check_word_limits as cwl
import journal

POSTING = {"company": "NHS Trust", "role_title": "Clinical Scientist",
           "application_type": "structured"}
STAR = ("At the trust I owned the migration of the reporting pipeline. The task was "
        "to cut a four-hour nightly batch without losing any audit trail. I profiled "
        "the job, rewrote the two slowest stages, and agreed a rollback plan with the "
        "data protection officer before touching production. The batch now finishes "
        "in forty minutes and no audit record has been lost since. ")

GOOD = ("# Supporting statement — Clinical Scientist, NHS Trust\n\n"
        "## Essential criteria\n\n"
        "### Making Effective Decisions (250 words)\n" + STAR + "\n\n"
        "### Communicating and Influencing (max 250 words)\n" + STAR + "\n")


def _ws(tmp_path, text=GOOD, posting=POSTING):
    ws = tmp_path / "nhs-clinical-scientist-2026-08-09"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "supporting-statement.md").write_text(text, encoding="utf-8")
    if posting is not None:
        (ws / "posting.yaml").write_text(yaml.safe_dump(posting, allow_unicode=True),
                                         encoding="utf-8")
    return ws


def test_a_statement_inside_its_limits_passes_silently(tmp_path, capsys):
    ws = _ws(tmp_path)
    assert cwl.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_both_limit_spellings_are_read(tmp_path):
    rows = cwl.sections(GOOD)
    assert [r[1] for r in rows] == [250, 250]
    assert all(0 < r[2] < 250 for r in rows)


def test_an_over_limit_criterion_is_caught_with_both_numbers(tmp_path, capsys):
    ws = _ws(tmp_path, GOOD.replace("(250 words)", "(40 words)"))
    assert cwl.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "OVER_LIMIT" in out and "Making Effective Decisions" in out and "40" in out
    assert out.count("OVER_LIMIT") == 1        # the 250-word criterion stays quiet


def test_an_unaddressed_criterion_is_caught(tmp_path, capsys):
    text = GOOD + "\n### Delivering at Pace (250 words)\n\n"
    ws = _ws(tmp_path, text)
    assert cwl.main(["--workspace", str(ws)]) == 1
    assert "EMPTY_CRITERION" in capsys.readouterr().out


def test_a_structured_posting_with_no_limits_anywhere_must_say_so(tmp_path, capsys):
    bare = GOOD.replace(" (250 words)", "").replace(" (max 250 words)", "")
    ws = _ws(tmp_path, bare)
    assert cwl.main(["--workspace", str(ws)]) == 1
    assert "NO_LIMIT_DECLARED" in capsys.readouterr().out
    ws2 = _ws(tmp_path / "declared",
              "<!-- word-limits: none stated in the posting -->\n" + bare)
    assert cwl.main(["--workspace", str(ws2)]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_an_unstructured_posting_is_not_policed(tmp_path, capsys):
    """A free-CV application has no scored criteria. Firing here would make this
    gate noise on the common case."""
    bare = GOOD.replace(" (250 words)", "").replace(" (max 250 words)", "")
    ws = _ws(tmp_path, bare, posting={"company": "Acme", "application_type": "cv"})
    assert cwl.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_a_structured_posting_with_no_criteria_headings_is_caught(tmp_path, capsys):
    ws = _ws(tmp_path, "# Supporting statement\n\n" + STAR)
    assert cwl.main(["--workspace", str(ws)]) == 1
    assert "NO_CRITERIA" in capsys.readouterr().out


def test_cjk_is_counted_by_character_not_as_one_giant_word(tmp_path):
    """A criterion answered in Chinese is a real case (the skill is bilingual).
    Splitting on whitespace would score a 600-character answer as three words."""
    rows = cwl.sections("### 沟通与影响 (200 words)\n" + "我负责该项目的交付与验收。" * 20 + "\n")
    assert rows[0][1] == 200 and rows[0][2] > 200


def test_a_missing_statement_is_exit_2_and_leaves_a_receipt(tmp_path, capsys):
    ws = _ws(tmp_path)
    (ws / "supporting-statement.md").unlink()
    assert cwl.main(["--workspace", str(ws)]) == 2
    assert "supporting-statement.md" in capsys.readouterr().err
    assert [r["verdict"] for r in journal.read_receipts(ws, "check_word_limits")] == \
        ["could_not_run"]


def test_each_run_leaves_exactly_one_receipt(tmp_path):
    ws = _ws(tmp_path)
    cwl.main(["--workspace", str(ws)])
    assert [r["verdict"] for r in journal.read_receipts(ws, "check_word_limits")] == \
        ["pass"]
