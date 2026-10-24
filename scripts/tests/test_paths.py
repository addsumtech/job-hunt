import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import paths


def test_profiles_root_is_under_the_claude_dir():
    assert paths.PROFILES_ROOT == pathlib.Path.home() / ".claude" / "job-profiles"


def test_skill_root_is_the_repo_root_and_holds_this_test():
    """Every script that needs the skill root asks paths for it. A script that
    re-derives it with .parent.parent works until someone moves the file."""
    assert paths.SKILL_ROOT == pathlib.Path(__file__).resolve().parent.parent.parent
    assert (paths.SKILL_ROOT / "scripts" / "paths.py").is_file()


def test_mode_file_and_allowlist_resolve_under_an_explicit_root(tmp_path):
    assert paths.mode_file("apply", tmp_path) == tmp_path / "modes" / "apply.md"
    assert paths.mode_file("apply") == paths.SKILL_ROOT / "modes" / "apply.md"
    assert paths.lossless_allowlist(tmp_path) == \
        tmp_path / "scripts" / "lossless-allowlist.json"


@pytest.mark.parametrize("raw,expected", [
    ("Acme Corp.", "acme-corp"),
    ("Senior ML Engineer", "senior-ml-engineer"),
    ("  Donghang  ", "donghang"),
    ("R&D / Imaging", "r-d-imaging"),
    ("ASML Netherlands B.V.", "asml-netherlands-b-v"),
])
def test_slugify(raw, expected):
    assert paths.slugify(raw) == expected


def test_slugify_keeps_cjk_so_a_chinese_employer_does_not_become_an_empty_name():
    assert paths.slugify("字节跳动") == "字节跳动"
    assert paths.slugify("北京 字节跳动") == "北京-字节跳动"


def test_workspace_shape_is_company_role_date(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path)
    ws = paths.workspace("Donghang", "Acme Corp.", "Senior ML Engineer", "2026-08-09")
    assert ws == tmp_path / "donghang" / "applications" / "acme-corp-senior-ml-engineer-2026-08-09"


def test_workspace_rejects_a_date_that_is_not_iso(tmp_path, monkeypatch):
    """A bad date must not silently produce a directory the resume lookup
    will never find again."""
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path)
    with pytest.raises(ValueError):
        paths.workspace("Donghang", "Acme", "Engineer", "Aug 9 2026")


def test_the_shared_spine_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path)
    d = tmp_path / "donghang"
    assert paths.profile_dir("Donghang") == d
    assert paths.master_profile("Donghang") == d / "profile.yaml"
    assert paths.search_prefs("Donghang") == d / "search-preferences.yaml"
    assert paths.answer_bank("Donghang") == d / "answer-bank.md"
    assert paths.search_dir("Donghang", "2026-08-09-MRI recon NL") == \
        d / "searches" / "2026-08-09-mri-recon-nl"


def test_no_path_helper_creates_anything_on_disk(tmp_path, monkeypatch):
    """These are pure path builders. A helper that mkdir'd would create an
    empty workspace on a typo and make the resume lookup find a shell."""
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path)
    paths.workspace("Donghang", "Acme", "Engineer", "2026-08-09")
    paths.search_dir("Donghang", "slug")
    assert list(tmp_path.iterdir()) == []


def test_the_workspace_shape_can_be_inverted():
    ws = paths.workspace("Donghang", "ASML", "MR recon engineer", "2026-08-09")
    assert paths.profile_dir_of(ws) == paths.profile_dir("Donghang")
    assert paths.answer_bank_of(ws) == paths.answer_bank("Donghang")


def test_the_inverse_works_on_a_workspace_outside_the_profiles_root(tmp_path):
    """A gate is routinely pointed at a copied workspace or a test fixture. Inverting
    the SHAPE is the point; locating the home directory is not."""
    ws = tmp_path / "job-profiles" / "demo" / "applications" / "acme-eng-2026-08-09"
    ws.mkdir(parents=True)
    assert paths.profile_dir_of(ws) == tmp_path / "job-profiles" / "demo"
    assert paths.answer_bank_of(ws).name == paths.ANSWER_BANK_NAME


def test_a_directory_that_is_not_a_workspace_is_refused():
    with pytest.raises(ValueError, match="not a workspace"):
        paths.profile_dir_of(pathlib.Path("/tmp/somewhere"))


# ---------------------------------------------------------------------------
# slugify across writing systems. Audited 2026-09-05.
#
# The old rule was an allowlist of four scripts (ASCII, kana, CJK, hangul), so
# a Cyrillic, Greek, Arabic, Thai, Hebrew or Devanagari employer slugged to the
# EMPTY STRING. Two consequences, both silent: `profile_dir` then returned
# PROFILES_ROOT — the shared parent of every candidate's private data — and
# every such company shared one workspace, so the resume lookup this module
# exists to protect offered the wrong prior application.
# ---------------------------------------------------------------------------

_SCRIPTS = [
    ("ООО Яндекс", "ооо-яндекс"),          # Cyrillic
    ("ΟΤΕ Group", "οτε-group"),            # Greek
    ("שקל אלביט", "שקל-אלביט"),             # Hebrew
    ("阿里巴巴", "阿里巴巴"),                  # Han
    ("株式会社リクルート", "株式会社リクルート"),   # kana + Han
    ("삼성전자", "삼성전자"),                  # hangul
]


@pytest.mark.parametrize("name,expected", _SCRIPTS, ids=[s[0] for s in _SCRIPTS])
def test_a_name_in_any_script_keeps_its_letters(name, expected):
    assert paths.slugify(name) == expected


def test_scripts_that_spell_with_combining_marks_keep_them():
    """Thai vowel signs and Devanagari matras are Unicode Marks, not accents.
    A rule that stripped them would mangle the word rather than fold it."""
    assert paths.slugify("บริษัท ปตท.") == "บริษัท-ปตท"
    assert paths.slugify("टाटा कंसल्टेंसी") == "टाटा-कंसल्टेंसी"


def test_latin_diacritics_fold_rather_than_vanish():
    """`Müller` and `Möller` both became `m-ller`: two employers, one workspace."""
    assert paths.slugify("Müller GmbH") == "muller-gmbh"
    assert paths.slugify("Möller GmbH") == "moller-gmbh"
    assert paths.slugify("Müller GmbH") != paths.slugify("Möller GmbH")


def test_a_latin_name_folds_to_the_same_slug_as_its_unaccented_spelling():
    """The other half: `Société Générale` and `Societe Generale` are one employer,
    and two directories for them is the same resume-lookup failure mirrored."""
    assert paths.slugify("Société Générale") == paths.slugify("Societe Generale")


@pytest.mark.parametrize("name,expected", [
    ("Straße AG", "strasse-ag"), ("Łódź", "lodz"), ("Ærø", "aero"),
    ("Đại học FPT", "dai-hoc-fpt"), ("İstanbul", "istanbul"),
])
def test_latin_letters_nfkd_cannot_decompose_are_spelled_out(name, expected):
    assert paths.slugify(name) == expected


@pytest.mark.parametrize("bad", ["", "   ", "---", "!!!", "()"])
def test_a_name_with_no_letters_is_refused_rather_than_pointed_at_the_root(bad):
    """`profile_dir("")` returned PROFILES_ROOT itself. Loud is the only safe
    direction — an empty slug is a caller bug, never a real candidate."""
    with pytest.raises(ValueError):
        paths.profile_dir(bad)


@pytest.mark.parametrize("field", ["company", "role"])
def test_a_workspace_part_with_no_letters_is_refused(field):
    kwargs = {"company": "Acme", "role": "Engineer"}
    kwargs[field] = "!!!"
    with pytest.raises(ValueError):
        paths.workspace("tester", kwargs["company"], kwargs["role"], "2026-09-05")


def test_the_ordinary_case_is_unchanged():
    """The regression guard: the workspace shape is what resumption parses back."""
    assert paths.workspace("donghang-lyu", "DeepHealth", "Junior SWE",
                           "2026-09-05").name == "deephealth-junior-swe-2026-09-05"


# ---------------------------------------------------------------------------
# A run never lives inside the skill. `--workspace .` from the skill root put
# the candidate's private candidate-profile.yaml and a journal.jsonl into the
# skill directory, with nothing failing.
# ---------------------------------------------------------------------------

def test_the_skill_root_is_not_a_workspace(monkeypatch):
    assert paths.skill_workspace_refusal(paths.SKILL_ROOT).startswith("WORKSPACE_IN_SKILL:")
    monkeypatch.chdir(paths.SKILL_ROOT)
    for spelling in (".", "scripts/..", "./"):
        reason = paths.skill_workspace_refusal(spelling)
        assert reason.startswith("WORKSPACE_IN_SKILL:") and " is the job-hunt" in reason


def test_nothing_inside_the_skill_is_a_workspace_either(monkeypatch):
    monkeypatch.chdir(paths.SKILL_ROOT)
    for inside in ("evals/fixtures/workspaces/clean", "scripts/tests/fixtures/mock-dryrun",
                   "not-yet-created/round-1"):
        assert "is inside the job-hunt" in paths.skill_workspace_refusal(inside), inside


def test_a_workspace_outside_the_skill_is_accepted(tmp_path):
    ws = tmp_path / "job-profiles" / "demo" / "applications" / "acme-eng-2026-08-09"
    assert paths.skill_workspace_refusal(ws) == ""
    assert paths.skill_workspace_refusal(tmp_path) == ""


def test_a_sibling_that_shares_the_skill_roots_name_as_a_prefix_is_accepted(tmp_path):
    """Containment is by path component, not by string prefix: a workspace
    folder called `job-hunt-workspace` next to `job-hunt` is not inside it."""
    skill = tmp_path / "job-hunt"
    (skill / "scripts").mkdir(parents=True)
    sibling = tmp_path / "job-hunt-workspace" / "iteration-2"
    sibling.mkdir(parents=True)
    assert paths.skill_workspace_refusal(sibling, root=skill) == ""
    assert paths.skill_workspace_refusal(skill / "scripts", root=skill) != ""


def test_a_symlink_to_the_skill_is_still_the_skill(tmp_path):
    skill = tmp_path / "real" / "job-hunt"
    skill.mkdir(parents=True)
    link = tmp_path / "skills-link"
    link.symlink_to(skill, target_is_directory=True)
    assert paths.skill_workspace_refusal(link, root=skill) != ""
    assert paths.skill_workspace_refusal(link / "round", root=skill) != ""


def test_another_spelling_on_a_case_insensitive_disk_is_still_the_skill(tmp_path):
    skill = tmp_path / "Job-Hunt"
    skill.mkdir()
    other = tmp_path / "job-hunt"
    if not other.exists():
        pytest.skip("case-sensitive filesystem: the two spellings are two directories")
    assert paths.skill_workspace_refusal(other, root=skill) != ""
    assert paths.skill_workspace_refusal(other / "round", root=skill) != ""
