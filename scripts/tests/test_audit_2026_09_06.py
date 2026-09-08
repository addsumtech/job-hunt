"""Defects found by a four-way adversarial audit on 2026-09-06.

Every test here pins something that was REPRODUCED, not reasoned about. Most of
the defects were introduced the same day, by the multi-language master store and
the delivery step; two were older. They are collected in one file because they
share a cause worth seeing together: each was a function that looked right in
isolation and was wrong about what its CALLER would hand it.

The categories, in the order they cost a user something:

  data loss        a master profile overwritten with no backup
  wrong document   the first draft delivered under the name the user opens
  gate lies        a gate reporting a state it did not check
  leak             protected personal data reaching a CV that must not carry it
"""
import os
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import deliver  # noqa: E402
import enter_mode  # noqa: E402
import journal  # noqa: E402
import paths  # noqa: E402
import render_cv  # noqa: E402
import save_profile  # noqa: E402


# ══ data loss ═══════════════════════════════════════════════════════════════
#
# `normalise_language` was not idempotent: f("Chinese (Simplified)") gave
# "chinese-simplified" and f of THAT gave "zh". `save_profile` looked the master
# up under the first key and `master_profile` built the filename from the second,
# so the lookup missed, `replaced` was None, NO BACKUP was taken — and the write
# landed on profile.zh.yaml anyway, destroying the user's Chinese CV. The run
# printed "new slot" and "no other master profiles" and exited 0.

@pytest.mark.parametrize("spelling", [
    "Chinese (Simplified)", "English (US)", "Dutch (Netherlands)",
    "French Canadian", "Japanese (business)", "English", "en-US", "中文",
    "Klingon", "zh", "",
])
def test_normalise_language_is_idempotent(spelling):
    once = paths.normalise_language(spelling)
    assert paths.normalise_language(once) == once, (
        f"{spelling!r} -> {once!r} -> {paths.normalise_language(once)!r}; the key "
        "and the filename are then built from different values")


@pytest.mark.parametrize("spelling, key", [
    ("Chinese (Simplified)", "zh"), ("English (US)", "en"),
    ("Dutch (Netherlands)", "nl"), ("French Canadian", "fr"),
    ("Japanese (business)", "ja"),
])
def test_a_qualified_language_name_lands_in_the_plain_slot(spelling, key):
    assert paths.normalise_language(spelling) == key


@pytest.mark.parametrize("value", [False, True, None])
def test_a_yaml_boolean_is_not_a_language(value):
    """`language: no` is Norwegian to a human and False to YAML; `on`/`yes` give
    True. Filing a CV under "true" is worse than refusing it, and save_profile
    refuses when the key is empty."""
    assert paths.normalise_language(value) == ""


def test_a_qualified_language_does_not_destroy_the_existing_master(tmp_path, monkeypatch):
    """The end-to-end reproduction of the data loss."""
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path)
    store = tmp_path / "demo"
    store.mkdir()
    (store / "profile.zh.yaml").write_text(
        "meta: {name: Demo, language: zh}\nmarker: THE-REAL-CHINESE-MASTER\n",
        encoding="utf-8")
    incoming = tmp_path / "in.yaml"
    incoming.write_text(
        'meta: {name: Demo, language: "Chinese (Simplified)"}\nmarker: NEW\n',
        encoding="utf-8")

    assert save_profile.main(["--name", "demo", "--profile", str(incoming)]) == 0
    backups = list(store.glob("profile.zh.yaml.bak-*"))
    assert backups, "the existing Chinese master was replaced with no backup"
    assert "THE-REAL-CHINESE-MASTER" in backups[0].read_text(encoding="utf-8")
    assert not (store / "profile.chinese-simplified.yaml").exists()


def test_three_saves_in_one_day_keep_the_original(tmp_path, monkeypatch):
    """Each `.bak-<date>` overwrote the last while both runs printed "backed up",
    so the version the user started with was unrecoverable."""
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path)
    store = tmp_path / "demo"
    store.mkdir()
    (store / "profile.yaml").write_text(
        "meta: {name: D, language: en}\nmarker: V1\n", encoding="utf-8")
    incoming = tmp_path / "in.yaml"
    for marker in ("V2", "V3"):
        incoming.write_text(f"meta: {{name: D, language: en}}\nmarker: {marker}\n",
                            encoding="utf-8")
        assert save_profile.main(["--name", "demo", "--profile", str(incoming)]) == 0
    kept = "".join(b.read_text(encoding="utf-8") for b in store.glob("*.bak-*"))
    assert "V1" in kept and "V2" in kept


def test_a_second_master_claiming_the_same_language_is_reported(tmp_path, monkeypatch, capsys):
    """`master_profiles` keeps the first and drops the rest — which is all a
    mapping can do — but dropping SILENTLY meant a CV the user wrote was
    invisible to the provenance gate while save_profile said it did not exist."""
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path)
    store = tmp_path / "demo"
    store.mkdir()
    (store / "profile.yaml").write_text(
        "meta: {name: D, language: zh}\nmarker: FIRST\n", encoding="utf-8")
    (store / "profile.zh.yaml").write_text(
        "meta: {name: D, language: 中文}\nmarker: SECOND\n", encoding="utf-8")
    assert set(paths.master_profile_collisions("demo")) == {"zh"}
    incoming = tmp_path / "in.yaml"
    incoming.write_text("meta: {name: D, language: zh}\nmarker: NEW\n", encoding="utf-8")
    save_profile.main(["--name", "demo", "--profile", str(incoming)])
    err = capsys.readouterr().err
    assert "claimed by more than one file" in err
    assert "profile.zh.yaml" in err


def test_a_legacy_untagged_master_is_reachable(tmp_path, monkeypatch):
    """Every candidate onboarded before languages were tracked has an untagged
    `profile.yaml`, filed under "". `master_for_language` fell through to a
    computed path that did not exist, and apply mode's baseline step died:
    `cannot run check_claims: --master must point at an existing profile.yaml`."""
    monkeypatch.setattr(paths, "PROFILES_ROOT", tmp_path)
    store = tmp_path / "demo"
    store.mkdir()
    legacy = store / "profile.yaml"
    legacy.write_text("meta: {name: Demo}\nskills: {programming: [Python]}\n",
                      encoding="utf-8")
    for language in ("en", "zh", "nl", ""):
        assert paths.master_for_language("demo", language) == legacy


# ══ wrong document ══════════════════════════════════════════════════════════

def test_redelivering_overwrites_the_name_the_user_opens(tmp_path):
    """The `-2` rename fired on every redelivery, so the obvious filename in
    Downloads was frozen at round 1 forever. A user opening `<slug>-cv.md` after
    three judge rounds read the FIRST draft, and could send it to the employer."""
    ws = tmp_path / "ws"
    ws.mkdir()
    dest = tmp_path / "out"
    for marker in ("DRAFT-1", "DRAFT-2", "FINAL-3"):
        (ws / "cv.md").write_text(f"# cv\n{marker}\n", encoding="utf-8")
        assert deliver.main(["--workspace", str(ws), "--to", str(dest),
                             "--no-pdf"]) == 0
    assert sorted(p.name for p in dest.iterdir()) == ["ws-cv.md"]
    assert "FINAL-3" in (dest / "ws-cv.md").read_text(encoding="utf-8")


def test_three_paths_that_used_to_collide_all_arrive(tmp_path):
    """Joining the relative path with `-` moved the collision one level up:
    `mock/answer/guide.md`, `mock/answer-guide.md` and `mock-answer-guide.md` all
    flattened to one name, and the run reported three deliveries over two files."""
    ws = tmp_path / "ws"
    (ws / "mock" / "answer").mkdir(parents=True)
    (ws / "mock" / "answer" / "guide.md").write_text("FILE-A\n", encoding="utf-8")
    (ws / "mock" / "answer-guide.md").write_text("FILE-B\n", encoding="utf-8")
    (ws / "mock-answer-guide.md").write_text("FILE-C\n", encoding="utf-8")
    dest = tmp_path / "out"
    assert deliver.main(["--workspace", str(ws), "--to", str(dest), "--no-pdf"]) == 0
    assert len(list(dest.iterdir())) == 3
    assert {p.read_text(encoding="utf-8").strip() for p in dest.iterdir()} == \
        {"FILE-A", "FILE-B", "FILE-C"}


def test_one_unreadable_file_does_not_abandon_the_round(tmp_path, monkeypatch):
    """It raised, exited 1 — which this script's contract says is impossible and
    which in this repo means "ran and found problems" — and left no journal
    record, so a partial delivery could not be told from one that never ran."""
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "a-cv.md").write_text("A\n", encoding="utf-8")
    blocked = ws / "b-cv.docx"
    blocked.write_text("B\n", encoding="utf-8")
    (ws / "c-letter.md").write_text("C\n", encoding="utf-8")
    # Windows copy2 can use CopyFile2 without Python open(); stage the OS
    # failure at the copy boundary while retaining real copies for other files.
    copy2 = deliver.shutil.copy2

    def guarded_copy(src, dst, *args, **kwargs):
        if src == blocked:
            raise PermissionError("Permission denied")
        return copy2(src, dst, *args, **kwargs)

    monkeypatch.setattr(deliver.shutil, "copy2", guarded_copy)
    dest = tmp_path / "out"
    assert deliver.main(["--workspace", str(ws), "--to", str(dest),
                         "--no-pdf"]) == 0
    assert sorted(p.name for p in dest.iterdir()) == ["ws-a-cv.md", "ws-c-letter.md"]
    import json
    rec = [json.loads(l) for l
           in (ws / "journal.jsonl").read_text(encoding="utf-8").splitlines()
           if l.strip()]
    delivery = [r for r in rec if r.get("action") == "delivery"][0]
    assert any("not delivered" in n for n in delivery["pdf_refused"])


# ══ gate lies ═══════════════════════════════════════════════════════════════

@pytest.mark.parametrize("verdict, expected", [
    ("pass", True), ("recorded", True), ("could_not_run", False), ("fail", False),
])
def test_only_a_decided_assessment_counts_as_present(tmp_path, verdict, expected):
    """`_assessment_present` matched the gate NAME and never read the verdict, so
    a `could_not_run` receipt made `check_apply` suppress its NO_ASSESSMENT
    notice — and the completion message never said "no fit assessment was made",
    which modes/apply.md requires it to say."""
    ws = tmp_path / verdict
    ws.mkdir()
    journal.receipt(ws, "check_assessment", {}, verdict,
                    [] if expected else ["NO_INPUT: posting.yaml is absent"])
    assert enter_mode._assessment_present(ws) is expected


# ══ leak ════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("market, place", [
    ("Wilmington, DE", "Delaware"), ("Boise, ID", "Idaho"),
    ("Indianapolis, IN", "Indiana"), ("St. John's, NL", "Newfoundland"),
])
def test_a_us_or_canadian_subdivision_code_resolves_to_the_safe_side(market, place):
    """Four two-letter codes are both a country this table knows and a Cluster-1
    subdivision. `Wilmington, DE` resolved to cluster 2 and rendered a date of
    birth, an age, a marital status, a nationality and a photo onto a US CV — the
    exact fields US employers bin a CV for carrying. No warning fired, and
    `check_personal_data` exited 0 because it calls the same resolver."""
    assert render_cv.resolve_cluster(market) == 1, place
    assert render_cv._suppress_personal_data(
        {"meta": {"target_market": market}}) is True


@pytest.mark.parametrize("market, cluster", [
    ("Berlin, Germany", 2), ("Amsterdam, Netherlands", 2), ("Jakarta, Indonesia", 3),
    ("Mumbai, India", 3), ("Los Angeles, CA", 1), ("London, United Kingdom", 1),
])
def test_writing_the_country_out_still_resolves_to_its_real_cluster(market, cluster):
    """The safe side is only acceptable because the escape hatch works: the fix
    must not make a German or Indonesian CV unreachable."""
    assert render_cv.resolve_cluster(market) == cluster


def test_the_ambiguous_code_says_why_it_chose_the_safe_side(capsys):
    """Over-stripping silently would leave a German user with no idea why the
    photo vanished. Every other withhold in this module is loud."""
    render_cv._AMBIGUOUS_WARNED.clear()
    render_cv.resolve_cluster("Frankfurt, DE")
    err = capsys.readouterr().err
    assert "both a country code and a" in err
    assert "Delaware" in err
    assert "write it out" in err


@pytest.mark.parametrize("market, cluster", [
    ("nl", 2), ("de", 2), ("id", 3), ("in", 3),
    ("NL-based", 2), ("NL-remote", 2), ("DE-based", 2),
    ("Netherlands", 2), ("Germany", 2), ("Indonesia", 3), ("India", 3),
])
def test_a_bare_or_modified_code_is_still_the_country(market, cluster):
    """The narrowing that keeps the fix from over-reaching.

    Nobody writes `meta.target_market: "DE"` meaning Delaware, and `NL-remote` is
    a Dutch remote role. The subdivision reading applies only to the
    `<place>, <CODE>` shape — the first version of this fix flagged bare codes
    too and turned every Dutch and German CV into a Cluster-1 strip.
    """
    assert render_cv.resolve_cluster(market) == cluster


def test_a_european_city_with_a_code_takes_the_safe_side_and_says_so(capsys):
    """`Eindhoven, NL` and `Wilmington, DE` are the same shape and the renderer
    has no gazetteer. It takes the cheaper error and names it; writing
    "Netherlands" restores the photo."""
    render_cv._AMBIGUOUS_WARNED.clear()
    assert render_cv.resolve_cluster("Eindhoven, NL (hybrid)") == 1
    assert "write it out" in capsys.readouterr().err
    assert render_cv.resolve_cluster("Eindhoven, Netherlands") == 2
