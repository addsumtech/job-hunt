"""Weekly digest, task 6: the procedure, the narrowed source policy, the wiring."""
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_policy_red_line_is_unchanged_and_has_no_digest_exception():
    # Revision 2026-11-02: the digest runs with the user present, so no exception.
    red = read("references/source-policy.md").split("## Red", 1)[1].split("\n## ", 1)[0]
    assert "- Background or unattended operation while the user is not present.\n" in red
    assert "weekly-digest" not in read("references/source-policy.md")


def test_procedure_says_the_user_is_present():
    text = read("references/weekly-digest.md")
    assert "present" in text and "Run now" in text and "LinkedIn" in text


def test_procedure_names_every_step():
    text = read("references/weekly-digest.md")
    for anchor in ("## Setup", "## The run", "digest.py tick", "digest.py inbox", "--unreadable",
                   "digest.py compose", "check_digest.py", "digest.py sent", "deliver-file",
                   "digest.py install", "digest.py cancel", "digest.py pause", "digest.py presend",
                   "digest.py status", "send-failed", "nothing is sent", "digest-picks.yaml",
                   "digest-sources.yaml", "five"):
        assert anchor in text, anchor


def test_skill_and_discover_point_to_the_procedure():
    assert "references/weekly-digest.md" in read("SKILL.md")
    assert "references/weekly-digest.md" in read("modes/discover.md")
    assert "check_digest.py" in read("references/workflow-checklist.md")


def test_documented_digest_subcommands_exist():
    help_text = subprocess.run([sys.executable, str(ROOT / "scripts" / "digest.py"), "--help"],
                               capture_output=True, text=True, encoding="utf-8").stdout
    documented = set(re.findall(r"digest\.py ([a-z][a-z-]+)", read("references/weekly-digest.md")))
    for sub in documented:
        assert f"digest.py {sub} " in help_text, sub


def test_the_digest_is_opt_in_and_says_what_it_needs():
    text = read("references/weekly-digest.md")
    section = text.split("## Before offering it", 1)[1].split("\n## ", 1)[0]
    for need in ("email tool", "send and search", "macOS", "consent", "present", "Monday", "yes"):
        assert need in section, need
    assert "never set it up" in section.lower()
    handoff = read("modes/discover.md").split("## Hand the artifacts over", 1)[1].split("\n## ", 1)[0]
    assert "weekly-digest.md" in handoff and "optional" in handoff
