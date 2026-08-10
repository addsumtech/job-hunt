import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import check_skill_lossless as csl

LINE = ("Never fabricate experience, skills, titles, dates, or credentials — "
        "this rule overrides every other instinct in this skill.")


def _tree(root, files):
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


def test_normalize_folds_form_but_not_words():
    assert csl.normalize("**Honest** reframing — only!") == csl.normalize("honest reframing only")
    assert csl.normalize("- Honest reframing") == csl.normalize("Honest reframing")
    assert csl.normalize("诚实 改写") == "诚实 改写"
    assert csl.normalize("honest reframing") != csl.normalize("honest")


def test_lossless_when_the_line_merely_moved_to_another_file(tmp_path, capsys):
    base = _tree(tmp_path / "base", {"SKILL.md": f"# Old\n\n{LINE}\n"})
    new = _tree(tmp_path / "new", {"SKILL.md": "# New\n",
                                   "references/honesty.md": f"## Honesty\n\n{LINE}\n"})
    rc = csl.main(["--baseline", str(base), "--skill-dir", str(new)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "LOSSLESS" in out


def test_lossless_when_the_line_was_only_re_wrapped(tmp_path, capsys):
    """Reflowing a paragraph must stay quiet — a check that fires on ordinary
    editing is a check everyone learns to skip."""
    base = _tree(tmp_path / "base", {"SKILL.md": f"{LINE}\n"})
    wrapped = LINE.replace("— ", "—\n")
    new = _tree(tmp_path / "new", {"SKILL.md": f"{wrapped}\n"})
    assert csl.main(["--baseline", str(base), "--skill-dir", str(new)]) == 0
    assert "LOSSLESS" in capsys.readouterr().out


def test_content_lost_when_the_line_is_gone(tmp_path, capsys):
    base = _tree(tmp_path / "base", {"SKILL.md": f"# Old\n\n{LINE}\n"})
    new = _tree(tmp_path / "new", {"SKILL.md": "# New\n"})
    rc = csl.main(["--baseline", str(base), "--skill-dir", str(new)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "CONTENT LOST" in out
    assert "Never fabricate experience" in out


def test_content_lost_when_the_line_was_condensed(tmp_path, capsys):
    """The failure this exists for: 'split into references' quietly becoming
    'rewrite and condense'."""
    base = _tree(tmp_path / "base", {"SKILL.md": f"{LINE}\n"})
    new = _tree(tmp_path / "new", {"SKILL.md": "Never fabricate experience.\n"})
    assert csl.main(["--baseline", str(base), "--skill-dir", str(new)]) == 1
    assert "CONTENT LOST" in capsys.readouterr().out


def test_an_allowlisted_line_stops_failing_the_build(tmp_path, capsys):
    base = _tree(tmp_path / "base", {"SKILL.md": f"{LINE}\n"})
    new = _tree(tmp_path / "new", {"SKILL.md": "# New\n"})
    allow = tmp_path / "allow.json"
    allow.write_text(json.dumps({
        "waived": {csl.line_key(csl.normalize(LINE)): "superseded by lint_no_prediction.py"},
        "deleted_files": {},
    }), encoding="utf-8")
    rc = csl.main(["--baseline", str(base), "--skill-dir", str(new), "--allow", str(allow)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "1 waived" in out


def test_editing_a_waived_line_revokes_its_waiver(tmp_path, capsys):
    base = _tree(tmp_path / "base", {"SKILL.md": f"{LINE} And a new clause.\n"})
    new = _tree(tmp_path / "new", {"SKILL.md": "# New\n"})
    allow = tmp_path / "allow.json"
    allow.write_text(json.dumps({
        "waived": {csl.line_key(csl.normalize(LINE)): "reason"},
        "deleted_files": {},
    }), encoding="utf-8")
    assert csl.main(["--baseline", str(base), "--skill-dir", str(new), "--allow", str(allow)]) == 1


def test_a_stale_deleted_files_entry_fails_instead_of_rotting(tmp_path, capsys):
    base = _tree(tmp_path / "base", {"SKILL.md": "# Old\n"})
    new = _tree(tmp_path / "new", {"SKILL.md": "# Old\n",
                                   "assets/cv/template.tex": "\\documentclass{article}\n"})
    allow = tmp_path / "allow.json"
    allow.write_text(json.dumps({
        "waived": {},
        "deleted_files": {"assets/cv/template.tex": "dead and drifted"},
    }), encoding="utf-8")
    rc = csl.main(["--baseline", str(base), "--skill-dir", str(new), "--allow", str(allow)])
    assert rc == 1
    assert "NOT_DELETED: assets/cv/template.tex" in capsys.readouterr().out


def test_short_structural_lines_are_not_checked(tmp_path, capsys):
    """`---`, bare bullets and one-word headings carry no rule and would fail
    every time a heading is renamed."""
    base = _tree(tmp_path / "base", {"SKILL.md": "---\n# Steps\n- one\n"})
    new = _tree(tmp_path / "new", {"SKILL.md": "# Pipeline\n"})
    assert csl.main(["--baseline", str(base), "--skill-dir", str(new)]) == 0


def test_docs_are_not_part_of_the_corpus(tmp_path, capsys):
    """A line that survives only in docs/ has not survived: the design doc is
    not something a skill trigger can reach. It matters in production too —
    this plan file quotes SKILL.md verbatim and lives under docs/, so a
    recursive corpus would let a condensed SKILL.md report LOSSLESS."""
    base = _tree(tmp_path / "base", {"SKILL.md": f"{LINE}\n"})
    new = _tree(tmp_path / "new", {"SKILL.md": "# New\n",
                                   "docs/superpowers/specs/design.md": LINE})
    assert csl.main(["--baseline", str(base), "--skill-dir", str(new)]) == 1


def test_test_fixtures_are_outside_the_corpus_on_both_sides(tmp_path, capsys):
    """Both sides of the comparison must use the SAME membership rule. When the
    git-ref baseline read `scripts/tests/fixtures/*.yaml` and the on-disk corpus
    did not, a byte-identical tree reported 26 lines lost — a check that cries
    wolf on the very run it was written for."""
    base = _tree(tmp_path / "base", {
        "SKILL.md": "# Old\n",
        "scripts/tests/fixtures/full_profile.yaml":
            "summary: a long enough line of prose to be checked\n"})
    new = _tree(tmp_path / "new", {"SKILL.md": "# Old\n"})
    assert csl.main(["--baseline", str(base), "--skill-dir", str(new)]) == 0
    assert "LOSSLESS" in capsys.readouterr().out


def test_an_unreadable_baseline_ref_is_exit_2_not_a_crash(tmp_path, capsys):
    """`could not run` is exit 2 with a message, not sys.exit(str) — which
    exits 1 and makes 'the baseline is unreachable' indistinguishable from
    'content was lost'."""
    new = _tree(tmp_path / "new", {"SKILL.md": "# New\n"})
    rc = csl.main(["--baseline", "no-such-ref", "--repo", str(tmp_path),
                   "--skill-dir", str(new)])
    assert rc == 2
    assert "no-such-ref" in capsys.readouterr().err
