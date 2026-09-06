"""One candidate, one CV per language — and a new language never overwrites another.

The failure this guards is silent: a user with an English master supplies a
Chinese CV, the file is written to `profile.yaml`, and the English one is gone.
Nothing errors, nothing is logged, and the user finds out the next time they need
the file that is no longer there.
"""
import os
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import paths  # noqa: E402
import save_profile  # noqa: E402


@pytest.fixture
def store(tmp_path, monkeypatch):
    """A sandboxed profile store. Never the real one."""
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path)
    (tmp_path / "demo").mkdir()
    return tmp_path / "demo"


def write(path, language, marker):
    path.write_text(f"meta:\n  name: Demo\n  language: {language}\n"
                    f"  marker: {marker}\n", encoding="utf-8")


def save(tmp_path, language, marker, name="demo"):
    src = tmp_path / "incoming.yaml"
    write(src, language, marker)
    return save_profile.main(["--name", name, "--profile", str(src)])


# ---- the language normalisation the slots depend on -----------------------

@pytest.mark.parametrize("spelling", ["English", "en", "EN", "en-US", "en_GB", "英文"])
def test_every_spelling_of_one_language_is_one_slot(spelling):
    """Otherwise "English" and "en-US" become two masters for one CV, which is
    the same defect as an overwrite arriving from the other side."""
    assert paths.normalise_language(spelling) == "en"


@pytest.mark.parametrize("spelling, key", [
    ("Chinese", "zh"), ("中文", "zh"), ("zh-Hans", "zh"), ("繁體中文", "zh-tw"),
    ("Nederlands", "nl"), ("Deutsch", "de"), ("日本語", "ja"), ("한국어", "ko"),
])
def test_the_endonyms_and_codes_agree(spelling, key):
    assert paths.normalise_language(spelling) == key


def test_an_unknown_language_gets_its_own_slot_rather_than_a_refusal():
    """This skill writes CVs in languages the table has not been taught. Filing
    one under its own name beats rejecting a CV that is perfectly valid."""
    assert paths.normalise_language("Klingon") == "klingon"
    assert paths.normalise_language("") == ""
    assert paths.normalise_language(None) == ""


# ---- the slots themselves -------------------------------------------------

def test_a_new_language_never_touches_an_existing_master(store, tmp_path):
    write(store / "profile.yaml", "en", "ORIGINAL-EN")
    assert save(tmp_path, "zh", "NEW-ZH") == 0
    assert "ORIGINAL-EN" in (store / "profile.yaml").read_text(encoding="utf-8")
    assert "NEW-ZH" in (store / "profile.zh.yaml").read_text(encoding="utf-8")


def test_the_same_language_replaces_its_own_slot_and_backs_it_up(store, tmp_path):
    """The user asked for this half explicitly: same language may overwrite."""
    write(store / "profile.yaml", "en", "ORIGINAL-EN")
    assert save(tmp_path, "English", "SECOND-EN") == 0
    assert "SECOND-EN" in (store / "profile.yaml").read_text(encoding="utf-8")
    backups = list(store.glob("profile.yaml.bak-*"))
    assert backups, "the replaced master must be recoverable"
    assert "ORIGINAL-EN" in backups[0].read_text(encoding="utf-8")


def test_a_legacy_master_is_resolved_not_duplicated(store, tmp_path):
    """A user whose only master is `profile.yaml` holding an English CV has the
    English slot AT that path. A second English CV belongs in it — writing
    `profile.en.yaml` beside it would leave two English masters and no rule
    saying which one apply mode should read."""
    write(store / "profile.yaml", "en", "ORIGINAL-EN")
    assert save(tmp_path, "en", "SECOND-EN") == 0
    assert not (store / "profile.en.yaml").exists()
    assert "SECOND-EN" in (store / "profile.yaml").read_text(encoding="utf-8")


def test_the_language_comes_from_the_file_not_the_filename(store):
    """The renderer, the heading tables and the letter salutations all key off
    `meta.language`; a filename reaches none of them."""
    write(store / "profile.en.yaml", "zh", "MISLABELLED")
    found = paths.master_profiles("demo")
    assert found == {"zh": store / "profile.en.yaml"}


def test_three_languages_coexist(store, tmp_path):
    write(store / "profile.yaml", "en", "EN")
    assert save(tmp_path, "zh", "ZH") == 0
    assert save(tmp_path, "Nederlands", "NL") == 0
    assert set(paths.master_profiles("demo")) == {"en", "zh", "nl"}
    for marker, f in (("EN", "profile.yaml"), ("ZH", "profile.zh.yaml"),
                      ("NL", "profile.nl.yaml")):
        assert marker in (store / f).read_text(encoding="utf-8")


# ---- refusals, which are the point ----------------------------------------

def test_a_profile_with_no_language_is_refused(store, tmp_path):
    """The unsuffixed slot is where a legacy English master usually lives.
    Dropping an untagged CV there IS the overwrite this script prevents."""
    write(store / "profile.yaml", "en", "ORIGINAL-EN")
    src = tmp_path / "incoming.yaml"
    src.write_text("meta:\n  name: Demo\n", encoding="utf-8")
    assert save_profile.main(["--name", "demo", "--profile", str(src)]) == 2
    assert "ORIGINAL-EN" in (store / "profile.yaml").read_text(encoding="utf-8")


def test_an_unreadable_profile_is_refused(store, tmp_path):
    src = tmp_path / "incoming.yaml"
    src.write_text("meta: [this: is: not: a: mapping\n", encoding="utf-8")
    assert save_profile.main(["--name", "demo", "--profile", str(src)]) == 2


def test_a_missing_profile_is_refused(tmp_path):
    assert save_profile.main(["--name", "demo",
                              "--profile", str(tmp_path / "nope.yaml")]) == 2


def test_a_corrupt_master_does_not_hide_the_others(store):
    """One unparsable file must not make the store look empty — that is how an
    overwrite would be justified."""
    write(store / "profile.yaml", "en", "EN")
    (store / "profile.zz.yaml").write_text("[: broken\n", encoding="utf-8")
    assert "en" in paths.master_profiles("demo")


def test_dry_run_writes_nothing(store, tmp_path):
    write(store / "profile.yaml", "en", "ORIGINAL-EN")
    src = tmp_path / "incoming.yaml"
    write(src, "zh", "NEW-ZH")
    assert save_profile.main(["--name", "demo", "--profile", str(src),
                              "--dry-run"]) == 0
    assert not (store / "profile.zh.yaml").exists()


def test_it_runs_as_a_script(tmp_path):
    """The skill tells the model to run a COMMAND, so it has to work as one."""
    src = tmp_path / "incoming.yaml"
    write(src, "en", "X")
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "save_profile.py"),
                        "--name", "demo", "--profile", str(src), "--dry-run"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ---- the skill has to tell the run to use it ------------------------------

def test_both_layers_tell_the_run_to_save_through_the_script():
    for f in ("SKILL.md", "modes/apply.md"):
        t = (REPO / f).read_text(encoding="utf-8")
        assert "save_profile.py" in t, f
        assert "one CV per language" in t, f


def test_the_read_side_rule_is_stated_too():
    """Saving safely is half of it. A Chinese CV built from the English master
    throws away the file the user wrote for that purpose."""
    for f in ("SKILL.md", "modes/apply.md"):
        t = (REPO / f).read_text(encoding="utf-8")
        assert "tailor from the master whose language matches" in " ".join(t.split()), f


# ---- the master a RUN must be checked against -----------------------------
#
# REPRODUCED 2026-09-06, and it was introduced the same day. `modes/apply.md`
# told the run to compute `paths.master_profile('<name>')` with no language,
# which always returns `profile.yaml`. Once one candidate could have several
# masters, that pointed `check_claims.py` at the wrong one and the provenance
# gate — the thing that stops this skill inventing credentials — failed in BOTH
# directions on the same pair of files:
#
#   tailoring a Chinese CV, checked against profile.yaml
#     "CUDA", present in the Chinese master, was reported UNSOURCED
#     "Kubernetes", in NEITHER Chinese file, passed with exit 0
#
# The first is a gate crying wolf at a truthful CV. The second is an unsourced
# claim reaching a rendered CV with the gate green.

def test_the_resolver_prefers_an_existing_master_over_a_computed_path(store):
    """A legacy `profile.yaml` holding a Chinese CV IS the Chinese master;
    `master_profile(name, "zh")` would point past it at a file that does not
    exist."""
    write(store / "profile.yaml", "zh", "LEGACY-ZH")
    assert paths.master_for_language("demo", "zh") == store / "profile.yaml"
    assert paths.master_for_language("demo", "中文") == store / "profile.yaml"


def test_the_resolver_falls_back_to_a_new_slot_for_an_unseen_language(store):
    write(store / "profile.yaml", "en", "EN")
    assert paths.master_for_language("demo", "nl") == store / "profile.nl.yaml"


def test_the_resolver_picks_the_right_one_when_several_exist(store):
    write(store / "profile.yaml", "en", "EN")
    write(store / "profile.zh.yaml", "zh", "ZH")
    assert paths.master_for_language("demo", "en") == store / "profile.yaml"
    assert paths.master_for_language("demo", "zh") == store / "profile.zh.yaml"


def test_the_provenance_gate_reaches_opposite_verdicts_on_the_two_masters(store, tmp_path):
    """The end-to-end reproduction, both directions, in one test.

    This is the assertion that would have caught the defect: it does not check a
    path, it checks that the GATE's answer changes when the master does.
    """
    import subprocess
    write(store / "profile.yaml", "en", "EN")
    (store / "profile.yaml").write_text(
        "meta: {name: Li Wei, language: en}\nskills: {programming: [Python, Kubernetes]}\n",
        encoding="utf-8")
    (store / "profile.zh.yaml").write_text(
        "meta: {name: 李维, language: zh}\nskills: {programming: [Python, CUDA]}\n",
        encoding="utf-8")

    def verdict(tailored, master):
        ws = tmp_path / f"ws-{abs(hash((tailored, str(master))))}"
        ws.mkdir()
        (ws / "tailored-profile.yaml").write_text(tailored, encoding="utf-8")
        env = {**os.environ, "JOBHUNT_PROFILES_ROOT": str(store.parent)}
        for extra in (["--record"], []):
            r = subprocess.run(
                [sys.executable, str(REPO / "scripts" / "check_claims.py"),
                 "--workspace", str(ws), "--master", str(master), *extra],
                capture_output=True, text=True, env=env)
        return r.returncode, r.stdout

    zh_cv = "meta: {name: 李维, language: zh}\nskills: {programming: [Python, CUDA]}\n"
    wrong_rc, wrong_out = verdict(zh_cv, store / "profile.yaml")
    right_rc, _ = verdict(zh_cv, paths.master_for_language("demo", "zh"))
    assert wrong_rc == 1 and "CUDA" in wrong_out, "the wrong master should cry wolf"
    assert right_rc == 0, "CUDA is in the Chinese master and must pass"

    bad_cv = "meta: {name: 李维, language: zh}\nskills: {programming: [Python, Kubernetes]}\n"
    wrong_rc2, _ = verdict(bad_cv, store / "profile.yaml")
    right_rc2, right_out2 = verdict(bad_cv, paths.master_for_language("demo", "zh"))
    assert wrong_rc2 == 0, "the wrong master let an unsourced claim through"
    assert right_rc2 == 1 and "Kubernetes" in right_out2


def test_the_finding_names_the_master_it_actually_read(store, tmp_path):
    """It said "absent from profile.yaml" whatever file it had read, which sends
    the reader to check a document the gate never opened."""
    import subprocess
    (store / "profile.zh.yaml").write_text(
        "meta: {name: X, language: zh}\nskills: {programming: [Python]}\n", encoding="utf-8")
    ws = tmp_path / "ws"; ws.mkdir()
    (ws / "tailored-profile.yaml").write_text(
        "meta: {name: X, language: zh}\nskills: {programming: [Python, Rust]}\n",
        encoding="utf-8")
    env = {**os.environ, "JOBHUNT_PROFILES_ROOT": str(store.parent)}
    master = store / "profile.zh.yaml"
    for extra in (["--record"], []):
        r = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "check_claims.py"),
             "--workspace", str(ws), "--master", str(master), *extra],
            capture_output=True, text=True, env=env)
    assert "profile.zh.yaml" in r.stdout, r.stdout


def test_apply_mode_resolves_the_master_by_language():
    """The doc is where the defect actually lived: the code was right and the
    instruction computed the wrong path."""
    t = (REPO / "modes" / "apply.md").read_text(encoding="utf-8")
    assert "master_for_language" in t
    assert "paths.master_profile('<name>')" not in t, (
        "the language-less form is back, and it resolves to profile.yaml every time")
