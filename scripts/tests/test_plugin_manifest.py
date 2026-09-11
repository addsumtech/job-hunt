"""The two install paths key off manifests nothing else reads.

`npx skills add addsumtech/job-hunt` copies the repository root and reads
`SKILL.md`'s frontmatter. `/plugin marketplace add addsumtech/job-hunt` reads
`.claude-plugin/marketplace.json`, which points at `.claude-plugin/plugin.json`.
Neither file is exercised by any other test, and a typo in either one fails at
the user's terminal rather than here.

The specific hazard is version drift. travel-buddy keeps its version in four
hand-maintained places and they have disagreed before, which is why
marketplace.json is GENERATED from plugin.json rather than retyped, and why the
README's badge is checked against both.
"""
import json
import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLUGIN = ROOT / ".claude-plugin" / "plugin.json"
MARKET = ROOT / ".claude-plugin" / "marketplace.json"
SKILL = ROOT / "SKILL.md"
READMES = [ROOT / "README.md"] + [
    ROOT / f"README_{lang}.md" for lang in ("EN", "JA", "KO", "ES")
]
HUB_LISTINGS = (
    "https://skillhub.cn/skills/user_f486c577/best-job-hunt",
    "https://clawhub.ai/dong845/skills/job-hunt",
)


def _json(p):
    return json.loads(p.read_text(encoding="utf-8"))


def _skill_frontmatter():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "SKILL.md has no frontmatter; npx skills reads it"
    return yaml.safe_load(text.split("---\n", 2)[1])


def test_both_manifests_parse():
    assert _json(PLUGIN)["name"] and _json(MARKET)["name"]


def test_the_plugin_name_is_the_skill_name():
    """Three places name this skill and a user types the third: the install line
    is `/plugin install <plugin name>@<marketplace name>`."""
    fm = _skill_frontmatter()
    assert fm["name"] == _json(PLUGIN)["name"] == _json(MARKET)["name"]
    assert _json(MARKET)["plugins"][0]["name"] == fm["name"]


def test_the_skill_frontmatter_carries_a_description():
    """`npx skills add` lists the skill by this line; without it the entry is
    blank and the model has nothing to route on either."""
    fm = _skill_frontmatter()
    assert len(str(fm.get("description", "")).strip()) > 80


def test_the_marketplace_entry_agrees_with_the_plugin_manifest():
    """Generated from it, so this is the check that it stayed generated."""
    p, entry = _json(PLUGIN), _json(MARKET)["plugins"][0]
    for field in ("name", "description", "version", "homepage", "repository",
                  "license", "keywords", "author"):
        assert entry[field] == p[field], f"{field} disagrees between the two manifests"
    assert _json(MARKET)["metadata"]["version"] == p["version"]


def test_the_plugin_source_is_the_repository_root():
    """The repo root IS the skill — SKILL.md sits at the top level. A `source`
    pointing anywhere else installs an empty plugin, and the failure shows up as
    a skill that is present but never triggers."""
    assert _json(MARKET)["plugins"][0]["source"] == "./"
    assert SKILL.is_file()
    assert not (ROOT / "skills").exists(), (
        "a skills/ directory would mean the layout moved; source './' is now wrong")


def test_the_version_is_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", _json(PLUGIN)["version"])


@pytest.mark.parametrize("readme", READMES, ids=lambda p: p.name)
def test_the_readme_advertises_the_manifest_version(readme):
    """A badge or an install line quoting a version the manifests do not carry
    sends people to a release that does not exist."""
    text = readme.read_text(encoding="utf-8")
    quoted = set(re.findall(r"[-/]v?(\d+\.\d+\.\d+)[-)\s\"']", text))
    if not quoted:
        pytest.skip("this README does not quote a version")
    assert quoted == {_json(PLUGIN)["version"]}, (
        f"{readme.name} quotes {sorted(quoted)}, the manifests say "
        f"{_json(PLUGIN)['version']}")


@pytest.mark.parametrize("readme", READMES, ids=lambda p: p.name)
def test_both_install_paths_are_documented(readme):
    """A manifest nobody is told about installs nothing."""
    text = readme.read_text(encoding="utf-8")
    assert "npx skills add addsumtech/job-hunt" in text, f"{readme.name} omits the npx path"
    assert "/plugin marketplace add addsumtech/job-hunt" in text, (
        f"{readme.name} omits the plugin path")
    assert "/plugin install job-hunt@job-hunt" in text, (
        f"{readme.name} omits the install line; the marketplace add alone does nothing")


@pytest.mark.parametrize("readme", READMES, ids=lambda p: p.name)
def test_the_readme_links_to_supported_skill_hubs(readme):
    """Listing pages follow the release badge and precede the project image."""
    text = readme.read_text(encoding="utf-8")
    release = "https://github.com/addsumtech/job-hunt/releases"
    hero = "docs/assets/hero.jpg"
    for url in HUB_LISTINGS:
        assert url in text, f"{readme.name} omits {url}"
        assert text.index(release) < text.index(url) < text.index(hero), (
            f"{readme.name} does not place {url} after the release block")


def test_the_repository_url_matches_the_documented_install_target():
    """`npx skills add addsumtech/job-hunt` and the repository field have to name
    the same repo, or one of the two install paths reaches a different tree."""
    repo = _json(PLUGIN)["repository"]
    assert repo.endswith("/addsumtech/job-hunt"), repo
    for readme in READMES:
        assert "addsumtech/job-hunt" in readme.read_text(encoding="utf-8")
