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
