"""Education's place on the CV is decided by relevance, not by academic-vs-industry.

MEASURED IN A REAL RUN, 2026-09-01. A late-stage PhD applied to an industry AI
Engineer role. Two rules in this skill pointed opposite ways and neither yielded:

  modes/apply.md      "an industry engineering target leads with Experience
                       even for a PhD"
  cv-craft.md §1      "Early-career / Student (0-3 years experience, OR STILL
                       IN EDUCATION)" -> Education near the top

The candidate was both — still in education AND under three years of formal
industry experience — so both templates fired and the skill offered no tiebreak.
The run followed apply.md, put Education on page two, and the candidate pushed
back with the rule the skill was missing:

  "Education 靠前的真正依据是博士与岗位的相关性，不是学术 vs 工业界."
  (Whether Education leads depends on how RELEVANT the doctorate is to the
   target role, not on whether the employer is academic or industry.)

That is the missing axis. A doctorate in the target role's own field is a
CREDENTIAL a reader is looking for; the same doctorate applied to an unrelated
role is background. The posting in that run named a Master's degree as its first
must-have — and it was on page two.

These tests pin the tiebreak in both files so the contradiction cannot come back
silently, and so neither file can be edited into stating the rule alone.
"""
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[2]
APPLY = (REPO / "modes" / "apply.md").read_text(encoding="utf-8")
CRAFT = (REPO / "references" / "cv-craft.md").read_text(encoding="utf-8")


def _section_order_bullet():
    """The one bullet in apply.md that tells the model where Education goes."""
    for line in APPLY.splitlines():
        if line.strip().startswith("- **Section order:**"):
            return line
    raise AssertionError("modes/apply.md no longer has a `Section order:` bullet")


def test_apply_does_not_state_the_unconditional_industry_rule():
    """"...leads with Experience even for a PhD" with no exception is the half of
    the contradiction that sent a relevant doctorate to page two."""
    bullet = _section_order_bullet()
    phrase = "leads with Experience even for a PhD"
    if phrase not in bullet:
        return                                   # removed outright is also fine
    # It may stay ONLY with its exception attached. Checked by looking at what
    # follows it, not at the punctuation: the first draft of this test demanded a
    # comma and failed on a correct fix that used "*only when*".
    tail = bullet.split(phrase, 1)[1][:160].lower()
    assert re.search(r"\bonly when\b|\bunless\b|\bexcept\b", tail), (
        f"apply.md states the unconditional rule. A PhD in the target role's own "
        f"field is a credential, not background — the sentence needs its "
        f"exception attached. What follows it: {tail[:80]!r}")


def test_apply_names_relevance_as_the_deciding_factor():
    bullet = _section_order_bullet()
    assert "relevan" in bullet.lower(), (
        "the Section order bullet must say that the degree's RELEVANCE to the "
        "target role decides where Education goes")
    assert "cv-craft.md" in bullet, "it must route to the full rule"


def test_cv_craft_carries_the_tiebreak_for_a_candidate_matching_two_templates():
    """§1's three templates overlap: a PhD candidate is 'still in education' AND
    may be applying to industry. Whichever way that resolves, it must be
    WRITTEN, because the model reading it has to pick one."""
    assert "### Deciding between the templates" in CRAFT, (
        "cv-craft.md §1 needs the block that resolves a candidate matching more "
        "than one template")
    block = CRAFT.split("### Deciding between the templates")[1].split("\n## ")[0]
    for needed in ("relevan", "still in education"):
        assert needed in block.lower(), f"the tiebreak never mentions {needed!r}"
    assert len(block.split()) > 80, (
        "a tiebreak this short is a restatement, not a rule someone can apply")


def test_the_tiebreak_covers_both_directions():
    """A rule that only says when to promote Education is half a rule — the
    case that sends it down the page has to be written too, or every PhD gets
    Education first regardless of the target."""
    block = CRAFT.split("### Deciding between the templates")[1].split("\n## ")[0].lower()
    assert "not relevant" in block or "unrelated" in block, (
        "the tiebreak must say what happens when the degree is NOT in the "
        "target role's domain")
    assert re.search(r"\b(3|three)\+?\s*(\+|or more)?\s*years?", block), (
        "the tiebreak must name the experience threshold at which Education "
        "moves down regardless of relevance")


def test_the_two_files_do_not_contradict_each_other():
    """The whole point. Both must decide on the same inputs."""
    bullet = _section_order_bullet().lower()
    block = CRAFT.split("### Deciding between the templates")[1].split("\n## ")[0].lower()
    for axis in ("relevan",):
        assert axis in bullet and axis in block, (
            f"{axis!r} decides this in one file and not the other — that is the "
            f"same divergence, moved")
