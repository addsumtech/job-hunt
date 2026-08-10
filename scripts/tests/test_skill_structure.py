import json
import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import enter_mode
import vocab

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SKILL = ROOT / "SKILL.md"
ANCHORS = json.loads((pathlib.Path(__file__).parent / "required_inline.json")
                     .read_text(encoding="utf-8"))["anchors"]


def _self_check_section() -> str:
    text = SKILL.read_text(encoding="utf-8")
    m = re.search(r"^## Self-check.*?(?=^## |\Z)", text, re.M | re.S)
    assert m, "SKILL.md has no '## Self-check' section"
    return m.group(0)


@pytest.mark.parametrize("anchor", ANCHORS, ids=lambda a: a["text"][:40])
def test_every_layer1_rule_is_inline_in_skill_md(anchor):
    """Each of these fails SILENTLY if skipped — no lint, no artifact, no test
    reports it. `why` on each anchor records what goes wrong without it."""
    assert anchor["text"] in SKILL.read_text(encoding="utf-8"), \
        f"missing from SKILL.md: {anchor['text']!r} — {anchor['why']}"


def test_the_self_check_names_every_reference_file():
    section = _self_check_section()
    for f in sorted((ROOT / "references").glob("*.md")):
        assert f"references/{f.name}" in section, f"self-check does not name {f.name}"


def test_the_self_check_names_every_agent_file():
    section = _self_check_section()
    for f in sorted((ROOT / "agents").glob("*.md")):
        assert f"agents/{f.name}" in section


def test_the_self_check_names_every_mode_file():
    section = _self_check_section()
    for f in sorted((ROOT / "modes").glob("*.md")):
        assert f"modes/{f.name}" in section


def test_the_self_check_names_every_script():
    # Library-only modules: imported by gates, never invoked as a step, so a
    # checklist line for them would be a line the reader can never tick. Every
    # later plan extends this set for its own libraries and — more importantly —
    # adds its own gates to the self-check, or this test goes red.
    #
    # PLANS 2, 3 AND 4: this set is APPENDED TO, never replaced. Plan 1 owns the
    # four names below; Plan 3 adds "opencli_meta.py"; Plan 4 adds "mock_vocab.py"
    # and "mock_blocks.py"; Plan 2 adds nothing (it has no library-only module).
    # Written as a whole-line replacement instead of an append, whichever plan
    # lands last silently deletes the earlier plans' entries and the deletion
    # shows up as an unrelated red test in someone else's task.
    skip = {"journal.py", "paths.py", "rounds.py", "vocab.py"}
    section = _self_check_section()
    for f in sorted((ROOT / "scripts").glob("*.py")):
        if f.name in skip:
            continue
        assert f"scripts/{f.name}" in section, f"self-check does not name {f.name}"


def test_every_path_the_self_check_names_exists():
    """The other direction: a checklist that names a file nobody wrote sends the
    model to read nothing and report it as done."""
    for rel in re.findall(r"`((?:references|agents|modes|scripts|assets)/[\w./-]+)`",
                          _self_check_section()):
        assert (ROOT / rel).exists(), f"self-check names a missing path: {rel}"


def test_the_apply_mode_file_defines_the_honest_stop_schema():
    """modes/apply.md is layer 1.5 because it defines an artifact field
    check_apply.py requires. If this stops being true the mode file becomes an
    ordinary reference and loses its backstop."""
    text = (ROOT / "modes" / "apply.md").read_text(encoding="utf-8")
    assert "honest-stop.yaml" in text
    for token in ("poorly_built", "honest_stretch", "classification", "evidence"):
        assert token in text, f"modes/apply.md does not define {token}"


def test_skill_md_tells_the_run_to_record_mode_entry():
    text = SKILL.read_text(encoding="utf-8")
    assert "scripts/enter_mode.py" in text
    assert "journal.jsonl" in text


def test_the_frontmatter_name_matches_the_skill_directory():
    head = SKILL.read_text(encoding="utf-8").split("---")[1]
    assert re.search(r"^name:\s*job-hunt\s*$", head, re.M)


def test_the_description_names_all_four_modes():
    """The description is trigger text. Carried over from the baseline "with the
    name changed" it would describe applying to one job and nothing else, so a
    "find me roles" request would never reach the file that says discover is not
    built yet — and nothing would report it, because the name check above passes
    either way."""
    head = SKILL.read_text(encoding="utf-8").split("---")[1].lower()
    for mode in enter_mode.MODES:
        assert mode in head, f"the frontmatter description never mentions {mode}"
    assert "honest reframing only" in head
    assert "probability" in head          # the D2 promise is in the trigger text


def test_every_mode_named_in_skill_md_has_a_file_or_is_marked_unbuilt():
    text = SKILL.read_text(encoding="utf-8")
    for mode in enter_mode.MODES:
        if (ROOT / "modes" / f"{mode}.md").exists():
            continue
        assert re.search(rf"{mode}.{{0,80}}not yet", text, re.I | re.S), \
            f"SKILL.md names the {mode} mode but there is no modes/{mode}.md and no " \
            f"'not yet' marker — a mode that does not exist must not read as available"


def test_a_mode_that_exists_is_not_still_described_as_not_yet_built():
    """The other direction, and it is the one that rots. This plan ships SKILL.md
    saying discover, assess and interview are not yet built; Plans 2, 3 and 4 each
    land one of those mode files. The guard above only fires when a file is
    ABSENT, so once the file exists the stale sentence passes every check and
    layer 1 tells the model to refuse a mode that works. This turns that
    coordination hope into a red suite."""
    text = re.sub(r"\s+", " ",
                  SKILL.read_text(encoding="utf-8").replace("`", "")).lower()
    for mode in ("discover", "assess", "interview"):
        if (ROOT / "modes" / f"{mode}.md").exists():
            assert f"{mode} is not yet built" not in text, (
                f"modes/{mode}.md exists — delete '{mode} is not yet built in this "
                f"repo' from SKILL.md's Modes table and give the row its real status")


def test_skill_md_carries_the_apply_verdict_block_and_its_disclaimer():
    """spec §6: the block template AND the disclaimer, because the disclaimer is
    the only thing standing between a count and a prediction. New prose, so it
    cannot be an anchor in required_inline.json (those must quote the baseline)."""
    text = SKILL.read_text(encoding="utf-8")
    for token in ("投递建议：", "强烈建议投", "硬性阻断",
                  "不是对面试或录用概率的预测"):
        assert token in text, f"SKILL.md is missing {token!r} from the advice block"
    # Asked of vocab.py rather than typed, because a closed-vocabulary label
    # spelled a second way in prose is the exact drift vocab.py exists to stop
    # — and prose is the one place no other test compares against the module.
    assert vocab.VERDICT_ZH[vocab.REFUSAL] in text, (
        f"SKILL.md does not carry {vocab.VERDICT_ZH[vocab.REFUSAL]!r} verbatim; "
        f"the refusal label is spelled by vocab.py, never re-typed")


def test_skill_md_carries_the_banned_vocabulary_and_its_one_exception():
    text = SKILL.read_text(encoding="utf-8")
    for token in ("likely to be hired", "strong candidate", "would pass",
                  "Success Profiles", "Quoting the employer's scale is reporting"):
        assert token in text, f"SKILL.md is missing {token!r} from the banned list"


def test_skill_md_lists_every_posting_field_including_company():
    """The condensation defect that already shipped: SKILL.md:71's table dropped
    salary_range and application_type, and `application_type: structured` is the
    ONLY signal that routes to the supporting-statement branch. `company` is new
    and load-bearing — check_letter.py hard-fails without it."""
    text = SKILL.read_text(encoding="utf-8")
    for field in ("role_title", "company", "seniority", "location", "must_haves",
                  "nice_to_haves", "responsibilities", "keywords",
                  "company_values_tone", "red_flags", "salary_range",
                  "application_type"):
        assert field in text, f"the extraction field table is missing {field}"


def test_skill_md_carries_the_grounding_contract_summary():
    """spec §8's three mechanisms. Without the summary in layer 1 the model has
    three separate rules and no account of why none of them substitutes for
    another — which is exactly when one gets treated as covering for a missing
    other."""
    text = SKILL.read_text(encoding="utf-8")
    for token in ("check_evidence_refs.py", "claims.yaml", "check_conventions.py",
                  "a floor on credibility, not a proof",
                  "restated in exactly three places"):
        assert token in text, f"SKILL.md is missing {token!r} from §8's summary"


# Scripts a later plan builds. A path named in SKILL.md or a mode file that does not
# exist yet is a forward reference, which is fine — but only if it is DECLARED here,
# so it is a decision rather than a dangling pointer. The pair of tests below pins it
# from both sides: an undeclared missing script fails, and a declared one that has
# since been built ALSO fails, which is what forces the entry out when its plan lands.
NOT_YET_BUILT: dict[str, str] = {}


def _named_scripts() -> dict[str, list[str]]:
    """Every `<name>.py` mentioned anywhere in SKILL.md or a mode file, and where."""
    found: dict[str, list[str]] = {}
    files = [SKILL] + sorted((ROOT / "modes").glob("*.md"))
    for f in files:
        for name in set(re.findall(r"\b([a-z_]+\.py)\b", f.read_text(encoding="utf-8"))):
            found.setdefault(name, []).append(f.name)
    return found


def test_every_script_named_in_layer_1_or_a_mode_file_exists_or_is_declared_pending():
    """The Self-check guard only reads the `## Self-check` section. SKILL.md names
    scripts elsewhere too — the grounding-contract summary and the gate table both do —
    and a name there that resolves to nothing sends the model to run a command that is
    not there. Nothing else reports that."""
    for name, where in sorted(_named_scripts().items()):
        if (ROOT / "scripts" / name).exists():
            continue
        assert name in NOT_YET_BUILT, (
            f"{' and '.join(where)} names scripts/{name}, which does not exist and is "
            f"not declared in NOT_YET_BUILT — either build it, stop naming it, or "
            f"declare it with the plan that owns it")


def test_a_pending_script_that_now_exists_is_removed_from_the_declaration():
    """Self-retracting, like the Modes table. The moment its plan lands the script,
    this goes red and the stale 'not yet built' note has to come out — otherwise the
    declaration quietly becomes a lie that reads exactly like the truth."""
    for name, owner in sorted(NOT_YET_BUILT.items()):
        assert not (ROOT / "scripts" / name).exists(), (
            f"scripts/{name} exists now ({owner} landed) — delete its NOT_YET_BUILT "
            f"entry so the declaration keeps meaning something")
