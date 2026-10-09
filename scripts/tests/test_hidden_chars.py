"""Invisible and BiDi control characters must not ship in source or docs.

U+202E and its siblings reorder how a reader sees a line without changing what
the compiler or interpreter reads, which is the Trojan Source vector: a comment
that displays as one thing and parses as another. U+00AD and the zero-width
family are the same problem in the other direction, a character nobody can see
sitting inside an identifier, a URL or a regex.

Both of the repo's real occurrences were legitimate in intent (a hyphen class
that has to ignore LaTeX's hyphenation, and a comment quoting measured Arabic
output), which is exactly why the rule is mechanical rather than a judgement
call: the literal character becomes an escape or goes away, and the gate says so
for every future one without anyone having to decide again.

Every fixture below is built with chr() at runtime. Typing the character into
this file would make the gate's own test suite its first exception, and an
exception is how the next one gets in.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import check_hidden_chars as chc

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

LF = chr(10)
BACKSLASH = chr(92)
AD = chr(0x00AD)
RLO = chr(0x202E)
POP = chr(0x202C)
NBSP = chr(0x00A0)


def run(argv, capsys):
    code = chc.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_the_shipped_tree_has_no_invisible_or_bidi_control_characters(capsys):
    """The check the static reviewer runs. Keep this green by fixing the file,
    never by narrowing the gate."""
    code, out, err = run(["--root", str(ROOT)], capsys)
    assert code == 0, "hidden characters are still in the tree:" + LF + out
    assert out == "", "stdout is findings-only and there are no findings"


def test_a_bidi_override_is_reported_with_file_line_and_codepoint(tmp_path, capsys):
    (tmp_path / "a.py").write_text("x = 1  # " + RLO + "reversed" + POP + LF,
                                   encoding="utf-8")
    code, out, err = run(["--root", str(tmp_path)], capsys)
    assert code == 1
    lines = out.strip().splitlines()
    assert len(lines) == 2, out
    assert lines[0].startswith("HIDDEN_CHAR: a.py:1:"), lines[0]
    assert "U+202E" in lines[0] and "RIGHT-TO-LEFT OVERRIDE" in lines[0], lines[0]
    assert "U+202C" in lines[1], lines[1]


def test_a_soft_hyphen_is_reported_with_its_column(tmp_path, capsys):
    (tmp_path / "doc.md").write_text("recog" + AD + "nised sponsor" + LF,
                                     encoding="utf-8")
    code, out, err = run(["--root", str(tmp_path)], capsys)
    assert code == 1
    assert "U+00AD" in out and "doc.md:1:6" in out, out


def test_every_targeted_codepoint_is_caught(tmp_path, capsys):
    """One file per codepoint. A set that catches only the two the reviewer
    happened to find is a gate tuned to one report."""
    wanted = list(chc.TARGETS) + [0xE0001, 0xE0041]
    for cp in wanted:
        d = tmp_path / ("c%04X" % cp)
        d.mkdir()
        (d / "f.txt").write_text("a" + chr(cp) + "b" + LF, encoding="utf-8")
    code, out, err = run(["--root", str(tmp_path)], capsys)
    assert code == 1
    for cp in wanted:
        assert ("U+%04X" % cp) in out, "U+%04X was not reported" % cp


def test_ordinary_text_does_not_fire(tmp_path, capsys):
    """Calibrated against the kind of text this repo is full of. A check that
    fires on correct input is worse than no check."""
    zh = "Qiu Zhi Bao Gao: " + chr(0x6C42) + chr(0x804C) + chr(0x5EFA) + chr(0x8BAE)
    eu = "Zo" + chr(0xEB) + " Nowak " + chr(0x2014) + " Moody" + chr(0x2019) + "s, caf" + chr(0xE9)
    nb = "8" + NBSP + chr(0xD7) + NBSP + "H200 " + chr(0x1F3AF)
    ar = chr(0x0623) + chr(0x062D) + chr(0x0645) + chr(0x062F)
    code_line = 'PAT = re.compile(r"[' + BACKSLASH + "xad" + BACKSLASH + '-]+")'
    (tmp_path / "zh.md").write_text(zh + LF, encoding="utf-8")
    (tmp_path / "eu.md").write_text(eu + LF, encoding="utf-8")
    (tmp_path / "nb.md").write_text(nb + LF, encoding="utf-8")
    (tmp_path / "ar.md").write_text(ar + LF, encoding="utf-8")
    (tmp_path / "code.py").write_text(code_line + LF, encoding="utf-8")
    code, out, err = run(["--root", str(tmp_path)], capsys)
    assert code == 0, out
    assert out == ""


def test_a_tree_with_nothing_to_scan_exits_2_not_0(tmp_path, capsys):
    """A scan that read no files is not a clean scan. Reporting 0 findings over
    0 files is how a gate goes green after a path change."""
    code, out, err = run(["--root", str(tmp_path)], capsys)
    assert code == 2, "empty tree must be could-not-run, got %r" % code
    assert "NO_FILES" in err, err


def test_binary_and_undecodable_files_are_skipped_without_crashing(tmp_path, capsys):
    (tmp_path / "img.png").write_bytes(bytes([0x89, 0x50, 0x4E, 0x47, 0xAD, 0x8D, 0x00]))
    (tmp_path / "latin.txt").write_bytes(("caf" + chr(0xE9) + " soft" + AD + "hyphen").encode("latin-1"))
    (tmp_path / "ok.md").write_text("plain" + LF, encoding="utf-8")
    code, out, err = run(["--root", str(tmp_path)], capsys)
    assert code == 0, out
    assert "UNREADABLE: latin.txt" in err, (
        "a file it could not decode must be named, not silently dropped")


def test_the_scanned_file_count_is_reported(tmp_path, capsys):
    (tmp_path / "a.md").write_text("x" + LF, encoding="utf-8")
    (tmp_path / "b.md").write_text("y" + LF, encoding="utf-8")
    code, out, err = run(["--root", str(tmp_path)], capsys)
    assert code == 0
    assert "2 files" in err, "the gate must say what it covered: %r" % err


def test_a_missing_root_exits_2(tmp_path, capsys):
    code, out, err = run(["--root", str(tmp_path / "nope")], capsys)
    assert code == 2
    assert "NO_INPUT" in err, err
