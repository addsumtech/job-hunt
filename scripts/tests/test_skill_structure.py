import json
import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import check_apply
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


def _self_check_items() -> str:
    """Only the CHECKLIST ITEMS — each `- [ ]` line plus its indented continuations.

    `_self_check_section()` runs to end-of-file, because `## Self-check` is the last
    heading. So `"references/cv-craft.md" in section` is satisfied by the name appearing
    ANYWHERE below that heading, including in ordinary prose. Measured: deleting
    cv-craft.md's READ trigger line and mentioning the filename in a sentence appended
    at the end left all 59 structure tests green. A checklist whose entries can be
    satisfied by prose is not a checklist — and this section is spec section 6's third
    backstop, the one that is supposed to catch a reference file nobody routed to.

    Naive `^- \\[ \\]` filtering is wrong in the other direction: it reports 17 false
    missing entries, because most items wrap onto indented continuation lines."""
    lines = _self_check_section().split("\n")
    out, in_item = [], False
    for line in lines:
        if re.match(r"^\s*- \[ \]", line):
            in_item = True
            out.append(line)
        elif in_item and line.strip() and line.startswith((" ", "\t")):
            out.append(line)          # a continuation of the item above
        else:
            in_item = False
    return "\n".join(out)


def test_the_self_check_is_the_last_section_so_its_boundary_is_known():
    """Everything above depends on where this section ends. It has no closing marker —
    the regex stops at the next `## ` or at EOF — so a section appended AFTER it is
    swallowed whole. That has already happened once: plan 3 appended a discovery block
    and two reference files silently inherited a pass from prose inside the swallowed
    region (fixed in 54b20fc). Appending here is exactly what a later plan is told to
    do, so the invariant has to be a test rather than a convention."""
    headings = re.findall(r"^## .*$", SKILL.read_text(encoding="utf-8"), re.M)
    assert headings[-1].startswith("## Self-check"), (
        f"SKILL.md's last section is {headings[-1]!r}, not the self-check. Move the new "
        f"section ABOVE '## Self-check' — the self-check has no closing marker, so "
        f"anything below it is read as part of it and its guards start passing on prose.")


@pytest.mark.parametrize("anchor", ANCHORS, ids=lambda a: a["text"][:40])
def test_every_layer1_rule_is_inline_in_skill_md(anchor):
    """Each of these fails SILENTLY if skipped — no lint, no artifact, no test
    reports it. `why` on each anchor records what goes wrong without it."""
    assert anchor["text"] in SKILL.read_text(encoding="utf-8"), \
        f"missing from SKILL.md: {anchor['text']!r} — {anchor['why']}"


def test_the_self_check_names_every_reference_file():
    section = _self_check_items()
    for f in sorted((ROOT / "references").glob("*.md")):
        assert f"references/{f.name}" in section, f"self-check does not name {f.name}"


def test_the_self_check_names_every_agent_file():
    section = _self_check_items()
    for f in sorted((ROOT / "agents").glob("*.md")):
        assert f"agents/{f.name}" in section


def test_the_self_check_names_every_mode_file():
    section = _self_check_items()
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
    skip = {"journal.py", "paths.py", "rounds.py", "vocab.py",
            "cli_io.py",                         # imported by CLI entry points
            "report_locales.py",                 # shared text, imported by gates
            "opencli_meta.py",                    # Plan 3 — leave it
            "mock_vocab.py", "mock_blocks.py",    # imported, never invoked
            # A MAINTAINER tool, not a run-time gate: it mutates the repo in a
            # temp copy and re-runs the suite. Naming it in the self-check would
            # tell a run to execute it mid-application, which is both useless to
            # that run and slow. Same category as check_skill_lossless, which is
            # CI-only for the same reason.
            "mutants.py",
            # The shared AI-tell library. `lint_cv`, `check_letter` and
            # `check_word_limits` import it; nothing runs it, so a checklist line
            # for it would be a line the reader can never tick.
            "prose_tells.py",
            # Discovery matching is shared policy and rendering logic. The gate
            # invokes it; a run must invoke `check_candidate_match.py`, not this
            # import-only module.
            "candidate_match.py",
            # Renderer host diagnostics are shared by doctor and render_cv;
            # there is no standalone run step for a user to invoke.
            "host_execution.py",
            # Imported by the browser launcher and evidence gates; no CLI.
            "browser_budget.py",
            # Shared Word artifact validation; renderers and delivery invoke it.
            "docx_content.py",
            # Reads references/discovery-sources.md for check_shortlist; there is
            # no run step, and a self-check line telling a round to "run the
            # catalogue" would describe work nobody does.
            "discovery_catalogue.py"}
    section = _self_check_items()
    for f in sorted((ROOT / "scripts").glob("*.py")):
        if f.name in skip:
            continue
        assert f"scripts/{f.name}" in section, f"self-check does not name {f.name}"


def _self_check_block(header_fragment: str) -> str:
    """The blank-line-delimited block of the self-check whose heading says this."""
    for block in re.split(r"\n\s*\n", _self_check_section()):
        if header_fragment in " ".join(block.split()):
            return block
    raise AssertionError(
        f"SKILL.md's self-check has no block whose heading says {header_fragment!r} — "
        f"the required / not-required partition is pinned against check_apply.py by "
        f"name, so renaming a heading has to be a deliberate edit here too")


def _gates_in(block: str) -> set:
    """The gates a block's checklist BULLETS name — not its heading, which names
    `scripts/check_apply.py` itself in every one of these blocks."""
    bullets = [ln for ln in block.split("\n") if ln.lstrip().startswith("- [ ]")]
    return set(re.findall(r"`?scripts/([a-z_]+)\.py`?", "\n".join(bullets)))


def test_the_self_check_partition_matches_what_check_apply_actually_requires():
    """The heading over this list used to say `check_apply.py` requires all ten
    gates. Two of them — check_pages and check_word_limits — were not in
    REQUIRED_GATES at all, and a checklist that overstates its backstop is worse
    than none: it converts "I skipped it" into "check_apply covered it", and the
    reader has no way to tell which line is the decorative one.

    Pinned against the code in BOTH directions, so the doc cannot drift and neither
    can the tuples: adding a gate to REQUIRED_GATES without listing it here goes red,
    and listing one here that the gate does not require goes red too."""
    unconditional = _gates_in(_self_check_block("requires each of these"))
    assert unconditional == set(check_apply.REQUIRED_GATES), (
        f"the self-check's unconditional list is {sorted(unconditional)} but "
        f"check_apply.REQUIRED_GATES is {sorted(check_apply.REQUIRED_GATES)}")

    conditional = _gates_in(_self_check_block("only when the artifact they read is on disk"))
    assert conditional == set(check_apply.CONDITIONAL_GATES), (
        f"the self-check's conditional list is {sorted(conditional)} but "
        f"check_apply.CONDITIONAL_GATES is {sorted(check_apply.CONDITIONAL_GATES)}")

    not_required = _gates_in(_self_check_block("does NOT require these"))
    assert not_required, "the not-required block names no script at all"
    overlap = not_required & (unconditional | conditional)
    assert not overlap, (
        f"{sorted(overlap)} is listed as both required and not required by "
        f"check_apply.py — one of the two lines is teaching the reader a backstop "
        f"that is not there")
    assert "check_apply" in not_required, (
        "the composer cannot require its own receipt, and the checklist has to say "
        "so — otherwise skipping check_apply.py itself is the one silent skip left")


def test_apply_mode_actually_runs_every_gate_its_own_composer_requires():
    """The other half of the partition, and the one that bites at runtime. A gate
    added to REQUIRED_GATES that modes/apply.md never invokes makes every apply run
    fail its own completion gate — and the mode file is layer 1.5, read on entry,
    so nothing else compares the two lists."""
    text = (ROOT / "modes" / "apply.md").read_text(encoding="utf-8")
    for gate in check_apply.REQUIRED_GATES + check_apply.CONDITIONAL_GATES:
        assert f"scripts/{gate}.py" in text, (
            f"check_apply requires {gate} but modes/apply.md never runs it")


def test_every_conditionally_required_gate_names_its_trigger_file():
    """A conditional line whose trigger is vaguer than the code's is how
    check_word_limits came to be listed as "if application_type: structured" while
    check_apply keyed on nothing at all. The reader must be able to evaluate the
    condition from the checklist alone."""
    block = _self_check_block("only when the artifact they read is on disk")
    for gate, trigger in (("check_letter", "letter.yaml"),
                          ("check_pages", "cv.pdf"),
                          ("check_pages", "tailored-profile.yaml"),
                          ("check_word_limits", "supporting-statement.md")):
        assert gate in block and trigger in block, (
            f"the self-check's {gate} line does not name {trigger}, which is the file "
            f"check_apply.conditional_gates() actually keys on")


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
    # The disclaimer token below WAS 不是对面试或录用概率的预测 — a paraphrase that means
    # the right thing and that check_assessment.py does not match. This test pinned it,
    # so the drift was not merely undetected, it was enforced: layer 1 taught the model a
    # wording the gate rejects. Pin the string the gate actually greps for.
    for token in ("投递建议：", "强烈建议投", "硬性阻断",
                  "不是对结果的预判"):
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
        # Anywhere under scripts/, not only as a direct child. The mode files
        # legitimately cite a test (scripts/tests/…) to name the guard that keeps
        # a documented invariant true, and a guard that cannot express "this file
        # lives in a subdirectory" pushes the author into not naming it at all —
        # which is the opposite of what this check is for.
        if any((ROOT / "scripts").rglob(name)):
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


# ---------------------------------------------------------------------------
# Layer 1 and layer 1.5 deliberately carry some of the same text: spec section 6
# requires the judge-loop rules and the workspace conventions to be inline in
# SKILL.md (nothing reports their absence), and modes/apply.md needs them at the
# point of use. Duplication is the decision. Silent DRIFT between the copies is not.
#
# This is not hypothetical. The required disclaimer had already drifted: SKILL.md
# said 不是对面试或录用概率的预测 while check_assessment.py looks for the literal
# 不是对结果的预判, so a model following layer 1 verbatim failed the gate with
# NO_DISCLAIMER — and the message read as "you forgot it", not "you paraphrased it".
# Nothing caught that, because the two copies had already stopped being identical
# and an exact-match scan only sees the pairs that have not drifted yet.

_MODES = pathlib.Path(ROOT / "modes")


def _paragraphs(path: pathlib.Path) -> list[str]:
    """Whitespace-normalised paragraphs of at least 60 characters. Short lines are
    excluded because headings and one-line list items collide across files for
    reasons that are not duplication."""
    text = path.read_text(encoding="utf-8")
    out = []
    for para in re.split(r"\n\s*\n", text):
        flat = " ".join(para.split())
        if len(flat) >= 60:
            out.append(flat)
    return out


# The number of paragraphs SKILL.md and modes/apply.md carry word-for-word. Spec
# section 6 requires the duplication; this pins its SIZE, which is the only thing that
# moves when a copy drifts.
# 17 since 2026-09-06. The new one is "Reusing a master carries their experience
# forward, never their target", and the duplication is deliberate rather than
# undecided: it guards `meta.target_market`, the field that arms the personal-data
# interlock. SKILL.md is always loaded and apply.md only on mode entry, so a run
# that read layer 1 alone would otherwise inherit a stale market off a saved
# profile with nothing telling it not to — and inheriting `nl` for a US
# application is how a date of birth reaches a CV that US employers bin for
# carrying one.
# 18 since 2026-09-06: "One candidate has one CV per language" joins it. Same
# reasoning as 17 — the rule guards against silent data loss (a Chinese CV
# overwriting an English master), SKILL.md is always loaded and apply.md only on
# mode entry, and a run that read layer 1 alone would write the path by hand.
# 19 since 2026-09-06: "The mechanism is replaceable; the isolation is not" joins
# it. The review loop is called non-negotiable in layer 1, so the sentence saying
# what to do on a host with no subagent tool has to be in layer 1 too — a codex run
# reading only SKILL.md would otherwise hit "dispatch subagents" with no subagents
# and no stated alternative.
SHARED_WITH_APPLY = 26  # includes resolved profile-store lookup guidance


def test_the_paragraphs_layer_1_shares_with_a_mode_file_are_byte_identical():
    """Pinned as a COUNT, and the reason is worth keeping.

    The obvious version of this test — `shared = set(skill) & set(mode); assert shared`
    — cannot detect drift at all. A set intersection is byte-identical by construction,
    so a paragraph that has drifted simply drops OUT of it: the assertion never sees the
    changed text, and every drop moves toward the only condition being checked
    (non-empty). Confirmed by mutating 15 of the 16 shared paragraphs — the whole suite
    stayed green, and `check_skill_lossless` reported 1317/1317 too, because a paragraph
    drifting between two CURRENT files leaves every BASELINE line still present.

    Pinning the count goes red on drift and on deletion, with no threshold to tune and
    no normalisation to get wrong. It does not say WHICH paragraph changed — read the
    diff — but it says that one did, which is the part nothing else could see."""
    skill = _paragraphs(SKILL)
    shared = set(skill) & set(_paragraphs(_MODES / "apply.md"))
    assert len(shared) == SHARED_WITH_APPLY, (
        f"SKILL.md and modes/apply.md now share {len(shared)} word-for-word paragraphs, "
        f"not {SHARED_WITH_APPLY}. FEWER means a copy DRIFTED (or was deleted) — the two "
        f"layers now say different things about the same rule, which is how the required "
        f"disclaimer came to fail its own gate. MORE means new duplication that spec "
        f"section 6 has not decided on. Either way, look at the diff, then update this "
        f"number deliberately.")


@pytest.mark.parametrize("phrase", [
    # Every string a gate matches literally. A paraphrase here passes review and
    # fails the gate, which is the worst combination available.
    "不是对结果的预判",
    "not a forecast of the outcome",
])
def test_a_literally_matched_gate_string_appears_verbatim_in_layer_1(phrase):
    """check_assessment.py greps for these. If SKILL.md shows the model a different
    wording, the model writes the different wording and the gate rejects it."""
    assert phrase in SKILL.read_text(encoding="utf-8"), (
        f"SKILL.md does not contain {phrase!r} verbatim — check_assessment.py matches "
        f"it literally, so layer 1 must show the exact string, not a paraphrase")


def test_layer_1_shows_both_language_shapes_of_the_advice_block():
    """count_coverage.py renders zh and en, check_assessment accepts both markers, and
    the block follows the USER's language. A layer 1 that shows only one shape leaves
    the other language to improvisation, and an improvised block loses the anchor."""
    text = SKILL.read_text(encoding="utf-8")
    for marker in ("投递建议：", "apply verdict:"):
        assert marker in text, f"SKILL.md's advice block is missing the {marker!r} shape"


def test_every_verdict_is_offered_wherever_layer_1_lists_the_verdicts():
    """The FIT SNAPSHOT listed four of five and omitted `blocked` — a legal barrier
    silently downgraded to a weak screen-out, in the one section a model copies from."""
    lines = SKILL.read_text(encoding="utf-8").split("\n")
    for i, line in enumerate(lines):
        if "APPLY VERDICT:" not in line and "apply verdict:" not in line:
            continue
        # A template line may wrap; the continuation carries the rest of the choices.
        window = " ".join(lines[i:i + 2])
        if not any(v in window for v in vocab.VERDICTS):
            continue  # a prose mention, not a template line offering the choices
        missing = [v for v in vocab.VERDICTS if v not in window]
        assert not missing, (
            f"a verdict template line omits {missing}: {line.strip()[:90]}")


def test_skill_md_does_not_credit_a_script_with_a_code_it_never_emits():
    """SKILL.md said `check_apply.py` prints a `NEXT_MODES` notice. It does not,
    and `test_mode_declaration_and_handoff.py` asserts it must not — a gate that
    says what to do next is prompting rather than checking, and an always-on line
    on stdout trains the reader to skip the findings channel.

    So layer 1 described a mechanism that had been deliberately rejected, and a
    reader trusting it would have waited for a notice that never comes. Cheap to
    check mechanically, so it is checked rather than trusted.
    """
    scripts = {p.stem: p.read_text(encoding="utf-8")
               for p in (ROOT / "scripts").glob("*.py")}

    def emitted_by(name):
        """The codes a script can print — its own, plus those of the sibling
        modules it imports.

        A gate that shares a check with another gate emits the code through a
        library: `lint_cv`, `check_letter` and `check_word_limits` all report
        `AI_VOCABULARY`, and the string lives once, in `prose_tells.py`. Reading
        only the gate's own source would have made layer 1 either wrong about
        which gate reports it or forced the message to be copied three times,
        which is the drift the library exists to prevent.
        """
        text = scripts.get(name, "")
        for mod in re.findall(r"^import ([a-z_]+)$", text, re.M):
            if mod in scripts:
                text += scripts[mod]
        return text

    wrong = []
    for line in SKILL.read_text(encoding="utf-8").splitlines():
        named = [n for n in re.findall(r"scripts/([a-z_]+)\.py", line) if n in scripts]
        if not named:
            continue
        # ANY of the scripts the line names, not every one of them. A row that
        # credits a gate AND the library behind it names two scripts, and asking
        # each to carry every code on the line reports the library for the gate's
        # own findings. Where a line names one script — which is the shape of the
        # defect this test was written for, `check_apply.py` credited with a
        # `NEXT_MODES` notice it never prints — any and every are the same test.
        haystack = "".join(emitted_by(n) for n in named)
        for code in re.findall(r"`([A-Z][A-Z0-9_]{4,})`", line):
            if code not in haystack:
                wrong.append(f"{'/'.join(named)} is credited with {code}: "
                             f"{line.strip()[:70]}")
    assert not wrong, "\n  ".join([""] + wrong)
