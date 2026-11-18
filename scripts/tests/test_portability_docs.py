"""The fresh-context route for judges and assessors has to work off Claude Code.

Two ways it broke silently: a `codex exec` line without `--skip-git-repo-check`
refuses to run in any directory that is not a git repository (an installed copy of
the skill, every workspace), and a mode that says only "two `Agent` calls" leaves a
host without that tool no instruction except to assess the round itself.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILL_DOCS = [ROOT / "SKILL.md", *sorted((ROOT / "modes").glob("*.md")),
              *sorted((ROOT / "references").glob("*.md"))]


def test_every_codex_exec_command_skips_the_git_repo_check():
    found = 0
    for path in SKILL_DOCS:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            # A command, not prose naming the tool: `codex exec` followed by a flag or a prompt.
            for m in re.finditer(r"codex exec (?=[-\"$'])(.*)", line):
                found += 1
                assert "--skip-git-repo-check" in m.group(1), (
                    f"{path.name}:{n}: a codex exec command without --skip-git-repo-check "
                    "fails outside a git repository")
    assert found, "no codex exec command found; the check would pass vacuously"


def test_every_mode_that_dispatches_with_agent_names_the_portable_route():
    for path in sorted((ROOT / "modes").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if re.search(r"Dispatch[^\n]*(assessor|judge)", text) or "`Agent` calls" in text:
            assert "references/portability.md" in text, (
                f"{path.name} dispatches assessors or judges but never says how to do it "
                "on a host without the Agent tool")
