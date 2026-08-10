import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import check_letter
import journal

POSTING = {"company": "Acme Medical Systems B.V.",
           "role_title": "Senior Reconstruction Engineer",
           "must_haves": ["MRI reconstruction"]}

PARA = ("I have spent four years building GPU reconstruction pipelines for clinical "
        "MRI, and the work your team published on motion-resolved cine recon is the "
        "closest thing I have seen to the problem I want to keep solving. At Acme I "
        "rebuilt the solver that cut a twelve-minute scan to seven, working directly "
        "with radiographers to keep the protocol changes clinically safe and "
        "auditable across three hospital sites. ")


# PARA is 67 words (measured). The default body is FOUR paragraphs — 277 words,
# inside both the 250–400 word band and the 3–4 paragraph band. Three paragraphs
# would be 210 words, which trips the gate's own floor: every "passes silently"
# test would then fail, and the fixture would be teaching the reader that this
# gate cries wolf.
def _letter(body=None, **over):
    d = {"sender": {"name": "Test User", "email": "t@x.com", "location": "Delft"},
         "recipient": {"name": "Hiring Team", "company": "Acme Medical Systems B.V.",
                       "location": "Eindhoven"},
         "date": "2026-08-09",
         "salutation": "Geachte heer/mevrouw,",
         "body": body if body is not None else [
             PARA + "I am applying for the Senior Reconstruction Engineer role.",
             PARA, PARA, PARA],
         "closing": "Met vriendelijke groet,"}
    d.update(over)
    return d


def _ws(tmp_path, letter, posting=POSTING):
    ws = tmp_path / "acme-engineer-2026-08-09"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "letter.yaml").write_text(yaml.safe_dump(letter, allow_unicode=True),
                                    encoding="utf-8")
    if posting is not None:
        (ws / "posting.yaml").write_text(yaml.safe_dump(posting, allow_unicode=True),
                                         encoding="utf-8")
    return ws


def test_a_well_formed_letter_passes_silently(tmp_path, capsys):
    ws = _ws(tmp_path, _letter())
    assert check_letter.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_markdown_in_a_body_string_is_caught(tmp_path, capsys):
    """render_letter passes body strings through untouched, so '**bold**' prints
    four asterisks on the PDF."""
    body = _letter()["body"]
    body[1] = "I **rebuilt** the solver. " + PARA
    ws = _ws(tmp_path, _letter(body=body))
    assert check_letter.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "MARKDOWN_IN_BODY: body[1]" in out and "**" in out


def test_a_bulleted_body_paragraph_is_caught(tmp_path, capsys):
    body = _letter()["body"]
    body[2] = "- MRI reconstruction\n- GPU solvers\n" + PARA   # stays in the word band
    ws = _ws(tmp_path, _letter(body=body))
    assert check_letter.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "MARKDOWN_IN_BODY: body[2]" in out
    assert "WORD_COUNT" not in out and "PARA_COUNT" not in out


def test_word_count_below_the_floor_is_caught(tmp_path, capsys):
    ws = _ws(tmp_path, _letter(body=["Short.", "Also short.", "Still short."]))
    assert check_letter.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "WORD_COUNT" in out and "250" in out and "400" in out


def test_word_count_above_the_ceiling_is_caught(tmp_path, capsys):
    ws = _ws(tmp_path, _letter(body=[PARA * 3, PARA * 3, PARA * 3]))
    assert check_letter.main(["--workspace", str(ws)]) == 1
    assert "WORD_COUNT" in capsys.readouterr().out


def test_paragraph_count_outside_three_to_four_is_caught(tmp_path, capsys):
    """`motivation-letter.md:121`: "3–4 paragraphs total. Never a single
    monolithic block. Never more than 4 unless a specific structure requires it
    (rare)." A gate that silently permitted 5 would be enforcing a rule the
    reference does not contain."""
    ws = _ws(tmp_path, _letter(body=[PARA * 2, PARA * 2]))
    assert check_letter.main(["--workspace", str(ws)]) == 1
    assert "PARA_COUNT" in capsys.readouterr().out
    ws = _ws(tmp_path / "five", _letter(body=[PARA] * 5))
    assert check_letter.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "PARA_COUNT" in out and "5 paragraphs" in out


def test_sender_name_in_the_closing_prints_twice(tmp_path, capsys):
    """render_letter appends sender.name after the closing automatically."""
    ws = _ws(tmp_path, _letter(closing="Met vriendelijke groet,\nTest User"))
    assert check_letter.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "NAME_DUPLICATED" in out and "Test User" in out


def test_a_wrong_company_is_caught(tmp_path, capsys):
    letter = _letter()
    letter["recipient"]["company"] = "Acme Manufacturing"
    ws = _ws(tmp_path, letter)
    assert check_letter.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "COMPANY_MISMATCH" in out and "Acme Medical Systems B.V." in out


def test_a_shorter_but_matching_company_name_is_accepted(tmp_path, capsys):
    """'Acme Medical Systems' addressed to 'Acme Medical Systems B.V.' is
    correct in a letter; only a genuinely different name is an error."""
    letter = _letter()
    letter["recipient"]["company"] = "Acme Medical Systems"
    ws = _ws(tmp_path, letter)
    assert check_letter.main(["--workspace", str(ws)]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_a_letter_that_never_names_the_role_is_caught(tmp_path, capsys):
    ws = _ws(tmp_path, _letter(body=[PARA, PARA, PARA, PARA]))
    assert check_letter.main(["--workspace", str(ws)]) == 1
    out = capsys.readouterr().out
    assert "ROLE_NOT_NAMED" in out and "Senior Reconstruction Engineer" in out
    assert "WORD_COUNT" not in out and "PARA_COUNT" not in out   # one finding, not three


def test_a_posting_without_a_company_field_fails_loudly(tmp_path, capsys):
    ws = _ws(tmp_path, _letter(), posting={"role_title": "Senior Reconstruction Engineer"})
    assert check_letter.main(["--workspace", str(ws)]) == 1
    assert "NO_COMPANY_IN_POSTING" in capsys.readouterr().out


def test_a_missing_posting_is_exit_2(tmp_path, capsys):
    ws = _ws(tmp_path, _letter(), posting=None)
    assert check_letter.main(["--workspace", str(ws)]) == 2
    assert "posting.yaml" in capsys.readouterr().err


def test_each_run_leaves_exactly_one_receipt_including_the_exit_2_path(tmp_path):
    ws = _ws(tmp_path, _letter())
    check_letter.main(["--workspace", str(ws)])
    (ws / "posting.yaml").unlink()
    assert check_letter.main(["--workspace", str(ws)]) == 2
    assert [r["verdict"] for r in journal.read_receipts(ws, "check_letter")] == \
        ["pass", "could_not_run"]
